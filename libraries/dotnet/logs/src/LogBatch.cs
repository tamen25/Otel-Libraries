// This file contains log batch logic for logs src.
namespace Otel.Logs;

internal sealed class LogBatch
{
    // Logs batch.
    public LogBatch(LogEntry firstEntry)
    {
        Logs.Add(firstEntry);
    }

    public List<LogEntry> Logs { get; } = [];
}
