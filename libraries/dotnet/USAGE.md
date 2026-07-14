# .NET — Otel.Logs / Otel.Traces usage

OpenTelemetry logging and tracing for .NET services. Two independent packages —
reference only what you need. Targets net8.0.

## Install (NuGet)

Add your private NuGet feed to `nuget.config`, then:

```bash
dotnet add package Otel.Logs   --version 0.1.0
dotnet add package Otel.Traces --version 0.1.0
```

Or pack from the source in this package:

```bash
dotnet pack logs/Otel.Logs.csproj -c Release
dotnet pack traces/Otel.Traces.csproj -c Release
```

## Logging

```csharp
using Otel.Logs;
var logger = Logger.Init();

logger.Info("order created", orderId);
logger.Warn("retrying", attempt);
logger.Error(exception);
// logger.ExportLogs();   // optional — batched logs also flush on ProcessExit
```

## Tracing

One line in startup registers ASP.NET Core + HttpClient auto-instrumentation, so
inbound and outbound HTTP propagate W3C `tracecontext` automatically:

```csharp
using Otel.Traces;
var builder = WebApplication.CreateBuilder(args);
builder.Services.AddOtelTraces();
var app = builder.Build();
```

The TracerProvider is disposed by the host on graceful shutdown, which flushes
pending spans.

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
secret** — safe to keep in plain config. Azure runtime attributes are added
automatically.

## Test

```bash
dotnet test logs/tests/Otel.Logs.Tests.csproj
dotnet test traces/tests/Otel.Traces.Tests.csproj
```
