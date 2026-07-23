# GitHub Copilot instructions

## Project purpose

This folder builds a modular Grafana Alloy configuration for collecting telemetry from AKS, Kubernetes and Azure services and sending it directly to LGTM backends:

- Metrics go to Mimir through Prometheus `remote_write`.
- Traces go to Tempo through OTLP/HTTP.
- Logs go to Loki through `loki.write`.
- Grafana reads from Mimir, Tempo and Loki.
- There is no central OpenTelemetry gateway in this design.

## File roles

- `aks_alloy.alloy` is the main shared pipeline and must remain usable by itself.
- `alloy-aks-azure-lgtm-guide.md` documents metrics, traces, identity and deployment.
- `alloy-aks-logging-guide.md` documents every logging source and logging deployment requirement.
- `services/azure-monitor/*.alloy` contains optional Azure metric snippets.
- `services/event-hubs/*.alloy` contains optional Azure Event Hub log snippets.
- `services/kubernetes/*.alloy` contains optional Kubernetes metric and log snippets.

Users enable an optional service by copying its entire snippet to the bottom of `aks_alloy.alloy` and replacing its uppercase `<PLACEHOLDERS>`.

## Required design rules

1. Keep Mimir, Tempo and Loki as separate direct destinations.
2. Optional metric snippets must feed `otelcol.receiver.prometheus.convert_metrics` from the main file.
3. Optional log snippets must feed `loki.write.loki` from the main file.
4. Do not redefine shared backend exporters or endpoints inside optional snippets.
5. Do not add real subscription IDs, tenant IDs, credentials, resource IDs or internal URLs.
6. Use explicit uppercase placeholders such as `<AZURE_SUBSCRIPTION_ID>`.
7. Do not introduce Helm templating into `.alloy` files.
8. Keep component labels unique so snippets can be appended together.
9. Keep comments short and order components by data flow.
10. Use Azure Portal instructions for locating Azure values.

## Kubernetes logging rules

- Pod logs use node-local discovery with `HOSTNAME` populated from `spec.nodeName`.
- Kubernetes Events need one collector or Alloy clustering plus persistent `--storage.path`.
- Node journal collection needs a DaemonSet and read-only journal mounts.
- AKS control-plane logs must use Azure Diagnostic settings and Event Hub.
- Never enable API-based and file-based collection for the same pod logs.
- Document API/Kubelet load, duplicate-log and label-cardinality risks.

## Documentation rules

- Keep the main guide concise.
- Put detailed logging material only in `alloy-aks-logging-guide.md`.
- Preserve placeholder repository links using `<ADD_LINK_...>`.
- Update diagrams and troubleshooting when a data flow changes.
- Do not use the word “reconstructed”.

## Validation

Before proposing a completed change:

```bash
rg '<[A-Z0-9_]+>' aks_alloy.alloy
alloy validate aks_alloy.alloy
```

Remaining placeholders are acceptable in reusable source snippets and documentation, but not in a deployment-ready combined configuration.
