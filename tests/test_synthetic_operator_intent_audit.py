from datetime import UTC,datetime,timedelta
from hashlib import sha256
import unittest
from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_operator_intent_audit import OperatorIntentAuditCheckpoint

h=lambda x:sha256(x).hexdigest()
NOW=datetime(2026,9,18,tzinfo=UTC)

def complete():
 r=OperatorIntentAuditCheckpoint(h(b"receipt-report"))
 r.admit("SYNTHETIC_OPERATOR_INTENT_RECEIPTS_COMPLETED",(426,440),False,"synthetic:key:441")
 r.bind_scope("NURION_PG","READ_ONLY_INDEPENDENT_AUDIT","synthetic:key:442",1)
 r.freshness(NOW,NOW+timedelta(days=7),NOW+timedelta(hours=1),"synthetic:key:443",2)
 r.roles("synthetic:operator:1","synthetic:auditor:1","synthetic:key:444",3)
 r.vocabulary(("ACKNOWLEDGE_ONLY","CLOSE_CONSIDERATION","DEFER_CONSIDERATION","REQUEST_REVISION"),"synthetic:key:445",4)
 r.authority(("ACTIVATION_FALSE","AUTHORITY_FALSE","EXECUTION_FALSE","POLICY_CHANGE_FALSE"),"synthetic:key:446",5)
 r.integrity(h(b"receipt"),True,"synthetic:key:447",6)
 r.replay(True,True,"synthetic:key:448",7)
 r.supersession(True,False,"synthetic:key:449",8)
 r.privacy(False,False,"synthetic:key:450",9)
 r.effects((),"synthetic:key:451",10)
 r.findings((),"synthetic:key:452",11)
 r.attest("synthetic:auditor:1",("AUTHORITY","INTEGRITY","PRIVACY","REPLAY","SCOPE"),"synthetic:key:453",12)
 r.seal(None,"synthetic:key:454",13)
 r.complete(("NO_AUTHORIZATION","NO_DEPLOYMENT","NO_MONEY_MOVEMENT","READ_ONLY","SYNTHETIC_ONLY"),"synthetic:key:455",14)
 return r

class Tests(unittest.TestCase):
 def test_complete_audit_is_non_authorizing(self):
  e=complete().evidence()
  self.assertEqual(e["features"],list(range(441,456)))
  self.assertEqual(e["maximum_state"],"SYNTHETIC_OPERATOR_INTENT_AUDIT_COMPLETED")
  for k,v in e.items():
   if k.endswith("_allowed") or k.endswith("_used") or k.endswith("_accessed") or k.endswith("_conferred"): self.assertFalse(v)

 def test_source_authority_and_scope_fail_closed(self):
  r=OperatorIntentAuditCheckpoint(h(b"x"))
  with self.assertRaises(GovernanceRejected): r.admit("BAD",(426,440),False,"synthetic:key:x")
  with self.assertRaises(GovernanceRejected): r.admit("SYNTHETIC_OPERATOR_INTENT_RECEIPTS_COMPLETED",(426,440),True,"synthetic:key:y")
  q=complete();q.stages=q.stages[:1]
  with self.assertRaises(GovernanceRejected): q.bind_scope("OTHER","READ_ONLY_INDEPENDENT_AUDIT","synthetic:key:z",1)

 def test_role_vocabulary_and_effects_fail_closed(self):
  r=complete();r.stages=r.stages[:3]
  with self.assertRaises(GovernanceRejected): r.roles("synthetic:operator:1","synthetic:operator:1","synthetic:key:r",3)
  q=complete();q.stages=q.stages[:4]
  with self.assertRaises(GovernanceRejected): q.vocabulary(("APPROVE",),"synthetic:key:v",4)
  x=complete();x.stages=x.stages[:10]
  with self.assertRaises(GovernanceRejected): x.effects(("NOTIFY",),"synthetic:key:e",10)

 def test_integrity_privacy_and_findings_fail_closed(self):
  r=complete();r.stages=r.stages[:6]
  with self.assertRaises(GovernanceRejected): r.integrity(h(b"r"),False,"synthetic:key:i",6)
  q=complete();q.stages=q.stages[:9]
  with self.assertRaises(GovernanceRejected): q.privacy(True,False,"synthetic:key:p",9)
  x=complete();x.stages=x.stages[:11]
  with self.assertRaises(GovernanceRejected): x.findings(("AUTHORITY_LEAK",),"synthetic:key:f",11)

 def test_idempotency_and_sequence(self):
  r=OperatorIntentAuditCheckpoint(h(b"x"))
  a=r.admit("SYNTHETIC_OPERATOR_INTENT_RECEIPTS_COMPLETED",(426,440),False,"synthetic:key:a")
  self.assertIs(a,r.admit("SYNTHETIC_OPERATOR_INTENT_RECEIPTS_COMPLETED",(426,440),False,"synthetic:key:a"))
  with self.assertRaises(GovernanceRejected): r.admit("SYNTHETIC_OPERATOR_INTENT_RECEIPTS_COMPLETED",(426,440),False,"synthetic:key:b")
  with self.assertRaises(GovernanceRejected): r.admit("BAD",(426,440),False,"synthetic:key:a")

 def test_checkpoint_and_attestation_binding(self):
  r=complete();r.stages=r.stages[:12]
  with self.assertRaises(GovernanceRejected): r.attest("synthetic:auditor:other",("AUTHORITY","INTEGRITY","PRIVACY","REPLAY","SCOPE"),"synthetic:key:a",12)
  q=complete();q.stages=q.stages[:13]
  with self.assertRaises(GovernanceRejected): q.seal("bad","synthetic:key:s",13)

if __name__=="__main__": unittest.main()
