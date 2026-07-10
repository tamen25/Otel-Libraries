<!-- This document explains the readme for the otel traces library. -->
# otel-traces

Python tracing helper built on OpenTelemetry.

```python
from otel_traces import init

init()  # no-arg: instruments requests + Flask if importable, exports spans
```

`init()` takes no framework object. It gates OTLP export on **both** a resolved
endpoint URL and `X_ORG_ID` (sent as the `X-OrgId` header); otherwise it falls
back to console. It opportunistically instruments the `requests` and Flask HTTP
libraries when they are importable and silently skips absent ones, so incoming
and outgoing HTTP calls create spans and propagate W3C `tracecontext`
automatically — a request flowing through several services stays one connected
trace. Flask instrumentation is global, so call `init()` before creating the
Flask app. A best-effort span flush is registered at interpreter exit.

Configuration mirrors the other libraries:

- `OTEL_BACKEND_EXPORTERS`: `console` (default) or `otel`.
- `OTEL_SERVICE_NAME` / `OTEL_RESOURCE_ATTRIBUTES`: resource identity; Azure
  runtime attributes (Functions / Container Apps / App Service / AKS) are added
  automatically.
- `OTEL_EXPORTER_PARAMETERS`: inline JSON with `otel.trace.url`.
- `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` / `OTEL_EXPORTER_OTLP_ENDPOINT`: endpoint,
  else the `DEFAULT_TRACES_ENDPOINT` constant.
- `X_ORG_ID`: authentication key (or `DEFAULT_X_ORG_ID`). Required for OTLP export.

Logs emitted by `otel-logs` within an active span automatically carry
`otel-trace-id` / `otel-span-id`, so logs and traces correlate in Grafana.
