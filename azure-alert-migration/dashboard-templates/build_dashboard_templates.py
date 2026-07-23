#!/usr/bin/env python3
"""Generate and provision standard Azure and Kubernetes dashboard templates."""

import argparse
import json
import os
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))

GRAFANA = os.getenv("GRAFANA", "http://localhost:3000")
OUTPUT = os.path.join(HERE, "dashboards")
FOLDER_UID = "standard-dashboard-templates"
FOLDER_TITLE = "Standard Dashboard Templates"
PROM = {"type": "prometheus", "uid": "$metrics_datasource"}
LOKI = {"type": "loki", "uid": "$logs_datasource"}
TEMPO = {"type": "tempo", "uid": "$traces_datasource"}

AZURE_BLUE = "#0078D4"
AZURE_GREEN = "#107C10"
AZURE_AMBER = "#FFB900"
AZURE_RED = "#D13438"
PROM_CMDB_LABEL = "cmdbReference"
PROM_SERVICE_LABEL = "service_name"
OVERVIEW_METRIC_SELECTOR = (
    '{__name__=~"(?:azure_.+|databricks_.+|container_.+|kube_.+)"}'
)


def common_prom_filter():
    return (
        f'{PROM_CMDB_LABEL}=~"$cmdb_reference",'
        f'{PROM_SERVICE_LABEL}=~"$service_name"'
    )


def common_loki_selector():
    return '{job=~"$service_name",cmdbReference=~"$cmdb_reference"}'


def correlated_loki_selector():
    return '{cmdbReference=~"$cmdb_reference"}'


def correlated_trace_selector():
    return '{resource.cmdbReference=~"$cmdb_reference"}'


SERVICES = {
    "virtual_machines": {"title": "Virtual Machines", "type": "Microsoft.Compute/virtualMachines"},
    "sql_database": {"title": "SQL Database", "type": "Microsoft.Sql/servers/databases"},
    "sql_managed_instance": {"title": "SQL Managed Instance", "type": "Microsoft.Sql/managedInstances"},
    "service_bus": {"title": "Service Bus", "type": "Microsoft.ServiceBus/Namespaces"},
    "event_hubs": {"title": "Event Hubs", "type": "Microsoft.EventHub/Namespaces"},
    "event_grid": {"title": "Event Grid", "type": "Microsoft.EventGrid/topics"},
    "logic_apps": {"title": "Logic Apps Consumption", "type": "Microsoft.Logic/Workflows"},
    "logic_apps_standard": {"title": "Logic Apps Standard", "type": "Microsoft.Web/sites"},
    "redis_cache": {"title": "Azure Cache for Redis", "type": "Microsoft.Cache/redis"},
    "cosmos_db": {"title": "Cosmos DB", "type": "Microsoft.DocumentDB/DatabaseAccounts"},
    "databricks": {"title": "Azure Databricks", "type": "Microsoft.Databricks/workspaces"},
    "storage_accounts": {"title": "Storage Accounts", "type": "Microsoft.Storage/storageAccounts"},
    "storage_files": {"title": "Azure Files", "type": "Microsoft.Storage/storageAccounts/fileServices"},
    "storage_blobs": {"title": "Blob Storage", "type": "Microsoft.Storage/storageAccounts/blobServices"},
    "kubernetes": {"title": "AKS / Kubernetes", "type": "Microsoft.ContainerService/managedClusters"},
}


def azure_name(resource_type, metric, aggregation, unit):
    """Match prometheus.exporter.azure default metric_name_template."""
    normalized_type = resource_type.lower().replace("/", "_").replace(".", "_")
    normalized_metric = (
        metric.lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("%", "percent")
    )
    return f"azure_{normalized_type}_{normalized_metric}_{aggregation}_{unit}"


METRICS = {
    "virtual_machines": [
        ("CPU utilization", azure_name("Microsoft.Compute/virtualMachines", "Percentage CPU", "average", "percent"), "percent"),
        ("Available memory", azure_name("Microsoft.Compute/virtualMachines", "Available Memory Percentage", "average", "percent"), "percent"),
        ("Data disk latency", azure_name("Microsoft.Compute/virtualMachines", "Data Disk Latency", "average", "milliseconds"), "ms"),
        ("Disk queue depth", azure_name("Microsoft.Compute/virtualMachines", "Data Disk Queue Depth", "average", "count"), "short"),
        ("Disk read bytes", azure_name("Microsoft.Compute/virtualMachines", "Disk Read Bytes", "total", "bytes"), "bytes"),
        ("Disk write bytes", azure_name("Microsoft.Compute/virtualMachines", "Disk Write Bytes", "total", "bytes"), "bytes"),
    ],
    "sql_database": [
        ("CPU", azure_name("Microsoft.Sql/servers/databases", "cpu_percent", "average", "percent"), "percent"),
        ("DTU utilization", azure_name("Microsoft.Sql/servers/databases", "dtu_consumption_percent", "average", "percent"), "percent"),
        ("Storage used", azure_name("Microsoft.Sql/servers/databases", "storage_percent", "average", "percent"), "percent"),
        ("Deadlocks", azure_name("Microsoft.Sql/servers/databases", "deadlock", "total", "count"), "short"),
        ("Failed connections", azure_name("Microsoft.Sql/servers/databases", "connection_failed", "total", "count"), "short"),
        ("Database availability", azure_name("Microsoft.Sql/servers/databases", "availability", "average", "percent"), "percent"),
    ],
    "sql_managed_instance": [
        ("CPU", azure_name("Microsoft.Sql/managedInstances", "avg_cpu_percent", "average", "percent"), "percent"),
        ("Storage used", azure_name("Microsoft.Sql/managedInstances", "storage_space_used_mb", "average", "megabytes"), "decmbytes"),
        ("Reserved storage", azure_name("Microsoft.Sql/managedInstances", "reserved_storage_mb", "average", "megabytes"), "decmbytes"),
        ("Bytes read", azure_name("Microsoft.Sql/managedInstances", "io_bytes_read", "total", "bytes"), "bytes"),
        ("Bytes written", azure_name("Microsoft.Sql/managedInstances", "io_bytes_written", "total", "bytes"), "bytes"),
        ("I/O requests", azure_name("Microsoft.Sql/managedInstances", "io_requests", "total", "count"), "short"),
    ],
    "service_bus": [
        ("Active messages", azure_name("Microsoft.ServiceBus/Namespaces", "ActiveMessages", "average", "count"), "short"),
        ("Dead-letter messages", azure_name("Microsoft.ServiceBus/Namespaces", "DeadletteredMessages", "average", "count"), "short"),
        ("Incoming messages", azure_name("Microsoft.ServiceBus/Namespaces", "IncomingMessages", "total", "count"), "short"),
        ("Outgoing messages", azure_name("Microsoft.ServiceBus/Namespaces", "OutgoingMessages", "total", "count"), "short"),
        ("Namespace CPU", azure_name("Microsoft.ServiceBus/Namespaces", "NamespaceCpuUsage", "average", "percent"), "percent"),
        ("Send latency", azure_name("Microsoft.ServiceBus/Namespaces", "ServerSendLatency", "average", "milliseconds"), "ms"),
    ],
    "event_hubs": [
        ("Incoming messages", azure_name("Microsoft.EventHub/Namespaces", "IncomingMessages", "total", "count"), "short"),
        ("Outgoing messages", azure_name("Microsoft.EventHub/Namespaces", "OutgoingMessages", "total", "count"), "short"),
        ("Ingress", azure_name("Microsoft.EventHub/Namespaces", "IncomingBytes", "total", "bytes"), "bytes"),
        ("Egress", azure_name("Microsoft.EventHub/Namespaces", "OutgoingBytes", "total", "bytes"), "bytes"),
        ("Throttled requests", azure_name("Microsoft.EventHub/Namespaces", "ThrottledRequests", "total", "count"), "short"),
        ("Server errors", azure_name("Microsoft.EventHub/Namespaces", "ServerErrors", "total", "count"), "short"),
    ],
    "event_grid": [
        ("Publish successes", azure_name("Microsoft.EventGrid/topics", "PublishSuccessCount", "total", "count"), "short"),
        ("Publish failures", azure_name("Microsoft.EventGrid/topics", "PublishFailCount", "total", "count"), "short"),
        ("Dead-lettered events", azure_name("Microsoft.EventGrid/topics", "DeadLetteredCount", "total", "count"), "short"),
        ("Delivery successes", azure_name("Microsoft.EventGrid/topics", "DeliverySuccessCount", "total", "count"), "short"),
        ("Publish latency", azure_name("Microsoft.EventGrid/topics", "PublishSuccessLatencyInMs", "average", "milliseconds"), "ms"),
        ("Destination processing", azure_name("Microsoft.EventGrid/topics", "DestinationProcessingDurationInMs", "average", "milliseconds"), "ms"),
    ],
    "logic_apps": [
        ("Runs started", azure_name("Microsoft.Logic/Workflows", "RunsStarted", "total", "count"), "short"),
        ("Runs succeeded", azure_name("Microsoft.Logic/Workflows", "RunsSucceeded", "total", "count"), "short"),
        ("Runs failed", azure_name("Microsoft.Logic/Workflows", "RunsFailed", "total", "count"), "short"),
        ("Failure percentage", azure_name("Microsoft.Logic/Workflows", "RunFailurePercentage", "average", "percent"), "percent"),
        ("Run latency", azure_name("Microsoft.Logic/Workflows", "RunLatency", "average", "milliseconds"), "ms"),
        ("Throttled runs", azure_name("Microsoft.Logic/Workflows", "RunThrottledEvents", "total", "count"), "short"),
    ],
    "logic_apps_standard": [
        ("CPU time", azure_name("Microsoft.Web/sites", "CpuTime", "total", "seconds"), "s"),
        ("Memory working set", azure_name("Microsoft.Web/sites", "MemoryWorkingSet", "average", "bytes"), "bytes"),
        ("HTTP response time", azure_name("Microsoft.Web/sites", "HttpResponseTime", "average", "seconds"), "s"),
        ("HTTP 5xx", azure_name("Microsoft.Web/sites", "Http5xx", "total", "count"), "short"),
        ("Workflow failure rate", azure_name("Microsoft.Web/sites", "WorkflowRunsFailureRate", "total", "percent"), "percent"),
        ("Job execution duration", azure_name("Microsoft.Web/sites", "WorkflowJobExecutionDuration", "average", "seconds"), "s"),
    ],
    "redis_cache": [
        ("Operations/sec", azure_name("Microsoft.Cache/redis", "alloperationsPerSecond", "average", "count"), "ops"),
        ("Server load", azure_name("Microsoft.Cache/redis", "allserverLoad", "average", "percent"), "percent"),
        ("Connected clients", azure_name("Microsoft.Cache/redis", "allconnectedclients", "average", "count"), "short"),
        ("Memory used", azure_name("Microsoft.Cache/redis", "allusedmemorypercentage", "average", "percent"), "percent"),
        ("Cache hits", azure_name("Microsoft.Cache/redis", "allcachehits", "total", "count"), "short"),
        ("Cache misses", azure_name("Microsoft.Cache/redis", "allcachemisses", "total", "count"), "short"),
    ],
    "cosmos_db": [
        ("Normalized RU consumption", azure_name("Microsoft.DocumentDB/DatabaseAccounts", "NormalizedRUConsumption", "average", "percent"), "percent"),
        ("Provisioned throughput", azure_name("Microsoft.DocumentDB/DatabaseAccounts", "ProvisionedThroughput", "average", "count"), "short"),
        ("Server-side latency", azure_name("Microsoft.DocumentDB/DatabaseAccounts", "ServerSideLatencyDirect", "average", "milliseconds"), "ms"),
        ("Service availability", azure_name("Microsoft.DocumentDB/DatabaseAccounts", "ServiceAvailability", "average", "percent"), "percent"),
        ("Total requests", azure_name("Microsoft.DocumentDB/DatabaseAccounts", "TotalRequests", "total", "count"), "short"),
        ("Request units", azure_name("Microsoft.DocumentDB/DatabaseAccounts", "TotalRequestUnits", "total", "count"), "short"),
    ],
    "databricks": [
        ("Exporter health", "databricks_exporter_up", "bool"),
        ("DBUs consumed (24h window)", "databricks_billing_dbus_sliding", "short"),
        ("Job runs", "databricks_job_runs_sliding", "short"),
        ("Job SLA misses", "databricks_job_sla_miss_sliding", "short"),
        ("SQL query errors", "databricks_query_errors_sliding", "short"),
        ("Pipeline freshness lag", "databricks_pipeline_freshness_lag_seconds_sliding", "s"),
    ],
    "storage_accounts": [
        ("Availability", azure_name("Microsoft.Storage/storageAccounts", "Availability", "average", "percent"), "percent"),
        ("Ingress", azure_name("Microsoft.Storage/storageAccounts", "Ingress", "total", "bytes"), "bytes"),
        ("Egress", azure_name("Microsoft.Storage/storageAccounts", "Egress", "total", "bytes"), "bytes"),
        ("End-to-end latency", azure_name("Microsoft.Storage/storageAccounts", "SuccessE2ELatency", "average", "milliseconds"), "ms"),
        ("Transactions", azure_name("Microsoft.Storage/storageAccounts", "Transactions", "total", "count"), "short"),
        ("Used capacity", azure_name("Microsoft.Storage/storageAccounts", "UsedCapacity", "average", "bytes"), "bytes"),
    ],
    "storage_files": [
        ("Availability", azure_name("Microsoft.Storage/storageAccounts/fileServices", "Availability", "average", "percent"), "percent"),
        ("File capacity", azure_name("Microsoft.Storage/storageAccounts/fileServices", "FileCapacity", "average", "bytes"), "bytes"),
        ("IOPS utilization", azure_name("Microsoft.Storage/storageAccounts/fileServices", "PercentFileShareIOPSUtilization", "average", "percent"), "percent"),
        ("Bandwidth utilization", azure_name("Microsoft.Storage/storageAccounts/fileServices", "PercentFileShareBandwidthUtilization", "average", "percent"), "percent"),
        ("End-to-end latency", azure_name("Microsoft.Storage/storageAccounts/fileServices", "SuccessE2ELatency", "average", "milliseconds"), "ms"),
        ("Transactions", azure_name("Microsoft.Storage/storageAccounts/fileServices", "Transactions", "total", "count"), "short"),
    ],
    "storage_blobs": [
        ("Availability", azure_name("Microsoft.Storage/storageAccounts/blobServices", "Availability", "average", "percent"), "percent"),
        ("Blob capacity", azure_name("Microsoft.Storage/storageAccounts/blobServices", "BlobCapacity", "average", "bytes"), "bytes"),
        ("Blob count", azure_name("Microsoft.Storage/storageAccounts/blobServices", "BlobCount", "average", "count"), "locale"),
        ("Ingress", azure_name("Microsoft.Storage/storageAccounts/blobServices", "Ingress", "total", "bytes"), "bytes"),
        ("End-to-end latency", azure_name("Microsoft.Storage/storageAccounts/blobServices", "SuccessE2ELatency", "average", "milliseconds"), "ms"),
        ("Transactions", azure_name("Microsoft.Storage/storageAccounts/blobServices", "Transactions", "total", "count"), "short"),
    ],
    "kubernetes": [
        ("Containers observed", "container_memory_usage_bytes", "short"),
        ("Container CPU", "container_cpu_usage", "cores"),
        ("Container memory", "container_memory_usage_bytes", "bytes"),
        ("Filesystem usage", "container_filesystem_usage_bytes", "bytes"),
        ("Pod restarts", "kube_pod_container_status_restarts_total", "short"),
        ("Available replicas", "kube_deployment_status_replicas_available", "short"),
    ],
}


def target(expr, legend="", instant=False, ref="A", fmt="time_series"):
    return {
        "refId": ref,
        "datasource": PROM,
        "expr": expr,
        "legendFormat": legend,
        "instant": instant,
        "range": not instant,
        "format": fmt,
    }


def thresholds(kind):
    if kind == "good_high":
        return {"mode": "absolute", "steps": [{"color": AZURE_RED, "value": None}, {"color": AZURE_AMBER, "value": 99}, {"color": AZURE_GREEN, "value": 99.9}]}
    if kind == "bad_high":
        return {"mode": "absolute", "steps": [{"color": AZURE_GREEN, "value": None}, {"color": AZURE_AMBER, "value": 70}, {"color": AZURE_RED, "value": 90}]}
    if kind == "error":
        return {"mode": "absolute", "steps": [{"color": AZURE_GREEN, "value": None}, {"color": AZURE_AMBER, "value": 1}, {"color": AZURE_RED, "value": 5}]}
    return {"mode": "absolute", "steps": [{"color": AZURE_BLUE, "value": None}]}


def metric_reduce(metric):
    if metric.endswith("_percent"):
        return "avg"
    if metric.startswith("databricks_") and any(
        name in metric
        for name in (
            "_dbus_sliding",
            "_runs_sliding",
            "_sla_miss_sliding",
            "_errors_sliding",
        )
    ):
        return "sum"
    return "sum" if "_total_" in metric or metric.endswith("_total") else "avg"


def metric_pattern(metric):
    if metric.startswith("azure_"):
        return metric.rsplit("_", 2)[0] + "_.+"
    return None


def metric_series(metric, labels=""):
    if metric.startswith("{") and metric.endswith("}"):
        selector = metric[1:-1]
        if labels:
            selector += f",{labels}"
        return f"{{{selector}}}"
    pattern = metric_pattern(metric)
    if pattern:
        selector = f'__name__=~"{pattern}"'
        if labels:
            selector += f",{labels}"
        return f"{{{selector}}}"
    return f"{metric}{{{labels}}}" if labels else metric


def metric_threshold(title):
    name = title.lower()
    if "availability" in name or "available memory" in name or "success" in name:
        return "good_high"
    if any(word in name for word in ("fail", "error", "dead", "throttl", "restart", "not ready")):
        return "error"
    if any(word in name for word in ("cpu", "latency", "utilization", "load", "memory used", "queue")):
        return "bad_high"
    return "blue"


def text_panel(title, content, grid):
    return {"type": "text", "title": title, "gridPos": grid, "options": {"mode": "markdown", "content": content}, "transparent": True}


def stat_panel(title, expr, grid, unit="short", kind="blue", description=""):
    return {
        "type": "stat",
        "title": title,
        "description": description,
        "datasource": PROM,
        "gridPos": grid,
        "targets": [target(expr)],
        "fieldConfig": {"defaults": {"unit": unit, "color": {"mode": "background_solid"}, "thresholds": thresholds(kind)}, "overrides": []},
        "options": {"colorMode": "background", "graphMode": "area", "justifyMode": "auto", "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}, "textMode": "auto", "wideLayout": True},
    }


def timeseries(title, expr, grid, unit="short", legend="{{resource_name}}", description=""):
    return {
        "type": "timeseries",
        "title": title,
        "description": description,
        "datasource": PROM,
        "gridPos": grid,
        "targets": [target(expr, legend)],
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "color": {"mode": "palette-classic"},
                "custom": {"drawStyle": "line", "fillOpacity": 18, "lineInterpolation": "smooth", "lineWidth": 2, "showPoints": "never", "spanNulls": True},
            },
            "overrides": [],
        },
        "options": {"legend": {"calcs": ["lastNotNull", "max", "mean"], "displayMode": "table", "placement": "right", "showLegend": True}, "tooltip": {"mode": "multi", "sort": "desc"}},
    }


def bargauge(title, expr, grid, unit="percent", legend="{{azure_service}}", kind="bad_high"):
    return {
        "type": "bargauge",
        "title": title,
        "datasource": PROM,
        "gridPos": grid,
        "targets": [target(expr, legend, True)],
        "fieldConfig": {"defaults": {"unit": unit, "min": 0, "max": 100, "color": {"mode": "thresholds"}, "thresholds": thresholds(kind)}, "overrides": []},
        "options": {"displayMode": "gradient", "minVizHeight": 14, "minVizWidth": 8, "orientation": "horizontal", "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}, "showUnfilled": True},
    }


def multi_bargauge(title, queries, grid, unit="short"):
    return {
        "type": "bargauge",
        "title": title,
        "datasource": PROM,
        "gridPos": grid,
        "targets": [
            target(expr, legend, True, ref=chr(65 + index))
            for index, (legend, expr) in enumerate(queries)
        ],
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "min": 0,
                "color": {"mode": "continuous-GrYlRd"},
                "thresholds": thresholds("blue"),
            },
            "overrides": [],
        },
        "options": {
            "displayMode": "gradient",
            "minVizHeight": 14,
            "minVizWidth": 8,
            "orientation": "horizontal",
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "showUnfilled": True,
        },
    }


def table_panel(title, expr, grid, value_name="Current value"):
    return {
        "type": "table",
        "title": title,
        "datasource": PROM,
        "gridPos": grid,
        "targets": [target(expr, "", True, fmt="table")],
        "transformations": [{"id": "labelsToFields", "options": {"mode": "columns"}}, {"id": "organize", "options": {"excludeByName": {"Time": True, "__name__": True, "azure_service": True, "cloud_provider": True, "cloud_region": True, "data_mode": True, "deployment_environment_name": True, "environment": True, "job": True, "subscription_id": True}, "renameByName": {"Value": value_name, "cmdbReference": "CMDB_REFERENCE", "resource_group": "Resource group", "resource_name": "Resource", "resource_type": "Azure resource type", "region": "Region", "service_name": "Service name"}}}],
        "fieldConfig": {
            "defaults": {
                "custom": {
                    "align": "auto",
                    "cellOptions": {"type": "auto"},
                    "inspect": False,
                }
            },
            "overrides": [],
        },
        "options": {"cellHeight": "sm", "showHeader": True, "sortBy": [{"desc": False, "displayName": "Resource"}]},
    }


def logs_panel(title, expr, grid):
    return {
        "type": "logs",
        "title": title,
        "datasource": LOKI,
        "gridPos": grid,
        "targets": [{"refId": "A", "datasource": LOKI, "expr": expr, "queryType": "range"}],
        "options": {"dedupStrategy": "none", "enableLogDetails": True, "prettifyLogMessage": True, "showCommonLabels": False, "showLabels": False, "showTime": True, "sortOrder": "Descending", "wrapLogMessage": True},
    }


def loki_timeseries(title, expr, grid, legend="{{job}}"):
    return {
        "type": "timeseries",
        "title": title,
        "datasource": LOKI,
        "gridPos": grid,
        "targets": [{"refId": "A", "datasource": LOKI, "expr": expr, "legendFormat": legend, "queryType": "range"}],
        "fieldConfig": {
            "defaults": {
                "unit": "short",
                "color": {"mode": "palette-classic"},
                "custom": {"drawStyle": "bars", "fillOpacity": 45, "lineWidth": 1, "showPoints": "never", "stacking": {"group": "A", "mode": "normal"}},
            },
            "overrides": [],
        },
        "options": {"legend": {"displayMode": "table", "placement": "right", "showLegend": True}, "tooltip": {"mode": "multi", "sort": "desc"}},
    }


def tempo_timeseries(title, query, grid, legend="{{service.name}}"):
    return {
        "type": "timeseries",
        "title": title,
        "description": "Application traces received through Alloy and correlated by CMDB_REFERENCE.",
        "datasource": TEMPO,
        "gridPos": grid,
        "targets": [
            {
                "refId": "A",
                "datasource": TEMPO,
                "queryType": "traceql",
                "query": query,
                "legendFormat": legend,
                "limit": 20,
            }
        ],
        "fieldConfig": {
            "defaults": {
                "unit": "cps",
                "color": {"mode": "palette-classic"},
                "custom": {
                    "drawStyle": "line",
                    "fillOpacity": 18,
                    "lineInterpolation": "smooth",
                    "lineWidth": 2,
                    "showPoints": "never",
                    "spanNulls": True,
                },
            },
            "overrides": [],
        },
        "options": {
            "legend": {
                "calcs": ["lastNotNull", "max", "mean"],
                "displayMode": "table",
                "placement": "right",
                "showLegend": True,
            },
            "tooltip": {"mode": "multi", "sort": "desc"},
        },
    }


def traces_panel(title, query, grid):
    return {
        "type": "table",
        "title": title,
        "description": "Recent application traces received through Alloy and correlated by CMDB_REFERENCE.",
        "datasource": TEMPO,
        "gridPos": grid,
        "targets": [
            {
                "refId": "A",
                "datasource": TEMPO,
                "queryType": "traceql",
                "query": query,
                "limit": 20,
            }
        ],
    }


def datasource_variable(name, label, plugin_type, default_name, default_uid):
    return {
        "name": name,
        "label": label,
        "type": "datasource",
        "query": plugin_type,
        "regex": "",
        "refresh": 1,
        "multi": False,
        "includeAll": False,
        "options": [],
        "current": {
            "selected": True,
            "text": default_name,
            "value": default_uid,
        },
    }


def datasource_variables():
    return [
        datasource_variable(
            "metrics_datasource",
            "Metrics data source",
            "prometheus",
            "Prometheus",
            "prometheus",
        ),
        datasource_variable(
            "logs_datasource",
            "Logs data source",
            "loki",
            "Loki",
            "loki",
        ),
        datasource_variable(
            "traces_datasource",
            "Traces data source",
            "tempo",
            "Tempo",
            "tempo",
        ),
    ]


def prometheus_label_variable(name, label, metric, source_label, filters=""):
    query = f"label_values({metric_series(metric, filters)}, {source_label})"
    return {
        "name": name,
        "label": label,
        "type": "query",
        "datasource": PROM,
        "definition": query,
        "query": {"query": query, "refId": f"{name}Variable"},
        "includeAll": True,
        "allValue": ".*",
        "multi": True,
        "refresh": 2,
        "current": {"selected": True, "text": ["All"], "value": ["$__all"]},
        "sort": 1,
    }


def standard_prom_variables(metric, include_resource=False, include_namespace=False):
    variables = [
        prometheus_label_variable(
            "cmdb_reference",
            "CMDB_REFERENCE",
            metric,
            PROM_CMDB_LABEL,
        ),
        prometheus_label_variable(
            "service_name",
            "Service name",
            metric,
            PROM_SERVICE_LABEL,
            f'{PROM_CMDB_LABEL}=~"$cmdb_reference"',
        ),
    ]
    if include_resource:
        variables.append(
            prometheus_label_variable(
                "resource",
                "Azure resource",
                metric,
                "resource_name",
                common_prom_filter(),
            )
        )
    if include_namespace:
        variables.append(
            prometheus_label_variable(
                "namespace",
                "Kubernetes namespace",
                metric,
                "k8s_namespace_name",
                common_prom_filter(),
            )
        )
    return variables


def loki_label_variable(name, label, source_label, selector):
    query = f"label_values({selector}, {source_label})"
    return {
        "name": name,
        "label": label,
        "type": "query",
        "datasource": LOKI,
        "definition": query,
        "query": {"query": query, "refId": f"{name}Variable"},
        "includeAll": True,
        "allValue": ".*" if name == "cmdb_reference" else ".+",
        "multi": True,
        "refresh": 2,
        "current": {"selected": True, "text": ["All"], "value": ["$__all"]},
        "sort": 1,
    }


def standard_loki_variables():
    return [
        loki_label_variable(
            "cmdb_reference",
            "CMDB_REFERENCE",
            "cmdbReference",
            '{job=~".+"}',
        ),
        loki_label_variable(
            "service_name",
            "Service name",
            "job",
            '{job=~".+",cmdbReference=~"$cmdb_reference"}',
        ),
    ]


def dashboard(uid, title, panels, tags, variables=None):
    for panel_id, panel in enumerate(panels, 1):
        panel["id"] = panel_id
    return {
        "uid": uid,
        "title": title,
        "description": "Reusable standard dashboard template for Alloy, Azure Monitor and LGTM.",
        "tags": ["standard-template", "alloy", "lgtm"] + tags,
        "timezone": "browser",
        "schemaVersion": 41,
        "editable": True,
        "graphTooltip": 1,
        "refresh": "15s",
        "time": {"from": "now-30m", "to": "now"},
        "timepicker": {"refresh_intervals": ["5s", "15s", "30s", "1m", "5m"]},
        "templating": {"list": datasource_variables() + (variables or [])},
        "annotations": {"list": [{"builtIn": 1, "datasource": {"type": "grafana", "uid": "-- Grafana --"}, "enable": True, "hide": True, "iconColor": AZURE_BLUE, "name": "Annotations & Alerts", "type": "dashboard"}]},
        "panels": panels,
    }


def detail_dashboard(service, config):
    if service == "kubernetes":
        return kubernetes_dashboard(config)

    has_resource = service != "databricks"
    selector = common_prom_filter()
    if has_resource:
        selector += ',resource_name=~"$resource"'
    metrics = METRICS[service]
    panels = [
        text_panel(
            config["title"],
            f"# {config['title']}  \n"
            f"**Azure resource type:** `{config['type']}`  \n"
            "Standard template for metrics collected by Grafana Alloy and stored in Mimir.",
            {"x": 0, "y": 0, "w": 24, "h": 3},
        ),
    ]
    for index, (title, metric, unit) in enumerate(metrics):
        series = metric_series(metric, selector)
        panels.append(
            stat_panel(
                title,
                f"{metric_reduce(metric)}({series})",
                {"x": index * 4, "y": 3, "w": 4, "h": 4},
                unit,
                metric_threshold(title),
                f"Current value from `{metric}`.",
            )
        )
    for index, (title, metric, unit) in enumerate(metrics):
        series = metric_series(metric, selector)
        expression = (
            f"{metric_reduce(metric)} by (resource_name) ({series})"
            if has_resource
            else series
        )
        panels.append(
            timeseries(
                title,
                expression,
                {"x": (index % 3) * 8, "y": 7 + (index // 3) * 8, "w": 8, "h": 8},
                unit,
                "{{resource_name}}" if has_resource else title,
                description=f"Alloy metric: `{metric}`.",
            )
        )
    canonical = metrics[0][1]
    if has_resource:
        panels.append(
            table_panel(
                "Azure resource inventory",
                f"avg by (cmdbReference, service_name, resource_name, resource_group, resource_type, region) ({metric_series(canonical, selector)})",
                {"x": 0, "y": 23, "w": 24, "h": 8},
                metrics[0][0],
            )
        )
    signals_y = 31 if has_resource else 23
    log_selector = correlated_loki_selector()
    trace_selector = correlated_trace_selector()
    panels.extend(
        [
            loki_timeseries(
                "Related log volume",
                f"sum by (job) (count_over_time({log_selector}[$__auto]))",
                {"x": 0, "y": signals_y, "w": 12, "h": 8},
            ),
            tempo_timeseries(
                "Related trace rate by application service",
                f"{trace_selector} | rate() by (resource.service.name)",
                {"x": 12, "y": signals_y, "w": 12, "h": 8},
            ),
            logs_panel(
                "Related logs",
                log_selector,
                {"x": 0, "y": signals_y + 8, "w": 12, "h": 12},
            ),
            traces_panel(
                "Related application traces",
                trace_selector,
                {"x": 12, "y": signals_y + 8, "w": 12, "h": 12},
            ),
        ]
    )
    return dashboard(
        f"azure-{service.replace('_', '-')}",
        f"Standard | Azure | {config['title']}",
        panels,
        ["azure", service],
        standard_prom_variables(canonical, include_resource=has_resource),
    )


def kubernetes_dashboard(config):
    container_selector = common_prom_filter() + ',k8s_namespace_name=~"$namespace"'
    kube_selector = common_prom_filter() + ',namespace=~"$namespace"'
    panels = [
        text_panel(
            config["title"],
            "# AKS / Kubernetes  \n"
            "Standard template for cAdvisor, kube-state-metrics and node-local Kubernetes telemetry.",
            {"x": 0, "y": 0, "w": 24, "h": 3},
        ),
        stat_panel("Containers observed", f"count(container_memory_usage_bytes{{{container_selector}}})", {"x": 0, "y": 3, "w": 4, "h": 4}),
        stat_panel("Container CPU", f"sum(container_cpu_usage{{{container_selector}}})", {"x": 4, "y": 3, "w": 4, "h": 4}, "cores", "bad_high"),
        stat_panel("Container memory", f"sum(container_memory_usage_bytes{{{container_selector}}})", {"x": 8, "y": 3, "w": 4, "h": 4}, "bytes", "bad_high"),
        stat_panel("Filesystem usage", f"sum(container_filesystem_usage_bytes{{{container_selector}}})", {"x": 12, "y": 3, "w": 4, "h": 4}, "bytes", "bad_high"),
        stat_panel("Pod restarts", f"sum(increase(kube_pod_container_status_restarts_total{{{kube_selector}}}[$__range]))", {"x": 16, "y": 3, "w": 4, "h": 4}, "short", "error"),
        stat_panel("Available replicas", f"sum(kube_deployment_status_replicas_available{{{kube_selector}}})", {"x": 20, "y": 3, "w": 4, "h": 4}),
        timeseries("CPU by namespace", f"sum by (k8s_namespace_name) (container_cpu_usage{{{container_selector}}})", {"x": 0, "y": 7, "w": 8, "h": 8}, "cores", "{{k8s_namespace_name}}"),
        timeseries("Memory by namespace", f"sum by (k8s_namespace_name) (container_memory_usage_bytes{{{container_selector}}})", {"x": 8, "y": 7, "w": 8, "h": 8}, "bytes", "{{k8s_namespace_name}}"),
        timeseries("Filesystem by namespace", f"sum by (k8s_namespace_name) (container_filesystem_usage_bytes{{{container_selector}}})", {"x": 16, "y": 7, "w": 8, "h": 8}, "bytes", "{{k8s_namespace_name}}"),
        timeseries("Restart rate", f"sum by (namespace) (rate(kube_pod_container_status_restarts_total{{{kube_selector}}}[5m]))", {"x": 0, "y": 15, "w": 8, "h": 8}, "ops", "{{namespace}}"),
        timeseries("Available replicas", f"sum by (namespace) (kube_deployment_status_replicas_available{{{kube_selector}}})", {"x": 8, "y": 15, "w": 8, "h": 8}, "short", "{{namespace}}"),
        timeseries("Pods not ready", f'sum by (namespace) (kube_pod_status_ready{{{kube_selector},condition="false"}})', {"x": 16, "y": 15, "w": 8, "h": 8}, "short", "{{namespace}}"),
    ]
    log_selector = correlated_loki_selector()
    trace_selector = correlated_trace_selector()
    panels.extend(
        [
            loki_timeseries(
                "Related log volume",
                f"sum by (job) (count_over_time({log_selector}[$__auto]))",
                {"x": 0, "y": 23, "w": 12, "h": 8},
            ),
            tempo_timeseries(
                "Related trace rate by application service",
                f"{trace_selector} | rate() by (resource.service.name)",
                {"x": 12, "y": 23, "w": 12, "h": 8},
            ),
            logs_panel(
                "Related logs",
                log_selector,
                {"x": 0, "y": 31, "w": 12, "h": 12},
            ),
            traces_panel(
                "Related application traces",
                trace_selector,
                {"x": 12, "y": 31, "w": 12, "h": 12},
            ),
        ]
    )
    return dashboard(
        "azure-kubernetes",
        "Standard | AKS / Kubernetes",
        panels,
        ["kubernetes"],
        standard_prom_variables(
            "container_memory_usage_bytes",
            include_namespace=True,
        ),
    )


def coverage_expr(service):
    metric = METRICS[service][0][1]
    series = metric_series(metric, common_prom_filter())
    if service == "kubernetes":
        return f"count(count by (k8s_namespace_name) ({series}))"
    if service == "databricks":
        return f"count({series})"
    return f"count(count by (resource_name) ({series}))"


def coverage_queries():
    return [
        (config["title"], coverage_expr(service))
        for service, config in SERVICES.items()
    ]


def services_reporting_expr():
    checks = [
        f"scalar(count({metric_series(METRICS[service][0][1], common_prom_filter())}) > bool 0)"
        for service in SERVICES
    ]
    return " + ".join(checks)


def resources_reporting_expr():
    return " + ".join(f"scalar({coverage_expr(service)})" for service in SERVICES)


def overview_dashboard():
    links = "\n".join(
        f"- [{config['title']}](/d/azure-{service.replace('_', '-')})"
        for service, config in SERVICES.items()
    )
    links += "\n- [Kubernetes and Platform Logs](/d/kubernetes-platform-logs)"
    panels = [
        text_panel(
            "Standard Dashboard Templates",
            "# Standard Dashboard Templates  \n"
            "**Azure services · AKS · Alloy · LGTM**  \n"
            "Reusable operational views. Panels query production metric names emitted by Alloy exporters.",
            {"x": 0, "y": 0, "w": 18, "h": 4},
        ),
        text_panel("Template navigation", "### Open dashboard\n" + links, {"x": 18, "y": 0, "w": 6, "h": 20}),
        stat_panel("Included templates", f"vector({len(SERVICES) + 1})", {"x": 0, "y": 4, "w": 3, "h": 4}),
        stat_panel("Services reporting", services_reporting_expr(), {"x": 3, "y": 4, "w": 3, "h": 4}),
        stat_panel("Resources reporting", resources_reporting_expr(), {"x": 6, "y": 4, "w": 3, "h": 4}),
        stat_panel("Azure targets up", f'sum(up{{job=~"integrations/azure/.*",{common_prom_filter()}}}) or vector(0)', {"x": 9, "y": 4, "w": 3, "h": 4}, "short", "good_high"),
        stat_panel("Metric points sent/sec", "sum(rate(otelcol_exporter_sent_metric_points_total[5m])) or vector(0)", {"x": 12, "y": 4, "w": 3, "h": 4}, "cps"),
        stat_panel("Metric send failures/sec", "sum(rate(otelcol_exporter_send_failed_metric_points_total[5m])) or vector(0)", {"x": 15, "y": 4, "w": 3, "h": 4}, "cps", "error"),
        multi_bargauge("Resources reporting by template", coverage_queries(), {"x": 0, "y": 8, "w": 18, "h": 12}),
        timeseries("Alloy Azure scrape target health", f'up{{job=~"integrations/azure/.*",{common_prom_filter()}}}', {"x": 0, "y": 20, "w": 12, "h": 8}, "bool", "{{job}}"),
        timeseries("Alloy metric pipeline throughput", "sum(rate(otelcol_receiver_accepted_metric_points_total[5m]))", {"x": 12, "y": 20, "w": 12, "h": 8}, "cps", "accepted points/sec"),
        timeseries("AKS container CPU by namespace", f"sum by (k8s_namespace_name) (container_cpu_usage{{{common_prom_filter()}}})", {"x": 0, "y": 28, "w": 12, "h": 8}, "cores", "{{k8s_namespace_name}}"),
        timeseries("AKS container memory by namespace", f"sum by (k8s_namespace_name) (container_memory_usage_bytes{{{common_prom_filter()}}})", {"x": 12, "y": 28, "w": 12, "h": 8}, "bytes", "{{k8s_namespace_name}}"),
    ]
    log_selector = correlated_loki_selector()
    trace_selector = correlated_trace_selector()
    panels.extend(
        [
            loki_timeseries(
                "Related log volume",
                f"sum by (job) (count_over_time({log_selector}[$__auto]))",
                {"x": 0, "y": 36, "w": 12, "h": 8},
            ),
            tempo_timeseries(
                "Related trace rate by application service",
                f"{trace_selector} | rate() by (resource.service.name)",
                {"x": 12, "y": 36, "w": 12, "h": 8},
            ),
            logs_panel(
                "Recent related logs",
                log_selector,
                {"x": 0, "y": 44, "w": 12, "h": 12},
            ),
            traces_panel(
                "Recent related application traces",
                trace_selector,
                {"x": 12, "y": 44, "w": 12, "h": 12},
            ),
        ]
    )
    return dashboard(
        "standard-dashboard-templates",
        "Standard Dashboard Templates",
        panels,
        ["overview"],
        standard_prom_variables(OVERVIEW_METRIC_SELECTOR),
    )


def logging_dashboard():
    log_selector = common_loki_selector()
    panels = [
        text_panel("Kubernetes and Platform Logs", "# Kubernetes & Platform Logs  \nStandard Loki template for pod, node, cluster-event and AKS control-plane logs.", {"x": 0, "y": 0, "w": 24, "h": 3}),
        stat_panel("Collector log records accepted/sec", "sum(rate(otelcol_receiver_accepted_log_records_total[5m])) or vector(0)", {"x": 0, "y": 3, "w": 8, "h": 4}, "cps"),
        stat_panel("Collector log records refused/sec", "sum(rate(otelcol_receiver_refused_log_records_total[5m])) or vector(0)", {"x": 8, "y": 3, "w": 8, "h": 4}, "cps", "error"),
        stat_panel("Collector log export failures/sec", "sum(rate(otelcol_exporter_send_failed_log_records_total[5m])) or vector(0)", {"x": 16, "y": 3, "w": 8, "h": 4}, "cps", "error"),
        loki_timeseries("Log volume by service", f"sum by (job) (count_over_time({log_selector}[$__auto]))", {"x": 0, "y": 7, "w": 14, "h": 8}),
        loki_timeseries("Errors and failures", f'sum(count_over_time({log_selector} |~ "(?i)(error|failed|critical)" [$__auto]))', {"x": 14, "y": 7, "w": 10, "h": 8}, "errors"),
        logs_panel("All selected logs", log_selector, {"x": 0, "y": 15, "w": 14, "h": 16}),
        logs_panel("Errors, failures and critical events", f'{log_selector} |~ "(?i)(error|failed|critical)"', {"x": 14, "y": 15, "w": 10, "h": 16}),
    ]
    trace_selector = correlated_trace_selector()
    panels.extend(
        [
            tempo_timeseries(
                "Related trace rate by application service",
                f"{trace_selector} | rate() by (resource.service.name)",
                {"x": 0, "y": 31, "w": 12, "h": 8},
            ),
            traces_panel(
                "Related application traces",
                trace_selector,
                {"x": 12, "y": 31, "w": 12, "h": 8},
            ),
        ]
    )
    return dashboard(
        "kubernetes-platform-logs",
        "Standard | Kubernetes and Platform Logs",
        panels,
        ["kubernetes", "logs"],
        standard_loki_variables(),
    )


def request_headers():
    headers = {"Content-Type": "application/json"}
    token = os.getenv("GRAFANA_API_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def ensure_folder():
    body = json.dumps({"uid": FOLDER_UID, "title": FOLDER_TITLE}).encode()
    request = urllib.request.Request(
        GRAFANA + "/api/folders",
        data=body,
        headers=request_headers(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read()
    except urllib.error.HTTPError as exc:
        if exc.code not in (409, 412):
            raise


def write_dashboard(dash):
    path = os.path.join(OUTPUT, dash["uid"] + ".json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(dash, handle, indent=2)


def push(dash):
    body = json.dumps({"dashboard": dash, "overwrite": True, "folderUid": FOLDER_UID}).encode()
    request = urllib.request.Request(
        GRAFANA + "/api/dashboards/db",
        data=body,
        headers=request_headers(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
        print(f"OK   {dash['title']:<45} {GRAFANA}{result['url']}")
    except urllib.error.HTTPError as exc:
        print(f"FAIL {dash['title']}: {exc.code} {exc.read().decode()[:300]}")
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provision", action="store_true", help="also provision dashboards to Grafana")
    args = parser.parse_args()
    os.makedirs(OUTPUT, exist_ok=True)
    dashboards = [overview_dashboard()]
    dashboards.extend(detail_dashboard(service, config) for service, config in SERVICES.items())
    dashboards.append(logging_dashboard())
    for item in dashboards:
        write_dashboard(item)
    print(f"Generated {len(dashboards)} dashboard templates in {OUTPUT}")
    if not args.provision:
        return
    ensure_folder()
    for item in dashboards:
        push(item)
    print(f"Provisioned {len(dashboards)} dashboard templates")


if __name__ == "__main__":
    main()
