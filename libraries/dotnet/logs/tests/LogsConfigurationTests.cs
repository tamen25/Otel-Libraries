// This file contains logs configuration tests logic for logs tests.
using Xunit;

namespace CloudOps.Otel.Logs.Tests;

public sealed class LogsConfigurationTests
{
    [Fact]
    // Parses string array reads JSON and comma separated values.
    public void ParseStringArrayReadsJsonAndCommaSeparatedValues()
    {
        Assert.Equal(["console", "otel"], LogsConfiguration.ParseStringArray("[\"console\", \" otel \"]", ["fallback"]));
        Assert.Equal(["console", "otel"], LogsConfiguration.ParseStringArray("console, otel", ["fallback"]));
    }

    [Fact]
    // Parses string array copies fallback.
    public void ParseStringArrayCopiesFallback()
    {
        var fallback = new[] { "console" };
        var parsed = LogsConfiguration.ParseStringArray(null, fallback);

        Assert.NotSame(fallback, parsed);
        Assert.Equal(["console"], fallback);
    }

    [Fact]
    // Reads exporter parameters prefers configured JSON and falls back to OTel environment.
    public void ReadExporterParametersPrefersConfiguredJsonAndFallsBackToOtelEnvironment()
    {
        using (new EnvironmentScope(new Dictionary<string, string?>
        {
            ["OTEL_EXPORTER_PARAMETERS"] = """{"otel":{"logs":{"url":"https://collector.example.com/v1/logs"}}}""",
            ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "https://fallback.example.com"
        }))
        {
            var parsed = LogsConfiguration.ReadExporterParameters();
            Assert.Equal("https://collector.example.com/v1/logs", parsed.Otel?.Logs?.Url);
        }

        using (new EnvironmentScope(new Dictionary<string, string?>
        {
            ["OTEL_EXPORTER_PARAMETERS"] = null,
            ["OTEL_EXPORTER_PARAMETERS_FILE"] = Path.Combine(Path.GetTempPath(), $"missing-{Guid.NewGuid():N}.json"),
            ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "https://collector.example.com/"
        }))
        {
            var parsed = LogsConfiguration.ReadExporterParameters();
            Assert.Equal("https://collector.example.com/v1/logs", parsed.Otel?.Logs?.Url);
        }
    }

    [Fact]
    // Reads exporter parameters uses original params file before direct environment.
    public void ReadExporterParametersUsesOriginalParamsFileBeforeDirectEnvironment()
    {
        var tempDir = Directory.CreateTempSubdirectory("cloudops-otel-logs-");

        try
        {
            var paramsFile = Path.Combine(tempDir.FullName, "otelExporterParams.json");
            File.WriteAllText(
                paramsFile,
                """{"otel":{"logs":{"url":"https://file.example.com/v1/logs"}}}""");

            using (new EnvironmentScope(new Dictionary<string, string?>
            {
                ["OTEL_EXPORTER_PARAMETERS_FILE"] = paramsFile,
                ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "https://fallback.example.com"
            }))
            {
                var parsed = LogsConfiguration.ReadExporterParameters();
                Assert.Equal("https://file.example.com/v1/logs", parsed.Otel?.Logs?.Url);
            }
        }
        finally
        {
            tempDir.Delete(recursive: true);
        }
    }

    [Fact]
    // Reads exporter parameters falls back to direct environment when file is invalid.
    public void ReadExporterParametersFallsBackToDirectEnvironmentWhenFileIsInvalid()
    {
        var tempDir = Directory.CreateTempSubdirectory("cloudops-otel-logs-");

        try
        {
            var paramsFile = Path.Combine(tempDir.FullName, "otelExporterParams.json");
            File.WriteAllText(paramsFile, "{not-json");

            using (new EnvironmentScope(new Dictionary<string, string?>
            {
                ["OTEL_EXPORTER_PARAMETERS_FILE"] = paramsFile,
                ["OTEL_EXPORTER_OTLP_LOGS_ENDPOINT"] = "https://fallback.example.com/v1/logs"
            }))
            {
                var parsed = LogsConfiguration.ReadExporterParameters();
                Assert.Equal("https://fallback.example.com/v1/logs", parsed.Otel?.Logs?.Url);
            }
        }
        finally
        {
            tempDir.Delete(recursive: true);
        }
    }
}
