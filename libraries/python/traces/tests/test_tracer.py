#This file contains test tracer logic for traces tests.
import unittest
from unittest.mock import patch

from cloudops_otel_traces.tracer import (
    _normalize_endpoint,
    _org_id,
    _parse_list,
    _read_traces_endpoint,
    _runtime_resource_attributes,
)


class TracerHelperTests(unittest.TestCase):
    #Handles test normalize endpoint appends traces path.
    def test_normalize_endpoint(self):
        self.assertEqual(_normalize_endpoint("https://c.example.com/"), "https://c.example.com/v1/traces")
        self.assertEqual(_normalize_endpoint("https://c.example.com/v1/traces"), "https://c.example.com/v1/traces")
        self.assertIsNone(_normalize_endpoint(None))

    #Handles test parse list from JSON and CSV.
    def test_parse_list(self):
        self.assertEqual(_parse_list('["console","otel"]', ["x"]), ["console", "otel"])
        self.assertEqual(_parse_list("console, otel", ["x"]), ["console", "otel"])
        self.assertEqual(_parse_list(None, ["console"]), ["console"])

    #Handles test read traces endpoint prefers JSON then env.
    def test_read_traces_endpoint(self):
        with patch.dict("os.environ", {
            "OTEL_EXPORTER_PARAMETERS": '{"otel":{"trace":{"url":"https://collector.example.com/v1/traces"}}}',
            "OTEL_EXPORTER_OTLP_ENDPOINT": "https://fallback.example.com",
        }, clear=True):
            self.assertEqual(_read_traces_endpoint(), "https://collector.example.com/v1/traces")

        with patch.dict("os.environ", {"OTEL_EXPORTER_OTLP_ENDPOINT": "https://c.example.com"}, clear=True):
            self.assertEqual(_read_traces_endpoint(), "https://c.example.com/v1/traces")

        with patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(_read_traces_endpoint())

    #Handles test org id resolution.
    def test_org_id(self):
        with patch.dict("os.environ", {"X_ORG_ID": "org-1"}, clear=True):
            self.assertEqual(_org_id(), "org-1")
        with patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(_org_id())

    #Handles test Azure runtime detection for AKS and Functions.
    def test_runtime_resource_attributes(self):
        with patch.dict("os.environ", {
            "OTEL_SERVICE_NAME": "order-api",
            "KUBERNETES_SERVICE_HOST": "10.0.0.1",
            "AKS_CLUSTER_NAME": "cloudops-dev",
            "POD_NAMESPACE": "cloudops",
        }, clear=True):
            attrs = _runtime_resource_attributes()
        self.assertEqual(attrs["service.name"], "order-api")
        self.assertEqual(attrs["cloud.provider"], "azure")
        self.assertEqual(attrs["cloud.platform"], "azure_aks")
        self.assertEqual(attrs["k8s.cluster.name"], "cloudops-dev")

        with patch.dict("os.environ", {
            "FUNCTIONS_EXTENSION_VERSION": "~4",
            "WEBSITE_SITE_NAME": "orders-func",
        }, clear=True):
            attrs = _runtime_resource_attributes()
        self.assertEqual(attrs["cloud.platform"], "azure_functions")
        self.assertEqual(attrs["faas.name"], "orders-func")


if __name__ == "__main__":
    unittest.main()
