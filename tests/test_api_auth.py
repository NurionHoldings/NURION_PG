import json
import unittest

from fastapi.testclient import TestClient

from nurion_pg.api.app import create_app
from nurion_pg.api.auth import ApiKeyRecord,ApiKeyRegistry,Role,secret_digest
from nurion_pg.api.settings import Settings


class ApiKeyRegistryTests(unittest.TestCase):
    def test_registry_rejects_duplicate_key_ids_and_plaintext_digest(self):
        record=ApiKeyRecord("key1",secret_digest("secret"),"user1","merchant1",frozenset({Role.MERCHANT_ADMIN}))
        with self.assertRaises(ValueError):ApiKeyRegistry([record,record])
        with self.assertRaises(ValueError):ApiKeyRecord("key1","secret","user1","merchant1",frozenset({Role.MERCHANT_ADMIN}))
        with self.assertRaises(ValueError):ApiKeyRecord("key_1",secret_digest("secret"),"user1","merchant1",frozenset({Role.MERCHANT_ADMIN}))

    def test_json_registry_uses_hash_only_records(self):
        raw=json.dumps([{"key_id":"key1","secret_sha256":secret_digest("secret"),"principal_id":"user1","merchant_id":"merchant1","roles":["auditor"]}])
        principal=ApiKeyRegistry.from_json(raw).authenticate("npg_key1_secret")
        self.assertEqual(principal.principal_id,"user1")
        self.assertIsNone(ApiKeyRegistry.from_json(raw).authenticate("npg_key1_wrong"))


class AuthBoundaryTests(unittest.TestCase):
    def setUp(self):
        records=[
            ApiKeyRecord("admin1",secret_digest("alpha"),"principal1","merchant1",frozenset({Role.MERCHANT_ADMIN})),
            ApiKeyRecord("disabled",secret_digest("beta"),"principal2","merchant1",frozenset({Role.AUDITOR}),False),
        ]
        self.client=TestClient(create_app(Settings(environment="test"),ApiKeyRegistry(records)))
        self.headers={"x-api-key":"npg_admin1_alpha","x-correlation-id":"auth-test"}

    def test_health_is_public_but_auth_context_is_protected(self):
        self.assertEqual(self.client.get("/health/live").status_code,200)
        response=self.client.get("/v1/auth/context",headers={"x-correlation-id":"missing-key"})
        self.assertEqual(response.status_code,401)
        self.assertEqual(response.json()["error"]["code"],"UNAUTHENTICATED")
        self.assertEqual(response.json()["error"]["correlation_id"],"missing-key")

    def test_valid_key_resolves_principal_without_returning_secret(self):
        response=self.client.get("/v1/auth/context",headers=self.headers)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json(),{"principal_id":"principal1","merchant_id":"merchant1","roles":["merchant_admin"],"key_id":"admin1"})
        self.assertNotIn("alpha",response.text)

    def test_disabled_and_wrong_keys_fail_closed(self):
        for credential in ("npg_disabled_beta","npg_admin1_wrong","invalid"):
            response=self.client.get("/v1/auth/context",headers={"x-api-key":credential})
            self.assertEqual(response.status_code,401)

    def test_same_tenant_is_allowed_and_cross_tenant_is_denied(self):
        allowed=self.client.get("/v1/merchants/merchant1/context",headers=self.headers)
        denied=self.client.get("/v1/merchants/merchant2/context",headers=self.headers)
        self.assertEqual(allowed.status_code,200)
        self.assertEqual(denied.status_code,403)
        self.assertEqual(denied.json()["error"]["code"],"CROSS_TENANT_ACCESS_DENIED")
        self.assertEqual(denied.json()["error"]["correlation_id"],"auth-test")


if __name__=="__main__":unittest.main()
