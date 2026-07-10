// This file contains tracing setup logic for traces src.
using System.Text.Json;
using Microsoft.Extensions.DependencyInjection;
using OpenTelemetry.Exporter;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;

namespace CloudOps.Otel.Traces;

public static class CloudOpsTracing
{
    // Hardcoded fallbacks for the OTLP traces endpoint and org id. Env vars
    // override these; leave them empty to fall back to no OTLP export. X_ORG_ID
    // is required for OTLP export no matter what.
    public const string DefaultTracesEndpoint = "";
    public const string DefaultXOrgId = "";

    // Registers CloudOps tracing: gates OTLP on both an endpoint URL and X_ORG_ID,
    // and adds ASP.NET Core + HttpClient auto-instrumentation so W3C trace context
    // propagates across services automatically.
    public static IServiceCollection AddCloudOpsTracing(this IServiceCollection services)
    {
        var exporters = ParseExporters(Environment.GetEnvironmentVariable("OTEL_BACKEND_EXPORTERS"));
        var endpoint = ResolveEndpoint();
        var orgId = ResolveOrgId();
        var useOtel = exporters.Contains("otel") && HasValue(endpoint) && HasValue(orgId);

        services.AddOpenTelemetry().WithTracing(tracing =>
        {
            tracing.SetResourceBuilder(BuildResource());
            tracing.AddAspNetCoreInstrumentation();
            tracing.AddHttpClientInstrumentation();

            if (useOtel)
            {
                tracing.AddOtlpExporter(options =>
                {
                    options.Endpoint = new Uri(endpoint!);
                    options.Protocol = OtlpExportProtocol.HttpProtobuf;
                    options.Headers = $"X-OrgId={orgId}";
                });
            }
        });

        return services;
    }

    // Builds the resource with service.name and Azure runtime attributes.
    internal static ResourceBuilder BuildResource()
    {
        var serviceName = Environment.GetEnvironmentVariable("OTEL_SERVICE_NAME")
            ?? Environment.GetEnvironmentVariable("WEBSITE_SITE_NAME")
            ?? "unknown_service";

        var attributes = new Dictionary<string, object>();
        AddRuntimeAttributes(attributes);

        return ResourceBuilder.CreateDefault()
            .AddService(serviceName)
            .AddAttributes(attributes);
    }

    // Adds Azure runtime attributes.
    internal static void AddRuntimeAttributes(Dictionary<string, object> attributes)
    {
        if (HasValue(FirstEnv("FUNCTIONS_EXTENSION_VERSION", "FUNCTIONS_WORKER_RUNTIME")))
        {
            attributes["cloud.provider"] = "azure";
            attributes["cloud.platform"] = "azure_functions";
            return;
        }

        if (HasValue(Environment.GetEnvironmentVariable("CONTAINER_APP_NAME")))
        {
            attributes["cloud.provider"] = "azure";
            attributes["cloud.platform"] = "azure_container_apps";
        }

        if (HasValue(Environment.GetEnvironmentVariable("WEBSITE_SITE_NAME")))
        {
            attributes["cloud.provider"] = "azure";
            attributes["cloud.platform"] = "azure_app_service";
        }

        var k8sClusterName = FirstEnv("K8S_CLUSTER_NAME", "AKS_CLUSTER_NAME");
        if (HasValue(Environment.GetEnvironmentVariable("KUBERNETES_SERVICE_HOST")) || HasValue(k8sClusterName))
        {
            attributes["cloud.provider"] = "azure";
            attributes["cloud.platform"] = "azure_aks";
        }

        if (HasValue(k8sClusterName)) attributes["k8s.cluster.name"] = k8sClusterName!;
    }

    // Resolves the OTLP traces endpoint (normalised to end in /v1/traces).
    internal static string? ResolveEndpoint()
    {
        var configured = Environment.GetEnvironmentVariable("OTEL_EXPORTER_PARAMETERS");
        if (HasValue(configured))
        {
            try
            {
                using var doc = JsonDocument.Parse(configured!);
                if (doc.RootElement.TryGetProperty("otel", out var otel)
                    && otel.TryGetProperty("trace", out var trace)
                    && trace.TryGetProperty("url", out var url)
                    && url.ValueKind == JsonValueKind.String)
                {
                    var value = url.GetString();
                    if (HasValue(value)) return value;
                }
            }
            catch (JsonException)
            {
                // Fall through to the env vars and the hardcoded default.
            }
        }

        var endpoint = FirstEnv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
            ?? NormalizeEndpoint(Environment.GetEnvironmentVariable("OTEL_EXPORTER_OTLP_ENDPOINT"))
            ?? (HasValue(DefaultTracesEndpoint) ? DefaultTracesEndpoint : null);

        return endpoint;
    }

    // Resolves org id.
    internal static string? ResolveOrgId()
    {
        return FirstEnv("X_ORG_ID") ?? (HasValue(DefaultXOrgId) ? DefaultXOrgId : null);
    }

    // Normalizes an endpoint to end in /v1/traces.
    internal static string? NormalizeEndpoint(string? endpoint)
    {
        if (!HasValue(endpoint)) return null;
        var normalized = endpoint!.TrimEnd('/');
        return normalized.EndsWith("/v1/traces", StringComparison.Ordinal) ? normalized : $"{normalized}/v1/traces";
    }

    // Parses the exporters list (JSON array or CSV).
    internal static HashSet<string> ParseExporters(string? raw)
    {
        if (!HasValue(raw)) return new HashSet<string>(StringComparer.OrdinalIgnoreCase) { "console" };

        IEnumerable<string> values;
        try
        {
            values = JsonSerializer.Deserialize<string[]>(raw!) ?? Array.Empty<string>();
        }
        catch (JsonException)
        {
            values = raw!.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        }

        var set = new HashSet<string>(values.Select(v => v.Trim()).Where(HasValue), StringComparer.OrdinalIgnoreCase);
        return set.Count > 0 ? set : new HashSet<string>(StringComparer.OrdinalIgnoreCase) { "console" };
    }

    private static string? FirstEnv(params string[] names)
    {
        foreach (var name in names)
        {
            var value = Environment.GetEnvironmentVariable(name);
            if (HasValue(value)) return value;
        }

        return null;
    }

    private static bool HasValue(string? value) => !string.IsNullOrWhiteSpace(value);
}
