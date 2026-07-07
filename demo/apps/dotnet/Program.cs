// .NET tail service: logs and finalizes the order.
using CloudOps.Otel.Logs;

var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();
var log = CloudOpsLogger.InitializeLogger();

app.MapGet("/health", () => Results.Ok("ok"));

app.MapGet("/finalize", (string? order_id) =>
{
    var id = order_id ?? "unknown";
    log.Info("finalizing order", new Dictionary<string, object?> { ["order_id"] = id, ["hop"] = "dotnet" });
    log.ExportLogs();
    return Results.Ok(new { order_id = id, finalized = true });
});

log.Info("dotnet-app started", new Dictionary<string, object?> { ["port"] = 8081 });
app.Run("http://0.0.0.0:8081");
