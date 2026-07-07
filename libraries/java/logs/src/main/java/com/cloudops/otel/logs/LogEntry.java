// This file contains log entry logic for OTel logs.
package com.cloudops.otel.logs;

final class LogEntry {
  final String invocationId;
  final LogLevel level;
  final Object message;
  final Object[] optionalParams;

  LogEntry(String invocationId, LogLevel level, Object message, Object[] optionalParams) {
    this.invocationId = invocationId;
    this.level = level;
    this.message = message;
    this.optionalParams = optionalParams == null ? new Object[0] : optionalParams;
  }
}
