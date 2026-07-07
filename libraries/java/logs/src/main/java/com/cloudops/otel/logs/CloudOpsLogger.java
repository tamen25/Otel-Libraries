// This file contains cloud ops logger logic for OTel logs.
package com.cloudops.otel.logs;

import io.opentelemetry.api.OpenTelemetry;
import io.opentelemetry.api.baggage.Baggage;
import io.opentelemetry.api.common.Attributes;
import io.opentelemetry.api.common.AttributesBuilder;
import io.opentelemetry.api.logs.Logger;
import io.opentelemetry.api.logs.Severity;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.SpanContext;
import io.opentelemetry.context.Context;
import io.opentelemetry.exporter.otlp.http.logs.OtlpHttpLogRecordExporter;
import io.opentelemetry.sdk.OpenTelemetrySdk;
import io.opentelemetry.sdk.common.CompletableResultCode;
import io.opentelemetry.sdk.logs.SdkLoggerProvider;
import io.opentelemetry.sdk.logs.export.BatchLogRecordProcessor;
import io.opentelemetry.sdk.logs.LogRecordProcessor;
import io.opentelemetry.sdk.resources.Resource;
import java.io.PrintStream;
import java.util.Arrays;
import java.util.EnumSet;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

public final class CloudOpsLogger {
  private static final String[] DEFAULT_EXPORTERS = {"console"};
  private static volatile CloudOpsLogger instance;

  private final Set<LogLevel> enabledLevels;
  private final Map<String, String> resourceAttributes;
  private final String[] exportersList;
  private final LogSampler sampler;
  private SdkLoggerProvider loggerProvider;
  private Logger otelLogger;
  private boolean useConsole;
  private boolean useOtel;
  private String previousTraceId;
  private String uniqueId;

  CloudOpsLogger() {
    this.resourceAttributes = RuntimeResourceAttributes.create();
    this.enabledLevels = parseLogLevels(System.getenv("OTEL_LOG_LEVEL"));
    this.exportersList = LogsConfiguration.parseStringArray(System.getenv("OTEL_BACKEND_EXPORTERS"), DEFAULT_EXPORTERS);
    this.sampler = new LogSampler(this);
    init();
  }

  // Initializes logger.
  public static CloudOpsLogger initialiseLogger() {
    return initializeLogger();
  }

  // Initializes logger.
  public static CloudOpsLogger initializeLogger() {
    CloudOpsLogger localInstance = instance;
    if (localInstance == null) {
      synchronized (CloudOpsLogger.class) {
        localInstance = instance;
        if (localInstance == null) {
          localInstance = new CloudOpsLogger();
          instance = localInstance;
        }
      }
    }

    return localInstance;
  }

  // Handles resource attributes.
  public Map<String, String> resourceAttributes() {
    return resourceAttributes;
  }

  // Handles info.
  public void info(Object message, Object... optionalParams) {
    log(LogLevel.INFO, message, optionalParams);
  }

  // Handles error.
  public void error(Object message, Object... optionalParams) {
    log(LogLevel.ERROR, message, optionalParams);
  }

  // Handles debug.
  public void debug(Object message, Object... optionalParams) {
    log(LogLevel.DEBUG, message, optionalParams);
  }

  // Handles warn.
  public void warn(Object message, Object... optionalParams) {
    log(LogLevel.WARN, message, optionalParams);
  }

  // Exports logs.
  public void exportLogs() {
    sampler.flushOneBatch();
    if (useOtel && loggerProvider != null) {
      CompletableResultCode resultCode = loggerProvider.forceFlush();
      resultCode.join(30, TimeUnit.SECONDS);
    }
  }

  // Logs the requested work.
  private void log(LogLevel level, Object message, Object... optionalParams) {
    String currentTraceId = currentTraceId();
    if (!currentTraceId.equals(previousTraceId)) {
      uniqueId = UUID.randomUUID().toString();
      previousTraceId = currentTraceId;
    }

    sampler.addLog(new LogEntry(uniqueId == null ? "unknown" : uniqueId, level, message, optionalParams));
  }

  void processLog(LogEntry logEntry) {
    if (!enabledLevels.contains(logEntry.level)) return;

    String renderedMessage = render(logEntry.message, logEntry.optionalParams);
    if (useConsole) {
      PrintStream stream = logEntry.level == LogLevel.ERROR ? System.err : System.out;
      stream.println(renderedMessage);
    }

    if (useOtel && otelLogger != null) {
      otelLogger.logRecordBuilder()
          .setContext(Context.current())
          .setSeverity(toSeverity(logEntry.level))
          .setSeverityText(logEntry.level.value())
          .setBody(renderedMessage)
          .setAllAttributes(logAttributes(logEntry.invocationId))
          .emit();
    }
  }

  // Initializes the requested work.
  private void init() {
    if (exportersList.length <= 1 && containsExporter("console")) {
      useConsole = true;
      return;
    }

    SsmParameters ssmParameters = LogsConfiguration.readSsmParameters();
    if (ssmParameters == null || ssmParameters.isEmpty()) {
      useConsole = true;
      return;
    }

    for (String exporter : exportersList) {
      switch (exporter.trim().toLowerCase()) {
        case "console" -> useConsole = true;
        case "otel" -> initialiseOtel(ssmParameters);
        default -> useConsole = true;
      }
    }
  }

  // Initializes OTel.
  private void initialiseOtel(SsmParameters ssmParameters) {
    BackendConfig backendConfig = ssmParameters.backend("otel");
    if (backendConfig == null || backendConfig.logs == null) {
      useConsole = true;
      return;
    }

    var exporterBuilder = OtlpHttpLogRecordExporter.builder();
    if (LogsConfiguration.hasValue(backendConfig.logs.url)) {
      exporterBuilder.setEndpoint(backendConfig.logs.url);
    }
    if (LogsConfiguration.hasValue(backendConfig.logs.apiKey)) {
      exporterBuilder.addHeader("authorization", "Bearer " + backendConfig.logs.apiKey);
    }

    LogRecordProcessor processor = BatchLogRecordProcessor.builder(exporterBuilder.build()).build();
    loggerProvider = SdkLoggerProvider.builder()
        .setResource(Resource.getDefault().merge(resource()))
        .addLogRecordProcessor(processor)
        .build();

    OpenTelemetry openTelemetry = OpenTelemetrySdk.builder()
        .setLoggerProvider(loggerProvider)
        .build();
    otelLogger = openTelemetry.getLogsBridge().get(resourceAttributes.getOrDefault("service.name", "unknown_service"));
    useOtel = true;
  }

  // Handles resource.
  private Resource resource() {
    io.opentelemetry.sdk.resources.ResourceBuilder builder = Resource.builder();
    resourceAttributes.forEach(builder::put);
    return builder.build();
  }

  // Logs attributes.
  private Attributes logAttributes(String invocationId) {
    AttributesBuilder builder = Attributes.builder().put("invocation.id", invocationId == null ? "unknown" : invocationId);

    Baggage.current().forEach((key, entry) -> builder.put("baggage." + key, entry.getValue()));

    SpanContext spanContext = Span.current().getSpanContext();
    if (spanContext.isValid()) {
      builder.put("otel-trace-id", spanContext.getTraceId());
      builder.put("otel-span-id", spanContext.getSpanId());
    }

    return builder.build();
  }

  // Converts severity.
  private static Severity toSeverity(LogLevel level) {
    return switch (level) {
      case ERROR -> Severity.ERROR;
      case WARN -> Severity.WARN;
      case DEBUG -> Severity.DEBUG;
      case INFO -> Severity.INFO;
    };
  }

  // Parses log levels.
  static Set<LogLevel> parseLogLevels(String raw) {
    if (raw == null || raw.isBlank()) return EnumSet.allOf(LogLevel.class);

    EnumSet<LogLevel> levels = EnumSet.noneOf(LogLevel.class);
    for (String item : raw.replace("[", "").replace("]", "").replace("\"", "").split(",")) {
      String normalized = item.trim().toUpperCase(Locale.ROOT);
      if (normalized.isEmpty()) continue;

      try {
        levels.add(LogLevel.valueOf(normalized));
      } catch (IllegalArgumentException ignored) {
        // Ignore unknown level names so one bad value does not disable logging.
      }
    }

    return levels.isEmpty() ? EnumSet.allOf(LogLevel.class) : levels;
  }

  // Renders the requested work.
  private static String render(Object message, Object[] optionalParams) {
    String rendered = message instanceof Throwable throwable
        ? throwable.toString()
        : String.valueOf(message);

    if (optionalParams != null && optionalParams.length > 0) {
      rendered += "\n" + Arrays.deepToString(optionalParams);
    }

    return rendered;
  }

  // Handles contains exporter.
  private boolean containsExporter(String expected) {
    for (String exporter : exportersList) {
      if (expected.equalsIgnoreCase(exporter.trim())) return true;
    }

    return false;
  }

  // Gets current trace ID.
  private static String currentTraceId() {
    String lambdaTraceId = System.getenv("_X_AMZN_TRACE_ID");
    if (LogsConfiguration.hasValue(lambdaTraceId)) return lambdaTraceId;

    SpanContext spanContext = Span.current().getSpanContext();
    return spanContext.isValid() ? spanContext.getTraceId() : "unknown";
  }
}
