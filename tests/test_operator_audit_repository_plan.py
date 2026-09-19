from hashlib import sha256
import unittest
from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.operator_audit_repository_plan import OperatorAuditRepositoryPlan
h=lambda x:sha256(x).hexdigest()
def complete():
 r=OperatorAuditRepositoryPlan(h(b"parity"));r.discover("SYNTHETIC_OPERATOR_AUDIT_REGISTRY_PARITY_COMPLETED",(456,470),"synthetic:key:471");r.requirements(("APPEND_ONLY","AUDITABLE","IDEMPOTENT","ROLE_SEPARATED","TAMPER_EVIDENT"),"synthetic:key:472",1);r.conflicts(("EXTERNAL_IO","LIVE_TRAFFIC","MONEY_MOVEMENT","OPERATING_CREDENTIALS","POLICY_MUTATION"),"synthetic:key:473",2);r.architecture(("DOMAIN_PORT","POSTGRES_ADAPTER","SQLITE_TEST_ADAPTER","MIGRATION","EVIDENCE_EXPORT"),"synthetic:key:474",3);r.schema(("id","checkpoint_digest","sequence","previous_digest","report_digest","created_at"),"synthetic:key:475",4);r.invariants(("DIGEST_CHAIN","IMMUTABLE_ROWS","MONOTONIC_SEQUENCE","UNIQUE_CHECKPOINT","UNIQUE_IDEMPOTENCY"),"synthetic:key:476",5);r.transactions("SERIALIZABLE_OR_LOCKED_EQUIVALENT",True,"synthetic:key:477",6);r.migration(True,True,"synthetic:key:478",7);r.parity(True,True,"synthetic:key:479",8);r.acceptance(("CONCURRENCY","FRESH_SCHEMA","IDEMPOTENCY","ROLLBACK","TAMPER","TYPE_PARITY"),"synthetic:key:480",9);r.fixtures(True,False,"synthetic:key:481",10);r.rollout(True,True,"synthetic:key:482",11);r.reviewers("synthetic:designer:1","synthetic:auditor:1","synthetic:key:483",12);r.seal(None,"synthetic:key:484",13);r.complete(("NO_IMPLEMENTATION","NO_MIGRATION_RUN","NO_PERSISTENCE","NO_PRODUCTION","PLANNING_LOCK"),"synthetic:key:485",14)
 return r
class Tests(unittest.TestCase):
 def test_complete_plan_is_non_operational(self):
  e=complete().evidence();self.assertEqual(e["features"],list(range(471,486)));self.assertTrue(e["planning_only"])
  for k,v in e.items():
   if k.endswith("_allowed") or k.endswith("_used") or k.endswith("_accessed") or k.endswith("_present") or k.endswith("_executed"):self.assertFalse(v)
 def test_requirements_conflicts_architecture_fail_closed(self):
  r=complete();r.stages=r.stages[:1]
  with self.assertRaises(GovernanceRejected):r.requirements(("APPEND_ONLY",),"synthetic:key:r",1)
  q=complete();q.stages=q.stages[:2]
  with self.assertRaises(GovernanceRejected):q.conflicts(("MONEY_MOVEMENT",),"synthetic:key:c",2)
  x=complete();x.stages=x.stages[:3]
  with self.assertRaises(GovernanceRejected):x.architecture(("DIRECT_DB",),"synthetic:key:a",3)
 def test_migration_parity_acceptance_fail_closed(self):
  r=complete();r.stages=r.stages[:7]
  with self.assertRaises(GovernanceRejected):r.migration(True,False,"synthetic:key:m",7)
  q=complete();q.stages=q.stages[:8]
  with self.assertRaises(GovernanceRejected):q.parity(True,False,"synthetic:key:p",8)
  x=complete();x.stages=x.stages[:9]
  with self.assertRaises(GovernanceRejected):x.acceptance(("TAMPER",),"synthetic:key:x",9)
 def test_roles_and_rollout_fail_closed(self):
  r=complete();r.stages=r.stages[:11]
  with self.assertRaises(GovernanceRejected):r.rollout(False,True,"synthetic:key:o",11)
  q=complete();q.stages=q.stages[:12]
  with self.assertRaises(GovernanceRejected):q.reviewers("synthetic:designer:1","synthetic:designer:1","synthetic:key:q",12)
 def test_idempotency_and_sequence(self):
  r=OperatorAuditRepositoryPlan(h(b"x"));a=r.discover("SYNTHETIC_OPERATOR_AUDIT_REGISTRY_PARITY_COMPLETED",(456,470),"synthetic:key:a");self.assertIs(a,r.discover("SYNTHETIC_OPERATOR_AUDIT_REGISTRY_PARITY_COMPLETED",(456,470),"synthetic:key:a"))
  with self.assertRaises(GovernanceRejected):r.discover("BAD",(456,470),"synthetic:key:a")
if __name__=="__main__":unittest.main()
