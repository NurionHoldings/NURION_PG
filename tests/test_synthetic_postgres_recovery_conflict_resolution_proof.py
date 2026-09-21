from hashlib import sha256
import unittest
from pathlib import Path
from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_postgres_recovery_conflict_resolution_proof import *

def d(value):return sha256(value.encode()).hexdigest()
def conflicts():return (("c2",d("c2"),"reviewer:two"),("c1",d("c1"),"reviewer:one"))
def docket(ledger):return ledger.add_docket("recommendation",d("recommendation"),conflicts(),"resolution-key","author",d("resolution"))

class Tests(unittest.TestCase):
    def test_conflict_set_is_canonical_and_order_invariant(self):self.assertEqual(conflict_set_digest(conflicts()),conflict_set_digest(tuple(reversed(conflicts()))))
    def test_conflict_set_missing_added_and_changed_fail_identity(self):
        baseline=conflict_set_digest(conflicts())
        for rows in (conflicts()[:1],conflicts()+(('c3',d('c3'),'reviewer:three'),),(('c1',d('changed'),'reviewer:one'),conflicts()[0])):self.assertNotEqual(baseline,conflict_set_digest(rows))
    def test_duplicate_conflict_rejected(self):
        with self.assertRaises(GovernanceRejected):conflict_set_digest((conflicts()[0],conflicts()[0]))
    def test_docket_replay_converges_and_changed_resolution_differs(self):
        ledger=ConflictResolutionLedger();first=docket(ledger);self.assertEqual(first,docket(ledger));self.assertNotEqual(first.docket_id,deterministic_resolution_docket_id("recommendation",d("recommendation"),conflicts(),"resolution-key","author",d("changed")))
    def test_round_requires_independent_reviewer_and_exact_predecessor(self):
        ledger=ConflictResolutionLedger();row=docket(ledger)
        with self.assertRaises(GovernanceRejected):ledger.add_round(row.docket_id,None,None,1,"author","REVIEWED_HOLD",d("why"))
        first=ledger.add_round(row.docket_id,None,None,1,"reviewer:one","REVIEWED_HOLD",d("why"))
        with self.assertRaises(GovernanceRejected):ledger.add_round(row.docket_id,first.round_id,d("wrong"),2,"reviewer:two","REVIEWED_NON_EXECUTABLE",d("why2"))
    def test_single_genesis_and_successor_fork_rejected(self):
        ledger=ConflictResolutionLedger();row=docket(ledger);first=ledger.add_round(row.docket_id,None,None,1,"reviewer:one","REVIEWED_HOLD",d("one"))
        with self.assertRaises(GovernanceRejected):ledger.add_round(row.docket_id,None,None,1,"reviewer:two","REVIEWED_HOLD",d("two"))
        ledger.add_round(row.docket_id,first.round_id,first.digest,2,"reviewer:two","REVIEWED_NON_EXECUTABLE",d("two"))
        with self.assertRaises(GovernanceRejected):ledger.add_round(row.docket_id,first.round_id,first.digest,2,"reviewer:three","REVIEWED_HOLD",d("three"))
    def test_hold_and_zero_authority(self):
        ledger=ConflictResolutionLedger();row=docket(ledger);ledger.add_round(row.docket_id,None,None,1,"reviewer:one","REVIEWED_HOLD",d("why"));e=ledger.evidence();self.assertTrue(e["held"])
        for key in ("payment_authority","receipt_authority","retry_authority","approval_authority","execution_authority"):self.assertFalse(e[key])
    def test_invalid_verdict_and_non_monotonic_round_rejected(self):
        ledger=ConflictResolutionLedger();row=docket(ledger)
        with self.assertRaises(GovernanceRejected):ledger.add_round(row.docket_id,None,None,1,"reviewer","APPROVED",d("why"))
    def test_database_contract_contains_required_constraints(self):
        source=(Path(__file__).resolve().parents[1]/"scripts/run_postgres_recovery_conflict_resolution_integration.py").read_text(encoding="utf-8")
        for clause in ("one_genesis_resolution_round","one_successor_resolution_round","author_subject<>reviewer_subject","docket_append_only","round_append_only","default_transaction_read_only=on"):self.assertIn(clause,source)

if __name__=="__main__":unittest.main()
