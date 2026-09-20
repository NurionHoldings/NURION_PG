from datetime import UTC,datetime,timedelta
from hashlib import sha256
import unittest
from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_dispute_cases import *
NOW=datetime(2026,9,17,tzinfo=UTC);h=lambda x:sha256(x).hexdigest()
def case():return DisputeCase("synthetic:case:1","synthetic:intent:1","synthetic:merchant:1","FRAUD",5000,"KRW",NOW+timedelta(days=7),h(b"p"),h(b"s"))
class Tests(unittest.TestCase):
 def test_open_verify_freeze(self):
  b=SyntheticDisputeBook();b.open(case(),available_minor=6000,snapshot_valid=True,now=NOW,idempotency_key="synthetic:open");b.verify("synthetic:case:1",expected_version=1,idempotency_key="synthetic:verify");c=b.freeze("synthetic:case:1",tuple(sorted((h(b"a"),h(b"b")))),expected_version=2,idempotency_key="synthetic:freeze");self.assertEqual(c.state,DisputeState.EVIDENCE_FROZEN);self.assertFalse(b.evidence()["external_submission_allowed"])
 def test_ineligible_and_expired_rejected(self):
  for amount,valid,now in ((1,True,NOW),(6000,False,NOW),(6000,True,NOW+timedelta(days=8))):
   with self.assertRaises(GovernanceRejected):SyntheticDisputeBook().open(case(),available_minor=amount,snapshot_valid=valid,now=now,idempotency_key="synthetic:x")
 def test_stale_duplicate_and_tampered_evidence_rejected(self):
  b=SyntheticDisputeBook();b.open(case(),available_minor=6000,snapshot_valid=True,now=NOW,idempotency_key="synthetic:open")
  with self.assertRaises(GovernanceRejected):b.verify("synthetic:case:1",expected_version=0,idempotency_key="synthetic:stale")
  b.verify("synthetic:case:1",expected_version=1,idempotency_key="synthetic:verify")
  for refs in ((h(b"a"),h(b"a")),("bad",)):
   with self.assertRaises(GovernanceRejected):b.freeze("synthetic:case:1",refs,expected_version=2,idempotency_key="synthetic:"+str(refs))
 def test_non_synthetic_and_idempotency_conflict_fail_closed(self):
  with self.assertRaises(GovernanceRejected):DisputeCase("real","synthetic:i","synthetic:m","X",1,"KRW",NOW+timedelta(1),h(b"p"),h(b"s"))
  b=SyntheticDisputeBook();b.open(case(),available_minor=6000,snapshot_valid=True,now=NOW,idempotency_key="synthetic:key")
  with self.assertRaises(GovernanceRejected):b._command("synthetic:key",{"different":True})
