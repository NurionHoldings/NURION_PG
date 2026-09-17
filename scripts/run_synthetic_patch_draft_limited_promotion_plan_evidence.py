"""Generate evidence for metadata-only synthetic limited promotion plans."""

from __future__ import annotations

import json
from hashlib import sha256

from nurion_pg.patch_draft_promotion_receipt_ledger import (
    SyntheticPatchDraftPromotionDecisionReceiptLedger,
)
from nurion_pg.synthetic_patch_draft_limited_promotion_plans import (
    MAX_OBSERVATION_WINDOW_SECONDS,
    MAX_SYNTHETIC_SAMPLE_SIZE,
    MIN_OBSERVATION_WINDOW_SECONDS,
    MIN_SYNTHETIC_SAMPLE_SIZE,
    PATCH_DRAFT_LIMITED_PROMOTION_PLAN_STATE,
    PATCH_DRAFT_LIMITED_PROMOTION_SCOPE,
    REQUIRED_LIMITED_PROMOTION_CHECKS,
    REQUIRED_ROLLBACK_TRIGGERS,
    SyntheticPatchDraftLimitedPromotionPlan,
    SyntheticPatchDraftLimitedPromotionPlanBook,
)
from run_operator_decision_intake_evidence import NOW, ROOT, read_json
from run_patch_draft_promotion_receipt_ledger_evidence import (
    main as build_receiptable_promotion_intake,
)


CANDIDATE_DIGEST = sha256(b"synthetic-limited-promotion-candidate").hexdigest()
COHORT_DIGEST = sha256(b"synthetic-fixture-cohort").hexdigest()


def main() -> tuple[
    SyntheticPatchDraftLimitedPromotionPlanBook,
    SyntheticPatchDraftLimitedPromotionPlan,
]:
    policy = read_json("config/patch-draft-limited-promotion-plan-policy.json")
    forbidden = (
        "candidate_content_allowed",
        "patch_content_allowed",
        "diff_content_allowed",
        "source_code_change_allowed",
        "filesystem_write_allowed",
        "automatic_application_allowed",
        "safety_baseline_relaxation_allowed",
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
        != "SYNTHETIC_PATCH_DRAFT_PROMOTION_DECISION_RECEIPT_RECORDED"
        or policy["required_decision"]
        != "AUTHORIZE_SYNTHETIC_PATCH_DRAFT_LIMITED_PROMOTION"
        or policy["maximum_state"] != PATCH_DRAFT_LIMITED_PROMOTION_PLAN_STATE
        or policy["promotion_scope"] != PATCH_DRAFT_LIMITED_PROMOTION_SCOPE
        or policy["minimum_synthetic_sample_size"]
        != MIN_SYNTHETIC_SAMPLE_SIZE
        or policy["maximum_synthetic_sample_size"]
        != MAX_SYNTHETIC_SAMPLE_SIZE
        or policy["minimum_observation_window_seconds"]
        != MIN_OBSERVATION_WINDOW_SECONDS
        or policy["maximum_observation_window_seconds"]
        != MAX_OBSERVATION_WINDOW_SECONDS
        or tuple(policy["rollback_triggers"]) != REQUIRED_ROLLBACK_TRIGGERS
        or tuple(policy["required_checks"])
        != REQUIRED_LIMITED_PROMOTION_CHECKS
        or policy["metadata_only"] is not True
        or policy["rollback_required"] is not True
        or policy["eternian_review_required"] is not True
        or policy["operator_reconfirmation_required"] is not True
        or any(policy[field] is not False for field in forbidden)
    ):
        raise SystemExit("synthetic limited promotion plan policy drift detected")

    intake, envelope = build_receiptable_promotion_intake()
    ledger = SyntheticPatchDraftPromotionDecisionReceiptLedger(":memory:")
    receipt = ledger.record_from_intake(
        intake, envelope.envelope_id, recorded_at=NOW
    )
    source_before = ledger.evidence()["report_digest"]
    book = SyntheticPatchDraftLimitedPromotionPlanBook()
    plan = book.draft_from_receipt(
        ledger,
        receipt.receipt_id,
        candidate_digest=CANDIDATE_DIGEST,
        cohort_digest=COHORT_DIGEST,
        synthetic_sample_size=10,
        observation_window_seconds=600,
        rollback_triggers=REQUIRED_ROLLBACK_TRIGGERS,
        drafted_at=NOW,
    )
    source_after = ledger.evidence()["report_digest"]
    report = book.evidence()
    ledger.close()

    forbidden_report_fields = (
        "candidate_content_present",
        "patch_content_present",
        "diff_content_present",
        "source_code_changed",
        "filesystem_written",
        "application_method_present",
        "safety_baseline_relaxation_allowed",
        "execution_method_present",
        "network_access_method_present",
        "personal_data_used",
        "credentials_used",
        "money_movement_executed",
        "production_activation_allowed",
    )
    if (
        source_before != source_after
        or plan.source_receipt_id != receipt.receipt_id
        or plan.state != PATCH_DRAFT_LIMITED_PROMOTION_PLAN_STATE
        or plan.promotion_scope != PATCH_DRAFT_LIMITED_PROMOTION_SCOPE
        or plan.rollback_triggers != REQUIRED_ROLLBACK_TRIGGERS
        or plan.required_checks != REQUIRED_LIMITED_PROMOTION_CHECKS
        or report["plan_chain_valid"] is not True
        or report["synthetic_only"] is not True
        or report["rollback_required"] is not True
        or report["eternian_review_required"] is not True
        or report["operator_reconfirmation_required"] is not True
        or report["maximum_state"] != PATCH_DRAFT_LIMITED_PROMOTION_PLAN_STATE
        or any(report[field] is not False for field in forbidden_report_fields)
    ):
        raise SystemExit("synthetic limited promotion plan boundary failed")

    output = ROOT / "build/synthetic-patch-draft-limited-promotion-plan-evidence.json"
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode("utf-8")).hexdigest()
    output.with_suffix(".json.sha256").write_text(digest + "\n", encoding="ascii")
    print(f"synthetic patch draft limited promotion plan: PASS {digest}")
    return book, plan


if __name__ == "__main__":
    main()
