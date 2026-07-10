// This file contains logs configuration logic for OTel logs.
package otel.logs;

import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.Arrays;

final class LogsConfiguration {
  // Hardcoded fallbacks for the OTLP logs endpoint and org id. Env vars override
  // these; leave them empty to fall back to console. X_ORG_ID is required for OTLP
  // export no matter what — without it the logger always uses console.
  static final String DEFAULT_LOGS_ENDPOINT = "";
  static final String DEFAULT_X_ORG_ID = "";
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
        // Fall through to the direct OTEL env vars and the hardcoded default.
      }
    }

    String logsUrl = firstValue(
        System.getenv("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT"),
        normalizeEndpoint(System.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")),
        DEFAULT_LOGS_ENDPOINT);

    ExporterParameters parameters = new ExporterParameters();
    if (hasValue(logsUrl)) {
      LogsExporterConfig exporterConfig = new LogsExporterConfig();
      exporterConfig.url = logsUrl;

      BackendConfig backendConfig = new BackendConfig();
      backendConfig.logs = exporterConfig;
      parameters.otel = backendConfig;
    }

    return parameters;
  }

  // Resolves org id.
  static String orgId() {
    return firstValue(System.getenv("X_ORG_ID"), DEFAULT_X_ORG_ID);
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
