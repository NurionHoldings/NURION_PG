from __future__ import annotations

import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256
from pathlib import Path

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.synthetic_implementation_proposals import (
    SyntheticImplementationProposalBook,
)
from nurion_pg.synthetic_implementation_review_docket import (
    ImplementationProposalReviewDecision,
    ImplementationProposalReviewState,
    MAXIMUM_REVIEW_STATE,
    SyntheticImplementationReviewDocket,
)
from tests.test_operator_decision_intake import NOW
from tests.test_synthetic_implementation_proposals import SCOPES, receipted_source


FINDINGS = sha256(b"synthetic implementation review findings").hexdigest()
REVIEW_ID = "synthetic:implementation-proposal-review:test-1"
REVIEWER_ID = "synthetic:eternian-reviewer:implementation-proposal:test-1"


def pending_review(database=":memory:"):
    case, remediation, source_docket, ledger, receipt = receipted_source()
    book = SyntheticImplementationProposalBook()
    proposal = book.draft_from_receipt(
        ledger, receipt.receipt_id, draft_scopes=SCOPES, drafted_at=NOW
    )
    docket = SyntheticImplementationReviewDocket(database)
    record = docket.submit_from_book(book, receipt.receipt_id, submitted_at=NOW)
    return case, remediation, source_docket, ledger, book, proposal, docket, record


def close_source(case, remediation, source_docket, ledger):
    ledger.close()
    source_docket.close()
    remediation.close()
    case.close()


class SyntheticImplementationReviewDocketTests(unittest.TestCase):
    def test_requires_synthetic_sqlite_target(self):
        with self.assertRaises(GovernanceRejected):
            SyntheticImplementationReviewDocket("implementation.sqlite")
        with self.assertRaises(GovernanceRejected):
            SyntheticImplementationReviewDocket("postgresql://prod/review")

    def test_valid_draft_is_durably_pending_independent_review(self):
        resources = pending_review()
        case, remediation, source_docket, ledger, _, proposal, docket, record = resources
        self.assertEqual(record.proposal, proposal)
        self.assertEqual(
            record.state,
            ImplementationProposalReviewState.PENDING_ETERNIAN_REVIEW,
        )
        self.assertIsNone(record.review_id)
        self.assertFalse(record.code_change_allowed)
        self.assertFalse(record.automatic_application_allowed)
        self.assertFalse(record.execution_allowed)
        self.assertTrue(docket.verify_audit_chain())
        self.assertTrue(docket.verify_record_bindings())
        docket.close()
        close_source(case, remediation, source_docket, ledger)

    def test_pass_stops_at_ready_for_synthetic_patch_shadow(self):
        resources = pending_review()
        case, remediation, source_docket, ledger, _, proposal, docket, _ = resources
        record = docket.record_eternian_review(
            proposal.proposal_id,
            review_id=REVIEW_ID,
            reviewer_id=REVIEWER_ID,
            decision=ImplementationProposalReviewDecision.PASS,
            findings_digest=FINDINGS,
            reviewed_at=NOW,
        )
        self.assertEqual(
            record.state,
            ImplementationProposalReviewState.READY_FOR_SYNTHETIC_PATCH_SHADOW,
        )
        self.assertEqual(docket.ready_source(proposal.proposal_id), record)
        self.assertFalse(record.actual_operator_decision_recorded)
        self.assertFalse(record.code_change_allowed)
        self.assertFalse(record.execution_allowed)
        docket.close()
        close_source(case, remediation, source_docket, ledger)

    def test_hold_and_reject_are_terminal_and_not_shadow_ready(self):
        for decision, expected_state in (
            (
                ImplementationProposalReviewDecision.HOLD,
                ImplementationProposalReviewState.HELD,
            ),
            (
                ImplementationProposalReviewDecision.REJECT,
                ImplementationProposalReviewState.REJECTED,
            ),
        ):
            resources = pending_review()
            case, remediation, source_docket, ledger, _, proposal, docket, _ = resources
            record = docket.record_eternian_review(
                proposal.proposal_id,
                review_id=REVIEW_ID,
                reviewer_id=REVIEWER_ID,
                decision=decision,
                findings_digest=FINDINGS,
                reviewed_at=NOW,
            )
            self.assertEqual(record.state, expected_state)
            with self.assertRaises(GovernanceRejected):
                docket.ready_source(proposal.proposal_id)
            docket.close()
            close_source(case, remediation, source_docket, ledger)

    def test_review_metadata_and_time_are_validated(self):
        resources = pending_review()
        case, remediation, source_docket, ledger, _, proposal, docket, _ = resources
        invalid = (
            ("review:test", REVIEWER_ID, FINDINGS, NOW),
            (
                "synthetic:implementation-proposal-review:",
                REVIEWER_ID,
                FINDINGS,
                NOW,
            ),
            (REVIEW_ID, "synthetic:reviewer:wrong", FINDINGS, NOW),
            (
                REVIEW_ID,
                "synthetic:eternian-reviewer:implementation-proposal:",
                FINDINGS,
                NOW,
            ),
            (REVIEW_ID, REVIEWER_ID, "bad", NOW),
            (REVIEW_ID, REVIEWER_ID, FINDINGS, NOW.replace(tzinfo=None)),
            (REVIEW_ID, REVIEWER_ID, FINDINGS, NOW - timedelta(seconds=1)),
        )
        for review_id, reviewer_id, findings, reviewed_at in invalid:
            with self.assertRaises(GovernanceRejected):
                docket.record_eternian_review(
                    proposal.proposal_id,
                    review_id=review_id,
                    reviewer_id=reviewer_id,
                    decision=ImplementationProposalReviewDecision.PASS,
                    findings_digest=findings,
                    reviewed_at=reviewed_at,
                )
        docket.close()
        close_source(case, remediation, source_docket, ledger)

    def test_submission_requires_typed_intact_book_and_time(self):
        case, remediation, source_docket, ledger, receipt = receipted_source()
        docket = SyntheticImplementationReviewDocket(":memory:")
        with self.assertRaises(GovernanceRejected):
            docket.submit_from_book(object(), receipt.receipt_id, submitted_at=NOW)
        book = SyntheticImplementationProposalBook()
        proposal = book.draft_from_receipt(
            ledger, receipt.receipt_id, draft_scopes=SCOPES, drafted_at=NOW
        )
        object.__setattr__(proposal, "execution_allowed", True)
        with self.assertRaises(GovernanceRejected):
            docket.submit_from_book(book, receipt.receipt_id, submitted_at=NOW)
        object.__setattr__(proposal, "execution_allowed", False)
        object.__setattr__(proposal, "proposal_digest", canonical_digest(proposal.digest_value()))
        with self.assertRaises(GovernanceRejected):
            docket.submit_from_book(
                book, receipt.receipt_id, submitted_at=NOW - timedelta(seconds=1)
            )
        docket.close()
        close_source(case, remediation, source_docket, ledger)

    def test_exact_submission_replay_is_idempotent_and_collision_fails(self):
        resources = pending_review()
        case, remediation, source_docket, ledger, book, proposal, docket, first = resources
        second = docket.submit_from_book(
            book, proposal.source_receipt_id, submitted_at=NOW + timedelta(seconds=1)
        )
        self.assertEqual(first, second)
        object.__setattr__(proposal, "draft_scopes", (SCOPES[0],))
        object.__setattr__(proposal, "proposal_digest", canonical_digest(proposal.digest_value()))
        self.assertFalse(book.verify_proposal_chain())
        with self.assertRaises(GovernanceRejected):
            docket.submit_from_book(book, proposal.source_receipt_id, submitted_at=NOW)
        docket.close()
        close_source(case, remediation, source_docket, ledger)

    def test_exact_concurrent_review_records_once(self):
        resources = pending_review()
        case, remediation, source_docket, ledger, _, proposal, docket, _ = resources

        def review(_):
            return docket.record_eternian_review(
                proposal.proposal_id,
                review_id=REVIEW_ID,
                reviewer_id=REVIEWER_ID,
                decision=ImplementationProposalReviewDecision.PASS,
                findings_digest=FINDINGS,
                reviewed_at=NOW,
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            records = list(pool.map(review, range(8)))
        self.assertTrue(all(record == records[0] for record in records))
        self.assertEqual(
            docket._connection.execute(
                "SELECT COUNT(*) FROM synthetic_implementation_review_audit"
            ).fetchone()[0],
            2,
        )
        docket.close()
        close_source(case, remediation, source_docket, ledger)

    def test_audit_failure_rolls_back_submission(self):
        case, remediation, source_docket, ledger, receipt = receipted_source()
        book = SyntheticImplementationProposalBook()
        book.draft_from_receipt(
            ledger, receipt.receipt_id, draft_scopes=SCOPES, drafted_at=NOW
        )
        docket = SyntheticImplementationReviewDocket(":memory:")

        def fail(*_):
            raise sqlite3.IntegrityError("synthetic audit failure")

        docket._append_audit = fail
        with self.assertRaises(GovernanceRejected):
            docket.submit_from_book(book, receipt.receipt_id, submitted_at=NOW)
        self.assertEqual(
            docket._connection.execute(
                "SELECT COUNT(*) FROM synthetic_implementation_review_records"
            ).fetchone()[0],
            0,
        )
        docket.close()
        close_source(case, remediation, source_docket, ledger)

    def test_restart_preserves_review_and_integrity(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "synthetic-implementation-reviews.sqlite3"
            resources = pending_review(database)
            case, remediation, source_docket, ledger, _, proposal, docket, _ = resources
            expected = docket.record_eternian_review(
                proposal.proposal_id,
                review_id=REVIEW_ID,
                reviewer_id=REVIEWER_ID,
                decision=ImplementationProposalReviewDecision.PASS,
                findings_digest=FINDINGS,
                reviewed_at=NOW,
            )
            docket.close()
            reopened = SyntheticImplementationReviewDocket(database)
            self.assertEqual(reopened.get(proposal.proposal_id), expected)
            self.assertTrue(reopened.verify_audit_chain())
            self.assertTrue(reopened.verify_record_bindings())
            reopened.close()
            close_source(case, remediation, source_docket, ledger)

    def test_stored_proposal_review_and_audit_tampering_are_detected(self):
        resources = pending_review()
        case, remediation, source_docket, ledger, _, proposal, docket, _ = resources
        docket.record_eternian_review(
            proposal.proposal_id,
            review_id=REVIEW_ID,
            reviewer_id=REVIEWER_ID,
            decision=ImplementationProposalReviewDecision.PASS,
            findings_digest=FINDINGS,
            reviewed_at=NOW,
        )
        docket._connection.execute(
            "UPDATE synthetic_implementation_review_records SET findings_digest = ?",
            ("e" * 64,),
        )
        self.assertFalse(docket.verify_record_bindings())
        docket._connection.execute(
            "UPDATE synthetic_implementation_review_records SET proposal_json = '{}'"
        )
        with self.assertRaises(GovernanceRejected):
            docket.get(proposal.proposal_id)
        docket.close()
        close_source(case, remediation, source_docket, ledger)

    def test_audit_and_metadata_tampering_fail_closed(self):
        resources = pending_review()
        case, remediation, source_docket, ledger, _, proposal, docket, _ = resources
        docket._connection.execute(
            "UPDATE synthetic_implementation_review_audit SET audit_digest = ?",
            ("f" * 64,),
        )
        self.assertFalse(docket.verify_audit_chain())
        with self.assertRaises(GovernanceRejected):
            docket.ready_source(proposal.proposal_id)
        docket._connection.execute("DELETE FROM synthetic_implementation_review_metadata")
        self.assertFalse(docket.verify_metadata())
        docket.close()
        close_source(case, remediation, source_docket, ledger)

    def test_evidence_caps_state_and_exposes_no_execution_authority(self):
        resources = pending_review()
        case, remediation, source_docket, ledger, _, proposal, docket, _ = resources
        docket.record_eternian_review(
            proposal.proposal_id,
            review_id=REVIEW_ID,
            reviewer_id=REVIEWER_ID,
            decision=ImplementationProposalReviewDecision.PASS,
            findings_digest=FINDINGS,
            reviewed_at=NOW,
        )
        evidence = docket.evidence()
        self.assertTrue(evidence["metadata_valid"])
        self.assertTrue(evidence["audit_chain_valid"])
        self.assertTrue(evidence["record_bindings_valid"])
        self.assertEqual(evidence["maximum_state"], MAXIMUM_REVIEW_STATE)
        self.assertNotEqual(evidence["audit_head_digest"], "0" * 64)
        for field in (
            "actual_operator_decision_recording_method_present",
            "code_change_method_present",
            "application_method_present",
            "safety_baseline_relaxation_method_present",
            "execution_method_present",
            "money_movement_executed",
            "production_activation_allowed",
        ):
            self.assertFalse(evidence[field])
        docket.close()
        close_source(case, remediation, source_docket, ledger)


if __name__ == "__main__":
    unittest.main()
