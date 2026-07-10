# Otel.Logs

.NET logging helper for services.

```csharp
using Otel.Logs;

var logger = Logger.Init();

logger.Info("order created", orderId);
logger.Error(exception);
logger.ExportLogs();   // optional: batched logs also flush at process exit
```

Set `OTEL_SERVICE_NAME` in every app. The library also merges
`OTEL_RESOURCE_ATTRIBUTES` and adds Azure runtime attributes for Azure Functions, Container Apps, and
AKS when those environment hints are available.

Configuration matches the Node.js logs library:

- `OTEL_BACKEND_EXPORTERS`: JSON array or comma-separated list. Defaults to `console`.
- `OTEL_LOG_LEVEL`: JSON array or comma-separated list of `info`, `error`, `debug`, `warn`.
- `OTEL_LOGS_SAMPLING_RATE`: percentage from `0` to `100`. Error logs are always exported.
- `OTEL_EXPORTER_PARAMETERS`: inline JSON object with `otel.logs.url`.
- `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT` or `OTEL_EXPORTER_OTLP_ENDPOINT`: OTLP HTTP endpoint.
- `X_ORG_ID`: org identifier, sent on every OTLP export as the `X-OrgId` header (required for OTLP).

The OTLP exporter is used only when **both** an endpoint URL and `X_ORG_ID` resolve;
otherwise the library falls back to console. Provide them via the environment
variables above, or bake them into the `DefaultLogsEndpoint` / `DefaultXOrgId`
constants in `LogsConfiguration`. There is no secrets/parameter file.
