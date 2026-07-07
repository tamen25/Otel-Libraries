// This file contains runtime resource attributes logic for logs src.
namespace CloudOps.Otel.Logs;

public static class RuntimeResourceAttributes
{
    private const string AttrServiceName = "service.name";
    private const string AttrCloudPlatform = "cloud.platform";
    private const string AttrContainerId = "container.id";
    private const string AttrContainerName = "container.name";
    private const string AttrFaasName = "faas.name";
    private const string AttrK8sClusterName = "k8s.cluster.name";
    private const string AttrK8sNamespaceName = "k8s.namespace.name";
    private const string AttrK8sNodeName = "k8s.node.name";
    private const string AttrK8sPodName = "k8s.pod.name";

    // Creates the requested work.
    public static IReadOnlyDictionary<string, string> Create()
    {
        var attributes = ParseResourceAttributes(Environment.GetEnvironmentVariable("OTEL_RESOURCE_ATTRIBUTES"));
        attributes[AttrServiceName] = FirstValue(
            Environment.GetEnvironmentVariable("OTEL_SERVICE_NAME"),
            attributes.GetValueOrDefault(AttrServiceName),
            Environment.GetEnvironmentVariable("AWS_LAMBDA_FUNCTION_NAME"),
            "unknown_service");
        attributes["pe-lib-log-ver"] = "1.16.2";

        AddRuntimeAttributes(attributes);
        return attributes;
    }

    // Adds runtime attributes.
    private static void AddRuntimeAttributes(Dictionary<string, string> attributes)
    {
        var lambdaName = Environment.GetEnvironmentVariable("AWS_LAMBDA_FUNCTION_NAME");
        if (HasValue(lambdaName))
        {
            attributes[AttrCloudPlatform] = "aws_lambda";
            attributes[AttrFaasName] = lambdaName!;
            return;
        }

        if (HasValue(FirstEnv("ECS_CONTAINER_METADATA_URI_V4", "ECS_CONTAINER_METADATA_URI"))
            || HasValue(Environment.GetEnvironmentVariable("ECS_CONTAINER_METADATA_FILE")))
        {
            attributes[AttrCloudPlatform] = "aws_ecs";
        }

        var runningOnKubernetes = HasValue(Environment.GetEnvironmentVariable("KUBERNETES_SERVICE_HOST"));
        var k8sClusterName = FirstEnv("K8S_CLUSTER_NAME", "EKS_CLUSTER_NAME");
        var k8sNamespaceName = FirstEnv("K8S_NAMESPACE_NAME", "POD_NAMESPACE");
        var k8sNodeName = FirstEnv("K8S_NODE_NAME", "NODE_NAME");
        var k8sPodName = FirstEnv("K8S_POD_NAME", "POD_NAME");
        if (!HasValue(k8sPodName) && runningOnKubernetes)
        {
            k8sPodName = Environment.GetEnvironmentVariable("HOSTNAME");
        }

        if (runningOnKubernetes || HasValue(k8sClusterName) || HasValue(k8sNamespaceName) || HasValue(k8sPodName))
        {
            attributes[AttrCloudPlatform] = "aws_eks";
        }

        PutIfPresent(attributes, AttrK8sClusterName, k8sClusterName);
        PutIfPresent(attributes, AttrK8sNamespaceName, k8sNamespaceName);
        PutIfPresent(attributes, AttrK8sNodeName, k8sNodeName);
        PutIfPresent(attributes, AttrK8sPodName, k8sPodName);
        PutIfPresent(attributes, AttrContainerId, Environment.GetEnvironmentVariable("CONTAINER_ID"));
        PutIfPresent(attributes, AttrContainerName, FirstEnv("CONTAINER_NAME", "ECS_CONTAINER_NAME"));
    }

    // Parses resource attributes.
    private static Dictionary<string, string> ParseResourceAttributes(string? raw)
    {
        var attributes = new Dictionary<string, string>(StringComparer.Ordinal);
        if (!HasValue(raw)) return attributes;

        foreach (var item in raw!.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            var separatorIndex = item.IndexOf('=', StringComparison.Ordinal);
            if (separatorIndex <= 0) continue;

            var key = item[..separatorIndex].Trim();
            var value = item[(separatorIndex + 1)..].Trim();
            if (HasValue(key) && HasValue(value))
            {
                attributes[key] = value;
            }
        }

        return attributes;
    }

    // Handles put if present.
    private static void PutIfPresent(Dictionary<string, string> attributes, string key, string? value)
    {
        if (HasValue(value)) attributes[key] = value!;
    }

    // Finds first env.
    private static string? FirstEnv(params string[] names)
    {
        foreach (var name in names)
        {
            var value = Environment.GetEnvironmentVariable(name);
            if (HasValue(value)) return value!;
        }

        return null;
    }

    // Finds first value.
    private static string FirstValue(params string?[] values)
    {
        return values.FirstOrDefault(HasValue) ?? "unknown_service";
    }

    // Handles has value.
    private static bool HasValue(string? value)
    {
        return !string.IsNullOrWhiteSpace(value);
    }
}
