// This file contains logs exporter config logic for logs src.
using System.Text.Json.Serialization;

namespace Otel.Logs;

public sealed class LogsExporterConfig
{
    [JsonPropertyName("url")]
    public string? Url { get; set; }
}
