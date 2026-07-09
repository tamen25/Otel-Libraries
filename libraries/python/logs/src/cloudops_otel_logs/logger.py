#This file contains logger logic for src cloudops OTel logs.
from __future__ import annotations

import json
import logging
import os
import random
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

try:
    from opentelemetry import baggage, trace
    from opentelemetry._logs import set_logger_provider
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.sdk.resources import Resource
except ImportError:  # pragma: no cover - exercised only before package deps are installed.
    baggage = None
    trace = None
    set_logger_provider = None
    OTLPLogExporter = None
    LoggerProvider = None
    LoggingHandler = None
    BatchLogRecordProcessor = None
    Resource = None

LogLevel = str

DEFAULT_EXPORTERS = ["console"]
DEFAULT_LOG_LEVELS = {"info", "error", "debug", "warn"}
VALID_LOG_LEVELS = DEFAULT_LOG_LEVELS
# Hardcoded fallbacks for the OTLP logs endpoint and org id. Env vars override
# these; leave them empty to fall back to console. X_ORG_ID is required for OTLP
# export no matter what — without it the logger always uses console.
DEFAULT_LOGS_ENDPOINT = ""
DEFAULT_X_ORG_ID = ""


@dataclass
class LogsExporterConfig:
    url: str | None = None


@dataclass
class BackendConfig:
    logs: LogsExporterConfig | None = None


@dataclass
class ExporterParameters:
    otel: BackendConfig | None = None

    #Checks whether empty.
    def is_empty(self) -> bool:
        return self.otel is None or self.otel.logs is None or not self.otel.logs.url

    #Handles backend.
    def backend(self, name: str) -> BackendConfig | None:
        return self.otel if name == "otel" else None


@dataclass
class LogEntry:
    invocation_id: str
    level: LogLevel
    message: Any = None
    optional_params: tuple[Any, ...] = field(default_factory=tuple)


@dataclass
class LogBatch:
    logs: list[LogEntry]


#Parses string list.
def _parse_string_list(raw: str | None, fallback: list[str]) -> list[str]:
    if not raw:
        return list(fallback)

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            values = [str(item).strip() for item in parsed if str(item).strip()]
            return values or list(fallback)
    except json.JSONDecodeError:
        pass

    values = [item.strip() for item in raw.split(",") if item.strip()]
    return values or list(fallback)


#Parses string set.
def _parse_string_set(raw: str | None, fallback: set[str]) -> set[str]:
    return {item.lower() for item in _parse_string_list(raw, sorted(fallback))}


#Parses log levels.
def _parse_log_levels(raw: str | None) -> set[str]:
    levels = {item for item in _parse_string_set(raw, DEFAULT_LOG_LEVELS) if item in VALID_LOG_LEVELS}
    return levels or set(DEFAULT_LOG_LEVELS)


#Parses resource attributes.
def _parse_resource_attributes(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}

    attributes: dict[str, str] = {}
    for item in raw.split(","):
        key, separator, value = item.partition("=")
        if separator and key.strip() and value.strip():
            attributes[key.strip()] = value.strip()

    return attributes


#Normalizes endpoint.
def _normalize_endpoint(endpoint: str | None) -> str | None:
    if not endpoint:
        return None

    normalized = endpoint.rstrip("/")
    return normalized if normalized.endswith("/v1/logs") else f"{normalized}/v1/logs"


#Handles exporter parameters from JSON.
def _exporter_parameters_from_json(parsed: Any) -> ExporterParameters:
    if not isinstance(parsed, Mapping):
        return ExporterParameters()

    otel = parsed.get("otel", {})
    logs = otel.get("logs", {}) if isinstance(otel, Mapping) else {}
    logs = logs if isinstance(logs, Mapping) else {}
    return ExporterParameters(otel=BackendConfig(logs=LogsExporterConfig(
        url=logs.get("url"),
    )))


#Reads exporter parameters.
def _read_exporter_parameters() -> ExporterParameters:
    configured = os.getenv("OTEL_EXPORTER_PARAMETERS")
    if configured:
        try:
            parameters = _exporter_parameters_from_json(json.loads(configured))
            if not parameters.is_empty():
                return parameters
        except (json.JSONDecodeError, AttributeError):
            pass

    logs_url = (
        os.getenv("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT")
        or _normalize_endpoint(os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"))
        or DEFAULT_LOGS_ENDPOINT
    )
    if logs_url:
        return ExporterParameters(otel=BackendConfig(logs=LogsExporterConfig(url=logs_url)))

    return ExporterParameters()


#Resolves org id.
def _org_id() -> str | None:
    return os.getenv("X_ORG_ID") or DEFAULT_X_ORG_ID or None


#Finds first env.
def _first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value

    return None


#Handles runtime resource attributes.
def _runtime_resource_attributes() -> dict[str, str]:
    attributes = _parse_resource_attributes(os.getenv("OTEL_RESOURCE_ATTRIBUTES"))
    attributes["service.name"] = (
        os.getenv("OTEL_SERVICE_NAME")
        or attributes.get("service.name")
        or os.getenv("WEBSITE_SITE_NAME")
        or "unknown_service"
    )
    attributes["pe-lib-log-ver"] = "1.16.2"

    if _first_env("FUNCTIONS_EXTENSION_VERSION", "FUNCTIONS_WORKER_RUNTIME"):
        attributes["cloud.provider"] = "azure"
        attributes["cloud.platform"] = "azure_functions"
        site_name = os.getenv("WEBSITE_SITE_NAME")
        if site_name:
            attributes["faas.name"] = site_name
        return attributes

    if os.getenv("CONTAINER_APP_NAME"):
        attributes["cloud.provider"] = "azure"
        attributes["cloud.platform"] = "azure_container_apps"

    if os.getenv("WEBSITE_SITE_NAME"):
        attributes["cloud.provider"] = "azure"
        attributes["cloud.platform"] = "azure_app_service"

    running_on_kubernetes = bool(os.getenv("KUBERNETES_SERVICE_HOST"))
    k8s_cluster_name = _first_env("K8S_CLUSTER_NAME", "AKS_CLUSTER_NAME")
    k8s_namespace_name = _first_env("K8S_NAMESPACE_NAME", "POD_NAMESPACE")
    k8s_node_name = _first_env("K8S_NODE_NAME", "NODE_NAME")
    k8s_pod_name = _first_env("K8S_POD_NAME", "POD_NAME") or (os.getenv("HOSTNAME") if running_on_kubernetes else None)

    if running_on_kubernetes or k8s_cluster_name or k8s_namespace_name or k8s_pod_name:
        attributes["cloud.provider"] = "azure"
        attributes["cloud.platform"] = "azure_aks"

    optional_attributes = {
        "k8s.cluster.name": k8s_cluster_name,
        "k8s.namespace.name": k8s_namespace_name,
        "k8s.node.name": k8s_node_name,
        "k8s.pod.name": k8s_pod_name,
        "container.id": os.getenv("CONTAINER_ID"),
        "container.name": _first_env("CONTAINER_NAME", "CONTAINER_APP_NAME"),
    }
    attributes.update({key: value for key, value in optional_attributes.items() if value})
    return attributes


class LogSampler:
    #Initializes the requested work.
    def __init__(self, logger: CloudOpsLogger) -> None:
        self._logger = logger
        self._batch_map: dict[str, LogBatch] = {}
        self._probabilistic_sampling_rate = _sampling_rate()

    #Adds log.
    def add_log(self, log_entry: LogEntry) -> None:
        if self._probabilistic_sampling_rate == 0:
            self._logger.process_log(log_entry)
            return

        invocation_id = log_entry.invocation_id
        if not invocation_id or invocation_id == "unknown":
            self._logger.process_log(log_entry)
            return

        if invocation_id in self._batch_map:
            self._batch_map[invocation_id].logs.append(log_entry)
            return

        self.flush_one_batch()
        self._batch_map[invocation_id] = LogBatch(logs=[log_entry])

    #Flushes one batch.
    def flush_one_batch(self) -> None:
        for invocation_id, batch in list(self._batch_map.items()):
            has_error = any(log.level == "error" for log in batch.logs)
            if has_error or self._should_sample():
                for log_entry in batch.logs:
                    self._logger.process_log(log_entry)

            self._batch_map.pop(invocation_id, None)

    #Decides whether to sample.
    def _should_sample(self) -> bool:
        threshold = max(0, min(100, self._probabilistic_sampling_rate)) / 100
        return random.random() <= threshold


class CloudOpsLogger:
    #Initializes the requested work.
    def __init__(self, name: str | None = None) -> None:
        self.resource_attributes = _runtime_resource_attributes()
        self.enabled_levels = _parse_log_levels(os.getenv("OTEL_LOG_LEVEL"))
        self.exporters_list = _parse_string_list(os.getenv("OTEL_BACKEND_EXPORTERS"), DEFAULT_EXPORTERS)
        self._logger_name = name or self.resource_attributes["service.name"]
        self._use_console = False
        self._use_otel = False
        self._logger_provider: Any = None
        self._otel_logging_handler: logging.Handler | None = None
        self._otel_python_logger = logging.getLogger(f"cloudops.otel.logs.{self._logger_name}")
        self._previous_trace_id: str | None = None
        self._unique_id: str | None = None
        self._sampler = LogSampler(self)
        self._init()

    @classmethod
    #Initializes logger.
    def initialise_logger(cls) -> "CloudOpsLogger":
        return logger

    @classmethod
    #Initializes logger.
    def initialize_logger(cls) -> "CloudOpsLogger":
        return logger

    #Handles info.
    def info(self, message: Any = None, *optional_params: Any) -> None:
        self.log("info", message, *optional_params)

    #Handles error.
    def error(self, message: Any = None, *optional_params: Any) -> None:
        self.log("error", message, *optional_params)

    #Handles debug.
    def debug(self, message: Any = None, *optional_params: Any) -> None:
        self.log("debug", message, *optional_params)

    #Handles warn.
    def warn(self, message: Any = None, *optional_params: Any) -> None:
        self.log("warn", message, *optional_params)

    #Logs the requested work.
    def log(self, level: LogLevel, message: Any = None, *optional_params: Any) -> None:
        current_trace_id = _current_trace_id()
        if current_trace_id != self._previous_trace_id:
            self._unique_id = str(uuid4())
            self._previous_trace_id = current_trace_id

        self._sampler.add_log(LogEntry(
            invocation_id=self._unique_id or "unknown",
            level=level,
            message=message,
            optional_params=optional_params,
        ))

    #Processes log.
    def process_log(self, log_entry: LogEntry) -> None:
        if log_entry.level not in self.enabled_levels:
            return

        rendered = self._render(log_entry.message, log_entry.optional_params)
        if self._use_console:
            print(rendered, file=sys.stderr if log_entry.level == "error" else sys.stdout)

        if self._use_otel:
            attributes = self._log_attributes(log_entry.invocation_id)
            self._otel_python_logger.log(
                _python_log_level(log_entry.level),
                rendered,
                exc_info=log_entry.message if isinstance(log_entry.message, BaseException) else None,
                extra=attributes,
            )

    #Exports logs.
    def export_logs(self) -> None:
        self._sampler.flush_one_batch()
        if self._logger_provider:
            try:
                self._logger_provider.force_flush(timeout_millis=30000)
            except TypeError:
                self._logger_provider.force_flush()

    #Initializes the requested work.
    def _init(self) -> None:
        if len(self.exporters_list) <= 1 and "console" in {item.lower() for item in self.exporters_list}:
            self._use_console = True
            return

        exporter_parameters = _read_exporter_parameters()
        if exporter_parameters.is_empty():
            self._use_console = True
            return

        for exporter in [item.lower() for item in self.exporters_list]:
            if exporter == "console":
                self._use_console = True
            elif exporter == "otel":
                self._initialise_otel(exporter_parameters)
            else:
                self._use_console = True

    #Initializes OTel.
    def _initialise_otel(self, exporter_parameters: ExporterParameters) -> None:
        config = exporter_parameters.backend("otel").logs if exporter_parameters.backend("otel") else None
        org_id = _org_id()
        if not config or not config.url or not org_id or not _otel_available():
            self._use_console = True
            return

        resource = Resource.create(self.resource_attributes)
        self._logger_provider = LoggerProvider(resource=resource)
        exporter_options: dict[str, Any] = {
            "endpoint": config.url,
            "headers": {"X-OrgId": org_id},
        }
        exporter = OTLPLogExporter(**exporter_options)
        self._logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
        set_logger_provider(self._logger_provider)

        self._otel_python_logger.setLevel(logging.DEBUG)
        self._otel_python_logger.propagate = False
        self._otel_logging_handler = LoggingHandler(level=logging.DEBUG, logger_provider=self._logger_provider)
        self._otel_python_logger.handlers = [
            handler for handler in self._otel_python_logger.handlers
            if not getattr(handler, "_cloudops_otel_handler", False)
        ]
        setattr(self._otel_logging_handler, "_cloudops_otel_handler", True)
        self._otel_python_logger.addHandler(self._otel_logging_handler)
        self._use_otel = True

    #Logs attributes.
    def _log_attributes(self, invocation_id: str) -> dict[str, Any]:
        attributes: dict[str, Any] = {"invocation.id": invocation_id or "unknown"}

        if baggage is not None:
            for key, value in baggage.get_all().items():
                attributes[f"baggage.{key}"] = value

        span_context = _span_context()
        if span_context is not None and getattr(span_context, "is_valid", False):
            attributes["otel-trace-id"] = f"{span_context.trace_id:032x}"
            attributes["otel-span-id"] = f"{span_context.span_id:016x}"

        return attributes

    #Renders the requested work.
    def _render(self, message: Any, optional_params: tuple[Any, ...]) -> str:
        rendered = self._stringify(message)
        if optional_params:
            rendered = f"{rendered}\n" + "\n".join(self._stringify(param) for param in optional_params)

        return rendered

    @staticmethod
    #Turns into text the requested work.
    def _stringify(value: Any) -> str:
        if isinstance(value, BaseException):
            return repr(value)
        if isinstance(value, Mapping):
            return json.dumps(value, default=str, sort_keys=True)
        if isinstance(value, tuple | list):
            return json.dumps(value, default=str)
        return str(value)


#Gets sampling rate.
def _sampling_rate() -> float:
    try:
        return float(os.getenv("OTEL_LOGS_SAMPLING_RATE", "100"))
    except ValueError:
        return 100


#Handles span context.
def _span_context() -> Any:
    if trace is None:
        return None

    span = trace.get_current_span()
    if span is None:
        return None

    return span.get_span_context()


#Gets current trace ID.
def _current_trace_id() -> str:
    span_context = _span_context()
    if span_context is not None and getattr(span_context, "is_valid", False):
        return f"{span_context.trace_id:032x}"

    return "unknown"


#Handles python log level.
def _python_log_level(level: LogLevel) -> int:
    if level == "error":
        return logging.ERROR
    if level == "warn":
        return logging.WARNING
    if level == "debug":
        return logging.DEBUG
    return logging.INFO


#Handles OTel available.
def _otel_available() -> bool:
    return all([
        set_logger_provider,
        OTLPLogExporter,
        LoggerProvider,
        LoggingHandler,
        BatchLogRecordProcessor,
        Resource,
    ])


logger = CloudOpsLogger()
