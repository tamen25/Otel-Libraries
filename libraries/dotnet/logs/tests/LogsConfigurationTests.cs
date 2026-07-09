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
    // Reads exporter parameters prefers the JSON blob over the env endpoint.
    public void ReadExporterParametersPrefersJsonOverEnvEndpoint()
    {
        using var env = new EnvironmentScope(new Dictionary<string, string?>
        {
            ["OTEL_EXPORTER_PARAMETERS"] = """{"otel":{"logs":{"url":"https://collector.example.com/v1/logs"}}}""",
            ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "https://fallback.example.com"
        });

        var parsed = LogsConfiguration.ReadExporterParameters();
        Assert.Equal("https://collector.example.com/v1/logs", parsed.Otel?.Logs?.Url);
    }

    [Fact]
    // Reads exporter parameters normalises the env endpoint fallback.
    public void ReadExporterParametersNormalisesEnvEndpoint()
    {
        using var env = new EnvironmentScope(new Dictionary<string, string?>
        {
            ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "https://collector.example.com/"
        });

        var parsed = LogsConfiguration.ReadExporterParameters();
        Assert.Equal("https://collector.example.com/v1/logs", parsed.Otel?.Logs?.Url);
    }

    [Fact]
    // Reads exporter parameters is empty when no endpoint is configured.
    public void ReadExporterParametersIsEmptyWithoutEndpoint()
    {
        using var env = new EnvironmentScope(new Dictionary<string, string?>());

        var parsed = LogsConfiguration.ReadExporterParameters();
        Assert.True(parsed.IsEmpty());
    }

    [Fact]
    // Resolves org id from the environment, else null when unset.
    public void OrgIdPrefersEnvironmentElseNull()
    {
        using (new EnvironmentScope(new Dictionary<string, string?> { ["X_ORG_ID"] = "org-from-env" }))
        {
            Assert.Equal("org-from-env", LogsConfiguration.OrgId());
        }

        using (new EnvironmentScope(new Dictionary<string, string?>()))
        {
            Assert.Null(LogsConfiguration.OrgId());
        }
    }
}
