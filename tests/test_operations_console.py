import unittest
from fastapi.testclient import TestClient
from nurion_pg.api.app import create_app
from nurion_pg.api.auth import ApiKeyRecord,ApiKeyRegistry,Role,secret_digest
from nurion_pg.api.settings import Settings
from nurion_pg.operations import LimitedOperationPolicy
class OpsRepo:
 def payments(self,*_):return [{"payment_intent_id":"pi-1","status":"captured"}]
 def webhooks(self,*_):return [{"inbox_id":"wh-1","state":"quarantined"}]
 def settlements(self,*_):return [{"settlement_id":"st-1","state":"held"}]
 def audits(self,*_):return [{"audit_id":"a-1","outcome":"allowed"}]
 def approve_webhook_retry(self,merchant,inbox,principal,correlation):return (merchant,inbox,principal)==("m1","wh-1","admin") and bool(correlation)
class OperationsTests(unittest.TestCase):
 def setUp(self):
  records=[ApiKeyRecord("admin",secret_digest("s"),"admin","m1",frozenset({Role.MERCHANT_ADMIN})),ApiKeyRecord("aud",secret_digest("s"),"aud","m1",frozenset({Role.AUDITOR}))]
  self.client=TestClient(create_app(Settings(environment="test"),ApiKeyRegistry(records),operations_repository=OpsRepo()));self.admin={"x-api-key":"npg_admin_s"};self.aud={"x-api-key":"npg_aud_s"}
 def test_scoped_console_reads_and_masks_provider_identifiers(self):
  for path in ("payments","webhooks","settlements","audit"):
   value=self.client.get(f"/v1/merchants/m1/operations/{path}",headers=self.aud);self.assertEqual(value.status_code,200);self.assertNotIn("payment_key",value.text)
  self.assertEqual(self.client.get("/v1/merchants/other/operations/payments",headers=self.aud).status_code,403)
 def test_retry_requires_operations_writer(self):
  url="/v1/merchants/m1/operations/webhooks/wh-1/retry";self.assertEqual(self.client.post(url,headers=self.aud).status_code,403);self.assertEqual(self.client.post(url,headers=self.admin).json()["status"],"pending")
 def test_limited_gate_fails_closed_and_binds_cohort_amount_evidence(self):
  with self.assertRaises(ValueError):LimitedOperationPolicy.from_values(True,"m1",1000,"")
  gate=LimitedOperationPolicy.from_values(True,"m1",1000,"a"*64);gate.require("m1",1000)
  for merchant,amount in (("other",100),("m1",1001)):
   with self.assertRaises(PermissionError):gate.require(merchant,amount)
  self.assertFalse(gate.public_view()["live_money_movement"])
if __name__=="__main__":unittest.main()
