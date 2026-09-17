"""Generate evidence for synthetic patch draft limited promotion shadow."""

from __future__ import annotations

import json
from hashlib import sha256

from nurion_pg.arkaon.governance import canonical_digest
from nurion_pg.synthetic_patch_draft_limited_promotion_review_docket import (
    LimitedPromotionPlanReviewDecision,
    SyntheticPatchDraftLimitedPromotionReviewDocket,
)
from nurion_pg.synthetic_patch_draft_limited_promotion_shadow import (
    MAXIMUM_LIMITED_PROMOTION_SHADOW_DECISION,
    LimitedPromotionShadowDecision,
    SyntheticPatchDraftLimitedPromotionObservation,
    SyntheticPatchDraftLimitedPromotionShadowAssessment,
    SyntheticPatchDraftLimitedPromotionShadowBook,
)
from run_operator_decision_intake_evidence import NOW, ROOT, read_json
from run_synthetic_patch_draft_limited_promotion_review_evidence import (
    main as build_limited_promotion_review_source,
)


def main() -> tuple[
    SyntheticPatchDraftLimitedPromotionShadowBook,
    SyntheticPatchDraftLimitedPromotionShadowAssessment,
]:
    policy = read_json(
        "config/patch-draft-limited-promotion-shadow-policy.json"
    )
    forbidden = (
        "candidate_content_allowed",
        "patch_content_allowed",
        "diff_content_allowed",
        "source_code_change_allowed",
        "filesystem_write_allowed",
        "automatic_application_allowed",
        "safety_baseline_relaxation_allowed",
        "execution_allowed",
        "synthetic_activation_allowed",
        "payment_execution_allowed",
        "money_movement_allowed",
        "production_activation_allowed",
        "network_access_allowed",
        "real_credentials_allowed",
        "real_personal_data_allowed",
    )
    if (
        policy["mode"] != "UNREGISTERED_SYNTHETIC_ONLY"
        or policy["required_input_state"]
        != "READY_FOR_SYNTHETIC_PATCH_DRAFT_LIMITED_PROMOTION_SHADOW"
        or policy["maximum_decision"]
        != MAXIMUM_LIMITED_PROMOTION_SHADOW_DECISION
        or policy["rollback_decision"] != "ROLLBACK_REQUIRED"
        or policy["synthetic_observation_only"] is not True
        or policy["exact_cohort_size_required"] is not True
        or policy["eternian_review_required"] is not True
        or tuple(policy["rollback_triggers"])
        != (
            "ANY_SAFETY_INVARIANT_FAILURE",
            "ANY_EVIDENCE_CHAIN_FAILURE",
            "ANY_SYNTHETIC_REGRESSION",
            "ANY_UNEXPECTED_SIDE_EFFECT",
        )
        or any(policy[field] is not False for field in forbidden)
    ):
        raise SystemExit("synthetic limited promotion shadow policy drift detected")

    plan_book, plan = build_limited_promotion_review_source()
    review = SyntheticPatchDraftLimitedPromotionReviewDocket(":memory:")
    review.submit_from_book(
        plan_book, plan.source_receipt_id, submitted_at=NOW
    )
    review.record_eternian_review(
        plan.plan_id,
        review_id=(
            "synthetic:patch-draft-limited-promotion-review:shadow-evidence"
        ),
        reviewer_id=(
            "synthetic:eternian-reviewer:patch-draft-limited-promotion:"
            "shadow-evidence"
        ),
        decision=LimitedPromotionPlanReviewDecision.PASS,
        findings_digest=sha256(
            b"synthetic limited promotion shadow review source"
        ).hexdigest(),
        reviewed_at=NOW,
    )
    source_before = review.evidence()["report_digest"]
    observations = []
    for ordinal in range(1, plan.synthetic_sample_size + 1):
        values = {
            "ordinal": ordinal,
            "observation_id": (
                "synthetic:patch-draft-limited-promotion-observation:"
                f"evidence-{ordinal}"
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
        observations.append(
            SyntheticPatchDraftLimitedPromotionObservation(
                **values,
                observation_digest=canonical_digest(values),
            )
        )
    book = SyntheticPatchDraftLimitedPromotionShadowBook()
    assessment = book.evaluate(
        review, plan.plan_id, tuple(observations), evaluated_at=NOW
    )
    source_after = review.evidence()["report_digest"]
    report = book.evidence()
    review.close()

    forbidden_report_fields = (
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
    )
    if (
        source_before != source_after
        or assessment.decision
        is not LimitedPromotionShadowDecision.PROPOSED_FOR_ETERNIAN_REVIEW
        or assessment.plan_id != plan.plan_id
        or len(assessment.item_results) != plan.synthetic_sample_size
        or report["assessment_chain_valid"] is not True
        or report["maximum_decision"]
        != MAXIMUM_LIMITED_PROMOTION_SHADOW_DECISION
        or any(report[field] is not False for field in forbidden_report_fields)
    ):
        raise SystemExit("synthetic limited promotion shadow boundary failed")

    output = (
        ROOT
        / "build/synthetic-patch-draft-limited-promotion-shadow-evidence.json"
    )
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode("utf-8")).hexdigest()
    output.with_suffix(".json.sha256").write_text(digest + "\n", encoding="ascii")
    print(f"synthetic patch draft limited promotion shadow: PASS {digest}")
    return book, assessment


if __name__ == "__main__":
    main()
