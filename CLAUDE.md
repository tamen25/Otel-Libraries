# OtelLibraries — CloudOps Telemetry Client Libraries (Python / Java / .NET)

This project is a standalone extraction of the CloudOps OpenTelemetry (OTel)
client libraries. It was copied from the larger `CloudOps` monorepo and trimmed
to only the **Python**, **Java**, and **.NET** ports. The goal here is to
continue developing these libraries in isolation.

## What this is

A set of parallel client libraries that wrap OpenTelemetry to give services a
small, consistent logging API. Every language port implements the **same
logical design** and honours the **same `OTEL_*` environment-variable
contract**, so behaviour stays identical across runtimes.

Currently only the **logs** signal is implemented (`libraries/<lang>/logs`).
Metrics and traces are future signals; new signals follow the same shape:
`libraries/<language>/<signal>/`.

## Layout

```text
libraries/
  python/logs/     cloudops-otel-logs        (pyproject.toml, hatchling)
  java/logs/       com.cloudops:otel-logs    (pom.xml, Maven)
  dotnet/logs/     CloudOps.Otel.Logs        (.csproj, net8.0)
  README.md
```

Each library has: a `src/` (or package) tree, a `tests/` tree, its own
`README.md`, and its build manifest.

## The shared design (keep ports in sync)

All three ports mirror the same class/type structure. When you change behaviour
in one language, apply the equivalent change to the others:

- `CloudOpsLogger` — public entry point. Methods: `info` / `error` / `debug` /
  `warn`, plus `log(level, message, ...)`, `export_logs()` (flush).
- `LogSampler` — per-invocation batching + probabilistic sampling. Batches are
  keyed by invocation id; a batch is always emitted if it contains an `error`,
  otherwise it is sampled at `OTEL_LOGS_SAMPLING_RATE`.
- `LogEntry` / `LogBatch` — data carriers.
- `LogsExporterConfig` / `BackendConfig` / `SsmParameters` — exporter config,
  resolved from env vars, an inline `OTEL_SSM_PARAMETERS` JSON blob, or the
  SSM parameters file (`/tmp/otelExporterParams.json` by default).
- `RuntimeResourceAttributes` — derives OTel resource attributes and detects the
  AWS runtime (Lambda / ECS / EKS / plain Kubernetes) from env vars.
- `LogsConfiguration` (Java/.NET) — configuration surface.

Exporters: `console` (default) and `otel` (OTLP/HTTP). If OTel deps or exporter
config are unavailable, ports fall back to console.

### `OTEL_*` env-var contract (identical across languages)

- `OTEL_BACKEND_EXPORTERS` — list, e.g. `console`, `otel` (JSON array or CSV).
- `OTEL_LOG_LEVEL` — enabled levels among `info,error,debug,warn`.
- `OTEL_LOGS_SAMPLING_RATE` — 0–100 (default 100 = emit everything).
- `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT` / `OTEL_EXPORTER_OTLP_ENDPOINT` — endpoint
  (the plain endpoint is normalised to end in `/v1/logs`).
- `OTEL_API_KEY` / `OTEL_EXPORTER_OTLP_HEADERS` — auth (sent as
  `authorization: Bearer <key>`).
- `OTEL_SERVICE_NAME` / `OTEL_RESOURCE_ATTRIBUTES` — resource identity.
- `OTEL_SSM_PARAMETERS` (inline JSON) / `OTEL_SSM_PARAMETERS_FILE` — exporter
  config source; falls back to `/tmp/otelExporterParams.json`.

AWS runtime auto-detection uses `AWS_LAMBDA_FUNCTION_NAME`,
`ECS_CONTAINER_METADATA_URI*`, `KUBERNETES_SERVICE_HOST`, `K8S_*`/`POD_*`, etc.

## Build & test

Run each library from its own directory.

**Python** (`libraries/python/logs`, requires Python ≥ 3.11):
```bash
python -m venv .venv && . .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]" || pip install -e .
pytest                     # rtk vitest-style: prefer `rtk pytest` if configured
```

**Java** (`libraries/java/logs`, Java 21, Maven):
```bash
mvn -q test                # unit tests + JaCoCo coverage
mvn -q package             # build the jar
```

**.NET** (`libraries/dotnet/logs`, net8.0):
```bash
dotnet test                # tests + Cobertura coverage
dotnet pack                # build the NuGet package
```

## Package identities

| Lang   | Package                    | Manifest       | Runtime      |
|--------|----------------------------|----------------|--------------|
| Python | `cloudops-otel-logs`       | pyproject.toml | Python ≥3.11 |
| Java   | `com.cloudops:otel-logs`   | pom.xml        | Java 21      |
| .NET   | `CloudOps.Otel.Logs`       | .csproj        | net8.0       |

OTel SDK versions in use: Python `1.41.0`, Java (`${otel.version}` in pom),
.NET `1.15.3`.

## Conventions

- **Keep the three ports behaviourally in sync** — same env-var handling, same
  sampling logic, same runtime detection. A change to one usually needs the
  same change in the other two; call it out if you intentionally diverge.
- Match the existing code style in each language (the Python source uses terse
  `#comment` headers above functions; mirror the file's local idiom).
- Tests live beside the code under `tests/` (or `src/test`) — add/adjust tests
  with any behaviour change; each port has a coverage gate.
- Don't commit build artifacts (`bin/`, `obj/`, `target/`, `dist/`,
  `__pycache__/`, `*.pyc`, `TestResults/`) — see `.gitignore`.

## Git commit messages

- Do **not** include `Co-Authored-By` lines or any AI/Claude/Anthropic
  attribution in commit messages.

## Origin

Extracted from the `CloudOps` monorepo's `libraries/` tree (which also has
Node.js, Go, and C++ ports plus a full Terraform/infra stack). Publishing in the
original repo went to AWS CodeArtifact via GitHub Actions; that pipeline was
**not** copied here. This project is source-only for library development.
