from __future__ import annotations

import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256
from pathlib import Path

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_patch_draft_limited_promotion_plans import (
    SyntheticPatchDraftLimitedPromotionPlanBook,
)
from nurion_pg.synthetic_patch_draft_limited_promotion_review_docket import (
    MAXIMUM_LIMITED_PROMOTION_REVIEW_STATE,
    LimitedPromotionPlanReviewDecision,
    LimitedPromotionPlanReviewState,
    SyntheticPatchDraftLimitedPromotionReviewDocket,
)
from tests.test_patch_draft_promotion_decision_intake import NOW
from tests.test_synthetic_patch_draft_limited_promotion_plans import (
    draft,
    receipted_source,
)
from tests.test_synthetic_patch_draft_shadow_review_docket import close_resources


FINDINGS = sha256(b"synthetic limited promotion plan review findings").hexdigest()


def plan_source():
    resources, docket, ledger, receipt = receipted_source()
    book = SyntheticPatchDraftLimitedPromotionPlanBook()
    plan = draft(book, ledger, receipt)
    return resources, docket, ledger, book, plan


def close_source(resources, docket, ledger):
    ledger.close()
    close_resources(resources, docket)


def review_pass(review, plan, **overrides):
    values = {
        "review_id": "synthetic:patch-draft-limited-promotion-review:pass",
        "reviewer_id": (
            "synthetic:eternian-reviewer:patch-draft-limited-promotion:pass"
        ),
        "decision": LimitedPromotionPlanReviewDecision.PASS,
        "findings_digest": FINDINGS,
        "reviewed_at": NOW,
    }
    values.update(overrides)
    return review.record_eternian_review(plan.plan_id, **values)


class SyntheticPatchDraftLimitedPromotionReviewDocketTests(unittest.TestCase):
    def test_requires_synthetic_sqlite_target(self):
        for target in (
            "limited-promotion-review.sqlite3",
            "file:synthetic-review.sqlite3",
            "postgresql://prod/review",
        ):
            with self.assertRaises(GovernanceRejected):
                SyntheticPatchDraftLimitedPromotionReviewDocket(target)

    def test_plan_is_persisted_pending_review_without_authority(self):
        resources, source_docket, ledger, book, plan = plan_source()
        review = SyntheticPatchDraftLimitedPromotionReviewDocket(":memory:")
        record = review.submit_from_book(
            book, plan.source_receipt_id, submitted_at=NOW
        )
        self.assertEqual(
            record.state,
            LimitedPromotionPlanReviewState.PENDING_ETERNIAN_REVIEW,
        )
        self.assertIsNone(record.review_id)
        self.assertFalse(record.synthetic_activation_allowed)
        self.assertFalse(record.production_activation_allowed)
        self.assertTrue(review.verify_record_bindings())
        review.close()
        close_source(resources, source_docket, ledger)

    def test_pass_stops_at_ready_for_separate_synthetic_shadow(self):
        resources, source_docket, ledger, book, plan = plan_source()
        review = SyntheticPatchDraftLimitedPromotionReviewDocket(":memory:")
        review.submit_from_book(book, plan.source_receipt_id, submitted_at=NOW)
        record = review_pass(review, plan)
        self.assertEqual(
            record.state,
            LimitedPromotionPlanReviewState
            .READY_FOR_SYNTHETIC_PATCH_DRAFT_LIMITED_PROMOTION_SHADOW,
        )
        self.assertEqual(review.ready_source(plan.plan_id), record)
        self.assertFalse(record.execution_allowed)
        self.assertFalse(record.synthetic_activation_allowed)
        review.close()
        close_source(resources, source_docket, ledger)

    def test_hold_and_reject_are_terminal_and_not_shadow_ready(self):
        for decision, expected in (
            (
                LimitedPromotionPlanReviewDecision.HOLD,
                LimitedPromotionPlanReviewState.HELD,
            ),
            (
                LimitedPromotionPlanReviewDecision.REJECT,
                LimitedPromotionPlanReviewState.REJECTED,
            ),
        ):
            resources, source_docket, ledger, book, plan = plan_source()
            review = SyntheticPatchDraftLimitedPromotionReviewDocket(":memory:")
            review.submit_from_book(book, plan.source_receipt_id, submitted_at=NOW)
            record = review.record_eternian_review(
                plan.plan_id,
                review_id=(
                    "synthetic:patch-draft-limited-promotion-review:"
                    f"{decision.value.lower()}"
                ),
                reviewer_id=(
                    "synthetic:eternian-reviewer:patch-draft-limited-promotion:"
                    f"{decision.value.lower()}"
                ),
                decision=decision,
                findings_digest=FINDINGS,
                reviewed_at=NOW,
            )
            self.assertEqual(record.state, expected)
            with self.assertRaises(GovernanceRejected):
                review.ready_source(plan.plan_id)
            review.close()
            close_source(resources, source_docket, ledger)

    def test_requires_typed_intact_book_and_valid_submission_time(self):
        review = SyntheticPatchDraftLimitedPromotionReviewDocket(":memory:")
        with self.assertRaises(GovernanceRejected):
            review.submit_from_book(
                object(), "synthetic:receipt:fake", submitted_at=NOW
            )
        resources, source_docket, ledger, book, plan = plan_source()
        for value in (NOW - timedelta(seconds=1), NOW.replace(tzinfo=None)):
            with self.assertRaises(GovernanceRejected):
                review.submit_from_book(
                    book, plan.source_receipt_id, submitted_at=value
                )
        object.__setattr__(plan, "candidate_content_present", True)
        with self.assertRaises(GovernanceRejected):
            review.submit_from_book(
                book, plan.source_receipt_id, submitted_at=NOW
            )
        review.close()
        close_source(resources, source_docket, ledger)

    def test_invalid_review_metadata_time_and_second_review_are_blocked(self):
        resources, source_docket, ledger, book, plan = plan_source()
        review = SyntheticPatchDraftLimitedPromotionReviewDocket(":memory:")
        review.submit_from_book(book, plan.source_receipt_id, submitted_at=NOW)
        invalid = (
            {"review_id": "bad"},
            {"reviewer_id": "bad"},
            {"decision": "PASS"},
            {"findings_digest": "bad"},
            {"reviewed_at": NOW - timedelta(seconds=1)},
            {"reviewed_at": NOW.replace(tzinfo=None)},
        )
        for override in invalid:
            with self.assertRaises(GovernanceRejected):
                review_pass(review, plan, **override)
        first = review_pass(review, plan)
        self.assertEqual(first, review_pass(review, plan))
        with self.assertRaises(GovernanceRejected):
            review_pass(
                review,
                plan,
                findings_digest=sha256(b"different").hexdigest(),
            )
        review.close()
        close_source(resources, source_docket, ledger)

    def test_concurrent_exact_review_records_once(self):
        resources, source_docket, ledger, book, plan = plan_source()
        review = SyntheticPatchDraftLimitedPromotionReviewDocket(":memory:")
        review.submit_from_book(book, plan.source_receipt_id, submitted_at=NOW)

        def record(_):
            return review_pass(review, plan)

        with ThreadPoolExecutor(max_workers=4) as pool:
            records = list(pool.map(record, range(8)))
        self.assertTrue(all(item == records[0] for item in records))
        self.assertTrue(review.verify_record_bindings())
        review.close()
        close_source(resources, source_docket, ledger)

    def test_restart_preserves_plan_review_and_integrity(self):
        resources, source_docket, ledger, book, plan = plan_source()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic-limited-promotion-reviews.sqlite3"
            review = SyntheticPatchDraftLimitedPromotionReviewDocket(path)
            review.submit_from_book(book, plan.source_receipt_id, submitted_at=NOW)
            expected = review_pass(review, plan)
            report = review.evidence()
            review.close()
            reopened = SyntheticPatchDraftLimitedPromotionReviewDocket(path)
            self.assertEqual(reopened.get(plan.plan_id), expected)
            self.assertEqual(reopened.ready_source(plan.plan_id), expected)
            self.assertEqual(reopened.evidence(), report)
            reopened.close()
        close_source(resources, source_docket, ledger)

    def test_audit_failure_rolls_back_submission_and_review(self):
        resources, source_docket, ledger, book, plan = plan_source()
        review = SyntheticPatchDraftLimitedPromotionReviewDocket(":memory:")

        def fail(*_):
            raise sqlite3.IntegrityError("synthetic audit failure")

        review._append_audit = fail
        with self.assertRaises(GovernanceRejected):
            review.submit_from_book(
                book, plan.source_receipt_id, submitted_at=NOW
            )
        self.assertEqual(
            review._connection.execute(
                "SELECT COUNT(*) "
                "FROM synthetic_limited_promotion_review_records"
            ).fetchone()[0],
            0,
        )
        review.close()
        close_source(resources, source_docket, ledger)

    def test_stored_plan_and_audit_tampering_are_detected(self):
        resources, source_docket, ledger, book, plan = plan_source()
        review = SyntheticPatchDraftLimitedPromotionReviewDocket(":memory:")
        review.submit_from_book(book, plan.source_receipt_id, submitted_at=NOW)
        review._connection.execute(
            "UPDATE synthetic_limited_promotion_review_audit "
            "SET audit_digest = ?",
            ("f" * 64,),
        )
        self.assertFalse(review.verify_record_bindings())
        with self.assertRaises(GovernanceRejected):
            review.ready_source(plan.plan_id)
        review._connection.execute(
            "UPDATE synthetic_limited_promotion_review_records "
            "SET plan_json = '{}'"
        )
        with self.assertRaises(GovernanceRejected):
            review.get(plan.plan_id)
        review.close()
        close_source(resources, source_docket, ledger)

    def test_evidence_caps_state_and_exposes_no_activation_authority(self):
        resources, source_docket, ledger, book, plan = plan_source()
        review = SyntheticPatchDraftLimitedPromotionReviewDocket(":memory:")
        review.submit_from_book(book, plan.source_receipt_id, submitted_at=NOW)
        evidence = review.evidence()
        self.assertEqual(
            evidence["maximum_state"], MAXIMUM_LIMITED_PROMOTION_REVIEW_STATE
        )
        self.assertTrue(evidence["audit_chain_valid"])
        self.assertTrue(evidence["record_bindings_valid"])
        for field in (
            "automatic_review_allowed",
            "operator_decision_recorded",
            "candidate_content_present",
            "patch_content_present",
            "diff_content_present",
            "source_code_changed",
            "filesystem_written",
            "application_method_present",
            "safety_baseline_relaxation_method_present",
            "execution_method_present",
            "synthetic_activation_allowed",
            "network_access_method_present",
            "personal_data_used",
            "credentials_used",
            "money_movement_executed",
            "production_activation_allowed",
        ):
            self.assertFalse(evidence[field])
        review.close()
        close_source(resources, source_docket, ledger)


if __name__ == "__main__":
    unittest.main()
