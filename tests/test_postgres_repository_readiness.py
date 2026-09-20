from dataclasses import replace
from hashlib import sha256
import unittest
from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.postgres_repository_readiness import WORKSTREAMS,REQUIRED_GATES,build_readiness_portfolio,readiness_evidence,validate_readiness_portfolio
h=lambda x:sha256(x).hexdigest()
class Tests(unittest.TestCase):
 def setUp(self):self.controls=build_readiness_portfolio(h(b"repository-evidence"))
 def test_complete_continuous_portfolio(self):
  e=readiness_evidence(self.controls);self.assertEqual(e["feature_count"],200);self.assertEqual(e["features"],list(range(501,701)));self.assertEqual(len(e["workstreams"]),8);self.assertTrue(all(x["control_count"]==25 for x in e["workstreams"]))
 def test_all_workstreams_are_exactly_25_controls(self):
  for start,end,name in WORKSTREAMS:self.assertEqual([x.workstream for x in self.controls].count(name),25);self.assertEqual(end-start+1,25)
 def test_safety_boundary_is_closed(self):
  e=readiness_evidence(self.controls)
  for k,v in e.items():
   if k.endswith("_used") or k.endswith("_executed") or k.endswith("_allowed") or k.endswith("_accessed"):self.assertFalse(v)
 def test_missing_duplicate_and_reordered_features_fail(self):
  with self.assertRaises(GovernanceRejected):validate_readiness_portfolio(self.controls[:-1])
  bad=list(self.controls);bad[2]=bad[1]
  with self.assertRaises(GovernanceRejected):validate_readiness_portfolio(tuple(bad))
  with self.assertRaises(GovernanceRejected):validate_readiness_portfolio(tuple(reversed(self.controls)))
 def test_tampering_and_gate_drift_fail(self):
  bad=list(self.controls);bad[40]=replace(bad[40],digest=h(b"tampered"))
  with self.assertRaises(GovernanceRejected):validate_readiness_portfolio(tuple(bad))
  drift=list(self.controls);drift[80]=replace(drift[80],gates=REQUIRED_GATES+("LIVE_DB",))
  with self.assertRaises(GovernanceRejected):validate_readiness_portfolio(tuple(drift))
 def test_invalid_source_digest_fails(self):
  with self.assertRaises(GovernanceRejected):build_readiness_portfolio("bad")
if __name__=="__main__":unittest.main()
