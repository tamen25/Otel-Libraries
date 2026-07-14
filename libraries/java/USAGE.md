# Java — otel:otel-logs / otel:otel-traces usage

OpenTelemetry logging and tracing for Java services. Two independent artifacts —
depend on only what you need. Requires Java 21.

## Install (Maven)

Add your private Maven repository (credentials in `~/.m2/settings.xml`), then:

```xml
<dependency>
  <groupId>otel</groupId><artifactId>otel-logs</artifactId><version>0.1.0</version>
</dependency>
<dependency>
  <groupId>otel</groupId><artifactId>otel-traces</artifactId><version>0.1.0</version>
</dependency>
```

Or build + install from the source in this package:

```bash
mvn -f logs/pom.xml install
mvn -f traces/pom.xml install
```

## Logging

```java
import otel.logs.Logger;
final Logger logger = Logger.init();

logger.info("order created", "order_id", orderId);   // key/value varargs
logger.warn("retrying", "attempt", 2);
logger.error(exception);
// logger.exportLogs();   // optional — batched logs also flush at shutdown
```

## Tracing

`Tracer.init()` registers the W3C `tracecontext` propagator. Two framework-free
edge helpers replace manual span plumbing for the raw JDK HTTP server/client:

```java
import otel.traces.Tracer;
final Tracer tracer = Tracer.init();

// Inbound: run a handler inside a SERVER span that continues the caller's trace.
server.createContext("/process", tracer.wrap("process", handler));

// Outbound: a client whose send() creates a CLIENT span and injects W3C headers.
var resp = tracer.tracedClient().send(request, HttpResponse.BodyHandlers.ofString());
```

The lower-level API (`startServerSpan`, `startClientSpan`, `injectHeaders`,
`exportSpans`) remains public for non-HTTP transports.

## Configuration (`OTEL_*` environment variables)

| Variable | Meaning |
|----------|---------|
| `OTEL_SERVICE_NAME` | `service.name` on every record. **Set in every app.** |
| `OTEL_BACKEND_EXPORTERS` | `console` (default) or `otel` (OTLP/HTTP). |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP endpoint (or the `*_LOGS_`/`*_TRACES_` variants). |
| `X_ORG_ID` | Org identifier, sent as the `X-OrgId` header. Required for `otel`. |
| `OTEL_RESOURCE_ATTRIBUTES` | Extra resource attributes (CSV `k=v`). |
| `OTEL_LOG_LEVEL` | Enabled log levels (logs). |
| `OTEL_LOGS_SAMPLING_RATE` | 0–100, default 100 (logs). |

The OTLP exporter is used only when **both** an endpoint and `X_ORG_ID` resolve;
otherwise it falls back to console. `X_ORG_ID` is an **org identifier, not a
secret** — safe to keep in plain config. Azure runtime attributes are added
automatically.

## Test

```bash
mvn -f logs/pom.xml verify
mvn -f traces/pom.xml verify
```
