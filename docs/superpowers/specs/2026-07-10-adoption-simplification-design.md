# Adoption Simplification & De-brand — Design

**Date:** 2026-07-10
**Status:** Approved (all sections) by project owner
**Scope:** All four library ports (Python / Java / .NET / Node.js), both signals (logs, traces), demo apps, docs.

## Problem

Adopting the libraries today takes too many steps per app team: two packages to
discover, two differently-shaped init calls per language, 4+ env vars, manual
flush calls, ~20 lines of manual span code in Java, and an import-order footgun
in Node. The goal is **one package, one line, standard env vars** per signal.

The libraries are also being made fully independent: **every `CloudOps`
identifier is removed** (package names, namespaces, class names, docs).

## Decisions (from design Q&A)

| Decision | Choice |
|---|---|
| Target DX | **One-liner** per signal (install 1 pkg, 1 init line, env vars from infra) |
| Config source | **Env vars from infra** (deployment templates), not baked defaults |
| `X_ORG_ID` | An **org identifier, not a secret** — safe to commit; docs must not treat it as a credential |
| Framework coupling | **None** — libraries stay framework-independent |
| Package shape | Logs and traces stay **separate packages** (no umbrella/merge) so teams only pull the signal they use |
| Branding | **De-brand completely** — names are just "logs" and "traces" under an `otel` qualifier |
| `OTEL_BACKEND_EXPORTERS` | **Kept as an explicit env var** (default `console`) — it is the operational switch for changing backends via env alone |
| Back-compat | None needed — no existing users |

## 1. Naming & packaging

Repo layout stays `libraries/<lang>/{logs,traces}`. Renames:

| Ecosystem | Package (old → new) | Entry point (old → new) |
|---|---|---|
| Python | `cloudops-otel-logs` → `otel-logs` (module `otel_logs`) | `from cloudops_otel_logs import logger` → `from otel_logs import logger` |
| Python | `cloudops-otel-traces` → `otel-traces` (module `otel_traces`) | `init_tracing(app)` → `init()` |
| Java | `com.cloudops:otel-logs` → `otel:otel-logs` (package `otel.logs`) | `CloudOpsLogger.initialiseLogger()` → `Logger.init()` |
| Java | `com.cloudops:otel-traces` → `otel:otel-traces` (package `otel.traces`) | `CloudOpsTracer.initializeTracer()` → `Tracer.init()` |
| .NET | `CloudOps.Otel.Logs` → `Otel.Logs` | `CloudOpsLogger.InitialiseLogger()` → `Logger.Init()` |
| .NET | `CloudOps.Otel.Traces` → `Otel.Traces` | `AddCloudOpsTracing()` → `AddOtelTraces()` |
| Node | `@cloudops/otel-logs` → `@otel/logs` | `import { logger }` (shape unchanged) |
| Node | `@cloudops/otel-traces` → `@otel/traces` | adds `@otel/traces/register` side-effect entry |

**Risk noted:** bare names on registries that proxy public npm/PyPI are exposed
to dependency-confusion squatting. Mitigation: the private registry must route
these names to the internal feed only. If that cannot be guaranteed, a scope
word can be substituted later — the rest of this design is name-agnostic.

## 2. One-liner API per language

What an app team writes, in full:

**Python**
```python
from otel_logs import logger      # logs: import IS the init
logger.info("hi")

from otel_traces import init      # traces: no-arg, framework-independent
init()
```
`init()` takes no framework object. It opportunistically instruments supported
HTTP libraries that are importable (`requests`, Flask) inside try/except and
silently skips absent ones. No hard framework dependencies.

**Node.js**
```js
require("@otel/traces/register");        // line 1 — or zero-code via
                                          // NODE_OPTIONS="--require @otel/traces/register"
const { logger } = require("@otel/logs");
```
The `register` subpath performs init as a side effect, eliminating the
import-order footgun (HTTP auto-instrumentation must precede the app's `http`
usage).

**.NET**
```csharp
builder.Services.AddOtelTraces();   // traces (ASP.NET Core + HttpClient auto-instr.)
var logger = Logger.Init();         // logs
```

**Java** — framework-free edge helpers replace manual span plumbing:
```java
var logger = Logger.init();
var tracer = Tracer.init();

// Outbound: wraps java.net.http.HttpClient — creates a CLIENT span and injects
// W3C headers on every send:
var client = tracer.tracedClient();

// Inbound: wraps a com.sun.net.httpserver handler — extracts W3C context from
// the request headers and runs the handler inside a SERVER span:
server.createContext("/x", tracer.wrap("x", handler));
```
The existing manual API (`startServerSpan`, `startClientSpan`, `injectHeaders`)
remains public for non-HTTP or custom transports.

## 3. Environment contract (unchanged, plus templates)

No variables are added, removed, or renamed:

- `OTEL_SERVICE_NAME` (required), `OTEL_RESOURCE_ATTRIBUTES`
- `OTEL_BACKEND_EXPORTERS` — **explicit** backend switch, default `console`
- `OTEL_EXPORTER_OTLP_{LOGS|TRACES}_ENDPOINT` / `OTEL_EXPORTER_OTLP_ENDPOINT`
- `X_ORG_ID` — org identifier sent as `X-OrgId` header; required for OTLP
- `OTEL_LOG_LEVEL`, `OTEL_LOGS_SAMPLING_RATE`, `OTEL_EXPORTER_PARAMETERS`

Gating unchanged: `otel` exporter is used only when endpoint + `X_ORG_ID` both
resolve, else console fallback.

Docs gain copy-paste **infra templates** (docker-compose block, K8s manifest
snippet, Azure App Service app-settings) carrying the standard 4 vars, and the
"X_ORG_ID is a credential" security note is corrected to "org identifier".

## 4. Lifecycle: auto-flush on shutdown

Each port registers a best-effort flush at process shutdown so batched
telemetry is not lost on stop:

| Port | Mechanism |
|---|---|
| Python | `atexit` |
| Node | `beforeExit` + `SIGTERM` handler |
| Java | `Runtime.addShutdownHook` |
| .NET | `AppDomain.ProcessExit` (+ host lifetime when available) |

Explicit `export_logs()` / `exportSpans()` (per-language casing) remain public —
still required in Functions/serverless where the process outlives invocations.

## 5. Explicitly unchanged

Sampling logic, X-OrgId header gating, Azure runtime detection
(Functions / Container Apps / App Service / AKS), console/OTLP exporters,
per-signal tests and coverage gates, demo stack architecture
(collector → Loki/Tempo/Mimir → Grafana), and the OTel SDK versions from the
2026-07-10 security patch (Node OTel JS 2.x line).

## 6. Migration & verification

1. Rename all four ports: source, tests, build manifests (pyproject, pom,
   csproj, package.json), README titles.
2. Implement the new API surface: Python no-arg `init()`, Node `register`
   entry, Java `tracedClient()`/`wrap()`, shutdown flush in all ports.
3. Update demo apps, Dockerfiles, `demo/scripts/build-libs.sh`, compose file to
   the new package names.
4. Rewrite docs: `docs/USING-THE-LIBRARIES.md` (new names, one-liner quick
   starts, infra templates, corrected X_ORG_ID note), per-library READMEs,
   `CLAUDE.md`.
5. Verify: each port's unit suite green (existing coverage gates), then the
   live demo chain — one W3C trace across browser → node → python → java →
   dotnet, logs correlated in Grafana, service-graph edges present in Mimir.

No back-compat shims; no existing consumers.

## Error handling

Init never throws: all wiring stays inside try/catch with console fallback
(existing pattern). Opportunistic instrumentation failures are debug-logged and
skipped. Shutdown-flush hooks swallow and debug-log exporter errors — a failing
collector must not break process exit.

## Testing

- Unit tests per port for: new init surfaces, shutdown-hook registration,
  Java `tracedClient()` header injection + span kinds, Node `register`
  side-effect init, Python opportunistic-instrumentation skip path.
- Existing suites keep passing (rename-only churn must not change behaviour).
- Demo E2E as the integration proof (trace continuity + log correlation).
