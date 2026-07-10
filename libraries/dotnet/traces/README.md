# Otel.Traces

.NET tracing helper for services.

```csharp
using Otel.Traces;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddOtelTraces();
var app = builder.Build();
```

`AddOtelTraces` gates OTLP export on **both** a resolved endpoint URL and
`X_ORG_ID` (sent as the `X-OrgId` header); otherwise no OTLP exporter is added.
It registers ASP.NET Core + HttpClient auto-instrumentation, so incoming and
outgoing HTTP calls create spans and propagate W3C `tracecontext` automatically.

Configuration mirrors the other libraries:

- `OTEL_BACKEND_EXPORTERS`: `console` (default) or `otel`.
- `OTEL_SERVICE_NAME` / `OTEL_RESOURCE_ATTRIBUTES`: resource identity; Azure
  runtime attributes are added automatically.
- `OTEL_EXPORTER_PARAMETERS`: inline JSON with `otel.trace.url`.
- `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` / `OTEL_EXPORTER_OTLP_ENDPOINT`: endpoint,
  else the `DefaultTracesEndpoint` constant.
- `X_ORG_ID`: authentication key (or `DefaultXOrgId`). Required for OTLP export.

Logs emitted by `Otel.Logs` within an active span automatically carry
`otel-trace-id` / `otel-span-id`, so logs and traces correlate in Grafana.
