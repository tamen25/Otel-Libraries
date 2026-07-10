// This file contains exporter parameters test logic for OTel logs.
package otel.logs;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class ExporterParametersTest {
  @Test
  void emptyWhenNoLogsBackendIsConfigured() {
    assertTrue(new ExporterParameters().isEmpty());
  }

  @Test
  void backendReturnsConfiguredOtelBackendOnly() {
    LogsExporterConfig logs = new LogsExporterConfig();
    logs.url = "https://collector.example.com/v1/logs";

    BackendConfig backend = new BackendConfig();
    backend.logs = logs;

    ExporterParameters parameters = new ExporterParameters();
    parameters.otel = backend;

    assertFalse(parameters.isEmpty());
    assertSame(backend, parameters.backend("otel"));
    assertNull(parameters.backend("metrics"));
  }
}
