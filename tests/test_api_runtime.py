import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from fastapi import Query
from nurion_pg.api.app import create_app
from nurion_pg.api.settings import Settings

class SettingsTests(unittest.TestCase):
    def test_defaults_and_public_view_exclude_environment_secrets(self):
        with patch.dict(os.environ,{"NURION_PG_SECRET_TOKEN":"must-not-leak"},clear=True):
            view=Settings.from_env().public_view();self.assertNotIn("secret",str(view).lower());self.assertNotIn("must-not-leak",str(view))
    def test_invalid_environment_port_and_log_level_fail_closed(self):
        for values in ({"NURION_PG_ENV":"invalid"},{"NURION_PG_PORT":"zero"},{"NURION_PG_PORT":"70000"},{"NURION_PG_LOG_LEVEL":"TRACE"},{"NURION_PG_MAX_REQUEST_BYTES":"100"},{"NURION_PG_GRACEFUL_SHUTDOWN_SECONDS":"0"}):
            with patch.dict(os.environ,values,clear=True),self.assertRaises(ValueError):Settings.from_env()

class RuntimeTests(unittest.TestCase):
    def setUp(self):self.app=create_app(Settings(environment="test",max_request_bytes=1024));self.client=TestClient(self.app)
    def test_liveness(self):self.assertEqual(self.client.get("/health/live").json(),{"status":"alive","service":"nurion-pg-api"})
    def test_readiness(self):self.assertEqual(self.client.get("/health/ready").status_code,200);self.app.state.ready=False;self.assertEqual(self.client.get("/health/ready").status_code,503)
    def test_correlation_id_generated_and_valid_incoming_preserved(self):
        response=self.client.get("/health/live");self.assertTrue(response.headers["x-correlation-id"])
        response=self.client.get("/health/live",headers={"x-correlation-id":"trace-123"});self.assertEqual(response.headers["x-correlation-id"],"trace-123")
    def test_invalid_correlation_id_replaced(self):
        response=self.client.get("/health/live",headers={"x-correlation-id":"x"*129});self.assertNotEqual(response.headers["x-correlation-id"],"x"*129)
    def test_unhandled_error_uses_safe_envelope(self):
        @self.app.get("/_test/boom")
        async def boom():raise RuntimeError("sensitive-detail")
        response=self.client.get("/_test/boom",headers={"x-correlation-id":"failure-123"})
        self.assertEqual(response.status_code,500)
        self.assertEqual(response.json(),{"error":{"code":"INTERNAL_ERROR","message":"Internal server error","correlation_id":"failure-123"}})
        self.assertNotIn("sensitive-detail",response.text)
    def test_production_disables_interactive_docs(self):
        client=TestClient(create_app(Settings(environment="production")))
        self.assertEqual(client.get("/docs").status_code,404)
    def test_security_headers_and_runtime_info_exclude_secrets(self):
        response=self.client.get("/runtime/info")
        for header in ("x-content-type-options","x-frame-options","referrer-policy","cache-control"):self.assertIn(header,response.headers)
        self.assertNotIn("api_keys",response.text);self.assertNotIn("secret",response.text.lower())
    def test_startup_and_not_ready_retry_contract(self):
        self.assertEqual(self.client.get("/health/startup").json()["status"],"started")
        self.app.state.ready=False;response=self.client.get("/health/ready");self.assertEqual(response.headers["retry-after"],"5")
    def test_request_size_and_content_length_fail_closed(self):
        oversized=self.client.post("/unknown",headers={"content-length":"2048"})
        malformed=self.client.post("/unknown",headers={"content-length":"invalid"})
        self.assertEqual(oversized.status_code,413);self.assertEqual(oversized.json()["error"]["code"],"REQUEST_TOO_LARGE")
        self.assertEqual(malformed.status_code,400);self.assertEqual(malformed.json()["error"]["code"],"INVALID_CONTENT_LENGTH")
    def test_framework_errors_use_standard_envelope(self):
        @self.app.get("/_test/number")
        async def number(value:int=Query()):return {"value":value}
        missing=self.client.get("/not-found",headers={"x-correlation-id":"not-found"})
        invalid=self.client.get("/_test/number?value=nope",headers={"x-correlation-id":"invalid"})
        self.assertEqual(missing.json()["error"],{"code":"ROUTE_NOT_FOUND","message":"Request could not be served","correlation_id":"not-found"})
        self.assertEqual(invalid.json()["error"]["code"],"REQUEST_VALIDATION_FAILED")

if __name__=="__main__":unittest.main()
