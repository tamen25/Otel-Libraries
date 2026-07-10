// This file contains log batch logic for OTel logs.
package otel.logs;

import java.util.ArrayList;
import java.util.List;

final class LogBatch {
  final List<LogEntry> logs = new ArrayList<>();

  LogBatch(LogEntry firstEntry) {
    logs.add(firstEntry);
  }
}
