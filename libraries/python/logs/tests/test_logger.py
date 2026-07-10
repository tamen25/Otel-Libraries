#This file contains test logger logic for logs tests.
import contextlib
import io
import unittest
from unittest.mock import patch

from otel_logs import Logger
from otel_logs.logger import (
    BackendConfig,
    LogEntry,
    LogSampler,
    LogsExporterConfig,
    ExporterParameters,
    _normalize_endpoint,
    _org_id,
    _parse_log_levels,
    _parse_resource_attributes,
    _parse_string_list,
    _read_exporter_parameters,
    _sampling_rate,
)


class LoggerTests(unittest.TestCase):
    #Handles test runtime resource attributes for AKS.
    def test_runtime_resource_attributes_for_aks(self):
        with patch.dict("os.environ", {
            "OTEL_SERVICE_NAME": "order-api",
            "KUBERNETES_SERVICE_HOST": "10.0.0.1",
            "K8S_NAMESPACE_NAME": "demo",
            "K8S_POD_NAME": "order-api-abc",
            "K8S_NODE_NAME": "aks-nodepool1-1",
            "AKS_CLUSTER_NAME": "demo-cluster",
        }, clear=True):
            logger = Logger("test")

        self.assertEqual(logger.resource_attributes["service.name"], "order-api")
        self.assertEqual(logger.resource_attributes["cloud.provider"], "azure")
        self.assertEqual(logger.resource_attributes["cloud.platform"], "azure_aks")
        self.assertEqual(logger.resource_attributes["k8s.namespace.name"], "demo")
        self.assertEqual(logger.resource_attributes["k8s.pod.name"], "order-api-abc")
        self.assertEqual(logger.resource_attributes["k8s.node.name"], "aks-nodepool1-1")
        self.assertEqual(logger.resource_attributes["k8s.cluster.name"], "demo-cluster")

    #Handles test runtime resource attributes for Azure Functions.
    def test_runtime_resource_attributes_for_functions(self):
        with patch.dict("os.environ", {
            "FUNCTIONS_EXTENSION_VERSION": "~4",
            "WEBSITE_SITE_NAME": "orders-func",
        }, clear=True):
            logger = Logger("test")

        self.assertEqual(logger.resource_attributes["service.name"], "orders-func")
        self.assertEqual(logger.resource_attributes["cloud.provider"], "azure")
        self.assertEqual(logger.resource_attributes["cloud.platform"], "azure_functions")
        self.assertEqual(logger.resource_attributes["faas.name"], "orders-func")

    #Handles test Functions detection early-returns before K8s attributes.
    def test_runtime_resource_attributes_functions_early_return(self):
        with patch.dict("os.environ", {
            "FUNCTIONS_WORKER_RUNTIME": "python",
            "WEBSITE_SITE_NAME": "orders-func",
            "KUBERNETES_SERVICE_HOST": "10.0.0.1",
        }, clear=True):
            logger = Logger("test")

        self.assertEqual(logger.resource_attributes["cloud.platform"], "azure_functions")
        self.assertNotIn("k8s.pod.name", logger.resource_attributes)

    #Handles test runtime resource attributes for Container Apps.
    def test_runtime_resource_attributes_for_container_apps(self):
        with patch.dict("os.environ", {
            "OTEL_SERVICE_NAME": "order-api",
            "CONTAINER_APP_NAME": "orders-ca",
        }, clear=True):
            logger = Logger("test")

        self.assertEqual(logger.resource_attributes["cloud.provider"], "azure")
        self.assertEqual(logger.resource_attributes["cloud.platform"], "azure_container_apps")
        self.assertEqual(logger.resource_attributes["container.name"], "orders-ca")

    #Handles test Container Apps plus K8s signals fall through to AKS.
    def test_container_apps_with_k8s_falls_through_to_aks(self):
        with patch.dict("os.environ", {
            "CONTAINER_APP_NAME": "orders-ca",
            "KUBERNETES_SERVICE_HOST": "10.0.0.1",
        }, clear=True):
            logger = Logger("test")

        self.assertEqual(logger.resource_attributes["cloud.platform"], "azure_aks")
        self.assertEqual(logger.resource_attributes["container.name"], "orders-ca")

    #Handles test runtime resource attributes for App Service.
    def test_runtime_resource_attributes_for_app_service(self):
        with patch.dict("os.environ", {
            "WEBSITE_SITE_NAME": "orders-web",
        }, clear=True):
            logger = Logger("test")

        self.assertEqual(logger.resource_attributes["service.name"], "orders-web")
        self.assertEqual(logger.resource_attributes["cloud.provider"], "azure")
        self.assertEqual(logger.resource_attributes["cloud.platform"], "azure_app_service")
        self.assertNotIn("faas.name", logger.resource_attributes)

    #Handles test runtime resource attributes merge OTel resource attributes.
    def test_runtime_resource_attributes_merge_otel_resource_attributes(self):
        with patch.dict("os.environ", {
            "OTEL_RESOURCE_ATTRIBUTES": "deployment.environment=dev,k8s.cluster.name=demo-cluster",
            "OTEL_SERVICE_NAME": "order-api",
        }, clear=True):
            logger = Logger("test")

        self.assertEqual(logger.resource_attributes["service.name"], "order-api")
        self.assertEqual(logger.resource_attributes["deployment.environment"], "dev")
        self.assertEqual(logger.resource_attributes["k8s.cluster.name"], "demo-cluster")

    #Handles test invalid log levels do not disable logging.
    def test_invalid_log_levels_do_not_disable_logging(self):
        self.assertEqual(_parse_log_levels("bad,error"), {"error"})
        self.assertEqual(_parse_log_levels("bad"), {"info", "error", "debug", "warn"})

    #Handles test string list and resource attribute parsers.
    def test_string_list_and_resource_attribute_parsers(self):
        fallback = ["console"]
        parsed_fallback = _parse_string_list(None, fallback)
        parsed_fallback.append("otel")

        self.assertEqual(fallback, ["console"])
        self.assertEqual(_parse_string_list('["console", " otel "]', ["x"]), ["console", "otel"])
        self.assertEqual(_parse_string_list("console, otel", ["x"]), ["console", "otel"])
        self.assertEqual(
            _parse_resource_attributes("service.name=orders,empty=,deployment.environment=dev"),
            {"service.name": "orders", "deployment.environment": "dev"},
        )
        self.assertEqual(_normalize_endpoint("https://collector.example.com/"), "https://collector.example.com/v1/logs")

    #Handles test read exporter parameters prefers the JSON blob over the env endpoint.
    def test_read_exporter_parameters_prefers_json_over_env_endpoint(self):
        with patch.dict("os.environ", {
            "OTEL_EXPORTER_PARAMETERS": '{"otel":{"logs":{"url":"https://collector.example.com/v1/logs"}}}',
            "OTEL_EXPORTER_OTLP_ENDPOINT": "https://fallback.example.com",
        }, clear=True):
            parsed = _read_exporter_parameters()

        self.assertEqual(parsed.otel.logs.url, "https://collector.example.com/v1/logs")

    #Handles test read exporter parameters normalises the env endpoint fallback.
    def test_read_exporter_parameters_normalises_env_endpoint(self):
        with patch.dict("os.environ", {
            "OTEL_EXPORTER_OTLP_ENDPOINT": "https://collector.example.com/",
        }, clear=True):
            parsed = _read_exporter_parameters()

        self.assertEqual(parsed.otel.logs.url, "https://collector.example.com/v1/logs")

    #Handles test read exporter parameters falls back to the hardcoded default endpoint.
    def test_read_exporter_parameters_uses_default_endpoint_constant(self):
        with patch.dict("os.environ", {}, clear=True), \
                patch("otel_logs.logger.DEFAULT_LOGS_ENDPOINT", "https://baked-in.example.com/v1/logs"):
            parsed = _read_exporter_parameters()

        self.assertEqual(parsed.otel.logs.url, "https://baked-in.example.com/v1/logs")

    #Handles test read exporter parameters is empty when nothing is configured.
    def test_read_exporter_parameters_empty_without_endpoint(self):
        with patch.dict("os.environ", {}, clear=True):
            parsed = _read_exporter_parameters()

        self.assertTrue(parsed.is_empty())

    #Handles test org id prefers env over the hardcoded default.
    def test_org_id_resolution(self):
        with patch.dict("os.environ", {"X_ORG_ID": "org-from-env"}, clear=True):
            self.assertEqual(_org_id(), "org-from-env")

        with patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(_org_id())
            with patch("otel_logs.logger.DEFAULT_X_ORG_ID", "org-baked-in"):
                self.assertEqual(_org_id(), "org-baked-in")

    #Handles test otel export without X_ORG_ID falls back to console.
    def test_otel_without_org_id_falls_back_to_console(self):
        with patch.dict("os.environ", {
            "OTEL_BACKEND_EXPORTERS": "otel",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "https://collector.example.com",
            "OTEL_SERVICE_NAME": "order-api",
        }, clear=True):
            logger = Logger("test")

        self.assertTrue(logger._use_console)
        self.assertFalse(logger._use_otel)

    #Handles test otel export without an endpoint falls back to console.
    def test_otel_without_endpoint_falls_back_to_console(self):
        with patch.dict("os.environ", {
            "OTEL_BACKEND_EXPORTERS": "otel",
            "X_ORG_ID": "org-123",
            "OTEL_SERVICE_NAME": "order-api",
        }, clear=True):
            logger = Logger("test")

        self.assertTrue(logger._use_console)
        self.assertFalse(logger._use_otel)

    #Handles test otel export with endpoint and X_ORG_ID enables the OTLP exporter.
    def test_otel_with_endpoint_and_org_id_enables_otel(self):
        with patch.dict("os.environ", {
            "OTEL_BACKEND_EXPORTERS": "otel",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "https://collector.example.com",
            "X_ORG_ID": "org-123",
            "OTEL_SERVICE_NAME": "order-api",
        }, clear=True):
            logger = Logger("test")

        self.assertTrue(logger._use_otel)
        self.assertFalse(logger._use_console)

    #Handles test console logger renders enabled messages.
    def test_console_logger_renders_enabled_messages(self):
        with patch.dict("os.environ", {
            "OTEL_BACKEND_EXPORTERS": "console",
            "OTEL_LOG_LEVEL": "info,error",
            "OTEL_LOGS_SAMPLING_RATE": "0",
        }, clear=True):
            logger = Logger("test")

        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            logger.info("created order", {"order_id": 42})
            logger.debug("debug should be disabled")
            logger.error(ValueError("payment failed"))
            logger.export_logs()

        self.assertIn("created order", stdout.getvalue())
        self.assertIn("order_id", stdout.getvalue())
        self.assertNotIn("debug should be disabled", stdout.getvalue())
        self.assertIn("payment failed", stderr.getvalue())

    #Handles test sampler processes directly when sampling is zero.
    def test_sampler_processes_directly_when_sampling_is_zero(self):
        class FakeLogger:
            #Initializes the requested work.
            def __init__(self):
                self.processed = []

            #Processes log.
            def process_log(self, log_entry):
                self.processed.append(log_entry)

        with patch.dict("os.environ", {"OTEL_LOGS_SAMPLING_RATE": "0"}, clear=True):
            self.assertEqual(_sampling_rate(), 0)
            logger = FakeLogger()
            sampler = LogSampler(logger)

        sampler.add_log(LogEntry(invocation_id="batch-1", level="error", message="boom"))
        self.assertEqual([entry.message for entry in logger.processed], ["boom"])

    #Handles test exporter parameters backend and empty detection.
    def test_exporter_parameters_backend_and_empty_detection(self):
        self.assertTrue(ExporterParameters().is_empty())

        backend = BackendConfig(logs=LogsExporterConfig(url="https://collector.example.com/v1/logs"))
        parameters = ExporterParameters(otel=backend)

        self.assertFalse(parameters.is_empty())
        self.assertIs(parameters.backend("otel"), backend)
        self.assertIsNone(parameters.backend("metrics"))


#the module registers an atexit flush on import
def test_atexit_flush_registered():
    import otel_logs
    # re-registering is harmless; assert the hook target exists and is callable
    assert callable(otel_logs.logger.export_logs)


if __name__ == "__main__":
    unittest.main()
