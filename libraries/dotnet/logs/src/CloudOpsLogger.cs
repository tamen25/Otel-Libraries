// This file contains cloud ops logger logic for logs src.
using System.Text;
using System.Text.Json;
using Microsoft.Extensions.Logging;
using OpenTelemetry.Exporter;
using OpenTelemetry.Logs;
using OpenTelemetry.Resources;

namespace CloudOps.Otel.Logs;

public sealed class CloudOpsLogger
{
    private static readonly IReadOnlyList<string> DefaultExporters = ["console"];
    private static readonly Lazy<CloudOpsLogger> Instance = new(() => new CloudOpsLogger());
    private readonly HashSet<LogLevel> enabledLevels;
    private readonly IReadOnlyList<string> exportersList;
    private readonly LogSampler sampler;
    private ILoggerFactory? loggerFactory;
    private ILogger? otelLogger;
    private bool useConsole;
    private bool useOtel;
    private string? previousTraceId;
    private string? uniqueId;

    // Handles cloud ops logger.
    internal CloudOpsLogger()
    {
        ResourceAttributes = RuntimeResourceAttributes.Create();
        enabledLevels = ParseLogLevels(Environment.GetEnvironmentVariable("OTEL_LOG_LEVEL"));
        exportersList = LogsConfiguration.ParseStringArray(Environment.GetEnvironmentVariable("OTEL_BACKEND_EXPORTERS"), DefaultExporters);
        sampler = new LogSampler(this);
        Init();
    }

    public IReadOnlyDictionary<string, string> ResourceAttributes { get; }

    // Initializes logger.
    public static CloudOpsLogger InitialiseLogger()
    {
        return Instance.Value;
    }

    // Initializes logger.
    public static CloudOpsLogger InitializeLogger()
    {
        return Instance.Value;
    }

    // Handles info.
    public void Info(object? message, params object?[] optionalParams)
    {
        Log(LogLevel.Info, message, optionalParams);
    }

    // Handles error.
    public void Error(object? message, params object?[] optionalParams)
    {
        Log(LogLevel.Error, message, optionalParams);
    }

    // Handles debug.
    public void Debug(object? message, params object?[] optionalParams)
    {
        Log(LogLevel.Debug, message, optionalParams);
    }

    // Handles warn.
    public void Warn(object? message, params object?[] optionalParams)
    {
        Log(LogLevel.Warn, message, optionalParams);
    }

    // Exports logs.
    public void ExportLogs()
    {
        sampler.FlushOneBatch();
        Console.Out.Flush();
        Console.Error.Flush();

        if (useOtel)
        {
            loggerFactory?.Dispose();
            InitOtelLogger();
        }
    }

    // Logs the requested work.
    private void Log(LogLevel level, object? message, object?[] optionalParams)
    {
        var currentTraceId = CurrentTraceId();
        if (currentTraceId != previousTraceId)
        {
            uniqueId = Guid.NewGuid().ToString();
            previousTraceId = currentTraceId;
        }

        sampler.AddLog(new LogEntry(uniqueId ?? "unknown", level, message, optionalParams));
    }

    // Processes log.
    internal void ProcessLog(LogEntry logEntry)
    {
        if (!enabledLevels.Contains(logEntry.Level)) return;

        var rendered = Render(logEntry.Message, logEntry.OptionalParams);
        if (useConsole)
        {
            if (logEntry.Level == LogLevel.Error)
            {
                Console.Error.WriteLine(rendered);
            }
            else
            {
                Console.WriteLine(rendered);
            }
        }

        if (useOtel && otelLogger is not null)
        {
            using var scope = otelLogger.BeginScope(LogAttributes(logEntry.InvocationId));
            otelLogger.Log(ToMicrosoftLevel(logEntry.Level), ToException(logEntry.Message), "{Message}", rendered);
        }
    }

    // Initializes the requested work.
    private void Init()
    {
        if (exportersList.Count <= 1 && exportersList.Contains("console", StringComparer.OrdinalIgnoreCase))
        {
            useConsole = true;
            return;
        }

        var exporterParameters = LogsConfiguration.ReadExporterParameters();
        if (exporterParameters.IsEmpty())
        {
            useConsole = true;
            return;
        }

        foreach (var exporter in exportersList.Select(item => item.Trim().ToLowerInvariant()))
        {
            switch (exporter)
            {
                case "console":
                    useConsole = true;
                    break;
                case "otel":
                    InitOtelLogger(exporterParameters);
                    break;
                default:
                    useConsole = true;
                    break;
            }
        }
    }

    // Initializes OTel logger.
    private void InitOtelLogger(ExporterParameters? exporterParameters = null)
    {
        exporterParameters ??= LogsConfiguration.ReadExporterParameters();
        var config = exporterParameters.Backend("otel")?.Logs;
        if (config is null)
        {
            useConsole = true;
            return;
        }

        loggerFactory = LoggerFactory.Create(builder =>
        {
            builder.SetMinimumLevel(Microsoft.Extensions.Logging.LogLevel.Trace);
            builder.AddOpenTelemetry(options =>
            {
                options.IncludeFormattedMessage = true;
                options.IncludeScopes = true;
                options.ParseStateValues = true;
                options.SetResourceBuilder(ResourceBuilder.CreateDefault().AddAttributes(
                    ResourceAttributes.Select(item => new KeyValuePair<string, object>(item.Key, item.Value))));
                options.AddOtlpExporter(exporterOptions =>
                {
                    exporterOptions.Protocol = OtlpExportProtocol.HttpProtobuf;
                    if (LogsConfiguration.HasValue(config.Url))
                    {
                        exporterOptions.Endpoint = new Uri(config.Url!);
                    }
                    var orgId = Environment.GetEnvironmentVariable("X_ORG_ID");
                    if (LogsConfiguration.HasValue(orgId))
                    {
                        exporterOptions.Headers = $"X-OrgId={orgId}";
                    }
                });
            });
        });

        otelLogger = loggerFactory.CreateLogger(ResourceAttributes.GetValueOrDefault("service.name", "unknown_service"));
        useOtel = true;
    }

    // Logs attributes.
    private static IReadOnlyDictionary<string, object> LogAttributes(string invocationId)
    {
        var attributes = new Dictionary<string, object>(StringComparer.Ordinal)
        {
            ["invocation.id"] = string.IsNullOrWhiteSpace(invocationId) ? "unknown" : invocationId
        };

        var activity = System.Diagnostics.Activity.Current;
        if (activity is not null)
        {
            if (activity.TraceId != default) attributes["otel-trace-id"] = activity.TraceId.ToString();
            if (activity.SpanId != default) attributes["otel-span-id"] = activity.SpanId.ToString();

            foreach (var baggage in activity.Baggage)
            {
                attributes[$"baggage.{baggage.Key}"] = baggage.Value ?? string.Empty;
            }
        }

        return attributes;
    }

    // Gets current trace ID.
    private static string CurrentTraceId()
    {
        var activity = System.Diagnostics.Activity.Current;
        return activity?.TraceId.ToString() ?? "unknown";
    }

    // Converts microsoft level.
    private static Microsoft.Extensions.Logging.LogLevel ToMicrosoftLevel(LogLevel level)
    {
        return level switch
        {
            LogLevel.Error => Microsoft.Extensions.Logging.LogLevel.Error,
            LogLevel.Warn => Microsoft.Extensions.Logging.LogLevel.Warning,
            LogLevel.Debug => Microsoft.Extensions.Logging.LogLevel.Debug,
            _ => Microsoft.Extensions.Logging.LogLevel.Information
        };
    }

    // Converts exception.
    private static Exception? ToException(object? message)
    {
        return message as Exception;
    }

    // Renders the requested work.
    private static string Render(object? message, object?[] optionalParams)
    {
        var builder = new StringBuilder()
            .Append(message is Exception exception ? exception.ToString() : Stringify(message));

        if (optionalParams.Length > 0)
        {
            builder.AppendLine().Append(string.Join(Environment.NewLine, optionalParams.Select(Stringify)));
        }

        return builder.ToString();
    }

    // Turns into text the requested work.
    private static string Stringify(object? value)
    {
        return value switch
        {
            null => "null",
            Exception exception => exception.ToString(),
            string text => text,
            _ when IsSimpleValue(value) => value.ToString() ?? string.Empty,
            _ => JsonSerializer.Serialize(value)
        };
    }

    // Checks whether simple value.
    private static bool IsSimpleValue(object value)
    {
        return value switch
        {
            bool or byte or sbyte or short or ushort or int or uint or long or ulong or float or double or decimal or char => true,
            _ => false
        };
    }

    // Parses log levels.
    internal static HashSet<LogLevel> ParseLogLevels(string? raw)
    {
        if (string.IsNullOrWhiteSpace(raw)) return Enum.GetValues<LogLevel>().ToHashSet();

        var levels = new HashSet<LogLevel>();
        foreach (var item in raw.Replace("[", string.Empty).Replace("]", string.Empty).Replace("\"", string.Empty).Split(','))
        {
            if (Enum.TryParse<LogLevel>(item.Trim(), ignoreCase: true, out var level))
            {
                levels.Add(level);
            }
        }

        return levels.Count > 0 ? levels : Enum.GetValues<LogLevel>().ToHashSet();
    }
}
