// This file contains cloud ops tracing tests logic for traces tests.
using Xunit;

namespace Otel.Traces.Tests;

public sealed class OtelTracingTests
{
    [Fact]
    // Normalizes an endpoint to end in the traces path.
    public void NormalizeEndpointAppendsTracesPath()
    {
        Assert.Equal("https://c.example.com/v1/traces", OtelTracing.NormalizeEndpoint("https://c.example.com/"));
        Assert.Equal("https://c.example.com/v1/traces", OtelTracing.NormalizeEndpoint("https://c.example.com/v1/traces"));
        Assert.Null(OtelTracing.NormalizeEndpoint(null));
    }

    [Fact]
    // Parses the exporters list from JSON and CSV.
    public void ParseExportersReadsJsonAndCsv()
    {
        Assert.Contains("otel", OtelTracing.ParseExporters("[\"console\",\"otel\"]"));
        Assert.Contains("otel", OtelTracing.ParseExporters("console, otel"));
        Assert.Contains("console", OtelTracing.ParseExporters(null));
    }

    [Fact]
    // Resolves the endpoint from the inline JSON blob.
    public void ResolveEndpointPrefersJsonBlob()
    {
        var previous = Environment.GetEnvironmentVariable("OTEL_EXPORTER_PARAMETERS");
        try
        {
            Environment.SetEnvironmentVariable(
                "OTEL_EXPORTER_PARAMETERS",
                "{\"otel\":{\"trace\":{\"url\":\"https://collector.example.com/v1/traces\"}}}");
            Assert.Equal("https://collector.example.com/v1/traces", OtelTracing.ResolveEndpoint());
        }
        finally
        {
            Environment.SetEnvironmentVariable("OTEL_EXPORTER_PARAMETERS", previous);
        }
    }

    [Fact]
    // Adds Azure AKS runtime attributes.
    public void AddRuntimeAttributesDetectsAks()
    {
        var previousHost = Environment.GetEnvironmentVariable("KUBERNETES_SERVICE_HOST");
        var previousCluster = Environment.GetEnvironmentVariable("AKS_CLUSTER_NAME");
        try
        {
            Environment.SetEnvironmentVariable("KUBERNETES_SERVICE_HOST", "10.0.0.1");
            Environment.SetEnvironmentVariable("AKS_CLUSTER_NAME", "otel-dev");

            var attributes = new Dictionary<string, object>();
            OtelTracing.AddRuntimeAttributes(attributes);

            Assert.Equal("azure", attributes["cloud.provider"]);
            Assert.Equal("azure_aks", attributes["cloud.platform"]);
            Assert.Equal("otel-dev", attributes["k8s.cluster.name"]);
        }
        finally
        {
            Environment.SetEnvironmentVariable("KUBERNETES_SERVICE_HOST", previousHost);
            Environment.SetEnvironmentVariable("AKS_CLUSTER_NAME", previousCluster);
        }
    }
}
