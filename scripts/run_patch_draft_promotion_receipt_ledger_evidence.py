"""Generate evidence for the patch draft promotion intent receipt ledger."""

from __future__ import annotations

import json
import tempfile
from hashlib import sha256
from pathlib import Path

from nurion_pg.patch_draft_promotion_decision_intake import (
    PATCH_DRAFT_PROMOTION_VALIDATION_STATE,
    SyntheticPatchDraftPromotionDecisionEnvelope,
    SyntheticPatchDraftPromotionDecisionIntake,
)
from nurion_pg.patch_draft_promotion_receipt_ledger import (
    PATCH_DRAFT_PROMOTION_RECEIPT_STATE,
    SyntheticPatchDraftPromotionDecisionReceiptLedger,
)
from run_operator_decision_intake_evidence import NOW, ROOT, read_json
from run_patch_draft_promotion_decision_intake_evidence import (
    main as build_validated_promotion_intake,
)


def main() -> tuple[
    SyntheticPatchDraftPromotionDecisionIntake,
    SyntheticPatchDraftPromotionDecisionEnvelope,
]:
    policy = read_json("config/patch-draft-promotion-receipt-ledger-policy.json")
    forbidden = (
        "actual_operator_decision_recording_allowed", "packet_state_change_allowed",
        "patch_content_allowed", "diff_content_allowed",
        "source_code_change_allowed", "filesystem_write_allowed",
        "automatic_application_allowed", "safety_baseline_relaxation_allowed",
        "payment_execution_allowed", "money_movement_allowed",
        "production_activation_allowed", "network_access_allowed",
        "real_credentials_allowed", "real_personal_data_allowed",
    )
    if (
        policy["mode"] != "UNREGISTERED_SYNTHETIC_ONLY"
        or policy["required_input_state"] != PATCH_DRAFT_PROMOTION_VALIDATION_STATE
        or policy["maximum_state"] != PATCH_DRAFT_PROMOTION_RECEIPT_STATE
        or policy["database_engine"] != "SQLite"
        or policy["synthetic_evidence_only"] is not True
        or any(policy[field] is not False for field in forbidden)
    ):
        raise SystemExit("patch draft promotion receipt policy drift detected")

    intake, envelope = build_validated_promotion_intake()
    source_before = intake.evidence()["report_digest"]
    assessment = next(
        item for item in intake.assessments if item.envelope_id == envelope.envelope_id
    )
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "synthetic-patch-draft-promotion-receipts.sqlite3"
        ledger = SyntheticPatchDraftPromotionDecisionReceiptLedger(path)
        receipt = ledger.record_from_intake(
            intake, envelope.envelope_id, recorded_at=NOW
        )
        first_report = ledger.evidence()
        ledger.close()
        reopened = SyntheticPatchDraftPromotionDecisionReceiptLedger(path)
        persisted = reopened.get(receipt.receipt_id)
        report = reopened.evidence()
        reopened.close()

    source_after = intake.evidence()["report_digest"]
    forbidden_report_fields = (
        "actual_operator_decision_recording_method_present",
        "packet_state_change_method_present", "patch_content_present",
        "diff_content_present", "source_code_change_method_present",
        "filesystem_write_method_present", "application_method_present",
        "safety_baseline_relaxation_method_present", "execution_method_present",
        "network_access_method_present", "personal_data_used", "credentials_used",
        "money_movement_executed", "production_activation_allowed",
    )
    if (
        source_before != source_after
        or persisted != receipt
        or receipt.assessment_digest != assessment.assessment_digest
        or receipt.state != PATCH_DRAFT_PROMOTION_RECEIPT_STATE
        or first_report != report
        or report["metadata_valid"] is not True
        or report["audit_chain_valid"] is not True
        or report["record_bindings_valid"] is not True
        or report["synthetic_evidence_only"] is not True
        or report["maximum_state"] != PATCH_DRAFT_PROMOTION_RECEIPT_STATE
        or any(report[field] is not False for field in forbidden_report_fields)
    ):
        raise SystemExit("patch draft promotion receipt evidence boundary failed")

    output = ROOT / "build/patch-draft-promotion-receipt-ledger-evidence.json"
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode("utf-8")).hexdigest()
    output.with_suffix(".json.sha256").write_text(digest + "\n", encoding="ascii")
    print(f"patch draft promotion receipt ledger: PASS {digest}")
    return intake, envelope


if __name__ == "__main__":
    main()
