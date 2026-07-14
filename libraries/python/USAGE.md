# Python — otel-logs / otel-traces usage

OpenTelemetry logging and tracing for Python services. Two independent packages —
install only what you need.

## Install

From your private PyPI feed (set `index-url` in `~/.pip/pip.conf`, Windows
`%APPDATA%\pip\pip.ini`):

```bash
pip install otel-logs        # logs
pip install otel-traces      # traces
```

Or from the source in this package:

```bash
cd logs   && pip install .
cd traces && pip install .
```

Requires Python ≥ 3.11.

## Logging

```python
from otel_logs import logger

logger.info("order created", {"order_id": order_id})
logger.warn("retrying", {"attempt": 2})
logger.error(exc)               # pass an exception or a message
# logger.export_logs()          # optional — batched logs also flush at process exit
```

Levels: `info` / `warn` / `error` / `debug`. A batch is always emitted if it
contains an error, otherwise it is sampled at `OTEL_LOGS_SAMPLING_RATE`.

## Tracing

**Call `init()` before importing Flask** — Flask instrumentation swaps the
`flask.Flask` class, so the app must be created from the already-patched class:

```python
from otel_traces import init
init()                          # instruments requests + Flask; register first

from flask import Flask         # import AFTER init()
app = Flask(__name__)
```

`init()` is no-arg and framework-independent — it opportunistically instruments
`requests` and Flask if they are importable. Incoming and outgoing HTTP then
propagate W3C `tracecontext` automatically, so a request stays one connected
trace across services, and logs emitted inside a span carry its `trace_id`.

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
secret** — safe to keep in plain config. Azure runtime attributes (Functions /
Container Apps / App Service / AKS) are added automatically.

## Test

```bash
cd logs   && PYTHONPATH=src python -m pytest -q
cd traces && PYTHONPATH=src python -m pytest -q
```
