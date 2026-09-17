"""Generate evidence for durable activation manifest final review."""

from __future__ import annotations

import json
import tempfile
from hashlib import sha256
from pathlib import Path

from nurion_pg.synthetic_patch_draft_limited_promotion_activation_review_docket import (
    MAXIMUM_ACTIVATION_MANIFEST_REVIEW_STATE,
    ActivationManifestReviewDecision,
    ActivationManifestReviewState,
    SyntheticPatchDraftLimitedPromotionActivationReviewDocket,
)
from run_operator_decision_intake_evidence import NOW, ROOT, read_json
from run_synthetic_patch_draft_limited_promotion_activation_manifest_evidence import (
    main as build_activation_manifest_source,
)


def main() -> tuple[
    SyntheticPatchDraftLimitedPromotionActivationReviewDocket, str
]:
    policy = read_json(
        "config/patch-draft-limited-promotion-activation-review-policy.json"
    )
    forbidden = (
        "automatic_review_allowed", "operator_decision_recording_allowed",
        "candidate_content_allowed", "patch_content_allowed",
        "diff_content_allowed", "source_code_change_allowed",
        "filesystem_write_allowed", "activation_allowed",
        "rollback_execution_allowed", "safety_baseline_relaxation_allowed",
        "execution_allowed", "payment_execution_allowed",
        "money_movement_allowed", "automatic_merge_allowed",
        "automatic_deploy_allowed", "production_activation_allowed",
        "network_access_allowed", "real_credentials_allowed",
        "real_personal_data_allowed",
    )
    if (
        policy["mode"] != "UNREGISTERED_SYNTHETIC_ONLY"
        or policy["review_authority"] != "ETERNIAN_FINAL_REVIEW"
        or tuple(policy["allowed_decisions"]) != ("PASS", "HOLD", "REJECT")
        or policy["pass_state"] != MAXIMUM_ACTIVATION_MANIFEST_REVIEW_STATE
        or policy["maximum_state"] != MAXIMUM_ACTIVATION_MANIFEST_REVIEW_STATE
        or policy["synthetic_sqlite_only"] is not True
        or policy["append_only_audit_required"] is not True
        or policy["source_manifest_preservation_required"] is not True
        or any(policy[field] is not False for field in forbidden)
    ):
        raise SystemExit("activation final review policy drift detected")

    book, manifest = build_activation_manifest_source()
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "synthetic-activation-final-reviews.sqlite3"
        docket = SyntheticPatchDraftLimitedPromotionActivationReviewDocket(path)
        pending = docket.submit_from_book(
            book, manifest.manifest_id, submitted_at=NOW
        )
        reviewed = docket.record_eternian_review(
            manifest.manifest_id,
            review_id="synthetic:limited-promotion-activation-final-review:evidence",
            reviewer_id=(
                "synthetic:eternian-reviewer:limited-promotion-activation:evidence"
            ),
            decision=ActivationManifestReviewDecision.PASS,
            findings_digest=sha256(b"activation final review evidence").hexdigest(),
            reviewed_at=NOW,
        )
        before = docket.evidence()
        ready = docket.ready_source(manifest.manifest_id)
        docket.close()
        reopened = SyntheticPatchDraftLimitedPromotionActivationReviewDocket(path)
        after = reopened.evidence()
        persisted = reopened.get(manifest.manifest_id)

    forbidden_report_fields = (
        "automatic_review_allowed", "operator_decision_recording_method_present",
        "candidate_content_present", "patch_content_present",
        "diff_content_present", "source_code_changed", "filesystem_written",
        "activation_method_present", "rollback_execution_method_present",
        "safety_baseline_relaxation_method_present", "execution_method_present",
        "network_access_method_present", "external_blocker_close_method_present",
        "automatic_merge_method_present", "automatic_deploy_method_present",
        "personal_data_used", "credentials_used", "money_movement_executed",
        "production_activation_allowed",
    )
    if (
        pending.state is not ActivationManifestReviewState.PENDING_ETERNIAN_FINAL_REVIEW
        or reviewed.state is not (
            ActivationManifestReviewState
            .READY_FOR_SYNTHETIC_LIMITED_PROMOTION_OPERATOR_DECISION
        )
        or before != after or persisted != reviewed
        or ready.manifest.manifest_digest != manifest.manifest_digest
        or after["metadata_valid"] is not True
        or after["audit_chain_valid"] is not True
        or after["record_bindings_valid"] is not True
        or after["maximum_state"] != MAXIMUM_ACTIVATION_MANIFEST_REVIEW_STATE
        or any(after[field] is not False for field in forbidden_report_fields)
    ):
        raise SystemExit("activation final review boundary failed")

    output = ROOT / "build/synthetic-patch-draft-limited-promotion-activation-review-evidence.json"
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(after, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode("utf-8")).hexdigest()
    output.with_suffix(".json.sha256").write_text(digest + "\n", encoding="ascii")
    print(f"synthetic limited promotion activation final review: PASS {digest}")
    return reopened, manifest.manifest_id


if __name__ == "__main__":
    docket, _ = main()
    docket.close()
