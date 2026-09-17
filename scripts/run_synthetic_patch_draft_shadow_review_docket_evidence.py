"""Generate deterministic evidence for the patch draft shadow review docket."""

from __future__ import annotations

import json
import tempfile
from hashlib import sha256
from pathlib import Path

from nurion_pg.synthetic_patch_draft_shadow_review_docket import (
    MAXIMUM_PATCH_DRAFT_SHADOW_REVIEW_STATE,
    PatchDraftShadowReviewDecision,
    PatchDraftShadowReviewState,
    SyntheticPatchDraftShadowReviewDocket,
)
from run_operator_decision_intake_evidence import NOW, ROOT, read_json
from run_synthetic_patch_draft_shadow_evidence import (
    main as build_patch_draft_shadow_source,
)


def main() -> tuple[SyntheticPatchDraftShadowReviewDocket, str]:
    policy = read_json(
        "config/synthetic-patch-draft-shadow-review-docket-policy.json"
    )
    forbidden = (
        "automatic_review_allowed", "operator_decision_recording_allowed",
        "patch_content_allowed", "diff_content_allowed",
        "source_code_change_allowed", "filesystem_write_allowed",
        "automatic_application_allowed", "safety_baseline_relaxation_allowed",
        "payment_execution_allowed", "money_movement_allowed",
        "production_activation_allowed", "network_access_allowed",
        "real_credentials_allowed", "real_personal_data_allowed",
    )
    if (
        policy["mode"] != "UNREGISTERED_SYNTHETIC_ONLY"
        or policy["required_shadow_decision"] != "PROPOSED_FOR_ETERNIAN_REVIEW"
        or policy["review_authority"] != "ETERNIAN_INDEPENDENT_REVIEW"
        or policy["maximum_state"] != MAXIMUM_PATCH_DRAFT_SHADOW_REVIEW_STATE
        or policy["synthetic_sqlite_only"] is not True
        or any(policy[field] is not False for field in forbidden)
    ):
        raise SystemExit("patch draft shadow review policy drift detected")

    book, assessment = build_patch_draft_shadow_source()
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "synthetic-patch-draft-shadow-review.sqlite3"
        docket = SyntheticPatchDraftShadowReviewDocket(path)
        record = docket.submit_from_book(
            book, assessment.manifest_id, submitted_at=NOW
        )
        docket.record_eternian_review(
            record.shadow_id,
            review_id="synthetic:patch-draft-shadow-review:evidence",
            reviewer_id=(
                "synthetic:eternian-reviewer:patch-draft-shadow:evidence"
            ),
            decision=PatchDraftShadowReviewDecision.PASS,
            findings_digest=sha256(
                b"independent patch draft shadow review evidence"
            ).hexdigest(),
            reviewed_at=NOW,
        )
        before = docket.evidence()
        ready = docket.ready_source(record.shadow_id)
        docket.close()
        reopened = SyntheticPatchDraftShadowReviewDocket(path)
        after = reopened.evidence()
        persisted = reopened.get(record.shadow_id)

    forbidden_report_fields = (
        "automatic_review_allowed", "operator_decision_method_present",
        "operator_decision_recorded", "patch_content_present",
        "diff_content_present", "source_code_changed", "filesystem_written",
        "application_method_present", "safety_baseline_relaxation_method_present",
        "execution_method_present", "network_access_method_present",
        "personal_data_used", "credentials_used", "money_movement_executed",
        "production_activation_allowed",
    )
    if (
        before != after
        or persisted.state
        is not PatchDraftShadowReviewState.READY_FOR_PATCH_DRAFT_OPERATOR_DECISION
        or ready.shadow_assessment_digest != assessment.assessment_digest
        or after["audit_chain_valid"] is not True
        or after["record_bindings_valid"] is not True
        or after["maximum_state"] != MAXIMUM_PATCH_DRAFT_SHADOW_REVIEW_STATE
        or any(after[field] is not False for field in forbidden_report_fields)
    ):
        raise SystemExit("patch draft shadow review evidence boundary failed")

    output = ROOT / "build/synthetic-patch-draft-shadow-review-evidence.json"
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(after, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode("utf-8")).hexdigest()
    output.with_suffix(".json.sha256").write_text(digest + "\n", encoding="ascii")
    print(f"synthetic patch draft shadow review: PASS {digest}")
    return reopened, record.shadow_id


if __name__ == "__main__":
    docket, _ = main()
    docket.close()
