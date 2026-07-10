<!-- This document explains readme for CloudOps. -->
# cloudops-otel-traces

Python tracing helper for CloudOps services.

```python
from flask import Flask
from cloudops_otel_traces import init_tracing

app = Flask(__name__)
init_tracing(app)  # instruments Flask + requests, exports spans to the collector
```

`init_tracing` gates OTLP export on **both** a resolved endpoint URL and
`X_ORG_ID` (sent as the `X-OrgId` header); otherwise it falls back to console.
It registers Flask + `requests` auto-instrumentation, so incoming and outgoing
HTTP calls create spans and propagate W3C `tracecontext` automatically — a
request flowing through several services stays one connected trace.

Configuration mirrors the other CloudOps libraries:

- `OTEL_BACKEND_EXPORTERS`: `console` (default) or `otel`.
- `OTEL_SERVICE_NAME` / `OTEL_RESOURCE_ATTRIBUTES`: resource identity; Azure
  runtime attributes (Functions / Container Apps / App Service / AKS) are added
  automatically.
- `OTEL_EXPORTER_PARAMETERS`: inline JSON with `otel.trace.url`.
- `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` / `OTEL_EXPORTER_OTLP_ENDPOINT`: endpoint,
  else the `DEFAULT_TRACES_ENDPOINT` constant.
- `X_ORG_ID`: authentication key (or `DEFAULT_X_ORG_ID`). Required for OTLP export.

Logs emitted by `cloudops-otel-logs` within an active span automatically carry
`otel-trace-id` / `otel-span-id`, so logs and traces correlate in Grafana.
