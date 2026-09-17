from __future__ import annotations

import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.reconciliation_case_docket import (
    ReconciliationCaseReviewDecision,
    SyntheticReconciliationCaseDocket,
)
from nurion_pg.reconciliation_remediation_proposals import (
    SyntheticRemediationProposalBook,
)
from nurion_pg.remediation_review_docket import (
    RemediationDocketState,
    RemediationReviewDecision,
    SyntheticRemediationReviewDocket,
)


NOW = datetime(2026, 9, 17, tzinfo=UTC)
FINDINGS_DIGEST = sha256(b"synthetic remediation docket review").hexdigest()


def source_report(code: str = "PROPOSAL_MISSING_DOCKET") -> dict[str, object]:
    value: dict[str, object] = {
        "schema": "nurion.pg.synthetic-reconciliation-report.v1",
        "observed_at": NOW.isoformat(),
        "status": "BLOCKED",
        "component_snapshot_digests": {
            name: sha256(name.encode("ascii")).hexdigest()
            for name in ("payment", "inbox", "proposals", "docket")
        },
        "findings": [
            {
                "code": code,
                "severity": "BLOCKED",
                "subject_id": "synthetic:subject:remediation-review",
                "detail": "synthetic discrepancy",
                "suggested_action": "Eternian review required",
                "automatic_repair_allowed": False,
            }
        ],
        "finding_counts": {"WARNING": 0, "BLOCKED": 1},
        "read_only_verified": True,
        "synthetic_only": True,
        "automatic_repair_allowed": False,
        "operator_decision_recorded": False,
        "payment_state_changed": False,
        "money_movement_executed": False,
        "production_activation_allowed": False,
    }
    return {**value, "report_digest": canonical_digest(value)}


def proposal_book(code: str = "PROPOSAL_MISSING_DOCKET"):
    case_docket = SyntheticReconciliationCaseDocket(":memory:")
    case = case_docket.submit_report(source_report(code), submitted_at=NOW)
    case_docket.record_eternian_review(
        case.case_id,
        review_id="synthetic:reconciliation-review:remediation-docket-source",
        reviewer_id="synthetic:eternian-reviewer:remediation-docket-source",
        decision=ReconciliationCaseReviewDecision.CONFIRM,
        findings_digest=FINDINGS_DIGEST,
        reviewed_at=NOW,
    )
    book = SyntheticRemediationProposalBook()
    assessment = book.draft(case_docket, case.case_id, now=NOW)
    return case_docket, case.case_id, book, assessment


class RemediationReviewDocketTests(unittest.TestCase):
    def test_requires_synthetic_sqlite_target(self):
        with self.assertRaises(GovernanceRejected):
            SyntheticRemediationReviewDocket("production.db")
        with self.assertRaises(GovernanceRejected):
            SyntheticRemediationReviewDocket("postgresql://prod/remediation")

    def test_valid_proposal_is_persisted_pending_independent_review(self):
        source, case_id, book, assessment = proposal_book()
        docket = SyntheticRemediationReviewDocket(":memory:")
        record = docket.submit_from_book(book, case_id, submitted_at=NOW)
        self.assertEqual(record.proposal_id, assessment.proposal.proposal_id)
        self.assertEqual(record.state, RemediationDocketState.PENDING_ETERNIAN_REVIEW)
        self.assertFalse(record.automatic_review_allowed)
        self.assertTrue(docket.verify_audit_chain())
        self.assertTrue(docket.verify_record_bindings())
        docket.close()
        source.close()

    def test_unstructured_human_review_assessment_cannot_be_submitted(self):
        source, case_id, book, assessment = proposal_book("UNKNOWN_FUTURE_FINDING")
        self.assertIsNone(assessment.proposal)
        docket = SyntheticRemediationReviewDocket(":memory:")
        with self.assertRaises(GovernanceRejected):
            docket.submit_from_book(book, case_id, submitted_at=NOW)
        docket.close()
        source.close()

    def test_tampered_assessment_chain_is_blocked(self):
        source, case_id, book, _ = proposal_book()
        book._assessments[0] = replace(book._assessments[0], reason="tampered")
        docket = SyntheticRemediationReviewDocket(":memory:")
        with self.assertRaises(GovernanceRejected):
            docket.submit_from_book(book, case_id, submitted_at=NOW)
        docket.close()
        source.close()

    def test_pass_stops_at_ready_for_synthetic_shadow(self):
        source, case_id, book, assessment = proposal_book()
        docket = SyntheticRemediationReviewDocket(":memory:")
        record = docket.submit_from_book(book, case_id, submitted_at=NOW)
        reviewed = docket.record_eternian_review(
            record.proposal_id,
            review_id="synthetic:remediation-review:pass",
            reviewer_id="synthetic:eternian-reviewer:independent",
            decision=RemediationReviewDecision.PASS,
            findings_digest=FINDINGS_DIGEST,
            reviewed_at=NOW,
        )
        self.assertEqual(reviewed.state, RemediationDocketState.READY_FOR_SYNTHETIC_SHADOW)
        self.assertEqual(assessment.proposal.proposal_digest, reviewed.proposal_digest)
        evidence = docket.evidence()
        self.assertEqual(evidence["maximum_state"], "READY_FOR_SYNTHETIC_SHADOW")
        self.assertFalse(evidence["synthetic_shadow_method_present"])
        self.assertFalse(evidence["code_change_method_present"])
        self.assertFalse(evidence["application_method_present"])
        self.assertFalse(evidence["operator_decision_method_present"])
        self.assertFalse(evidence["execution_method_present"])
        docket.close()
        source.close()

    def test_hold_and_reject_are_terminal(self):
        for decision, state in (
            (RemediationReviewDecision.HOLD, RemediationDocketState.HELD),
            (RemediationReviewDecision.REJECT, RemediationDocketState.REJECTED),
        ):
            source, case_id, book, _ = proposal_book()
            docket = SyntheticRemediationReviewDocket(":memory:")
            record = docket.submit_from_book(book, case_id, submitted_at=NOW)
            result = docket.record_eternian_review(
                record.proposal_id,
                review_id=f"synthetic:remediation-review:{decision.value.lower()}",
                reviewer_id="synthetic:eternian-reviewer:independent",
                decision=decision,
                findings_digest=FINDINGS_DIGEST,
                reviewed_at=NOW,
            )
            self.assertEqual(result.state, state)
            with self.assertRaises(GovernanceRejected):
                docket.record_eternian_review(
                    record.proposal_id,
                    review_id="synthetic:remediation-review:second",
                    reviewer_id="synthetic:eternian-reviewer:independent",
                    decision=RemediationReviewDecision.PASS,
                    findings_digest=FINDINGS_DIGEST,
                    reviewed_at=NOW,
                )
            docket.close()
            source.close()

    def test_review_requires_valid_identity_digest_and_time(self):
        source, case_id, book, _ = proposal_book()
        docket = SyntheticRemediationReviewDocket(":memory:")
        record = docket.submit_from_book(book, case_id, submitted_at=NOW)
        invalid = (
            {"reviewer_id": "synthetic:arkaon:NURION_PG:remediation-proposer"},
            {"reviewer_id": "synthetic:not-eternian"},
            {"findings_digest": "bad"},
            {"reviewed_at": NOW - timedelta(seconds=1)},
        )
        for index, changes in enumerate(invalid):
            arguments = {
                "review_id": f"synthetic:remediation-review:invalid-{index}",
                "reviewer_id": "synthetic:eternian-reviewer:independent",
                "decision": RemediationReviewDecision.PASS,
                "findings_digest": FINDINGS_DIGEST,
                "reviewed_at": NOW,
                **changes,
            }
            with self.assertRaises(GovernanceRejected):
                docket.record_eternian_review(record.proposal_id, **arguments)
        docket.close()
        source.close()

    def test_review_idempotency_rejects_payload_mismatch(self):
        source, case_id, book, _ = proposal_book()
        docket = SyntheticRemediationReviewDocket(":memory:")
        record = docket.submit_from_book(book, case_id, submitted_at=NOW)
        arguments = {
            "review_id": "synthetic:remediation-review:idempotent",
            "reviewer_id": "synthetic:eternian-reviewer:independent",
            "decision": RemediationReviewDecision.PASS,
            "findings_digest": FINDINGS_DIGEST,
            "reviewed_at": NOW,
        }
        first = docket.record_eternian_review(record.proposal_id, **arguments)
        second = docket.record_eternian_review(record.proposal_id, **arguments)
        self.assertEqual(first, second)
        with self.assertRaises(GovernanceRejected):
            docket.record_eternian_review(
                record.proposal_id,
                **{**arguments, "findings_digest": sha256(b"other").hexdigest()},
            )
        docket.close()
        source.close()

    def test_restart_preserves_state_and_integrity(self):
        source, case_id, book, _ = proposal_book()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic-remediation.sqlite3"
            docket = SyntheticRemediationReviewDocket(path)
            record = docket.submit_from_book(book, case_id, submitted_at=NOW)
            docket.record_eternian_review(
                record.proposal_id,
                review_id="synthetic:remediation-review:restart",
                reviewer_id="synthetic:eternian-reviewer:restart",
                decision=RemediationReviewDecision.PASS,
                findings_digest=FINDINGS_DIGEST,
                reviewed_at=NOW,
            )
            docket.close()
            reopened = SyntheticRemediationReviewDocket(path)
            self.assertEqual(
                reopened.get(record.proposal_id).state,
                RemediationDocketState.READY_FOR_SYNTHETIC_SHADOW,
            )
            self.assertTrue(reopened.verify_audit_chain())
            self.assertTrue(reopened.verify_record_bindings())
            reopened.close()
        source.close()

    def test_concurrent_review_records_exactly_one_decision(self):
        source, case_id, book, _ = proposal_book()
        docket = SyntheticRemediationReviewDocket(":memory:")
        record = docket.submit_from_book(book, case_id, submitted_at=NOW)

        def review(_):
            return docket.record_eternian_review(
                record.proposal_id,
                review_id="synthetic:remediation-review:concurrent",
                reviewer_id="synthetic:eternian-reviewer:concurrent",
                decision=RemediationReviewDecision.PASS,
                findings_digest=FINDINGS_DIGEST,
                reviewed_at=NOW,
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(review, range(8)))
        self.assertTrue(all(result == results[0] for result in results))
        review_count = docket._connection.execute(
            "SELECT COUNT(*) FROM synthetic_remediation_reviews"
        ).fetchone()[0]
        self.assertEqual(review_count, 1)
        self.assertTrue(docket.verify_record_bindings())
        docket.close()
        source.close()

    def test_audit_failure_rolls_back_submission(self):
        source, case_id, book, _ = proposal_book()
        docket = SyntheticRemediationReviewDocket(":memory:")
        original = docket._append_audit

        def fail(**_):
            raise sqlite3.IntegrityError("synthetic audit failure")

        docket._append_audit = fail
        with self.assertRaises(GovernanceRejected):
            docket.submit_from_book(book, case_id, submitted_at=NOW)
        count = docket._connection.execute(
            "SELECT COUNT(*) FROM synthetic_remediation_dockets"
        ).fetchone()[0]
        self.assertEqual(count, 0)
        docket._append_audit = original
        docket.close()
        source.close()

    def test_stored_payload_review_and_audit_tampering_are_detected(self):
        source, case_id, book, _ = proposal_book()
        docket = SyntheticRemediationReviewDocket(":memory:")
        record = docket.submit_from_book(book, case_id, submitted_at=NOW)
        docket.record_eternian_review(
            record.proposal_id,
            review_id="synthetic:remediation-review:tamper",
            reviewer_id="synthetic:eternian-reviewer:tamper",
            decision=RemediationReviewDecision.PASS,
            findings_digest=FINDINGS_DIGEST,
            reviewed_at=NOW,
        )
        docket._connection.execute(
            "UPDATE synthetic_remediation_reviews SET findings_digest = ?",
            (sha256(b"tampered").hexdigest(),),
        )
        self.assertFalse(docket.verify_record_bindings())
        docket._connection.execute(
            "UPDATE synthetic_remediation_docket_audit SET action = 'TAMPERED' WHERE audit_sequence = 1"
        )
        self.assertFalse(docket.verify_audit_chain())
        docket._connection.execute(
            "UPDATE synthetic_remediation_dockets SET proposal_json = '{}'"
        )
        with self.assertRaises(GovernanceRejected):
            docket.get(record.proposal_id)
        docket.close()
        source.close()


if __name__ == "__main__":
    unittest.main()
