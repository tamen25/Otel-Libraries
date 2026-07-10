// This file contains trace instrumentation logic for traces src.
import { NodeTracerProvider } from "@opentelemetry/sdk-trace-node";
import {
  SDKRegistrationConfig,
  BatchSpanProcessor,
  ConsoleSpanExporter,
  ParentBasedSampler,
  SimpleSpanProcessor,
  SpanProcessor,
  TraceIdRatioBasedSampler,
} from "@opentelemetry/sdk-trace-base";
import { registerInstrumentations } from "@opentelemetry/instrumentation";
import { HttpInstrumentation } from "@opentelemetry/instrumentation-http";
import { defaultResource, resourceFromAttributes } from "@opentelemetry/resources";
import { ATTR_SERVICE_NAME } from "@opentelemetry/semantic-conventions";
import api, {
  Context,
  diag,
  DiagConsoleLogger,
  DiagLogLevel,
  propagation,
  Span,
  SpanKind,
  SpanStatusCode,
  trace,
  Tracer,
} from "@opentelemetry/api";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-http";

import {
  configureSdkRegistration,
  configureTracer,
  isExporterParametersEmpty,
  orgId,
  readExporterParameters,
  setObjectAttributes,
  setSingleAttribute,
} from "./utils";
import { ServiceAttributes, spanProps, SpanAttributes } from "./interface";
import { AzureService } from "./enums";
import { ServicesExtensions } from "./services/serviceExtensions";

const PE_LIB_TRACE_VER = "0.1.0";

const ATTR_CLOUD_PROVIDER = "cloud.provider";
const ATTR_CLOUD_PLATFORM = "cloud.platform";
const ATTR_CONTAINER_ID = "container.id";
const ATTR_CONTAINER_NAME = "container.name";
const ATTR_FAAS_NAME = "faas.name";
const ATTR_K8S_CLUSTER_NAME = "k8s.cluster.name";
const ATTR_K8S_NAMESPACE_NAME = "k8s.namespace.name";
const ATTR_K8S_NODE_NAME = "k8s.node.name";
const ATTR_K8S_POD_NAME = "k8s.pod.name";
const CLOUD_PROVIDER_VALUE_AZURE = "azure";
const CLOUD_PLATFORM_VALUE_AZURE_FUNCTIONS = "azure_functions";
const CLOUD_PLATFORM_VALUE_AZURE_CONTAINER_APPS = "azure_container_apps";
const CLOUD_PLATFORM_VALUE_AZURE_APP_SERVICE = "azure_app_service";
const CLOUD_PLATFORM_VALUE_AZURE_AKS = "azure_aks";

// Parses string array.
export function parseStringArray(raw: string | undefined, fallback: string[]): string[] {
  if (!raw) return [...fallback];

  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      const values = parsed.map(String).map((item) => item.trim()).filter(Boolean);
      return values.length > 0 ? values : [...fallback];
    }
  } catch {
    return raw.split(",").map((item) => item.trim()).filter(Boolean);
  }

  return [...fallback];
}

// Parses resource attributes.
export function parseResourceAttributes(raw: string | undefined): Record<string, string> {
  if (!raw) return {};

  return raw.split(",").reduce<Record<string, string>>((attributes, item) => {
    const separatorIndex = item.indexOf("=");
    if (separatorIndex <= 0) return attributes;

    const key = item.slice(0, separatorIndex).trim();
    const value = item.slice(separatorIndex + 1).trim();
    if (key && value) attributes[key] = value;

    return attributes;
  }, {});
}

// Handles org id headers.
function orgIdHeaders(id: string | undefined): Record<string, string> {
  if (!id) return {};
  return { "X-OrgId": id };
}

// Finds first env.
function firstEnv(...names: string[]): string | undefined {
  for (const name of names) {
    const value = process.env[name];
    if (value) return value;
  }

  return undefined;
}

// Adds runtime resource attributes.
export function addRuntimeResourceAttributes(attributes: Record<string, string>): void {
  if (firstEnv("FUNCTIONS_EXTENSION_VERSION", "FUNCTIONS_WORKER_RUNTIME")) {
    attributes[ATTR_CLOUD_PROVIDER] = CLOUD_PROVIDER_VALUE_AZURE;
    attributes[ATTR_CLOUD_PLATFORM] = CLOUD_PLATFORM_VALUE_AZURE_FUNCTIONS;
    const siteName = process.env.WEBSITE_SITE_NAME;
    if (siteName) attributes[ATTR_FAAS_NAME] = siteName;
    return;
  }

  if (process.env.CONTAINER_APP_NAME) {
    attributes[ATTR_CLOUD_PROVIDER] = CLOUD_PROVIDER_VALUE_AZURE;
    attributes[ATTR_CLOUD_PLATFORM] = CLOUD_PLATFORM_VALUE_AZURE_CONTAINER_APPS;
  }

  if (process.env.WEBSITE_SITE_NAME) {
    attributes[ATTR_CLOUD_PROVIDER] = CLOUD_PROVIDER_VALUE_AZURE;
    attributes[ATTR_CLOUD_PLATFORM] = CLOUD_PLATFORM_VALUE_AZURE_APP_SERVICE;
  }

  const runningOnKubernetes = Boolean(process.env.KUBERNETES_SERVICE_HOST);
  const k8sClusterName = firstEnv("K8S_CLUSTER_NAME", "AKS_CLUSTER_NAME");
  const k8sNamespaceName = firstEnv("K8S_NAMESPACE_NAME", "POD_NAMESPACE");
  const k8sNodeName = firstEnv("K8S_NODE_NAME", "NODE_NAME");
  const k8sPodName = firstEnv("K8S_POD_NAME", "POD_NAME", runningOnKubernetes ? "HOSTNAME" : "");

  if (runningOnKubernetes || k8sClusterName || k8sNamespaceName || k8sPodName) {
    attributes[ATTR_CLOUD_PROVIDER] = CLOUD_PROVIDER_VALUE_AZURE;
    attributes[ATTR_CLOUD_PLATFORM] = CLOUD_PLATFORM_VALUE_AZURE_AKS;
  }

  if (k8sClusterName) attributes[ATTR_K8S_CLUSTER_NAME] = k8sClusterName;
  if (k8sNamespaceName) attributes[ATTR_K8S_NAMESPACE_NAME] = k8sNamespaceName;
  if (k8sNodeName) attributes[ATTR_K8S_NODE_NAME] = k8sNodeName;
  if (k8sPodName) attributes[ATTR_K8S_POD_NAME] = k8sPodName;

  const containerId = firstEnv("CONTAINER_ID");
  const containerName = firstEnv("CONTAINER_NAME", "CONTAINER_APP_NAME");
  if (containerId) attributes[ATTR_CONTAINER_ID] = containerId;
  if (containerName) attributes[ATTR_CONTAINER_NAME] = containerName;
}

// Builds active baggage attributes.
function traceBaggageAttrs(): Record<string, string> {
  const activeBaggage = propagation.getActiveBaggage();
  if (!activeBaggage) return {};

  const attributes: Record<string, string> = {};
  activeBaggage.getAllEntries().forEach(([key, entry]) => {
    attributes[`baggage.${key}`] = entry.value;
  });

  return attributes;
}

class TraceInstrumentation {
  private isInitialized = false;

  private serviceName: string | undefined = process.env.OTEL_SERVICE_NAME || process.env.WEBSITE_SITE_NAME;

  private tracerProvider!: NodeTracerProvider;

  private tracer!: Tracer;

  private activeContext!: Context;

  private currentSpan!: Span;

  private static instance?: TraceInstrumentation;

  private batchProcessorConfig!: SpanProcessor;

  private servicesExtensions: ServicesExtensions = new ServicesExtensions();

  private propagationContext!: Context;

  get activeSpan(): Span | undefined {
    return this.currentSpan;
  }

  // Initializes tracer.
  static initialiseTracer(): TraceInstrumentation {
    if (!this.instance) {
      this.instance = new TraceInstrumentation();
      this.instance.init();
    }

    return this.instance;
  }

  // Initializes the requested work.
  private init(): void {
    if (this.isInitialized) return;

    diag.debug("Registering OpenTelemetry");

    if (
      typeof process.env.ENABLE_OTEL_DEBUG_LOGS === "string"
      && process.env.ENABLE_OTEL_DEBUG_LOGS.toLocaleLowerCase() === "true"
    ) {
      diag.setLogger(new DiagConsoleLogger(), DiagLogLevel.DEBUG);
    }

    const traceRatio = parseFloat(process.env.TRACEID_RATIO_BASED_SAMPLER ?? "1");

    const envResourceAttributes = parseResourceAttributes(process.env.OTEL_RESOURCE_ATTRIBUTES);
    const resourceAttributes: Record<string, string> = {
      ...envResourceAttributes,
      [ATTR_SERVICE_NAME]: process.env.OTEL_SERVICE_NAME
        || envResourceAttributes[ATTR_SERVICE_NAME]
        || process.env.WEBSITE_SITE_NAME
        || process.env.npm_package_name
        || "unknown_service",
      "pe-lib-trace-ver": PE_LIB_TRACE_VER,
    };

    addRuntimeResourceAttributes(resourceAttributes);

    const resource = defaultResource().merge(resourceFromAttributes(resourceAttributes));

    try {
      const exportersList = parseStringArray(process.env.OTEL_BACKEND_EXPORTERS, ["console"]);
      const exporterParameters = readExporterParameters();

      const backend = exportersList.map((item) => item.toLowerCase())[0];

      // OTel JS 2.x: span processors are passed to the NodeTracerProvider
      // constructor (addSpanProcessor was removed). Build the list first.
      let spanProcessors: SpanProcessor[];

      switch (backend) {
        case "otel":
          if (isExporterParametersEmpty(exporterParameters) || !orgId()) {
            diag.debug("TraceInstrumentation endpoint or X_ORG_ID is empty. Switching tracer to console.");
            spanProcessors = [new SimpleSpanProcessor(new ConsoleSpanExporter())];
            break;
          }

          this.batchProcessorConfig = new BatchSpanProcessor(
            new OTLPTraceExporter({
              url: exporterParameters.otel?.trace?.url,
              headers: orgIdHeaders(orgId()),
            }),
          );
          spanProcessors = [this.batchProcessorConfig];
          break;

        case "console":
        default:
          spanProcessors = [new SimpleSpanProcessor(new ConsoleSpanExporter())];
          break;
      }

      this.tracerProvider = new NodeTracerProvider(
        configureTracer({
          resource,
          sampler: new ParentBasedSampler({
            root: new TraceIdRatioBasedSampler(traceRatio),
          }),
          spanProcessors,
        }),
      );

      let sdkRegistrationConfig: SDKRegistrationConfig = {};
      sdkRegistrationConfig = configureSdkRegistration(sdkRegistrationConfig);
      this.tracerProvider.register(sdkRegistrationConfig);

      // Auto-instrument HTTP so incoming/outgoing requests create spans and
      // propagate W3C trace context across services automatically.
      registerInstrumentations({
        tracerProvider: this.tracerProvider,
        instrumentations: [new HttpInstrumentation()],
      });

      this.tracer = trace.getTracer(`${this.serviceName || "cloudops"}-tracer`);
      this.isInitialized = true;
    } catch (e) {
      diag.debug("OTEL register failed", e);
    }
  }

  /**
   * Starts a basic span
   *
   * @param name Attribute value
   * @param props Properties for startSpan
   *
   * @returns the {@link Span} object.
   */
  startBasicSpan(name: string, props?: spanProps): Span | undefined {
    if (!this.isInitialized) {
      return undefined;
    }

    try {
      const span = this.tracer.startSpan(
        name,
        {
          root: props?.root,
          kind: props?.spanKind ?? SpanKind.INTERNAL,
          attributes: {},
          startTime: new Date(),
        },
        props?.parent || this.activeContext,
      );

      this.setAttributes(span, traceBaggageAttrs());

      if (props?.setActiveContext) {
        this.activeContext = api.trace.setSpan(api.context.active(), span);
      }

      this.currentSpan = span;

      return span;
    } catch (e) {
      diag.debug("startSpan failed", e);
      return undefined;
    }
  }

  /**
   * Sets attributes to the span.
   *
   * @param data the key and value of the attributes
   */
  setAttributes(span: any, data: SpanAttributes): void {
    if (!span || !this.isInitialized || (!data && !span)) {
      return;
    }

    if (data && typeof data === "object") {
      setObjectAttributes(span, data);
    } else {
      setSingleAttribute(span, data);
    }
  }

  /**
   * Sets the active span status as error span and exception as a span event
   *
   * @param error the exception the only accepted values are string or Error
   */
  recordError(error: any, span?: Span): void {
    if (!this.activeContext) {
      return;
    }

    const recordErrorSpan = span || this.currentSpan;
    try {
      recordErrorSpan?.recordException(error);
      recordErrorSpan?.setStatus({ code: SpanStatusCode.ERROR });
    } catch (e) {
      diag.debug("recordError failed", e);
    }
  }

  /**
   * Sets the active span status as active
   *
   * @param span The span which need to be set as active
   */
  setActiveContext(span: Span | undefined): void {
    if (!span) {
      return;
    }

    this.activeContext = api.trace.setSpan(api.context.active(), span);
  }

  /**
   * Fetch the trace attributes for context propagation.
   *
   * Injects the active W3C trace context (traceparent/tracestate) into a new
   * carrier object — useful for manual propagation over non-HTTP transports
   * (e.g. Service Bus message applicationProperties).
   *
   * @returns carrier object with injected context
   */
  fetchTraceAttrs(): { [key: string]: string } | undefined {
    const traceAttrs = {};

    api.propagation.inject(api.trace.setSpan(api.context.active(), this.currentSpan), traceAttrs);
    return traceAttrs || undefined;
  }

  /**
   * Extract trace attributes from a carrier (W3C traceparent/tracestate).
   *
   * @param carrier object holding the propagated context headers
   */
  extractTraceAttrs(carrier: { [key: string]: string }): void {
    this.propagationContext = api.propagation.extract(api.context.active(), carrier);
  }

  /**
   * Starts an Azure specific service span using the service extension mappers.
   *
   * @param service Type of the azure service
   * @param props Service attributes
   *
   * @returns the {@link Span} object.
   */
  startAzureSpan(service: AzureService, props: ServiceAttributes): Span | undefined {
    const metadata = this.servicesExtensions.requestPreSpanHook(service, props);

    if (!metadata.spanName) {
      return undefined;
    }

    const span = this.startBasicSpan(metadata.spanName, {
      spanKind: metadata.spanKind,
      setActiveContext: false,
      parent: this.propagationContext ? this.propagationContext : undefined,
    });
    this.setAttributes(span, metadata.spanAttributes);

    return span;
  }

  /**
   * Fetch propagation attributes to attach to an outgoing Azure message.
   */
  requestPropagationAttributes(span: Span, service: AzureService): any {
    return this.servicesExtensions.requestPropagationAttributes(span, service);
  }

  /**
   * Retrieve propagation attributes from a received Azure message.
   */
  retrievePropagationAttributes(event: any, service: AzureService): any {
    return this.servicesExtensions.retrievePropagationAttributes(event, service);
  }

  /**
   * Force all the spans to get exported.
   *
   * @returns promise
   */
  async exportSpans(): Promise<void> {
    if (!this.batchProcessorConfig) {
      return;
    }

    await this.batchProcessorConfig.forceFlush();
  }
}

export const tracer = TraceInstrumentation.initialiseTracer();
