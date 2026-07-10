<!-- This document explains the readme for the otel logs library. -->
# otel:otel-logs

Java logging helper built on OpenTelemetry.

```java
import otel.logs.Logger;

final Logger logger = Logger.init();

logger.info("order created", orderId);
logger.error(exception);
logger.exportLogs();
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
- `X_ORG_ID`: authentication key, sent on every OTLP export as the `X-OrgId` header.

The OTLP exporter is used only when **both** an endpoint URL and `X_ORG_ID` resolve;
otherwise the library falls back to console. Provide them via the environment
variables above, or bake them into the `DEFAULT_LOGS_ENDPOINT` / `DEFAULT_X_ORG_ID`
constants in `LogsConfiguration`. There is no secrets/parameter file.
