#This file contains tracer logic for the otel traces library.
import atexit
import json
import os

# Hardcoded fallbacks for the OTLP traces endpoint and org id. Env vars override
# these; leave them empty to fall back to console. X_ORG_ID is required for OTLP
# export no matter what — without it the tracer uses console.
DEFAULT_TRACES_ENDPOINT = ""
DEFAULT_X_ORG_ID = ""

DEFAULT_EXPORTERS = ["console"]

_initialized = False


#Finds first env.
def _first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


#Parses a JSON array or CSV list.
def _parse_list(raw: str | None, fallback: list[str]) -> list[str]:
    if not raw:
        return list(fallback)
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            values = [str(item).strip() for item in parsed if str(item).strip()]
            return values or list(fallback)
    except json.JSONDecodeError:
        pass
    values = [item.strip() for item in raw.split(",") if item.strip()]
    return values or list(fallback)


#Parses resource attributes.
def _parse_resource_attributes(raw: str | None) -> dict[str, str]:
    attributes: dict[str, str] = {}
    if not raw:
        return attributes
    for item in raw.split(","):
        key, sep, value = item.partition("=")
        key, value = key.strip(), value.strip()
        if key and sep and value:
            attributes[key] = value
    return attributes


#Normalizes endpoint to end in /v1/traces.
def _normalize_endpoint(endpoint: str | None) -> str | None:
    if not endpoint:
        return None
    if endpoint.endswith("/v1/traces"):
        return endpoint
    return f"{endpoint.rstrip('/')}/v1/traces"


#Derives runtime resource attributes, detecting the Azure runtime.
def _runtime_resource_attributes() -> dict[str, str]:
    attributes = _parse_resource_attributes(os.getenv("OTEL_RESOURCE_ATTRIBUTES"))
    attributes["service.name"] = (
        os.getenv("OTEL_SERVICE_NAME")
        or attributes.get("service.name")
        or os.getenv("WEBSITE_SITE_NAME")
        or "unknown_service"
    )
    attributes["pe-lib-trace-ver"] = "0.1.0"

    if _first_env("FUNCTIONS_EXTENSION_VERSION", "FUNCTIONS_WORKER_RUNTIME"):
        attributes["cloud.provider"] = "azure"
        attributes["cloud.platform"] = "azure_functions"
        site_name = os.getenv("WEBSITE_SITE_NAME")
        if site_name:
            attributes["faas.name"] = site_name
        return attributes

    if os.getenv("CONTAINER_APP_NAME"):
        attributes["cloud.provider"] = "azure"
        attributes["cloud.platform"] = "azure_container_apps"

    if os.getenv("WEBSITE_SITE_NAME"):
        attributes["cloud.provider"] = "azure"
        attributes["cloud.platform"] = "azure_app_service"

    running_on_kubernetes = bool(os.getenv("KUBERNETES_SERVICE_HOST"))
    k8s_cluster_name = _first_env("K8S_CLUSTER_NAME", "AKS_CLUSTER_NAME")
    k8s_namespace_name = _first_env("K8S_NAMESPACE_NAME", "POD_NAMESPACE")
    if running_on_kubernetes or k8s_cluster_name or k8s_namespace_name:
        attributes["cloud.provider"] = "azure"
        attributes["cloud.platform"] = "azure_aks"
    if k8s_cluster_name:
        attributes["k8s.cluster.name"] = k8s_cluster_name
    if k8s_namespace_name:
        attributes["k8s.namespace.name"] = k8s_namespace_name
    return attributes


#Reads the OTLP traces endpoint from env or the hardcoded default.
def _read_traces_endpoint() -> str | None:
    configured = os.getenv("OTEL_EXPORTER_PARAMETERS")
    if configured:
        try:
            parsed = json.loads(configured)
            url = parsed.get("otel", {}).get("trace", {}).get("url")
            if url:
                return url
        except (json.JSONDecodeError, AttributeError):
            pass
    return (
        os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
        or _normalize_endpoint(os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"))
        or DEFAULT_TRACES_ENDPOINT
        or None
    )


#Resolves org id.
def _org_id() -> str | None:
    return os.getenv("X_ORG_ID") or DEFAULT_X_ORG_ID or None


#Sets up the tracer provider: gates OTLP on endpoint + X_ORG_ID, else console;
#registers W3C tracecontext propagation (the OTel Python default).
def _init_provider() -> None:
    global _initialized
    if _initialized:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
            SimpleSpanProcessor,
        )
    except ImportError:
        return

    exporters = [item.lower() for item in _parse_list(os.getenv("OTEL_BACKEND_EXPORTERS"), DEFAULT_EXPORTERS)]
    endpoint = _read_traces_endpoint()
    org_id = _org_id()

    provider = TracerProvider(resource=Resource.create(_runtime_resource_attributes()))

    if "otel" in exporters and endpoint and org_id:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        exporter = OTLPSpanExporter(endpoint=endpoint, headers={"X-OrgId": org_id})
        provider.add_span_processor(BatchSpanProcessor(exporter))
    elif "console" in exporters:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    _initialized = True


#Initializes tracing: gates OTLP on endpoint + X_ORG_ID, else console; registers
#W3C propagation and opportunistically instruments HTTP libs that are installed.
def init():
    _init_provider()
    try:
        from opentelemetry.instrumentation.requests import RequestsInstrumentor
        RequestsInstrumentor().instrument()
    except Exception:
        pass
    try:
        from opentelemetry.instrumentation.flask import FlaskInstrumentor
        FlaskInstrumentor().instrument()  # global: instruments Flask apps created after this call
    except Exception:
        pass
    atexit.register(_flush)


#flush spans at interpreter exit
def _flush():
    try:
        from opentelemetry import trace
        trace.get_tracer_provider().force_flush()
    except Exception:
        pass


#Gets a tracer for manual spans.
def get_tracer(name: str = "otel"):
    from opentelemetry import trace

    return trace.get_tracer(name)
