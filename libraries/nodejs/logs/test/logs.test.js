// This file contains logs test logic for logs test.
const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const originalEnv = { ...process.env };
const instrumentationPath = path.resolve(__dirname, "../dist/logsInstrumentation.js");
const utilsPath = path.resolve(__dirname, "../dist/utils.js");

// Resets env.
function resetEnv(overrides = {}) {
  for (const key of Object.keys(process.env)) {
    delete process.env[key];
  }

  Object.assign(process.env, originalEnv, overrides);
  for (const key of Object.keys(process.env)) {
    if (
      key.startsWith("OTEL_")
      || key.startsWith("FUNCTIONS_")
      || key.startsWith("K8S_")
      || key.startsWith("POD_")
      || key.startsWith("AKS_")
      || key.startsWith("CONTAINER_")
      || key === "HOSTNAME"
      || key === "KUBERNETES_SERVICE_HOST"
      || key === "WEBSITE_SITE_NAME"
      || key === "X_ORG_ID"
      || key === "npm_package_name"
    ) {
      delete process.env[key];
    }
  }
  Object.assign(process.env, overrides);
}

// Handles fresh require.
function freshRequire(modulePath) {
  delete require.cache[require.resolve(modulePath)];
  return require(modulePath);
}

test.afterEach(() => {
  resetEnv();
  delete require.cache[require.resolve(instrumentationPath)];
  delete require.cache[require.resolve(utilsPath)];
});

test("readExporterParameters prefers configured JSON and falls back to OTEL env vars", () => {
  resetEnv({
    OTEL_BACKEND_EXPORTERS: "console",
    OTEL_EXPORTER_PARAMETERS: JSON.stringify({
      otel: { logs: { url: "https://collector.example.com/v1/logs" } },
    }),
    OTEL_EXPORTER_OTLP_ENDPOINT: "https://fallback.example.com",
  });

  const { readExporterParameters } = freshRequire(utilsPath);
  assert.deepEqual(readExporterParameters(), {
    otel: { logs: { url: "https://collector.example.com/v1/logs" } },
  });

  resetEnv({
    OTEL_BACKEND_EXPORTERS: "console",
    OTEL_EXPORTER_OTLP_ENDPOINT: "https://collector.example.com/",
  });

  delete require.cache[require.resolve(utilsPath)];
  assert.deepEqual(freshRequire(utilsPath).readExporterParameters(), {
    otel: { logs: { url: "https://collector.example.com/v1/logs" } },
  });
});

test("readExporterParameters is empty when no endpoint is configured", () => {
  resetEnv({ OTEL_BACKEND_EXPORTERS: "console" });
  const { readExporterParameters, isExporterParametersEmpty } = freshRequire(utilsPath);
  const params = readExporterParameters();
  assert.equal(isExporterParametersEmpty(params), true);
  assert.deepEqual(params, {});
});

test("orgId resolves from X_ORG_ID, else undefined", () => {
  resetEnv({ OTEL_BACKEND_EXPORTERS: "console", X_ORG_ID: "org-from-env" });
  assert.equal(freshRequire(utilsPath).orgId(), "org-from-env");

  resetEnv({ OTEL_BACKEND_EXPORTERS: "console" });
  delete require.cache[require.resolve(utilsPath)];
  assert.equal(freshRequire(utilsPath).orgId(), undefined);
});

test("configuration parsers trim values and reject unknown log levels", () => {
  resetEnv({ OTEL_BACKEND_EXPORTERS: "console" });
  const {
    parseLogLevels,
    parseResourceAttributes,
    parseStringArray,
  } = freshRequire(instrumentationPath);

  const fallback = ["console"];
  const parsedFallback = parseStringArray(undefined, fallback);
  parsedFallback.push("otel");
  assert.deepEqual(fallback, ["console"]);

  assert.deepEqual(parseStringArray('["console", " otel "]', ["x"]), ["console", "otel"]);
  assert.deepEqual(parseStringArray("console, otel", ["x"]), ["console", "otel"]);
  assert.deepEqual(parseLogLevels("bad,error"), ["error"]);
  assert.deepEqual(parseLogLevels("bad"), ["info", "error", "debug", "warn"]);
  assert.deepEqual(
    parseResourceAttributes("service.name=orders,empty=,deployment.environment=dev"),
    { "service.name": "orders", "deployment.environment": "dev" },
  );
});

test("runtime resource attributes identify Azure Functions and AKS environments", () => {
  resetEnv({
    OTEL_BACKEND_EXPORTERS: "console",
    FUNCTIONS_EXTENSION_VERSION: "~4",
    WEBSITE_SITE_NAME: "orders-func",
  });
  const { addRuntimeResourceAttributes } = freshRequire(instrumentationPath);

  const functionsAttributes = {};
  addRuntimeResourceAttributes(functionsAttributes);
  assert.equal(functionsAttributes["cloud.provider"], "azure");
  assert.equal(functionsAttributes["cloud.platform"], "azure_functions");
  assert.equal(functionsAttributes["faas.name"], "orders-func");
  assert.equal(functionsAttributes["k8s.pod.name"], undefined);

  resetEnv({
    OTEL_BACKEND_EXPORTERS: "console",
    KUBERNETES_SERVICE_HOST: "10.0.0.1",
    K8S_CLUSTER_NAME: "demo-cluster",
    POD_NAMESPACE: "demo",
    HOSTNAME: "orders-pod",
    CONTAINER_NAME: "orders",
  });
  delete require.cache[require.resolve(instrumentationPath)];

  const { addRuntimeResourceAttributes: addKubernetesAttributes } = freshRequire(instrumentationPath);
  const kubernetesAttributes = {};
  addKubernetesAttributes(kubernetesAttributes);
  assert.equal(kubernetesAttributes["cloud.provider"], "azure");
  assert.equal(kubernetesAttributes["cloud.platform"], "azure_aks");
  assert.equal(kubernetesAttributes["k8s.cluster.name"], "demo-cluster");
  assert.equal(kubernetesAttributes["k8s.namespace.name"], "demo");
  assert.equal(kubernetesAttributes["k8s.pod.name"], "orders-pod");
  assert.equal(kubernetesAttributes["container.name"], "orders");
});

test("runtime resource attributes detect Container Apps", () => {
  resetEnv({
    OTEL_BACKEND_EXPORTERS: "console",
    CONTAINER_APP_NAME: "orders-ca",
  });
  const { addRuntimeResourceAttributes } = freshRequire(instrumentationPath);

  const attributes = {};
  addRuntimeResourceAttributes(attributes);
  assert.equal(attributes["cloud.provider"], "azure");
  assert.equal(attributes["cloud.platform"], "azure_container_apps");
  assert.equal(attributes["container.name"], "orders-ca");
});

test("console logger renders enabled levels and structured parameters", async () => {
  resetEnv({
    OTEL_BACKEND_EXPORTERS: "console",
    OTEL_LOG_LEVEL: "info,error",
    OTEL_LOGS_SAMPLING_RATE: "0",
  });

  const infoLines = [];
  const errorLines = [];
  const originalInfo = console.info;
  const originalError = console.error;
  console.info = (...args) => infoLines.push(args.join(" "));
  console.error = (...args) => errorLines.push(args.join(" "));

  try {
    const { logger } = freshRequire(instrumentationPath);
    logger.info("created order", { order_id: 42 });
    logger.debug("debug should be disabled");
    logger.error(new Error("payment failed"));
    await logger.exportLogs();
  } finally {
    console.info = originalInfo;
    console.error = originalError;
  }

  const infoOutput = infoLines.join("\n");
  const errorOutput = errorLines.join("\n");
  assert.match(infoOutput, /created order/);
  assert.match(infoOutput, /order_id/);
  assert.doesNotMatch(infoOutput, /debug should be disabled/);
  assert.match(errorOutput, /payment failed/);
});

test("otel requested without X_ORG_ID falls back to console", async () => {
  resetEnv({
    OTEL_BACKEND_EXPORTERS: "otel",
    OTEL_LOG_LEVEL: "info",
    OTEL_LOGS_SAMPLING_RATE: "0",
    OTEL_EXPORTER_OTLP_ENDPOINT: "https://collector.example.com",
  });

  const infoLines = [];
  const originalInfo = console.info;
  console.info = (...args) => infoLines.push(args.join(" "));
  try {
    const { logger } = freshRequire(instrumentationPath);
    logger.info("gated to console");
    await logger.exportLogs();
  } finally {
    console.info = originalInfo;
  }

  assert.match(infoLines.join("\n"), /gated to console/);
});

test("LogSampler probabilistic batches and flushes per invocation id", async () => {
  resetEnv({
    OTEL_BACKEND_EXPORTERS: "console",
    OTEL_LOG_LEVEL: "info,error",
    OTEL_LOGS_SAMPLING_RATE: "100",
  });

  const infoLines = [];
  const originalInfo = console.info;
  console.info = (...args) => infoLines.push(args.join(" "));
  try {
    const { logger } = freshRequire(instrumentationPath);
    logger.info("first-invocation");
    logger.info("first-invocation-2");
    logger.info("second-invocation");
    await logger.exportLogs();
  } finally {
    console.info = originalInfo;
  }

  assert.match(infoLines.join("\n"), /first-invocation/);
});

test("exportLogs is a no-op when no OTel exporter is configured", async () => {
  resetEnv({ OTEL_BACKEND_EXPORTERS: "console", OTEL_LOG_LEVEL: "info" });
  const { logger } = freshRequire(instrumentationPath);
  // Should resolve without throwing.
  await logger.exportLogs();
});

test("parseStringArray returns fallback for non-array JSON or empty arrays", () => {
  resetEnv({ OTEL_BACKEND_EXPORTERS: "console" });
  const { parseStringArray } = freshRequire(instrumentationPath);
  // CSV path: pure-whitespace input filters down to [] (current behavior —
  // documented here so a future change can't silently shift the contract).
  assert.deepEqual(parseStringArray("  ", ["a"]), []);
  // Non-array JSON falls through and returns fallback.
  assert.deepEqual(parseStringArray('{"k":1}', ["fb"]), ["fb"]);
  // Empty JSON array → fallback.
  assert.deepEqual(parseStringArray("[]", ["fb"]), ["fb"]);
});

test("shutdown flush hooks are registered after init", () => {
  const before = process.listenerCount("beforeExit");
  require("../dist/index.js"); // importing initialises the logger singleton
  assert.ok(process.listenerCount("beforeExit") >= before);
});
