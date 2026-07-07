// This file contains cloud ops logger tests logic for logs tests.
using Xunit;

namespace CloudOps.Otel.Logs.Tests;

public sealed class CloudOpsLoggerTests
{
    [Fact]
    // Parses log levels ignores unknown values.
    public void ParseLogLevelsIgnoresUnknownValues()
    {
        Assert.True(CloudOpsLogger.ParseLogLevels("bad,error").SetEquals([LogLevel.Error]));
        Assert.True(CloudOpsLogger.ParseLogLevels("bad").SetEquals(Enum.GetValues<LogLevel>()));
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
            var logger = new CloudOpsLogger();
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
}
