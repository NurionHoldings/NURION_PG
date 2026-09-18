from hashlib import sha256
import unittest
from concurrent.futures import ThreadPoolExecutor
from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_dispute_review_docket import *
h=lambda x:sha256(x).hexdigest()
def docket():return Docket("synthetic:docket:1","synthetic:case:1",h(b"c"),h(b"e"),"synthetic:intake:1",5000,h(b"p"))
def ready():
 b=ReviewBook();b.open(docket(),source_frozen=True,key="synthetic:open");b.assign("synthetic:docket:1","synthetic:reviewer:1",expected_version=1,key="synthetic:assign");b.start("synthetic:docket:1","synthetic:reviewer:1",expected_version=2,key="synthetic:start");return b
class Tests(unittest.TestCase):
 def test_independent_recommendation_draft(self):
  b=ready();d=b.draft("synthetic:docket:1","synthetic:reviewer:1",Recommendation.PARTIAL_DRAFT,2500,"PARTIAL_SUPPORT",expected_version=3,key="synthetic:draft");self.assertEqual(d.state,ReviewState.RECOMMENDATION_DRAFTED);self.assertFalse(b.evidence()["decision_final"])
 def test_self_review_source_and_stale_fail_closed(self):
  with self.assertRaises(GovernanceRejected):ReviewBook().open(docket(),source_frozen=False,key="synthetic:x")
  b=ReviewBook();b.open(docket(),source_frozen=True,key="synthetic:o")
  with self.assertRaises(GovernanceRejected):b.assign("synthetic:docket:1","synthetic:intake:1",expected_version=1,key="synthetic:a")
  with self.assertRaises(GovernanceRejected):b.assign("synthetic:docket:1","synthetic:reviewer:1",expected_version=0,key="synthetic:s")
 def test_amount_contracts_fail_closed(self):
  for rec,amount,code in ((Recommendation.ACCEPT_DRAFT,1,"VALID_EVIDENCE"),(Recommendation.REJECT_DRAFT,1,"INVALID_EVIDENCE"),(Recommendation.PARTIAL_DRAFT,5000,"PARTIAL_SUPPORT")):
   with self.assertRaises(GovernanceRejected):ready().draft("synthetic:docket:1","synthetic:reviewer:1",rec,amount,code,expected_version=3,key="synthetic:d")
 def test_concurrent_draft_has_one_winner(self):
  b=ready()
  def go(i):
   try:b.draft("synthetic:docket:1","synthetic:reviewer:1",Recommendation.ACCEPT_DRAFT,5000,"VALID_EVIDENCE",expected_version=3,key=f"synthetic:d:{i}");return True
   except GovernanceRejected:return False
  with ThreadPoolExecutor(max_workers=4) as x:r=list(x.map(go,range(4)))
  self.assertEqual(r.count(True),1)
