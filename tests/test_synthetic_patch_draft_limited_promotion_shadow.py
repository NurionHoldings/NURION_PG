from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.synthetic_patch_draft_limited_promotion_review_docket import (
    LimitedPromotionPlanReviewDecision,
    SyntheticPatchDraftLimitedPromotionReviewDocket,
)
from nurion_pg.synthetic_patch_draft_limited_promotion_shadow import (
    MAXIMUM_LIMITED_PROMOTION_SHADOW_DECISION,
    LimitedPromotionShadowDecision,
    LimitedPromotionShadowItemDecision,
    SyntheticPatchDraftLimitedPromotionObservation,
    SyntheticPatchDraftLimitedPromotionShadowBook,
)
from tests.test_patch_draft_promotion_decision_intake import NOW
from tests.test_synthetic_patch_draft_limited_promotion_review_docket import (
    FINDINGS,
    close_source,
    plan_source,
)


def reviewed_source(
    decision: LimitedPromotionPlanReviewDecision = (
        LimitedPromotionPlanReviewDecision.PASS
    ),
):
    resources, source_docket, ledger, book, plan = plan_source()
    review = SyntheticPatchDraftLimitedPromotionReviewDocket(":memory:")
    review.submit_from_book(book, plan.source_receipt_id, submitted_at=NOW)
    review.record_eternian_review(
        plan.plan_id,
        review_id=(
            "synthetic:patch-draft-limited-promotion-review:shadow-"
            f"{decision.value.lower()}"
        ),
        reviewer_id=(
            "synthetic:eternian-reviewer:patch-draft-limited-promotion:shadow-"
            f"{decision.value.lower()}"
        ),
        decision=decision,
        findings_digest=FINDINGS,
        reviewed_at=NOW,
    )
    return resources, source_docket, ledger, review, plan


def observation_for(plan, ordinal, **overrides):
    values = {
        "ordinal": ordinal,
        "observation_id": (
            "synthetic:patch-draft-limited-promotion-observation:"
            f"test-{ordinal}"
        ),
        "plan_id": plan.plan_id,
        "plan_digest": plan.plan_digest,
        "candidate_digest": plan.candidate_digest,
        "cohort_digest": plan.cohort_digest,
        "synthetic_input_only": True,
        "plan_binding_verified": True,
        "candidate_binding_verified": True,
        "cohort_binding_verified": True,
        "safety_invariants_passed": True,
        "evidence_chain_passed": True,
        "synthetic_regression_detected": False,
        "unexpected_side_effect_detected": False,
        "rollback_trigger_evaluated": True,
        "candidate_content_present": False,
        "patch_content_present": False,
        "diff_content_present": False,
        "source_code_changed": False,
        "filesystem_written": False,
        "network_access_used": False,
        "production_access_used": False,
        "credentials_used": False,
        "personal_data_used": False,
        "money_movement_executed": False,
    }
    values.update(overrides)
    return SyntheticPatchDraftLimitedPromotionObservation(
        **values,
        observation_digest=canonical_digest(values),
    )


def observations_for(plan, **first_overrides):
    return tuple(
        observation_for(
            plan,
            ordinal,
            **(first_overrides if ordinal == 1 else {}),
        )
        for ordinal in range(1, plan.synthetic_sample_size + 1)
    )


def close_all(resources, source_docket, ledger, review):
    review.close()
    close_source(resources, source_docket, ledger)


class SyntheticPatchDraftLimitedPromotionShadowTests(unittest.TestCase):
    def test_passed_observations_create_review_candidate_without_activation(self):
        resources, source_docket, ledger, review, plan = reviewed_source()
        before = review.evidence()["report_digest"]
        assessment = SyntheticPatchDraftLimitedPromotionShadowBook().evaluate(
            review, plan.plan_id, observations_for(plan), evaluated_at=NOW
        )
        self.assertEqual(before, review.evidence()["report_digest"])
        self.assertEqual(
            assessment.decision,
            LimitedPromotionShadowDecision.PROPOSED_FOR_ETERNIAN_REVIEW,
        )
        self.assertTrue(
            all(
                item.decision is LimitedPromotionShadowItemDecision.PASS
                for item in assessment.item_results
            )
        )
        self.assertFalse(assessment.synthetic_activation_allowed)
        self.assertFalse(assessment.production_activation_allowed)
        close_all(resources, source_docket, ledger, review)

    def test_each_required_trigger_requires_rollback(self):
        cases = (
            {"safety_invariants_passed": False},
            {"evidence_chain_passed": False},
            {"synthetic_regression_detected": True},
            {"unexpected_side_effect_detected": True},
        )
        for override in cases:
            resources, source_docket, ledger, review, plan = reviewed_source()
            assessment = SyntheticPatchDraftLimitedPromotionShadowBook().evaluate(
                review,
                plan.plan_id,
                observations_for(plan, **override),
                evaluated_at=NOW,
            )
            self.assertEqual(
                assessment.decision,
                LimitedPromotionShadowDecision.ROLLBACK_REQUIRED,
            )
            self.assertEqual(
                assessment.item_results[0].decision,
                LimitedPromotionShadowItemDecision.ROLLBACK_REQUIRED,
            )
            close_all(resources, source_docket, ledger, review)

    def test_forbidden_side_effects_require_rollback(self):
        for field in (
            "synthetic_input_only",
            "plan_binding_verified",
            "candidate_binding_verified",
            "cohort_binding_verified",
            "rollback_trigger_evaluated",
            "candidate_content_present",
            "patch_content_present",
            "diff_content_present",
            "source_code_changed",
            "filesystem_written",
            "network_access_used",
            "production_access_used",
            "credentials_used",
            "personal_data_used",
            "money_movement_executed",
        ):
            resources, source_docket, ledger, review, plan = reviewed_source()
            false_fields = {
                "synthetic_input_only",
                "plan_binding_verified",
                "candidate_binding_verified",
                "cohort_binding_verified",
                "rollback_trigger_evaluated",
            }
            value = False if field in false_fields else True
            assessment = SyntheticPatchDraftLimitedPromotionShadowBook().evaluate(
                review,
                plan.plan_id,
                observations_for(plan, **{field: value}),
                evaluated_at=NOW,
            )
            self.assertEqual(
                assessment.decision,
                LimitedPromotionShadowDecision.ROLLBACK_REQUIRED,
            )
            close_all(resources, source_docket, ledger, review)

    def test_nonpass_review_and_invalid_time_are_blocked(self):
        for decision in (
            LimitedPromotionPlanReviewDecision.HOLD,
            LimitedPromotionPlanReviewDecision.REJECT,
        ):
            resources, source_docket, ledger, review, plan = reviewed_source(
                decision
            )
            with self.assertRaises(GovernanceRejected):
                SyntheticPatchDraftLimitedPromotionShadowBook().evaluate(
                    review,
                    plan.plan_id,
                    observations_for(plan),
                    evaluated_at=NOW,
                )
            close_all(resources, source_docket, ledger, review)
        resources, source_docket, ledger, review, plan = reviewed_source()
        for value in (NOW - timedelta(seconds=1), NOW.replace(tzinfo=None)):
            with self.assertRaises(GovernanceRejected):
                SyntheticPatchDraftLimitedPromotionShadowBook().evaluate(
                    review,
                    plan.plan_id,
                    observations_for(plan),
                    evaluated_at=value,
                )
        close_all(resources, source_docket, ledger, review)

    def test_requires_typed_docket_and_exact_observation_count(self):
        resources, source_docket, ledger, review, plan = reviewed_source()
        book = SyntheticPatchDraftLimitedPromotionShadowBook()
        with self.assertRaises(GovernanceRejected):
            book.evaluate(
                object(), plan.plan_id, observations_for(plan), evaluated_at=NOW
            )
        with self.assertRaises(GovernanceRejected):
            book.evaluate(review, plan.plan_id, (), evaluated_at=NOW)
        with self.assertRaises(GovernanceRejected):
            book.evaluate(
                review,
                plan.plan_id,
                observations_for(plan)[:-1],
                evaluated_at=NOW,
            )
        close_all(resources, source_docket, ledger, review)

    def test_order_uniqueness_and_plan_bindings_are_strict(self):
        resources, source_docket, ledger, review, plan = reviewed_source()
        book = SyntheticPatchDraftLimitedPromotionShadowBook()
        observations = observations_for(plan)
        invalid_sets = (
            tuple(reversed(observations)),
            (observations[0], observations[0], *observations[2:]),
            observations_for(plan, plan_digest="f" * 64),
            observations_for(plan, candidate_digest="f" * 64),
            observations_for(plan, cohort_digest="f" * 64),
        )
        for values in invalid_sets:
            with self.assertRaises(GovernanceRejected):
                book.evaluate(review, plan.plan_id, values, evaluated_at=NOW)
        close_all(resources, source_docket, ledger, review)

    def test_concurrent_replay_is_idempotent_and_collision_blocked(self):
        resources, source_docket, ledger, review, plan = reviewed_source()
        book = SyntheticPatchDraftLimitedPromotionShadowBook()
        observations = observations_for(plan)

        def evaluate(_):
            return book.evaluate(
                review, plan.plan_id, observations, evaluated_at=NOW
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            assessments = list(pool.map(evaluate, range(8)))
        self.assertTrue(all(item == assessments[0] for item in assessments))
        with self.assertRaises(GovernanceRejected):
            book.evaluate(
                review,
                plan.plan_id,
                observations_for(plan, synthetic_regression_detected=True),
                evaluated_at=NOW,
            )
        self.assertEqual(len(book.assessments), 1)
        close_all(resources, source_docket, ledger, review)

    def test_observation_and_assessment_tampering_fail_closed(self):
        resources, source_docket, ledger, review, plan = reviewed_source()
        observations = observations_for(plan)
        object.__setattr__(observations[0], "observation_digest", "f" * 64)
        with self.assertRaises(GovernanceRejected):
            SyntheticPatchDraftLimitedPromotionShadowBook().evaluate(
                review, plan.plan_id, observations, evaluated_at=NOW
            )
        book = SyntheticPatchDraftLimitedPromotionShadowBook()
        assessment = book.evaluate(
            review, plan.plan_id, observations_for(plan), evaluated_at=NOW
        )
        object.__setattr__(assessment, "synthetic_activation_allowed", True)
        self.assertFalse(book.verify_assessment_chain())
        close_all(resources, source_docket, ledger, review)

    def test_rehashed_shadow_identity_tamper_breaks_chain(self):
        resources, source_docket, ledger, review, plan = reviewed_source()
        book = SyntheticPatchDraftLimitedPromotionShadowBook()
        assessment = book.evaluate(
            review, plan.plan_id, observations_for(plan), evaluated_at=NOW
        )
        object.__setattr__(
            assessment,
            "shadow_id",
            "synthetic:patch-draft-limited-promotion-shadow:tampered",
        )
        object.__setattr__(
            assessment,
            "assessment_digest",
            canonical_digest(assessment.digest_value()),
        )
        self.assertFalse(book.verify_assessment_chain())
        close_all(resources, source_docket, ledger, review)

    def test_rehashed_item_decision_tamper_breaks_chain(self):
        resources, source_docket, ledger, review, plan = reviewed_source()
        book = SyntheticPatchDraftLimitedPromotionShadowBook()
        assessment = book.evaluate(
            review, plan.plan_id, observations_for(plan), evaluated_at=NOW
        )
        item = assessment.item_results[0]
        object.__setattr__(
            item,
            "decision",
            LimitedPromotionShadowItemDecision.ROLLBACK_REQUIRED,
        )
        object.__setattr__(
            item,
            "triggered_rollback_conditions",
            ("ANY_SYNTHETIC_REGRESSION",),
        )
        object.__setattr__(
            item,
            "reason",
            "limited_promotion_rollback_triggered",
        )
        object.__setattr__(
            item,
            "result_digest",
            canonical_digest(item.digest_value()),
        )
        object.__setattr__(
            assessment,
            "assessment_digest",
            canonical_digest(assessment.digest_value()),
        )
        self.assertFalse(book.verify_assessment_chain())
        close_all(resources, source_docket, ledger, review)

    def test_evidence_proves_no_activation_or_execution(self):
        resources, source_docket, ledger, review, plan = reviewed_source()
        book = SyntheticPatchDraftLimitedPromotionShadowBook()
        book.evaluate(
            review, plan.plan_id, observations_for(plan), evaluated_at=NOW
        )
        evidence = book.evidence()
        self.assertTrue(evidence["assessment_chain_valid"])
        self.assertEqual(
            evidence["maximum_decision"],
            MAXIMUM_LIMITED_PROMOTION_SHADOW_DECISION,
        )
        for field in (
            "source_docket_state_changed",
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
        close_all(resources, source_docket, ledger, review)


if __name__ == "__main__":
    unittest.main()
