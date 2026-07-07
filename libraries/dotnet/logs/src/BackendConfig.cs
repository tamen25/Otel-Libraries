// This file contains backend config logic for logs src.
using System.Text.Json.Serialization;

namespace CloudOps.Otel.Logs;

public sealed class BackendConfig
{
    [JsonPropertyName("logs")]
    public LogsExporterConfig? Logs { get; set; }
}
