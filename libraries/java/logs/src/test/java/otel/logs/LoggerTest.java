// This file contains cloud ops logger test logic for OTel logs.
package otel.logs;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.util.EnumSet;
import java.util.Map;
import org.junit.jupiter.api.Test;

class LoggerTest {
  @Test
  void parseLogLevelsIgnoresUnknownValues() {
    assertEquals(EnumSet.of(LogLevel.ERROR), Logger.parseLogLevels("bad,error"));
    assertEquals(EnumSet.allOf(LogLevel.class), Logger.parseLogLevels("bad"));
  }

  @Test
  void consoleLoggerRendersEnabledMessagesAndStructuredParams() {
    PrintStream originalOut = System.out;
    ByteArrayOutputStream output = new ByteArrayOutputStream();
    System.setOut(new PrintStream(output, true, StandardCharsets.UTF_8));

    try {
      Logger logger = new Logger();
      logger.info("created order", Map.of("order_id", 42));
      logger.exportLogs();
    } finally {
      System.setOut(originalOut);
    }

    String rendered = output.toString(StandardCharsets.UTF_8);
    assertTrue(rendered.contains("created order"), rendered);
    assertTrue(rendered.contains("order_id"), rendered);
  }
}
