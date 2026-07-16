# OtelLibraries

OpenTelemetry client libraries — **Python**, **Java**, **.NET**, and **Node.js** —
for the **logs** and **traces** signals, kept in sync behind a common `OTEL_*`
environment-variable contract.

## Libraries

| Language | Signal        | Package                                | Build          |
|----------|---------------|----------------------------------------|----------------|
| Python   | logs / traces | `otel-logs` / `otel-traces`            | `pytest`       |
| Java     | logs / traces | `otel:otel-logs` / `otel:otel-traces`  | `mvn test`     |
| .NET     | logs / traces | `Otel.Logs` / `Otel.Traces`            | `dotnet test`  |
| Node.js  | logs / traces | `@otel/logs` / `@otel/traces`          | `npm test`     |

## Quick start (build & test)

Each library builds and tests from its own directory:

```bash
cd libraries/python/logs && pip install -e . && pytest                  # Python >= 3.11
cd libraries/java/logs   && mvn test                                    # Java 21
cd libraries/dotnet/logs && dotnet test tests/Otel.Logs.Tests.csproj    # net8.0
cd libraries/nodejs/logs && npm test                                    # Node >= 22
```

## Using the libraries in an app

Start with **[`GETTING-STARTED.md`](./GETTING-STARTED.md)** — how to use the
libraries plus the full `OTEL_*` environment-variable configuration. For deeper
per-language detail see [`docs/USING-THE-LIBRARIES.md`](./docs/USING-THE-LIBRARIES.md)
and each [`libraries/<lang>/USAGE.md`](./libraries/); prerequisites to install are
in each `libraries/<lang>/REQUIREMENTS.md`. For the shared design and
cross-language conventions, see [`CLAUDE.md`](./CLAUDE.md).

A runnable end-to-end demo (all four languages → Grafana Alloy → Loki/Tempo/Mimir
→ Grafana, with correlated logs+traces and a service-graph flow chart) lives in
[`demo/`](./demo/README.md).
