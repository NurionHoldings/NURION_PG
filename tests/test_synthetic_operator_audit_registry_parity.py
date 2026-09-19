from hashlib import sha256
import unittest
from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_operator_audit_registry_parity import OperatorAuditRegistryParity
h=lambda x:sha256(x).hexdigest()
def complete():
 r=OperatorAuditRegistryParity(h(b"audit"));r.admit("SYNTHETIC_OPERATOR_INTENT_AUDIT_COMPLETED",(441,455),True,"synthetic:key:456");r.contract("nurion.pg.operator-audit-registry.v1",("checkpoint_digest","sequence","previous_digest","report_digest"),"synthetic:key:457",1);r.backends(("memory","sqlite-memory"),"synthetic:key:458",2);r.fixture(h(b"fixture"),"synthetic:key:459",3);r.write_preview(1,None,"synthetic:key:460",4);r.memory(h(b"record"),1,"synthetic:key:461",5);r.sqlite(h(b"record"),1,False,"synthetic:key:462",6);r.parity(h(b"record"),h(b"record"),"synthetic:key:463",7);r.replay(True,True,"synthetic:key:464",8);r.concurrency(True,"synthetic:key:465",9);r.tamper(True,True,"synthetic:key:466",10);r.privacy(False,False,"synthetic:key:467",11);r.effects((),"synthetic:key:468",12);r.seal(None,"synthetic:key:469",13);r.complete(("IN_MEMORY_ONLY","NO_AUTHORITY","NO_EXTERNAL_IO","READ_ONLY","SYNTHETIC_ONLY"),"synthetic:key:470",14);return r
class Tests(unittest.TestCase):
 def test_complete_parity_is_non_operational(self):
  e=complete().evidence();self.assertEqual(e["features"],list(range(456,471)))
  for k,v in e.items():
   if k.endswith("_allowed") or k.endswith("_used") or k.endswith("_accessed") or k.endswith("_conferred"):self.assertFalse(v)
 def test_source_contract_and_backends_fail_closed(self):
  r=OperatorAuditRegistryParity(h(b"x"))
  with self.assertRaises(GovernanceRejected):r.admit("BAD",(441,455),True,"synthetic:key:x")
  a=complete();a.stages=a.stages[:1]
  with self.assertRaises(GovernanceRejected):a.contract("bad",(),"synthetic:key:c",1)
  b=complete();b.stages=b.stages[:2]
  with self.assertRaises(GovernanceRejected):b.backends(("disk",),"synthetic:key:b",2)
 def test_digest_parity_and_io_fail_closed(self):
  r=complete();r.stages=r.stages[:7]
  with self.assertRaises(GovernanceRejected):r.parity(h(b"a"),h(b"b"),"synthetic:key:p",7)
  q=complete();q.stages=q.stages[:6]
  with self.assertRaises(GovernanceRejected):q.sqlite(h(b"x"),1,True,"synthetic:key:s",6)
  x=complete();x.stages=x.stages[:12]
  with self.assertRaises(GovernanceRejected):x.effects(("WRITE_DISK",),"synthetic:key:e",12)
 def test_replay_concurrency_and_tamper_fail_closed(self):
  r=complete();r.stages=r.stages[:8]
  with self.assertRaises(GovernanceRejected):r.replay(False,True,"synthetic:key:r",8)
  q=complete();q.stages=q.stages[:9]
  with self.assertRaises(GovernanceRejected):q.concurrency(False,"synthetic:key:c",9)
  x=complete();x.stages=x.stages[:10]
  with self.assertRaises(GovernanceRejected):x.tamper(True,False,"synthetic:key:t",10)
 def test_idempotency_and_sequence(self):
  r=OperatorAuditRegistryParity(h(b"x"));a=r.admit("SYNTHETIC_OPERATOR_INTENT_AUDIT_COMPLETED",(441,455),True,"synthetic:key:a");self.assertIs(a,r.admit("SYNTHETIC_OPERATOR_INTENT_AUDIT_COMPLETED",(441,455),True,"synthetic:key:a"))
  with self.assertRaises(GovernanceRejected):r.admit("BAD",(441,455),True,"synthetic:key:a")
if __name__=="__main__":unittest.main()
