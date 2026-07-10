// This file contains log sampler logic for OTel logs.
package otel.logs;

import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.Map;

final class LogSampler {
  private final Map<String, LogBatch> batchMap = new LinkedHashMap<>();
  private final double probabilisticSamplingRate = LogsConfiguration.samplingRate();
  private final Logger logger;

  LogSampler(Logger logger) {
    this.logger = logger;
  }

  synchronized void addLog(LogEntry logEntry) {
    if (probabilisticSamplingRate == 0) {
      logger.processLog(logEntry);
      return;
    }

    if (!LogsConfiguration.hasValue(logEntry.invocationId) || "unknown".equals(logEntry.invocationId)) {
      logger.processLog(logEntry);
      return;
    }

    LogBatch existingBatch = batchMap.get(logEntry.invocationId);
    if (existingBatch != null) {
      existingBatch.logs.add(logEntry);
      return;
    }

    flushOneBatch();
    batchMap.put(logEntry.invocationId, new LogBatch(logEntry));
  }

  synchronized void flushOneBatch() {
    if (batchMap.isEmpty()) return;

    Iterator<Map.Entry<String, LogBatch>> iterator = batchMap.entrySet().iterator();
    while (iterator.hasNext()) {
      Map.Entry<String, LogBatch> entry = iterator.next();
      LogBatch batch = entry.getValue();
      boolean hasError = batch.logs.stream().anyMatch(log -> log.level == LogLevel.ERROR);

      if (hasError || shouldSample()) {
        batch.logs.forEach(logger::processLog);
      }

      iterator.remove();
    }
  }

  // Decides whether to sample.
  private boolean shouldSample() {
    double threshold = Math.max(0, Math.min(100, probabilisticSamplingRate)) / 100.0;
    return Math.random() <= threshold;
  }
}
