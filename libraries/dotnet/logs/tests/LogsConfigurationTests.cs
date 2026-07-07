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
    // Reads SSM parameters prefers configured JSON and falls back to OTel environment.
    public void ReadSsmParametersPrefersConfiguredJsonAndFallsBackToOtelEnvironment()
    {
        using (new EnvironmentScope(new Dictionary<string, string?>
        {
            ["OTEL_SSM_PARAMETERS"] = """{"otel":{"logs":{"url":"https://collector.example.com/v1/logs","api_key":"secret"}}}""",
            ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "https://fallback.example.com",
            ["OTEL_API_KEY"] = "fallback-secret"
        }))
        {
            var parsed = LogsConfiguration.ReadSsmParameters();
            Assert.Equal("https://collector.example.com/v1/logs", parsed.Otel?.Logs?.Url);
            Assert.Equal("secret", parsed.Otel?.Logs?.ApiKey);
        }

        using (new EnvironmentScope(new Dictionary<string, string?>
        {
            ["OTEL_SSM_PARAMETERS"] = null,
            ["OTEL_SSM_PARAMETERS_FILE"] = Path.Combine(Path.GetTempPath(), $"missing-{Guid.NewGuid():N}.json"),
            ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "https://collector.example.com/",
            ["OTEL_API_KEY"] = "direct-secret"
        }))
        {
            var parsed = LogsConfiguration.ReadSsmParameters();
            Assert.Equal("https://collector.example.com/v1/logs", parsed.Otel?.Logs?.Url);
            Assert.Equal("direct-secret", parsed.Otel?.Logs?.ApiKey);
        }
    }

    [Fact]
    // Reads SSM parameters uses original params file before direct environment.
    public void ReadSsmParametersUsesOriginalParamsFileBeforeDirectEnvironment()
    {
        var tempDir = Directory.CreateTempSubdirectory("cloudops-otel-logs-");

        try
        {
            var paramsFile = Path.Combine(tempDir.FullName, "otelExporterParams.json");
            File.WriteAllText(
                paramsFile,
                """{"otel":{"logs":{"url":"https://file.example.com/v1/logs","api_key":"file-secret"}}}""");

            using (new EnvironmentScope(new Dictionary<string, string?>
            {
                ["OTEL_SSM_PARAMETERS_FILE"] = paramsFile,
                ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "https://fallback.example.com",
                ["OTEL_API_KEY"] = "fallback-secret"
            }))
            {
                var parsed = LogsConfiguration.ReadSsmParameters();
                Assert.Equal("https://file.example.com/v1/logs", parsed.Otel?.Logs?.Url);
                Assert.Equal("file-secret", parsed.Otel?.Logs?.ApiKey);
            }
        }
        finally
        {
            tempDir.Delete(recursive: true);
        }
    }

    [Fact]
    // Reads SSM parameters falls back to direct environment when file is invalid.
    public void ReadSsmParametersFallsBackToDirectEnvironmentWhenFileIsInvalid()
    {
        var tempDir = Directory.CreateTempSubdirectory("cloudops-otel-logs-");

        try
        {
            var paramsFile = Path.Combine(tempDir.FullName, "otelExporterParams.json");
            File.WriteAllText(paramsFile, "{not-json");

            using (new EnvironmentScope(new Dictionary<string, string?>
            {
                ["OTEL_SSM_PARAMETERS_FILE"] = paramsFile,
                ["OTEL_EXPORTER_OTLP_LOGS_ENDPOINT"] = "https://fallback.example.com/v1/logs",
                ["OTEL_API_KEY"] = "fallback-secret"
            }))
            {
                var parsed = LogsConfiguration.ReadSsmParameters();
                Assert.Equal("https://fallback.example.com/v1/logs", parsed.Otel?.Logs?.Url);
                Assert.Equal("fallback-secret", parsed.Otel?.Logs?.ApiKey);
            }
        }
        finally
        {
            tempDir.Delete(recursive: true);
        }
    }
}
