// This file contains logs configuration logic for logs src.
using System.Text.Json;

namespace Otel.Logs;

internal static class LogsConfiguration
{
    // Hardcoded fallbacks for the OTLP logs endpoint and org id. Env vars override
    // these; leave them empty to fall back to console. X_ORG_ID is required for OTLP
    // export no matter what — without it the logger always uses console.
    public const string DefaultLogsEndpoint = "";
    public const string DefaultXOrgId = "";

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true
    };

    // Reads exporter parameters.
    public static ExporterParameters ReadExporterParameters()
    {
        var configured = Environment.GetEnvironmentVariable("OTEL_EXPORTER_PARAMETERS");
        if (HasValue(configured))
        {
            try
            {
                var parsed = JsonSerializer.Deserialize<ExporterParameters>(configured!, JsonOptions);
                if (parsed is not null && !parsed.IsEmpty()) return parsed;
            }
            catch (JsonException)
            {
                // Fall through to the direct OTEL env vars and the hardcoded default.
            }
        }

        var logsUrl = FirstValue(
            Environment.GetEnvironmentVariable("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT"),
            NormalizeEndpoint(Environment.GetEnvironmentVariable("OTEL_EXPORTER_OTLP_ENDPOINT")),
            DefaultLogsEndpoint);

        var parameters = new ExporterParameters();
        if (HasValue(logsUrl))
        {
            parameters.Otel = new BackendConfig
            {
                Logs = new LogsExporterConfig
                {
                    Url = logsUrl
                }
            };
        }

        return parameters;
    }

    // Resolves org id.
    public static string? OrgId()
    {
        return FirstValue(Environment.GetEnvironmentVariable("X_ORG_ID"), DefaultXOrgId);
    }

    // Parses string array.
    public static IReadOnlyList<string> ParseStringArray(string? raw, IReadOnlyList<string> fallback)
    {
        if (!HasValue(raw)) return fallback.ToArray();

        try
        {
            var parsed = JsonSerializer.Deserialize<string[]>(raw!, JsonOptions);
            if (parsed is { Length: > 0 })
            {
                var jsonValues = parsed.Select(item => item.Trim()).Where(HasValue).ToArray();
                if (jsonValues.Length > 0) return jsonValues;
            }
        }
        catch (JsonException)
        {
            // Fall back to comma-separated values.
        }

        var values = raw!.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        return values.Length > 0 ? values : fallback.ToArray();
    }

    // Gets sampling rate.
    public static double SamplingRate()
    {
        return double.TryParse(Environment.GetEnvironmentVariable("OTEL_LOGS_SAMPLING_RATE"), out var value)
            ? value
            : 100;
    }

    // Handles has value.
    public static bool HasValue(string? value)
    {
        return !string.IsNullOrWhiteSpace(value);
    }

    // Finds first value.
    public static string? FirstValue(params string?[] values)
    {
        return values.FirstOrDefault(HasValue);
    }

    // Normalizes endpoint.
    private static string? NormalizeEndpoint(string? endpoint)
    {
        if (!HasValue(endpoint)) return null;

        var normalized = endpoint!.EndsWith("/", StringComparison.Ordinal)
            ? endpoint[..^1]
            : endpoint;
        return normalized.EndsWith("/v1/logs", StringComparison.Ordinal) ? normalized : $"{normalized}/v1/logs";
    }
}
