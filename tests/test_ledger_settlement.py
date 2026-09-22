import unittest
from nurion_pg.ledger import *

class LedgerTests(unittest.TestCase):
 def test_capture_rules_balance_and_split_fees(self):
  j=capture_journal("j1","m1","KRW","pay1",10000,500,300);j.validate()
  self.assertEqual(sum(e.amount for e in j.entries if e.side==Side.DEBIT),10000);self.assertEqual({e.account:e.amount for e in j.entries if e.side==Side.CREDIT},{"merchant_payable":9200,"platform_fee_revenue":500,"pg_fee_payable":300})
 def test_unbalanced_and_invalid_minor_units_fail(self):
  with self.assertRaises(LedgerError):Journal("j","m","KRW","x","r",(Entry("a",Side.DEBIT,2),Entry("b",Side.CREDIT,1))).validate()
  with self.assertRaises(LedgerError):capture_journal("j","m","KRW","r",100,80,30)
  with self.assertRaises(LedgerError):capture_journal("j","m","krw","r",100,0,0)
 def test_correction_is_reversal_plus_new_journal(self):
  original=refund_journal("j1","m","KRW","r",500);rev=reversal("j2",original);rev.validate();self.assertEqual(rev.reversal_of,"j1");self.assertEqual(rev.entries[0].side,Side.CREDIT)
 def test_settlement_state_machine_hold_and_adjust(self):
  s=Settlement("s","m","KRW",1000,100);s=s.transition(SettlementState.REVIEW);s=s.hold("difference");self.assertEqual(s.state,SettlementState.HELD);self.assertEqual(s.transition(SettlementState.ADJUSTED).state,SettlementState.ADJUSTED)
  with self.assertRaises(LedgerError):Settlement("s","m","KRW",1,0).transition(SettlementState.APPROVED)
 def test_reconciliation_difference_blocks_approval(self):
  s=Settlement("s","m","KRW",1000,0).transition(SettlementState.REVIEW)
  with self.assertRaises(LedgerError):s.transition(SettlementState.APPROVED,reconciliation_clear=False)
 def test_available_balance_accounts_pending_reserve_hold(self):self.assertEqual(available_balance(1000,200,100,50),650);self.assertEqual(available_balance(100,200,0,0),0)
 def test_payout_needs_two_distinct_non_requester_approvals(self):
  p=PayoutRequest("p","s","m","KRW",500,"requester","key");p=p.approve("a1");self.assertEqual(p.state,"pending_approval");self.assertEqual(p.approve("a1"),p);p=p.approve("a2");self.assertEqual(p.state,"approved")
  with self.assertRaises(LedgerError):PayoutRequest("p","s","m","KRW",1,"same","k").approve("same")
  with self.assertRaises(LedgerError):p.mark_paid()

if __name__=="__main__":unittest.main()
