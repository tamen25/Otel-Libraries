// This file contains traces configuration logic for OTel traces.
package com.cloudops.otel.traces;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.opentelemetry.api.common.Attributes;
import io.opentelemetry.api.common.AttributesBuilder;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;
import java.util.stream.Collectors;

final class TracesConfiguration {
  // Hardcoded fallbacks for the OTLP traces endpoint and org id. Env vars override
  // these; leave them empty to fall back to console. X_ORG_ID is required for OTLP
  // export no matter what — without it the tracer uses console.
  static final String DEFAULT_TRACES_ENDPOINT = "";
  static final String DEFAULT_X_ORG_ID = "";

  private static final ObjectMapper MAPPER = new ObjectMapper();

  private TracesConfiguration() {}

  // Builds the resource attributes with service.name and Azure runtime attributes.
  static Attributes resourceAttributes() {
    AttributesBuilder builder = Attributes.builder();
    String serviceName = firstValue(
        System.getenv("OTEL_SERVICE_NAME"),
        System.getenv("WEBSITE_SITE_NAME"),
        "unknown_service");
    builder.put("service.name", serviceName);
    builder.put("pe-lib-trace-ver", "0.1.0");

    if (hasValue(firstEnv("FUNCTIONS_EXTENSION_VERSION", "FUNCTIONS_WORKER_RUNTIME"))) {
      builder.put("cloud.provider", "azure");
      builder.put("cloud.platform", "azure_functions");
      return builder.build();
    }

    if (hasValue(System.getenv("CONTAINER_APP_NAME"))) {
      builder.put("cloud.provider", "azure");
      builder.put("cloud.platform", "azure_container_apps");
    }
    if (hasValue(System.getenv("WEBSITE_SITE_NAME"))) {
      builder.put("cloud.provider", "azure");
      builder.put("cloud.platform", "azure_app_service");
    }

    String k8sCluster = firstEnv("K8S_CLUSTER_NAME", "AKS_CLUSTER_NAME");
    if (hasValue(System.getenv("KUBERNETES_SERVICE_HOST")) || hasValue(k8sCluster)) {
      builder.put("cloud.provider", "azure");
      builder.put("cloud.platform", "azure_aks");
    }
    if (hasValue(k8sCluster)) {
      builder.put("k8s.cluster.name", k8sCluster);
    }
    return builder.build();
  }

  // Resolves the OTLP traces endpoint (normalised to end in /v1/traces).
  static String endpoint() {
    String configured = System.getenv("OTEL_EXPORTER_PARAMETERS");
    if (hasValue(configured)) {
      try {
        JsonNode url = MAPPER.readTree(configured).path("otel").path("trace").path("url");
        if (url.isTextual() && hasValue(url.asText())) {
          return url.asText();
        }
      } catch (Exception ignored) {
        // Fall through to the env vars and the hardcoded default.
      }
    }

    String endpoint = firstValue(
        System.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"),
        normalizeEndpoint(System.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")),
        DEFAULT_TRACES_ENDPOINT);
    return hasValue(endpoint) ? endpoint : null;
  }

  // Resolves org id.
  static String orgId() {
    String value = firstValue(System.getenv("X_ORG_ID"), DEFAULT_X_ORG_ID);
    return hasValue(value) ? value : null;
  }

  // Parses the exporters list (JSON array or CSV).
  static Set<String> exporters() {
    String raw = System.getenv("OTEL_BACKEND_EXPORTERS");
    if (!hasValue(raw)) {
      return new HashSet<>(Arrays.asList("console"));
    }
    try {
      JsonNode parsed = MAPPER.readTree(raw);
      if (parsed.isArray()) {
        Set<String> values = new HashSet<>();
        parsed.forEach(node -> {
          String value = node.asText().trim().toLowerCase();
          if (!value.isEmpty()) {
            values.add(value);
          }
        });
        if (!values.isEmpty()) {
          return values;
        }
      }
    } catch (Exception ignored) {
      // Fall back to CSV parsing.
    }
    Set<String> values = Arrays.stream(raw.split(","))
        .map(item -> item.trim().toLowerCase())
        .filter(item -> !item.isEmpty())
        .collect(Collectors.toSet());
    return values.isEmpty() ? new HashSet<>(Arrays.asList("console")) : values;
  }

  // Normalizes an endpoint to end in /v1/traces.
  static String normalizeEndpoint(String endpoint) {
    if (!hasValue(endpoint)) {
      return null;
    }
    String normalized = endpoint.endsWith("/") ? endpoint.substring(0, endpoint.length() - 1) : endpoint;
    return normalized.endsWith("/v1/traces") ? normalized : normalized + "/v1/traces";
  }

  static boolean hasValue(String value) {
    return value != null && !value.isBlank();
  }

  static String firstValue(String... values) {
    for (String value : values) {
      if (hasValue(value)) {
        return value;
      }
    }
    return null;
  }

  private static String firstEnv(String... names) {
    for (String name : names) {
      String value = System.getenv(name);
      if (hasValue(value)) {
        return value;
      }
    }
    return null;
  }
}
