// This file contains logs exporter config logic for logs src.
using System.Text.Json.Serialization;

namespace CloudOps.Otel.Logs;

public sealed class LogsExporterConfig
{
    [JsonPropertyName("url")]
    public string? Url { get; set; }

    [JsonPropertyName("api_key")]
    public string? ApiKey { get; set; }
}
