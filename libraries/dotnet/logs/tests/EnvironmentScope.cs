// This file contains environment scope logic for logs tests.
namespace CloudOps.Otel.Logs.Tests;

internal sealed class EnvironmentScope : IDisposable
{
    private static readonly string[] TelemetryKeys =
    [
        "AWS_LAMBDA_FUNCTION_NAME",
        "CONTAINER_ID",
        "CONTAINER_NAME",
        "ECS_CONTAINER_METADATA_FILE",
        "ECS_CONTAINER_METADATA_URI",
        "ECS_CONTAINER_METADATA_URI_V4",
        "ECS_CONTAINER_NAME",
        "EKS_CLUSTER_NAME",
        "HOSTNAME",
        "K8S_CLUSTER_NAME",
        "K8S_NAMESPACE_NAME",
        "K8S_NODE_NAME",
        "K8S_POD_NAME",
        "KUBERNETES_SERVICE_HOST",
        "NODE_NAME",
        "OTEL_API_KEY",
        "OTEL_BACKEND_EXPORTERS",
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "OTEL_EXPORTER_OTLP_HEADERS",
        "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT",
        "OTEL_LOG_LEVEL",
        "OTEL_LOGS_SAMPLING_RATE",
        "OTEL_RESOURCE_ATTRIBUTES",
        "OTEL_SERVICE_NAME",
        "OTEL_SSM_PARAMETERS",
        "OTEL_SSM_PARAMETERS_FILE",
        "POD_NAME",
        "POD_NAMESPACE",
        "_X_AMZN_TRACE_ID"
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
