// This file contains traces configuration test logic for OTel traces.
package com.cloudops.otel.traces;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class TracesConfigurationTest {
  @Test
  void normalizeEndpointAppendsTracesPath() {
    assertEquals("https://c.example.com/v1/traces", TracesConfiguration.normalizeEndpoint("https://c.example.com/"));
    assertEquals("https://c.example.com/v1/traces", TracesConfiguration.normalizeEndpoint("https://c.example.com/v1/traces"));
    assertNull(TracesConfiguration.normalizeEndpoint(null));
  }

  @Test
  void endpointIsNullWithoutConfig() {
    // No OTLP endpoint env vars are set and the hardcoded default is empty.
    assertNull(TracesConfiguration.endpoint());
  }

  @Test
  void orgIdIsNullWithoutEnvOrDefault() {
    // X_ORG_ID is unset and the hardcoded default org id is empty.
    assertNull(TracesConfiguration.orgId());
  }

  @Test
  void exportersDefaultToConsole() {
    // OTEL_BACKEND_EXPORTERS is unset, so the default is console.
    assertTrue(TracesConfiguration.exporters().contains("console"));
  }
}
