// This file contains log level logic for OTel logs.
package otel.logs;

public enum LogLevel {
  INFO,
  ERROR,
  DEBUG,
  WARN;

  // Handles value.
  public String value() {
    return name().toLowerCase();
  }
}
