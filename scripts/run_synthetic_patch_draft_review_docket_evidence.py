"""Generate deterministic evidence for the synthetic patch draft review docket."""

from __future__ import annotations

import json
import tempfile
from hashlib import sha256
from pathlib import Path

from nurion_pg.synthetic_patch_draft_review_docket import (
    MAXIMUM_PATCH_DRAFT_REVIEW_STATE,
    PatchDraftReviewDecision,
    PatchDraftReviewState,
    SyntheticPatchDraftReviewDocket,
)
from run_operator_decision_intake_evidence import NOW, ROOT, read_json
from run_synthetic_patch_draft_manifest_evidence import (
    main as build_patch_draft_manifest,
)


def main() -> None:
    policy = read_json("config/synthetic-patch-draft-review-policy.json")
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
        or policy["required_input_state"] != "SYNTHETIC_PATCH_DRAFT_MANIFESTED"
        or tuple(policy["allowed_review_decisions"]) != ("PASS", "HOLD", "REJECT")
        or policy["pass_state"] != MAXIMUM_PATCH_DRAFT_REVIEW_STATE
        or policy["maximum_state"] != MAXIMUM_PATCH_DRAFT_REVIEW_STATE
        or policy["eternian_review_required"] is not True
        or policy["database_engine"] != "SQLite"
        or any(policy[field] is not False for field in forbidden)
    ):
        raise SystemExit("synthetic patch draft review policy drift detected")

    book, manifest = build_patch_draft_manifest()
    source_before = book.evidence()["report_digest"]
    findings = sha256(b"synthetic patch draft review evidence").hexdigest()
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "synthetic-patch-draft-reviews.sqlite3"
        docket = SyntheticPatchDraftReviewDocket(database)
        pending = docket.submit_from_book(
            book, manifest.source_receipt_id, submitted_at=NOW
        )
        reviewed = docket.record_eternian_review(
            manifest.manifest_id,
            review_id="synthetic:patch-draft-review:evidence",
            reviewer_id="synthetic:eternian-reviewer:patch-draft:evidence",
            decision=PatchDraftReviewDecision.PASS,
            findings_digest=findings,
            reviewed_at=NOW,
        )
        first_report = docket.evidence()
        docket.close()
        reopened = SyntheticPatchDraftReviewDocket(database)
        persisted = reopened.get(manifest.manifest_id)
        ready = reopened.ready_source(manifest.manifest_id)
        report = reopened.evidence()
        reopened.close()
    source_after = book.evidence()["report_digest"]

    forbidden_report_fields = (
        "patch_content_present",
        "diff_content_present",
        "source_code_changed",
        "filesystem_written",
        "application_method_present",
        "safety_baseline_relaxation_method_present",
        "execution_method_present",
        "network_access_method_present",
        "money_movement_executed",
        "production_activation_allowed",
    )
    if (
        source_before != source_after
        or pending.state is not PatchDraftReviewState.PENDING_ETERNIAN_REVIEW
        or reviewed.state
        is not PatchDraftReviewState.READY_FOR_SYNTHETIC_PATCH_DRAFT_SHADOW
        or persisted != reviewed
        or ready != reviewed
        or first_report != report
        or report["metadata_valid"] is not True
        or report["audit_chain_valid"] is not True
        or report["record_bindings_valid"] is not True
        or report["maximum_state"] != MAXIMUM_PATCH_DRAFT_REVIEW_STATE
        or any(report[field] is not False for field in forbidden_report_fields)
    ):
        raise SystemExit("synthetic patch draft review evidence boundary failed")

    output = ROOT / "build/synthetic-patch-draft-review-evidence.json"
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode("utf-8")).hexdigest()
    output.with_suffix(".json.sha256").write_text(digest + "\n", encoding="ascii")
    print(f"synthetic patch draft review docket: PASS {digest}")


if __name__ == "__main__":
    main()
