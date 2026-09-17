from __future__ import annotations

import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256
from pathlib import Path

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_patch_shadow import SyntheticPatchShadowBook
from nurion_pg.synthetic_patch_shadow_review_docket import (
    PatchShadowReviewDecision,
    PatchShadowReviewState,
    SyntheticPatchShadowReviewDocket,
)
from tests.test_operator_decision_intake import NOW
from tests.test_synthetic_patch_shadow import (
    close_all,
    fixtures_for,
    ready_review,
)


FINDINGS = sha256(b"synthetic patch shadow independent review").hexdigest()


def shadow_source(**fixture_changes):
    resources = ready_review()
    case, remediation, source_docket, ledger, _, proposal, review_docket, _ = resources
    book = SyntheticPatchShadowBook()
    assessment = book.evaluate(
        review_docket,
        proposal.proposal_id,
        fixtures_for(proposal, **fixture_changes),
        evaluated_at=NOW,
    )
    return resources, book, assessment


def close_resources(resources, docket=None):
    if docket is not None:
        docket.close()
    case, remediation, source_docket, ledger, _, _, review_docket, _ = resources
    close_all(case, remediation, source_docket, ledger, review_docket)


class SyntheticPatchShadowReviewDocketTests(unittest.TestCase):
    def test_requires_synthetic_sqlite_target(self):
        with self.assertRaises(GovernanceRejected):
            SyntheticPatchShadowReviewDocket("production.sqlite")
        with self.assertRaises(GovernanceRejected):
            SyntheticPatchShadowReviewDocket("postgresql://prod/patch-shadow")

    def test_requires_typed_book_and_stable_submission_time(self):
        resources, book, assessment = shadow_source()
        docket = SyntheticPatchShadowReviewDocket(":memory:")
        with self.assertRaises(GovernanceRejected):
            docket.submit_from_book(object(), assessment.proposal_id, submitted_at=NOW)
        docket.submit_from_book(book, assessment.proposal_id, submitted_at=NOW)
        with self.assertRaises(GovernanceRejected):
            docket.submit_from_book(
                book,
                assessment.proposal_id,
                submitted_at=NOW + timedelta(seconds=1),
            )
        close_resources(resources, docket)

    def test_passed_shadow_is_persisted_pending_review_with_exact_identity(self):
        resources, book, assessment = shadow_source()
        docket = SyntheticPatchShadowReviewDocket(":memory:")
        record = docket.submit_from_book(
            book, assessment.proposal_id, submitted_at=NOW
        )
        self.assertEqual(record.shadow_id, assessment.shadow_id)
        self.assertEqual(record.state, PatchShadowReviewState.PENDING_ETERNIAN_REVIEW)
        self.assertEqual(record.shadow_assessment_digest, assessment.assessment_digest)
        self.assertFalse(record.automatic_review_allowed)
        self.assertFalse(record.patch_content_present)
        self.assertTrue(docket.verify_audit_chain())
        self.assertTrue(docket.verify_record_bindings())
        close_resources(resources, docket)

    def test_nonpassing_or_tampered_shadow_cannot_enter_docket(self):
        resources, book, assessment = shadow_source(regression_test_passed=False)
        docket = SyntheticPatchShadowReviewDocket(":memory:")
        with self.assertRaises(GovernanceRejected):
            docket.submit_from_book(book, assessment.proposal_id, submitted_at=NOW)
        close_resources(resources, docket)

        resources, book, assessment = shadow_source()
        docket = SyntheticPatchShadowReviewDocket(":memory:")
        object.__setattr__(book._assessments[0], "reason", "tampered")
        with self.assertRaises(GovernanceRejected):
            docket.submit_from_book(book, assessment.proposal_id, submitted_at=NOW)
        close_resources(resources, docket)

    def test_pass_stops_at_ready_for_operator_decision(self):
        resources, book, assessment = shadow_source()
        docket = SyntheticPatchShadowReviewDocket(":memory:")
        record = docket.submit_from_book(
            book, assessment.proposal_id, submitted_at=NOW
        )
        reviewed = docket.record_eternian_review(
            record.shadow_id,
            review_id="synthetic:patch-shadow-review:pass",
            reviewer_id="synthetic:eternian-reviewer:patch-shadow-independent",
            decision=PatchShadowReviewDecision.PASS,
            findings_digest=FINDINGS,
            reviewed_at=NOW,
        )
        self.assertEqual(
            reviewed.state, PatchShadowReviewState.READY_FOR_OPERATOR_DECISION
        )
        self.assertFalse(reviewed.operator_decision_recorded)
        self.assertFalse(reviewed.code_change_allowed)
        self.assertFalse(reviewed.production_activation_allowed)
        close_resources(resources, docket)

    def test_hold_and_reject_are_terminal(self):
        for decision, state in (
            (PatchShadowReviewDecision.HOLD, PatchShadowReviewState.HELD),
            (PatchShadowReviewDecision.REJECT, PatchShadowReviewState.REJECTED),
        ):
            resources, book, assessment = shadow_source()
            docket = SyntheticPatchShadowReviewDocket(":memory:")
            record = docket.submit_from_book(
                book, assessment.proposal_id, submitted_at=NOW
            )
            reviewed = docket.record_eternian_review(
                record.shadow_id,
                review_id=f"synthetic:patch-shadow-review:{decision.value.lower()}",
                reviewer_id="synthetic:eternian-reviewer:patch-shadow-independent",
                decision=decision,
                findings_digest=FINDINGS,
                reviewed_at=NOW,
            )
            self.assertEqual(reviewed.state, state)
            with self.assertRaises(GovernanceRejected):
                docket.record_eternian_review(
                    record.shadow_id,
                    review_id="synthetic:patch-shadow-review:second",
                    reviewer_id="synthetic:eternian-reviewer:patch-shadow-independent",
                    decision=PatchShadowReviewDecision.PASS,
                    findings_digest=FINDINGS,
                    reviewed_at=NOW,
                )
            close_resources(resources, docket)

    def test_review_metadata_time_and_idempotency_are_enforced(self):
        resources, book, assessment = shadow_source()
        docket = SyntheticPatchShadowReviewDocket(":memory:")
        record = docket.submit_from_book(
            book, assessment.proposal_id, submitted_at=NOW
        )
        arguments = {
            "review_id": "synthetic:patch-shadow-review:idempotent",
            "reviewer_id": "synthetic:eternian-reviewer:patch-shadow-independent",
            "decision": PatchShadowReviewDecision.PASS,
            "findings_digest": FINDINGS,
            "reviewed_at": NOW,
        }
        with self.assertRaises(GovernanceRejected):
            docket.record_eternian_review(
                record.shadow_id,
                **{**arguments, "review_id": "bad"},
            )
        with self.assertRaises(GovernanceRejected):
            docket.record_eternian_review(
                record.shadow_id,
                **{**arguments, "reviewed_at": NOW - timedelta(seconds=1)},
            )
        first = docket.record_eternian_review(record.shadow_id, **arguments)
        second = docket.record_eternian_review(record.shadow_id, **arguments)
        self.assertEqual(first, second)
        with self.assertRaises(GovernanceRejected):
            docket.record_eternian_review(
                record.shadow_id,
                **{**arguments, "findings_digest": sha256(b"different").hexdigest()},
            )
        close_resources(resources, docket)

    def test_restart_preserves_review_state(self):
        resources, book, assessment = shadow_source()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic-patch-shadow-review.sqlite3"
            docket = SyntheticPatchShadowReviewDocket(path)
            record = docket.submit_from_book(
                book, assessment.proposal_id, submitted_at=NOW
            )
            docket.record_eternian_review(
                record.shadow_id,
                review_id="synthetic:patch-shadow-review:restart",
                reviewer_id="synthetic:eternian-reviewer:patch-shadow-restart",
                decision=PatchShadowReviewDecision.PASS,
                findings_digest=FINDINGS,
                reviewed_at=NOW,
            )
            docket.close()
            reopened = SyntheticPatchShadowReviewDocket(path)
            self.assertEqual(
                reopened.get(record.shadow_id).state,
                PatchShadowReviewState.READY_FOR_OPERATOR_DECISION,
            )
            self.assertTrue(reopened.verify_record_bindings())
            reopened.close()
        close_resources(resources)

    def test_concurrent_review_records_one_transition(self):
        resources, book, assessment = shadow_source()
        docket = SyntheticPatchShadowReviewDocket(":memory:")
        record = docket.submit_from_book(
            book, assessment.proposal_id, submitted_at=NOW
        )

        def review(_):
            return docket.record_eternian_review(
                record.shadow_id,
                review_id="synthetic:patch-shadow-review:concurrent",
                reviewer_id="synthetic:eternian-reviewer:patch-shadow-concurrent",
                decision=PatchShadowReviewDecision.PASS,
                findings_digest=FINDINGS,
                reviewed_at=NOW,
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(review, range(8)))
        self.assertTrue(all(result == results[0] for result in results))
        count = docket._connection.execute(
            "SELECT COUNT(*) FROM synthetic_patch_shadow_reviews"
        ).fetchone()[0]
        self.assertEqual(count, 1)
        close_resources(resources, docket)

    def test_audit_failure_rolls_back_submission(self):
        resources, book, assessment = shadow_source()
        docket = SyntheticPatchShadowReviewDocket(":memory:")

        def fail(**_):
            raise sqlite3.IntegrityError("synthetic audit failure")

        docket._append_audit = fail
        with self.assertRaises(GovernanceRejected):
            docket.submit_from_book(book, assessment.proposal_id, submitted_at=NOW)
        count = docket._connection.execute(
            "SELECT COUNT(*) FROM synthetic_patch_shadow_review_dockets"
        ).fetchone()[0]
        self.assertEqual(count, 0)
        close_resources(resources, docket)

    def test_audit_failure_rolls_back_review_transition(self):
        resources, book, assessment = shadow_source()
        docket = SyntheticPatchShadowReviewDocket(":memory:")
        record = docket.submit_from_book(
            book, assessment.proposal_id, submitted_at=NOW
        )

        def fail(**_):
            raise sqlite3.IntegrityError("synthetic review audit failure")

        docket._append_audit = fail
        with self.assertRaises(GovernanceRejected):
            docket.record_eternian_review(
                record.shadow_id,
                review_id="synthetic:patch-shadow-review:audit-failure",
                reviewer_id="synthetic:eternian-reviewer:patch-shadow-audit",
                decision=PatchShadowReviewDecision.PASS,
                findings_digest=FINDINGS,
                reviewed_at=NOW,
            )
        self.assertEqual(
            docket.get(record.shadow_id).state,
            PatchShadowReviewState.PENDING_ETERNIAN_REVIEW,
        )
        count = docket._connection.execute(
            "SELECT COUNT(*) FROM synthetic_patch_shadow_reviews"
        ).fetchone()[0]
        self.assertEqual(count, 0)
        close_resources(resources, docket)

    def test_tampering_blocks_review_and_idempotent_replay(self):
        resources, book, assessment = shadow_source()
        docket = SyntheticPatchShadowReviewDocket(":memory:")
        record = docket.submit_from_book(
            book, assessment.proposal_id, submitted_at=NOW
        )
        arguments = {
            "review_id": "synthetic:patch-shadow-review:tamper",
            "reviewer_id": "synthetic:eternian-reviewer:patch-shadow-tamper",
            "decision": PatchShadowReviewDecision.PASS,
            "findings_digest": FINDINGS,
            "reviewed_at": NOW,
        }
        docket.record_eternian_review(record.shadow_id, **arguments)
        docket._connection.execute(
            "UPDATE synthetic_patch_shadow_review_audit "
            "SET actor_id = 'synthetic:tampered' WHERE audit_sequence = 2"
        )
        self.assertFalse(docket.verify_audit_chain())
        with self.assertRaises(GovernanceRejected):
            docket.record_eternian_review(record.shadow_id, **arguments)
        close_resources(resources, docket)

    def test_stored_assessment_tampering_is_rejected(self):
        resources, book, assessment = shadow_source()
        docket = SyntheticPatchShadowReviewDocket(":memory:")
        record = docket.submit_from_book(
            book, assessment.proposal_id, submitted_at=NOW
        )
        docket._connection.execute(
            "UPDATE synthetic_patch_shadow_review_dockets "
            "SET assessment_json = '{}' WHERE shadow_id = ?",
            (record.shadow_id,),
        )
        with self.assertRaises(GovernanceRejected):
            docket.get(record.shadow_id)
        self.assertFalse(docket.verify_record_bindings())
        close_resources(resources, docket)

    def test_ready_source_requires_pass_and_is_read_only(self):
        resources, book, assessment = shadow_source()
        docket = SyntheticPatchShadowReviewDocket(":memory:")
        record = docket.submit_from_book(
            book, assessment.proposal_id, submitted_at=NOW
        )
        with self.assertRaises(GovernanceRejected):
            docket.ready_source(record.shadow_id)
        docket.record_eternian_review(
            record.shadow_id,
            review_id="synthetic:patch-shadow-review:ready-source",
            reviewer_id="synthetic:eternian-reviewer:patch-shadow-ready-source",
            decision=PatchShadowReviewDecision.PASS,
            findings_digest=FINDINGS,
            reviewed_at=NOW,
        )
        before = docket.evidence()["report_digest"]
        source = docket.ready_source(record.shadow_id)
        after = docket.evidence()["report_digest"]
        self.assertEqual(source.shadow_id, assessment.shadow_id)
        self.assertEqual(
            source.source_review_digest, assessment.source_review_digest
        )
        self.assertEqual(source.shadow_assessment_digest, assessment.assessment_digest)
        self.assertEqual(before, after)
        close_resources(resources, docket)

    def test_evidence_proves_non_authorizing_review_boundary(self):
        resources, book, assessment = shadow_source()
        docket = SyntheticPatchShadowReviewDocket(":memory:")
        docket.submit_from_book(book, assessment.proposal_id, submitted_at=NOW)
        evidence = docket.evidence()
        self.assertTrue(evidence["audit_chain_valid"])
        self.assertTrue(evidence["record_bindings_valid"])
        self.assertEqual(evidence["maximum_state"], "READY_FOR_OPERATOR_DECISION")
        for field in (
            "automatic_review_allowed",
            "patch_content_present",
            "operator_decision_method_present",
            "code_change_method_present",
            "application_method_present",
            "safety_baseline_relaxation_allowed",
            "execution_method_present",
            "network_access_method_present",
            "personal_data_used",
            "credentials_used",
            "money_movement_executed",
            "production_activation_allowed",
        ):
            self.assertFalse(evidence[field])
        close_resources(resources, docket)


if __name__ == "__main__":
    unittest.main()
