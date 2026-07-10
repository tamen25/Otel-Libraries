// This file contains cloud ops logger tests logic for logs tests.
using Xunit;

namespace Otel.Logs.Tests;

public sealed class LoggerTests
{
    [Fact]
    // Parses log levels ignores unknown values.
    public void ParseLogLevelsIgnoresUnknownValues()
    {
        Assert.True(Logger.ParseLogLevels("bad,error").SetEquals([LogLevel.Error]));
        Assert.True(Logger.ParseLogLevels("bad").SetEquals(Enum.GetValues<LogLevel>()));
    }

    [Fact]
    // Handles console logger renders enabled messages and structured params.
    public void ConsoleLoggerRendersEnabledMessagesAndStructuredParams()
    {
        using var env = new EnvironmentScope(new Dictionary<string, string?>
        {
            ["OTEL_BACKEND_EXPORTERS"] = "console",
            ["OTEL_LOG_LEVEL"] = "info,error",
            ["OTEL_LOGS_SAMPLING_RATE"] = "0"
        });

        var originalOut = Console.Out;
        using var output = new StringWriter();
        Console.SetOut(output);

        try
        {
            var logger = new Logger();
            logger.Info("created order", new { order_id = 42 });
            logger.Debug("debug should be disabled");
            logger.ExportLogs();
        }
        finally
        {
            Console.SetOut(originalOut);
        }

        var rendered = output.ToString();
        Assert.Contains("created order", rendered);
        Assert.Contains("order_id", rendered);
        Assert.DoesNotContain("debug should be disabled", rendered);
    }

    [Fact]
    // Handles otel requested without X_ORG_ID falling back to console.
    public void OtelWithoutOrgIdFallsBackToConsole()
    {
        using var env = new EnvironmentScope(new Dictionary<string, string?>
        {
            ["OTEL_BACKEND_EXPORTERS"] = "otel",
            ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "https://collector.example.com",
            ["OTEL_LOGS_SAMPLING_RATE"] = "0"
        });

        var originalOut = Console.Out;
        using var output = new StringWriter();
        Console.SetOut(output);

        try
        {
            var logger = new Logger();
            logger.Info("gated to console");
            logger.ExportLogs();
        }
        finally
        {
            Console.SetOut(originalOut);
        }

        Assert.Contains("gated to console", output.ToString());
    }

    [Fact]
    // Handles otel with endpoint and X_ORG_ID not writing to console.
    public void OtelWithEndpointAndOrgIdDoesNotUseConsole()
    {
        using var env = new EnvironmentScope(new Dictionary<string, string?>
        {
            ["OTEL_BACKEND_EXPORTERS"] = "otel",
            ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "https://collector.example.com",
            ["X_ORG_ID"] = "org-123",
            ["OTEL_LOGS_SAMPLING_RATE"] = "0"
        });

        var originalOut = Console.Out;
        using var output = new StringWriter();
        Console.SetOut(output);

        try
        {
            var logger = new Logger();
            logger.Info("should go to otel");
        }
        finally
        {
            Console.SetOut(originalOut);
        }

        Assert.DoesNotContain("should go to otel", output.ToString());
    }
}
