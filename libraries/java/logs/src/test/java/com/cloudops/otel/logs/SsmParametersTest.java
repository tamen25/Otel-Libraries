// This file contains SSM parameters test logic for OTel logs.
package com.cloudops.otel.logs;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class SsmParametersTest {
  @Test
  void emptyWhenNoLogsBackendIsConfigured() {
    assertTrue(new SsmParameters().isEmpty());
  }

  @Test
  void backendReturnsConfiguredOtelBackendOnly() {
    LogsExporterConfig logs = new LogsExporterConfig();
    logs.url = "https://collector.example.com/v1/logs";

    BackendConfig backend = new BackendConfig();
    backend.logs = logs;

    SsmParameters parameters = new SsmParameters();
    parameters.otel = backend;

    assertFalse(parameters.isEmpty());
    assertSame(backend, parameters.backend("otel"));
    assertNull(parameters.backend("metrics"));
  }
}
