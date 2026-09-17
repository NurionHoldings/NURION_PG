"""Generate evidence for durable limited promotion shadow review."""

from __future__ import annotations

import json
import tempfile
from hashlib import sha256
from pathlib import Path

from nurion_pg.synthetic_patch_draft_limited_promotion_shadow_review_docket import (
    MAXIMUM_LIMITED_PROMOTION_SHADOW_REVIEW_STATE,
    LimitedPromotionShadowReviewDecision,
    LimitedPromotionShadowReviewState,
    SyntheticPatchDraftLimitedPromotionShadowReviewDocket,
)
from run_operator_decision_intake_evidence import NOW, ROOT, read_json
from run_synthetic_patch_draft_limited_promotion_shadow_evidence import (
    main as build_limited_promotion_shadow_source,
)


def main() -> tuple[
    SyntheticPatchDraftLimitedPromotionShadowReviewDocket,
    str,
]:
    policy = read_json(
        "config/patch-draft-limited-promotion-shadow-review-policy.json"
    )
    forbidden = (
        "automatic_review_allowed",
        "operator_reconfirmation_recording_allowed",
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
        or tuple(policy["allowed_shadow_decisions"])
        != ("PROPOSED_FOR_ETERNIAN_REVIEW", "ROLLBACK_REQUIRED")
        or policy["review_authority"] != "ETERNIAN_INDEPENDENT_REVIEW"
        or tuple(policy["allowed_review_decisions"])
        != ("PASS", "HOLD", "REJECT")
        or policy["pass_state_for_clear_shadow"]
        != MAXIMUM_LIMITED_PROMOTION_SHADOW_REVIEW_STATE
        or policy["pass_state_for_rollback_shadow"]
        != "ROLLBACK_REQUIRED_CONFIRMED"
        or policy["maximum_state"]
        != MAXIMUM_LIMITED_PROMOTION_SHADOW_REVIEW_STATE
        or policy["synthetic_sqlite_only"] is not True
        or policy["append_only_audit_required"] is not True
        or policy["source_assessment_preservation_required"] is not True
        or any(policy[field] is not False for field in forbidden)
    ):
        raise SystemExit("limited promotion shadow review policy drift detected")

    book, assessment = build_limited_promotion_shadow_source()
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "synthetic-limited-shadow-reviews.sqlite3"
        docket = SyntheticPatchDraftLimitedPromotionShadowReviewDocket(path)
        pending = docket.submit_from_book(
            book, assessment.plan_id, submitted_at=NOW
        )
        reviewed = docket.record_eternian_review(
            assessment.shadow_id,
            review_id=(
                "synthetic:patch-draft-limited-promotion-shadow-review:evidence"
            ),
            reviewer_id=(
                "synthetic:eternian-reviewer:"
                "patch-draft-limited-promotion-shadow:evidence"
            ),
            decision=LimitedPromotionShadowReviewDecision.PASS,
            findings_digest=sha256(
                b"independent limited promotion shadow review evidence"
            ).hexdigest(),
            reviewed_at=NOW,
        )
        before = docket.evidence()
        ready = docket.ready_source(assessment.shadow_id)
        docket.close()
        reopened = SyntheticPatchDraftLimitedPromotionShadowReviewDocket(path)
        after = reopened.evidence()
        persisted = reopened.get(assessment.shadow_id)

    forbidden_report_fields = (
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
    )
    if (
        pending.state
        is not LimitedPromotionShadowReviewState.PENDING_ETERNIAN_REVIEW
        or reviewed.state
        is not LimitedPromotionShadowReviewState.READY_FOR_PATCH_DRAFT_LIMITED_PROMOTION_OPERATOR_RECONFIRMATION
        or before != after
        or persisted != reviewed
        or ready.assessment.assessment_digest != assessment.assessment_digest
        or after["metadata_valid"] is not True
        or after["audit_chain_valid"] is not True
        or after["record_bindings_valid"] is not True
        or after["maximum_state"]
        != MAXIMUM_LIMITED_PROMOTION_SHADOW_REVIEW_STATE
        or any(after[field] is not False for field in forbidden_report_fields)
    ):
        raise SystemExit("limited promotion shadow review boundary failed")

    output = (
        ROOT
        / "build/synthetic-patch-draft-limited-promotion-shadow-review-evidence.json"
    )
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(after, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode("utf-8")).hexdigest()
    output.with_suffix(".json.sha256").write_text(digest + "\n", encoding="ascii")
    print(f"synthetic patch draft limited promotion shadow review: PASS {digest}")
    return reopened, assessment.shadow_id


if __name__ == "__main__":
    review_docket, _ = main()
    review_docket.close()
