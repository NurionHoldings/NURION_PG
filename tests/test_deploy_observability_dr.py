import json,unittest
from scripts.deploy_preflight import validate as preflight
from scripts.validate_deploy_observability_dr_closure import validate
from nurion_pg.observability import METRICS,MetricsRegistry,structured_log
class OpsTests(unittest.TestCase):
 def test_preflight_requires_digest_and_hardened_manifest(self):
  with self.assertRaises(ValueError):preflight({"NURION_PG_ENV":"staging"})
  with self.assertRaises(ValueError):preflight({"NURION_PG_ENV":"staging","NURION_PG_IMAGE_DIGEST":"sha256:"+"a"*64,"NURION_PG_BASE_IMAGE":"python:latest"})
  value=preflight({"NURION_PG_ENV":"staging","NURION_PG_IMAGE_DIGEST":"sha256:"+"a"*64,"NURION_PG_BASE_IMAGE":"python@sha256:"+"b"*64});self.assertFalse(value["external_deployment_performed"])
 def test_structured_log_redacts_secrets(self):
  value=json.loads(structured_log("provider",correlation_id="c1",merchant_id="m-safe",authorization="Basic secret",paymentKey="pk",nested={"api_key":"nested"},status="unknown"));self.assertEqual(value["authorization"],"[REDACTED]");self.assertEqual(value["paymentKey"],"[REDACTED]");self.assertEqual(value["nested"]["api_key"],"[REDACTED]");self.assertEqual(len(value["merchant_ref"]),16);self.assertNotEqual(value["merchant_ref"],"m-safe")
 def test_metrics_cover_financial_runtime(self):
  for name in ("http_request_errors_total","payment_operation_queue_depth","provider_unknown_total","outbox_oldest_unpublished_seconds","ledger_imbalance","payout_pending_total","migration_version","backup_restore_age_seconds"):self.assertIn(name,METRICS)
  registry=MetricsRegistry();registry.set("ledger_imbalance",0);registry.increment("provider_unknown_total");rendered=registry.render();self.assertIn("provider_unknown_total 1.0",rendered);self.assertIn("ledger_imbalance 0.0",rendered)
 def test_closure(self):self.assertEqual(validate()["criteria_passed"],23)
if __name__=="__main__":unittest.main()
