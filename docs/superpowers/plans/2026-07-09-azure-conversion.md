# AWS → Azure Conversion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert all three CloudOps OTel logs libraries (Python/Java/.NET) from AWS runtime detection + SSM naming to Azure runtime detection + provider-neutral config naming, leaving zero AWS references.

**Architecture:** In-place swap. The detection ladder in `RuntimeResourceAttributes` (Java/.NET) / `_runtime_resource_attributes` (Python) keeps its exact shape — early-return serverless branch, fall-through container/K8s branches — with Azure triggers and `azure_*` platform values. `SsmParameters` becomes `ExporterParameters` everywhere. The Lambda trace-header branch in the trace-id helpers is deleted.

**Tech Stack:** Python 3.11+ / pytest+unittest; Java 21 / Maven / JUnit 5 / Jackson; .NET 8 / xUnit.

**Spec:** `docs/superpowers/specs/2026-07-09-azure-conversion-design.md`

## Global Constraints

- Hard cutover: no AWS env var is read anywhere after this plan; no deprecated aliases.
- Platform values exactly: `azure_functions`, `azure_container_apps`, `azure_app_service`, `azure_aks`. `cloud.provider=azure` is set whenever a platform is set.
- New env vars exactly: `OTEL_EXPORTER_PARAMETERS`, `OTEL_EXPORTER_PARAMETERS_FILE` (replacing `OTEL_SSM_PARAMETERS`, `OTEL_SSM_PARAMETERS_FILE`).
- Default params file stays `/tmp/otelExporterParams.json`.
- `pe-lib-log-ver` attribute value `1.16.2` stays (not AWS-related).
- Keep each port's existing code style (terse `#comment`/`// comment` headers).
- Commit messages: NO Co-Authored-By or AI attribution (project rule).
- Acceptance (Task 5): `grep -rniE "aws|ssm|lambda|amzn|\becs\b|\beks\b" libraries/` → no hits.

---

### Task 1: Python — Azure runtime detection

**Files:**
- Modify: `libraries/python/logs/src/cloudops_otel_logs/logger.py:187-225` (`_runtime_resource_attributes`)
- Test: `libraries/python/logs/tests/test_logger.py:26-66`

**Interfaces:**
- Produces: `_runtime_resource_attributes() -> dict[str, str]` — same signature, Azure attribute output. Task 6 relies on the runtime behaviour end-to-end.

- [ ] **Step 1: Replace the three AWS detection tests with Azure tests**

In `libraries/python/logs/tests/test_logger.py`, replace `test_runtime_resource_attributes_for_eks` (lines 26-43) and `test_runtime_resource_attributes_for_lambda` (lines 45-54) with the following five tests (keep `test_runtime_resource_attributes_merge_otel_resource_attributes` unchanged):

```python
    #Handles test runtime resource attributes for AKS.
    def test_runtime_resource_attributes_for_aks(self):
        with patch.dict("os.environ", {
            "OTEL_SERVICE_NAME": "order-api",
            "KUBERNETES_SERVICE_HOST": "10.0.0.1",
            "K8S_NAMESPACE_NAME": "cloudops",
            "K8S_POD_NAME": "order-api-abc",
            "K8S_NODE_NAME": "aks-nodepool1-1",
            "AKS_CLUSTER_NAME": "cloudops-dev",
        }, clear=True):
            logger = CloudOpsLogger("test")

        self.assertEqual(logger.resource_attributes["service.name"], "order-api")
        self.assertEqual(logger.resource_attributes["cloud.provider"], "azure")
        self.assertEqual(logger.resource_attributes["cloud.platform"], "azure_aks")
        self.assertEqual(logger.resource_attributes["k8s.namespace.name"], "cloudops")
        self.assertEqual(logger.resource_attributes["k8s.pod.name"], "order-api-abc")
        self.assertEqual(logger.resource_attributes["k8s.node.name"], "aks-nodepool1-1")
        self.assertEqual(logger.resource_attributes["k8s.cluster.name"], "cloudops-dev")

    #Handles test runtime resource attributes for Azure Functions.
    def test_runtime_resource_attributes_for_functions(self):
        with patch.dict("os.environ", {
            "FUNCTIONS_EXTENSION_VERSION": "~4",
            "WEBSITE_SITE_NAME": "orders-func",
        }, clear=True):
            logger = CloudOpsLogger("test")

        self.assertEqual(logger.resource_attributes["service.name"], "orders-func")
        self.assertEqual(logger.resource_attributes["cloud.provider"], "azure")
        self.assertEqual(logger.resource_attributes["cloud.platform"], "azure_functions")
        self.assertEqual(logger.resource_attributes["faas.name"], "orders-func")

    #Handles test Functions detection early-returns before K8s attributes.
    def test_runtime_resource_attributes_functions_early_return(self):
        with patch.dict("os.environ", {
            "FUNCTIONS_WORKER_RUNTIME": "python",
            "WEBSITE_SITE_NAME": "orders-func",
            "KUBERNETES_SERVICE_HOST": "10.0.0.1",
        }, clear=True):
            logger = CloudOpsLogger("test")

        self.assertEqual(logger.resource_attributes["cloud.platform"], "azure_functions")
        self.assertNotIn("k8s.pod.name", logger.resource_attributes)

    #Handles test runtime resource attributes for Container Apps.
    def test_runtime_resource_attributes_for_container_apps(self):
        with patch.dict("os.environ", {
            "OTEL_SERVICE_NAME": "order-api",
            "CONTAINER_APP_NAME": "orders-ca",
        }, clear=True):
            logger = CloudOpsLogger("test")

        self.assertEqual(logger.resource_attributes["cloud.provider"], "azure")
        self.assertEqual(logger.resource_attributes["cloud.platform"], "azure_container_apps")
        self.assertEqual(logger.resource_attributes["container.name"], "orders-ca")

    #Handles test Container Apps plus K8s signals fall through to AKS.
    def test_container_apps_with_k8s_falls_through_to_aks(self):
        with patch.dict("os.environ", {
            "CONTAINER_APP_NAME": "orders-ca",
            "KUBERNETES_SERVICE_HOST": "10.0.0.1",
        }, clear=True):
            logger = CloudOpsLogger("test")

        self.assertEqual(logger.resource_attributes["cloud.platform"], "azure_aks")
        self.assertEqual(logger.resource_attributes["container.name"], "orders-ca")

    #Handles test runtime resource attributes for App Service.
    def test_runtime_resource_attributes_for_app_service(self):
        with patch.dict("os.environ", {
            "WEBSITE_SITE_NAME": "orders-web",
        }, clear=True):
            logger = CloudOpsLogger("test")

        self.assertEqual(logger.resource_attributes["service.name"], "orders-web")
        self.assertEqual(logger.resource_attributes["cloud.provider"], "azure")
        self.assertEqual(logger.resource_attributes["cloud.platform"], "azure_app_service")
        self.assertNotIn("faas.name", logger.resource_attributes)
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run (from `libraries/python/logs`): `python -m pytest tests/test_logger.py -k "runtime_resource" -v`
Expected: the five new tests FAIL (KeyError `cloud.provider` / wrong platform values); merge test PASSES.

- [ ] **Step 3: Implement the Azure ladder**

Replace `_runtime_resource_attributes` (currently `logger.py` lines 187-225) with:

```python
#Handles runtime resource attributes.
def _runtime_resource_attributes() -> dict[str, str]:
    attributes = _parse_resource_attributes(os.getenv("OTEL_RESOURCE_ATTRIBUTES"))
    attributes["service.name"] = (
        os.getenv("OTEL_SERVICE_NAME")
        or attributes.get("service.name")
        or os.getenv("WEBSITE_SITE_NAME")
        or "unknown_service"
    )
    attributes["pe-lib-log-ver"] = "1.16.2"

    if _first_env("FUNCTIONS_EXTENSION_VERSION", "FUNCTIONS_WORKER_RUNTIME"):
        attributes["cloud.provider"] = "azure"
        attributes["cloud.platform"] = "azure_functions"
        site_name = os.getenv("WEBSITE_SITE_NAME")
        if site_name:
            attributes["faas.name"] = site_name
        return attributes

    if os.getenv("CONTAINER_APP_NAME"):
        attributes["cloud.provider"] = "azure"
        attributes["cloud.platform"] = "azure_container_apps"

    if os.getenv("WEBSITE_SITE_NAME"):
        attributes["cloud.provider"] = "azure"
        attributes["cloud.platform"] = "azure_app_service"

    running_on_kubernetes = bool(os.getenv("KUBERNETES_SERVICE_HOST"))
    k8s_cluster_name = _first_env("K8S_CLUSTER_NAME", "AKS_CLUSTER_NAME")
    k8s_namespace_name = _first_env("K8S_NAMESPACE_NAME", "POD_NAMESPACE")
    k8s_node_name = _first_env("K8S_NODE_NAME", "NODE_NAME")
    k8s_pod_name = _first_env("K8S_POD_NAME", "POD_NAME") or (os.getenv("HOSTNAME") if running_on_kubernetes else None)

    if running_on_kubernetes or k8s_cluster_name or k8s_namespace_name or k8s_pod_name:
        attributes["cloud.provider"] = "azure"
        attributes["cloud.platform"] = "azure_aks"

    optional_attributes = {
        "k8s.cluster.name": k8s_cluster_name,
        "k8s.namespace.name": k8s_namespace_name,
        "k8s.node.name": k8s_node_name,
        "k8s.pod.name": k8s_pod_name,
        "container.id": os.getenv("CONTAINER_ID"),
        "container.name": _first_env("CONTAINER_NAME", "CONTAINER_APP_NAME"),
    }
    attributes.update({key: value for key, value in optional_attributes.items() if value})
    return attributes
```

- [ ] **Step 4: Run the runtime tests to verify they pass**

Run: `python -m pytest tests/test_logger.py -k "runtime_resource" -v`
Expected: all six PASS.

- [ ] **Step 5: Commit**

```bash
git add libraries/python/logs
git commit -m "feat(python): detect Azure runtimes instead of AWS"
```

---

### Task 2: Python — ExporterParameters rename, trace-id cleanup, README

**Files:**
- Modify: `libraries/python/logs/src/cloudops_otel_logs/logger.py` (lines 36, 51-60, 127-174, 359-374, 456-466 + comments)
- Modify: `libraries/python/logs/tests/test_logger.py` (imports + config-source tests)
- Modify: `libraries/python/logs/README.md:22-24`

**Interfaces:**
- Produces: public dataclass `ExporterParameters` (was `SsmParameters`), functions `_read_exporter_parameters()`, `_read_exporter_parameters_file()`, `_exporter_parameters_from_json()`, constant `DEFAULT_EXPORTER_PARAMETERS_FILE`. Tasks 3/4 mirror these names in Java/.NET (`ExporterParameters`, `readExporterParameters`, `ReadExporterParameters`).

- [ ] **Step 1: Re-point the config-source tests**

In `tests/test_logger.py` apply exactly (imports at lines 15/20, tests at 88-143 and 186-193):

| Old | New |
|---|---|
| `SsmParameters,` (import) | `ExporterParameters,` |
| `_read_ssm_parameters,` (import) | `_read_exporter_parameters,` |
| `test_read_ssm_parameters_prefers_json_and_falls_back_to_otel_env` | `test_read_exporter_parameters_prefers_json_and_falls_back_to_otel_env` |
| `test_read_ssm_parameters_uses_params_file_before_direct_env` | `test_read_exporter_parameters_uses_params_file_before_direct_env` |
| `test_read_ssm_parameters_falls_back_when_params_file_is_invalid` | `test_read_exporter_parameters_falls_back_when_params_file_is_invalid` |
| `test_ssm_parameters_backend_and_empty_detection` | `test_exporter_parameters_backend_and_empty_detection` |
| `"OTEL_SSM_PARAMETERS"` (all occurrences) | `"OTEL_EXPORTER_PARAMETERS"` |
| `"OTEL_SSM_PARAMETERS_FILE"` (all occurrences) | `"OTEL_EXPORTER_PARAMETERS_FILE"` |
| `_read_ssm_parameters()` (all call sites) | `_read_exporter_parameters()` |
| `SsmParameters()` / `SsmParameters(otel=...)` | `ExporterParameters()` / `ExporterParameters(otel=...)` |
| `#Handles test read SSM parameters ...` comments | `#Handles test read exporter parameters ...` |

- [ ] **Step 2: Run tests to verify they fail on import**

Run: `python -m pytest tests/test_logger.py -v`
Expected: collection error — `ImportError: cannot import name 'ExporterParameters'`.

- [ ] **Step 3: Rename in `logger.py`**

Apply exactly, whole file:

| Old | New |
|---|---|
| `DEFAULT_SSM_PARAMETERS_FILE` (def + uses) | `DEFAULT_EXPORTER_PARAMETERS_FILE` |
| `class SsmParameters:` | `class ExporterParameters:` |
| `SsmParameters(` (all constructions) | `ExporterParameters(` |
| `-> SsmParameters` (all annotations) | `-> ExporterParameters` |
| `_ssm_parameters_from_json` (def + calls) | `_exporter_parameters_from_json` |
| `_read_ssm_parameters_file` (def + calls) | `_read_exporter_parameters_file` |
| `_read_ssm_parameters` (def + calls) | `_read_exporter_parameters` |
| `os.getenv("OTEL_SSM_PARAMETERS")` | `os.getenv("OTEL_EXPORTER_PARAMETERS")` |
| `os.getenv("OTEL_SSM_PARAMETERS_FILE")` | `os.getenv("OTEL_EXPORTER_PARAMETERS_FILE")` |
| `#Handles SSM parameters from JSON.` | `#Handles exporter parameters from JSON.` |
| `#Reads SSM parameters file.` | `#Reads exporter parameters file.` |
| `#Reads SSM parameters.` | `#Reads exporter parameters.` |
| `ssm_parameters` (local vars, lines 359-374) | `exporter_parameters` |

Then delete the Lambda branch in `_current_trace_id` (lines 456-466) so it reads:

```python
#Gets current trace ID.
def _current_trace_id() -> str:
    span_context = _span_context()
    if span_context is not None and getattr(span_context, "is_valid", False):
        return f"{span_context.trace_id:032x}"

    return "unknown"
```

- [ ] **Step 4: Run full suite**

Run: `python -m pytest`
Expected: all PASS. Then `grep -rniE "aws|ssm|lambda|amzn" src/ tests/ README.md` — README hits remain (fixed next step), src/tests clean.

- [ ] **Step 5: Update README**

In `libraries/python/logs/README.md` replace lines 23-24:

```markdown
- `OTEL_EXPORTER_PARAMETERS`: JSON object with `otel.logs.url` and `otel.logs.api_key`.
- `/tmp/otelExporterParams.json`: parameter file fallback. Set `OTEL_EXPORTER_PARAMETERS_FILE` to override the path.
```

Scan the rest of the README for AWS/Lambda/ECS/EKS/SSM mentions (runtime-detection section) and rewrite to Azure Functions / Container Apps / App Service / AKS with the trigger env vars from Task 1. Verify: `grep -rniE "aws|ssm|lambda|amzn|\becs\b|\beks\b" libraries/python/` → empty.

- [ ] **Step 6: Commit**

```bash
git add libraries/python/logs
git commit -m "feat(python): rename SSM parameters to exporter parameters, drop Lambda trace header"
```

---

### Task 3: Java — Azure detection, ExporterParameters, trace-id, README

**Files:**
- Modify: `libraries/java/logs/src/main/java/com/cloudops/otel/logs/RuntimeResourceAttributes.java:23-67`
- Rename: `SsmParameters.java` → `ExporterParameters.java` (same package)
- Modify: `LogsConfiguration.java:11,18-69`
- Modify: `CloudOpsLogger.java:145,161,262-269`
- Rename test: `SsmParametersTest.java` → `ExporterParametersTest.java`
- Modify test: `LogsConfigurationTest.java:45-64`
- Modify: `libraries/java/logs/README.md`

**Interfaces:**
- Consumes: naming convention from Task 2 (`ExporterParameters`).
- Produces: `ExporterParameters` class (fields/methods unchanged: `otel`, `isEmpty()`, `backend(String)`), `LogsConfiguration.readExporterParameters()`, `readExporterParametersFile()`, `readExporterParametersFile(Path)`.

Note: Java has no env-mocking today, so runtime detection has no unit tests (same as the AWS version). Detection is verified live in Task 6.

- [ ] **Step 1: Rename the parameter tests (failing first)**

`git mv src/test/java/com/cloudops/otel/logs/SsmParametersTest.java src/test/java/com/cloudops/otel/logs/ExporterParametersTest.java`, then inside: class `SsmParametersTest` → `ExporterParametersTest`, every `SsmParameters` → `ExporterParameters`, header comment `SSM parameters` → `exporter parameters`.

In `LogsConfigurationTest.java`: `readSsmParametersFileReadsOriginalParamsFile` → `readExporterParametersFileReadsOriginalParamsFile`, `readSsmParametersFileReturnsEmptyForInvalidFile` → `readExporterParametersFileReturnsEmptyForInvalidFile`, `SsmParameters parsed = LogsConfiguration.readSsmParametersFile(paramsFile)` → `ExporterParameters parsed = LogsConfiguration.readExporterParametersFile(paramsFile)` (both tests), comments likewise.

- [ ] **Step 2: Run to verify compile failure**

Run (from `libraries/java/logs`): `mvn -q test`
Expected: COMPILATION ERROR — `cannot find symbol: class ExporterParameters`.

- [ ] **Step 3: Rename production classes**

`git mv src/main/java/com/cloudops/otel/logs/SsmParameters.java src/main/java/com/cloudops/otel/logs/ExporterParameters.java`; inside: class name → `ExporterParameters`, header comment → `// This file contains exporter parameters logic for OTel logs.`

`LogsConfiguration.java`:

| Old | New |
|---|---|
| `DEFAULT_SSM_PARAMETERS_FILE` | `DEFAULT_EXPORTER_PARAMETERS_FILE` |
| `readSsmParameters()` | `readExporterParameters()` |
| `readSsmParametersFile()` / `(Path)` | `readExporterParametersFile()` / `(Path)` |
| `System.getenv("OTEL_SSM_PARAMETERS")` | `System.getenv("OTEL_EXPORTER_PARAMETERS")` |
| `System.getenv("OTEL_SSM_PARAMETERS_FILE")` | `System.getenv("OTEL_EXPORTER_PARAMETERS_FILE")` |
| every `SsmParameters` type use | `ExporterParameters` |
| `// Reads SSM parameters...` comments | `// Reads exporter parameters...` |

`CloudOpsLogger.java`: line 145 `SsmParameters ssmParameters = LogsConfiguration.readSsmParameters();` → `ExporterParameters exporterParameters = LogsConfiguration.readExporterParameters();`; line 161 `private void initialiseOtel(SsmParameters ssmParameters)` → `private void initialiseOtel(ExporterParameters exporterParameters)` (update body references `ssmParameters` → `exporterParameters`). Replace `currentTraceId()` (lines 262-269) with:

```java
  // Gets current trace ID.
  private static String currentTraceId() {
    SpanContext spanContext = Span.current().getSpanContext();
    return spanContext.isValid() ? spanContext.getTraceId() : "unknown";
  }
```

- [ ] **Step 4: Swap the detection ladder**

In `RuntimeResourceAttributes.java`, line 27: `"AWS_LAMBDA_FUNCTION_NAME"` → `"WEBSITE_SITE_NAME"`. Add constant `private static final String ATTR_CLOUD_PROVIDER = "cloud.provider";` after line 10. Replace `addRuntimeAttributes` (lines 34-67) with:

```java
  // Adds runtime attributes.
  private static void addRuntimeAttributes(Map<String, String> attributes) {
    if (hasValue(firstEnv("FUNCTIONS_EXTENSION_VERSION", "FUNCTIONS_WORKER_RUNTIME"))) {
      attributes.put(ATTR_CLOUD_PROVIDER, "azure");
      attributes.put(ATTR_CLOUD_PLATFORM, "azure_functions");
      String siteName = env("WEBSITE_SITE_NAME");
      if (hasValue(siteName)) {
        attributes.put(ATTR_FAAS_NAME, siteName);
      }
      return;
    }

    if (hasValue(env("CONTAINER_APP_NAME"))) {
      attributes.put(ATTR_CLOUD_PROVIDER, "azure");
      attributes.put(ATTR_CLOUD_PLATFORM, "azure_container_apps");
    }

    if (hasValue(env("WEBSITE_SITE_NAME"))) {
      attributes.put(ATTR_CLOUD_PROVIDER, "azure");
      attributes.put(ATTR_CLOUD_PLATFORM, "azure_app_service");
    }

    boolean runningOnKubernetes = hasValue(env("KUBERNETES_SERVICE_HOST"));
    String k8sClusterName = firstEnv("K8S_CLUSTER_NAME", "AKS_CLUSTER_NAME");
    String k8sNamespaceName = firstEnv("K8S_NAMESPACE_NAME", "POD_NAMESPACE");
    String k8sNodeName = firstEnv("K8S_NODE_NAME", "NODE_NAME");
    String k8sPodName = firstEnv("K8S_POD_NAME", "POD_NAME");
    if (!hasValue(k8sPodName) && runningOnKubernetes) {
      k8sPodName = env("HOSTNAME");
    }

    if (runningOnKubernetes || hasValue(k8sClusterName) || hasValue(k8sNamespaceName) || hasValue(k8sPodName)) {
      attributes.put(ATTR_CLOUD_PROVIDER, "azure");
      attributes.put(ATTR_CLOUD_PLATFORM, "azure_aks");
    }

    putIfPresent(attributes, ATTR_K8S_CLUSTER_NAME, k8sClusterName);
    putIfPresent(attributes, ATTR_K8S_NAMESPACE_NAME, k8sNamespaceName);
    putIfPresent(attributes, ATTR_K8S_NODE_NAME, k8sNodeName);
    putIfPresent(attributes, ATTR_K8S_POD_NAME, k8sPodName);
    putIfPresent(attributes, ATTR_CONTAINER_ID, env("CONTAINER_ID"));
    putIfPresent(attributes, ATTR_CONTAINER_NAME, firstEnv("CONTAINER_NAME", "CONTAINER_APP_NAME"));
  }
```

- [ ] **Step 5: Run tests**

Run: `mvn -q test`
Expected: BUILD SUCCESS, all tests + JaCoCo gate green.

- [ ] **Step 6: Update README + verify no AWS strings**

`libraries/java/logs/README.md`: line 24 SSM bullet → same replacement text as Python Task 2 Step 5 (`OTEL_EXPORTER_PARAMETERS` / `OTEL_EXPORTER_PARAMETERS_FILE`); rewrite any AWS runtime-detection prose to the Azure ladder. Verify: `grep -rniE "aws|ssm|lambda|amzn|\becs\b|\beks\b" libraries/java/` → empty.

- [ ] **Step 7: Commit**

```bash
git add libraries/java/logs
git commit -m "feat(java): Azure runtime detection and exporter-parameters rename"
```

---

### Task 4: .NET — Azure detection, ExporterParameters, trace-id, README

**Files:**
- Modify: `libraries/dotnet/logs/tests/EnvironmentScope.cs:6-37`
- Modify: `libraries/dotnet/logs/tests/RuntimeResourceAttributesTests.cs`
- Modify: `libraries/dotnet/logs/tests/LogsConfigurationTests.cs` (all `Ssm`/`OTEL_SSM_*`)
- Modify: `libraries/dotnet/logs/tests/CloudOpsLoggerTests.cs` (any `Ssm` references)
- Rename: `src/SsmParameters.cs` → `src/ExporterParameters.cs`
- Modify: `src/LogsConfiguration.cs`, `src/RuntimeResourceAttributes.cs`, `src/CloudOpsLogger.cs:221-229`
- Modify: `libraries/dotnet/logs/README.md`

**Interfaces:**
- Consumes: naming from Task 2 (`ExporterParameters`).
- Produces: `ExporterParameters` class (`Otel`, `IsEmpty()`, `Backend(string)` unchanged), `LogsConfiguration.ReadExporterParameters()`.

- [ ] **Step 1: Update EnvironmentScope telemetry keys**

In `EnvironmentScope.cs` replace the `TelemetryKeys` array entries: delete `"AWS_LAMBDA_FUNCTION_NAME"`, `"ECS_CONTAINER_METADATA_FILE"`, `"ECS_CONTAINER_METADATA_URI"`, `"ECS_CONTAINER_METADATA_URI_V4"`, `"ECS_CONTAINER_NAME"`, `"EKS_CLUSTER_NAME"`, `"_X_AMZN_TRACE_ID"`; rename `"OTEL_SSM_PARAMETERS"` → `"OTEL_EXPORTER_PARAMETERS"`, `"OTEL_SSM_PARAMETERS_FILE"` → `"OTEL_EXPORTER_PARAMETERS_FILE"`; add `"AKS_CLUSTER_NAME"`, `"CONTAINER_APP_NAME"`, `"FUNCTIONS_EXTENSION_VERSION"`, `"FUNCTIONS_WORKER_RUNTIME"`, `"WEBSITE_SITE_NAME"` (keep the list alphabetised).

- [ ] **Step 2: Write failing Azure detection tests**

In `RuntimeResourceAttributesTests.cs`, replace `LambdaAttributesAreDetected` with (keep `ServiceNameEnvironmentOverridesResourceAttributes`):

```csharp
    [Fact]
    // Handles functions attributes are detected.
    public void FunctionsAttributesAreDetected()
    {
        using var env = new EnvironmentScope(new Dictionary<string, string?>
        {
            ["FUNCTIONS_EXTENSION_VERSION"] = "~4",
            ["WEBSITE_SITE_NAME"] = "orders-func"
        });

        var attributes = RuntimeResourceAttributes.Create();

        Assert.Equal("orders-func", attributes["service.name"]);
        Assert.Equal("azure", attributes["cloud.provider"]);
        Assert.Equal("azure_functions", attributes["cloud.platform"]);
        Assert.Equal("orders-func", attributes["faas.name"]);
    }

    [Fact]
    // Handles functions detection early-returns before kubernetes attributes.
    public void FunctionsDetectionSkipsKubernetesAttributes()
    {
        using var env = new EnvironmentScope(new Dictionary<string, string?>
        {
            ["FUNCTIONS_WORKER_RUNTIME"] = "dotnet-isolated",
            ["WEBSITE_SITE_NAME"] = "orders-func",
            ["KUBERNETES_SERVICE_HOST"] = "10.0.0.1"
        });

        var attributes = RuntimeResourceAttributes.Create();

        Assert.Equal("azure_functions", attributes["cloud.platform"]);
        Assert.False(attributes.ContainsKey("k8s.pod.name"));
    }

    [Fact]
    // Handles container apps attributes are detected.
    public void ContainerAppsAttributesAreDetected()
    {
        using var env = new EnvironmentScope(new Dictionary<string, string?>
        {
            ["OTEL_SERVICE_NAME"] = "order-api",
            ["CONTAINER_APP_NAME"] = "orders-ca"
        });

        var attributes = RuntimeResourceAttributes.Create();

        Assert.Equal("azure", attributes["cloud.provider"]);
        Assert.Equal("azure_container_apps", attributes["cloud.platform"]);
        Assert.Equal("orders-ca", attributes["container.name"]);
    }

    [Fact]
    // Handles app service attributes are detected.
    public void AppServiceAttributesAreDetected()
    {
        using var env = new EnvironmentScope(new Dictionary<string, string?>
        {
            ["WEBSITE_SITE_NAME"] = "orders-web"
        });

        var attributes = RuntimeResourceAttributes.Create();

        Assert.Equal("orders-web", attributes["service.name"]);
        Assert.Equal("azure_app_service", attributes["cloud.platform"]);
        Assert.False(attributes.ContainsKey("faas.name"));
    }

    [Fact]
    // Handles container apps with kubernetes signals fall through to AKS.
    public void ContainerAppsWithKubernetesFallsThroughToAks()
    {
        using var env = new EnvironmentScope(new Dictionary<string, string?>
        {
            ["CONTAINER_APP_NAME"] = "orders-ca",
            ["KUBERNETES_SERVICE_HOST"] = "10.0.0.1"
        });

        var attributes = RuntimeResourceAttributes.Create();

        Assert.Equal("azure_aks", attributes["cloud.platform"]);
        Assert.Equal("orders-ca", attributes["container.name"]);
    }

    [Fact]
    // Handles AKS attributes are detected.
    public void AksAttributesAreDetected()
    {
        using var env = new EnvironmentScope(new Dictionary<string, string?>
        {
            ["OTEL_SERVICE_NAME"] = "order-api",
            ["KUBERNETES_SERVICE_HOST"] = "10.0.0.1",
            ["AKS_CLUSTER_NAME"] = "cloudops-dev",
            ["K8S_POD_NAME"] = "order-api-abc"
        });

        var attributes = RuntimeResourceAttributes.Create();

        Assert.Equal("azure", attributes["cloud.provider"]);
        Assert.Equal("azure_aks", attributes["cloud.platform"]);
        Assert.Equal("cloudops-dev", attributes["k8s.cluster.name"]);
        Assert.Equal("order-api-abc", attributes["k8s.pod.name"]);
    }
```

Also in `LogsConfigurationTests.cs`: method names `ReadSsmParameters*` → `ReadExporterParameters*`, calls `LogsConfiguration.ReadSsmParameters()` → `LogsConfiguration.ReadExporterParameters()`, env keys `OTEL_SSM_PARAMETERS`/`OTEL_SSM_PARAMETERS_FILE` → `OTEL_EXPORTER_PARAMETERS`/`OTEL_EXPORTER_PARAMETERS_FILE`, comments `SSM` → `exporter`. Same sweep in `CloudOpsLoggerTests.cs` if it references `Ssm` (grep first).

- [ ] **Step 3: Run tests to verify failure**

Run (from `libraries/dotnet/logs`): `dotnet test`
Expected: compile errors (`ReadExporterParameters` not found) — confirms tests point at the new API.

- [ ] **Step 4: Implement src changes**

`git mv src/SsmParameters.cs src/ExporterParameters.cs`; inside: class `SsmParameters` → `ExporterParameters`, header comment → `// This file contains exporter parameters logic for logs src.`

`LogsConfiguration.cs`: `ReadSsmParameters` → `ReadExporterParameters` (+ any `ReadSsmParametersFile` helper), `OTEL_SSM_PARAMETERS`/`OTEL_SSM_PARAMETERS_FILE` env names → new names, `SsmParameters` type uses → `ExporterParameters`, `DEFAULT_SSM`-style const → `DefaultExporterParametersFile` naming kept consistent with file's existing const style, comments `SSM` → `exporter`.

`CloudOpsLogger.cs`: update `ReadSsmParameters()` call site + local `ssmParameters` variable names → `exporterParameters`; replace `CurrentTraceId()` (lines 221-229) with:

```csharp
    // Gets current trace ID.
    private static string CurrentTraceId()
    {
        var activity = System.Diagnostics.Activity.Current;
        return activity?.TraceId.ToString() ?? "unknown";
    }
```

`RuntimeResourceAttributes.cs`: line 23 `AWS_LAMBDA_FUNCTION_NAME` → `WEBSITE_SITE_NAME`; add `private const string AttrCloudProvider = "cloud.provider";`; replace `AddRuntimeAttributes` (lines 32-69) with:

```csharp
    // Adds runtime attributes.
    private static void AddRuntimeAttributes(Dictionary<string, string> attributes)
    {
        if (HasValue(FirstEnv("FUNCTIONS_EXTENSION_VERSION", "FUNCTIONS_WORKER_RUNTIME")))
        {
            attributes[AttrCloudProvider] = "azure";
            attributes[AttrCloudPlatform] = "azure_functions";
            var siteName = Environment.GetEnvironmentVariable("WEBSITE_SITE_NAME");
            if (HasValue(siteName))
            {
                attributes[AttrFaasName] = siteName!;
            }
            return;
        }

        if (HasValue(Environment.GetEnvironmentVariable("CONTAINER_APP_NAME")))
        {
            attributes[AttrCloudProvider] = "azure";
            attributes[AttrCloudPlatform] = "azure_container_apps";
        }

        if (HasValue(Environment.GetEnvironmentVariable("WEBSITE_SITE_NAME")))
        {
            attributes[AttrCloudProvider] = "azure";
            attributes[AttrCloudPlatform] = "azure_app_service";
        }

        var runningOnKubernetes = HasValue(Environment.GetEnvironmentVariable("KUBERNETES_SERVICE_HOST"));
        var k8sClusterName = FirstEnv("K8S_CLUSTER_NAME", "AKS_CLUSTER_NAME");
        var k8sNamespaceName = FirstEnv("K8S_NAMESPACE_NAME", "POD_NAMESPACE");
        var k8sNodeName = FirstEnv("K8S_NODE_NAME", "NODE_NAME");
        var k8sPodName = FirstEnv("K8S_POD_NAME", "POD_NAME");
        if (!HasValue(k8sPodName) && runningOnKubernetes)
        {
            k8sPodName = Environment.GetEnvironmentVariable("HOSTNAME");
        }

        if (runningOnKubernetes || HasValue(k8sClusterName) || HasValue(k8sNamespaceName) || HasValue(k8sPodName))
        {
            attributes[AttrCloudProvider] = "azure";
            attributes[AttrCloudPlatform] = "azure_aks";
        }

        PutIfPresent(attributes, AttrK8sClusterName, k8sClusterName);
        PutIfPresent(attributes, AttrK8sNamespaceName, k8sNamespaceName);
        PutIfPresent(attributes, AttrK8sNodeName, k8sNodeName);
        PutIfPresent(attributes, AttrK8sPodName, k8sPodName);
        PutIfPresent(attributes, AttrContainerId, Environment.GetEnvironmentVariable("CONTAINER_ID"));
        PutIfPresent(attributes, AttrContainerName, FirstEnv("CONTAINER_NAME", "CONTAINER_APP_NAME"));
    }
```

- [ ] **Step 5: Run tests**

Run: `dotnet test`
Expected: all PASS, coverage gate green.

- [ ] **Step 6: Update README + verify**

`libraries/dotnet/logs/README.md`: SSM bullet (line 24 area) → `OTEL_EXPORTER_PARAMETERS` text as in Task 2 Step 5; Azure-ify any runtime-detection prose. Verify: `grep -rniE "aws|ssm|lambda|amzn|\becs\b|\beks\b" libraries/dotnet/ --include="*.cs" --include="*.md"` → empty (exclude `bin/`/`obj/`).

- [ ] **Step 7: Commit**

```bash
git add libraries/dotnet/logs
git commit -m "feat(dotnet): Azure runtime detection and exporter-parameters rename"
```

---

### Task 5: Docs sweep (CLAUDE.md, libraries README) + acceptance grep

**Files:**
- Modify: `CLAUDE.md` (shared-design bullet, env contract, AWS detection paragraph)
- Modify: `libraries/README.md` (if it mentions AWS/SSM — grep first)

- [ ] **Step 1: Update CLAUDE.md**

Replace the shared-design bullet: `` `LogsExporterConfig` / `BackendConfig` / `SsmParameters` — exporter config, resolved from env vars, an inline `OTEL_SSM_PARAMETERS` JSON blob, or the SSM parameters file (`/tmp/otelExporterParams.json` by default). `` →

```markdown
- `LogsExporterConfig` / `BackendConfig` / `ExporterParameters` — exporter config,
  resolved from env vars, an inline `OTEL_EXPORTER_PARAMETERS` JSON blob, or the
  exporter parameters file (`/tmp/otelExporterParams.json` by default).
```

Replace the `RuntimeResourceAttributes` bullet's `detects the AWS runtime (Lambda / ECS / EKS / plain Kubernetes)` → `detects the Azure runtime (Functions / Container Apps / App Service / AKS)`.

Replace the env-contract bullet `` `OTEL_SSM_PARAMETERS` (inline JSON) / `OTEL_SSM_PARAMETERS_FILE` — exporter config source; falls back to `/tmp/otelExporterParams.json`. `` → same text with `OTEL_EXPORTER_PARAMETERS` / `OTEL_EXPORTER_PARAMETERS_FILE`.

Replace the paragraph `AWS runtime auto-detection uses ...` →

```markdown
Azure runtime auto-detection uses `FUNCTIONS_EXTENSION_VERSION`/`FUNCTIONS_WORKER_RUNTIME`,
`WEBSITE_SITE_NAME`, `CONTAINER_APP_NAME`, `KUBERNETES_SERVICE_HOST`, `K8S_*`/`POD_*`, etc.
```

- [ ] **Step 2: Acceptance grep**

Run: `grep -rniE "aws|ssm|lambda|amzn|\becs\b|\beks\b" libraries/ CLAUDE.md`
Expected: no output. Any hit → fix it, re-run.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md libraries/README.md
git commit -m "docs: Azure runtime detection and exporter-parameters contract"
```

---

### Task 6: Live end-to-end verification via demo stack

**Files:** none committed (temp override file only).

- [ ] **Step 1: Rebuild library artifacts + app images**

```bash
bash demo/scripts/build-libs.sh
docker compose -f demo/docker-compose.yml up -d --build python-app java-app dotnet-app
```

- [ ] **Step 2: Azure runtime override**

Write `/tmp/azure-runtime-test.yml`:

```yaml
services:
  python-app:
    environment:
      FUNCTIONS_EXTENSION_VERSION: "~4"
      WEBSITE_SITE_NAME: fake-orders-func
  java-app:
    environment:
      KUBERNETES_SERVICE_HOST: 10.0.0.1
      AKS_CLUSTER_NAME: demo-aks
      POD_NAMESPACE: demo-ns
  dotnet-app:
    environment:
      CONTAINER_APP_NAME: fake-orders-ca
```

Run: `docker compose -f demo/docker-compose.yml -f /tmp/azure-runtime-test.yml up -d python-app java-app dotnet-app`

- [ ] **Step 3: Assert in Loki (wait ~45s for traffic)**

Query each service's latest entry stream metadata (`curl -G http://localhost:3100/loki/api/v1/query_range --data-urlencode 'query={service_name="python-app"}' --data-urlencode limit=1`).
Expected:
- python-app: `cloud_provider=azure`, `cloud_platform=azure_functions`, `faas_name=fake-orders-func`
- java-app: `cloud_provider=azure`, `cloud_platform=azure_aks`, `k8s_cluster_name=demo-aks`, `k8s_namespace_name=demo-ns`
- dotnet-app: `cloud_provider=azure`, `cloud_platform=azure_container_apps`, `container_name=fake-orders-ca`

- [ ] **Step 4: Revert to clean env**

Run: `docker compose -f demo/docker-compose.yml up -d python-app java-app dotnet-app`
Confirm baseline entries carry no `cloud_platform`.
