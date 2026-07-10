<!-- This document explains the readme for the otel traces library. -->
# otel:otel-traces

Java tracing helper built on OpenTelemetry.

```java
import otel.traces.Tracer;
import java.net.http.HttpResponse;

Tracer tracer = Tracer.init();

// Inbound: wrap a com.sun.net.httpserver handler — extracts W3C context from
// the request headers and runs the handler inside a SERVER span.
server.createContext("/process", tracer.wrap("GET /process", handler));

// Outbound: wraps java.net.http.HttpClient — creates a CLIENT span and injects
// W3C headers on every send, so the downstream service continues the trace.
var client = tracer.tracedClient();
var response = client.send(request, HttpResponse.BodyHandlers.ofString());
```

The manual API (`startServerSpan`, `startClientSpan`, `injectHeaders`,
`exportSpans`) stays public for non-HTTP or custom transports.

`Tracer.init()` gates OTLP export on **both** a resolved endpoint URL and
`X_ORG_ID` (sent as the `X-OrgId` header); otherwise no OTLP exporter is added.
The W3C `tracecontext` propagator is registered, and `wrap` / `tracedClient`
extract and inject it — so a request stays one connected trace across services
even with the raw JDK HTTP server/client. A best-effort span flush is registered
at process shutdown.

Configuration mirrors the other libraries: `OTEL_BACKEND_EXPORTERS`,
`OTEL_SERVICE_NAME` / `OTEL_RESOURCE_ATTRIBUTES` (Azure runtime attributes added
automatically), `OTEL_EXPORTER_PARAMETERS` (`otel.trace.url`),
`OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` / `OTEL_EXPORTER_OTLP_ENDPOINT`, and
`X_ORG_ID` (required for OTLP export).
