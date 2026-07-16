# Node.js — what to install

## Toolchain (install on the machine)

- **Node.js ≥ 22**
- **npm** (bundled with Node)

## Library dependencies

`npm install` in each package pulls these from `package.json` — you don't install
them by hand.

**`@otel/logs`**:
- `@opentelemetry/api` ^1.9.0
- `@opentelemetry/api-logs` ^0.220.0
- `@opentelemetry/exporter-logs-otlp-http` ^0.220.0
- `@opentelemetry/instrumentation` ^0.220.0
- `@opentelemetry/instrumentation-winston` ^0.64.0
- `@opentelemetry/resources` ^2.9.0
- `@opentelemetry/sdk-logs` ^0.220.0
- `@opentelemetry/semantic-conventions` ^1.43.0
- `@opentelemetry/winston-transport` ^0.30.0
- `winston` ^3.17.0

**`@otel/traces`**:
- `@opentelemetry/api` ^1.9.0
- `@opentelemetry/core` ^2.9.0
- `@opentelemetry/exporter-trace-otlp-http` ^0.220.0
- `@opentelemetry/instrumentation` ^0.220.0
- `@opentelemetry/instrumentation-http` ^0.220.0
- `@opentelemetry/resources` ^2.9.0
- `@opentelemetry/sdk-trace-base` ^2.9.0
- `@opentelemetry/sdk-trace-node` ^2.9.0
- `@opentelemetry/semantic-conventions` ^1.43.0

Dev (build + test): `typescript` ^5.6.3, `@types/node` ^22.

## Build / test / pack

```bash
cd logs   && npm install && npm run build && npm test
cd traces && npm install && npm run build && npm test

npm pack   # in each package -> otel-logs-0.1.0.tgz / otel-traces-0.1.0.tgz
```
