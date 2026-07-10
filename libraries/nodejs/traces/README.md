<!-- This document explains readme for CloudOps. -->
# @cloudops/otel-traces

CloudOps OpenTelemetry traces helper for Node.js services.

Aligned with `@cloudops/otel-logs` in this repo: `console`/`otel` exporters,
Azure runtime detection (Functions / Container Apps / App Service / AKS with
`cloud.provider=azure`), and X_ORG_ID/`X-OrgId` authentication.

**Automatic cross-service propagation:** HTTP calls are auto-instrumented and
the W3C `tracecontext` propagator is registered, so a request flowing through
several services stays one connected trace with no manual header handling.
Azure-SDK service extensions (Service Bus, Cosmos DB, Event Hubs, Event Grid,
Blob Storage, Data Explorer, API Management, Functions) decorate spans with
service-specific attributes on top.

## Usage

```ts
import { tracer, AzureService } from "@cloudops/otel-traces";

const span = tracer.startBasicSpan("handle-order");
try {
  // ... work ...
} catch (error) {
  tracer.recordError(error, span);
} finally {
  span?.end();
  await tracer.exportSpans();
}

// Azure-service-aware spans
const busSpan = tracer.startAzureSpan(AzureService.SERVICE_BUS_TOPIC, {
  serviceBusTopicAttributes: { topicName: "orders", namespace: "cloudops" },
});
busSpan?.end();
```

## Configuration

Driven by the same `OTEL_*` env-var contract as the other libraries:

- `OTEL_BACKEND_EXPORTERS` — `console` (default) or `otel` (OTLP/HTTP).
- `OTEL_SERVICE_NAME` / `OTEL_RESOURCE_ATTRIBUTES` — resource identity.
- `OTEL_EXPORTER_PARAMETERS` — inline JSON exporter config
  (`{ "otel": { "trace": { "url": "..." } } }`).
- `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` / `OTEL_EXPORTER_OTLP_ENDPOINT` — endpoint
  (normalised to end in `/v1/traces`), else the `DEFAULT_TRACES_ENDPOINT` constant.
- `X_ORG_ID` — authentication key, sent on every OTLP export as the `X-OrgId`
  header (or bake into `DEFAULT_X_ORG_ID`). **Required** for OTLP export: without
  both an endpoint URL and `X_ORG_ID` the tracer falls back to console.
- `TRACEID_RATIO_BASED_SAMPLER` — root sampler ratio (default `1`).
- `ENABLE_OTEL_DEBUG_LOGS=true` — verbose diagnostics.

There is no secrets/parameter file. Trace context propagation uses W3C
`tracecontext`; IDs use the default random id generator.

## Build & test

```bash
npm install
npm run build          # tsc -> dist/
npm test               # build + node --test
npm run test:coverage  # build + node --test with coverage gates
```
