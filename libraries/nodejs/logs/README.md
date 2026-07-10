<!-- This document explains the readme for the otel logs library. -->
# @otel/logs

Node.js/TypeScript OpenTelemetry logs helper.

```ts
import { logger } from "@otel/logs";

logger.info("order created", { orderId });
logger.error(error);

await logger.exportLogs();
```

The logger supports console output by default and OTLP export when configured
with `OTEL_BACKEND_EXPORTERS=["otel"]`.

## OTLP configuration

The endpoint URL is resolved in this order:

1. `OTEL_EXPORTER_PARAMETERS` as inline JSON:
   `{"otel":{"logs":{"url":"https://otel.example.com/v1/logs"}}}`
2. Direct OpenTelemetry env vars:
   `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT` or `OTEL_EXPORTER_OTLP_ENDPOINT`.
3. The hardcoded `DEFAULT_LOGS_ENDPOINT` constant in `src/utils.ts`.

`X_ORG_ID` is the authentication key, sent on every OTLP export as the `X-OrgId`
header (or bake it into the `DEFAULT_X_ORG_ID` constant). The OTLP exporter is
used only when **both** an endpoint URL and `X_ORG_ID` resolve; otherwise the
library falls back to console. There is no secrets/parameter file.

## Runtime resource attributes

Set `OTEL_SERVICE_NAME` in every app. The library uses it as `service.name`.
It also merges `OTEL_RESOURCE_ATTRIBUTES`, so app or deployment metadata such
as `deployment.environment=dev,k8s.cluster.name=demo-cluster` is kept
on exported log records.

The library also detects the Azure runtime and adds OpenTelemetry resource
attributes without requiring deprecated semantic-convention constants:

| Runtime | Detection | Attributes added |
| --- | --- | --- |
| Azure Functions | `FUNCTIONS_EXTENSION_VERSION` or `FUNCTIONS_WORKER_RUNTIME` | `cloud.provider=azure`, `cloud.platform=azure_functions`, `faas.name` |
| Container Apps | `CONTAINER_APP_NAME` | `cloud.provider=azure`, `cloud.platform=azure_container_apps`, optional container attributes |
| App Service | `WEBSITE_SITE_NAME` | `cloud.provider=azure`, `cloud.platform=azure_app_service` |
| AKS | `KUBERNETES_SERVICE_HOST` or injected `K8S_*` values | `cloud.provider=azure`, `cloud.platform=azure_aks`, optional Kubernetes attributes |

For AKS, expose these env vars from the Kubernetes downward API when possible:
`K8S_CLUSTER_NAME` (or `AKS_CLUSTER_NAME`), `K8S_NAMESPACE_NAME`, `K8S_POD_NAME`,
`K8S_NODE_NAME`, and `CONTAINER_NAME`. The pod `HOSTNAME` is used as a fallback
pod name when the app is running inside Kubernetes.
