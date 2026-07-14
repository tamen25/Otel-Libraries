# Node.js — @otel/logs / @otel/traces usage

OpenTelemetry logging and tracing for Node.js / TypeScript services. Two
independent packages — install only what you need. Requires Node ≥ 22.

## Install (npm)

Scope `@otel` to your private registry in `.npmrc`, then:

```bash
npm install @otel/logs @otel/traces
```

Or build + pack from the source in this package:

```bash
cd logs   && npm install && npm run build && npm pack   # -> otel-logs-0.1.0.tgz
cd traces && npm install && npm run build && npm pack   # -> otel-traces-0.1.0.tgz
```

## Logging

```ts
import { logger } from "@otel/logs";

logger.info("order created", { orderId });
logger.warn("retrying", { attempt: 2 });
logger.error(error);
// await logger.exportLogs();   // optional — batched logs also flush at shutdown
```

## Tracing

**Require the register entry FIRST**, before your HTTP server/framework loads, so
HTTP auto-instrumentation patches the `http` module before the server is created:

```ts
import "@otel/traces/register";     // FIRST line
import { logger } from "@otel/logs";
// ...your http server; inbound + outbound HTTP are traced and propagate W3C context
```

Or with zero code edits: `node --require @otel/traces/register server.js`.

For manual or Azure-service-aware spans:

```ts
import { tracer, AzureService } from "@otel/traces";
const span = tracer.startBasicSpan("handle-order");
try { /* work */ } finally { span?.end(); await tracer.exportSpans(); }
```

## Configuration (`OTEL_*` environment variables)

| Variable | Meaning |
|----------|---------|
| `OTEL_SERVICE_NAME` | `service.name` on every record. **Set in every app.** |
| `OTEL_BACKEND_EXPORTERS` | `console` (default) or `otel` (OTLP/HTTP). |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP endpoint (or the `*_LOGS_`/`*_TRACES_` variants). |
| `X_ORG_ID` | Org identifier, sent as the `X-OrgId` header. Required for `otel`. |
| `OTEL_RESOURCE_ATTRIBUTES` | Extra resource attributes (CSV `k=v`). |
| `OTEL_LOG_LEVEL` | Enabled log levels (logs). |
| `OTEL_LOGS_SAMPLING_RATE` | 0–100, default 100 (logs). |

The OTLP exporter is used only when **both** an endpoint and `X_ORG_ID` resolve;
otherwise it falls back to console. `X_ORG_ID` is an **org identifier, not a
secret** — safe to keep in plain config. Azure runtime attributes are added
automatically.

## Test

```bash
cd logs   && npm test
cd traces && npm test
```
