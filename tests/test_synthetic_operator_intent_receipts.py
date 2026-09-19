from datetime import UTC,datetime,timedelta
from hashlib import sha256
import unittest
from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_operator_intent_receipts import OperatorIntentReceipts
h=lambda x:sha256(x).hexdigest();NOW=datetime(2026,9,18,tzinfo=UTC)
def complete(code="ACKNOWLEDGE_ONLY"):
 r=OperatorIntentReceipts(h(b"packet"),h(b"policy"));r.admit("SYNTHETIC_SHADOW_READINESS_REVIEW_COMPLETED","SUBMIT_FOR_OPERATOR_REVIEW",("NONE",),"synthetic:operator:1","synthetic:key:426");r.bind_scope("NURION_PG",(381,425),"READ_ONLY_CONSIDERATION","synthetic:key:427",1);r.validity(NOW,NOW+timedelta(days=7),NOW+timedelta(hours=1),"synthetic:key:428",2);r.actor("synthetic:operator:1","synthetic:operator:1","synthetic:key:429",3);r.intent(code,"synthetic:key:430",4);r.prerequisites(("DIGESTS","NON_AUTHORITY","SAFETY","SCOPE"),"synthetic:key:431",5);r.reviewer("synthetic:operator:1","synthetic:reviewer:1","synthetic:key:432",6);r.nonce("synthetic:nonce:abcdefghijklmnop","synthetic:key:433",7);r.canonicalize(("code","operator","packet_digest","scope_digest"),"synthetic:key:434",8);r.review("synthetic:reviewer:1",("IDENTITY","NONCE","SCOPE","SAFETY"),"synthetic:key:435",9);r.receipt("synthetic:receipt:1","synthetic:key:436",10);r.ledger(1,None,"synthetic:key:437",11);r.supersession(None,"INITIAL","synthetic:key:438",12);r.seal(None,"synthetic:key:439",13);r.complete(("INTENT_NOT_APPROVAL","NO_ACTIVATION","READ_ONLY","SYNTHETIC_ONLY"),"synthetic:key:440",14);return r
class Tests(unittest.TestCase):
 def test_complete_receipts_are_non_authorizing(self):
  e=complete().evidence();self.assertEqual(e["features"],list(range(426,441)));self.assertTrue(e["synthetic_only"]);self.assertTrue(e["read_only"])
  for k,v in e.items():
   if k.endswith("_allowed") or k.endswith("_used") or k.endswith("_accessed") or k.endswith("_granted") or k.endswith("_conferred") or k=="intent_is_approval":self.assertFalse(v)
 def test_sequence_and_idempotency(self):
  r=OperatorIntentReceipts(h(b"x"),h(b"p"))
  with self.assertRaises(GovernanceRejected):r.bind_scope("NURION_PG",(381,425),"READ_ONLY_CONSIDERATION","synthetic:key:x",0)
  a=r.admit("SYNTHETIC_SHADOW_READINESS_REVIEW_COMPLETED","HOLD",("CRITERIA_FAILED",),"synthetic:operator:1","synthetic:key:a");self.assertIs(a,r.admit("SYNTHETIC_SHADOW_READINESS_REVIEW_COMPLETED","HOLD",("CRITERIA_FAILED",),"synthetic:operator:1","synthetic:key:a"))
  with self.assertRaises(GovernanceRejected):r.admit("BAD","HOLD",("CRITERIA_FAILED",),"synthetic:operator:1","synthetic:key:a")
 def test_approval_like_intents_rejected(self):
  r=complete();r.stages=r.stages[:4]
  for code in ("APPROVE","ACTIVATE","PROMOTE","CONSIDER_NEXT_SYNTHETIC_STAGE"):
   with self.assertRaises(GovernanceRejected):r.intent(code,"synthetic:key:"+code,4)
 def test_expiry_scope_and_actor_fail_closed(self):
  r=complete();r.stages=r.stages[:1]
  with self.assertRaises(GovernanceRejected):r.bind_scope("OTHER",(381,425),"READ_ONLY_CONSIDERATION","synthetic:key:s",1)
  q=complete();q.stages=q.stages[:2]
  with self.assertRaises(GovernanceRejected):q.validity(NOW,NOW+timedelta(days=1),NOW+timedelta(days=2),"synthetic:key:t",2)
  a=complete();a.stages=a.stages[:3]
  with self.assertRaises(GovernanceRejected):a.actor("synthetic:operator:2","synthetic:operator:1","synthetic:key:o",3)
 def test_nonce_and_reviewer_binding(self):
  r=complete();r.stages=r.stages[:7]
  with self.assertRaises(GovernanceRejected):r.nonce("synthetic:nonce:x","synthetic:key:n",7)
  q=complete();q.stages=q.stages[:9]
  with self.assertRaises(GovernanceRejected):q.review("synthetic:reviewer:other",("IDENTITY","NONCE","SCOPE","SAFETY"),"synthetic:key:r",9)
 def test_receipt_and_supersession_constraints(self):
  r=complete();r.stages=r.stages[:10]
  with self.assertRaises(GovernanceRejected):r.receipt("real-receipt","synthetic:key:x",10)
  q=complete();q.stages=q.stages[:12]
  with self.assertRaises(GovernanceRejected):q.supersession(None,"CORRECTION","synthetic:key:s",12)
 def test_all_consideration_codes_complete(self):
  for code in ("ACKNOWLEDGE_ONLY","REQUEST_REVISION","DEFER_CONSIDERATION","CLOSE_CONSIDERATION"):self.assertEqual(complete(code).evidence()["maximum_state"],"SYNTHETIC_OPERATOR_INTENT_RECEIPTS_COMPLETED")
