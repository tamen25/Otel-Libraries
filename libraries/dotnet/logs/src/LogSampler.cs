// This file contains log sampler logic for logs src.
namespace Otel.Logs;

internal sealed class LogSampler
{
    private readonly Dictionary<string, LogBatch> batchMap = new(StringComparer.Ordinal);
    private readonly double probabilisticSamplingRate = LogsConfiguration.SamplingRate();
    private readonly Logger logger;
    private readonly object syncRoot = new();

    // Logs sampler.
    public LogSampler(Logger logger)
    {
        this.logger = logger;
    }

    // Adds log.
    public void AddLog(LogEntry logEntry)
    {
        lock (syncRoot)
        {
            if (probabilisticSamplingRate == 0)
            {
                logger.ProcessLog(logEntry);
                return;
            }

            if (!LogsConfiguration.HasValue(logEntry.InvocationId) || logEntry.InvocationId == "unknown")
            {
                logger.ProcessLog(logEntry);
                return;
            }

            if (batchMap.TryGetValue(logEntry.InvocationId, out var existingBatch))
            {
                existingBatch.Logs.Add(logEntry);
                return;
            }

            FlushOneBatch();
            batchMap[logEntry.InvocationId] = new LogBatch(logEntry);
        }
    }

    // Flushes one batch.
    public void FlushOneBatch()
    {
        lock (syncRoot)
        {
            foreach (var (invocationId, batch) in batchMap.ToArray())
            {
                var hasError = batch.Logs.Any(log => log.Level == LogLevel.Error);
                if (hasError || ShouldSample())
                {
                    foreach (var log in batch.Logs)
                    {
                        logger.ProcessLog(log);
                    }
                }

                batchMap.Remove(invocationId);
            }
        }
    }

    // Decides whether to sample.
    private bool ShouldSample()
    {
        var threshold = Math.Clamp(probabilisticSamplingRate, 0, 100) / 100;
        return Random.Shared.NextDouble() <= threshold;
    }
}
