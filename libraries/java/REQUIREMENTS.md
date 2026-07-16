# Java — what to install

## Toolchain (install on the machine)

- **JDK 21** (e.g. Eclipse Temurin 21)
- **Apache Maven 3.9+**

## Library dependencies

Maven resolves these automatically from each `pom.xml` on first build — you don't
install them by hand. Both artifacts use **OpenTelemetry 1.60.1**:

- `io.opentelemetry:opentelemetry-api:1.60.1`
- `io.opentelemetry:opentelemetry-sdk:1.60.1`
- `io.opentelemetry:opentelemetry-exporter-otlp:1.60.1`
- `com.fasterxml.jackson.core:jackson-databind:2.17.2`
- `org.junit.jupiter:junit-jupiter:5.11.4` *(test scope only)*

## Build / test / install

```bash
mvn -f logs/pom.xml verify        # compile + test + coverage gate
mvn -f traces/pom.xml verify

# install to the local Maven repo so other projects can depend on otel:otel-logs / otel:otel-traces
mvn -f logs/pom.xml install
mvn -f traces/pom.xml install
```
