// This file contains environment scope logic for logs tests.
namespace CloudOps.Otel.Logs.Tests;

internal sealed class EnvironmentScope : IDisposable
{
    private static readonly string[] TelemetryKeys =
    [
        "AKS_CLUSTER_NAME",
        "CONTAINER_APP_NAME",
        "CONTAINER_ID",
        "CONTAINER_NAME",
        "FUNCTIONS_EXTENSION_VERSION",
        "FUNCTIONS_WORKER_RUNTIME",
        "HOSTNAME",
        "K8S_CLUSTER_NAME",
        "K8S_NAMESPACE_NAME",
        "K8S_NODE_NAME",
        "K8S_POD_NAME",
        "KUBERNETES_SERVICE_HOST",
        "NODE_NAME",
        "OTEL_BACKEND_EXPORTERS",
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT",
        "OTEL_EXPORTER_PARAMETERS",
        "OTEL_LOG_LEVEL",
        "OTEL_LOGS_SAMPLING_RATE",
        "OTEL_RESOURCE_ATTRIBUTES",
        "OTEL_SERVICE_NAME",
        "POD_NAME",
        "POD_NAMESPACE",
        "WEBSITE_SITE_NAME",
        "X_ORG_ID"
    ];

    private readonly Dictionary<string, string?> previousValues = new(StringComparer.Ordinal);

    // Handles environment scope.
    public EnvironmentScope(IReadOnlyDictionary<string, string?> values)
    {
        foreach (var key in TelemetryKeys.Concat(values.Keys).Distinct(StringComparer.Ordinal))
        {
            previousValues[key] = Environment.GetEnvironmentVariable(key);
            Environment.SetEnvironmentVariable(key, null);
        }

        foreach (var (key, value) in values)
        {
            Environment.SetEnvironmentVariable(key, value);
        }
    }

    // Handles dispose.
    public void Dispose()
    {
        foreach (var (key, value) in previousValues)
        {
            Environment.SetEnvironmentVariable(key, value);
        }
    }
}
