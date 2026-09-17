from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.operator_decision_intake import (
    SyntheticOperatorDecision,
    SyntheticOperatorDecisionIntake,
)
from nurion_pg.operator_decision_receipt_ledger import (
    SyntheticOperatorDecisionReceiptLedger,
)
from nurion_pg.synthetic_implementation_proposals import (
    ALLOWED_DRAFT_SCOPES,
    IMPLEMENTATION_PROPOSAL_STATE,
    REQUIRED_DRAFT_CHECKS,
    SyntheticImplementationProposalBook,
)
from tests.test_operator_decision_intake import (
    NOW,
    decision_envelope,
    key_registry,
    packet_source,
)


SCOPES = (
    "SYNTHETIC_FIXTURE_PATCH_DRAFT_ONLY",
    "TEST_HARDENING_PATCH_DRAFT_ONLY",
)


def receipted_source(
    decision: SyntheticOperatorDecision = (
        SyntheticOperatorDecision.AUTHORIZE_SYNTHETIC_IMPLEMENTATION_PROPOSAL_DRAFT
    ),
):
    case, remediation, docket, record, packet_book, packet = packet_source()
    intake = SyntheticOperatorDecisionIntake(key_registry())
    envelope = decision_envelope(packet, decision=decision)
    intake.assess(packet_book, record.shadow_id, envelope, received_at=NOW)
    ledger = SyntheticOperatorDecisionReceiptLedger(":memory:")
    receipt = ledger.record_from_intake(
        intake, envelope.envelope_id, recorded_at=NOW
    )
    return case, remediation, docket, ledger, receipt


class SyntheticImplementationProposalTests(unittest.TestCase):
    def test_authorized_receipt_creates_non_executable_review_draft(self):
        case, remediation, docket, ledger, receipt = receipted_source()
        book = SyntheticImplementationProposalBook()
        proposal = book.draft_from_receipt(
            ledger, receipt.receipt_id, draft_scopes=SCOPES, drafted_at=NOW
        )
        self.assertEqual(proposal.state, IMPLEMENTATION_PROPOSAL_STATE)
        self.assertEqual(proposal.source_receipt_id, receipt.receipt_id)
        self.assertEqual(proposal.draft_scopes, SCOPES)
        self.assertEqual(proposal.required_checks, REQUIRED_DRAFT_CHECKS)
        self.assertTrue(proposal.eternian_review_required)
        self.assertFalse(proposal.actual_operator_decision_recorded)
        self.assertFalse(proposal.code_change_allowed)
        self.assertFalse(proposal.automatic_application_allowed)
        self.assertFalse(proposal.execution_allowed)
        self.assertFalse(proposal.money_movement_allowed)
        self.assertFalse(proposal.production_activation_allowed)
        ledger.close()
        docket.close()
        remediation.close()
        case.close()

    def test_hold_and_reject_receipts_cannot_create_drafts(self):
        for decision in (
            SyntheticOperatorDecision.HOLD,
            SyntheticOperatorDecision.REJECT,
        ):
            case, remediation, docket, ledger, receipt = receipted_source(decision)
            with self.assertRaises(GovernanceRejected):
                SyntheticImplementationProposalBook().draft_from_receipt(
                    ledger, receipt.receipt_id, draft_scopes=SCOPES, drafted_at=NOW
                )
            ledger.close()
            docket.close()
            remediation.close()
            case.close()

    def test_requires_typed_intact_receipt_ledger(self):
        with self.assertRaises(GovernanceRejected):
            SyntheticImplementationProposalBook().draft_from_receipt(
                object(),
                "synthetic:operator-decision-receipt:fake",
                draft_scopes=SCOPES,
                drafted_at=NOW,
            )
        case, remediation, docket, ledger, receipt = receipted_source()
        ledger._connection.execute(
            "UPDATE synthetic_decision_receipt_audit SET audit_digest = ?",
            ("f" * 64,),
        )
        with self.assertRaises(GovernanceRejected):
            SyntheticImplementationProposalBook().draft_from_receipt(
                ledger, receipt.receipt_id, draft_scopes=SCOPES, drafted_at=NOW
            )
        ledger.close()
        docket.close()
        remediation.close()
        case.close()

    def test_scopes_are_nonempty_unique_allowlisted_and_ordered(self):
        case, remediation, docket, ledger, receipt = receipted_source()
        invalid = (
            (),
            ("UNKNOWN_SCOPE",),
            (SCOPES[0], SCOPES[0]),
            tuple(reversed(SCOPES)),
        )
        for scopes in invalid:
            with self.assertRaises(GovernanceRejected):
                SyntheticImplementationProposalBook().draft_from_receipt(
                    ledger,
                    receipt.receipt_id,
                    draft_scopes=scopes,
                    drafted_at=NOW,
                )
        self.assertTrue(all(scope.endswith("_DRAFT_ONLY") for scope in ALLOWED_DRAFT_SCOPES))
        ledger.close()
        docket.close()
        remediation.close()
        case.close()

    def test_draft_time_cannot_predate_receipt_or_be_naive(self):
        case, remediation, docket, ledger, receipt = receipted_source()
        book = SyntheticImplementationProposalBook()
        with self.assertRaises(GovernanceRejected):
            book.draft_from_receipt(
                ledger,
                receipt.receipt_id,
                draft_scopes=SCOPES,
                drafted_at=NOW - timedelta(seconds=1),
            )
        with self.assertRaises(GovernanceRejected):
            book.draft_from_receipt(
                ledger,
                receipt.receipt_id,
                draft_scopes=SCOPES,
                drafted_at=NOW.replace(tzinfo=None),
            )
        ledger.close()
        docket.close()
        remediation.close()
        case.close()

    def test_exact_replay_is_idempotent_and_scope_collision_is_blocked(self):
        case, remediation, docket, ledger, receipt = receipted_source()
        book = SyntheticImplementationProposalBook()
        first = book.draft_from_receipt(
            ledger, receipt.receipt_id, draft_scopes=SCOPES, drafted_at=NOW
        )
        second = book.draft_from_receipt(
            ledger,
            receipt.receipt_id,
            draft_scopes=SCOPES,
            drafted_at=NOW + timedelta(seconds=1),
        )
        self.assertEqual(first, second)
        with self.assertRaises(GovernanceRejected):
            book.draft_from_receipt(
                ledger,
                receipt.receipt_id,
                draft_scopes=(ALLOWED_DRAFT_SCOPES[0],),
                drafted_at=NOW,
            )
        self.assertEqual(len(book.proposals), 1)
        ledger.close()
        docket.close()
        remediation.close()
        case.close()

    def test_concurrent_replay_records_one_draft(self):
        case, remediation, docket, ledger, receipt = receipted_source()
        book = SyntheticImplementationProposalBook()

        def draft(_):
            return book.draft_from_receipt(
                ledger, receipt.receipt_id, draft_scopes=SCOPES, drafted_at=NOW
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            proposals = list(pool.map(draft, range(8)))
        self.assertTrue(all(proposal == proposals[0] for proposal in proposals))
        self.assertEqual(len(book.proposals), 1)
        self.assertTrue(book.verify_proposal_chain())
        ledger.close()
        docket.close()
        remediation.close()
        case.close()

    def test_source_receipt_ledger_is_read_only(self):
        case, remediation, docket, ledger, receipt = receipted_source()
        before = ledger.evidence()["report_digest"]
        SyntheticImplementationProposalBook().draft_from_receipt(
            ledger, receipt.receipt_id, draft_scopes=SCOPES, drafted_at=NOW
        )
        self.assertEqual(before, ledger.evidence()["report_digest"])
        ledger.close()
        docket.close()
        remediation.close()
        case.close()

    def test_proposal_tampering_breaks_chain_and_replay_fails_closed(self):
        case, remediation, docket, ledger, receipt = receipted_source()
        book = SyntheticImplementationProposalBook()
        proposal = book.draft_from_receipt(
            ledger, receipt.receipt_id, draft_scopes=SCOPES, drafted_at=NOW
        )
        object.__setattr__(proposal, "code_change_allowed", True)
        self.assertFalse(book.verify_proposal_chain())
        with self.assertRaises(GovernanceRejected):
            book.draft_from_receipt(
                ledger, receipt.receipt_id, draft_scopes=SCOPES, drafted_at=NOW
            )
        ledger.close()
        docket.close()
        remediation.close()
        case.close()

    def test_rehashed_source_binding_tamper_is_rejected_on_replay(self):
        case, remediation, docket, ledger, receipt = receipted_source()
        book = SyntheticImplementationProposalBook()
        proposal = book.draft_from_receipt(
            ledger, receipt.receipt_id, draft_scopes=SCOPES, drafted_at=NOW
        )
        object.__setattr__(proposal, "source_receipt_digest", "f" * 64)
        object.__setattr__(
            proposal, "proposal_digest", canonical_digest(proposal.digest_value())
        )
        self.assertTrue(book.verify_proposal_chain())
        with self.assertRaises(GovernanceRejected):
            book.draft_from_receipt(
                ledger, receipt.receipt_id, draft_scopes=SCOPES, drafted_at=NOW
            )
        ledger.close()
        docket.close()
        remediation.close()
        case.close()

    def test_evidence_caps_state_and_exposes_no_execution_authority(self):
        case, remediation, docket, ledger, receipt = receipted_source()
        book = SyntheticImplementationProposalBook()
        book.draft_from_receipt(
            ledger, receipt.receipt_id, draft_scopes=SCOPES, drafted_at=NOW
        )
        evidence = book.evidence()
        self.assertTrue(evidence["proposal_chain_valid"])
        self.assertTrue(evidence["eternian_review_required"])
        self.assertEqual(evidence["maximum_state"], IMPLEMENTATION_PROPOSAL_STATE)
        for field in (
            "actual_operator_decision_recording_method_present",
            "code_change_method_present",
            "application_method_present",
            "execution_method_present",
            "money_movement_executed",
            "production_activation_allowed",
        ):
            self.assertFalse(evidence[field])
        ledger.close()
        docket.close()
        remediation.close()
        case.close()


if __name__ == "__main__":
    unittest.main()
