// This file contains utils logic for traces src.
import { diag } from "@opentelemetry/api";
import { SDKRegistrationConfig } from "@opentelemetry/sdk-trace-base";
import { NodeTracerConfig } from "@opentelemetry/sdk-trace-node";
import {
  CompositePropagator,
  W3CBaggagePropagator,
  W3CTraceContextPropagator,
} from "@opentelemetry/core";

// Hardcoded fallbacks for the OTLP traces endpoint and org id. Env vars override
// these; leave them empty to fall back to console. X_ORG_ID is required for OTLP
// export no matter what — without it the tracer always uses console.
export const DEFAULT_TRACES_ENDPOINT = "";
export const DEFAULT_X_ORG_ID = "";

export interface TracesExporterConfig {
  url?: string;
}

export interface BackendConfig {
  trace?: TracesExporterConfig;
}

export interface ExporterParameters {
  otel?: BackendConfig;
}

// Configures sdk registration with the W3C tracecontext + baggage propagators so
// HTTP context propagates automatically across services (matches all other ports).
export function configureSdkRegistration(config: SDKRegistrationConfig): SDKRegistrationConfig {
  return {
    ...config,
    propagator: new CompositePropagator({
      propagators: [new W3CTraceContextPropagator(), new W3CBaggagePropagator()],
    }),
  };
}

// Configures tracer.
export function configureTracer(config: NodeTracerConfig): NodeTracerConfig {
  return {
    ...config,
    forceFlushTimeoutMillis: 90000,
  };
}

// Gets attribute value.
export function getAttributeValue(value: number | string | undefined): string | undefined {
  if (typeof value === "number") {
    return value.toString();
  }

  if (typeof value === "string") {
    return value;
  }

  return undefined;
}

// Sets object attributes.
export function setObjectAttributes(span: any, data: { [key: string]: number | string | undefined }): void {
  try {
    for (const key in data) {
      if (data[key]) {
        span.setAttribute(key, getAttributeValue(data[key]));
      }
    }
  } catch (e) {
    diag.debug("setObjectAttributes failed", e);
  }
}

// Sets single attribute.
export function setSingleAttribute(span: any, data: string | undefined): void {
  try {
    if (data) {
      span.setAttribute(data);
    }
  } catch (e) {
    diag.debug("setSingleAttribute failed", e);
  }
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
  return endpoint.endsWith("/v1/traces") ? endpoint : `${endpoint.replace(/\/$/, "")}/v1/traces`;
}

// Checks whether exporter parameters empty.
export function isExporterParametersEmpty(parameters: ExporterParameters | null | undefined): boolean {
  return !parameters?.otel?.trace?.url;
}

// Reads exporter parameters.
export function readExporterParameters(): ExporterParameters {
  const configured = parseJsonEnv<ExporterParameters>("OTEL_EXPORTER_PARAMETERS");
  if (!isExporterParametersEmpty(configured)) return configured!;

  const otelTracesUrl = process.env.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT
    || normalizeEndpoint(process.env.OTEL_EXPORTER_OTLP_ENDPOINT)
    || DEFAULT_TRACES_ENDPOINT;

  const params: ExporterParameters = {};

  if (otelTracesUrl) {
    params.otel = {
      trace: {
        url: otelTracesUrl,
      },
    };
  }

  return params;
}

// Resolves org id.
export function orgId(): string | undefined {
  return process.env.X_ORG_ID || DEFAULT_X_ORG_ID || undefined;
}
