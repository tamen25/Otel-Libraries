#!/usr/bin/env python3
"""Generate isolated validation data for standard dashboard templates."""

import json
import math
import os
import time
import urllib.parse
import urllib.request

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://lgtm.lgtm.svc:9090")
OTLP_HTTP_URL = os.getenv("OTLP_HTTP_URL", "http://lgtm.lgtm.svc:4318")
INTERVAL = int(os.getenv("INTERVAL_SECONDS", "15"))
SUBSCRIPTION = "template-validation-subscription"
RESOURCE_GROUP = "rg-template-validation"
REGION = "northeurope"
START_NS = str(time.time_ns())


SERVICES = {
    "virtual_machines": {
        "title": "Virtual Machines",
        "type": "Microsoft.Compute/virtualMachines",
        "resources": ["vm-app-01", "vm-worker-02"],
    },
    "sql_database": {
        "title": "SQL Database",
        "type": "Microsoft.Sql/servers/databases",
        "resources": ["sqldb-orders", "sqldb-customer"],
    },
    "sql_managed_instance": {
        "title": "SQL Managed Instance",
        "type": "Microsoft.Sql/managedInstances",
        "resources": ["sqlmi-core-01"],
    },
    "service_bus": {
        "title": "Service Bus",
        "type": "Microsoft.ServiceBus/Namespaces",
        "resources": ["sb-orders-prod", "sb-notifications-prod"],
    },
    "event_hubs": {
        "title": "Event Hubs",
        "type": "Microsoft.EventHub/Namespaces",
        "resources": ["evh-telemetry-prod", "evh-audit-prod"],
    },
    "event_grid": {
        "title": "Event Grid",
        "type": "Microsoft.EventGrid/topics",
        "resources": ["evg-domain-events", "evg-integration-events"],
    },
    "logic_apps": {
        "title": "Logic Apps Consumption",
        "type": "Microsoft.Logic/Workflows",
        "resources": ["la-order-orchestration", "la-customer-sync"],
    },
    "logic_apps_standard": {
        "title": "Logic Apps Standard",
        "type": "Microsoft.Web/sites",
        "resources": ["las-integration-prod"],
    },
    "redis_cache": {
        "title": "Azure Cache for Redis",
        "type": "Microsoft.Cache/redis",
        "resources": ["redis-session-prod", "redis-catalog-prod"],
    },
    "cosmos_db": {
        "title": "Cosmos DB",
        "type": "Microsoft.DocumentDB/DatabaseAccounts",
        "resources": ["cosmos-orders-prod", "cosmos-profile-prod"],
    },
    "databricks": {
        "title": "Azure Databricks",
        "type": "Microsoft.Databricks/workspaces",
        "resources": ["dbw-analytics-prod"],
    },
    "storage_accounts": {
        "title": "Storage Accounts",
        "type": "Microsoft.Storage/storageAccounts",
        "resources": ["stappdata01", "stshareddata01"],
    },
    "storage_files": {
        "title": "Azure Files",
        "type": "Microsoft.Storage/storageAccounts/fileServices",
        "resources": ["stshareddata01/default"],
    },
    "storage_blobs": {
        "title": "Blob Storage",
        "type": "Microsoft.Storage/storageAccounts/blobServices",
        "resources": ["stappdata01/default", "stshareddata01/default"],
    },
    "kubernetes": {
        "title": "AKS / Kubernetes",
        "type": "Microsoft.ContainerService/managedClusters",
        "resources": ["aks-template-validation"],
    },
}


def query(expr, default):
    try:
        url = PROMETHEUS_URL + "/api/v1/query?query=" + urllib.parse.quote(expr)
        with urllib.request.urlopen(url, timeout=5) as response:
            result = json.load(response)["data"]["result"]
        return float(result[0]["value"][1]) if result else default
    except Exception:
        return default


def live_baseline():
    return {
        "cpu": max(1.0, query("avg(container_cpu_usage) * 100", 18.0)),
        "memory": max(1.0, query("sum(container_memory_usage_bytes)", 4_000_000_000)),
        "rps": max(0.5, query("sum(rate(traces_spanmetrics_calls_total[5m]))", 8.0)),
        "latency": max(
            20.0,
            query(
                "histogram_quantile(0.95,sum by (le)(rate(traces_spanmetrics_latency_bucket[5m]))) * 1000",
                180.0,
            ),
        ),
        "spans": max(0.5, query("sum(rate(otelcol_receiver_accepted_spans_total[5m]))", 10.0)),
        "containers": max(
            1.0,
            query("count(container_memory_usage_bytes)", 24.0),
        ),
    }


def wave(seed, period=300, amplitude=1.0):
    return math.sin((time.time() + seed * 37) * 2 * math.pi / period) * amplitude


def point(name, value, attributes, unit=""):
    metric = {
        "name": name,
        "gauge": {
            "dataPoints": [
                {
                    "attributes": [
                        {"key": key, "value": {"stringValue": str(val)}}
                        for key, val in attributes.items()
                    ],
                    "timeUnixNano": str(time.time_ns()),
                    "asDouble": round(float(value), 4),
                }
            ]
        },
    }
    if unit:
        metric["unit"] = unit
    return metric


def azure_name(resource_type, metric, aggregation, unit):
    normalized_type = resource_type.lower().replace("/", "_").replace(".", "_")
    normalized_metric = (
        metric.lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("%", "percent")
    )
    return f"azure_{normalized_type}_{normalized_metric}_{aggregation}_{unit}"


def specific_metrics(service, common, base, index):
    saturation = common["saturation"]
    rps = common["rps"]
    latency = common["latency"]
    errors = common["errors"]
    availability = common["availability"]
    w = wave(index + 11, 180)
    names = {}

    if service == "virtual_machines":
        names = {
            azure_name("Microsoft.Compute/virtualMachines", "Percentage CPU", "average", "percent"): saturation,
            azure_name("Microsoft.Compute/virtualMachines", "Available Memory Percentage", "average", "percent"): 100 - saturation * 0.58,
            azure_name("Microsoft.Compute/virtualMachines", "Data Disk Latency", "average", "milliseconds"): latency * 0.16,
            azure_name("Microsoft.Compute/virtualMachines", "Data Disk Queue Depth", "average", "count"): max(0, saturation / 18 + w),
            azure_name("Microsoft.Compute/virtualMachines", "Disk Read Bytes", "total", "bytes"): rps * 700_000,
            azure_name("Microsoft.Compute/virtualMachines", "Disk Write Bytes", "total", "bytes"): rps * 420_000,
        }
    elif service == "sql_database":
        names = {
            azure_name("Microsoft.Sql/servers/databases", "cpu_percent", "average", "percent"): saturation * 0.84,
            azure_name("Microsoft.Sql/servers/databases", "dtu_consumption_percent", "average", "percent"): saturation,
            azure_name("Microsoft.Sql/servers/databases", "storage_percent", "average", "percent"): 61 + w * 4,
            azure_name("Microsoft.Sql/servers/databases", "deadlock", "total", "count"): max(0, errors * 0.2),
            azure_name("Microsoft.Sql/servers/databases", "connection_failed", "total", "count"): max(0, errors * rps * 0.08),
            azure_name("Microsoft.Sql/servers/databases", "availability", "average", "percent"): availability,
        }
    elif service == "sql_managed_instance":
        names = {
            azure_name("Microsoft.Sql/managedInstances", "avg_cpu_percent", "average", "percent"): saturation * 0.78,
            azure_name("Microsoft.Sql/managedInstances", "storage_space_used_mb", "average", "megabytes"): 182_000 + w * 8_000,
            azure_name("Microsoft.Sql/managedInstances", "reserved_storage_mb", "average", "megabytes"): 512_000,
            azure_name("Microsoft.Sql/managedInstances", "io_bytes_read", "total", "bytes"): rps * 1_900_000,
            azure_name("Microsoft.Sql/managedInstances", "io_bytes_written", "total", "bytes"): rps * 1_100_000,
            azure_name("Microsoft.Sql/managedInstances", "io_requests", "total", "count"): rps * 42,
        }
    elif service == "service_bus":
        names = {
            azure_name("Microsoft.ServiceBus/Namespaces", "ActiveMessages", "average", "count"): rps * 18 + 30,
            azure_name("Microsoft.ServiceBus/Namespaces", "DeadletteredMessages", "average", "count"): errors * 2,
            azure_name("Microsoft.ServiceBus/Namespaces", "IncomingMessages", "total", "count"): rps * 60,
            azure_name("Microsoft.ServiceBus/Namespaces", "OutgoingMessages", "total", "count"): rps * 58,
            azure_name("Microsoft.ServiceBus/Namespaces", "NamespaceCpuUsage", "average", "percent"): saturation * 0.5,
            azure_name("Microsoft.ServiceBus/Namespaces", "ServerSendLatency", "average", "milliseconds"): latency * 0.28,
        }
    elif service == "event_hubs":
        names = {
            azure_name("Microsoft.EventHub/Namespaces", "IncomingMessages", "total", "count"): rps * 160,
            azure_name("Microsoft.EventHub/Namespaces", "OutgoingMessages", "total", "count"): rps * 151,
            azure_name("Microsoft.EventHub/Namespaces", "IncomingBytes", "total", "bytes"): rps * 1_800_000,
            azure_name("Microsoft.EventHub/Namespaces", "OutgoingBytes", "total", "bytes"): rps * 1_650_000,
            azure_name("Microsoft.EventHub/Namespaces", "ThrottledRequests", "total", "count"): max(0, saturation - 75) * 0.2,
            azure_name("Microsoft.EventHub/Namespaces", "ServerErrors", "total", "count"): errors * 0.4,
        }
    elif service == "event_grid":
        names = {
            azure_name("Microsoft.EventGrid/topics", "PublishSuccessCount", "total", "count"): rps * 75,
            azure_name("Microsoft.EventGrid/topics", "PublishFailCount", "total", "count"): errors * rps * 0.2,
            azure_name("Microsoft.EventGrid/topics", "DeadLetteredCount", "total", "count"): errors * 0.5,
            azure_name("Microsoft.EventGrid/topics", "DeliverySuccessCount", "total", "count"): rps * 72,
            azure_name("Microsoft.EventGrid/topics", "PublishSuccessLatencyInMs", "average", "milliseconds"): latency * 0.18,
            azure_name("Microsoft.EventGrid/topics", "DestinationProcessingDurationInMs", "average", "milliseconds"): latency * 0.7,
        }
    elif service == "logic_apps":
        names = {
            azure_name("Microsoft.Logic/Workflows", "RunsStarted", "total", "count"): rps * 8,
            azure_name("Microsoft.Logic/Workflows", "RunsSucceeded", "total", "count"): rps * 8 * (1 - errors / 100),
            azure_name("Microsoft.Logic/Workflows", "RunsFailed", "total", "count"): rps * 8 * errors / 100,
            azure_name("Microsoft.Logic/Workflows", "RunFailurePercentage", "average", "percent"): errors,
            azure_name("Microsoft.Logic/Workflows", "RunLatency", "average", "milliseconds"): latency * 3.2,
            azure_name("Microsoft.Logic/Workflows", "RunThrottledEvents", "total", "count"): max(0, saturation - 78) * 0.12,
        }
    elif service == "logic_apps_standard":
        names = {
            azure_name("Microsoft.Web/sites", "CpuTime", "average", "percent"): saturation * 0.62,
            azure_name("Microsoft.Web/sites", "MemoryWorkingSet", "average", "bytes"): base["memory"] * 0.08,
            azure_name("Microsoft.Web/sites", "HttpResponseTime", "average", "milliseconds"): latency * 1.4,
            azure_name("Microsoft.Web/sites", "Http5xx", "total", "count"): errors * rps * 0.1,
            azure_name("Microsoft.Web/sites", "WorkflowRunsFailureRate", "average", "percent"): errors,
            azure_name("Microsoft.Web/sites", "WorkflowJobExecutionDuration", "average", "milliseconds"): latency * 4.0,
        }
    elif service == "redis_cache":
        hit_ratio = 96 + w * 2
        names = {
            azure_name("Microsoft.Cache/redis", "alloperationsPerSecond", "average", "count"): rps * 125,
            azure_name("Microsoft.Cache/redis", "allserverLoad", "average", "percent"): saturation * 0.72,
            azure_name("Microsoft.Cache/redis", "allconnectedclients", "average", "count"): 42 + rps * 2,
            azure_name("Microsoft.Cache/redis", "allusedmemorypercentage", "average", "percent"): 58 + w * 6,
            azure_name("Microsoft.Cache/redis", "allcachehits", "total", "count"): rps * 125 * hit_ratio / 100,
            azure_name("Microsoft.Cache/redis", "allcachemisses", "total", "count"): rps * 125 * (100 - hit_ratio) / 100,
        }
    elif service == "cosmos_db":
        names = {
            azure_name("Microsoft.DocumentDB/DatabaseAccounts", "NormalizedRUConsumption", "average", "percent"): saturation * 0.9,
            azure_name("Microsoft.DocumentDB/DatabaseAccounts", "ProvisionedThroughput", "average", "count"): 12_000,
            azure_name("Microsoft.DocumentDB/DatabaseAccounts", "ServerSideLatencyDirect", "average", "milliseconds"): latency * 0.09,
            azure_name("Microsoft.DocumentDB/DatabaseAccounts", "ServiceAvailability", "average", "percent"): availability,
            azure_name("Microsoft.DocumentDB/DatabaseAccounts", "TotalRequests", "total", "count"): rps * 90,
            azure_name("Microsoft.DocumentDB/DatabaseAccounts", "TotalRequestUnits", "total", "count"): rps * 380,
        }
    elif service == "databricks":
        names = {
            "databricks_exporter_up": 1,
            "databricks_billing_dbus_sliding": 640 + saturation * 4.2,
            "databricks_job_runs_sliding": 48 + w * 8,
            "databricks_job_sla_miss_sliding": errors * 0.25,
            "databricks_query_errors_sliding": errors * 1.8,
            "databricks_pipeline_freshness_lag_seconds_sliding": latency * 2.4,
        }
    elif service == "storage_accounts":
        names = {
            azure_name("Microsoft.Storage/storageAccounts", "Availability", "average", "percent"): availability,
            azure_name("Microsoft.Storage/storageAccounts", "Ingress", "total", "bytes"): rps * 2_400_000,
            azure_name("Microsoft.Storage/storageAccounts", "Egress", "total", "bytes"): rps * 1_650_000,
            azure_name("Microsoft.Storage/storageAccounts", "SuccessE2ELatency", "average", "milliseconds"): latency * 0.2,
            azure_name("Microsoft.Storage/storageAccounts", "Transactions", "total", "count"): rps * 110,
            azure_name("Microsoft.Storage/storageAccounts", "UsedCapacity", "average", "bytes"): 7.8e11 + w * 8e10,
        }
    elif service == "storage_files":
        names = {
            azure_name("Microsoft.Storage/storageAccounts/fileServices", "Availability", "average", "percent"): availability,
            azure_name("Microsoft.Storage/storageAccounts/fileServices", "FileCapacity", "average", "bytes"): 2.8e11 + w * 2e10,
            azure_name("Microsoft.Storage/storageAccounts/fileServices", "PercentFileShareIOPSUtilization", "average", "percent"): saturation * 0.74,
            azure_name("Microsoft.Storage/storageAccounts/fileServices", "PercentFileShareBandwidthUtilization", "average", "percent"): saturation * 0.61,
            azure_name("Microsoft.Storage/storageAccounts/fileServices", "SuccessE2ELatency", "average", "milliseconds"): latency * 0.32,
            azure_name("Microsoft.Storage/storageAccounts/fileServices", "Transactions", "total", "count"): rps * 42,
        }
    elif service == "storage_blobs":
        names = {
            azure_name("Microsoft.Storage/storageAccounts/blobServices", "Availability", "average", "percent"): availability,
            azure_name("Microsoft.Storage/storageAccounts/blobServices", "BlobCapacity", "average", "bytes"): 5.2e11 + w * 4e10,
            azure_name("Microsoft.Storage/storageAccounts/blobServices", "BlobCount", "average", "count"): 1_820_000 + w * 80_000,
            azure_name("Microsoft.Storage/storageAccounts/blobServices", "Ingress", "total", "bytes"): rps * 3_200_000,
            azure_name("Microsoft.Storage/storageAccounts/blobServices", "SuccessE2ELatency", "average", "milliseconds"): latency * 0.24,
            azure_name("Microsoft.Storage/storageAccounts/blobServices", "Transactions", "total", "count"): rps * 88,
        }
    elif service == "kubernetes":
        names = {
            "container_cpu_usage": base["cpu"] / 100,
            "container_memory_usage_bytes": base["memory"],
            "container_filesystem_usage_bytes": base["memory"] * 2.4,
            "kube_pod_container_status_restarts_total": max(0, errors - 1),
            "kube_deployment_status_replicas_available": max(1, round(base["containers"] / 6)),
            "kube_pod_status_ready": 1 if errors > 5 else 0,
        }
    return names


def resource_metrics(base):
    result = []
    for service_index, (service, config) in enumerate(SERVICES.items()):
        for resource_index, resource in enumerate(config["resources"]):
            seed = service_index * 5 + resource_index
            factor = 0.75 + (service_index % 5) * 0.12 + resource_index * 0.09
            saturation = min(96, max(5, base["cpu"] * 3.4 * factor + 28 + wave(seed, 240, 12)))
            rps = max(0.1, base["rps"] * factor * 4 + 6 + wave(seed, 150, 3))
            latency = max(5, base["latency"] * (0.35 + factor * 0.24) + wave(seed, 210, 18))
            errors = min(12, max(0.02, 0.18 + abs(wave(seed, 420, 1.8)) + max(0, saturation - 80) * 0.12))
            availability = max(97.5, 100 - errors * 0.08)
            common = {
                "saturation": saturation,
                "rps": rps,
                "latency": latency,
                "errors": errors,
                "availability": availability,
            }
            attrs = {
                "subscription_id": SUBSCRIPTION,
                "resource_group": RESOURCE_GROUP,
                "resource_name": resource,
                "resource_type": config["type"],
                "region": REGION,
                "azure_service": service,
                "cmdbReference": f"CMDB-{service_index + 1:03d}",
                "environment": "template-validation",
                "data_mode": "template-validation",
            }
            if service == "kubernetes":
                attrs.update(
                    {
                        "k8s_namespace_name": "template-validation",
                        "namespace": "template-validation",
                        "condition": "false",
                    }
                )
            metrics = []
            if service != "kubernetes":
                scrape_attrs = dict(attrs)
                scrape_attrs.update(
                    {
                        "job": f"integrations/azure/{service}",
                        "instance": resource,
                    }
                )
                metrics.append(point("up", 1, scrape_attrs))
            for name, value in specific_metrics(service, common, base, seed).items():
                metrics.append(point(name, value, attrs))
            result.append(
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": f"integrations/azure/{service}"}},
                            {"key": "cloud.provider", "value": {"stringValue": "azure"}},
                            {"key": "cloud.region", "value": {"stringValue": REGION}},
                            {"key": "deployment.environment.name", "value": {"stringValue": "template-validation"}},
                        ]
                    },
                    "scopeMetrics": [
                        {
                            "scope": {"name": "dashboard.template.validation", "version": "1.0.0"},
                            "metrics": metrics,
                        }
                    ],
                }
            )
    return result


def post(path, payload):
    request = urllib.request.Request(
        OTLP_HTTP_URL + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        response.read()


def send_logs(base):
    now = time.time_ns()
    logs = []
    for index, (service, config) in enumerate(SERVICES.items()):
        if index % 3 != int(time.time() / INTERVAL) % 3:
            continue
        severity = "WARN" if (index + int(time.time() / 60)) % 11 == 0 else "INFO"
        severity_number = 13 if severity == "WARN" else 9
        body = {
            "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "category": "AzureResourceHealth" if severity == "WARN" else "Operational",
            "level": severity,
            "azure_service": service,
            "resource_type": config["type"],
            "resource_name": config["resources"][0],
            "region": REGION,
            "message": (
                "Transient validation saturation detected; automatic recovery active"
                if severity == "WARN"
                else f"{config['title']} telemetry collection healthy"
            ),
            "live_stack_rps": round(base["rps"], 2),
        }
        logs.append(
            {
                "timeUnixNano": str(now + index),
                "severityNumber": severity_number,
                "severityText": severity,
                "body": {"stringValue": json.dumps(body, separators=(",", ":"))},
                "attributes": [
                    {"key": "azure_service", "value": {"stringValue": service}},
                    {"key": "resource_name", "value": {"stringValue": config["resources"][0]}},
                    {"key": "data_mode", "value": {"stringValue": "template-validation"}},
                ],
            }
        )
    payload = {
        "resourceLogs": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "azure-dashboard-template-test-data"}},
                        {"key": "cloud.provider", "value": {"stringValue": "azure"}},
                    ]
                },
                "scopeLogs": [
                    {
                        "scope": {"name": "dashboard.template.validation"},
                        "logRecords": logs,
                    }
                ],
            }
        ]
    }
    post("/v1/logs", payload)


def main():
    print("Dashboard template validation generator starting", flush=True)
    while True:
        try:
            base = live_baseline()
            post("/v1/metrics", {"resourceMetrics": resource_metrics(base)})
            send_logs(base)
            print("sent", json.dumps(base, sort_keys=True), flush=True)
        except Exception as exc:
            print("send failed:", repr(exc), flush=True)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
