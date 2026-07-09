# AWS → Azure Conversion — Design

**Date:** 2026-07-09
**Status:** Approved
**Scope:** All three library ports (`libraries/python/logs`, `libraries/java/logs`, `libraries/dotnet/logs`) plus documentation. Hard cutover — no AWS names retained, no deprecated aliases.

## Background

The CloudOps OTel logs libraries were built for AWS: runtime detection covers
Lambda / ECS / EKS, and the exporter-config source is named after AWS SSM
Parameter Store (`SsmParameters`, `OTEL_SSM_PARAMETERS*`). The libraries are
being redeployed to Azure. Requirement: convert detection and naming to Azure,
leaving **no trace of AWS** in code, tests, or docs.

## Goals

1. Auto-detect Azure runtimes: Azure Functions, Azure Container Apps, Azure
   App Service, AKS (and plain Kubernetes).
2. Rename the exporter-config source to provider-neutral names.
3. Keep the three ports behaviourally identical (same env contract, same
   attribute output).
4. `grep -ri aws libraries/` returns nothing when done.

## Non-goals

- No provider-abstraction layer (single provider; YAGNI).
- No change to the JSON config-blob shape, sampling, batching, level
  filtering, or exporter logic.
- No package renames (`cloudops-otel-logs` etc. stay).

## 1. Runtime detection ladder

Replaces the Lambda/ECS/EKS logic in `RuntimeResourceAttributes` (Java/.NET)
and `_runtime_resource_attributes` (Python). Checked in order; the first match
sets `cloud.platform`. Whenever a platform is detected, `cloud.provider=azure`
is also set.

| # | Runtime | Trigger env vars | Attributes set | Flow |
|---|---------|------------------|----------------|------|
| 1 | Azure Functions | `FUNCTIONS_EXTENSION_VERSION` or `FUNCTIONS_WORKER_RUNTIME` | `cloud.platform=azure_functions`, `faas.name=<WEBSITE_SITE_NAME>` | early return (mirrors current Lambda short-circuit) |
| 2 | Azure Container Apps | `CONTAINER_APP_NAME` | `cloud.platform=azure_container_apps` | falls through to K8s/optional attrs |
| 3 | Azure App Service | `WEBSITE_SITE_NAME` (Functions already excluded by row 1) | `cloud.platform=azure_app_service` | falls through |
| 4 | AKS / Kubernetes | `KUBERNETES_SERVICE_HOST` or any `K8S_*` signal | `cloud.platform=azure_aks` + `k8s.*` attributes | falls through |

Platform strings follow OTel semantic conventions: `azure_functions`,
`azure_container_apps`, `azure_app_service`, `azure_aks`.

If `WEBSITE_SITE_NAME` is unset on a detected Functions runtime (e.g. local
Functions tooling), `faas.name` is omitted; `cloud.platform` is still set.

### Fallback env-var changes

| Attribute | Old fallback chain | New fallback chain |
|---|---|---|
| `service.name` | `OTEL_SERVICE_NAME` → resource attrs → `AWS_LAMBDA_FUNCTION_NAME` → `unknown_service` | `OTEL_SERVICE_NAME` → resource attrs → `WEBSITE_SITE_NAME` → `unknown_service` |
| `k8s.cluster.name` | `K8S_CLUSTER_NAME` → `EKS_CLUSTER_NAME` | `K8S_CLUSTER_NAME` → `AKS_CLUSTER_NAME` |
| `container.name` | `CONTAINER_NAME` → `ECS_CONTAINER_NAME` | `CONTAINER_NAME` → `CONTAINER_APP_NAME` |
| `k8s.pod.name` | `K8S_POD_NAME` → `POD_NAME` → `HOSTNAME` (when on K8s) | unchanged (already neutral) |
| `k8s.namespace.name`, `k8s.node.name` | `K8S_*` → `POD_NAMESPACE`/`NODE_NAME` | unchanged (already neutral) |

Precedence rules preserved from the current implementation:

- Functions detection early-returns, so a Functions app never reports
  `azure_app_service` or `k8s.*` attributes (same as Lambda today).
- Container Apps and App Service do **not** early-return (same as ECS today);
  K8s signals can still add `k8s.*` attributes afterwards, and the last
  platform assignment in the fall-through order wins exactly as it does in the
  current AWS ladder (ECS then EKS → Container Apps / App Service then AKS).

## 2. Exporter-config source rename (hard cutover)

Provider-neutral naming; mechanism (inline JSON env var, or file) unchanged.

| Old | New |
|---|---|
| `OTEL_SSM_PARAMETERS` | `OTEL_EXPORTER_PARAMETERS` |
| `OTEL_SSM_PARAMETERS_FILE` | `OTEL_EXPORTER_PARAMETERS_FILE` |
| `SsmParameters` (class, all ports) | `ExporterParameters` |
| `_read_ssm_parameters` etc. (internal readers) | `_read_exporter_parameters` etc. |
| `/tmp/otelExporterParams.json` (default file) | unchanged — already neutral |

JSON blob shape is unchanged. Anything still setting only `OTEL_SSM_PARAMETERS`
after the cutover gets the existing missing-config behaviour: fall back to the
console exporter.

## 3. Documentation and comment sweep

- `libraries/{python,java,dotnet}/logs/README.md`: env-var tables, runtime
  detection sections, examples.
- `CLAUDE.md`: shared-design section (`SsmParameters` → `ExporterParameters`),
  env-var contract, "AWS runtime auto-detection" paragraph → Azure.
- Any code comments naming AWS/Lambda/ECS/EKS/SSM.
- Acceptance check: `grep -ri "aws\|ssm\|lambda\|ecs\|eks" libraries/` returns
  no hits (word "eks" checked with word boundaries to avoid false positives).

## 4. Testing

Per port, unit tests (existing coverage gates must stay green):

- Each runtime trigger produces its platform + attributes (4 runtimes × 3 ports).
- Precedence: Functions beats App Service (both set `WEBSITE_SITE_NAME`);
  Container Apps + K8s signals together end as `azure_aks` via fall-through
  (documents the winner explicitly).
- `service.name` fallback to `WEBSITE_SITE_NAME`.
- Config source honoured via `OTEL_EXPORTER_PARAMETERS` (inline) and
  `OTEL_EXPORTER_PARAMETERS_FILE` (file), old names dead.
- All existing AWS-named tests renamed/re-pointed.

Live verification (after implementation): run the demo stack, override one app
per Azure runtime (as done for AWS during design), confirm `azure_functions` /
`azure_container_apps` / `azure_aks` platform attributes arrive in Loki
structured metadata end-to-end.

## Rollout

Single change set across the three ports (keep-in-sync convention). Version
stays 0.1.0 — libraries are source-only here, not published from this repo.
