# Package Three OTel Logs Libraries — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make each of the three CloudOps OTel logs libraries (Python, Java, .NET) reliably build its distributable artifact locally, and prove a consumer can install that artifact and call `CloudOpsLogger`.

**Architecture:** Verify-first, minimal-fix. For each language: run the standard build command, observe the result, change project config **only** if it demonstrably blocks a clean artifact, then run a throwaway "install the package and call the logger" smoke test in a temp directory. No new committed files, no registry publishing.

**Tech Stack:** Python 3.11+ / hatchling / `build`; Java 21 / Maven; .NET / net8.0 / `dotnet pack`. Commands run from each library's own directory. Shell is PowerShell (primary) with a Bash tool available; paths are Windows.

## Global Constraints

- Readiness bar: **buildable artifacts only** — no registry publishing, publish scripts, or CI.
- Registry target: **unspecified/local** — metadata must be valid and portable; do **not** add registry-only metadata (license files, source/symbol jars, SCM URLs) unless the build fails without it.
- **No behavioural changes** to any library; no changes to the shared design or the `OTEL_*` env-var contract.
- Keep the three ports behaviourally in sync — but this task changes packaging config only, so no cross-port source edits are expected.
- **No AI/Claude/Anthropic attribution** and **no `Co-Authored-By`** lines in commit messages (per project CLAUDE.md).
- Smoke tests are **throwaway** — build them in the scratchpad/temp dir, never commit them.
- Do **not** commit build artifacts (`dist/`, `target/`, `bin/`, `obj/`, `*.nupkg`, `__pycache__/`).
- Java runtime is **21** (documented). If only an incompatible JDK is available, report a toolchain blocker with exact remediation — do **not** downgrade `maven.compiler.release`.
- Scratchpad for temp files: `C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Desktop-OtelLibraries\4d3d0fd0-16f4-40e7-92e4-0066da5246ce\scratchpad`

---

### Task 1: Python — build wheel/sdist and smoke-test

**Files:**
- Modify (only if build requires it): `libraries/python/logs/pyproject.toml`
- Throwaway (do not commit): a smoke-test script + temp venv under the scratchpad dir

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: a confirmed-buildable Python package. No API surface for later tasks.

- [ ] **Step 1: Run the build (this is the failing/observing test)**

From `libraries/python/logs`, using an isolated venv so project deps are untouched:

```bash
cd "C:/Users/user/Desktop/OtelLibraries/libraries/python/logs"
python -m venv "$SCRATCH/pybuild" && "$SCRATCH/pybuild/Scripts/python" -m pip install -q build
"$SCRATCH/pybuild/Scripts/python" -m build --outdir "$SCRATCH/pydist" .
```
(`$SCRATCH` = the scratchpad path from Global Constraints.)

Expected: produces `cloudops_otel_logs-0.1.0-py3-none-any.whl` and `cloudops_otel_logs-0.1.0.tar.gz` in `$SCRATCH/pydist`. If it succeeds, **make no changes** to `pyproject.toml`.

- [ ] **Step 2: Diagnose only if it failed**

If the build errors, read the exact error. Apply the **minimal** hatchling fix (e.g. an sdist `include`/`packages` entry, or the readme path). Do not add license/registry metadata. Re-run Step 1 until the wheel + sdist are produced.

- [ ] **Step 3: Smoke test — install the artifact and call the logger**

```bash
python -m venv "$SCRATCH/pysmoke"
"$SCRATCH/pysmoke/Scripts/python" -m pip install -q "$SCRATCH/pydist/cloudops_otel_logs-0.1.0-py3-none-any.whl"
```

Write `$SCRATCH/py_smoke.py`:

```python
from cloudops_otel_logs import CloudOpsLogger

logger = CloudOpsLogger(service_name="smoke-test")
logger.info("hello from the packaged wheel")
logger.export_logs()
print("PY_SMOKE_OK")
```

Note: confirm the constructor/import names against `libraries/python/logs/src/cloudops_otel_logs/__init__.py` before running; use whatever the public API actually exposes (fix the smoke script, not the library).

Run:
```bash
"$SCRATCH/pysmoke/Scripts/python" "$SCRATCH/py_smoke.py"
```
Expected: prints a log line then `PY_SMOKE_OK`, exit 0.

- [ ] **Step 4: Run the existing test suite (regression guard)**

Only needed if Step 2 changed a file. From `libraries/python/logs`:
```bash
"$SCRATCH/pybuild/Scripts/python" -m pip install -q -e ".[dev]"
"$SCRATCH/pybuild/Scripts/python" -m pytest -q
```
Expected: all tests pass.

- [ ] **Step 5: Commit (only if a file changed)**

If `pyproject.toml` was modified:
```bash
cd "C:/Users/user/Desktop/OtelLibraries"
git add libraries/python/logs/pyproject.toml
git commit -m "build(python): make cloudops-otel-logs build a clean wheel/sdist"
```
If nothing changed, record "Python already builds; no changes" and move on.

---

### Task 2: .NET — pack the NuGet package and smoke-test

**Files:**
- Modify (only if pack requires it): `libraries/dotnet/logs/CloudOps.Otel.Logs.csproj`
- Throwaway (do not commit): temp console project + local NuGet source under the scratchpad dir

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: a confirmed-packable `.nupkg`. No API surface for later tasks.

- [ ] **Step 1: Confirm the net8.0 targeting pack, then pack (observing test)**

```bash
cd "C:/Users/user/Desktop/OtelLibraries/libraries/dotnet/logs"
dotnet pack -c Release -o "$SCRATCH/nupkgs"
```
Expected: produces `CloudOps.Otel.Logs.0.1.0.nupkg` in `$SCRATCH/nupkgs`. If pack fails complaining the **net8.0 targeting pack** is missing, install it (`dotnet workload`/reference pack — an SDK/environment fix, **not** a csproj change) and re-run. If pack succeeds, **make no changes** to the csproj.

- [ ] **Step 2: Diagnose only if it failed for a project reason**

If pack fails for a project-config reason (not a missing pack), read the error and apply the minimal csproj fix (e.g. a genuinely missing `PackageReadmeFile` path — but README.md is already confirmed present). Do not add license/registry metadata. Re-run Step 1.

- [ ] **Step 3: Smoke test — consume the .nupkg and call the logger**

```bash
mkdir -p "$SCRATCH/netsmoke" && cd "$SCRATCH/netsmoke"
dotnet new console -n Smoke -o . 2>/dev/null || dotnet new console --force
dotnet nuget add source "$SCRATCH/nupkgs" -n localpkgs 2>/dev/null || true
dotnet add package CloudOps.Otel.Logs --version 0.1.0 --source "$SCRATCH/nupkgs"
```

Replace `$SCRATCH/netsmoke/Program.cs` with a minimal consumer that constructs `CloudOpsLogger` and calls `Info(...)` — confirm the exact public constructor/method names against `libraries/dotnet/logs/src/CloudOpsLogger.cs` first, and match them. End the program by printing `NET_SMOKE_OK`.

Run:
```bash
cd "$SCRATCH/netsmoke" && dotnet run -c Release
```
Expected: prints a log line then `NET_SMOKE_OK`, exit 0.

- [ ] **Step 4: Run the existing test suite (regression guard)**

Only needed if Step 2 changed a file. From `libraries/dotnet/logs`:
```bash
dotnet test
```
Expected: all tests pass.

- [ ] **Step 5: Commit (only if a file changed)**

If the csproj was modified:
```bash
cd "C:/Users/user/Desktop/OtelLibraries"
git add libraries/dotnet/logs/CloudOps.Otel.Logs.csproj
git commit -m "build(dotnet): make CloudOps.Otel.Logs pack a clean NuGet package"
```
If nothing changed, record "NET already packs; no changes" and move on.

---

### Task 3: Java — remove dead deploy config, build the jar, smoke-test

**Files:**
- Modify: `libraries/java/logs/pom.xml` (remove the `<distributionManagement>` block, lines 114–120)
- Throwaway (do not commit): a temp consumer `.java` + classpath under the scratchpad dir

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: a confirmed-buildable jar under `target/`. No API surface for later tasks.

- [ ] **Step 1: Verify a Java 21 toolchain is available**

```bash
java -version
```
The pom requires `maven.compiler.release=21`. If the default JDK is < 21, locate a JDK 21 and set `JAVA_HOME` to it for the build commands. If no JDK 21 can be provisioned in this environment, **stop this task** and report: "Java build blocked — needs JDK 21; the environment has JDK <version>. Remediation: install a JDK 21 (e.g. Temurin 21) and set JAVA_HOME." Do **not** lower `maven.compiler.release`.

- [ ] **Step 2: Remove the dead `distributionManagement` block**

In `libraries/java/logs/pom.xml`, delete exactly this block (it points at the old monorepo's CodeArtifact endpoint `${env.CODEARTIFACT_MAVEN_ENDPOINT}`, which does not exist in this repo):

```xml
  <distributionManagement>
    <repository>
      <id>codeartifact</id>
      <name>CloudOps CodeArtifact Maven</name>
      <url>${env.CODEARTIFACT_MAVEN_ENDPOINT}</url>
    </repository>
  </distributionManagement>
```

Leave everything else in the pom unchanged.

- [ ] **Step 3: Build the jar (observing test)**

```bash
cd "C:/Users/user/Desktop/OtelLibraries/libraries/java/logs"
mvn -q -DskipTests package
```
Expected: produces `target/otel-logs-0.1.0.jar`. (`-DskipTests` isolates the packaging step from the coverage gate; the full suite runs in Step 5.) If it fails, read the error; the only expected in-scope failure is toolchain (Step 1). Do not add source/javadoc plugins.

- [ ] **Step 4: Smoke test — compile a consumer against the jar and run it**

Build a runtime classpath from the built jar plus its transitive deps:
```bash
cd "C:/Users/user/Desktop/OtelLibraries/libraries/java/logs"
mvn -q dependency:build-classpath -Dmdep.outputFile="$SCRATCH/java_cp.txt" -Dmdep.includeScope=runtime
```
Write `$SCRATCH/Smoke.java` that imports `com.cloudops.otel.logs.CloudOpsLogger`, constructs it, and calls `info(...)` — confirm the exact public constructor/method against `libraries/java/logs/src/main/java/com/cloudops/otel/logs/CloudOpsLogger.java` first. Print `JAVA_SMOKE_OK` at the end.

Compile and run with the library jar + deps on the classpath (use `;` as the Windows classpath separator):
```bash
CP="target/otel-logs-0.1.0.jar;$(cat $SCRATCH/java_cp.txt)"
javac -cp "$CP" -d "$SCRATCH/javaout" "$SCRATCH/Smoke.java"
java -cp "$CP;$SCRATCH/javaout" Smoke
```
Expected: prints a log line then `JAVA_SMOKE_OK`, exit 0.

- [ ] **Step 5: Run the existing test suite (regression guard)**

```bash
cd "C:/Users/user/Desktop/OtelLibraries/libraries/java/logs"
mvn -q verify
```
Expected: unit tests pass and the JaCoCo coverage gate (line ≥ 0.50) is met. Confirms removing `distributionManagement` broke nothing.

- [ ] **Step 6: Commit**

```bash
cd "C:/Users/user/Desktop/OtelLibraries"
git add libraries/java/logs/pom.xml
git commit -m "build(java): drop dead CodeArtifact deploy config; build a clean jar"
```

---

### Task 4: Final verification and summary

**Files:** none (verification only).

**Interfaces:**
- Consumes: the confirmed builds from Tasks 1–3.
- Produces: a final status report.

- [ ] **Step 1: Confirm a clean working tree except intended changes**

```bash
cd "C:/Users/user/Desktop/OtelLibraries"
git status
git log --oneline -6
```
Expected: only the intended packaging commit(s) present; no artifacts (`dist/`, `target/`, `bin/`, `obj/`, `*.nupkg`) staged or committed.

- [ ] **Step 2: Report per-language outcome**

State, for each language: the exact build command, that the artifact was produced, that the smoke test printed its `*_OK` marker, and whether any file changed. Explicitly call out any toolchain blocker (most likely Java/JDK 21) with its remediation.

---

## Self-Review

**1. Spec coverage:**
- Python wheel/sdist build + smoke test → Task 1. ✓
- .NET `.nupkg` pack + smoke test → Task 2. ✓
- Java jar build + smoke test → Task 3. ✓
- Remove dead `distributionManagement` (spec's only planned source-config change) → Task 3 Step 2. ✓
- JDK-21 toolchain risk handled without downgrading → Task 3 Step 1 + Global Constraints. ✓
- .NET net8.0 targeting-pack risk → Task 2 Step 1. ✓
- No new committed files / no artifacts committed → Global Constraints + Task 4 Step 1. ✓
- Existing suites still pass → regression steps in each task. ✓
- No gaps found.

**2. Placeholder scan:** No "TBD/TODO/handle edge cases". The smoke-test scripts intentionally defer exact API names to verification against the real source files (the public constructor/method names), which is a correctness safeguard, not a placeholder — the plan names the file to check in each case.

**3. Type consistency:** No shared types across tasks (each task is an independent build target). Marker strings are distinct per language (`PY_SMOKE_OK`, `NET_SMOKE_OK`, `JAVA_SMOKE_OK`). Consistent.
