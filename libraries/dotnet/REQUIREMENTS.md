# .NET — what to install

## Toolchain (install on the machine)

- **.NET SDK 8.0** (both packages target `net8.0`)
- The **ASP.NET Core shared framework** (`Microsoft.AspNetCore.App`), used by the
  traces package — it ships with the .NET SDK, nothing extra to install.

## Library dependencies

NuGet restores these automatically from each `.csproj` on `dotnet restore`/`build`
— you don't install them by hand.

**`Otel.Logs`**:
- `Microsoft.Extensions.Logging` 10.0.0
- `OpenTelemetry` 1.15.3
- `OpenTelemetry.Exporter.OpenTelemetryProtocol` 1.15.3

**`Otel.Traces`**:
- `OpenTelemetry` 1.15.3
- `OpenTelemetry.Extensions.Hosting` 1.15.3
- `OpenTelemetry.Exporter.OpenTelemetryProtocol` 1.15.3
- `OpenTelemetry.Instrumentation.AspNetCore` 1.12.0
- `OpenTelemetry.Instrumentation.Http` 1.12.0

## Build / test / pack

```bash
dotnet test logs/tests/Otel.Logs.Tests.csproj
dotnet test traces/tests/Otel.Traces.Tests.csproj

dotnet pack logs/Otel.Logs.csproj -c Release       # -> Otel.Logs.0.1.0.nupkg
dotnet pack traces/Otel.Traces.csproj -c Release   # -> Otel.Traces.0.1.0.nupkg
```
