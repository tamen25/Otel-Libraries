// This file contains logs configuration logic for OTel logs.
package com.cloudops.otel.logs;

import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.nio.file.Path;
import java.util.Arrays;

final class LogsConfiguration {
  private static final String DEFAULT_EXPORTER_PARAMETERS_FILE = "/tmp/otelExporterParams.json";
  private static final ObjectMapper MAPPER = new ObjectMapper()
      .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);

  // Handles logs configuration.
  private LogsConfiguration() {}

  // Reads exporter parameters.
  static ExporterParameters readExporterParameters() {
    String configured = System.getenv("OTEL_EXPORTER_PARAMETERS");
    if (hasValue(configured)) {
      try {
        ExporterParameters parsed = MAPPER.readValue(configured, ExporterParameters.class);
        if (parsed != null && !parsed.isEmpty()) return parsed;
      } catch (Exception ignored) {
        // Fall through to the params file and then direct OTEL env vars.
      }
    }

    ExporterParameters fileParameters = readExporterParametersFile();
    if (!fileParameters.isEmpty()) return fileParameters;

    String logsUrl = firstValue(
        System.getenv("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT"),
        normalizeEndpoint(System.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")));
    String apiKey = firstValue(
        System.getenv("OTEL_API_KEY"),
        System.getenv("OTEL_EXPORTER_OTLP_HEADERS"));

    ExporterParameters parameters = new ExporterParameters();
    if (hasValue(logsUrl) || hasValue(apiKey)) {
      LogsExporterConfig exporterConfig = new LogsExporterConfig();
      exporterConfig.url = logsUrl;
      exporterConfig.apiKey = apiKey;

      BackendConfig backendConfig = new BackendConfig();
      backendConfig.logs = exporterConfig;
      parameters.otel = backendConfig;
    }

    return parameters;
  }

  // Reads exporter parameters file.
  static ExporterParameters readExporterParametersFile() {
    String configuredPath = System.getenv("OTEL_EXPORTER_PARAMETERS_FILE");
    String filePath = firstValue(configuredPath, DEFAULT_EXPORTER_PARAMETERS_FILE);
    return readExporterParametersFile(Path.of(filePath));
  }

  // Reads exporter parameters file.
  static ExporterParameters readExporterParametersFile(Path filePath) {
    try {
      ExporterParameters parsed = MAPPER.readValue(filePath.toFile(), ExporterParameters.class);
      return parsed == null ? new ExporterParameters() : parsed;
    } catch (IOException ignored) {
      return new ExporterParameters();
    }
  }

  // Parses string array.
  static String[] parseStringArray(String raw, String[] fallback) {
    if (!hasValue(raw)) return Arrays.copyOf(fallback, fallback.length);

    try {
      String[] parsed = MAPPER.readValue(raw, String[].class);
      String[] values = Arrays.stream(parsed)
          .map(String::trim)
          .filter(LogsConfiguration::hasValue)
          .toArray(String[]::new);
      if (values.length > 0) return values;
    } catch (Exception ignored) {
      // Fall back to comma-separated values.
    }

    String[] values = Arrays.stream(raw.split(","))
        .map(String::trim)
        .filter(LogsConfiguration::hasValue)
        .toArray(String[]::new);
    return values.length > 0 ? values : Arrays.copyOf(fallback, fallback.length);
  }

  // Gets sampling rate.
  static double samplingRate() {
    try {
      return Double.parseDouble(firstValue(System.getenv("OTEL_LOGS_SAMPLING_RATE"), "100"));
    } catch (NumberFormatException ignored) {
      return 100;
    }
  }

  // Normalizes endpoint.
  private static String normalizeEndpoint(String endpoint) {
    if (!hasValue(endpoint)) return null;
    String normalized = endpoint.endsWith("/") ? endpoint.substring(0, endpoint.length() - 1) : endpoint;
    return normalized.endsWith("/v1/logs") ? normalized : normalized + "/v1/logs";
  }

  // Handles has value.
  static boolean hasValue(String value) {
    return value != null && !value.isBlank();
  }

  // Finds first value.
  static String firstValue(String... values) {
    for (String value : values) {
      if (hasValue(value)) return value;
    }

    return null;
  }
}
