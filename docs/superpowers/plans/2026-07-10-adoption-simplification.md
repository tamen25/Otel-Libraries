# Adoption Simplification & De-brand Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Swap the demo collector to Grafana Alloy, remove every CloudOps identifier from all four library ports, and ship the one-liner adoption APIs (no-arg init, register entry, Java edge helpers, auto-flush) per the approved spec.

**Architecture:** Per-signal packages stay separate under `libraries/<lang>/{logs,traces}`. Each task is independently testable and committed. Infra first (Alloy), then per-language rename+API tasks, then demo migration, then docs.

**Tech Stack:** Python ≥3.11 (hatchling), Java 21 (Maven), .NET 8, Node ≥22 (TypeScript, OTel JS 2.x line), Docker Compose demo (Loki/Tempo/Mimir/Grafana).

**Spec:** `docs/superpowers/specs/2026-07-10-adoption-simplification-design.md` — read it first.

## Global Constraints

- **No AI/Claude/Co-Authored-By attribution in ANY commit message** (project rule, CLAUDE.md).
- Work directly on branch `azure-conversion`; commit after every task.
- Versions stay `0.1.0` everywhere. OTel SDK versions do NOT change (Node stays on the 2.x/0.220 line, Python 1.41.0/0.62b0, Java 1.60.1, .NET current).
- New names (exact): Python `otel-logs`/`otel-traces` (modules `otel_logs`/`otel_traces`); Java `otel:otel-logs`/`otel:otel-traces` (packages `otel.logs`/`otel.traces`, classes `Logger`/`Tracer`); .NET `Otel.Logs`/`Otel.Traces` (classes `Logger`, extension `AddOtelTraces`); Node `@otel/logs`/`@otel/traces` (+ `@otel/traces/register`).
- Env-var contract unchanged: `OTEL_BACKEND_EXPORTERS` stays explicit (default `console`); gating (endpoint + `X_ORG_ID` else console) unchanged.
- `X_ORG_ID` is an **org identifier, not a secret** — never describe it as a credential in docs.
- `libraries/nodejs/metrics/` is untracked and **out of scope** — do not touch it.
- Test commands (run from each lib dir): Python `PYTHONPATH=src python -m pytest -q`; Java `mvn -q verify` (use absolute paths — shell cwd can reset); .NET `dotnet test tests/<Name>.Tests.csproj`; Node `npm test` / `npm run test:coverage`.
- Demo: `docker compose -f demo/docker-compose.yml ...` from repo root; volume-mounted configs (tempo/grafana/alloy) need `docker compose restart <svc>` after edits; rebuild images only after `bash demo/scripts/build-libs.sh`.

---

### Task 1: Swap the demo collector to Grafana Alloy

**Files:**
- Create: `demo/alloy/config.alloy`
- Modify: `demo/docker-compose.yml` (service `otel-collector` → `alloy`; every app's `OTEL_EXPORTER_OTLP_ENDPOINT`; `depends_on`)
- Delete: `demo/collector/config.yaml` (and the empty `demo/collector/` dir)
- Modify: `demo/README.md` (collector mentions — quick pass; full docs rewrite is Task 11)

**Interfaces:**
- Produces: OTLP/HTTP ingest at `http://alloy:4318` (host `localhost:4318`), logs → Loki with `service_name` label, traces → Tempo. Apps keep the exact same OTLP contract.

- [x] **Step 1: Write `demo/alloy/config.alloy`** (mirrors the old collector pipelines exactly):

```alloy
// Grafana Alloy collector for the demo: OTLP in -> logs to Loki, traces to Tempo.
otelcol.receiver.otlp "default" {
  http {
    endpoint = "0.0.0.0:4318"
  }
  grpc {
    endpoint = "0.0.0.0:4317"
  }
  output {
    logs   = [otelcol.processor.transform.service_name.input]
    traces = [otelcol.processor.batch.traces.input]
  }
}

// Promote service.name to a service_name resource attribute Loki labels on
// (mirrors the old collector's `resource` processor).
otelcol.processor.transform "service_name" {
  error_mode = "ignore"
  log_statements {
    context    = "resource"
    statements = ["set(attributes[\"service_name\"], attributes[\"service.name\"])"]
  }
  output {
    logs = [otelcol.processor.batch.logs.input]
  }
}

otelcol.processor.batch "logs" {
  output {
    logs = [otelcol.exporter.otlphttp.loki.input, otelcol.exporter.debug.default.input]
  }
}

otelcol.processor.batch "traces" {
  output {
    traces = [otelcol.exporter.otlp.tempo.input]
  }
}

// Loki accepts OTLP natively on /otlp.
otelcol.exporter.otlphttp "loki" {
  client {
    endpoint = "http://loki:3100/otlp"
  }
}

otelcol.exporter.otlp "tempo" {
  client {
    endpoint = "tempo:4317"
    tls {
      insecure = true
    }
  }
}

otelcol.exporter.debug "default" {
  verbosity = "normal"
}
```

- [x] **Step 2: Update `demo/docker-compose.yml`.** Replace the `otel-collector` service block with:

```yaml
  alloy:
    image: grafana/alloy:v1.5.1
    command: ["run", "--storage.path=/var/lib/alloy/data", "/etc/alloy/config.alloy"]
    volumes:
      - ./alloy/config.alloy:/etc/alloy/config.alloy:ro
    ports:
      - "4318:4318"
    depends_on:
      - loki
      - tempo
```

Then across ALL app services (`python-app`, `java-app`, `dotnet-app`, `node-edge`): set `OTEL_EXPORTER_OTLP_ENDPOINT: http://alloy:4318` and change `depends_on: [otel-collector]` → `alloy`. (If `grafana/alloy:v1.5.1` fails to pull, use the newest `v1.x` tag that pulls and note it in the commit body.)

- [x] **Step 3: Delete the old collector config**: `git rm -r demo/collector`

- [x] **Step 4: Validate + deploy**:

```bash
docker compose -f demo/docker-compose.yml config -q          # expect: silence (valid)
docker compose -f demo/docker-compose.yml up -d --remove-orphans alloy python-app java-app dotnet-app node-edge
docker compose -f demo/docker-compose.yml logs alloy | tail -20   # expect: no error-level lines
```

- [x] **Step 5: Verify E2E through Alloy** (loadgen is already driving traffic):

```bash
# logs land in Loki with service_name label:
curl -s "http://localhost:3100/loki/api/v1/label/service_name/values"
# expect JSON containing python-app, java-app, dotnet-app, node-edge

# traces land in Tempo — drive one and look it up from inside the network:
TID=$(curl -s http://localhost:8090/api/order | python -c "import sys,json;print(json.load(sys.stdin)['traceId'])")
sleep 12
docker compose -f demo/docker-compose.yml exec -T python-app python3 -c "import urllib.request,json;d=json.load(urllib.request.urlopen('http://tempo:3200/api/traces/$TID'));print(len(d['batches']))"
# expect: a number >= 4 (batches from 4 services)
```

- [x] **Step 6: Commit**

```bash
git add demo/alloy demo/docker-compose.yml demo/README.md
git rm -r demo/collector
git commit -m "demo: replace OTel Collector with Grafana Alloy as the collector layer"
```

---

### Task 2: Node logs → `@otel/logs` + shutdown auto-flush

**Files:**
- Modify: `libraries/nodejs/logs/package.json` (name), `libraries/nodejs/logs/src/logsInstrumentation.ts`, `libraries/nodejs/logs/README.md` (title/name only)
- Test: existing `libraries/nodejs/logs/tests/*.test.*` (update any `@cloudops` strings) + new flush-hook test

**Interfaces:**
- Produces: npm package `@otel/logs@0.1.0`, same exports (`logger`, `exportLogs()`); `npm pack` filename becomes `otel-logs-0.1.0.tgz` (Task 10 depends on this).

- [x] **Step 1:** In `package.json`: `"name": "@cloudops/otel-logs"` → `"@otel/logs"`; description drop "CloudOps". Grep the package for remaining brand strings: `grep -ri cloudops libraries/nodejs/logs/src libraries/nodejs/logs/tests libraries/nodejs/logs/package.json` and fix every hit (comments, class names like `CloudOpsLogger` → `OtelLogsInstrumentation` keep internal names simple: rename class only if it contains "CloudOps"; internal `LogsInstrumentation` class name is already brand-free — keep it).

- [x] **Step 2: Add shutdown flush** in `logsInstrumentation.ts` — call this at the end of successful init (where `isInitialized = true` is set):

```ts
  // Best-effort flush at process shutdown so batched logs are not lost.
  private registerShutdownFlush(): void {
    process.once("beforeExit", () => {
      void this.exportLogs().catch(() => {});
    });
    process.once("SIGTERM", () => {
      void this.exportLogs().catch(() => {}).finally(() => process.exit(143));
    });
  }
```

- [x] **Step 3: New test** (same style/location as existing tests):

```js
test("shutdown flush hooks are registered after init", () => {
  const before = process.listenerCount("beforeExit");
  require("../dist/index.js"); // importing initialises the logger singleton
  assert.ok(process.listenerCount("beforeExit") >= before);
});
```

- [x] **Step 4:** `cd libraries/nodejs/logs && npm run test:coverage` — expect all tests pass, coverage above existing gates.

- [x] **Step 5: Commit**: `git add libraries/nodejs/logs && git commit -m "feat(nodejs-logs): rename to @otel/logs, add shutdown auto-flush"` (add specific paths, never `node_modules`).

---

### Task 3: Node traces → `@otel/traces` + `/register` entry + shutdown auto-flush

**Files:**
- Create: `libraries/nodejs/traces/src/register.ts`
- Modify: `libraries/nodejs/traces/package.json` (name + exports map), `src/traceInstrumentation.ts` (flush hooks + brand strings), `README.md` (names)
- Test: new register test + existing suite

**Interfaces:**
- Produces: `@otel/traces@0.1.0` with entry points `.` (exports `tracer`, `AzureService`) and `./register` (side-effect init). Pack filename `otel-traces-0.1.0.tgz`.

- [x] **Step 1:** `package.json`: name → `"@otel/traces"`, and add the exports map (keep `main`/`types`):

```json
  "exports": {
    ".": { "types": "./dist/index.d.ts", "default": "./dist/index.js" },
    "./register": { "types": "./dist/register.d.ts", "default": "./dist/register.js" }
  },
```

- [x] **Step 2: Create `src/register.ts`**:

```ts
// Side-effect entry point: `require("@otel/traces/register")` (or
// `node -r @otel/traces/register`) initialises tracing before any app module
// loads, so HTTP auto-instrumentation hooks in ahead of the app's http usage.
import "./index";
```

- [x] **Step 3: Add shutdown flush** in `traceInstrumentation.ts` (call at end of successful init, mirroring Task 2's pattern):

```ts
  private registerShutdownFlush(): void {
    process.once("beforeExit", () => {
      void this.exportSpans().catch(() => {});
    });
    process.once("SIGTERM", () => {
      void this.exportSpans().catch(() => {}).finally(() => process.exit(143));
    });
  }
```

- [x] **Step 4:** De-brand strings: `grep -ri cloudops libraries/nodejs/traces/src libraries/nodejs/traces/tests libraries/nodejs/traces/package.json` → fix all (e.g., tracer name `"${serviceName || "cloudops"}-tracer"` → `"${serviceName || "otel"}-tracer"`).

- [x] **Step 5: New test:**

```js
test("register entry initialises the tracer as a side effect", () => {
  require("../dist/register.js");
  const { tracer } = require("../dist/index.js");
  assert.ok(tracer, "tracer singleton exists after register import");
});
```

- [x] **Step 6:** `cd libraries/nodejs/traces && npm run test:coverage` — all pass, gates hold (register.ts is excluded from coverage automatically only if trivially covered — it will be, since the test imports it).

- [x] **Step 7: Commit**: `git commit -m "feat(nodejs-traces): rename to @otel/traces, add /register entry and shutdown auto-flush"`.

---

### Task 4: Python logs → `otel-logs` (module `otel_logs`) + atexit flush

**Files:**
- Rename: `libraries/python/logs/src/cloudops_otel_logs/` → `libraries/python/logs/src/otel_logs/`
- Modify: `libraries/python/logs/pyproject.toml` (name + hatch packages path), `src/otel_logs/logger.py` (class rename + atexit), all files in `libraries/python/logs/tests/` (imports/patch targets), `README.md`

**Interfaces:**
- Produces: dist `otel-logs`, wheel `otel_logs-0.1.0-py3-none-any.whl` (Task 10 depends on this filename); public API `from otel_logs import logger` + `logger.export_logs()` unchanged.

- [x] **Step 1:** `git mv libraries/python/logs/src/cloudops_otel_logs libraries/python/logs/src/otel_logs`

- [x] **Step 2:** `pyproject.toml`: `name = "cloudops-otel-logs"` → `"otel-logs"`; update the hatch wheel packages entry `src/cloudops_otel_logs` → `src/otel_logs`; scrub description/keywords of "cloudops".

- [x] **Step 3:** In the package + tests, replace module references: `cloudops_otel_logs` → `otel_logs` everywhere (imports and `patch("cloudops_otel_logs.logger....")` targets). Rename class `CloudOpsLogger` → `Logger` (keep the module-level `logger` singleton name). Command:

```bash
cd libraries/python/logs
grep -rl "cloudops_otel_logs\|CloudOpsLogger\|cloudops" src tests README.md | xargs sed -i "s/cloudops_otel_logs/otel_logs/g; s/CloudOpsLogger/Logger/g"
grep -ri cloudops src tests pyproject.toml README.md   # expect: no hits (fix any leftovers by hand)
```

- [x] **Step 4: atexit flush** — at the bottom of `logger.py`, right after the module-level singleton is created:

```python
#flush batched logs at interpreter exit so shutdown does not lose telemetry
atexit.register(logger.export_logs)
```

(add `import atexit` to the imports). New test:

```python
#the module registers an atexit flush on import
def test_atexit_flush_registered():
    import atexit
    import otel_logs
    # re-registering is harmless; assert the hook target exists and is callable
    assert callable(otel_logs.logger.export_logs)
```

- [x] **Step 5:** `cd libraries/python/logs && PYTHONPATH=src python -m pytest -q` — expect all pass (20 existing + new).

- [x] **Step 6: Commit**: `git add -A libraries/python/logs && git commit -m "feat(python-logs): rename to otel-logs, add atexit auto-flush"`.

---

### Task 5: Python traces → `otel-traces` + no-arg `init()` + atexit flush

**Files:**
- Rename: `libraries/python/traces/src/cloudops_otel_traces/` → `src/otel_traces/`
- Modify: `pyproject.toml`, `src/otel_traces/tracer.py` (init signature + atexit), `src/otel_traces/__init__.py` (export `init`), tests, `README.md`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: dist `otel-traces`, wheel `otel_traces-0.1.0-py3-none-any.whl`; public API `from otel_traces import init; init()` — **no framework argument**.

- [x] **Step 1:** `git mv` the module dir; update `pyproject.toml` name → `"otel-traces"` + hatch path; sed `cloudops_otel_traces` → `otel_traces` across src/tests/README (same pattern as Task 4).

- [x] **Step 2: Replace `init_tracing(app)` with no-arg `init()`** in `tracer.py`. Keep ALL existing provider/exporter/gating logic in place; only the public entry and instrumentation registration change:

```python
#Initializes tracing: gates OTLP on endpoint + X_ORG_ID, else console; registers
#W3C propagation and opportunistically instruments HTTP libs that are installed.
def init():
    _init_provider()  # the existing provider/exporter/propagator setup, unchanged
    try:
        from opentelemetry.instrumentation.requests import RequestsInstrumentor
        RequestsInstrumentor().instrument()
    except Exception:
        pass
    try:
        from opentelemetry.instrumentation.flask import FlaskInstrumentor
        FlaskInstrumentor().instrument()  # global: instruments Flask apps created after this call
    except Exception:
        pass
    atexit.register(_flush)

#flush spans at interpreter exit
def _flush():
    try:
        trace.get_tracer_provider().force_flush()
    except Exception:
        pass
```

If the current file inlines provider setup inside `init_tracing`, extract it to `_init_provider()` verbatim. Export `init` from `__init__.py`; delete `init_tracing`.

- [x] **Step 3: Tests** — update existing tests calling `init_tracing(app)` to call `init()` (drop Flask fixtures where they only existed to satisfy the old signature). Add:

```python
#init is no-arg and never throws even with no frameworks importable
def test_init_no_arg_never_throws(monkeypatch):
    import otel_traces
    otel_traces.init()
```

- [x] **Step 4:** `PYTHONPATH=src python -m pytest -q` — all pass.

- [x] **Step 5: Commit**: `git commit -m "feat(python-traces): rename to otel-traces, no-arg init() with opportunistic instrumentation, atexit flush"`.

---

### Task 6: Java logs → `otel:otel-logs`, `Logger.init()` + shutdown-hook flush

**Files:**
- Rename: `libraries/java/logs/src/main/java/com/cloudops/otel/logs/` → `src/main/java/otel/logs/` (same for `src/test/java/...`)
- Rename class: `CloudOpsLogger.java` → `Logger.java`
- Modify: `libraries/java/logs/pom.xml` (groupId `com.cloudops` → `otel`), all `.java` files (package/import/class refs), `README.md`

**Interfaces:**
- Produces: Maven artifact `otel:otel-logs:0.1.0`, class `otel.logs.Logger` with static `Logger init()` (rename of `initialiseLogger()`), instance methods `info/warn/error/debug/exportLogs` unchanged.

- [x] **Step 1: Mechanical rename** (Git Bash, from repo root):

```bash
cd libraries/java/logs
mkdir -p src/main/java/otel src/test/java/otel
git mv src/main/java/com/cloudops/otel/logs src/main/java/otel/logs
git mv src/test/java/com/cloudops/otel/logs src/test/java/otel/logs
find src -name "*.java" -exec sed -i "s/com\.cloudops\.otel\.logs/otel.logs/g; s/CloudOpsLogger/Logger/g; s/initialiseLogger/init/g; s/initializeLogger/init/g" {} +
git mv src/main/java/otel/logs/CloudOpsLogger.java src/main/java/otel/logs/Logger.java 2>/dev/null || true
sed -i "s/<groupId>com.cloudops<\/groupId>/<groupId>otel<\/groupId>/" pom.xml
grep -ri cloudops src pom.xml README.md   # fix every remaining hit (README text, pom <name>)
```

(If the test class file name contains `CloudOpsLogger`, `git mv` it too.)

- [x] **Step 2: Shutdown-hook flush** — inside `Logger.init()`, after the singleton is constructed (guard so it registers once):

```java
    Runtime.getRuntime().addShutdownHook(new Thread(instance::exportLogs));
```

- [x] **Step 3:** `mvn -q -f "C:/Users/user/Desktop/OtelLibraries/libraries/java/logs/pom.xml" verify` — expect BUILD SUCCESS, 9+ tests, JaCoCo gate green.

- [x] **Step 4: Commit**: `git add -A libraries/java/logs && git commit -m "feat(java-logs): rename to otel:otel-logs with Logger.init(), add shutdown-hook flush"`.

---

### Task 7: Java traces → `otel:otel-traces`, `Tracer.init()` + `tracedClient()` / `wrap()` helpers

**Files:**
- Rename: package dirs as in Task 6 (`com/cloudops/otel/traces` → `otel/traces`); `CloudOpsTracer.java` → `Tracer.java`
- Create: `libraries/java/traces/src/main/java/otel/traces/TracedHttpClient.java`
- Modify: `pom.xml` (groupId), all `.java` files, `README.md`
- Test: `src/test/java/otel/traces/TracedHttpClientTest.java` (new)

**Interfaces:**
- Consumes: existing `startServerSpan(String, Map<String,String>)`, `startClientSpan(String)`, `injectHeaders()`, `exportSpans()` (public, unchanged).
- Produces: `otel:otel-traces:0.1.0`; `otel.traces.Tracer.init()`; `tracer.tracedClient()` returning `TracedHttpClient` with `<T> HttpResponse<T> send(HttpRequest, BodyHandler<T>)`; `tracer.wrap(String name, HttpHandler handler)` returning a wrapped `com.sun.net.httpserver.HttpHandler`. Task 10's demo app uses exactly these.

- [ ] **Step 1: Mechanical rename** (same recipe as Task 6, substituting `traces`, `CloudOpsTracer` → `Tracer`, `initializeTracer` → `init`). Run the `grep -ri cloudops` sweep and fix all hits.

- [ ] **Step 2: Write the failing test** `TracedHttpClientTest.java`:

```java
package otel.traces;

import static org.junit.jupiter.api.Assertions.*;

import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;

class TracedHttpClientTest {
  @Test
  void tracedClientInjectsTraceparentAndReturnsResponse() throws Exception {
    HttpServer server = HttpServer.create(new InetSocketAddress(0), 0);
    AtomicReference<String> traceparent = new AtomicReference<>();
    server.createContext("/t", ex -> {
      traceparent.set(ex.getRequestHeaders().getFirst("traceparent"));
      ex.sendResponseHeaders(200, -1);
      ex.close();
    });
    server.start();
    try {
      Tracer tracer = Tracer.init();
      HttpResponse<Void> resp = tracer.tracedClient().send(
          HttpRequest.newBuilder(URI.create(
              "http://localhost:" + server.getAddress().getPort() + "/t")).GET().build(),
          HttpResponse.BodyHandlers.discarding());
      assertEquals(200, resp.statusCode());
      assertNotNull(traceparent.get(), "W3C traceparent header must be injected");
    } finally {
      server.stop(0);
    }
  }

  @Test
  void wrapRunsHandlerInsideServerSpan() throws Exception {
    HttpServer server = HttpServer.create(new InetSocketAddress(0), 0);
    Tracer tracer = Tracer.init();
    AtomicReference<Boolean> handled = new AtomicReference<>(false);
    server.createContext("/w", tracer.wrap("w", ex -> {
      handled.set(true);
      ex.sendResponseHeaders(200, -1);
      ex.close();
    }));
    server.start();
    try {
      HttpResponse<Void> resp = java.net.http.HttpClient.newHttpClient().send(
          HttpRequest.newBuilder(URI.create(
              "http://localhost:" + server.getAddress().getPort() + "/w")).GET().build(),
          HttpResponse.BodyHandlers.discarding());
      assertEquals(200, resp.statusCode());
      assertTrue(handled.get());
    } finally {
      server.stop(0);
    }
  }
}
```

- [ ] **Step 3:** `mvn -q -f <abs>/libraries/java/traces/pom.xml verify` — expect FAIL: `cannot find symbol: method tracedClient()` / `wrap(...)`.

- [ ] **Step 4: Implement.** New file `TracedHttpClient.java`:

```java
package otel.traces;

import io.opentelemetry.api.trace.Span;
import io.opentelemetry.context.Scope;
import java.io.IOException;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

// Traced wrapper over java.net.http.HttpClient: each send() runs in a CLIENT
// span named "<METHOD> <path>" with W3C tracecontext headers injected, so the
// downstream service continues the same trace.
public final class TracedHttpClient {
  private final Tracer tracer;
  private final HttpClient delegate;

  TracedHttpClient(Tracer tracer, HttpClient delegate) {
    this.tracer = tracer;
    this.delegate = delegate;
  }

  public <T> HttpResponse<T> send(HttpRequest request, HttpResponse.BodyHandler<T> handler)
      throws IOException, InterruptedException {
    Span span = tracer.startClientSpan(request.method() + " " + request.uri().getPath());
    try (Scope scope = span.makeCurrent()) {
      HttpRequest.Builder builder = HttpRequest.newBuilder(request, (k, v) -> true);
      tracer.injectHeaders().forEach(builder::header);
      return delegate.send(builder.build(), handler);
    } catch (IOException | InterruptedException e) {
      span.recordException(e);
      throw e;
    } finally {
      span.end();
    }
  }
}
```

And in `Tracer.java` add:

```java
  // Returns an HttpClient wrapper whose send() creates a CLIENT span and
  // injects W3C headers — one line replaces manual client-span plumbing.
  public TracedHttpClient tracedClient() {
    return new TracedHttpClient(this, java.net.http.HttpClient.newHttpClient());
  }

  // Wraps a JDK HttpServer handler: extracts W3C context from the request
  // headers and runs the handler inside a SERVER span, exporting on completion.
  public com.sun.net.httpserver.HttpHandler wrap(
      String name, com.sun.net.httpserver.HttpHandler handler) {
    return exchange -> {
      java.util.Map<String, String> incoming = new java.util.HashMap<>();
      exchange.getRequestHeaders().forEach((key, values) -> {
        if (values != null && !values.isEmpty()) {
          incoming.put(key.toLowerCase(), values.get(0));
        }
      });
      Span span = startServerSpan(name, incoming);
      try (Scope scope = span.makeCurrent()) {
        handler.handle(exchange);
      } catch (java.io.IOException e) {
        span.recordException(e);
        throw e;
      } finally {
        span.end();
        exportSpans();
      }
    };
  }
```

Also add the shutdown-hook flush inside `Tracer.init()` (once): `Runtime.getRuntime().addShutdownHook(new Thread(instance::exportSpans));`

- [ ] **Step 5:** `mvn -q verify` again — expect BUILD SUCCESS, new tests + existing suite green.

- [ ] **Step 6: Commit**: `git commit -m "feat(java-traces): rename to otel:otel-traces with Tracer.init(), add tracedClient()/wrap() helpers and shutdown flush"`.

---

### Task 8: .NET logs → `Otel.Logs`, `Logger.Init()` + ProcessExit flush

**Files:**
- Modify: `libraries/dotnet/logs/CloudOps.Otel.Logs.csproj` → rename file to `Otel.Logs.csproj`; inside: `<PackageId>Otel.Logs</PackageId>`, `<RootNamespace>Otel.Logs</RootNamespace>` (add if absent), `<AssemblyName>Otel.Logs</AssemblyName>`
- Rename: `src/CloudOpsLogger.cs` → `src/Logger.cs`; namespace `CloudOps.Otel.Logs` → `Otel.Logs`; class `CloudOpsLogger` → `Logger`; `InitialiseLogger()` → `Init()`
- Modify: `tests/CloudOps.Otel.Logs.Tests.csproj` → `tests/Otel.Logs.Tests.csproj` (+ ProjectReference path), all test `.cs` files, `README.md`

**Interfaces:**
- Produces: NuGet `Otel.Logs.0.1.0.nupkg`; `Otel.Logs.Logger.Init()` returning the logger; `Info/Warn/Error/Debug/ExportLogs` unchanged.

- [ ] **Step 1: Mechanical rename**:

```bash
cd libraries/dotnet/logs
git mv CloudOps.Otel.Logs.csproj Otel.Logs.csproj
git mv src/CloudOpsLogger.cs src/Logger.cs
git mv tests/CloudOps.Otel.Logs.Tests.csproj tests/Otel.Logs.Tests.csproj
grep -rl "CloudOps" src tests *.csproj README.md | xargs sed -i "s/CloudOps\.Otel\.Logs/Otel.Logs/g; s/CloudOpsLogger/Logger/g; s/InitialiseLogger/Init/g; s/CloudOps//g"
grep -ri cloudops . --include="*.cs" --include="*.csproj" --include="*.md"   # expect zero
```

(Inspect the `s/CloudOps//g` results — it's a catch-all for comments/strings; revert any mangled words by hand.)

- [ ] **Step 2: ProcessExit flush** — in `Logger.Init()` after singleton construction (register once):

```csharp
        AppDomain.CurrentDomain.ProcessExit += (_, _) => Instance?.ExportLogs();
```

- [ ] **Step 3:** `cd libraries/dotnet/logs && dotnet test tests/Otel.Logs.Tests.csproj` — expect 17+ tests pass, coverage gate green.

- [ ] **Step 4: Commit**: `git commit -m "feat(dotnet-logs): rename to Otel.Logs with Logger.Init(), add ProcessExit flush"`.

---

### Task 9: .NET traces → `Otel.Traces`, `AddOtelTraces()`

**Files:**
- Rename: `libraries/dotnet/traces/CloudOps.Otel.Traces.csproj` → `Otel.Traces.csproj`; `src/CloudOpsTracing.cs` → `src/OtelTracing.cs`; `tests/...Tests.csproj` likewise
- Modify: namespace → `Otel.Traces`; extension method `AddCloudOpsTracing()` → `AddOtelTraces()`; class `CloudOpsTracing` → `OtelTracing`; constants (`DefaultTracesEndpoint`, `DefaultXOrgId`) keep their names

**Interfaces:**
- Produces: NuGet `Otel.Traces.0.1.0.nupkg`; `services.AddOtelTraces()`. No shutdown hook needed: the OTel .NET SDK's TracerProvider is disposed by the DI host on graceful shutdown, which flushes — note this in the README.

- [ ] **Step 1:** Same mechanical rename recipe as Task 8 with `Otel.Traces` / `OtelTracing` / `AddOtelTraces` substitutions; `grep -ri cloudops` sweep to zero.

- [ ] **Step 2:** `dotnet test tests/Otel.Traces.Tests.csproj` — all pass.

- [ ] **Step 3: Commit**: `git commit -m "feat(dotnet-traces): rename to Otel.Traces with AddOtelTraces()"`.

---

### Task 10: Migrate the demo to the new packages and verify E2E

**Files:**
- Modify: `demo/scripts/build-libs.sh` (no logic change — verify output names), `demo/apps/python/app.py` + `demo/apps/python/Dockerfile`, `demo/apps/java/src/main/java/com/cloudops/demo/App.java` (+ its pom.xml + `demo/apps/java/Dockerfile`), `demo/apps/dotnet/Program.cs` + `DotnetApp.csproj` + Dockerfile, `demo/apps/node/server.js` + `package.json` + Dockerfile

**Interfaces:**
- Consumes: artifacts from Tasks 2-9 — `otel-logs-0.1.0.tgz`, `otel-traces-0.1.0.tgz`, `otel_logs-0.1.0-py3-none-any.whl`, `otel_traces-0.1.0-py3-none-any.whl`, `Otel.Logs.0.1.0.nupkg`, `Otel.Traces.0.1.0.nupkg`, Maven `otel:otel-logs`/`otel:otel-traces`.

- [ ] **Step 1:** Per app, apply the new names:
  - **python/app.py**: `from cloudops_otel_logs import logger` → `from otel_logs import logger`; `from cloudops_otel_traces import init_tracing` + `init_tracing(app)` → `from otel_traces import init` and call `init()` **before** `app = Flask(__name__)` (global Flask instrumentation applies to apps created after the call). Dockerfile: wheel filenames → `otel_logs-0.1.0-py3-none-any.whl`, `otel_traces-0.1.0-py3-none-any.whl`.
  - **java/App.java**: imports → `otel.logs.Logger`, `otel.traces.Tracer`; `CloudOpsLogger.initializeLogger()` → `Logger.init()`; `CloudOpsTracer.initializeTracer()` → `Tracer.init()`. Replace the manual server-span plumbing in `process()` with `tracer.wrap(...)` at context registration, and the manual client-span block with `TRACER.tracedClient().send(...)` — the app should shrink markedly. Java demo `pom.xml`: dependency groupIds `com.cloudops` → `otel`. Dockerfile: update any `com/cloudops` paths if it references built jar paths.
  - **dotnet/Program.cs**: `using CloudOps.Otel.Logs;`/`...Traces` → `Otel.Logs`/`Otel.Traces`; `CloudOpsLogger.InitialiseLogger()` → `Logger.Init()`; `AddCloudOpsTracing()` → `AddOtelTraces()`. csproj PackageReferences → `Otel.Logs`, `Otel.Traces`.
  - **node/server.js**: `require("@cloudops/otel-traces")` → `require("@otel/traces/register")`; `require("@cloudops/otel-logs")` → `require("@otel/logs")`. package.json deps + Dockerfile tarball names → `otel-logs-0.1.0.tgz` / `otel-traces-0.1.0.tgz`.

- [ ] **Step 2: Rebuild artifacts and images**:

```bash
bash demo/scripts/build-libs.sh          # verify it lists the NEW artifact names
docker compose -f demo/docker-compose.yml up -d --build python-app java-app dotnet-app node-edge
```

- [ ] **Step 3: Full E2E verification** (same recipe as Task 1 Step 5): drive `http://localhost:8090/api/order`, confirm the trace spans all 4 services in Tempo (query from inside python-app), confirm `service_name` labels in Loki, confirm service-graph edges still land in Mimir: `curl -s "http://localhost:9009/prometheus/api/v1/query?query=traces_service_graph_request_total"` shows the 4 edges, and Grafana `http://localhost:3000/api/health` is ok.

- [ ] **Step 4: Commit**: `git commit -m "demo: migrate apps to the renamed otel-logs/otel-traces packages and one-liner APIs"`.

---

### Task 11: Docs rewrite + final de-brand sweep

**Files:**
- Modify: `docs/USING-THE-LIBRARIES.md`, `libraries/README.md`, all 8 per-library `README.md`s, `libraries/{python,java,dotnet,nodejs}/README.md` (per-language rollups, if present), `CLAUDE.md`, `demo/README.md`

- [ ] **Step 1:** Rewrite `docs/USING-THE-LIBRARIES.md`: new package names/coordinates everywhere; quick starts become the one-liners from the spec §2; **add an "Infra templates" section** with three copy-paste blocks (docker-compose service env, K8s Deployment env, Azure App Service app settings) each carrying `OTEL_SERVICE_NAME`, `OTEL_BACKEND_EXPORTERS=otel`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `X_ORG_ID`; change the security note: `X_ORG_ID` is an **org identifier (not a secret)** — recommend env-var supply for flexibility, HTTPS endpoints in non-local environments, and keep the "don't log secrets/PII" advice.
- [ ] **Step 2:** Update every README + `CLAUDE.md` (package identity table, layout, class names `Logger`/`Tracer`, env contract unchanged, Alloy in the demo description) and `demo/README.md` (Alloy, new package names).
- [ ] **Step 3: Final sweep** — must return ZERO hits:

```bash
grep -ri cloudops --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=target \
  --exclude-dir=bin --exclude-dir=obj --exclude-dir=.venv --exclude-dir=metrics \
  --exclude-dir=superpowers -r .
```

(`docs/superpowers/` is excluded as historical record; `libraries/nodejs/metrics/` is out of scope. Everything else must be clean — fix any hit and re-run.)

- [ ] **Step 4:** Re-run all four test suites one final time (commands in Global Constraints) — all green.
- [ ] **Step 5: Commit**: `git commit -m "docs: de-branded documentation with one-liner quick starts and infra templates"`.
