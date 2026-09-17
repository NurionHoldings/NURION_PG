from __future__ import annotations

import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256
from pathlib import Path

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_patch_draft_limited_promotion_shadow import (
    SyntheticPatchDraftLimitedPromotionShadowBook,
)
from nurion_pg.synthetic_patch_draft_limited_promotion_shadow_review_docket import (
    MAXIMUM_LIMITED_PROMOTION_SHADOW_REVIEW_STATE,
    LimitedPromotionShadowReviewDecision,
    LimitedPromotionShadowReviewState,
    SyntheticPatchDraftLimitedPromotionShadowReviewDocket,
)
from tests.test_patch_draft_promotion_decision_intake import NOW
from tests.test_synthetic_patch_draft_limited_promotion_shadow import (
    close_all,
    observations_for,
    reviewed_source,
)


FINDINGS = sha256(
    b"synthetic limited promotion shadow independent findings"
).hexdigest()


def shadow_source(**observation_overrides):
    resources, source_docket, ledger, review, plan = reviewed_source()
    book = SyntheticPatchDraftLimitedPromotionShadowBook()
    assessment = book.evaluate(
        review,
        plan.plan_id,
        observations_for(plan, **observation_overrides),
        evaluated_at=NOW,
    )
    return (resources, source_docket, ledger, review), book, assessment


def close_resources(resources, docket=None):
    source_resources, source_docket, ledger, review = resources
    if docket is not None:
        docket.close()
    close_all(source_resources, source_docket, ledger, review)


def review_record(docket, record, decision, **overrides):
    values = {
        "review_id": (
            "synthetic:patch-draft-limited-promotion-shadow-review:"
            f"{decision.value.lower()}"
        ),
        "reviewer_id": (
            "synthetic:eternian-reviewer:patch-draft-limited-promotion-shadow:"
            f"{decision.value.lower()}"
        ),
        "decision": decision,
        "findings_digest": FINDINGS,
        "reviewed_at": NOW,
    }
    values.update(overrides)
    return docket.record_eternian_review(record.assessment.shadow_id, **values)


class SyntheticPatchDraftLimitedPromotionShadowReviewDocketTests(
    unittest.TestCase
):
    def test_pass_shadow_is_submitted_pending_without_authority(self):
        resources, book, assessment = shadow_source()
        docket = SyntheticPatchDraftLimitedPromotionShadowReviewDocket(
            ":memory:"
        )
        record = docket.submit_from_book(
            book, assessment.plan_id, submitted_at=NOW
        )
        self.assertEqual(
            record.state,
            LimitedPromotionShadowReviewState.PENDING_ETERNIAN_REVIEW,
        )
        self.assertEqual(
            record.assessment.assessment_digest,
            assessment.assessment_digest,
        )
        self.assertFalse(record.operator_reconfirmation_recorded)
        self.assertFalse(record.synthetic_activation_allowed)
        close_resources(resources, docket)

    def test_rollback_shadow_is_preserved_pending_review(self):
        resources, book, assessment = shadow_source(
            synthetic_regression_detected=True
        )
        docket = SyntheticPatchDraftLimitedPromotionShadowReviewDocket(
            ":memory:"
        )
        record = docket.submit_from_book(
            book, assessment.plan_id, submitted_at=NOW
        )
        self.assertEqual(
            record.state,
            LimitedPromotionShadowReviewState.PENDING_ETERNIAN_REVIEW,
        )
        self.assertEqual(
            record.assessment.decision.value,
            "ROLLBACK_REQUIRED",
        )
        close_resources(resources, docket)

    def test_pass_review_maps_shadow_result_to_safe_exact_state(self):
        for overrides, expected in (
            (
                {},
                LimitedPromotionShadowReviewState
                .READY_FOR_PATCH_DRAFT_LIMITED_PROMOTION_OPERATOR_RECONFIRMATION,
            ),
            (
                {"synthetic_regression_detected": True},
                LimitedPromotionShadowReviewState
                .ROLLBACK_REQUIRED_CONFIRMED,
            ),
        ):
            resources, book, assessment = shadow_source(**overrides)
            docket = SyntheticPatchDraftLimitedPromotionShadowReviewDocket(
                ":memory:"
            )
            record = docket.submit_from_book(
                book, assessment.plan_id, submitted_at=NOW
            )
            reviewed = review_record(
                docket, record, LimitedPromotionShadowReviewDecision.PASS
            )
            self.assertEqual(reviewed.state, expected)
            self.assertFalse(reviewed.operator_reconfirmation_recorded)
            close_resources(resources, docket)

    def test_hold_and_reject_never_create_ready_source(self):
        for decision, expected in (
            (
                LimitedPromotionShadowReviewDecision.HOLD,
                LimitedPromotionShadowReviewState.HELD,
            ),
            (
                LimitedPromotionShadowReviewDecision.REJECT,
                LimitedPromotionShadowReviewState.REJECTED,
            ),
        ):
            resources, book, assessment = shadow_source()
            docket = SyntheticPatchDraftLimitedPromotionShadowReviewDocket(
                ":memory:"
            )
            record = docket.submit_from_book(
                book, assessment.plan_id, submitted_at=NOW
            )
            reviewed = review_record(docket, record, decision)
            self.assertEqual(reviewed.state, expected)
            with self.assertRaises(GovernanceRejected):
                docket.ready_source(record.assessment.shadow_id)
            close_resources(resources, docket)

    def test_typed_chain_time_ids_and_database_targets_fail_closed(self):
        for target in (
            "shadow-review.sqlite3",
            "file:synthetic-review.sqlite3",
            "postgresql://prod/review",
        ):
            with self.assertRaises(GovernanceRejected):
                SyntheticPatchDraftLimitedPromotionShadowReviewDocket(target)
        resources, book, assessment = shadow_source()
        docket = SyntheticPatchDraftLimitedPromotionShadowReviewDocket(
            ":memory:"
        )
        with self.assertRaises(GovernanceRejected):
            docket.submit_from_book(
                object(), assessment.plan_id, submitted_at=NOW
            )
        for value in (NOW - timedelta(seconds=1), NOW.replace(tzinfo=None)):
            with self.assertRaises(GovernanceRejected):
                docket.submit_from_book(
                    book, assessment.plan_id, submitted_at=value
                )
        record = docket.submit_from_book(
            book, assessment.plan_id, submitted_at=NOW
        )
        base_decision = LimitedPromotionShadowReviewDecision.PASS
        for override in (
            {"review_id": "bad"},
            {"reviewer_id": "bad"},
            {"findings_digest": "bad"},
            {"reviewed_at": NOW - timedelta(seconds=1)},
            {"reviewed_at": NOW.replace(tzinfo=None)},
        ):
            with self.assertRaises(GovernanceRejected):
                review_record(
                    docket, record, base_decision, **override
                )
        close_resources(resources, docket)

    def test_submission_and_review_are_idempotent_but_collisions_fail(self):
        resources, book, assessment = shadow_source()
        docket = SyntheticPatchDraftLimitedPromotionShadowReviewDocket(
            ":memory:"
        )
        first = docket.submit_from_book(
            book, assessment.plan_id, submitted_at=NOW
        )
        self.assertEqual(
            first,
            docket.submit_from_book(
                book, assessment.plan_id, submitted_at=NOW
            ),
        )
        decision = LimitedPromotionShadowReviewDecision.PASS
        reviewed = review_record(docket, first, decision)
        self.assertEqual(reviewed, review_record(docket, first, decision))
        with self.assertRaises(GovernanceRejected):
            review_record(
                docket,
                first,
                decision,
                findings_digest=sha256(b"changed").hexdigest(),
            )
        close_resources(resources, docket)

    def test_concurrent_review_records_one_transition(self):
        resources, book, assessment = shadow_source()
        docket = SyntheticPatchDraftLimitedPromotionShadowReviewDocket(
            ":memory:"
        )
        record = docket.submit_from_book(
            book, assessment.plan_id, submitted_at=NOW
        )

        def review(_):
            return review_record(
                docket, record, LimitedPromotionShadowReviewDecision.PASS
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            records = list(pool.map(review, range(8)))
        self.assertTrue(all(item == records[0] for item in records))
        self.assertEqual(
            docket._connection.execute(
                "SELECT COUNT(*) FROM "
                "synthetic_limited_promotion_shadow_review_audit"
            ).fetchone()[0],
            2,
        )
        close_resources(resources, docket)

    def test_restart_preserves_review_and_integrity(self):
        resources, book, assessment = shadow_source()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic-limited-shadow-review.sqlite3"
            docket = SyntheticPatchDraftLimitedPromotionShadowReviewDocket(path)
            record = docket.submit_from_book(
                book, assessment.plan_id, submitted_at=NOW
            )
            expected = review_record(
                docket, record, LimitedPromotionShadowReviewDecision.PASS
            )
            report = docket.evidence()
            docket.close()
            reopened = (
                SyntheticPatchDraftLimitedPromotionShadowReviewDocket(path)
            )
            self.assertEqual(
                reopened.get(record.assessment.shadow_id), expected
            )
            self.assertEqual(reopened.evidence(), report)
            reopened.close()
        close_resources(resources)

    def test_audit_failure_rolls_back_submission_and_review(self):
        resources, book, assessment = shadow_source()
        docket = SyntheticPatchDraftLimitedPromotionShadowReviewDocket(
            ":memory:"
        )

        def fail(**_):
            raise sqlite3.IntegrityError("synthetic audit failure")

        docket._append_audit = fail
        with self.assertRaises(GovernanceRejected):
            docket.submit_from_book(
                book, assessment.plan_id, submitted_at=NOW
            )
        self.assertEqual(
            docket._connection.execute(
                "SELECT COUNT(*) FROM "
                "synthetic_limited_promotion_shadow_review_records"
            ).fetchone()[0],
            0,
        )
        close_resources(resources, docket)

        resources, book, assessment = shadow_source()
        docket = SyntheticPatchDraftLimitedPromotionShadowReviewDocket(
            ":memory:"
        )
        record = docket.submit_from_book(
            book, assessment.plan_id, submitted_at=NOW
        )
        docket._append_audit = fail
        with self.assertRaises(GovernanceRejected):
            review_record(
                docket, record, LimitedPromotionShadowReviewDecision.PASS
            )
        self.assertEqual(
            docket.get(record.assessment.shadow_id).state,
            LimitedPromotionShadowReviewState.PENDING_ETERNIAN_REVIEW,
        )
        close_resources(resources, docket)

    def test_tampering_blocks_get_ready_and_replay(self):
        resources, book, assessment = shadow_source()
        docket = SyntheticPatchDraftLimitedPromotionShadowReviewDocket(
            ":memory:"
        )
        record = docket.submit_from_book(
            book, assessment.plan_id, submitted_at=NOW
        )
        docket._connection.execute(
            "UPDATE synthetic_limited_promotion_shadow_review_records "
            "SET assessment_json = '{}' WHERE shadow_id = ?",
            (record.assessment.shadow_id,),
        )
        with self.assertRaises(GovernanceRejected):
            docket.get(record.assessment.shadow_id)
        self.assertFalse(docket.verify_record_bindings())
        close_resources(resources, docket)

    def test_ready_and_rollback_sources_are_separate_and_read_only(self):
        resources, book, assessment = shadow_source()
        docket = SyntheticPatchDraftLimitedPromotionShadowReviewDocket(
            ":memory:"
        )
        record = docket.submit_from_book(
            book, assessment.plan_id, submitted_at=NOW
        )
        with self.assertRaises(GovernanceRejected):
            docket.ready_source(record.assessment.shadow_id)
        review_record(
            docket, record, LimitedPromotionShadowReviewDecision.PASS
        )
        before = docket.evidence()["report_digest"]
        self.assertEqual(
            docket.ready_source(record.assessment.shadow_id).assessment,
            assessment,
        )
        self.assertEqual(before, docket.evidence()["report_digest"])
        with self.assertRaises(GovernanceRejected):
            docket.rollback_source(record.assessment.shadow_id)
        close_resources(resources, docket)

        resources, book, assessment = shadow_source(
            synthetic_regression_detected=True
        )
        docket = SyntheticPatchDraftLimitedPromotionShadowReviewDocket(
            ":memory:"
        )
        record = docket.submit_from_book(
            book, assessment.plan_id, submitted_at=NOW
        )
        review_record(
            docket, record, LimitedPromotionShadowReviewDecision.PASS
        )
        self.assertEqual(
            docket.rollback_source(record.assessment.shadow_id).assessment,
            assessment,
        )
        with self.assertRaises(GovernanceRejected):
            docket.ready_source(record.assessment.shadow_id)
        close_resources(resources, docket)

    def test_evidence_proves_non_authorizing_boundary(self):
        resources, book, assessment = shadow_source()
        docket = SyntheticPatchDraftLimitedPromotionShadowReviewDocket(
            ":memory:"
        )
        docket.submit_from_book(book, assessment.plan_id, submitted_at=NOW)
        evidence = docket.evidence()
        self.assertTrue(evidence["metadata_valid"])
        self.assertTrue(evidence["audit_chain_valid"])
        self.assertTrue(evidence["record_bindings_valid"])
        self.assertEqual(
            evidence["maximum_state"],
            MAXIMUM_LIMITED_PROMOTION_SHADOW_REVIEW_STATE,
        )
        for field in (
            "automatic_review_allowed",
            "operator_reconfirmation_method_present",
            "operator_reconfirmation_recorded",
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
        close_resources(resources, docket)


if __name__ == "__main__":
    unittest.main()
