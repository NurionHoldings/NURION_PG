from datetime import UTC,datetime,timedelta
from hashlib import sha256
import unittest
from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_risk_response_plan import RiskResponsePlan
h=lambda x:sha256(x).hexdigest();NOW=datetime(2026,9,18,tzinfo=UTC)
def complete():
 p=RiskResponsePlan(h(b"risk"),h(b"policy"));p.intake("SYNTHETIC_PORTFOLIO_RISK_REPORT_COMPLETED",(),"synthetic:key:381");p.classify_gaps(("COVERAGE","DEADLINE"),"synthetic:key:382",1);p.candidates(("EXTEND_OBSERVATION","QUEUE_REVIEW"),"synthetic:key:383",2);p.impact("synthetic:merchant:1","KRW",500,1000,"synthetic:key:384",3);p.fairness(("A","B"),{"A":5000,"B":5200},"synthetic:key:385",4);p.priority(((1,"QUEUE_REVIEW"),(2,"EXTEND_OBSERVATION")),"synthetic:key:386",5);p.cooling(NOW,NOW+timedelta(days=7),"synthetic:key:387",6);p.exceptions(("FAIRNESS_REVIEW",),"synthetic:key:388",7);p.roles("synthetic:actor:author","synthetic:actor:reviewer","synthetic:operator:1","synthetic:key:389",8);p.rollback(("FAIRNESS_BREACH","METRIC_REGRESSION"),"synthetic:key:390",9);p.shadow_schedule(NOW,NOW+timedelta(days=14),1000,"synthetic:key:391",10);p.success_criteria((("COVERAGE_BP","GTE",9000),("DEADLINE_BP","LTE",500)),"synthetic:key:392",11);p.operator_packet("synthetic:operator:1",("EVIDENCE","FAIRNESS","ROLLBACK","SAFETY"),"synthetic:key:393",12);p.seal(None,"synthetic:key:394",13);p.complete(("NON_EXECUTABLE","OPERATOR_SEPARATE","READ_ONLY","SYNTHETIC_ONLY"),"synthetic:key:395",14);return p
class Tests(unittest.TestCase):
 def test_complete_plan_is_non_executable(self):
  e=complete().evidence();self.assertEqual(e["features"],list(range(381,396)));self.assertTrue(e["synthetic_only"]);self.assertTrue(e["read_only"])
  for k,v in e.items():
   if k.endswith("_allowed") or k.endswith("_used") or k.endswith("_accessed") or k.endswith("_granted"):self.assertFalse(v)
 def test_sequence_and_stale_version_fail_closed(self):
  p=RiskResponsePlan(h(b"r"),h(b"p"))
  with self.assertRaises(GovernanceRejected):p.classify_gaps(("DEADLINE",),"synthetic:key:x",0)
  p.intake("SYNTHETIC_PORTFOLIO_RISK_REPORT_COMPLETED",(),"synthetic:key:i")
  with self.assertRaises(GovernanceRejected):p.classify_gaps(("DEADLINE",),"synthetic:key:g",0)
 def test_idempotency_replay_and_conflict(self):
  p=RiskResponsePlan(h(b"r"),h(b"p"));a=p.intake("SYNTHETIC_PORTFOLIO_RISK_REPORT_COMPLETED",(),"synthetic:key:i");self.assertIs(a,p.intake("SYNTHETIC_PORTFOLIO_RISK_REPORT_COMPLETED",(),"synthetic:key:i"))
  with self.assertRaises(GovernanceRejected):p.intake("BAD",(),"synthetic:key:i")
 def test_duplicate_codes_and_ranks_rejected(self):
  p=RiskResponsePlan(h(b"r"),h(b"p"));p.intake("SYNTHETIC_PORTFOLIO_RISK_REPORT_COMPLETED",(),"synthetic:key:i")
  with self.assertRaises(GovernanceRejected):p.classify_gaps(("DEADLINE","DEADLINE"),"synthetic:key:g",1)
  q=complete()
  with self.assertRaises(GovernanceRejected):RiskResponsePlan(h(b"r"),h(b"p")).priority(((1,"A"),(1,"B")),"synthetic:key:x",0)
 def test_role_and_financial_boundaries(self):
  with self.assertRaises(GovernanceRejected):RiskResponsePlan(h(b"r"),h(b"p")).impact("merchant-real","KRW",1,1,"synthetic:key:x",0)
  with self.assertRaises(GovernanceRejected):RiskResponsePlan(h(b"r"),h(b"p")).roles("synthetic:actor:a","synthetic:actor:a","synthetic:actor:b","synthetic:key:x",0)
 def test_time_and_threshold_boundaries(self):
  with self.assertRaises(GovernanceRejected):RiskResponsePlan(h(b"r"),h(b"p")).cooling(NOW,NOW,"synthetic:key:x",0)
  with self.assertRaises(GovernanceRejected):RiskResponsePlan(h(b"r"),h(b"p")).shadow_schedule(NOW,NOW+timedelta(days=1),10001,"synthetic:key:x",0)
 def test_priority_threshold_and_operator_lineage_fail_closed(self):
  p=complete();p.stages=p.stages[:5]
  with self.assertRaises(GovernanceRejected):p.priority(((1,"QUEUE_REVIEW"),(3,"EXTEND_OBSERVATION")),"synthetic:key:rank-gap",5)
  with self.assertRaises(GovernanceRejected):p.priority(((1,"BLOCK_MERCHANT"),),"synthetic:key:unknown-candidate",5)
  q=complete();q.stages=q.stages[:11]
  with self.assertRaises(GovernanceRejected):q.success_criteria((("COVERAGE_BP","GTE",10001),),"synthetic:key:bp-overflow",11)
  r=complete();r.stages=r.stages[:12]
  with self.assertRaises(GovernanceRejected):r.operator_packet("synthetic:operator:other",("EVIDENCE","FAIRNESS","ROLLBACK","SAFETY"),"synthetic:key:wrong-operator",12)
