"""Generate evidence for the synthetic limited promotion plan review docket."""

from __future__ import annotations

import json
import tempfile
from hashlib import sha256
from pathlib import Path

from nurion_pg.synthetic_patch_draft_limited_promotion_plans import (
    SyntheticPatchDraftLimitedPromotionPlan,
    SyntheticPatchDraftLimitedPromotionPlanBook,
)
from nurion_pg.synthetic_patch_draft_limited_promotion_review_docket import (
    MAXIMUM_LIMITED_PROMOTION_REVIEW_STATE,
    LimitedPromotionPlanReviewDecision,
    LimitedPromotionPlanReviewState,
    SyntheticPatchDraftLimitedPromotionReviewDocket,
)
from run_operator_decision_intake_evidence import NOW, ROOT, read_json
from run_synthetic_patch_draft_limited_promotion_plan_evidence import (
    main as build_limited_promotion_plan,
)


def main() -> tuple[
    SyntheticPatchDraftLimitedPromotionPlanBook,
    SyntheticPatchDraftLimitedPromotionPlan,
]:
    policy = read_json(
        "config/patch-draft-limited-promotion-review-policy.json"
    )
    forbidden = (
        "automatic_review_allowed",
        "operator_decision_recording_allowed",
        "candidate_content_allowed",
        "patch_content_allowed",
        "diff_content_allowed",
        "source_code_change_allowed",
        "filesystem_write_allowed",
        "automatic_application_allowed",
        "safety_baseline_relaxation_allowed",
        "payment_execution_allowed",
        "money_movement_allowed",
        "synthetic_activation_allowed",
        "production_activation_allowed",
        "network_access_allowed",
        "real_credentials_allowed",
        "real_personal_data_allowed",
    )
    if (
        policy["mode"] != "UNREGISTERED_SYNTHETIC_ONLY"
        or policy["required_input_state"]
        != "SYNTHETIC_PATCH_DRAFT_LIMITED_PROMOTION_PLAN_DRAFTED"
        or tuple(policy["allowed_review_decisions"])
        != ("PASS", "HOLD", "REJECT")
        or policy["pass_state"] != MAXIMUM_LIMITED_PROMOTION_REVIEW_STATE
        or policy["maximum_state"] != MAXIMUM_LIMITED_PROMOTION_REVIEW_STATE
        or policy["database_engine"] != "SQLite"
        or policy["eternian_review_required"] is not True
        or policy["append_only_audit_required"] is not True
        or policy["source_plan_preservation_required"] is not True
        or policy["operator_reconfirmation_required"] is not True
        or any(policy[field] is not False for field in forbidden)
    ):
        raise SystemExit("synthetic limited promotion review policy drift detected")

    book, plan = build_limited_promotion_plan()
    source_before = book.evidence()["report_digest"]
    findings = sha256(
        b"synthetic limited promotion plan review evidence"
    ).hexdigest()
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "synthetic-limited-promotion-reviews.sqlite3"
        docket = SyntheticPatchDraftLimitedPromotionReviewDocket(database)
        pending = docket.submit_from_book(
            book, plan.source_receipt_id, submitted_at=NOW
        )
        reviewed = docket.record_eternian_review(
            plan.plan_id,
            review_id=(
                "synthetic:patch-draft-limited-promotion-review:evidence"
            ),
            reviewer_id=(
                "synthetic:eternian-reviewer:patch-draft-limited-promotion:"
                "evidence"
            ),
            decision=LimitedPromotionPlanReviewDecision.PASS,
            findings_digest=findings,
            reviewed_at=NOW,
        )
        first_report = docket.evidence()
        docket.close()
        reopened = SyntheticPatchDraftLimitedPromotionReviewDocket(database)
        persisted = reopened.get(plan.plan_id)
        ready = reopened.ready_source(plan.plan_id)
        report = reopened.evidence()
        reopened.close()
    source_after = book.evidence()["report_digest"]

    forbidden_report_fields = (
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
    )
    if (
        source_before != source_after
        or pending.state
        is not LimitedPromotionPlanReviewState.PENDING_ETERNIAN_REVIEW
        or reviewed.state
        is not LimitedPromotionPlanReviewState.READY_FOR_SYNTHETIC_PATCH_DRAFT_LIMITED_PROMOTION_SHADOW
        or persisted != reviewed
        or ready != reviewed
        or first_report != report
        or report["metadata_valid"] is not True
        or report["audit_chain_valid"] is not True
        or report["record_bindings_valid"] is not True
        or report["maximum_state"] != MAXIMUM_LIMITED_PROMOTION_REVIEW_STATE
        or any(report[field] is not False for field in forbidden_report_fields)
    ):
        raise SystemExit("synthetic limited promotion review boundary failed")

    output = (
        ROOT
        / "build/synthetic-patch-draft-limited-promotion-review-evidence.json"
    )
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode("utf-8")).hexdigest()
    output.with_suffix(".json.sha256").write_text(digest + "\n", encoding="ascii")
    print(f"synthetic patch draft limited promotion review: PASS {digest}")
    return book, plan


if __name__ == "__main__":
    main()
