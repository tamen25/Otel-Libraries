// This file contains logs instrumentation logic for logs src.
import {
  BatchLogRecordProcessor,
  LoggerProvider,
  LogRecordProcessor,
} from "@opentelemetry/sdk-logs";
import { ATTR_SERVICE_NAME } from "@opentelemetry/semantic-conventions";
import {
  diag,
  DiagConsoleLogger,
  DiagLogLevel,
  propagation,
  trace,
} from "@opentelemetry/api";
import { WinstonInstrumentation } from "@opentelemetry/instrumentation-winston";
import { OpenTelemetryTransportV3 } from "@opentelemetry/winston-transport";
import { registerInstrumentations } from "@opentelemetry/instrumentation";
import { OTLPLogExporter } from "@opentelemetry/exporter-logs-otlp-http";
import { Resource } from "@opentelemetry/resources";
import { randomUUID } from "crypto";
import { env } from "process";
import * as logsAPI from "@opentelemetry/api-logs";
import * as Winston from "winston";
import { inspect } from "util";
import { isExporterParametersEmpty, readExporterParameters, ExporterParameters, orgId } from "./utils";

export type LogLevel = "info" | "error" | "debug" | "warn";

export interface LogEntry {
  invocationId?: string;
  level: LogLevel;
  message: any;
  optionalParams?: any[];
}

interface LogBatch {
  logs: LogEntry[];
}

const DEFAULT_LOG_LEVELS: LogLevel[] = ["info", "error", "debug", "warn"];
const LOG_LEVELS = new Set<string>(DEFAULT_LOG_LEVELS);
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

// Parses log levels.
export function parseLogLevels(raw: string | undefined): LogLevel[] {
  const levels = parseStringArray(raw, DEFAULT_LOG_LEVELS)
    .map((item) => item.toLowerCase())
    .filter((item): item is LogLevel => LOG_LEVELS.has(item));
  return levels.length > 0 ? levels : [...DEFAULT_LOG_LEVELS];
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

export class LogSampler {
  private batchMap: Map<string, LogBatch> = new Map();
  private readonly probabilisticSamplingRate: number = parseFloat(process.env.OTEL_LOGS_SAMPLING_RATE || "100");

  // Adds log.
  public addLog(logEntry: LogEntry): void {
    if (this.probabilisticSamplingRate === 0) {
      logger.processLog(logEntry);
      return;
    }

    const { invocationId } = logEntry;
    if (!invocationId || invocationId === "unknown") {
      diag.debug("Invocation ID is unknown, processing log entry directly.");
      logger.processLog(logEntry);
      return;
    }

    if (this.batchMap.has(invocationId)) {
      this.batchMap.get(invocationId)!.logs.push(logEntry);
      return;
    }

    this.flushOneBatch();
    this.batchMap.set(invocationId, { logs: [logEntry] });
  }

  // Flushes one batch.
  public flushOneBatch(): void {
    diag.debug("LogSampler.flushOneBatch called");

    try {
      if (this.batchMap.size === 0) {
        diag.debug("No batches to flush");
        return;
      }

      for (const [invocationId, batch] of this.batchMap) {
        diag.debug(`Processing batch for invocationId: ${invocationId}`);
        const hasErrorLog = batch.logs.some((log) => log.level === "error");

        if (hasErrorLog) {
          diag.debug(`Batch for ${invocationId} contains error logs, processing immediately.`);
          this.processBatch(batch);
          this.batchMap.delete(invocationId);
          continue;
        }

        const samplingThreshold = Math.max(0, Math.min(100, this.probabilisticSamplingRate)) / 100;
        const random = Math.random();
        diag.debug(`Sampling threshold: ${samplingThreshold}, Random value: ${random}`);
        if (random <= samplingThreshold) {
          diag.debug("Processing batch due to sampling", random);
          this.processBatch(batch);
          this.batchMap.delete(invocationId);
          continue;
        }

        diag.debug(`Batch for ${invocationId} not sampled, deleting.`);
        this.batchMap.delete(invocationId);
      }
    } catch (error) {
      diag.debug("Error in LogSampler.flushOneBatch", error);
    }
  }

  // Processes batch.
  private processBatch(batch: LogBatch): void {
    diag.debug(`LogSampler.processBatch called with ${batch.logs.length} logs`);
    batch.logs.forEach((log) => logger.processLog(log));
  }
}

export class LogsInstrumentation {
  private isInitialized = false;
  private static instance: LogsInstrumentation;
  private otelLoggers: Record<string, Winston.Logger | undefined> = {};
  private exporters!: LogRecordProcessor;
  private loggerProvider?: LoggerProvider;
  private useConsole = false;
  private useOtel = false;
  private logLevels: LogLevel[] = [];
  private sampler: LogSampler;
  private previousTraceId: string | undefined;
  private uniqueId: string | undefined;
  private exportersList = parseStringArray(process.env.OTEL_BACKEND_EXPORTERS, ["console"]);

  // function Object() { [native code] } the requested work.
  private constructor() {
    this.sampler = new LogSampler();
  }

  // Initializes logger.
  public static initialiseLogger(): LogsInstrumentation {
    if (!this.instance) {
      this.instance = new LogsInstrumentation();
      this.instance.init();
    }

    return this.instance;
  }

  // Initializes the requested work.
  private init(): void {
    if (this.isInitialized) return;

    if (env.ENABLE_OTEL_DEBUG_LOGS?.toLowerCase() === "true") {
      diag.setLogger(new DiagConsoleLogger(), DiagLogLevel.DEBUG);
    }

    this.logLevels = parseLogLevels(process.env.OTEL_LOG_LEVEL);

    if (this.exportersList.length <= 1 && this.exportersList.includes("console")) {
      this.useConsole = true;
      this.isInitialized = true;
      return;
    }

    diag.debug("LogsInstrumentation.init called");

    try {
      const envResourceAttributes = parseResourceAttributes(process.env.OTEL_RESOURCE_ATTRIBUTES);
      const resourceAttributes: Record<string, string> = {
        ...envResourceAttributes,
        [ATTR_SERVICE_NAME]: process.env.OTEL_SERVICE_NAME
          || envResourceAttributes[ATTR_SERVICE_NAME]
          || process.env.WEBSITE_SITE_NAME
          || process.env.npm_package_name
          || "unknown_service",
        "pe-lib-log-ver": "1.16.2",
      };

      addRuntimeResourceAttributes(resourceAttributes);

      const resource = Resource.default().merge(new Resource(resourceAttributes));

      this.setupExporters();

      if (this.exporters) {
        this.loggerProvider = new LoggerProvider({ resource });
        this.loggerProvider.addLogRecordProcessor(this.exporters);
        logsAPI.logs.setGlobalLoggerProvider(this.loggerProvider);
        diag.debug("Logs Instrumentation Started");
      }

      this.initialiseWinston();
      this.isInitialized = true;
    } catch (error) {
      diag.debug("OTEL register failed", error);
    }
  }

  // Handles setup exporters.
  private setupExporters(): void {
    diag.debug("LogsInstrumentation.setupExporters called");

    try {
      diag.debug(`Exporters list: ${JSON.stringify(this.exportersList)}`);

      const exporterParameters = readExporterParameters();
      if (isExporterParametersEmpty(exporterParameters) || !orgId()) {
        diag.debug("LogsInstrumentation endpoint or X_ORG_ID is empty. Switching logger to console.");
        this.useConsole = true;
        return;
      }

      diag.debug(`Exporter Parameters Retrieved: ${JSON.stringify(exporterParameters)}`);

      for (const exporter of this.exportersList.map((item) => item.toLowerCase())) {
        switch (exporter) {
          case "console":
            this.useConsole = true;
            break;

          case "otel":
            this.exporters = this.createProcessor(exporterParameters, "otel");
            this.useOtel = true;
            break;

          default:
            this.useConsole = true;
            break;
        }
      }
    } catch (error) {
      diag.debug("Exporter setup failed", error);
    }
  }

  private createProcessor(
    exporterParameters: ExporterParameters,
    backend: keyof ExporterParameters,
  ): LogRecordProcessor {
    const config = exporterParameters[backend]?.logs;
    return new BatchLogRecordProcessor(new OTLPLogExporter({
      url: config?.url,
      headers: orgIdHeaders(orgId()),
    }));
  }

  // Initializes winston.
  private initialiseWinston(): void {
    diag.debug("LogsInstrumentation.initialiseWinston called");

    try {
      registerInstrumentations({
        instrumentations: [new WinstonInstrumentation({})],
      });

      const { combine, timestamp, json, prettyPrint, errors } = Winston.format;

      const createOtelLogger = (level: LogLevel): Winston.Logger | undefined => {
        if (this.logLevels.includes(level) && this.useOtel) {
          return Winston.createLogger({
            level,
            format: combine(
              timestamp(),
              json(),
              errors({ stack: true }),
              prettyPrint(),
            ),
            transports: [new OpenTelemetryTransportV3()],
            rejectionHandlers: [new OpenTelemetryTransportV3()],
            exceptionHandlers: [new OpenTelemetryTransportV3()],
          });
        }

        return undefined;
      };

      DEFAULT_LOG_LEVELS.forEach((level) => {
        this.otelLoggers[level] = createOtelLogger(level);
      });

      diag.debug("Winston setup completed");
    } catch (error) {
      diag.debug("Winston setup failed", error);
    }
  }

  // Handles merge log attributes.
  private mergeLogAttributes(extraAttributes?: Record<string, any>): Record<string, any> {
    let attributes: Record<string, any> = {};

    attributes = {
      ...extraAttributes,
      ...this.activeBaggageAttributes(),
    };

    const spanContext = trace.getActiveSpan()?.spanContext();
    if (spanContext) {
      attributes = {
        ...attributes,
        "otel-trace-id": spanContext.traceId,
        "otel-span-id": spanContext.spanId,
      };
    }

    return attributes;
  }

  // Handles active baggage attributes.
  private activeBaggageAttributes(): Record<string, string> {
    const activeBaggage = propagation.getActiveBaggage();
    if (!activeBaggage) return {};

    const attributes: Record<string, string> = {};
    activeBaggage.getAllEntries().forEach(([key, entry]) => {
      attributes[`baggage.${key}`] = entry.value;
    });

    return attributes;
  }

  // Processes log.
  public processLog(logEntry: LogEntry): void {
    diag.debug(`LogsInstrumentation.processLog called for level: ${logEntry.level}`);

    try {
      const consoleMethod = console[logEntry.level] || console.log;
      const otelLogger = this.otelLoggers[logEntry.level];
      const loggerMethod = otelLogger?.[logEntry.level]?.bind(otelLogger);

      const logMessage = logEntry.message instanceof Error
        ? logEntry.message.stack || logEntry.message.message
        : logEntry.message;
      const optionalParams: any[] = logEntry.optionalParams || [];

      if (this.logLevels.includes(logEntry.level)) {
        try {
          if (optionalParams.length > 0) {
            const formattedParams = optionalParams
              .map((param) => inspect(param, { depth: Infinity, colors: false }))
              .join("\n");

            if (this.useConsole) {
              consoleMethod(logMessage, formattedParams);
            }

            if (loggerMethod && this.useOtel) {
              loggerMethod(
                `${logMessage}\n${formattedParams}`,
                this.mergeLogAttributes({ "invocation.id": logEntry.invocationId || "unknown" }),
              );
            }
          } else {
            if (this.useConsole) {
              consoleMethod(logMessage);
            }

            if (loggerMethod && this.useOtel) {
              loggerMethod(
                logMessage,
                this.mergeLogAttributes({ "invocation.id": logEntry.invocationId || "unknown" }),
              );
            }
          }
        } catch (error) {
          diag.debug(`Logging failed for level: ${logEntry.level}`, error);
        }
      }
    } catch (error) {
      diag.debug("Error in LogsInstrumentation.processLog", error);
    }
  }

  // Logs the requested work.
  public log(level: LogLevel, message?: any, ...optionalParams: any[]): void {
    diag.debug(`LogsInstrumentation.log called with level: ${level}, message: ${message}`);
    const currentTraceID = trace.getActiveSpan()?.spanContext().traceId || "unknown";

    if (currentTraceID !== this.previousTraceId) {
      this.uniqueId = randomUUID();
      this.previousTraceId = currentTraceID;
    }

    const invocationId = this.uniqueId || "unknown";
    this.sampler.addLog({ invocationId, level, message, optionalParams });
  }

  // Handles info.
  public info(message?: any, ...optionalParams: any[]): void {
    this.log("info", message, ...optionalParams);
  }

  // Handles error.
  public error(message?: any, ...optionalParams: any[]): void {
    this.log("error", message, ...optionalParams);
  }

  // Handles debug.
  public debug(message?: any, ...optionalParams: any[]): void {
    this.log("debug", message, ...optionalParams);
  }

  // Handles warn.
  public warn(message?: any, ...optionalParams: any[]): void {
    this.log("warn", message, ...optionalParams);
  }

  // Exports logs.
  public async exportLogs(): Promise<void> {
    diag.debug("LogsInstrumentation.logs called");

    try {
      this.sampler.flushOneBatch();
      if (this.useOtel) {
        await this.exporters?.forceFlush();
      }

      diag.debug("Logs exported successfully");
    } catch (error) {
      diag.debug("Logs export failed", error);
    }
  }
}

export const logger = LogsInstrumentation.initialiseLogger();
