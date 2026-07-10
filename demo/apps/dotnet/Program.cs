// .NET tail service: logs and finalizes the order.
using CloudOps.Otel.Logs;
using CloudOps.Otel.Traces;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddCloudOpsTracing();
var app = builder.Build();
var log = CloudOpsLogger.InitializeLogger();

app.MapGet("/health", () => Results.Ok("ok"));

var finalizeCount = 0;

app.MapGet("/finalize", (string? order_id) =>
{
    var id = order_id ?? "unknown";
    var n = Interlocked.Increment(ref finalizeCount);
    log.Debug("validating finalize request", new Dictionary<string, object?> { ["order_id"] = id, ["hop"] = "dotnet" });
    log.Info("finalizing order", new Dictionary<string, object?> { ["order_id"] = id, ["hop"] = "dotnet" });
    if (n % 5 == 0)
    {
        log.Warn("finalize queue depth high (simulated)", new Dictionary<string, object?> { ["order_id"] = id, ["queue_depth"] = n });
    }
    log.ExportLogs();
    return Results.Ok(new { order_id = id, finalized = true });
});

log.Info("dotnet-app started", new Dictionary<string, object?> { ["port"] = 8081 });
app.Run("http://0.0.0.0:8081");
