# Getting Started

How to use the `otel-logs` / `otel-traces` libraries in an application. The model
is the same in every language: **install the package → set a few `OTEL_*`
environment variables → call one line of code.** The env vars decide *where*
telemetry goes; the code is just `logger` / `init()`.

Per-language detail lives in each [`libraries/<lang>/USAGE.md`](libraries/) and
[`docs/USING-THE-LIBRARIES.md`](docs/USING-THE-LIBRARIES.md); prerequisites to
install are in each `libraries/<lang>/REQUIREMENTS.md`.

---

## 1. Environment variables (the configuration)

Every language reads the **same** variables:

| Variable | Applies to | Default | What it does |
|---|---|---|---|
| `OTEL_SERVICE_NAME` | both | `unknown_service` | The `service.name` on every log/span. **Set this in every app.** |
| `OTEL_BACKEND_EXPORTERS` | both | `console` | `console` = print locally; `otel` = send to a collector over OTLP/HTTP. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | both | — | Collector URL, e.g. `http://alloy:4318`. Auto-normalised to `/v1/logs` and `/v1/traces`. |
| `X_ORG_ID` | both | — | **Org identifier** (not a secret), sent as the `X-OrgId` header. Required for `otel`. |
| `OTEL_RESOURCE_ATTRIBUTES` | both | — | Extra resource attributes, CSV: `deployment.environment=prod,team=payments`. |
| `OTEL_LOG_LEVEL` | logs | all | Which levels to emit, e.g. `info,warn,error` (omit `debug`). |
| `OTEL_LOGS_SAMPLING_RATE` | logs | `100` | 0–100. Errors are always emitted regardless. |
| `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT` / `..._TRACES_ENDPOINT` | per-signal | — | Override the endpoint for one signal only (optional). |
| `OTEL_EXPORTER_PARAMETERS` | both | — | Inline JSON alternative: `{"otel":{"logs":{"url":"…"},"trace":{"url":"…"}}}`. |

### The rule that controls where telemetry goes

The OTLP exporter is used **only when all three are true**:

1. `OTEL_BACKEND_EXPORTERS` = `otel`, **and**
2. an endpoint resolves, **and**
3. `X_ORG_ID` resolves.

If any is missing, it **silently falls back to `console`** — so if you set `otel`
but forget `X_ORG_ID`, you get console output, not an error. That is the most
common gotcha.

### Two ready-to-use configs

**Local dev (print to stdout)** — set nothing, or just the service name:

```bash
export OTEL_SERVICE_NAME=payments-api
# OTEL_BACKEND_EXPORTERS defaults to console → logs/traces print locally
```

**Ship to a collector:**

```bash
export OTEL_SERVICE_NAME=payments-api
export OTEL_BACKEND_EXPORTERS=otel
export OTEL_EXPORTER_OTLP_ENDPOINT=http://alloy:4318   # or https://otel.example.com
export X_ORG_ID=your-org
# optional:
export OTEL_RESOURCE_ATTRIBUTES=deployment.environment=prod
export OTEL_LOG_LEVEL=info,warn,error
export OTEL_LOGS_SAMPLING_RATE=100
```

The same four core variables work in a `docker-compose` `environment:` block, a
Kubernetes `env:` list, or Azure App Service application settings. Azure runtime
attributes (Functions / Container Apps / App Service / AKS) are detected and added
automatically — you don't configure those.

---

## 2. Using it in code

### Python

```python
# --- logs ---
from otel_logs import logger
logger.info("order created", {"order_id": order_id})
logger.error(exc)

# --- traces --- call init() BEFORE importing Flask
from otel_traces import init
init()
from flask import Flask          # import after init()
app = Flask(__name__)
```

### Node.js

```ts
import "@otel/traces/register";  // FIRST line, before your http server/framework
import { logger } from "@otel/logs";

logger.info("order created", { orderId });
```

Or with zero code edits: `node --require @otel/traces/register server.js`.

### .NET

```csharp
using Otel.Logs;
using Otel.Traces;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddOtelTraces();          // traces (ASP.NET Core + HttpClient)
var app = builder.Build();

var logger = Logger.Init();                // logs
logger.Info("order created", orderId);
```

### Java

```java
import otel.logs.Logger;
import otel.traces.Tracer;

var logger = Logger.init();
var tracer = Tracer.init();

logger.info("order created", "order_id", orderId);

// inbound span (continues the caller's trace):
server.createContext("/process", tracer.wrap("process", handler));
// outbound (creates a client span + injects W3C headers):
var resp = tracer.tracedClient().send(request, HttpResponse.BodyHandlers.ofString());
```

---

## 3. Two rules worth remembering

- **Initialise tracing before your web framework loads** (Node: require
  `@otel/traces/register` first; Python: call `init()` before `import Flask`).
  HTTP auto-instrumentation must patch the HTTP layer before your server is
  created, otherwise incoming requests won't join the trace. .NET and Java don't
  have this issue because `AddOtelTraces()` / `wrap()` are explicit.
- **`X_ORG_ID` is an org identifier, not a credential** — safe to keep in plain
  config/env. Use an `https://` endpoint in non-local environments so it isn't
  sent in cleartext.

Logs are flushed automatically at process shutdown, so you rarely call
`exportLogs()` / `export_logs()` yourself — only in serverless/Functions where the
process outlives an invocation.

---

## 4. Try it end-to-end

The [`demo/`](demo/README.md) stack runs all four languages through Grafana Alloy
into Loki (logs), Tempo (traces), and Mimir (service-graph metrics), with Grafana
for correlated logs+traces and a service-graph flow chart — a working reference
for the setup above.
