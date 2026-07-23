# Databricks metrics collection

Databricks does not use the Azure Monitor exporter in this project. Grafana
Alloy authenticates to a Databricks workspace, runs SQL against Databricks
System Tables, exposes the results as Prometheus metrics, and sends them through
the shared metrics pipeline to Mimir.

## Flow

```mermaid
flowchart LR
    ST[Databricks System Tables] --> WH[SQL Warehouse]
    WH --> EXP[Alloy Databricks exporter]
    EXP --> SCRAPE[Prometheus scrape]
    SCRAPE --> ENRICH[CMDB enrichment]
    ENRICH --> MIMIR[Mimir]
    MIMIR --> GRAFANA[Grafana]
```

## Requirements

- Unity Catalog enabled.
- Databricks System Tables available.
- Running or auto-starting SQL Warehouse.
- Databricks service principal assigned to the workspace.
- Databricks OAuth M2M client ID and secret.
- Service principal has `CAN USE` on the SQL Warehouse.
- Service principal can read required System Tables.
- Alloy can reach the Databricks workspace over HTTPS.

## 1. Create the Databricks service principal

In the Databricks workspace:

1. Open **Settings → Identity and access → Service principals → Manage**.
2. Add or select the service principal used by Alloy.
3. Open **Secrets** and generate an OAuth secret.
4. Record the displayed client ID and secret.

The secret is displayed once. Store it in the approved secret manager and never
commit its real value to the repository.

## 2. Grant SQL Warehouse access

1. Open **SQL → SQL Warehouses**.
2. Select the warehouse Alloy will query.
3. Open **Permissions**.
4. Grant the service principal **CAN USE**.
5. Open **Connection details** and copy the HTTP path.

A serverless SQL Warehouse is preferred when available. Auto-stop reduces cost,
but each scrape can auto-start the warehouse.

## 3. Grant System Table access

Run these statements from the Databricks SQL editor as an administrator. Replace
`<DATABRICKS_CLIENT_ID>` with the service principal application/client ID.

```sql
GRANT USE CATALOG ON CATALOG system TO `<DATABRICKS_CLIENT_ID>`;

GRANT USE SCHEMA ON SCHEMA system.billing TO `<DATABRICKS_CLIENT_ID>`;
GRANT SELECT ON SCHEMA system.billing TO `<DATABRICKS_CLIENT_ID>`;

GRANT USE SCHEMA ON SCHEMA system.query TO `<DATABRICKS_CLIENT_ID>`;
GRANT SELECT ON SCHEMA system.query TO `<DATABRICKS_CLIENT_ID>`;

GRANT USE SCHEMA ON SCHEMA system.lakeflow TO `<DATABRICKS_CLIENT_ID>`;
GRANT SELECT ON SCHEMA system.lakeflow TO `<DATABRICKS_CLIENT_ID>`;
```

This gives the exporter access to:

| System Table | Purpose |
|---|---|
| `system.billing.usage` | DBU consumption |
| `system.billing.list_prices` | Estimated cost metrics |
| `system.lakeflow.job_run_timeline` | Job runs, status, duration and SLA misses |
| `system.lakeflow.job_task_run_timeline` | Optional task retry metrics |
| `system.lakeflow.pipeline_update_timeline` | Pipeline status, duration and freshness |
| `system.query.history` | SQL query count, errors, concurrency and duration |

## 4. Configure Alloy

Open `databricks.alloy` and replace:

| Placeholder | Where to find it |
|---|---|
| `<DATABRICKS_WORKSPACE_HOSTNAME>` | Azure Portal: **Azure Databricks → workspace → Overview → Workspace URL**; remove `https://` |
| `<DATABRICKS_SQL_WAREHOUSE_HTTP_PATH>` | Databricks: **SQL → SQL Warehouses → warehouse → Connection details → HTTP path** |
| `<DATABRICKS_CLIENT_ID>` | Databricks: **Settings → Identity and access → Service principals → application/client ID** |
| `<DATABRICKS_CLIENT_SECRET>` | Databricks service principal OAuth secret generated in step 1 |

Append the completed `databricks.alloy` file to the bottom of
`aks_alloy.alloy`. Its scrape output already points to the shared receiver:

```text
prometheus.exporter.databricks
  → prometheus.scrape
  → otelcol.receiver.prometheus.convert_metrics
  → CMDB enrichment
  → Mimir
```

Use one exporter block per workspace or warehouse credential set. Give every
additional Alloy component a unique label.

## 5. Collection timing

- Current scrape interval: `10m`.
- Current scrape timeout: `9m`.
- Billing lookback: `24h`.
- Jobs and pipelines lookback: `3h`.
- SQL query lookback: `2h`.

These metrics use sliding windows. Values can decrease when older records leave
the window; they are not cumulative counters. Billing data normally arrives
24–48 hours late.

Longer lookbacks improve continuity but increase SQL Warehouse query time and
cost. Do not scrape more frequently than necessary.

## 6. Dashboard metrics

The standard Databricks dashboard uses:

| Metric | Shows |
|---|---|
| `databricks_exporter_up` | Exporter connection health |
| `databricks_billing_dbus_sliding` | DBUs in the billing lookback window |
| `databricks_job_runs_sliding` | Job runs in the jobs lookback window |
| `databricks_job_sla_miss_sliding` | Jobs exceeding the configured SLA threshold |
| `databricks_query_errors_sliding` | Failed SQL queries |
| `databricks_pipeline_freshness_lag_seconds_sliding` | Pipeline freshness delay |

The shared Alloy pipeline adds `cmdbReference`. Prometheus exposes the scrape
job identity as `service_name`, allowing the dashboard filters
`CMDB_REFERENCE` and `Service name` to work.

## 7. Validate

1. Open Alloy UI and confirm `prometheus.exporter.databricks` and
   `prometheus.scrape.azure_databricks` are healthy.
2. In Grafana Explore, select the Mimir/Prometheus datasource.
3. Query:

```promql
databricks_exporter_up
databricks_scrape_status
databricks_job_runs_sliding
```

Expected:

- `databricks_exporter_up` equals `1`.
- `databricks_scrape_status` equals `1` for each available query group.
- Metrics contain `cmdbReference` and `service_name`.
- Databricks dashboard filters populate after the first successful scrape.

## Troubleshooting

| Symptom | Check |
|---|---|
| `401` | Client ID, OAuth secret, secret expiry and workspace assignment |
| `403` | Warehouse `CAN USE` and Unity Catalog grants |
| Warehouse timeout | Warehouse state, HTTP path, network and scrape timeout |
| Billing panel empty | Recent billable usage and expected 24–48 hour delay |
| Pipeline panels empty | `SELECT` access and availability of `system.lakeflow.pipeline_update_timeline` |
| Some metrics missing | Recent jobs, pipelines or SQL activity inside configured lookback |
| Filters empty | Shared pipeline enrichment and successful write to Mimir |

## References

- [Grafana Alloy Databricks exporter](https://grafana.com/docs/grafana-cloud/send-data/alloy/reference/components/prometheus/prometheus.exporter.databricks/)
- [Exporter metrics reference](https://github.com/grafana/databricks-prometheus-exporter/blob/main/docs/metrics-reference.md)
- [Azure Databricks OAuth M2M](https://learn.microsoft.com/azure/databricks/dev-tools/auth/oauth-m2m)
- [Azure Databricks System Tables](https://learn.microsoft.com/azure/databricks/admin/system-tables/)
