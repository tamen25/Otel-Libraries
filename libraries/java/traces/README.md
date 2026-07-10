<!-- This document explains readme for CloudOps. -->
# com.cloudops:otel-traces

Java tracing helper for CloudOps services.

```java
import com.cloudops.otel.traces.CloudOpsTracer;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.context.Scope;

CloudOpsTracer tracer = CloudOpsTracer.initializeTracer();

// Continue the caller's trace from the incoming request headers.
Span span = tracer.startServerSpan("GET /process", incomingHeaders);
try (Scope scope = span.makeCurrent()) {
  // ... work; logs emitted here carry the trace id ...
  // Propagate context to the downstream call:
  Map<String, String> headers = tracer.injectHeaders();  // add these to the outgoing request
} finally {
  span.end();
  tracer.exportSpans();
}
```

`initializeTracer` gates OTLP export on **both** a resolved endpoint URL and
`X_ORG_ID` (sent as the `X-OrgId` header); otherwise no OTLP exporter is added.
The W3C `tracecontext` propagator is registered, and `startServerSpan` /
`injectHeaders` extract and inject it — so a request stays one connected trace
across services even with the raw JDK HTTP server/client.

Configuration mirrors the other CloudOps libraries: `OTEL_BACKEND_EXPORTERS`,
`OTEL_SERVICE_NAME` / `OTEL_RESOURCE_ATTRIBUTES` (Azure runtime attributes added
automatically), `OTEL_EXPORTER_PARAMETERS` (`otel.trace.url`),
`OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` / `OTEL_EXPORTER_OTLP_ENDPOINT`, and
`X_ORG_ID` (required for OTLP export).
