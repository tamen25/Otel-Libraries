# OtelLibraries — Telemetry Client Libraries (Python / Java / .NET / Node.js)

A standalone, self-contained set of OpenTelemetry (OTel) client libraries. Each
language port wraps OpenTelemetry to give services a small, consistent logging
and tracing API. Every port implements the **same logical design** and honours
the **same `OTEL_*` environment-variable contract**, so behaviour stays identical
across runtimes. This project is fully independent — there is no external
organisation or monorepo it depends on.

## What this is

Two signals are implemented, each a separate package so apps adopt only what
they need:

- **logs** — `libraries/<lang>/logs`
- **traces** — `libraries/<lang>/traces`

New signals (e.g. metrics) follow the same shape: `libraries/<language>/<signal>/`.

## Layout

```text
libraries/
  python/{logs,traces}/    otel-logs / otel-traces            (pyproject.toml, hatchling)
  java/{logs,traces}/      otel:otel-logs / otel:otel-traces  (pom.xml, Maven)
  dotnet/{logs,traces}/    Otel.Logs / Otel.Traces            (.csproj, net8.0)
  nodejs/{logs,traces}/    @otel/logs / @otel/traces          (package.json, TypeScript)
  README.md
```

Each library has a `src/` (or package) tree, a `tests/` tree, its own `README.md`,
and its build manifest. (`nodejs/metrics/` exists but is out of scope.)

## The shared design (keep ports in sync)

All four ports mirror the same structure. When you change behaviour in one
language, apply the equivalent change to the others.

**Logs** — public entry point `Logger` (`Logger.init()` / `Logger.Init()`; in
Python/Node a module-level `logger` singleton). Methods: `info` / `error` /
`debug` / `warn`, plus `log(level, message, …)` and a flush (`export_logs()` /
`exportLogs()` / `ExportLogs()`). Batched logs are **flushed automatically at
process shutdown** (atexit / shutdown hook / `ProcessExit` / `beforeExit`+SIGTERM);
the explicit flush is only needed in serverless. Internals: `LogSampler`
(per-invocation batching + probabilistic sampling; a batch is always emitted if
it contains an `error`, else sampled at `OTEL_LOGS_SAMPLING_RATE`), `LogEntry` /
`LogBatch`, `LogsConfiguration` / `BackendConfig` / `ExporterParameters`,
`RuntimeResourceAttributes` (Azure runtime detection).

**Traces** — public entry point `Tracer` / `init()`. Registers the W3C
`tracecontext` propagator and HTTP auto-instrumentation so a request stays one
connected trace across services. Per-language surface:

- **Node.js**: `import "@otel/traces/register"` (side-effect init) — or the
  `tracer` / `AzureService` exports for manual/Azure-service spans.
- **Python**: no-arg `init()` — opportunistically instruments `requests` + Flask.
- **.NET**: `builder.Services.AddOtelTraces()` (ASP.NET Core + HttpClient).
- **Java**: `Tracer.init()` plus framework-free edge helpers `tracedClient()`
  (CLIENT span + header injection) and `wrap(name, handler)` (SERVER span);
  lower-level `startServerSpan` / `startClientSpan` / `injectHeaders` remain public.

> **Init-before-framework rule:** tracing must be initialised before the app's
> web framework loads (Node: require `register` first; Python: call `init()`
> before importing Flask). HTTP auto-instrumentation must patch the HTTP layer
> before the server is created.

Exporters: `console` (default) and `otel` (OTLP/HTTP). The `otel` exporter is
used only when **both** an endpoint URL and `X_ORG_ID` resolve (from env or the
`DEFAULT_*` constants); otherwise — or if OTel deps are unavailable — ports fall
back to console.

### `OTEL_*` env-var contract (identical across languages)

- `OTEL_BACKEND_EXPORTERS` — `console` (default) or `otel` (JSON array or CSV). The explicit backend switch.
- `OTEL_LOG_LEVEL` — enabled levels among `info,error,debug,warn` (logs).
- `OTEL_LOGS_SAMPLING_RATE` — 0–100 (default 100) (logs).
- `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT` / `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` / `OTEL_EXPORTER_OTLP_ENDPOINT` — endpoint (normalised to `/v1/logs` or `/v1/traces`).
- `X_ORG_ID` — **org identifier (not a secret)**, sent as the `X-OrgId` header on every OTLP export; required for `otel`, else console.
- `OTEL_SERVICE_NAME` / `OTEL_RESOURCE_ATTRIBUTES` — resource identity.
- `OTEL_EXPORTER_PARAMETERS` (inline JSON) — exporter config (`otel.logs.url` / `otel.trace.url`).

Azure runtime auto-detection uses `FUNCTIONS_EXTENSION_VERSION`/`FUNCTIONS_WORKER_RUNTIME`,
`WEBSITE_SITE_NAME`, `CONTAINER_APP_NAME`, `KUBERNETES_SERVICE_HOST`, `K8S_*`/`POD_*`, etc.

## Build & test

Run each library from its own directory.

- **Python** (≥ 3.11): `PYTHONPATH=src python -m pytest -q`
- **Java** (21, Maven): `mvn -q verify` (use the absolute `-f <pom>` path — the shell cwd can reset)
- **.NET** (net8.0): `dotnet test tests/<Name>.Tests.csproj` (the test project is separate)
- **Node.js** (≥ 22, TypeScript): `npm test` / `npm run test:coverage`

## Package identities

| Lang    | Logs              | Traces              | Manifest       |
|---------|-------------------|---------------------|----------------|
| Python  | `otel-logs`       | `otel-traces`       | pyproject.toml |
| Java    | `otel:otel-logs`  | `otel:otel-traces`  | pom.xml        |
| .NET    | `Otel.Logs`       | `Otel.Traces`       | .csproj        |
| Node.js | `@otel/logs`      | `@otel/traces`      | package.json   |

OTel SDK versions: Python `1.41.0`, Java `1.60.1`, .NET `1.15.3`, Node.js OTel JS
2.x line (core/resources/sdk `2.9.0`, experimental `0.220.0`).

## Demo

`demo/` runs all four languages through **Grafana Alloy** (collector) into
**Loki** (logs), **Tempo** (traces), and **Mimir** (service-graph metrics), with
**Grafana** for correlated logs+traces and a service-graph flow chart. See
`demo/README.md`.

## Conventions

- **Keep the four ports behaviourally in sync** — same env-var handling, sampling
  logic, and runtime detection. A change to one usually needs the same change in
  the others; call it out if you intentionally diverge.
- Match the existing code style in each language (the Python source uses terse
  `#comment` headers above functions; mirror the file's local idiom).
- Tests live beside the code under `tests/` (or `src/test`) — add/adjust tests
  with any behaviour change; each port has a coverage gate.
- Don't commit build artifacts (`bin/`, `obj/`, `target/`, `dist/`, `node_modules/`,
  `__pycache__/`, `*.pyc`, `TestResults/`, `demo/artifacts/`) — see `.gitignore`.

## Git commit messages

- Do **not** include `Co-Authored-By` lines or any AI/Claude/Anthropic
  attribution in commit messages.
