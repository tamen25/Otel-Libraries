<!-- This document explains readme for CloudOps. -->
# CloudOps Client Libraries

Internal client libraries live here before they are published to AWS
CodeArtifact.

Current scope:

- `nodejs/logs`
- `nodejs/metrics`
- `nodejs/traces`
- `java/logs`
- `dotnet/logs`
- `python/logs`
- `go/logs`
- `cpp/logs`

Future language roots should follow the same shape:

```text
libraries/<language>/<signal>/
```

The library pipeline publishes npm, Maven, NuGet, and Python packages to
language-specific AWS CodeArtifact repositories. Go and C++ packages are
validated in CI while their artifact publishing path is finalized. All ports
honor the same `OTEL_*` env-var contract documented in each library's README.
Use the `publish_languages` workflow input, or the `LIBRARY_PUBLISH_LANGUAGES`
GitHub Actions variable, to publish only selected languages.

The pipeline runs unit tests with coverage gates for every implemented logs
library before any selected publish job can run.
