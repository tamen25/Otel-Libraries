// This file contains utils logic for logs src.

// Hardcoded fallbacks for the OTLP logs endpoint and org id. Env vars override
// these; leave them empty to fall back to console. X_ORG_ID is required for OTLP
// export no matter what — without it the logger always uses console.
export const DEFAULT_LOGS_ENDPOINT = "";
export const DEFAULT_X_ORG_ID = "";

export interface LogsExporterConfig {
  url?: string;
}

export interface BackendConfig {
  logs?: LogsExporterConfig;
}

export interface ExporterParameters {
  otel?: BackendConfig;
}

function parseJsonEnv<T>(name: string): T | undefined {
  const raw = process.env[name];
  if (!raw) return undefined;

  try {
    return JSON.parse(raw) as T;
  } catch {
    return undefined;
  }
}

// Normalizes endpoint.
function normalizeEndpoint(endpoint?: string): string | undefined {
  if (!endpoint) return undefined;
  return endpoint.endsWith("/v1/logs") ? endpoint : `${endpoint.replace(/\/$/, "")}/v1/logs`;
}

// Checks whether exporter parameters empty.
export function isExporterParametersEmpty(parameters: ExporterParameters | null | undefined): boolean {
  return !parameters?.otel?.logs?.url;
}

// Reads exporter parameters.
export function readExporterParameters(): ExporterParameters {
  const configured = parseJsonEnv<ExporterParameters>("OTEL_EXPORTER_PARAMETERS");
  if (!isExporterParametersEmpty(configured)) return configured!;

  const otelLogsUrl = process.env.OTEL_EXPORTER_OTLP_LOGS_ENDPOINT
    || normalizeEndpoint(process.env.OTEL_EXPORTER_OTLP_ENDPOINT)
    || DEFAULT_LOGS_ENDPOINT;

  const params: ExporterParameters = {};

  if (otelLogsUrl) {
    params.otel = {
      logs: {
        url: otelLogsUrl,
      },
    };
  }

  return params;
}

// Resolves org id.
export function orgId(): string | undefined {
  return process.env.X_ORG_ID || DEFAULT_X_ORG_ID || undefined;
}
