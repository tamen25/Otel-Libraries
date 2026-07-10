# Client Libraries

OpenTelemetry client libraries, one directory per language and signal:

```text
libraries/<language>/<signal>/
```

Current scope:

- `python/logs`, `python/traces`
- `java/logs`, `java/traces`
- `dotnet/logs`, `dotnet/traces`
- `nodejs/logs`, `nodejs/traces`

All ports honor the same `OTEL_*` env-var contract documented in each library's
README, and each has a unit-test suite with a coverage gate. See
[`../docs/USING-THE-LIBRARIES.md`](../docs/USING-THE-LIBRARIES.md) for how to
install and use them in an application.
