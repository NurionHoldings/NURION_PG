"""Generate evidence for durable activation intent receipts."""

from __future__ import annotations

import json
import tempfile
from hashlib import sha256
from pathlib import Path

from nurion_pg.synthetic_patch_draft_limited_promotion_activation_intake import (
    ACTIVATION_INTENT_VALIDATION_STATE,
)
from nurion_pg.synthetic_patch_draft_limited_promotion_activation_receipt_ledger import (
    ACTIVATION_RECEIPT_STATE,
    SyntheticPatchDraftLimitedPromotionActivationReceiptLedger,
)
from run_operator_decision_intake_evidence import NOW, ROOT, read_json
from run_synthetic_patch_draft_limited_promotion_activation_intake_evidence import (
    main as build_validated_activation_intake,
)


def main():
    policy = read_json(
        "config/patch-draft-limited-promotion-activation-"
        "receipt-ledger-policy.json"
    )
    forbidden = (
        "actual_operator_decision_recording_allowed",
        "activation_recording_allowed",
        "packet_state_change_allowed",
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
        or policy["required_input_state"] != ACTIVATION_INTENT_VALIDATION_STATE
        or policy["maximum_state"] != ACTIVATION_RECEIPT_STATE
        or policy["database_engine"] != "SQLite"
        or policy["synthetic_evidence_only"] is not True
        or any(policy[field] is not False for field in forbidden)
    ):
        raise SystemExit("activation receipt ledger policy drift detected")

    intake, envelope = build_validated_activation_intake()
    source_before = intake.evidence()["report_digest"]
    assessment = next(
        item for item in intake.assessments
        if item.envelope_id == envelope.envelope_id
    )
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "synthetic-activation-receipts.sqlite3"
        ledger = SyntheticPatchDraftLimitedPromotionActivationReceiptLedger(
            path
        )
        receipt = ledger.record_from_intake(
            intake, envelope.envelope_id, recorded_at=NOW
        )
        first_report = ledger.evidence()
        ledger.close()
        reopened = SyntheticPatchDraftLimitedPromotionActivationReceiptLedger(
            path
        )
        persisted = reopened.get(receipt.receipt_id)
        report = reopened.evidence()
        reopened.close()

    source_after = intake.evidence()["report_digest"]
    forbidden_report_fields = (
        "actual_operator_decision_recording_method_present",
        "activation_recording_method_present",
        "packet_state_change_method_present",
        "source_code_change_method_present",
        "filesystem_write_method_present",
        "activation_method_present",
        "rollback_execution_method_present",
        "safety_baseline_relaxation_method_present",
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
        source_before != source_after
        or persisted != receipt
        or receipt.assessment_digest != assessment.assessment_digest
        or receipt.manifest_id != assessment.manifest_id
        or receipt.state != ACTIVATION_RECEIPT_STATE
        or first_report != report
        or report["metadata_valid"] is not True
        or report["audit_chain_valid"] is not True
        or report["record_bindings_valid"] is not True
        or report["synthetic_evidence_only"] is not True
        or report["maximum_state"] != ACTIVATION_RECEIPT_STATE
        or any(report[field] is not False for field in forbidden_report_fields)
    ):
        raise SystemExit("activation receipt ledger boundary failed")

    output = (
        ROOT
        / "build/synthetic-patch-draft-limited-promotion-activation-"
        "receipt-ledger-evidence.json"
    )
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode("utf-8")).hexdigest()
    output.with_suffix(".json.sha256").write_text(
        digest + "\n", encoding="ascii"
    )
    print(f"synthetic activation receipt ledger: PASS {digest}")
    return intake, envelope


if __name__ == "__main__":
    main()
