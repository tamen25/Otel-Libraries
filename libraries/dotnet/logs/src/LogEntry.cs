// This file contains log entry logic for logs src.
namespace CloudOps.Otel.Logs;

// Logs entry.
internal sealed record LogEntry(
    string InvocationId,
    LogLevel Level,
    object? Message,
    object?[] OptionalParams);
