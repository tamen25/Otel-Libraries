// This file contains logs configuration test logic for OTel logs.
package com.cloudops.otel.logs;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotSame;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class LogsConfigurationTest {
  @Test
  void parseStringArrayReadsJsonAndCommaSeparatedValues() {
    assertArrayEquals(
        new String[] {"console", "otel"},
        LogsConfiguration.parseStringArray("[\"console\", \" otel \"]", new String[] {"fallback"}));
    assertArrayEquals(
        new String[] {"console", "otel"},
        LogsConfiguration.parseStringArray("console, otel", new String[] {"fallback"}));
  }

  @Test
  void parseStringArrayCopiesFallback() {
    String[] fallback = {"console"};
    String[] parsed = LogsConfiguration.parseStringArray("", fallback);

    parsed[0] = "otel";
    assertArrayEquals(new String[] {"console"}, fallback);
    assertNotSame(fallback, parsed);
  }

  @Test
  void firstValueSkipsBlankValues() {
    assertEquals(
        "https://collector.example.com",
        LogsConfiguration.firstValue(null, " ", "https://collector.example.com"));
  }

  @Test
  void readExporterParametersFileReadsOriginalParamsFile(@TempDir Path tempDir) throws IOException {
    Path paramsFile = tempDir.resolve("otelExporterParams.json");
    Files.writeString(
        paramsFile,
        "{\"otel\":{\"logs\":{\"url\":\"https://file.example.com/v1/logs\",\"api_key\":\"file-secret\"}}}");

    ExporterParameters parsed = LogsConfiguration.readExporterParametersFile(paramsFile);

    assertFalse(parsed.isEmpty());
    assertEquals("https://file.example.com/v1/logs", parsed.otel.logs.url);
    assertEquals("file-secret", parsed.otel.logs.apiKey);
  }

  @Test
  void readExporterParametersFileReturnsEmptyForInvalidFile(@TempDir Path tempDir) throws IOException {
    Path paramsFile = tempDir.resolve("otelExporterParams.json");
    Files.writeString(paramsFile, "{not-json");

    ExporterParameters parsed = LogsConfiguration.readExporterParametersFile(paramsFile);

    assertTrue(parsed.isEmpty());
  }
}
