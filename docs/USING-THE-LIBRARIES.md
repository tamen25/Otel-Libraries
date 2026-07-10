# Using the OTel Libraries

This guide is for **application developers** adding logging and tracing to a
service. Install one small package per signal, set a few `OTEL_*` environment
variables, and call one line — the library handles OpenTelemetry setup, Azure
runtime detection, batching, sampling, W3C trace propagation, OTLP export, and
flush-on-shutdown for you.

All four language ports implement the **same design and the same `OTEL_*`
contract**, so behaviour is identical across runtimes. **Logs** and **traces**
are separate packages — install only the signal you need.

---

## 1. Packages

| Language | Logs package | Traces package | Runtime |
|----------|--------------|----------------|---------|
| Python   | `otel-logs` (`otel_logs`)   | `otel-traces` (`otel_traces`)   | Python ≥ 3.11 |
| Java     | `otel:otel-logs`            | `otel:otel-traces`              | Java 21 |
| .NET     | `Otel.Logs`                 | `Otel.Traces`                   | net8.0 |
| Node.js  | `@otel/logs`                | `@otel/traces`                  | Node ≥ 22 |

All packages are version **`0.1.0`**.

---

## 2. Install from your private registry

Point your package manager at the feed, authenticate, then install. Replace
`registry.example.com` and the credentials with your feed's real values.

**Python (pip)** — `~/.pip/pip.conf` (Windows: `%APPDATA%\pip\pip.ini`):

```ini
[global]
index-url = https://<user>:<token>@registry.example.com/repository/pypi/simple
```
```bash
pip install otel-logs otel-traces
```

**Java (Maven)** — add the repository (credentials in `~/.m2/settings.xml`) and:

```xml
<dependency><groupId>otel</groupId><artifactId>otel-logs</artifactId><version>0.1.0</version></dependency>
<dependency><groupId>otel</groupId><artifactId>otel-traces</artifactId><version>0.1.0</version></dependency>
```

**.NET (NuGet)** — add the feed to `nuget.config`, then:

```bash
dotnet add package Otel.Logs --version 0.1.0
dotnet add package Otel.Traces --version 0.1.0
```

**Node.js (npm)** — scope `@otel` in `.npmrc`:

```ini
@otel:registry=https://registry.example.com/repository/npm/
//registry.example.com/repository/npm/:_authToken=${NPM_TOKEN}
```
```bash
npm install @otel/logs @otel/traces
```

---

## 3. Quick start — logging

Set `OTEL_SERVICE_NAME`. With no other config the logger writes to the console;
set the OTLP variables (section 5) to ship to your collector. Batched logs are
**flushed automatically at process shutdown** — you only call the flush method
explicitly in serverless/Functions where the process outlives an invocation.

**Python**
```python
from otel_logs import logger

logger.info("order created", {"order_id": order_id})
logger.warn("retrying downstream call", {"attempt": 2})
logger.error(exc)
```

**Java**
```java
import otel.logs.Logger;
final Logger logger = Logger.init();

logger.info("order created", "order_id", orderId);   // key/value varargs
logger.error(exception);
```

**.NET**
```csharp
using Otel.Logs;
var logger = Logger.Init();

logger.Info("order created", orderId);
logger.Error(exception);
```

**Node.js**
```ts
import { logger } from "@otel/logs";

logger.info("order created", { orderId });
await logger.exportLogs();   // optional: also auto-flushed at shutdown
```

Levels are `info` / `warn` / `error` / `debug`. A batch is always emitted if it
contains an `error`, otherwise it is sampled at `OTEL_LOGS_SAMPLING_RATE`.

---

## 4. Quick start — tracing

Tracing is designed so **cross-service context propagation is automatic**: the
library registers the W3C `tracecontext` propagator and HTTP auto-instrumentation.
A request flowing through several services stays **one connected trace**, and
logs emitted inside an active span automatically carry its `trace_id`.

> **The one rule that matters: initialise tracing _before_ your web framework is
> loaded.** HTTP auto-instrumentation must patch the HTTP machinery before your
> app creates its server. This is the same rule in every language — do it on the
> first lines of your entry point.

**Node.js — require the register entry first**
```ts
import "@otel/traces/register";       // FIRST line — before your http server/framework
import { logger } from "@otel/logs";
// ...your http server; inbound + outbound HTTP are traced automatically
```
Or with zero code edits: `node --require @otel/traces/register server.js`.

**Python (Flask/requests) — call `init()` before importing your framework**
```python
from otel_traces import init
init()                                 # BEFORE importing Flask

from flask import Flask                # now the app is auto-instrumented
app = Flask(__name__)
```
`init()` takes no framework object — it opportunistically instruments `requests`
and Flask if they are importable. Because Flask instrumentation swaps the
`flask.Flask` class, importing Flask *after* `init()` is what makes your app the
instrumented one.

**.NET (ASP.NET Core)**
```csharp
using Otel.Traces;
var builder = WebApplication.CreateBuilder(args);
builder.Services.AddOtelTraces();      // ASP.NET Core + HttpClient auto-instrumented
var app = builder.Build();
```

**Java — framework-free edge helpers**
```java
import otel.traces.Tracer;
final Tracer tracer = Tracer.init();

// Inbound: run a handler inside a SERVER span that continues the caller's trace.
server.createContext("/process", tracer.wrap("process", handler));

// Outbound: a client whose send() creates a CLIENT span and injects W3C headers.
var resp = tracer.tracedClient().send(request, HttpResponse.BodyHandlers.ofString());
```
The lower-level API (`startServerSpan`, `startClientSpan`, `injectHeaders`) stays
public for non-HTTP transports. Node/Python/.NET also expose manual span helpers.

---

## 5. Configuration — the `OTEL_*` contract

Every port reads the same variables. There is no secrets file; values come from
the environment (or the `DEFAULT_*` constants baked into each library).

| Variable | Applies to | Meaning |
|----------|-----------|---------|
| `OTEL_SERVICE_NAME` | both | `service.name` on every record. **Set this in every app.** |
| `OTEL_RESOURCE_ATTRIBUTES` | both | Extra resource attrs, e.g. `deployment.environment=prod`. |
| `OTEL_BACKEND_EXPORTERS` | both | `console` (default) or `otel` (OTLP/HTTP). The switch for choosing the backend. |
| `OTEL_LOG_LEVEL` | logs | Enabled levels among `info,error,debug,warn`. |
| `OTEL_LOGS_SAMPLING_RATE` | logs | `0`–`100` (default `100`). Errors are always emitted. |
| `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT` / `OTEL_EXPORTER_OTLP_ENDPOINT` | logs | OTLP endpoint (normalised to `/v1/logs`). |
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` / `OTEL_EXPORTER_OTLP_ENDPOINT` | traces | OTLP endpoint (normalised to `/v1/traces`). |
| `OTEL_EXPORTER_PARAMETERS` | both | Inline JSON: `{"otel":{"logs":{"url":"…"},"trace":{"url":"…"}}}`. |
| `X_ORG_ID` | both | **Org identifier** sent as the `X-OrgId` header on every OTLP export. Required for `otel`. |

The OTLP exporter is used **only when both** an endpoint URL and `X_ORG_ID`
resolve (from env or the `DEFAULT_*` constants); otherwise the library falls
back to console. `OTEL_BACKEND_EXPORTERS` selects the backend explicitly, so you
can flip between `console` and `otel` — or repoint the endpoint — purely through
environment variables, with no code change.

---

## 6. Infra templates

Wire the standard variables once in your deployment template. `X_ORG_ID` is an
**org identifier, not a secret** — it is safe to keep in plain config.

**docker-compose**
```yaml
environment:
  OTEL_SERVICE_NAME: payments-api
  OTEL_BACKEND_EXPORTERS: otel
  OTEL_EXPORTER_OTLP_ENDPOINT: http://alloy:4318
  X_ORG_ID: your-org
```

**Kubernetes (Deployment `env`)**
```yaml
env:
  - { name: OTEL_SERVICE_NAME,          value: payments-api }
  - { name: OTEL_BACKEND_EXPORTERS,     value: otel }
  - { name: OTEL_EXPORTER_OTLP_ENDPOINT, value: http://alloy.telemetry.svc:4318 }
  - { name: X_ORG_ID,                   value: your-org }
```

**Azure App Service (application settings)**
```
OTEL_SERVICE_NAME=payments-api
OTEL_BACKEND_EXPORTERS=otel
OTEL_EXPORTER_OTLP_ENDPOINT=https://otel.example.com
X_ORG_ID=your-org
```

---

## 7. Azure runtime auto-detection & correlation

Set `OTEL_SERVICE_NAME` and the library derives the rest, auto-detecting the
Azure runtime from environment hints and adding `cloud.provider=azure` plus a
`cloud.platform` (`azure_functions` / `azure_container_apps` / `azure_app_service`
/ `azure_aks`). A log emitted inside an active span automatically carries the
span's `trace_id`, so logs and traces correlate in Grafana.

---

## 8. Security notes

- **`X_ORG_ID` is an org identifier, not a credential** — it routes/labels
  telemetry by organisation. It is safe to commit and to keep in plain config.
- **Don't log secrets or PII.** The logger serialises whatever attributes you
  pass; never put tokens, passwords, or personal data in a message or attribute.
- **Use `https://` OTLP endpoints** in any non-local environment.

---

## 9. Verify it's working

- **Console fallback:** with no OTLP config, records print to stdout — confirms
  the library is wired in.
- **OTLP path:** set the variables in section 5; records appear in your collector
  → Loki (logs) / Tempo (traces). If they don't, check that **both** the endpoint
  and `X_ORG_ID` resolved (otherwise it silently used console), and — for traces —
  that you initialised **before** your web framework loaded (section 4).
- **Local end-to-end:** the [`demo/`](../demo/README.md) stack runs all four
  languages through Grafana Alloy into Loki + Tempo + Mimir + Grafana, with
  correlated logs/traces and a service-graph flow chart — a working reference.
