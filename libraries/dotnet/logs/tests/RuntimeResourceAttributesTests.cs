// This file contains runtime resource attributes tests logic for logs tests.
using Xunit;

namespace Otel.Logs.Tests;

public sealed class RuntimeResourceAttributesTests
{
    [Fact]
    // Handles service name environment overrides resource attributes.
    public void ServiceNameEnvironmentOverridesResourceAttributes()
    {
        using var env = new EnvironmentScope(new Dictionary<string, string?>
        {
            ["OTEL_RESOURCE_ATTRIBUTES"] = "service.name=from-resource,deployment.environment=dev",
            ["OTEL_SERVICE_NAME"] = "from-env"
        });

        var attributes = RuntimeResourceAttributes.Create();

        Assert.Equal("from-env", attributes["service.name"]);
        Assert.Equal("dev", attributes["deployment.environment"]);
    }

    [Fact]
    // Handles functions attributes are detected.
    public void FunctionsAttributesAreDetected()
    {
        using var env = new EnvironmentScope(new Dictionary<string, string?>
        {
            ["FUNCTIONS_EXTENSION_VERSION"] = "~4",
            ["WEBSITE_SITE_NAME"] = "orders-func"
        });

        var attributes = RuntimeResourceAttributes.Create();

        Assert.Equal("orders-func", attributes["service.name"]);
        Assert.Equal("azure", attributes["cloud.provider"]);
        Assert.Equal("azure_functions", attributes["cloud.platform"]);
        Assert.Equal("orders-func", attributes["faas.name"]);
    }

    [Fact]
    // Handles functions detection early-returns before kubernetes attributes.
    public void FunctionsDetectionSkipsKubernetesAttributes()
    {
        using var env = new EnvironmentScope(new Dictionary<string, string?>
        {
            ["FUNCTIONS_WORKER_RUNTIME"] = "dotnet-isolated",
            ["WEBSITE_SITE_NAME"] = "orders-func",
            ["KUBERNETES_SERVICE_HOST"] = "10.0.0.1"
        });

        var attributes = RuntimeResourceAttributes.Create();

        Assert.Equal("azure_functions", attributes["cloud.platform"]);
        Assert.False(attributes.ContainsKey("k8s.pod.name"));
    }

    [Fact]
    // Handles container apps attributes are detected.
    public void ContainerAppsAttributesAreDetected()
    {
        using var env = new EnvironmentScope(new Dictionary<string, string?>
        {
            ["OTEL_SERVICE_NAME"] = "order-api",
            ["CONTAINER_APP_NAME"] = "orders-ca"
        });

        var attributes = RuntimeResourceAttributes.Create();

        Assert.Equal("azure", attributes["cloud.provider"]);
        Assert.Equal("azure_container_apps", attributes["cloud.platform"]);
        Assert.Equal("orders-ca", attributes["container.name"]);
    }

    [Fact]
    // Handles app service attributes are detected.
    public void AppServiceAttributesAreDetected()
    {
        using var env = new EnvironmentScope(new Dictionary<string, string?>
        {
            ["WEBSITE_SITE_NAME"] = "orders-web"
        });

        var attributes = RuntimeResourceAttributes.Create();

        Assert.Equal("orders-web", attributes["service.name"]);
        Assert.Equal("azure_app_service", attributes["cloud.platform"]);
        Assert.False(attributes.ContainsKey("faas.name"));
    }

    [Fact]
    // Handles container apps with kubernetes signals fall through to AKS.
    public void ContainerAppsWithKubernetesFallsThroughToAks()
    {
        using var env = new EnvironmentScope(new Dictionary<string, string?>
        {
            ["CONTAINER_APP_NAME"] = "orders-ca",
            ["KUBERNETES_SERVICE_HOST"] = "10.0.0.1"
        });

        var attributes = RuntimeResourceAttributes.Create();

        Assert.Equal("azure_aks", attributes["cloud.platform"]);
        Assert.Equal("orders-ca", attributes["container.name"]);
    }

    [Fact]
    // Handles AKS attributes are detected.
    public void AksAttributesAreDetected()
    {
        using var env = new EnvironmentScope(new Dictionary<string, string?>
        {
            ["OTEL_SERVICE_NAME"] = "order-api",
            ["KUBERNETES_SERVICE_HOST"] = "10.0.0.1",
            ["AKS_CLUSTER_NAME"] = "otel-dev",
            ["K8S_POD_NAME"] = "order-api-abc"
        });

        var attributes = RuntimeResourceAttributes.Create();

        Assert.Equal("azure", attributes["cloud.provider"]);
        Assert.Equal("azure_aks", attributes["cloud.platform"]);
        Assert.Equal("otel-dev", attributes["k8s.cluster.name"]);
        Assert.Equal("order-api-abc", attributes["k8s.pod.name"]);
    }
}
