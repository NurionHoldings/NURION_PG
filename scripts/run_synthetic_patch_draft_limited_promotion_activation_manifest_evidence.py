"""Generate evidence for metadata-only activation preflight manifests."""

from __future__ import annotations

import json
from hashlib import sha256

from nurion_pg.patch_draft_limited_promotion_reconfirmation_receipt_ledger import (
    LIMITED_PROMOTION_RECONFIRMATION_RECEIPT_STATE,
    SyntheticPatchDraftLimitedPromotionReconfirmationReceiptLedger,
)
from nurion_pg.synthetic_patch_draft_limited_promotion_activation_manifests import (
    LIMITED_PROMOTION_ACTIVATION_MANIFEST_STATE,
    LIMITED_PROMOTION_ACTIVATION_SCOPE,
    REQUIRED_ACTIVATION_PREFLIGHT_CHECKS,
    SyntheticPatchDraftLimitedPromotionActivationManifest,
    SyntheticPatchDraftLimitedPromotionActivationManifestBook,
)
from nurion_pg.synthetic_patch_draft_limited_promotion_plans import (
    REQUIRED_ROLLBACK_TRIGGERS,
)
from run_operator_decision_intake_evidence import NOW, ROOT, read_json
from run_patch_draft_limited_promotion_operator_reconfirmation_packet_evidence import (
    main as build_reconfirmation_packet_source,
)
from run_patch_draft_limited_promotion_reconfirmation_intake_evidence import (
    main as build_validated_reconfirmation_intake,
)


def main() -> tuple[
    SyntheticPatchDraftLimitedPromotionActivationManifestBook,
    SyntheticPatchDraftLimitedPromotionActivationManifest,
]:
    policy = read_json(
        "config/patch-draft-limited-promotion-"
        "activation-manifest-policy.json"
    )
    forbidden = (
        "actual_operator_reconfirmation_recording_allowed",
        "candidate_content_allowed",
        "patch_content_allowed",
        "diff_content_allowed",
        "source_code_change_allowed",
        "filesystem_write_allowed",
        "activation_allowed",
        "rollback_execution_allowed",
        "safety_baseline_relaxation_allowed",
        "execution_allowed",
        "external_blocker_auto_close_allowed",
        "payment_execution_allowed",
        "money_movement_allowed",
        "automatic_merge_allowed",
        "automatic_deploy_allowed",
        "production_activation_allowed",
        "network_access_allowed",
        "real_credentials_allowed",
        "real_personal_data_allowed",
    )
    if (
        policy["mode"] != "UNREGISTERED_SYNTHETIC_ONLY"
        or policy["required_receipt_state"]
        != LIMITED_PROMOTION_RECONFIRMATION_RECEIPT_STATE
        or policy["required_decision"]
        != "RECONFIRM_SYNTHETIC_PATCH_DRAFT_LIMITED_PROMOTION"
        or policy["maximum_state"]
        != LIMITED_PROMOTION_ACTIVATION_MANIFEST_STATE
        or policy["activation_scope"]
        != LIMITED_PROMOTION_ACTIVATION_SCOPE
        or tuple(policy["rollback_triggers"])
        != REQUIRED_ROLLBACK_TRIGGERS
        or tuple(policy["required_checks"])
        != REQUIRED_ACTIVATION_PREFLIGHT_CHECKS
        or policy["metadata_only"] is not True
        or policy["eternian_final_review_required"] is not True
        or any(policy[field] is not False for field in forbidden)
    ):
        raise SystemExit("activation manifest policy drift detected")

    intake, envelope = build_validated_reconfirmation_intake()
    ledger = (
        SyntheticPatchDraftLimitedPromotionReconfirmationReceiptLedger(
            ":memory:"
        )
    )
    receipt = ledger.record_from_intake(
        intake, envelope.envelope_id, recorded_at=NOW
    )
    packet_book = build_reconfirmation_packet_source()
    ledger_before = ledger.evidence()["report_digest"]
    packet_before = packet_book.evidence()["report_digest"]
    book = SyntheticPatchDraftLimitedPromotionActivationManifestBook()
    manifest = book.draft_from_receipt(
        ledger,
        receipt.receipt_id,
        packet_book,
        drafted_at=NOW,
    )
    ledger_after = ledger.evidence()["report_digest"]
    packet_after = packet_book.evidence()["report_digest"]
    report = book.evidence()
    ledger.close()

    forbidden_report_fields = (
        "actual_operator_reconfirmation_recorded",
        "candidate_content_present",
        "patch_content_present",
        "diff_content_present",
        "source_code_changed",
        "filesystem_written",
        "activation_method_present",
        "rollback_execution_method_present",
        "safety_baseline_relaxation_allowed",
        "execution_method_present",
        "network_access_method_present",
        "external_blocker_close_method_present",
        "automatic_merge_method_present",
        "automatic_deploy_method_present",
        "personal_data_used",
        "credentials_used",
        "money_movement_executed",
        "production_activation_allowed",
    )
    if (
        ledger_before != ledger_after
        or packet_before != packet_after
        or manifest.source_receipt_id != receipt.receipt_id
        or manifest.source_packet_id != receipt.packet_id
        or manifest.shadow_id != receipt.shadow_id
        or manifest.state != LIMITED_PROMOTION_ACTIVATION_MANIFEST_STATE
        or manifest.activation_scope != LIMITED_PROMOTION_ACTIVATION_SCOPE
        or manifest.rollback_triggers != REQUIRED_ROLLBACK_TRIGGERS
        or manifest.required_checks != REQUIRED_ACTIVATION_PREFLIGHT_CHECKS
        or report["manifest_chain_valid"] is not True
        or report["synthetic_only"] is not True
        or report["eternian_final_review_required"] is not True
        or report["validated_reconfirmation_receipt_only"] is not True
        or report["maximum_state"]
        != LIMITED_PROMOTION_ACTIVATION_MANIFEST_STATE
        or any(report[field] is not False for field in forbidden_report_fields)
    ):
        raise SystemExit("activation manifest evidence boundary failed")

    output = (
        ROOT
        / "build/synthetic-patch-draft-limited-promotion-"
        "activation-manifest-evidence.json"
    )
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode("utf-8")).hexdigest()
    output.with_suffix(".json.sha256").write_text(
        digest + "\n", encoding="ascii"
    )
    print(
        "synthetic patch draft limited promotion activation manifest: "
        f"PASS {digest}"
    )
    return book, manifest


if __name__ == "__main__":
    main()
