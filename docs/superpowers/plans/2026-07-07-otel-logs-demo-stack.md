# OTel Logs Demo Stack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a fully local Docker stack (OTel Collector → Loki → Grafana, plus a dormant Tempo) exercised by three chained sample HTTP apps (Python → Java → .NET) that log via the CloudOps OTel logs libraries, with auto-provisioned Grafana log dashboards.

**Architecture:** One `docker-compose.yml` under a new top-level `demo/` directory defines seven services on a shared network. A `loadgen` drives `python-app`, which calls `java-app`, which calls `dotnet-app`. Each app logs via its CloudOps library configured with `OTEL_BACKEND_EXPORTERS=otel`, exporting OTLP/HTTP to the collector at `:4318/v1/logs`. The collector's logs pipeline exports to Loki; a dormant traces pipeline exports to Tempo. Grafana auto-provisions Loki+Tempo datasources and two log dashboards.

**Tech Stack:** Docker Compose; `otel/opentelemetry-collector-contrib`, `grafana/loki`, `grafana/tempo`, `grafana/grafana`; Python 3.11 (Flask), Java 21 (JDK HttpServer, Maven), .NET 8 (minimal API); the three local CloudOps OTel logs libraries.

## Global Constraints

- All new files live under a new top-level `demo/` directory. **Do not modify anything under `libraries/`.**
- Library versions are all `0.1.0`: Python wheel `cloudops_otel_logs-0.1.0-py3-none-any.whl`, Java `com.cloudops:otel-logs:0.1.0`, .NET `CloudOps.Otel.Logs.0.1.0.nupkg`.
- Apps export OTLP over HTTP/protobuf to the collector at `http://otel-collector:4318` (libraries normalize to `/v1/logs`).
- Each app sets `OTEL_SERVICE_NAME` = `python-app` / `java-app` / `dotnet-app` and `OTEL_BACKEND_EXPORTERS=otel`.
- Loki labels are bounded to `service_name`, `level`/`severity`, `detected_level`. All other fields stay in the log body.
- No persistent volumes for Loki/Tempo (ephemeral demo). No auth beyond Grafana default admin. No app-side trace emission this phase.
- Logger APIs (already built, do not change):
  - **Python:** `from cloudops_otel_logs import logger`; `logger.info(msg, {...})`, `.error(...)`, `.warn(...)`, `.debug(...)`, `logger.export_logs()`. The `logger` singleton is created at import time, so env must be set before import (guaranteed in Docker).
  - **Java:** `CloudOpsLogger log = CloudOpsLogger.initializeLogger();` then `log.info(Object message, Object... optionalParams)`, `.error`, `.warn`, `.debug`, `log.exportLogs()`.
  - **.NET:** `var log = CloudOpsLogger.InitializeLogger();` then `log.Info(object? message, params object?[] optionalParams)`, `.Error`, `.Warn`, `.Debug`, `log.ExportLogs()`.

---

## File Structure

```
demo/
  README.md                          # what it is + exact verification commands
  docker-compose.yml                 # 7 services on network "otel-demo"
  .gitignore                         # ignore built artifacts copied into build contexts
  collector/
    config.yaml                      # OTLP receiver; logs->Loki, traces->Tempo
  loki/
    config.yaml                      # single-binary filesystem Loki
  tempo/
    config.yaml                      # single-binary Tempo (dormant)
  grafana/
    provisioning/
      datasources/datasources.yaml   # Loki + Tempo datasources
      dashboards/dashboards.yaml     # dashboard provider pointing at ../../dashboards
    dashboards/
      logs-overview.json             # "All Apps - Logs Overview"
      per-app-drilldown.json         # "Per-App Drilldown" ($service variable)
  scripts/
    build-libs.sh                    # build wheel + nupkg into demo/artifacts/
  artifacts/                         # (gitignored) built wheel + nupkg land here
  apps/
    python/
      Dockerfile
      requirements.txt
      app.py
    java/
      Dockerfile
      pom.xml
      src/main/java/com/cloudops/demo/App.java
    dotnet/
      Dockerfile
      DotnetApp.csproj
      Program.cs
    loadgen/
      Dockerfile
      loadgen.sh
```

---

## Task 1: Scaffold `demo/` skeleton and library build script

**Files:**
- Create: `demo/.gitignore`
- Create: `demo/scripts/build-libs.sh`
- Create: `demo/README.md` (stub; expanded in Task 11)

**Interfaces:**
- Produces: `demo/artifacts/cloudops_otel_logs-0.1.0-py3-none-any.whl`, `demo/artifacts/CloudOps.Otel.Logs.0.1.0.nupkg` (created by running the script). Java is built from source inside its image, so no artifact here.

- [ ] **Step 1: Create `demo/.gitignore`**

```gitignore
# Built library artifacts copied into build contexts
artifacts/
# Per-language build cruft that may leak into contexts
**/bin/
**/obj/
**/target/
```

- [ ] **Step 2: Create `demo/scripts/build-libs.sh`**

```bash
#!/usr/bin/env bash
# Builds the Python wheel and .NET nupkg into demo/artifacts/.
# Java is built from source inside its Docker image, so it is not built here.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ART="$ROOT/demo/artifacts"
mkdir -p "$ART"

echo "==> Building Python wheel"
python -m pip install --quiet --upgrade build
( cd "$ROOT/libraries/python/logs" && python -m build --wheel --outdir "$ART" )

echo "==> Building .NET nupkg"
( cd "$ROOT/libraries/dotnet/logs" && dotnet pack -c Release -o "$ART" )

echo "==> Artifacts in $ART:"
ls -1 "$ART"
```

- [ ] **Step 3: Create stub `demo/README.md`**

```markdown
# OTel Logs Demo Stack

Local OTel Collector -> Loki -> Grafana pipeline exercised by three chained
sample apps (Python -> Java -> .NET) using the CloudOps OTel logs libraries.

See the full run + verification instructions at the bottom (added in Task 11).
```

- [ ] **Step 4: Run the build script to verify it produces artifacts**

Run: `bash demo/scripts/build-libs.sh`
Expected: ends with a listing that includes `cloudops_otel_logs-0.1.0-py3-none-any.whl` and `CloudOps.Otel.Logs.0.1.0.nupkg`.

- [ ] **Step 5: Commit**

```bash
git add demo/.gitignore demo/scripts/build-libs.sh demo/README.md
git commit -m "demo: scaffold demo dir and library build script"
```

---

## Task 2: OTel Collector config

**Files:**
- Create: `demo/collector/config.yaml`

**Interfaces:**
- Consumes: OTLP/HTTP on `:4318` from apps.
- Produces: pushes logs to `http://loki:3100/otlp` and traces to `http://tempo:4317`. Referenced by `otel-collector` service in Task 9.

- [ ] **Step 1: Create `demo/collector/config.yaml`**

```yaml
receivers:
  otlp:
    protocols:
      http:
        endpoint: 0.0.0.0:4318
      grpc:
        endpoint: 0.0.0.0:4317

processors:
  batch:
  # Promote resource + severity to attributes Loki can label on.
  resource:
    attributes:
      - key: service_name
        from_attribute: service.name
        action: upsert

exporters:
  # Loki accepts OTLP directly on /otlp; hint which attributes become labels.
  otlphttp/loki:
    endpoint: http://loki:3100/otlp
  otlp/tempo:
    endpoint: http://tempo:4317
    tls:
      insecure: true
  debug:
    verbosity: normal

service:
  pipelines:
    logs:
      receivers: [otlp]
      processors: [resource, batch]
      exporters: [otlphttp/loki, debug]
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlp/tempo]
```

- [ ] **Step 2: Validate YAML parses**

Run: `python -c "import yaml,sys; yaml.safe_load(open('demo/collector/config.yaml')); print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add demo/collector/config.yaml
git commit -m "demo: OTel collector config (logs->Loki, traces->Tempo)"
```

---

## Task 3: Loki config

**Files:**
- Create: `demo/loki/config.yaml`

**Interfaces:**
- Consumes: OTLP log push from collector on `:3100`.
- Produces: queryable at `http://loki:3100`. Configures which OTLP resource/log attributes become indexed labels.

- [ ] **Step 1: Create `demo/loki/config.yaml`**

```yaml
auth_enabled: false

server:
  http_listen_port: 3100

common:
  instance_addr: 127.0.0.1
  path_prefix: /tmp/loki
  storage:
    filesystem:
      chunks_directory: /tmp/loki/chunks
      rules_directory: /tmp/loki/rules
  replication_factor: 1
  ring:
    kvstore:
      store: inmemory

schema_config:
  configs:
    - from: 2024-01-01
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h

limits_config:
  # Only these OTLP attributes become indexed labels; everything else -> structured metadata / body.
  otlp_config:
    resource_attributes:
      attributes_config:
        - action: index_label
          attributes:
            - service_name
            - service.name
    log_attributes:
      - action: index_label
        attributes:
          - level
          - severity
          - detected_level
  allow_structured_metadata: true
```

- [ ] **Step 2: Validate YAML parses**

Run: `python -c "import yaml; yaml.safe_load(open('demo/loki/config.yaml')); print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add demo/loki/config.yaml
git commit -m "demo: Loki config with bounded label set"
```

---

## Task 4: Tempo config (dormant)

**Files:**
- Create: `demo/tempo/config.yaml`

**Interfaces:**
- Consumes: OTLP traces from collector on `:4317`.
- Produces: queryable at `http://tempo:3200`. Dormant until app-side tracing is added later.

- [ ] **Step 1: Create `demo/tempo/config.yaml`**

```yaml
server:
  http_listen_port: 3200

distributor:
  receivers:
    otlp:
      protocols:
        grpc:
          endpoint: 0.0.0.0:4317

ingester:
  max_block_duration: 5m

storage:
  trace:
    backend: local
    local:
      path: /var/tempo/blocks
    wal:
      path: /var/tempo/wal
```

- [ ] **Step 2: Validate YAML parses**

Run: `python -c "import yaml; yaml.safe_load(open('demo/tempo/config.yaml')); print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add demo/tempo/config.yaml
git commit -m "demo: Tempo config (dormant traces backend)"
```

---

## Task 5: Grafana provisioning (datasources + dashboard provider)

**Files:**
- Create: `demo/grafana/provisioning/datasources/datasources.yaml`
- Create: `demo/grafana/provisioning/dashboards/dashboards.yaml`

**Interfaces:**
- Produces: a `Loki` datasource (default) at `http://loki:3100` and a `Tempo` datasource at `http://tempo:3200`; a file-based dashboard provider loading JSON from `/var/lib/grafana/dashboards`. Task 9 mounts `demo/grafana/dashboards` there.

- [ ] **Step 1: Create `demo/grafana/provisioning/datasources/datasources.yaml`**

```yaml
apiVersion: 1
datasources:
  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
    isDefault: true
    jsonData:
      # Link log lines to traces once tracing is added later.
      derivedFields:
        - name: TraceID
          matcherRegex: '"trace_id":"(\w+)"'
          url: '$${__value.raw}'
          datasourceUid: tempo
  - name: Tempo
    type: tempo
    uid: tempo
    access: proxy
    url: http://tempo:3200
```

- [ ] **Step 2: Create `demo/grafana/provisioning/dashboards/dashboards.yaml`**

```yaml
apiVersion: 1
providers:
  - name: 'demo-dashboards'
    orgId: 1
    folder: 'OTel Demo'
    type: file
    disableDeletion: false
    editable: true
    options:
      path: /var/lib/grafana/dashboards
      foldersFromFilesStructure: false
```

- [ ] **Step 3: Validate both YAML files parse**

Run: `python -c "import yaml; yaml.safe_load(open('demo/grafana/provisioning/datasources/datasources.yaml')); yaml.safe_load(open('demo/grafana/provisioning/dashboards/dashboards.yaml')); print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add demo/grafana/provisioning
git commit -m "demo: Grafana datasource + dashboard provisioning"
```

---

## Task 6: Grafana dashboards (overview + drilldown)

**Files:**
- Create: `demo/grafana/dashboards/logs-overview.json`
- Create: `demo/grafana/dashboards/per-app-drilldown.json`

**Interfaces:**
- Consumes: the `Loki` datasource by name.
- Produces: two dashboards auto-loaded by the provider from Task 5.

- [ ] **Step 1: Create `demo/grafana/dashboards/logs-overview.json`**

```json
{
  "title": "All Apps - Logs Overview",
  "uid": "logs-overview",
  "schemaVersion": 39,
  "time": { "from": "now-15m", "to": "now" },
  "refresh": "5s",
  "templating": {
    "list": [
      {
        "name": "service",
        "type": "query",
        "datasource": { "type": "loki", "uid": "loki" },
        "query": { "label": "service_name", "stream": "", "type": 1 },
        "includeAll": true,
        "multi": true,
        "current": { "text": "All", "value": "$__all" }
      }
    ]
  },
  "panels": [
    {
      "title": "Log volume by service",
      "type": "timeseries",
      "datasource": { "type": "loki", "uid": "loki" },
      "gridPos": { "h": 8, "w": 12, "x": 0, "y": 0 },
      "options": { "legend": { "displayMode": "table", "placement": "right" } },
      "targets": [
        {
          "expr": "sum by (service_name) (count_over_time({service_name=~\"$service\"}[1m]))",
          "legendFormat": "{{service_name}}"
        }
      ]
    },
    {
      "title": "Log volume by level",
      "type": "timeseries",
      "datasource": { "type": "loki", "uid": "loki" },
      "gridPos": { "h": 8, "w": 12, "x": 12, "y": 0 },
      "targets": [
        {
          "expr": "sum by (detected_level) (count_over_time({service_name=~\"$service\"}[1m]))",
          "legendFormat": "{{detected_level}}"
        }
      ]
    },
    {
      "title": "Errors (last 5m)",
      "type": "stat",
      "datasource": { "type": "loki", "uid": "loki" },
      "gridPos": { "h": 4, "w": 6, "x": 0, "y": 8 },
      "targets": [
        {
          "expr": "sum(count_over_time({service_name=~\"$service\", detected_level=\"error\"}[5m]))"
        }
      ]
    },
    {
      "title": "Live logs (all apps)",
      "type": "logs",
      "datasource": { "type": "loki", "uid": "loki" },
      "gridPos": { "h": 12, "w": 24, "x": 0, "y": 12 },
      "options": { "showTime": true, "wrapLogMessage": true, "sortOrder": "Descending" },
      "targets": [
        { "expr": "{service_name=~\"$service\"}" }
      ]
    }
  ]
}
```

- [ ] **Step 2: Create `demo/grafana/dashboards/per-app-drilldown.json`**

```json
{
  "title": "Per-App Drilldown",
  "uid": "per-app-drilldown",
  "schemaVersion": 39,
  "time": { "from": "now-15m", "to": "now" },
  "refresh": "5s",
  "templating": {
    "list": [
      {
        "name": "service",
        "type": "query",
        "datasource": { "type": "loki", "uid": "loki" },
        "query": { "label": "service_name", "stream": "", "type": 1 },
        "includeAll": false,
        "multi": false,
        "current": { "text": "python-app", "value": "python-app" }
      }
    ]
  },
  "panels": [
    {
      "title": "$service - volume by level",
      "type": "timeseries",
      "datasource": { "type": "loki", "uid": "loki" },
      "gridPos": { "h": 8, "w": 24, "x": 0, "y": 0 },
      "targets": [
        {
          "expr": "sum by (detected_level) (count_over_time({service_name=\"$service\"}[1m]))",
          "legendFormat": "{{detected_level}}"
        }
      ]
    },
    {
      "title": "$service - all logs",
      "type": "logs",
      "datasource": { "type": "loki", "uid": "loki" },
      "gridPos": { "h": 10, "w": 12, "x": 0, "y": 8 },
      "options": { "showTime": true, "wrapLogMessage": true, "sortOrder": "Descending" },
      "targets": [ { "expr": "{service_name=\"$service\"}" } ]
    },
    {
      "title": "$service - errors only",
      "type": "logs",
      "datasource": { "type": "loki", "uid": "loki" },
      "gridPos": { "h": 10, "w": 12, "x": 12, "y": 8 },
      "options": { "showTime": true, "wrapLogMessage": true, "sortOrder": "Descending" },
      "targets": [ { "expr": "{service_name=\"$service\", detected_level=\"error\"}" } ]
    }
  ]
}
```

- [ ] **Step 3: Validate both JSON files parse**

Run: `python -c "import json; json.load(open('demo/grafana/dashboards/logs-overview.json')); json.load(open('demo/grafana/dashboards/per-app-drilldown.json')); print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add demo/grafana/dashboards
git commit -m "demo: Grafana log dashboards (overview + per-app drilldown)"
```

---

## Task 7: Python app (entry of chain)

**Files:**
- Create: `demo/apps/python/app.py`
- Create: `demo/apps/python/requirements.txt`
- Create: `demo/apps/python/Dockerfile`

**Interfaces:**
- Consumes: the local wheel from `demo/artifacts/`.
- Produces: HTTP server on `:8000` with `GET /order`; on each call it logs then calls `http://java-app:8080/process`. Called by `loadgen` (Task 10).

- [ ] **Step 1: Create `demo/apps/python/requirements.txt`**

```text
flask==3.0.3
requests==2.32.3
```

- [ ] **Step 2: Create `demo/apps/python/app.py`**

```python
# Python entry service: logs an order then calls the Java service.
import os
import uuid

import requests
from flask import Flask, jsonify

from cloudops_otel_logs import logger

app = Flask(__name__)
JAVA_URL = os.getenv("JAVA_URL", "http://java-app:8080/process")


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.get("/order")
def order():
    order_id = str(uuid.uuid4())
    logger.info("order received", {"order_id": order_id, "hop": "python"})
    try:
        resp = requests.get(JAVA_URL, params={"order_id": order_id}, timeout=5)
        logger.info("java responded", {"order_id": order_id, "status": resp.status_code})
    except Exception as exc:  # noqa: BLE001 - demo: log and surface any downstream failure
        logger.error("java call failed", {"order_id": order_id, "error": str(exc)})
        logger.export_logs()
        return jsonify(order_id=order_id, ok=False), 502
    logger.export_logs()
    return jsonify(order_id=order_id, ok=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
```

- [ ] **Step 3: Create `demo/apps/python/Dockerfile`**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
# Install the locally-built CloudOps logs wheel first (from build context).
COPY artifacts/cloudops_otel_logs-0.1.0-py3-none-any.whl /tmp/
RUN pip install --no-cache-dir /tmp/cloudops_otel_logs-0.1.0-py3-none-any.whl
COPY apps/python/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY apps/python/app.py .
EXPOSE 8000
CMD ["python", "app.py"]
```

Note: this Dockerfile's build context is `demo/` (set in Task 9's compose file) so both `artifacts/` and `apps/python/` are reachable.

- [ ] **Step 4: Commit**

```bash
git add demo/apps/python
git commit -m "demo: Python entry app (order -> java)"
```

---

## Task 8: Java app (middle hop)

**Files:**
- Create: `demo/apps/java/pom.xml`
- Create: `demo/apps/java/src/main/java/com/cloudops/demo/App.java`
- Create: `demo/apps/java/Dockerfile`

**Interfaces:**
- Consumes: `com.cloudops:otel-logs:0.1.0` (installed from local source inside the image).
- Produces: HTTP server on `:8080` with `GET /process`; logs then calls `http://dotnet-app:8081/finalize`. Called by the Python app.

- [ ] **Step 1: Create `demo/apps/java/pom.xml`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.cloudops.demo</groupId>
  <artifactId>java-app</artifactId>
  <version>1.0.0</version>
  <packaging>jar</packaging>
  <properties>
    <maven.compiler.release>21</maven.compiler.release>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
  </properties>
  <dependencies>
    <dependency>
      <groupId>com.cloudops</groupId>
      <artifactId>otel-logs</artifactId>
      <version>0.1.0</version>
    </dependency>
  </dependencies>
  <build>
    <finalName>java-app</finalName>
    <plugins>
      <plugin>
        <groupId>org.apache.maven.plugins</groupId>
        <artifactId>maven-shade-plugin</artifactId>
        <version>3.6.0</version>
        <executions>
          <execution>
            <phase>package</phase>
            <goals><goal>shade</goal></goals>
            <configuration>
              <transformers>
                <transformer implementation="org.apache.maven.plugins.shade.resource.ManifestResourceTransformer">
                  <mainClass>com.cloudops.demo.App</mainClass>
                </transformer>
              </transformers>
            </configuration>
          </execution>
        </executions>
      </plugin>
    </plugins>
  </build>
</project>
```

- [ ] **Step 2: Create `demo/apps/java/src/main/java/com/cloudops/demo/App.java`**

```java
// Java middle service: logs then calls the .NET service.
package com.cloudops.demo;

import com.cloudops.otel.logs.CloudOpsLogger;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

public final class App {
  private static final CloudOpsLogger LOG = CloudOpsLogger.initializeLogger();
  private static final String DOTNET_URL =
      System.getenv().getOrDefault("DOTNET_URL", "http://dotnet-app:8081/finalize");
  private static final HttpClient CLIENT = HttpClient.newHttpClient();

  public static void main(String[] args) throws IOException {
    HttpServer server = HttpServer.create(new InetSocketAddress(8080), 0);
    server.createContext("/health", ex -> respond(ex, 200, "ok"));
    server.createContext("/process", App::process);
    server.setExecutor(null);
    server.start();
    LOG.info("java-app started", "port", 8080);
  }

  private static void process(com.sun.net.httpserver.HttpExchange ex) throws IOException {
    String query = ex.getRequestURI().getQuery();
    String orderId = query != null && query.startsWith("order_id=") ? query.substring(9) : "unknown";
    LOG.info("processing order", "order_id", orderId, "hop", "java");
    try {
      HttpRequest req = HttpRequest.newBuilder()
          .uri(URI.create(DOTNET_URL + "?order_id=" + orderId)).GET().build();
      HttpResponse<String> resp = CLIENT.send(req, HttpResponse.BodyHandlers.ofString());
      LOG.info("dotnet responded", "order_id", orderId, "status", resp.statusCode());
      respond(ex, 200, "processed");
    } catch (Exception e) {
      LOG.error("dotnet call failed", "order_id", orderId, "error", e.getMessage());
      respond(ex, 502, "downstream error");
    } finally {
      LOG.exportLogs();
    }
  }

  private static void respond(com.sun.net.httpserver.HttpExchange ex, int code, String body)
      throws IOException {
    byte[] bytes = body.getBytes();
    ex.sendResponseHeaders(code, bytes.length);
    try (OutputStream os = ex.getResponseBody()) {
      os.write(bytes);
    }
  }
}
```

- [ ] **Step 3: Create `demo/apps/java/Dockerfile`**

```dockerfile
# Build stage: install the local CloudOps logs library from source, then build the app.
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /build
# Copy and install the CloudOps logs library into the local Maven repo.
COPY libraries/java/logs /libs/logs
RUN mvn -q -f /libs/logs/pom.xml install -DskipTests
# Build the demo app.
COPY demo/apps/java/pom.xml .
COPY demo/apps/java/src ./src
RUN mvn -q package

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /build/target/java-app.jar app.jar
EXPOSE 8080
CMD ["java", "-jar", "app.jar"]
```

Note: this Dockerfile's build context is the **repo root** (set in Task 9) so it can reach both `libraries/java/logs` and `demo/apps/java`.

- [ ] **Step 4: Commit**

```bash
git add demo/apps/java
git commit -m "demo: Java middle app (process -> dotnet)"
```

---

## Task 9: .NET app (tail of chain)

**Files:**
- Create: `demo/apps/dotnet/DotnetApp.csproj`
- Create: `demo/apps/dotnet/Program.cs`
- Create: `demo/apps/dotnet/nuget.config`
- Create: `demo/apps/dotnet/Dockerfile`

**Interfaces:**
- Consumes: `CloudOps.Otel.Logs` `0.1.0` from a local NuGet source (the mounted `artifacts/` folder).
- Produces: HTTP server on `:8081` with `GET /finalize`; logs and returns. End of the chain.

- [ ] **Step 1: Create `demo/apps/dotnet/DotnetApp.csproj`**

```xml
<Project Sdk="Microsoft.NET.Sdk.Web">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="CloudOps.Otel.Logs" Version="0.1.0" />
  </ItemGroup>
</Project>
```

- [ ] **Step 2: Create `demo/apps/dotnet/nuget.config`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <packageSources>
    <clear />
    <add key="nuget.org" value="https://api.nuget.org/v3/index.json" />
    <add key="local" value="/local-nuget" />
  </packageSources>
</configuration>
```

- [ ] **Step 3: Create `demo/apps/dotnet/Program.cs`**

```csharp
// .NET tail service: logs and finalizes the order.
using CloudOps.Otel.Logs;

var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();
var log = CloudOpsLogger.InitializeLogger();

app.MapGet("/health", () => Results.Ok("ok"));

app.MapGet("/finalize", (string? order_id) =>
{
    var id = order_id ?? "unknown";
    log.Info("finalizing order", new Dictionary<string, object?> { ["order_id"] = id, ["hop"] = "dotnet" });
    log.ExportLogs();
    return Results.Ok(new { order_id = id, finalized = true });
});

log.Info("dotnet-app started", new Dictionary<string, object?> { ["port"] = 8081 });
app.Run("http://0.0.0.0:8081");
```

- [ ] **Step 4: Create `demo/apps/dotnet/Dockerfile`**

```dockerfile
# Build stage: restore from a local NuGet source containing the CloudOps nupkg.
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src
# The local NuGet source is the mounted artifacts folder.
COPY artifacts /local-nuget
COPY apps/dotnet/nuget.config .
COPY apps/dotnet/DotnetApp.csproj .
RUN dotnet restore
COPY apps/dotnet/Program.cs .
RUN dotnet publish -c Release -o /out

FROM mcr.microsoft.com/dotnet/aspnet:8.0
WORKDIR /app
COPY --from=build /out .
EXPOSE 8081
CMD ["dotnet", "DotnetApp.dll"]
```

Note: build context is `demo/` (set in Task 9's compose) so `artifacts/` and `apps/dotnet/` are reachable.

- [ ] **Step 5: Commit**

```bash
git add demo/apps/dotnet
git commit -m "demo: .NET tail app (finalize)"
```

---

## Task 10: loadgen + docker-compose.yml (wire everything)

**Files:**
- Create: `demo/apps/loadgen/loadgen.sh`
- Create: `demo/apps/loadgen/Dockerfile`
- Create: `demo/docker-compose.yml`

**Interfaces:**
- Consumes: every service defined above.
- Produces: `docker compose up` brings up all 7 services; loadgen drives `http://python-app:8000/order`.

- [ ] **Step 1: Create `demo/apps/loadgen/loadgen.sh`**

```bash
#!/usr/bin/env sh
# Continuously drives the python entry service; ignores early failures.
TARGET="${TARGET:-http://python-app:8000/order}"
echo "loadgen -> $TARGET"
while true; do
  curl -s -o /dev/null -w "order: %{http_code}\n" "$TARGET" || echo "order: retry"
  sleep 3
done
```

- [ ] **Step 2: Create `demo/apps/loadgen/Dockerfile`**

```dockerfile
FROM curlimages/curl:8.10.1
COPY apps/loadgen/loadgen.sh /loadgen.sh
ENTRYPOINT ["sh", "/loadgen.sh"]
```

- [ ] **Step 3: Create `demo/docker-compose.yml`**

```yaml
name: otel-demo

services:
  loki:
    image: grafana/loki:3.2.0
    command: -config.file=/etc/loki/config.yaml
    volumes:
      - ./loki/config.yaml:/etc/loki/config.yaml:ro
    ports:
      - "3100:3100"

  tempo:
    image: grafana/tempo:2.6.0
    command: -config.file=/etc/tempo/config.yaml
    volumes:
      - ./tempo/config.yaml:/etc/tempo/config.yaml:ro

  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.111.0
    command: ["--config=/etc/collector/config.yaml"]
    volumes:
      - ./collector/config.yaml:/etc/collector/config.yaml:ro
    ports:
      - "4318:4318"
    depends_on:
      - loki
      - tempo

  grafana:
    image: grafana/grafana:11.3.0
    environment:
      GF_AUTH_ANONYMOUS_ENABLED: "true"
      GF_AUTH_ANONYMOUS_ORG_ROLE: "Admin"
      GF_SECURITY_ADMIN_PASSWORD: "admin"
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
      - ./grafana/dashboards:/var/lib/grafana/dashboards:ro
    ports:
      - "3000:3000"
    depends_on:
      - loki
      - tempo

  python-app:
    build:
      context: .
      dockerfile: apps/python/Dockerfile
    environment:
      OTEL_SERVICE_NAME: python-app
      OTEL_BACKEND_EXPORTERS: otel
      OTEL_LOG_LEVEL: info,warn,error,debug
      OTEL_EXPORTER_OTLP_ENDPOINT: http://otel-collector:4318
      JAVA_URL: http://java-app:8080/process
    restart: unless-stopped
    depends_on:
      - otel-collector

  java-app:
    build:
      context: ..
      dockerfile: demo/apps/java/Dockerfile
    environment:
      OTEL_SERVICE_NAME: java-app
      OTEL_BACKEND_EXPORTERS: otel
      OTEL_LOG_LEVEL: info,warn,error,debug
      OTEL_EXPORTER_OTLP_ENDPOINT: http://otel-collector:4318
      DOTNET_URL: http://dotnet-app:8081/finalize
    restart: unless-stopped
    depends_on:
      - otel-collector

  dotnet-app:
    build:
      context: .
      dockerfile: apps/dotnet/Dockerfile
    environment:
      OTEL_SERVICE_NAME: dotnet-app
      OTEL_BACKEND_EXPORTERS: otel
      OTEL_LOG_LEVEL: info,warn,error,debug
      OTEL_EXPORTER_OTLP_ENDPOINT: http://otel-collector:4318
    restart: unless-stopped
    depends_on:
      - otel-collector

  loadgen:
    build:
      context: .
      dockerfile: apps/loadgen/Dockerfile
    environment:
      TARGET: http://python-app:8000/order
    restart: unless-stopped
    depends_on:
      - python-app
```

Note: `java-app` uses build context `..` (repo root) so it can copy `libraries/java/logs`; all other app builds use context `.` (the `demo/` dir).

- [ ] **Step 4: Validate compose file**

Run: `docker compose -f demo/docker-compose.yml config -q && echo ok`
Expected: `ok` (no errors).

- [ ] **Step 5: Commit**

```bash
git add demo/apps/loadgen demo/docker-compose.yml
git commit -m "demo: loadgen + docker-compose wiring all 7 services"
```

---

## Task 11: End-to-end bring-up, verification, and README

**Files:**
- Modify: `demo/README.md` (replace stub with full run + verification steps)

**Interfaces:**
- Consumes: everything above.
- Produces: a verified running stack and documented commands.

- [ ] **Step 1: Build libraries and bring the stack up**

Run:
```bash
bash demo/scripts/build-libs.sh
docker compose -f demo/docker-compose.yml up -d --build
```
Expected: build completes; compose reports all containers started.

- [ ] **Step 2: Verify all 7 services are up**

Run: `docker compose -f demo/docker-compose.yml ps`
Expected: `loki`, `tempo`, `otel-collector`, `grafana`, `python-app`, `java-app`, `dotnet-app`, `loadgen` all `running` (loadgen may show `running` and print order codes).

- [ ] **Step 3: Verify the collector is receiving and exporting logs**

Run: `docker compose -f demo/docker-compose.yml logs otel-collector | grep -iE "LogsExporter|logs|error" | tail -20`
Expected: evidence of log records flowing; no persistent export errors after the first few seconds.

- [ ] **Step 4: Verify all three services appear in Loki (end-to-end proof)**

Wait ~20s for traffic, then run for each service:
```bash
for svc in python-app java-app dotnet-app; do
  echo "== $svc =="
  curl -s -G "http://localhost:3100/loki/api/v1/query_range" \
    --data-urlencode "query={service_name=\"$svc\"}" \
    --data-urlencode "limit=1" | python -c "import sys,json; d=json.load(sys.stdin); print('results:', len(d['data']['result']))"
done
```
Expected: each prints `results:` ≥ 1.

- [ ] **Step 5: Verify error-level logs are labeled**

First force an error path is not required (errors only occur on downstream failure); instead confirm the label exists by querying levels:
```bash
curl -s -G "http://localhost:3100/loki/api/v1/label/detected_level/values" | python -c "import sys,json; print(json.load(sys.stdin)['data'])"
```
Expected: a list including at least `info` (and `error` if any downstream call failed).

- [ ] **Step 6: Verify Grafana is up with the datasource healthy**

Run: `curl -s http://localhost:3000/api/health | python -c "import sys,json; print(json.load(sys.stdin))"`
Expected: JSON with `"database": "ok"`. Then open `http://localhost:3000` → Dashboards → "OTel Demo" folder → "All Apps - Logs Overview" shows all three services' streams.

- [ ] **Step 7: Replace `demo/README.md` with full instructions**

```markdown
# OTel Logs Demo Stack

Local **OTel Collector → Loki → Grafana** pipeline (plus a dormant **Tempo**
traces backend) exercised by three chained sample apps that log via the CloudOps
OTel logs libraries:

```
loadgen → python-app → java-app → dotnet-app
              └──────────── OTLP/HTTP logs ────────────→ collector → Loki → Grafana
```

## Prerequisites

- Docker Desktop
- Python + .NET SDK on the host (only to build the library artifacts)

## Run

```bash
# 1. Build the Python wheel and .NET nupkg into demo/artifacts/
bash demo/scripts/build-libs.sh

# 2. Build images and start everything
docker compose -f demo/docker-compose.yml up -d --build
```

Open Grafana at http://localhost:3000 (anonymous admin is enabled).
Dashboards live in the **OTel Demo** folder:
- **All Apps — Logs Overview**
- **Per-App Drilldown** (pick an app from the `service` dropdown)

## Verify from the command line

```bash
# All services present in Loki:
for svc in python-app java-app dotnet-app; do
  curl -s -G "http://localhost:3100/loki/api/v1/query_range" \
    --data-urlencode "query={service_name=\"$svc\"}" --data-urlencode "limit=1" \
    | python -c "import sys,json; d=json.load(sys.stdin); print('$svc results:', len(d['data']['result']))"
done

# Grafana health:
curl -s http://localhost:3000/api/health
```

## Stop

```bash
docker compose -f demo/docker-compose.yml down          # stop
docker compose -f demo/docker-compose.yml down -v       # stop + wipe data
```

## Tracing (future)

Tempo and the collector's traces pipeline are already running but idle. Adding
app-side spans later needs no infra change — logs already carry `trace_id` when a
trace context exists, and the Loki datasource is pre-wired to link to Tempo.
```

- [ ] **Step 8: Commit**

```bash
git add demo/README.md
git commit -m "demo: full README with run + verification steps"
```

---

## Notes for the implementer

- **Build order matters:** `demo/scripts/build-libs.sh` MUST run before `docker compose ... up --build`, because the Python and .NET Dockerfiles copy `artifacts/`. If `artifacts/` is empty the builds fail with "file not found".
- **Java is the exception:** it builds the library from source inside its image (context = repo root), so it does not need `artifacts/`.
- **If Loki labels don't appear:** the collector `debug` exporter output (`docker compose logs otel-collector`) shows the exact attributes on each record; adjust `demo/loki/config.yaml` `otlp_config` to match the real attribute keys the libraries emit (`service.name`, `severity`/`level`).
- **Windows note:** run the `bash` script via Git Bash; the `docker compose` commands work from PowerShell too.
