from datetime import UTC,datetime
from hashlib import sha256
import unittest
from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_dispute_observatory import DisputeObservatory
h=lambda x:sha256(x).hexdigest()
def complete():
 o=DisputeObservatory(h(b"manifest"),h(b"policy"))
 rows=({"case_id":"synthetic:case:1","currency":"KRW","state":"CLOSURE_RECONCILED","lineage_digest":h(b"lineage"),"reason":"SERVICE","merchant_ref":"synthetic:merchant:1","received_at":"2026-09-01T00:00:00+00:00","exposure_minor":1000},)
 o.projection(rows,"synthetic:key:366");o.cohorts(("age","currency","merchant","reason"),"synthetic:key:367",1);o.exposure((("KRW",1000),),"synthetic:key:368",2);o.aging(datetime(2026,9,18,tzinfo=UTC),(17,),"synthetic:key:369",3);o.deadline_risk(48,60,"synthetic:key:370",4);o.reason_concentration((("SERVICE",10000),),"synthetic:key:371",5);o.merchant_concentration((("synthetic:merchant:1","KRW",1000),),"synthetic:key:372",6);o.duplicate_clusters((("synthetic:case:1","synthetic:case:2"),),"synthetic:key:373",7);o.evidence_coverage(("AUTH","DELIVERY"),("AUTH","DELIVERY","COMMUNICATION"),"synthetic:key:374",8);o.independence("synthetic:actor:intake","synthetic:actor:reviewer","synthetic:actor:verifier","synthetic:key:375",9);o.impact_ceiling(900,1000,False,"synthetic:key:376",10);o.anomalies(("CONCENTRATION_HIGH","COVERAGE_LOW","DEADLINE_HIGH","IMPACT_NEAR_CEILING"),("COVERAGE_LOW",),"synthetic:key:377",11);o.alert_dockets(("synthetic:alert:coverage",),"synthetic:key:378",12);o.snapshot(None,"synthetic:key:379",13);o.report(("ALERTS_READ_ONLY","NO_AUTO_ACTION","NO_CURRENCY_COLLAPSE","ROLE_SEPARATION"),"synthetic:key:380",14);return o
class Tests(unittest.TestCase):
 def test_complete_read_only_report(self):
  e=complete().evidence();self.assertEqual(e["features"],list(range(366,381)))
  forbidden=("raw_evidence_accessed","card_network_submission_allowed","payment_execution_allowed","refund_allowed","settlement_allowed","transfer_allowed","ledger_posting_allowed","external_api_used","deployment_allowed","production_credentials_accessed","automatic_policy_change_allowed","operator_final_approval_granted")
  self.assertTrue(e["synthetic_only"]);self.assertTrue(e["read_only"])
  for k in forbidden:self.assertFalse(e[k])
 def test_skip_and_stale_version_fail_closed(self):
  o=DisputeObservatory(h(b"m"),h(b"p"))
  with self.assertRaises(GovernanceRejected):o.cohorts(("age",),"synthetic:key:x",0)
  rows=({"case_id":"synthetic:case:1","currency":"KRW","state":"CLOSURE_RECONCILED","lineage_digest":h(b"l"),"reason":"OTHER","merchant_ref":"synthetic:merchant:1","received_at":"x","exposure_minor":0},)
  o.projection(rows,"synthetic:key:1")
  with self.assertRaises(GovernanceRejected):o.cohorts(("age",),"synthetic:key:2",0)
 def test_idempotent_replay_and_conflict(self):
  o=DisputeObservatory(h(b"m"),h(b"p"));rows=({"case_id":"synthetic:case:1","currency":"KRW","state":"CLOSURE_RECONCILED","lineage_digest":h(b"l"),"reason":"OTHER","merchant_ref":"synthetic:merchant:1","received_at":"x","exposure_minor":0},)
  a=o.projection(rows,"synthetic:key:same");self.assertIs(a,o.projection(rows,"synthetic:key:same"))
  changed=({**rows[0],"exposure_minor":1},)
  with self.assertRaises(GovernanceRejected):o.projection(changed,"synthetic:key:same")
 def test_financial_currency_and_role_boundaries(self):
  o=complete()
  with self.assertRaises(GovernanceRejected):DisputeObservatory(h(b"m"),h(b"p")).exposure((("KRW",-1),),"synthetic:key:e",0)
  x=DisputeObservatory(h(b"m"),h(b"p"))
  with self.assertRaises(GovernanceRejected):x.independence("synthetic:actor:a","synthetic:actor:a","synthetic:actor:b","synthetic:key:i",0)
 def test_input_order_is_deterministic(self):
  base={"currency":"KRW","state":"CLOSURE_RECONCILED","reason":"OTHER","received_at":"x","exposure_minor":0}
  a={**base,"case_id":"synthetic:case:a","merchant_ref":"synthetic:merchant:a","lineage_digest":h(b"a")};b={**base,"case_id":"synthetic:case:b","merchant_ref":"synthetic:merchant:b","lineage_digest":h(b"b")}
  x=DisputeObservatory(h(b"m"),h(b"p")).projection((a,b),"synthetic:key:k").digest;y=DisputeObservatory(h(b"m"),h(b"p")).projection((b,a),"synthetic:key:k").digest;self.assertEqual(x,y)
 def test_duplicate_concentration_keys_fail_closed(self):
  o=DisputeObservatory(h(b"m"),h(b"p"))
  with self.assertRaises(GovernanceRejected):o.reason_concentration((("SERVICE",5000),("SERVICE",5000)),"synthetic:key:r",0)
  with self.assertRaises(GovernanceRejected):o.merchant_concentration((("synthetic:merchant:1","KRW",500),("synthetic:merchant:1","KRW",500)),"synthetic:key:m",0)
