"""Generate deterministic evidence for the synthetic patch decision receipt ledger."""

from __future__ import annotations

import json
import tempfile
from hashlib import sha256
from pathlib import Path

from nurion_pg.patch_operator_decision_receipt_ledger import (
    PATCH_RECEIPT_STATE,
    SyntheticPatchDecisionReceiptLedger,
)
from run_operator_decision_intake_evidence import NOW, ROOT, read_json
from run_patch_operator_decision_intake_evidence import (
    main as build_validated_patch_intake,
)


def main() -> None:
    policy = read_json("config/patch-operator-decision-receipt-ledger-policy.json")
    forbidden = (
        "actual_operator_decision_recording_allowed",
        "packet_state_change_allowed",
        "patch_content_allowed",
        "code_change_allowed",
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
        != "SYNTHETIC_PATCH_DECISION_VALIDATED"
        or policy["maximum_state"] != PATCH_RECEIPT_STATE
        or policy["database_engine"] != "SQLite"
        or policy["synthetic_evidence_only"] is not True
        or any(policy[field] is not False for field in forbidden)
    ):
        raise SystemExit("patch decision receipt ledger policy drift detected")

    intake, envelope = build_validated_patch_intake()
    source_before = intake.evidence()["report_digest"]
    assessment = next(
        item for item in intake.assessments if item.envelope_id == envelope.envelope_id
    )
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "synthetic-patch-decision-receipts.sqlite3"
        ledger = SyntheticPatchDecisionReceiptLedger(database)
        receipt = ledger.record_from_intake(
            intake, envelope.envelope_id, recorded_at=NOW
        )
        first_report = ledger.evidence()
        ledger.close()
        reopened = SyntheticPatchDecisionReceiptLedger(database)
        persisted = reopened.get(receipt.receipt_id)
        report = reopened.evidence()
        reopened.close()

    source_after = intake.evidence()["report_digest"]
    forbidden_report_fields = (
        "actual_operator_decision_recording_method_present",
        "packet_state_change_method_present",
        "patch_content_present",
        "code_change_method_present",
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
        or persisted != receipt
        or receipt.assessment_digest != assessment.assessment_digest
        or receipt.state != PATCH_RECEIPT_STATE
        or first_report != report
        or report["metadata_valid"] is not True
        or report["audit_chain_valid"] is not True
        or report["record_bindings_valid"] is not True
        or report["synthetic_evidence_only"] is not True
        or report["maximum_state"] != PATCH_RECEIPT_STATE
        or any(report[field] is not False for field in forbidden_report_fields)
    ):
        raise SystemExit("patch decision receipt ledger evidence boundary failed")

    output = ROOT / "build/synthetic-patch-decision-receipt-ledger-evidence.json"
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode("utf-8")).hexdigest()
    output.with_suffix(".json.sha256").write_text(digest + "\n", encoding="ascii")
    print(f"synthetic patch decision receipt ledger: PASS {digest}")


if __name__ == "__main__":
    main()
