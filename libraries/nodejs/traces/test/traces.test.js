// This file contains traces test logic for traces test.
const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const originalEnv = { ...process.env };
const instrumentationPath = path.resolve(__dirname, "../dist/traceInstrumentation.js");
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
      || key === "TRACEID_RATIO_BASED_SAMPLER"
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

test("readExporterParameters prefers configured JSON and falls back to OTEL trace env vars", () => {
  resetEnv({
    OTEL_BACKEND_EXPORTERS: "console",
    OTEL_EXPORTER_PARAMETERS: JSON.stringify({
      otel: { trace: { url: "https://collector.example.com/v1/traces" } },
    }),
    OTEL_EXPORTER_OTLP_ENDPOINT: "https://fallback.example.com",
  });

  const { readExporterParameters } = freshRequire(utilsPath);
  assert.deepEqual(readExporterParameters(), {
    otel: { trace: { url: "https://collector.example.com/v1/traces" } },
  });

  resetEnv({
    OTEL_BACKEND_EXPORTERS: "console",
    OTEL_EXPORTER_OTLP_ENDPOINT: "https://collector.example.com/",
  });

  delete require.cache[require.resolve(utilsPath)];
  assert.deepEqual(freshRequire(utilsPath).readExporterParameters(), {
    otel: { trace: { url: "https://collector.example.com/v1/traces" } },
  });
});

test("isExporterParametersEmpty detects empty and populated trace configs", () => {
  const { isExporterParametersEmpty } = freshRequire(utilsPath);
  assert.equal(isExporterParametersEmpty(undefined), true);
  assert.equal(isExporterParametersEmpty({}), true);
  assert.equal(isExporterParametersEmpty({ otel: { trace: {} } }), true);
  assert.equal(isExporterParametersEmpty({ otel: { trace: { url: "https://x/v1/traces" } } }), false);
});

test("orgId resolves from X_ORG_ID, else undefined", () => {
  resetEnv({ OTEL_BACKEND_EXPORTERS: "console", X_ORG_ID: "org-from-env" });
  assert.equal(freshRequire(utilsPath).orgId(), "org-from-env");

  resetEnv({ OTEL_BACKEND_EXPORTERS: "console" });
  delete require.cache[require.resolve(utilsPath)];
  assert.equal(freshRequire(utilsPath).orgId(), undefined);
});

test("configuration parsers trim values and reject empty arrays", () => {
  resetEnv({ OTEL_BACKEND_EXPORTERS: "console" });
  const { parseStringArray, parseResourceAttributes } = freshRequire(instrumentationPath);

  const fallback = ["console"];
  const parsedFallback = parseStringArray(undefined, fallback);
  parsedFallback.push("otel");
  assert.deepEqual(fallback, ["console"]);

  assert.deepEqual(parseStringArray('["console", " otel "]', ["x"]), ["console", "otel"]);
  assert.deepEqual(parseStringArray("console, otel", ["x"]), ["console", "otel"]);
  assert.deepEqual(
    parseResourceAttributes("service.name=orders,empty=,deployment.environment=dev"),
    { "service.name": "orders", "deployment.environment": "dev" },
  );
});

test("runtime resource attributes identify Azure Functions, AKS and Container Apps", () => {
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

  resetEnv({
    OTEL_BACKEND_EXPORTERS: "console",
    KUBERNETES_SERVICE_HOST: "10.0.0.1",
    K8S_CLUSTER_NAME: "cloudops-dev",
    POD_NAMESPACE: "cloudops",
    HOSTNAME: "orders-pod",
    CONTAINER_NAME: "orders",
  });
  delete require.cache[require.resolve(instrumentationPath)];

  const { addRuntimeResourceAttributes: addKubernetesAttributes } = freshRequire(instrumentationPath);
  const kubernetesAttributes = {};
  addKubernetesAttributes(kubernetesAttributes);
  assert.equal(kubernetesAttributes["cloud.provider"], "azure");
  assert.equal(kubernetesAttributes["cloud.platform"], "azure_aks");
  assert.equal(kubernetesAttributes["k8s.cluster.name"], "cloudops-dev");
  assert.equal(kubernetesAttributes["k8s.namespace.name"], "cloudops");
  assert.equal(kubernetesAttributes["k8s.pod.name"], "orders-pod");
  assert.equal(kubernetesAttributes["container.name"], "orders");

  resetEnv({ OTEL_BACKEND_EXPORTERS: "console", CONTAINER_APP_NAME: "orders-ca" });
  delete require.cache[require.resolve(instrumentationPath)];
  const { addRuntimeResourceAttributes: addCaAttributes } = freshRequire(instrumentationPath);
  const caAttributes = {};
  addCaAttributes(caAttributes);
  assert.equal(caAttributes["cloud.platform"], "azure_container_apps");
  assert.equal(caAttributes["container.name"], "orders-ca");
});

test("tracer starts a basic span and exports without an OTLP exporter", async () => {
  resetEnv({ OTEL_BACKEND_EXPORTERS: "console", OTEL_SERVICE_NAME: "orders-api" });
  const { tracer } = freshRequire(instrumentationPath);

  const span = tracer.startBasicSpan("manual-span");
  assert.ok(span, "expected a span to be returned when console exporter is active");
  span.end();

  await tracer.exportSpans();
});

test("startAzureSpan builds a service span from the Service Bus topic extension", () => {
  resetEnv({ OTEL_BACKEND_EXPORTERS: "console", OTEL_SERVICE_NAME: "orders-api" });
  const { tracer } = freshRequire(instrumentationPath);

  const span = tracer.startAzureSpan("servicebustopic", {
    serviceBusTopicAttributes: { topicName: "orders-topic" },
  });
  assert.ok(span, "expected a Service Bus topic service span");
  span.end();
});

test("startAzureSpan returns undefined for an unknown service", () => {
  resetEnv({ OTEL_BACKEND_EXPORTERS: "console", OTEL_SERVICE_NAME: "orders-api" });
  const { tracer } = freshRequire(instrumentationPath);

  assert.equal(tracer.startAzureSpan("unknown-service", {}), undefined);
});

test("startAzureSpan builds a span for every supported Azure service", () => {
  resetEnv({ OTEL_BACKEND_EXPORTERS: "console", OTEL_SERVICE_NAME: "orders-api" });
  const { tracer } = freshRequire(instrumentationPath);

  const cases = [
    ["servicebusqueue", { serviceBusQueueAttributes: { queueName: "orders-queue" } }],
    ["eventhubs", { eventHubsAttributes: { eventHubName: "orders-hub", partitionKey: "p1" } }],
    ["cosmosdb", { cosmosDbAttributes: { containerName: "orders", operation: "Upsert" } }],
    ["cosmosgremlin", { cosmosGremlinAttributes: { databaseName: "orders", graphName: "g" } }],
    ["dataexplorer", { dataExplorerAttributes: { databaseName: "orders-db", tableName: "events" } }],
    ["eventgrid", { eventGridAttributes: { topicName: "orders-topic", source: "orders" } }],
    ["blobstorage", { blobStorageAttributes: { containerName: "orders-blobs", blobName: "o/1" } }],
    ["apimanagement", { apiManagementAttributes: { apiName: "orders-api", httpMethod: "POST", path: "/orders" } }],
    ["functions", { functionsAttributes: { functionName: "orders-fn", triggerType: "http" } }],
  ];

  for (const [service, props] of cases) {
    const span = tracer.startAzureSpan(service, props);
    assert.ok(span, `expected a span for ${service}`);
    span.end();
  }
});

test("tracer records errors, sets active context, and propagates trace attributes", () => {
  resetEnv({ OTEL_BACKEND_EXPORTERS: "console", OTEL_SERVICE_NAME: "orders-api" });
  const { tracer } = freshRequire(instrumentationPath);

  const span = tracer.startBasicSpan("root", { setActiveContext: true });
  assert.ok(span);

  tracer.setAttributes(span, "single-attribute");
  tracer.setActiveContext(span);
  tracer.recordError(new Error("boom"), span);

  const traceAttrs = tracer.fetchTraceAttrs();
  assert.equal(typeof traceAttrs, "object");

  // Round-trips through extract without throwing (W3C tracecontext carrier).
  tracer.extractTraceAttrs({ traceparent: "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01" });

  span.end();
});

test("Service Bus extensions inject and retrieve W3C propagation attributes", () => {
  resetEnv({ OTEL_BACKEND_EXPORTERS: "console", OTEL_SERVICE_NAME: "orders-api" });
  const { tracer } = freshRequire(instrumentationPath);
  const { ServiceBusTopicServiceExtension } = freshRequire(
    path.resolve(__dirname, "../dist/services/ServiceBusTopicServiceExtension.js"),
  );
  const { ServiceBusQueueServiceExtension } = freshRequire(
    path.resolve(__dirname, "../dist/services/ServiceBusQueueServiceExtension.js"),
  );

  const span = tracer.startBasicSpan("propagation-root", { setActiveContext: true });

  const topic = new ServiceBusTopicServiceExtension();
  const topicAttrs = topic.requestPropagationAttributes(span);
  assert.equal(typeof topicAttrs, "object");
  assert.deepEqual(
    topic.retrievePropagationAttributes({ applicationProperties: { traceparent: "tp-1", tracestate: "ts-1" } }),
    { traceparent: "tp-1", tracestate: "ts-1" },
  );

  const queue = new ServiceBusQueueServiceExtension();
  const queueAttrs = queue.requestPropagationAttributes(span);
  assert.equal(typeof queueAttrs, "object");
  assert.deepEqual(
    queue.retrievePropagationAttributes({ applicationProperties: { traceparent: "tp-2" } }),
    { traceparent: "tp-2" },
  );

  span?.end();
});

test("service registry gates propagation to supported services", () => {
  resetEnv({ OTEL_BACKEND_EXPORTERS: "console", OTEL_SERVICE_NAME: "orders-api" });
  freshRequire(instrumentationPath);
  const { ServicesExtensions } = freshRequire(path.resolve(__dirname, "../dist/services/serviceExtensions.js"));

  const registry = new ServicesExtensions();
  assert.deepEqual(registry.requestPreSpanHook("unknown", {}), {});
  // cosmosdb is not a valid propagation service, so it is gated out.
  assert.equal(registry.requestPropagationAttributes({}, "cosmosdb"), undefined);
  assert.equal(registry.retrievePropagationAttributes({}, "cosmosdb"), undefined);
});
