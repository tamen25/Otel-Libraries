# OtelLibraries

CloudOps OpenTelemetry client libraries — **Python**, **Java**, and **.NET**.

A standalone extraction of the `logs` client libraries from the CloudOps
monorepo, kept in sync across three languages behind a common `OTEL_*`
environment-variable contract.

## Libraries

| Language | Path                   | Package                  | Build   |
|----------|------------------------|--------------------------|---------|
| Python   | `libraries/python/logs`| `cloudops-otel-logs`     | `pytest` |
| Java     | `libraries/java/logs`  | `com.cloudops:otel-logs` | `mvn test` |
| .NET     | `libraries/dotnet/logs`| `CloudOps.Otel.Logs`     | `dotnet test` |

## Quick start

Each library builds and tests from its own directory:

```bash
# Python (>= 3.11)
cd libraries/python/logs && pip install -e . && pytest

# Java 21
cd libraries/java/logs && mvn test

# .NET (net8.0)
cd libraries/dotnet/logs && dotnet test
```

See [`CLAUDE.md`](./CLAUDE.md) for the shared design, the full `OTEL_*` contract,
and cross-language conventions.
