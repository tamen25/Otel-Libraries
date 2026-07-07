<!-- This document explains readme for CloudOps. -->
# com.cloudops:otel-logs

Java logging helper for CloudOps services.

```java
import com.cloudops.otel.logs.CloudOpsLogger;

final CloudOpsLogger logger = CloudOpsLogger.initialiseLogger();

logger.info("order created", orderId);
logger.error(exception);
logger.exportLogs();
```

Set `OTEL_SERVICE_NAME` in every app. The library also merges
`OTEL_RESOURCE_ATTRIBUTES` and adds AWS runtime attributes for Lambda, ECS, and
EKS when those environment hints are available.

Configuration matches the Node.js logs library:

- `OTEL_BACKEND_EXPORTERS`: JSON array or comma-separated list. Defaults to `console`.
- `OTEL_LOG_LEVEL`: JSON array or comma-separated list of `info`, `error`, `debug`, `warn`.
- `OTEL_LOGS_SAMPLING_RATE`: percentage from `0` to `100`. Error logs are always exported.
- `OTEL_SSM_PARAMETERS`: JSON object with `otel.logs.url` and `otel.logs.api_key`.
- `/tmp/otelExporterParams.json`: original PE parameter file fallback. Set `OTEL_SSM_PARAMETERS_FILE` to override the path.
- `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT` or `OTEL_EXPORTER_OTLP_ENDPOINT`: OTLP HTTP endpoint fallback.
- `OTEL_API_KEY` or `OTEL_EXPORTER_OTLP_HEADERS`: OTLP auth fallback.
