# Make the three OTel logs libraries buildable as distributable packages

Date: 2026-07-07

## Goal

Make each of the three CloudOps OTel logs libraries reliably build its
distributable artifact locally:

- **Python** (`libraries/python/logs`) → wheel + sdist (`pip`/PyPI-style)
- **Java** (`libraries/java/logs`) → jar (Maven)
- **.NET** (`libraries/dotnet/logs`) → NuGet package (`.nupkg`)

A downstream consumer should be able to install the produced artifact and
immediately call `CloudOpsLogger`.

## Scope

- **Readiness bar:** *buildable artifacts*. Each library reliably produces its
  artifact via the standard local command. **No** registry publishing, publish
  scripts, or CI.
- **Registry target:** *unspecified / local*. Metadata must be valid and
  portable, not tailored to PyPI / Maven Central / NuGet.org specifically. No
  speculative registry-only metadata (license files, source/symbol jars, SCM
  URLs) unless something blocks the build without it.

## Non-goals

- No instrumentation of any consumer application (there is none in this repo).
- No behavioural changes to the libraries; no changes to the shared design or
  the `OTEL_*` env-var contract.
- No new committed example/demo apps. Smoke tests are throwaway (temp dirs),
  used only to verify, then discarded.
- No full public-registry metadata pass (explicitly out of scope per the
  chosen readiness bar).

## Approach: verify-first, minimal-fix

Actually run each build. Only change files that are **demonstrably** blocking a
clean artifact. After each artifact builds, do a throwaway "install the package
and call the logger" smoke test to prove the artifact is consumable.

## Per-language plan

### Python
- Build command: `python -m build` (produces wheel + sdist).
  - Toolchain gap: the `build` module is not installed. Install it into a
    throwaway venv (do not modify project deps).
- pyproject.toml (hatchling) already declares name, version, deps, and the
  wheel package path. Expected changes: **none** unless the build reveals a gap
  (e.g. sdist missing files).
- Smoke test: in a fresh temp venv, `pip install <wheel>`, then run a tiny
  script that imports and instantiates `CloudOpsLogger` and calls `info(...)`.

### Java
- Build command: `mvn -q package` (produces the jar under `target/`).
- **Toolchain gap (blocker):** pom targets `maven.compiler.release=21`; only
  JDK 17 is installed in this environment, so compilation targeting release 21
  will fail. Java 21 is the documented runtime — do **not** downgrade the
  library. Resolution: build against a JDK 21 (install/point Maven at one via
  `JAVA_HOME`). If a JDK 21 cannot be made available, report the build as
  blocked on the toolchain rather than altering the target.
- **Config cleanup:** remove the `<distributionManagement>` block that points at
  `${env.CODEARTIFACT_MAVEN_ENDPOINT}`. That is leftover from the original
  monorepo's CodeArtifact deploy pipeline, which CLAUDE.md states was **not**
  copied here. It is dead config referencing infra that does not exist in this
  repo. It does not break `package`, but it is misleading for a repo trimmed to
  isolation, and this task is specifically about packaging config. Removing it
  does not affect the produced jar.
- Smoke test: compile a tiny consumer `.java` against the built jar (plus the
  runtime OTel/Jackson deps on the classpath) that constructs `CloudOpsLogger`
  and calls `info(...)`; run it.

### .NET
- Build command: `dotnet pack` (produces the `.nupkg` under `bin/`).
  - Possible toolchain gap: environment has the .NET 10 SDK; project targets
    net8.0. Verify the net8.0 targeting pack is present; the SDK can build
    net8.0 with it. If missing, install the pack (environment change, not a
    project change).
- csproj already sets PackageId, Version, Description, and `PackageReadmeFile`
  (README.md confirmed present). Expected changes: **none** unless pack reveals
  a gap.
- Smoke test: in a temp console project, add the `.nupkg` via a local NuGet
  source, reference the package, construct `CloudOpsLogger`, call `info(...)`,
  run it.

## Verification / done criteria

For each language, "done" means:

1. The standard build command produces the artifact with no errors.
2. A throwaway consumer installs that exact artifact and successfully calls
   `CloudOpsLogger` (imports/resolves, instantiates, logs one line).
3. The library's own existing test suite still passes (no regressions from any
   config change made).

If a language is blocked purely by a missing/incompatible toolchain that cannot
be provisioned here (most likely: JDK 21 for Java), that is reported explicitly
as a toolchain blocker with the exact remediation, rather than worked around by
changing the library's target runtime.

## Risks

- **Java JDK version** is the highest-likelihood blocker. Mitigation above.
- **.NET net8.0 targeting pack** under the .NET 10 SDK may need installing.
- Removing `distributionManagement` is the only planned source-config change;
  it is inert with respect to the built jar and the test suite.
