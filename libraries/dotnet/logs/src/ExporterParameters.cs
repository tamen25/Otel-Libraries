// This file contains exporter parameters logic for logs src.
using System.Text.Json.Serialization;

namespace CloudOps.Otel.Logs;

public sealed class ExporterParameters
{
    [JsonPropertyName("otel")]
    public BackendConfig? Otel { get; set; }

    // Checks whether empty.
    public bool IsEmpty()
    {
        return Otel?.Logs == null
            || (string.IsNullOrWhiteSpace(Otel.Logs.Url) && string.IsNullOrWhiteSpace(Otel.Logs.ApiKey));
    }

    // Handles backend.
    public BackendConfig? Backend(string name)
    {
        return name == "otel" ? Otel : null;
    }
}
