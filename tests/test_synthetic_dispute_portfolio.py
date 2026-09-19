from datetime import UTC,datetime,timedelta
from hashlib import sha256
import unittest
from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_dispute_portfolio import *
h=lambda x:sha256(x).hexdigest();NOW=datetime(2026,9,18,tzinfo=UTC)
def run():
 p=DisputePortfolio("synthetic:case:1","synthetic:merchant:1","KRW",10000,h(b"f"),h(b"r"));p.supplement((h(b"a"),),(h(b"b"),),h(b"q"));p.merchant_response(("SERVICE_PROVIDED",),True);p.sla(NOW,NOW+timedelta(days=2),NOW+timedelta(hours=1));p.relationship("synthetic:case:2","synthetic:merchant:1","KRW",True);p.liability(20,70,10,h(b"m"));p.financial_impact(100,500,h(b"p"));p.resolution_packet("synthetic:issuer:1","synthetic:reviewer:1");p.verify_packet("synthetic:verifier:1","synthetic:issuer:1",("DIGESTS","ROLES","AMOUNTS","SAFETY"));p.ledger_preview(7000,7000);p.envelope_lint(h(b"s"),("case_digest","currency","evidence_set_digest","recommended_minor"));p.reversal("NEW_EVIDENCE");p.reconcile_closure();p.complete();return p
class Tests(unittest.TestCase):
 def test_complete_portfolio_is_non_operational(self):
  r=run().evidence();self.assertEqual([x["feature"] for x in r["artifacts"]],list(range(353,366)))
  for k,v in r.items():
   if k.endswith("_allowed") or k in {"network_used","credentials_accessed","real_money_moved"}:self.assertFalse(v)
 def test_sequence_gap_and_incomplete_completion_fail_closed(self):
  p=DisputePortfolio("synthetic:c","synthetic:m","KRW",1,h(b"f"),h(b"r"))
  with self.assertRaises(GovernanceRejected):p.merchant_response(("NO_SUPPORT",),True)
  with self.assertRaises(GovernanceRejected):p.complete()
 def test_tamper_boundaries_fail_closed(self):
  p=DisputePortfolio("synthetic:c","synthetic:m","KRW",100,h(b"f"),h(b"r"))
  with self.assertRaises(GovernanceRejected):p.supplement((h(b"a"),),(h(b"a"),),h(b"q"))
  p.supplement((h(b"a"),),(h(b"b"),),h(b"q"))
  with self.assertRaises(GovernanceRejected):p.merchant_response(("FREE_TEXT",),True)
 def test_financial_and_role_constraints(self):
  p=DisputePortfolio("synthetic:c","synthetic:m","KRW",100,h(b"f"),h(b"r"))
  p.supplement((h(b"a"),),(h(b"b"),),h(b"q"));p.merchant_response(("NO_SUPPORT",),True);p.sla(NOW,NOW+timedelta(days=2),NOW);p.relationship("synthetic:o","synthetic:m","KRW",True)
  with self.assertRaises(GovernanceRejected):p.liability(30,30,30,h(b"m"))
