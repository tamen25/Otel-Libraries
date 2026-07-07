// This file contains log level logic for OTel logs.
package com.cloudops.otel.logs;

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
