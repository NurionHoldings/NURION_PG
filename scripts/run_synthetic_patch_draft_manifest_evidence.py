"""Generate deterministic evidence for metadata-only synthetic patch drafts."""

from __future__ import annotations

import json
from hashlib import sha256

from nurion_pg.patch_operator_decision_receipt_ledger import (
    SyntheticPatchDecisionReceiptLedger,
)
from nurion_pg.synthetic_patch_draft_manifests import (
    PATCH_DRAFT_MANIFEST_STATE,
    REQUIRED_PATCH_DRAFT_CHECKS,
    SyntheticPatchDraftManifest,
    SyntheticPatchDraftManifestBook,
)
from run_operator_decision_intake_evidence import NOW, ROOT, read_json
from run_patch_operator_decision_receipt_ledger_evidence import (
    main as build_receiptable_patch_intake,
)


SCOPES = (
    "SYNTHETIC_FIXTURE_PATCH_DRAFT_ONLY",
    "TEST_HARDENING_PATCH_DRAFT_ONLY",
    "POLICY_CLARIFICATION_PATCH_DRAFT_ONLY",
)
TARGET_DIGESTS = tuple(
    sha256(f"synthetic-target:{scope}".encode("ascii")).hexdigest()
    for scope in SCOPES
)


def main() -> tuple[
    SyntheticPatchDraftManifestBook,
    SyntheticPatchDraftManifest,
]:
    policy = read_json("config/synthetic-patch-draft-manifest-policy.json")
    forbidden = (
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
        != "SYNTHETIC_PATCH_DECISION_RECEIPT_RECORDED"
        or policy["required_decision"] != "AUTHORIZE_SYNTHETIC_PATCH_DRAFT"
        or policy["maximum_state"] != PATCH_DRAFT_MANIFEST_STATE
        or policy["metadata_only"] is not True
        or policy["eternian_review_required"] is not True
        or tuple(policy["required_checks"]) != REQUIRED_PATCH_DRAFT_CHECKS
        or any(policy[field] is not False for field in forbidden)
    ):
        raise SystemExit("synthetic patch draft manifest policy drift detected")

    intake, envelope = build_receiptable_patch_intake()
    ledger = SyntheticPatchDecisionReceiptLedger(":memory:")
    receipt = ledger.record_from_intake(
        intake, envelope.envelope_id, recorded_at=NOW
    )
    source_before = ledger.evidence()["report_digest"]
    book = SyntheticPatchDraftManifestBook()
    manifest = book.draft_from_receipt(
        ledger,
        receipt.receipt_id,
        draft_scopes=SCOPES,
        target_path_digests=TARGET_DIGESTS,
        drafted_at=NOW,
    )
    source_after = ledger.evidence()["report_digest"]
    report = book.evidence()
    ledger.close()

    forbidden_report_fields = (
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
        or manifest.source_receipt_id != receipt.receipt_id
        or manifest.state != PATCH_DRAFT_MANIFEST_STATE
        or manifest.draft_scopes != SCOPES
        or manifest.target_path_digests != TARGET_DIGESTS
        or manifest.required_checks != REQUIRED_PATCH_DRAFT_CHECKS
        or report["manifest_chain_valid"] is not True
        or report["metadata_only"] is not True
        or report["eternian_review_required"] is not True
        or report["maximum_state"] != PATCH_DRAFT_MANIFEST_STATE
        or any(report[field] is not False for field in forbidden_report_fields)
    ):
        raise SystemExit("synthetic patch draft manifest evidence boundary failed")

    output = ROOT / "build/synthetic-patch-draft-manifest-evidence.json"
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode("utf-8")).hexdigest()
    output.with_suffix(".json.sha256").write_text(digest + "\n", encoding="ascii")
    print(f"synthetic patch draft manifest: PASS {digest}")
    return book, manifest


if __name__ == "__main__":
    main()
