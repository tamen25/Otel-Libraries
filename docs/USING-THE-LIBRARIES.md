# Using the CloudOps OTel Libraries

This guide is for **application developers** who want to add CloudOps logging
and tracing to a service. You install one (or two) packages from your private
registry, set a few `OTEL_*` environment variables, and call the logger — the
library handles OpenTelemetry setup, Azure runtime detection, batching,
sampling, W3C trace propagation, and OTLP export for you.

All four language ports implement the **same design and the same `OTEL_*`
environment-variable contract**, so behaviour is identical across runtimes.

---

## 1. What's available

Two signals are shipped today — **logs** and **traces** — for four languages.
Each is a separate package so you can adopt them independently.

| Language | Logs package | Traces package | Runtime |
|----------|--------------|----------------|---------|
| Python   | `cloudops-otel-logs`      | `cloudops-otel-traces`      | Python ≥ 3.11 |
| Java     | `com.cloudops:otel-logs`  | `com.cloudops:otel-traces`  | Java 21 |
| .NET     | `CloudOps.Otel.Logs`      | `CloudOps.Otel.Traces`      | net8.0 |
| Node.js  | `@cloudops/otel-logs`     | `@cloudops/otel-traces`     | Node ≥ 18 |

All packages are currently at version **`0.1.0`**.

> **Metrics** and other signals are future work and follow the same shape
> (`<language>/<signal>`).

---

## 2. Install from your private registry

The packages are published to a private registry (Nexus / Azure Artifacts /
CodeArtifact — anything that speaks the native protocol for each ecosystem).
Point your package manager at the feed, authenticate, then install as usual.
Replace `https://registry.example.com/...` and the credentials with your feed's
real values.

### Python (pip / PyPI feed)

`pip.conf` (Linux/macOS: `~/.pip/pip.conf`; Windows: `%APPDATA%\pip\pip.ini`):

```ini
[global]
index-url = https://<user>:<token>@registry.example.com/repository/pypi/simple
```

Then:

```bash
pip install cloudops-otel-logs cloudops-otel-traces
```

Or pin in `pyproject.toml` / `requirements.txt`:

```
cloudops-otel-logs==0.1.0
cloudops-otel-traces==0.1.0
```

### Java (Maven)

Add the repository and dependencies to your `pom.xml` (credentials go in
`~/.m2/settings.xml` under a matching `<server><id>cloudops</id>…</server>`):

```xml
<repositories>
  <repository>
    <id>cloudops</id>
    <url>https://registry.example.com/repository/maven</url>
  </repository>
</repositories>

<dependencies>
  <dependency>
    <groupId>com.cloudops</groupId>
    <artifactId>otel-logs</artifactId>
    <version>0.1.0</version>
  </dependency>
  <dependency>
    <groupId>com.cloudops</groupId>
    <artifactId>otel-traces</artifactId>
    <version>0.1.0</version>
  </dependency>
</dependencies>
```

### .NET (NuGet)

Add the feed to a `nuget.config` next to your solution (credentials via
`<packageSourceCredentials>` or `dotnet nuget add source ... -u ... -p ...`):

```xml
<configuration>
  <packageSources>
    <add key="cloudops" value="https://registry.example.com/repository/nuget/index.json" />
  </packageSources>
</configuration>
```

Then:

```bash
dotnet add package CloudOps.Otel.Logs --version 0.1.0
dotnet add package CloudOps.Otel.Traces --version 0.1.0
```

### Node.js (npm)

Scope the `@cloudops` packages to your registry in `.npmrc`:

```ini
@cloudops:registry=https://registry.example.com/repository/npm/
//registry.example.com/repository/npm/:_authToken=${NPM_TOKEN}
```

Then:

```bash
npm install @cloudops/otel-logs @cloudops/otel-traces
```

---

## 3. Quick start — logging

Set `OTEL_SERVICE_NAME` for every service. With **no other configuration** the
logger writes to the console; set the OTLP variables (section 5) to ship logs to
your collector. The API in each language:

### Python

```python
from cloudops_otel_logs import logger

logger.info("order created", {"order_id": order_id})
logger.warn("retrying downstream call", {"attempt": 2})
logger.error(exc)                     # pass an exception or a message
logger.export_logs()                  # flush the current batch
```

### Java

```java
import com.cloudops.otel.logs.CloudOpsLogger;

final CloudOpsLogger logger = CloudOpsLogger.initialiseLogger();

logger.info("order created", "order_id", orderId);   // key/value varargs
logger.warn("retrying downstream call", "attempt", 2);
logger.error(exception);
logger.exportLogs();                                  // flush
```

### .NET

```csharp
using CloudOps.Otel.Logs;

var logger = CloudOpsLogger.InitialiseLogger();

logger.Info("order created", orderId);
logger.Warn("retrying downstream call", attempt);
logger.Error(exception);
logger.ExportLogs();                  // flush
```

### Node.js / TypeScript

```ts
import { logger } from "@cloudops/otel-logs";

logger.info("order created", { orderId });
logger.warn("retrying downstream call", { attempt: 2 });
logger.error(error);
await logger.exportLogs();             // flush
```

**Levels** are `info` / `warn` / `error` / `debug`, plus a generic
`log(level, message, …)`. Batches are keyed by invocation; a batch is always
emitted if it contains an `error`, otherwise it is sampled at
`OTEL_LOGS_SAMPLING_RATE`.

---

## 4. Quick start — tracing

Tracing is designed so **cross-service context propagation is automatic**: the
library registers the W3C `tracecontext` propagator and HTTP auto-instrumentation
(Python Flask + requests, .NET ASP.NET Core + HttpClient, Node.js HTTP). Java
uses the raw JDK HTTP server/client so it wires spans in two explicit calls.
A request flowing through several services stays **one connected trace**, and
logs emitted inside an active span automatically carry its `trace_id`.

### Python (Flask)

```python
from flask import Flask
from cloudops_otel_traces import init_tracing

app = Flask(__name__)
init_tracing(app)   # instruments Flask + requests; nothing else to do
```

### .NET (ASP.NET Core)

```csharp
using CloudOps.Otel.Traces;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddCloudOpsTracing();   // ASP.NET Core + HttpClient auto-instrumented
var app = builder.Build();
```

### Node.js — import the traces package first

Require/import `@cloudops/otel-traces` **before** your HTTP server/framework so
its HTTP instrumentation hooks in. After that, incoming and outgoing HTTP is
traced with no manual code:

```ts
import "@cloudops/otel-traces";        // registers HTTP auto-instrumentation + W3C propagator
import { logger } from "@cloudops/otel-logs";
// ... your http server; spans + propagation happen automatically
```

For manual or Azure-service-aware spans:

```ts
import { tracer, AzureService } from "@cloudops/otel-traces";

const span = tracer.startBasicSpan("handle-order");
try {
  // ... work ...
} catch (error) {
  tracer.recordError(error, span);
} finally {
  span?.end();
  await tracer.exportSpans();
}

const busSpan = tracer.startAzureSpan(AzureService.SERVICE_BUS_TOPIC, {
  serviceBusTopicAttributes: { topicName: "orders", namespace: "cloudops" },
});
busSpan?.end();
```

### Java — manual server/client spans

The JDK HTTP server/client aren't auto-instrumented, so continue the incoming
trace and inject context on the outgoing call yourself:

```java
import com.cloudops.otel.traces.CloudOpsTracer;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.context.Scope;

CloudOpsTracer tracer = CloudOpsTracer.initializeTracer();

// Continue the caller's trace from the incoming request headers (lower-cased):
Span span = tracer.startServerSpan("GET /process", incomingHeaders);
try (Scope scope = span.makeCurrent()) {
  // ... work; logs here carry the trace id ...
  Span client = tracer.startClientSpan("GET /finalize");   // forms a service-graph edge
  try (Scope cs = client.makeCurrent()) {
    tracer.injectHeaders().forEach(request::header);        // propagate W3C context
    // ... send the downstream request ...
  } finally {
    client.end();
  }
} finally {
  span.end();
  tracer.exportSpans();
}
```

---

## 5. Configuration — the `OTEL_*` contract

Every port reads the same environment variables. Nothing here is a secrets file;
values come from the environment (or the `DEFAULT_*` constants baked into each
library — see section 6).

| Variable | Applies to | Meaning |
|----------|-----------|---------|
| `OTEL_SERVICE_NAME` | both | `service.name` on every record. **Set this in every app.** |
| `OTEL_RESOURCE_ATTRIBUTES` | both | Extra resource attrs, e.g. `deployment.environment=prod,team=payments`. Merged in. |
| `OTEL_BACKEND_EXPORTERS` | both | `console` (default) or `otel` (OTLP/HTTP). JSON array or CSV. |
| `OTEL_LOG_LEVEL` | logs | Enabled levels among `info,error,debug,warn`. |
| `OTEL_LOGS_SAMPLING_RATE` | logs | `0`–`100` (default `100` = emit everything). Errors are always emitted. |
| `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT` / `OTEL_EXPORTER_OTLP_ENDPOINT` | logs | OTLP endpoint (plain endpoint is normalised to `/v1/logs`). |
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` / `OTEL_EXPORTER_OTLP_ENDPOINT` | traces | OTLP endpoint (normalised to `/v1/traces`). |
| `OTEL_EXPORTER_PARAMETERS` | both | Inline JSON exporter config: `{"otel":{"logs":{"url":"…"},"trace":{"url":"…"}}}`. |
| `X_ORG_ID` | both | **Auth key.** Sent as the `X-OrgId` header on every OTLP export. Required for `otel`. |

**Node.js-only extras** (traces): `TRACEID_RATIO_BASED_SAMPLER` (root sampler
ratio, default `1`) and `ENABLE_OTEL_DEBUG_LOGS=true` (verbose diagnostics).

Minimal production-style setup to ship to a collector:

```bash
export OTEL_SERVICE_NAME=payments-api
export OTEL_BACKEND_EXPORTERS=otel
export OTEL_EXPORTER_OTLP_ENDPOINT=https://otel.example.com
export X_ORG_ID=<your-org-id>
```

---

## 6. How export is gated (`otel` vs `console`)

The OTLP exporter is used **only when both**:

1. an **endpoint URL** resolves (from `OTEL_EXPORTER_PARAMETERS`, then the
   `OTEL_EXPORTER_OTLP_*` vars, then the `DEFAULT_*_ENDPOINT` constant), **and**
2. **`X_ORG_ID`** resolves (from the env var or the `DEFAULT_X_ORG_ID` constant).

If either is missing — or the OpenTelemetry SDK isn't available — the library
**falls back to console**. `X_ORG_ID` is mandatory for OTLP; there is no other
auth source, and no Bearer/api-key path.

If you don't want consumers to set env vars, bake defaults into the library's
constants (endpoint + org id) before publishing:

| Language | Where |
|----------|-------|
| Python   | `DEFAULT_LOGS_ENDPOINT` / `DEFAULT_TRACES_ENDPOINT` / `DEFAULT_X_ORG_ID` (top of `logger.py` / traces module) |
| Java     | `DEFAULT_LOGS_ENDPOINT` / `DEFAULT_X_ORG_ID` in `LogsConfiguration` (traces equivalents in the traces config) |
| .NET     | `DefaultLogsEndpoint` / `DefaultTracesEndpoint` / `DefaultXOrgId` in `LogsConfiguration` |
| Node.js  | `DEFAULT_LOGS_ENDPOINT` / `DEFAULT_TRACES_ENDPOINT` / `DEFAULT_X_ORG_ID` in `src/utils.ts` |

> Baking a real `X_ORG_ID` into source commits a credential to the repo. Prefer
> supplying it via `X_ORG_ID` at deploy time; only hardcode a non-sensitive
> default. See the [security notes](#8-security-notes).

---

## 7. Azure runtime auto-detection & correlation

Set `OTEL_SERVICE_NAME` and the library derives the rest. It auto-detects the
Azure runtime from environment hints and adds `cloud.provider=azure` plus a
`cloud.platform`:

| Runtime | Detected from | `cloud.platform` |
|---------|---------------|------------------|
| Azure Functions | `FUNCTIONS_EXTENSION_VERSION` / `FUNCTIONS_WORKER_RUNTIME` (+ `WEBSITE_SITE_NAME`→`faas.name`) | `azure_functions` |
| Container Apps | `CONTAINER_APP_NAME` | `azure_container_apps` |
| App Service | `WEBSITE_SITE_NAME` | `azure_app_service` |
| AKS | `KUBERNETES_SERVICE_HOST` / `K8S_*` / `POD_*` | `azure_aks` |

For AKS, expose `K8S_CLUSTER_NAME` (or `AKS_CLUSTER_NAME`), `K8S_NAMESPACE_NAME`,
`K8S_POD_NAME`, `K8S_NODE_NAME`, `CONTAINER_NAME` from the Kubernetes downward API.

**Logs ↔ traces correlation:** a log emitted inside an active span automatically
carries the span's `trace_id` (and `span_id`), so in Grafana you can jump from a
log line to its full trace and back.

---

## 8. Security notes

- **`X_ORG_ID` is a credential.** Provide it via the environment or a secret
  manager at deploy time. Don't commit a real one into the `DEFAULT_X_ORG_ID`
  constant. It's sent as the `X-OrgId` header, so use an **HTTPS** OTLP endpoint
  so it isn't exposed in transit.
- **Don't log secrets.** The logger serialises whatever attributes you pass;
  never put tokens, passwords, or PII in a log message or attribute map.
- **Endpoints:** prefer `https://` OTLP endpoints in any non-local environment.

---

## 9. Verify it's working

- **Console fallback:** with no OTLP config, records print to stdout — confirms
  the logger/tracer is wired in.
- **OTLP path:** set the four env vars in section 5; records should appear in
  your collector → Loki (logs) / Tempo (traces). If they don't, check that
  **both** the endpoint and `X_ORG_ID` resolved (otherwise it silently used
  console).
- **Local end-to-end:** the `demo/` stack in this repo runs all four languages
  through a collector into Loki + Tempo + Grafana, with correlated logs/traces
  and a service-graph flow chart — a working reference for the env-var setup.
