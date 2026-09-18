from datetime import UTC,datetime
from hashlib import sha256
import unittest
from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_response_shadow_validation import ResponseShadowValidation
h=lambda x:sha256(x).hexdigest();NOW=datetime(2026,9,18,tzinfo=UTC)
def complete(recommendation="ELIGIBLE_DRAFT",observed=()):
 s=ResponseShadowValidation(h(b"plan"),h(b"policy"));s.admit("SYNTHETIC_RISK_RESPONSE_PLAN_COMPLETED",(),(("COVERAGE_BP","GTE",9000),("DEADLINE_BP","LTE",500),("FAIRNESS_GAP_BP","LTE",200),("IMPACT_MINOR","LTE",1000)),("CEILING_BREACH","FAIRNESS_BREACH"),"synthetic:key:396");s.fixture_cohort(("synthetic:case:1","synthetic:case:2"),"KRW","synthetic:key:397",1);s.baseline({"COVERAGE_BP":8000,"DEADLINE_BP":600,"FAIRNESS_GAP_BP":200,"IMPACT_MINOR":1000},NOW,"synthetic:key:398",2);s.project("QUEUE_REVIEW",{"COVERAGE_BP":9000,"DEADLINE_BP":400,"FAIRNESS_GAP_BP":150,"IMPACT_MINOR":900},"synthetic:key:399",3);s.deltas({"COVERAGE_BP":1000,"DEADLINE_BP":-200,"FAIRNESS_GAP_BP":-50,"IMPACT_MINOR":-100},"synthetic:key:400",4);s.criteria({"COVERAGE_BP":True,"DEADLINE_BP":True,"FAIRNESS_GAP_BP":True,"IMPACT_MINOR":True},"synthetic:key:401",5);s.fairness_drift((("synthetic:segment:a",4900),("synthetic:segment:b",5100)),"synthetic:key:402",6);s.financial_guard(900,1000,"synthetic:key:403",7);s.rollback_check(("CEILING_BREACH","FAIRNESS_BREACH"),observed,"synthetic:key:404",8);s.false_positive(1,20,"synthetic:key:405",9);s.sensitivity((("BASE",100),("HIGH",200),("LOW",50)),"synthetic:key:406",10);s.attest("synthetic:actor:planner","synthetic:actor:reviewer",("CRITERIA","FAIRNESS","FINANCIAL","ROLLBACK"),"synthetic:key:407",11);s.recommendation(recommendation,"synthetic:key:408",12);s.seal(None,"synthetic:key:409",13);s.complete(("NO_EXECUTION","NO_PROMOTION","READ_ONLY","SYNTHETIC_ONLY"),"synthetic:key:410",14);return s
class Tests(unittest.TestCase):
 def test_complete_shadow_is_non_operational(self):
  e=complete().evidence();self.assertEqual(e["features"],list(range(396,411)));self.assertTrue(e["synthetic_only"]);self.assertTrue(e["read_only"])
  for k,v in e.items():
   if k.endswith("_allowed") or k.endswith("_used") or k.endswith("_accessed") or k.endswith("_granted"):self.assertFalse(v)
 def test_sequence_and_stale_version_fail_closed(self):
  s=ResponseShadowValidation(h(b"p"),h(b"q"))
  with self.assertRaises(GovernanceRejected):s.fixture_cohort(("synthetic:case:1",),"KRW","synthetic:key:x",0)
  s.admit("SYNTHETIC_RISK_RESPONSE_PLAN_COMPLETED",(),(("COVERAGE_BP","GTE",9000),("DEADLINE_BP","LTE",500),("FAIRNESS_GAP_BP","LTE",200),("IMPACT_MINOR","LTE",1000)),("CEILING_BREACH","FAIRNESS_BREACH"),"synthetic:key:a")
  with self.assertRaises(GovernanceRejected):s.fixture_cohort(("synthetic:case:1",),"KRW","synthetic:key:b",0)
 def test_idempotency_replay_conflict(self):
  s=ResponseShadowValidation(h(b"p"),h(b"q"));a=s.admit("SYNTHETIC_RISK_RESPONSE_PLAN_COMPLETED",(),(("COVERAGE_BP","GTE",9000),("DEADLINE_BP","LTE",500),("FAIRNESS_GAP_BP","LTE",200),("IMPACT_MINOR","LTE",1000)),("CEILING_BREACH","FAIRNESS_BREACH"),"synthetic:key:a");self.assertIs(a,s.admit("SYNTHETIC_RISK_RESPONSE_PLAN_COMPLETED",(),(("COVERAGE_BP","GTE",9000),("DEADLINE_BP","LTE",500),("FAIRNESS_GAP_BP","LTE",200),("IMPACT_MINOR","LTE",1000)),("CEILING_BREACH","FAIRNESS_BREACH"),"synthetic:key:a"))
  with self.assertRaises(GovernanceRejected):s.admit("BAD",(),(("COVERAGE_BP","GTE",9000),("DEADLINE_BP","LTE",500),("FAIRNESS_GAP_BP","LTE",200),("IMPACT_MINOR","LTE",1000)),("CEILING_BREACH","FAIRNESS_BREACH"),"synthetic:key:a")
 def test_duplicate_and_metric_bounds(self):
  s=ResponseShadowValidation(h(b"p"),h(b"q"));s.admit("SYNTHETIC_RISK_RESPONSE_PLAN_COMPLETED",(),(("COVERAGE_BP","GTE",9000),("DEADLINE_BP","LTE",500),("FAIRNESS_GAP_BP","LTE",200),("IMPACT_MINOR","LTE",1000)),("CEILING_BREACH","FAIRNESS_BREACH"),"synthetic:key:a")
  with self.assertRaises(GovernanceRejected):s.fixture_cohort(("synthetic:case:1","synthetic:case:1"),"KRW","synthetic:key:b",1)
  q=complete();q.stages=q.stages[:2]
  with self.assertRaises(GovernanceRejected):q.baseline({"COVERAGE_BP":10001,"DEADLINE_BP":0,"FAIRNESS_GAP_BP":0,"IMPACT_MINOR":0},NOW,"synthetic:key:bad",2)
 def test_fraction_and_financial_bounds(self):
  with self.assertRaises(GovernanceRejected):ResponseShadowValidation(h(b"p"),h(b"q")).false_positive(2,1,"synthetic:key:x",0)
  with self.assertRaises(GovernanceRejected):ResponseShadowValidation(h(b"p"),h(b"q")).financial_guard(1001,1000,"synthetic:key:x",0)
 def test_eligibility_blocked_by_rollback_trigger(self):
  s=complete("HOLD",("FAIRNESS_BREACH",));s.stages=s.stages[:12]
  with self.assertRaises(GovernanceRejected):s.recommendation("ELIGIBLE_DRAFT","synthetic:key:eligible",12)
 def test_roles_scenarios_and_unknown_codes_fail(self):
  s=complete();s.stages=s.stages[:10]
  with self.assertRaises(GovernanceRejected):s.sensitivity((("BASE",1),("LOW",1)),"synthetic:key:missing",10)
  t=complete();t.stages=t.stages[:11]
  with self.assertRaises(GovernanceRejected):t.attest("synthetic:actor:x","synthetic:actor:x",("CRITERIA","FAIRNESS","FINANCIAL","ROLLBACK"),"synthetic:key:self",11)
 def test_plan_binding_rejects_self_reported_shadow_inputs(self):
  s=complete();s.stages=s.stages[:4]
  with self.assertRaises(GovernanceRejected):s.deltas({"COVERAGE_BP":999,"DEADLINE_BP":-200,"FAIRNESS_GAP_BP":-50,"IMPACT_MINOR":-100},"synthetic:key:wrong-delta",4)
  c=complete();c.stages=c.stages[:5]
  with self.assertRaises(GovernanceRejected):c.criteria({"COVERAGE_BP":True,"DEADLINE_BP":False,"FAIRNESS_GAP_BP":True,"IMPACT_MINOR":True},"synthetic:key:false-success",5)
  r=complete();r.stages=r.stages[:8]
  with self.assertRaises(GovernanceRejected):r.rollback_check(("DATA_DRIFT",),(),"synthetic:key:wrong-trigger",8)
