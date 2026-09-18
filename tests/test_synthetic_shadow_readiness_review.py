from datetime import UTC,datetime,timedelta
from hashlib import sha256
import unittest
from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_shadow_readiness_review import ShadowReadinessReview
h=lambda x:sha256(x).hexdigest();NOW=datetime(2026,9,18,tzinfo=UTC)
def complete():
 r=ShadowReadinessReview(h(b"validation"),h(b"policy"));r.admit("SYNTHETIC_RESPONSE_SHADOW_VALIDATION_COMPLETED","ELIGIBLE_DRAFT",True,False,"synthetic:key:411");r.blockers(("NONE",),"synthetic:key:412",1);r.evidence_matrix(("CRITERIA","FAIRNESS","FINANCIAL","ROLLBACK","SENSITIVITY"),"synthetic:key:413",2);r.consistency("ELIGIBLE_DRAFT","synthetic:key:414",3);r.fairness(150,200,"synthetic:key:415",4);r.financial(900,1000,"synthetic:key:416",5);r.rollback(("CEILING_BREACH","FAIRNESS_BREACH"),("CEILING_BREACH","FAIRNESS_BREACH"),"synthetic:key:417",6);r.capacity(100,90,20,"synthetic:key:418",7);r.window(NOW,NOW+timedelta(days=7),"synthetic:key:419",8);r.roles("synthetic:actor:author","synthetic:actor:reviewer","synthetic:operator:1","synthetic:key:420",9);r.alternatives(("HOLD","REQUEST_REVISION","SUBMIT_FOR_OPERATOR_REVIEW"),"synthetic:key:421",10);r.packet("synthetic:operator:1","SUBMIT_FOR_OPERATOR_REVIEW","synthetic:key:422",11);r.verify("synthetic:verifier:1",("DIGESTS","ROLES","BLOCKERS","SAFETY"),"synthetic:key:423",12);r.seal(None,"synthetic:key:424",13);r.complete(("NO_ACTIVATION","NO_AUTHORIZATION","READ_ONLY","SYNTHETIC_ONLY"),"synthetic:key:425",14);return r
class Tests(unittest.TestCase):
 def test_complete_review_is_non_authorizing(self):
  e=complete().evidence();self.assertEqual(e["features"],list(range(411,426)));self.assertTrue(e["synthetic_only"]);self.assertTrue(e["read_only"])
  for k,v in e.items():
   if k.endswith("_allowed") or k.endswith("_used") or k.endswith("_accessed") or k.endswith("_granted"):self.assertFalse(v)
 def test_sequence_and_stale_version_fail(self):
  r=ShadowReadinessReview(h(b"v"),h(b"p"))
  with self.assertRaises(GovernanceRejected):r.blockers(("NONE",),"synthetic:key:x",0)
  r.admit("SYNTHETIC_RESPONSE_SHADOW_VALIDATION_COMPLETED","HOLD",False,True,"synthetic:key:a")
  with self.assertRaises(GovernanceRejected):r.blockers(("ROLLBACK_TRIGGERED",),"synthetic:key:b",0)
 def test_idempotency_conflict(self):
  r=ShadowReadinessReview(h(b"v"),h(b"p"));a=r.admit("SYNTHETIC_RESPONSE_SHADOW_VALIDATION_COMPLETED","HOLD",False,True,"synthetic:key:a");self.assertIs(a,r.admit("SYNTHETIC_RESPONSE_SHADOW_VALIDATION_COMPLETED","HOLD",False,True,"synthetic:key:a"))
  with self.assertRaises(GovernanceRejected):r.admit("SYNTHETIC_RESPONSE_SHADOW_VALIDATION_COMPLETED","REVISE",False,True,"synthetic:key:a")
 def test_eligible_consistency_and_blockers(self):
  with self.assertRaises(GovernanceRejected):ShadowReadinessReview(h(b"v"),h(b"p")).admit("SYNTHETIC_RESPONSE_SHADOW_VALIDATION_COMPLETED","ELIGIBLE_DRAFT",False,False,"synthetic:key:a")
  r=complete();r.stages=r.stages[:1]
  with self.assertRaises(GovernanceRejected):r.blockers(("FAIRNESS_CONCERN",),"synthetic:key:bad",1)
 def test_bounds_and_roles(self):
  r=complete();r.stages=r.stages[:4]
  with self.assertRaises(GovernanceRejected):r.fairness(201,200,"synthetic:key:f",4)
  q=complete();q.stages=q.stages[:9]
  with self.assertRaises(GovernanceRejected):q.roles("synthetic:actor:x","synthetic:actor:x","synthetic:operator:1","synthetic:key:r",9)
 def test_all_rollback_triggers_rehearsed(self):
  r=complete();r.stages=r.stages[:6]
  with self.assertRaises(GovernanceRejected):r.rollback(("CEILING_BREACH","FAIRNESS_BREACH"),("CEILING_BREACH",),"synthetic:key:r",6)
 def test_operator_lineage_and_blocker_gate(self):
  r=complete();r.stages=r.stages[:11]
  with self.assertRaises(GovernanceRejected):r.packet("synthetic:operator:other","SUBMIT_FOR_OPERATOR_REVIEW","synthetic:key:o",11)
 def test_verifier_independence(self):
  r=complete();r.stages=r.stages[:12]
  with self.assertRaises(GovernanceRejected):r.verify("synthetic:operator:1",("DIGESTS","ROLES","BLOCKERS","SAFETY"),"synthetic:key:v",12)
