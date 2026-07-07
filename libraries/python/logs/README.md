<!-- This document explains readme for CloudOps. -->
# cloudops-otel-logs

Python logging helper for CloudOps services.

```python
from cloudops_otel_logs import logger

logger.info("order created", {"order_id": order_id})
logger.error(error)
logger.export_logs()
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
