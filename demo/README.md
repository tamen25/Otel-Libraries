# OTel Logs Demo Stack

Local **Grafana Alloy → Loki → Grafana** pipeline (plus a dormant **Tempo**
traces backend) exercised by three chained sample apps that log via the CloudOps
OTel logs libraries:

```
loadgen → python-app → java-app → dotnet-app
              └──────────── OTLP/HTTP logs ────────────→ alloy → Loki → Grafana
```

Each app logs through its own CloudOps OTel logs library (Python wheel, Java jar,
.NET nupkg), all configured with `OTEL_BACKEND_EXPORTERS=otel` and pointed at
Alloy. Alloy fans logs into Loki; Grafana visualizes them with
auto-provisioned dashboards.

## Prerequisites

- Docker Desktop (running)
- On the host, only to build the library artifacts: Python 3.11+ and the .NET SDK
  (Java is built from source inside its image, so no host Java/Maven needed)

## Run

```bash
# 1. Build the Python wheel and .NET nupkg into demo/artifacts/
bash demo/scripts/build-libs.sh

# 2. Build images and start everything
docker compose -f demo/docker-compose.yml up -d --build
```

`build-libs.sh` MUST run before `up --build` — the Python and .NET Dockerfiles
install the artifacts from `demo/artifacts/`.

Open **Grafana at http://localhost:3000** (anonymous admin is enabled — no login).
Dashboards live in the **OTel Demo** folder:

- **All Apps — Logs Overview** — log volume by service, volume by level, an error
  stat, and a live combined log stream with a `service` filter.
- **Per-App Drilldown** — pick an app from the `service` dropdown to see its
  level breakdown, all logs, and errors-only.

## Verify from the command line

```bash
# All three services are present in Loki:
curl -s "http://localhost:3100/loki/api/v1/label/service_name/values"
# -> {"status":"success","data":["dotnet-app","java-app","python-app"]}

# Log counts per service (last 2 minutes):
for svc in python-app java-app dotnet-app; do
  curl -s -G "http://localhost:3100/loki/api/v1/query" \
    --data-urlencode "query=sum(count_over_time({service_name=\"$svc\"}[2m]))" \
    | python -c "import sys,json;r=json.load(sys.stdin)['data']['result'];print('$svc', r[0]['value'][1] if r else 0)"
done

# Grafana health:
curl -s http://localhost:3000/api/health   # -> {"database":"ok",...}
```

## How logs are labeled

To keep Loki cardinality bounded, only **`service_name`** is an indexed stream
label. The log **level** arrives as OTLP severity; Loki derives a
**`detected_level`** value (info/warn/error/debug) into *structured metadata*.

- Aggregate by level: `sum by (detected_level) (count_over_time({service_name="python-app"}[1m]))`
- Filter by level: `{service_name="python-app"} | detected_level=` + `` `error` ``
  (level is structured metadata, so it goes after `|`, not inside `{}`).

Everything else (message, `order_id`, invocation id) is in the log body / metadata.

## Stop

```bash
docker compose -f demo/docker-compose.yml down          # stop
docker compose -f demo/docker-compose.yml down -v       # stop + wipe data
```

## Tracing (future)

Tempo and Alloy's traces pipeline are already running but idle — apps
emit no spans yet. Adding app-side spans later needs **no infra change**: Alloy
already accepts OTLP traces and exports them to Tempo, and the Loki
datasource is pre-wired with a derived `TraceID` field that links log lines to
Tempo once traces carry a `trace_id`.

## Notes / troubleshooting

- **Cold start:** on the very first seconds, `python-app` may log an `error`
  ("java call failed / connection refused") before `java-app` is listening. This
  is expected — loadgen retries and the chain self-heals. It also seeds the
  error-level dashboards with real data.
- **Rebuild after changing a library:** re-run `bash demo/scripts/build-libs.sh`
  then `docker compose -f demo/docker-compose.yml up -d --build`.
- **Inspect what Alloy receives:** `docker compose -f demo/docker-compose.yml logs alloy`
  (the `debug` exporter prints per-record detail).
