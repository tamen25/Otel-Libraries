# OTel Demo Stack

A local end-to-end telemetry pipeline exercised by four chained sample apps, one
per language, each using the `otel-logs` + `otel-traces` libraries:

```
frontend (React) → node-edge → python-app → java-app → dotnet-app
                        └──────── OTLP/HTTP logs + traces ────────→ Grafana Alloy
                                        Alloy → Loki (logs)
                                        Alloy → Tempo (traces) → Mimir (service-graph metrics)
                                        Grafana ← Loki / Tempo / Mimir
```

Each app is configured with `OTEL_BACKEND_EXPORTERS=otel` and points at **Grafana
Alloy** (the collector). Alloy fans logs into **Loki** and traces into **Tempo**;
Tempo's metrics-generator remote-writes service-graph + span metrics into
**Mimir**; **Grafana** visualizes everything with auto-provisioned dashboards and
logs↔traces correlation.

## Prerequisites

- Docker Desktop (running)
- On the host, only to build library artifacts: Python 3.11+, the .NET SDK, and
  Node 22+ (Java is built from source inside its image — no host Java/Maven needed)

## Run

```bash
# 1. Build the wheels, nupkgs, and npm tarballs into demo/artifacts/
bash demo/scripts/build-libs.sh

# 2. Build images and start everything
docker compose -f demo/docker-compose.yml up -d --build
```

`build-libs.sh` MUST run before `up --build` — the app Dockerfiles install the
artifacts from `demo/artifacts/`.

- **React demo UI:** http://localhost:5173 — click "Send a traced order", see the
  trace id and links into Grafana.
- **Grafana:** http://localhost:3000 (anonymous admin — no login). Dashboards in
  the **OTel Demo** folder: **Traces & Logs Correlation**, **Service Graph** (the
  `user → node-edge → python → java → dotnet` flow chart), and the logs dashboards.

## Verify from the command line

```bash
# All four services present in Loki:
curl -s "http://localhost:3100/loki/api/v1/label/service_name/values"
# -> {"status":"success","data":["dotnet-app","java-app","node-edge","python-app"]}

# Drive one traced order and confirm a single trace spans all services:
curl -s http://localhost:8090/api/order    # -> {"traceId":"...","chain":[...]}

# Service-graph edges in Mimir:
curl -s "http://localhost:9009/prometheus/api/v1/query?query=traces_service_graph_request_total"

# Grafana health:
curl -s http://localhost:3000/api/health   # -> {"database":"ok",...}
```

Tempo's API (`:3200`) is not published to the host — query it from inside the
network, e.g. `docker compose -f demo/docker-compose.yml exec python-app python3 -c "..."`.

## How logs are labeled

To keep Loki cardinality bounded, **`service_name`** is the indexed stream label
(Alloy promotes `service.name` to it). The log **level** arrives as OTLP severity;
Loki derives `detected_level` into structured metadata. A log emitted inside an
active span carries its `trace_id` (also a stream label), which powers the
Loki↔Tempo correlation.

## Stop

```bash
docker compose -f demo/docker-compose.yml down      # stop
docker compose -f demo/docker-compose.yml down -v   # stop + wipe data
```

## Notes / troubleshooting

- **Volume-mounted configs** (alloy / tempo / grafana / mimir) are NOT reloaded by
  `up -d` — run `docker compose -f demo/docker-compose.yml restart <svc>` after
  editing them.
- **Cold start:** in the first seconds an upstream app may log a connection error
  before its downstream is listening. This is expected — loadgen retries.
- **Rebuild after changing a library:** re-run `bash demo/scripts/build-libs.sh`
  then `docker compose -f demo/docker-compose.yml up -d --build`.
- **Inspect what Alloy receives:** `docker compose -f demo/docker-compose.yml logs alloy`
  (the `debug` exporter prints per-record detail).
