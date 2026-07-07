# Local OTel Collector → Loki → Grafana demo stack

**Date:** 2026-07-07
**Status:** Approved design, pre-implementation

## Goal

Stand up a fully local, Docker-based observability stack that exercises the three
CloudOps OTel **logs** libraries (Python / Java / .NET) end to end:

- An OpenTelemetry Collector receives OTLP/HTTP logs from three sample apps.
- The collector forwards logs to Loki; Grafana visualizes them.
- The three apps are **chained HTTP services** (Python → Java → .NET) driven by a
  load generator, so distributed **tracing** can be added later with no infra
  change.
- Grafana ships with **auto-provisioned** datasources and log dashboards for all
  three apps.

Everything runs with a single `docker compose up`.

## Non-goals (this phase)

- **No app-side trace emission.** Traces backend (Tempo) and the collector's
  traces pipeline are stood up and ready, but apps emit no spans yet. Adding
  spans later is app-side code only.
- **No PyPI / registry publishing.** The Python wheel (and .NET nupkg) are built
  locally and installed into the images; nothing is uploaded anywhere.
- No auth beyond Grafana's default admin login, no TLS, no persistent volumes,
  no unit tests for the throwaway demo apps.

## Architecture

```
                          docker compose network: "otel-demo"
┌──────────────┐   OTLP/HTTP    ┌───────────────────┐   loki push   ┌──────────┐
│ python-app   │──4318─┐        │                   │──────────────▶│  Loki    │◀─┐
│ java-app     │──4318─┼───────▶│  OTel Collector   │               └──────────┘  │
│ dotnet-app   │──4318─┘        │  (contrib image)  │   otlp        ┌──────────┐  │ reads
└──────┬───────┘                │                   │──────────────▶│  Tempo   │◀─┼──┐
       │ HTTP chain             └───────────────────┘  (ready, no   └──────────┘  │  │
       ▼                                                traffic yet)               │  │
  loadgen ─▶ python ─▶ java ─▶ dotnet                                    ┌──────────────┐
                                                                        │   Grafana    │
                                                                        │  (dashboards)│
                                                                        └──────────────┘
```

**Log flow (this phase):** `loadgen` calls `python-app` on a timer → python calls
`java-app` → java calls `dotnet-app`. Each hop logs via its CloudOps OTel logs
library configured with `OTEL_BACKEND_EXPORTERS=otel`, exporting OTLP/HTTP to the
collector at `:4318/v1/logs`. The collector's **logs pipeline** exports to Loki.
Grafana queries Loki.

**Traces plumbing (dormant):** The collector also runs a **traces pipeline**
(OTLP receiver → Tempo exporter) and Tempo is in the stack, but no spans flow yet.

All three libraries already export **OTLP over HTTP/protobuf** to `/v1/logs`
(port 4318) — confirmed in source — which the collector accepts natively.

## Components

All demo files live under a new top-level `demo/` directory, kept separate from
`libraries/`. One `docker-compose.yml` defines seven services on a shared network.

### Infra services (off-the-shelf images)

| Service | Image | Host ports | Role |
|---|---|---|---|
| `otel-collector` | `otel/opentelemetry-collector-contrib` | 4318 | OTLP/HTTP receiver; pipelines logs→Loki, traces→Tempo |
| `loki` | `grafana/loki` | 3100 | Log store the collector pushes to |
| `tempo` | `grafana/tempo` | (internal) | Trace store — running but dormant |
| `grafana` | `grafana/grafana` | 3000 | UI; datasources + dashboards auto-provisioned |

### Sample apps (built from `demo/apps/<lang>`)

| Service | Base image | Role | Lib install |
|---|---|---|---|
| `python-app` | `python:3.11-slim` | HTTP server, entry of chain | `pip install` local **wheel** |
| `java-app` | `eclipse-temurin:21` | HTTP server, middle hop | `mvn install` local source (jar+POM) |
| `dotnet-app` | `mcr.microsoft.com/dotnet/sdk:8.0` | HTTP server, tail of chain | install local **nupkg** from a local NuGet source |
| `loadgen` | tiny (curl loop) | Hits `python-app` every few seconds | n/a |

### Library packaging

Pre-built artifacts where the tooling allows; build-from-source only where a bare
artifact isn't cleanly installable:

- **Python** — `python -m build` → `cloudops_otel_logs-*.whl`; image runs
  `pip install *.whl`.
- **.NET** — `dotnet pack` → `CloudOps.Otel.Logs.*.nupkg`; image installs it from
  a local NuGet source folder.
- **Java** — a bare `.jar` is not cleanly installable via Maven, so the java-app
  image `mvn install`s the library from local source (jar + POM) into its local
  Maven repo. This is the one build-from-source case.

All three paths exercise the real library code.

### Config choices

- **Startup order:** apps `depends_on` collector; collector `depends_on`
  loki/tempo. `depends_on` waits only for *start*, not readiness — correctness
  relies on retries/fallbacks, not ordering.
- **Grafana provisioning:** datasources (Loki + Tempo) and dashboards are mounted
  as YAML/JSON provisioning files, so `docker compose up` yields working
  dashboards with no manual clicking, all version-controlled.
- **Service identity:** each app sets `OTEL_SERVICE_NAME`
  (`python-app`/`java-app`/`dotnet-app`) for per-app filtering.

## Log labeling & dashboards

### Loki labels (indexed — kept small/bounded to avoid cardinality blowups)

- `service_name` — `python-app` / `java-app` / `dotnet-app` (3 values)
- `level` / `severity` — info/warn/error/debug (4 values)
- `detected_level` — for Grafana's built-in level coloring

Everything else (message, `order_id`, invocation id, structured fields) stays in
the log **body** as JSON — searchable via LogQL (`|=`, `| json`) but not indexed.

### Dashboards (auto-provisioned JSON)

1. **"All Apps — Logs Overview"**
   - Log volume over time, stacked by `service_name`.
   - Volume by `level` (spot error spikes).
   - Live log stream across all apps with a `service_name` dropdown filter.
   - Stat panels: logs/min, error count (last 5m).

2. **"Per-App Drilldown"** — templated by a `$service` variable
   - Pick an app → its log stream, level breakdown, error-only view.
   - One reusable dashboard rather than three near-duplicates.

## Error handling & resilience

- **Collector not up when an app starts:** libraries fall back to console logging
  if the OTLP endpoint is unreachable; OTLP exporters retry, so export resumes
  once the collector is up. No app crashes on cold start.
- **Loki/Tempo not ready when collector starts:** collector exporters queue and
  retry; transient "connection refused" in the first few seconds is expected and
  self-heals.
- **App crash:** `restart: unless-stopped` on each app service.
- **loadgen before python is ready:** loadgen loops with a sleep and ignores curl
  failures; early failures just retry next tick.

## Verification (evidence, not assertions)

1. `docker compose up -d` → `docker compose ps` shows all 7 services up.
2. Collector logs show OTLP log records received and exported to Loki with no
   persistent export errors.
3. Direct Loki API query (`/loki/api/v1/query_range` for each
   `{service_name="..."}`) returns lines for **all three** services — proves
   end-to-end before opening Grafana.
4. Grafana reachable at `localhost:3000`; provisioned datasource passes its health
   check; overview dashboard shows all three apps' streams.
5. `{level="error"}` query returns the deliberately-emitted error logs.

A `demo/README.md` documents the exact verification commands for re-runs.

## Testing scope

Demo apps are throwaway — the verification steps above are their test; no unit
suites for them. The **libraries** keep their existing test suites untouched;
this project only consumes them.

## Future work (separate specs)

- App-side trace emission (spans across the python→java→dotnet chain), landing in
  the already-provisioned Tempo. Likely needs a new traces library port.
- Optional real/private PyPI (and NuGet/Maven) publishing.
