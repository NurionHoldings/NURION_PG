"""Generate deterministic evidence for synthetic patch draft shadow evaluation."""

from __future__ import annotations

import json
from hashlib import sha256

from nurion_pg.arkaon.governance import canonical_digest
from nurion_pg.synthetic_patch_draft_review_docket import (
    PatchDraftReviewDecision,
    SyntheticPatchDraftReviewDocket,
)
from nurion_pg.synthetic_patch_draft_shadow import (
    MAXIMUM_PATCH_DRAFT_SHADOW_DECISION,
    PatchDraftShadowDecision,
    SyntheticPatchDraftShadowBook,
    SyntheticPatchDraftShadowFixture,
)
from run_operator_decision_intake_evidence import NOW, ROOT, read_json
from run_synthetic_patch_draft_review_docket_evidence import (
    main as build_patch_draft_review_source,
)


def main() -> None:
    policy = read_json("config/synthetic-patch-draft-shadow-policy.json")
    forbidden = (
        "patch_content_allowed", "diff_content_allowed",
        "source_code_change_allowed", "filesystem_write_allowed",
        "automatic_application_allowed", "safety_baseline_relaxation_allowed",
        "payment_execution_allowed", "money_movement_allowed",
        "production_activation_allowed", "network_access_allowed",
        "real_credentials_allowed", "real_personal_data_allowed",
    )
    if (
        policy["mode"] != "UNREGISTERED_SYNTHETIC_ONLY"
        or policy["required_input_state"]
        != "READY_FOR_SYNTHETIC_PATCH_DRAFT_SHADOW"
        or policy["maximum_decision"] != MAXIMUM_PATCH_DRAFT_SHADOW_DECISION
        or policy["synthetic_fixture_only"] is not True
        or policy["eternian_review_required"] is not True
        or any(policy[field] is not False for field in forbidden)
    ):
        raise SystemExit("synthetic patch draft shadow policy drift detected")

    manifest_book, manifest = build_patch_draft_review_source()
    review = SyntheticPatchDraftReviewDocket(":memory:")
    review.submit_from_book(
        manifest_book, manifest.source_receipt_id, submitted_at=NOW
    )
    review.record_eternian_review(
        manifest.manifest_id,
        review_id="synthetic:patch-draft-review:shadow-evidence",
        reviewer_id="synthetic:eternian-reviewer:patch-draft:shadow-evidence",
        decision=PatchDraftReviewDecision.PASS,
        findings_digest=sha256(b"patch draft shadow review source").hexdigest(),
        reviewed_at=NOW,
    )
    source_before = review.evidence()["report_digest"]
    fixtures = []
    for index, (scope, target_digest) in enumerate(
        zip(manifest.draft_scopes, manifest.target_path_digests, strict=True), start=1
    ):
        values = {
            "fixture_id": f"synthetic:patch-draft-shadow-fixture:evidence-{index}",
            "manifest_id": manifest.manifest_id,
            "manifest_digest": manifest.manifest_digest,
            "draft_scope": scope,
            "target_path_digest": target_digest,
            "candidate_artifact_digest": sha256(
                f"patch-draft-candidate:{index}".encode("ascii")
            ).hexdigest(),
            "synthetic_input_only": True,
            "manifest_binding_verified": True,
            "expected_metadata_change_observed": True,
            "fail_closed_baseline_preserved": True,
            "regression_test_passed": True,
            "concurrency_failure_tests_passed": True,
            "sha256_evidence_reproduced": True,
            "eternian_review_retained": True,
            "patch_content_present": False,
            "diff_content_present": False,
            "source_code_changed": False,
            "filesystem_written": False,
            "network_access_used": False,
            "production_access_used": False,
            "credentials_used": False,
            "personal_data_used": False,
            "money_movement_executed": False,
        }
        fixtures.append(SyntheticPatchDraftShadowFixture(
            **values, fixture_digest=canonical_digest(values)
        ))
    book = SyntheticPatchDraftShadowBook()
    assessment = book.evaluate(
        review, manifest.manifest_id, tuple(fixtures), evaluated_at=NOW
    )
    source_after = review.evidence()["report_digest"]
    report = book.evidence()
    review.close()

    forbidden_report_fields = (
        "source_docket_state_changed", "patch_content_present",
        "diff_content_present", "source_code_changed", "filesystem_written",
        "application_method_present", "safety_baseline_relaxation_method_present",
        "execution_method_present", "network_access_method_present",
        "personal_data_used", "credentials_used", "money_movement_executed",
        "production_activation_allowed",
    )
    if (
        source_before != source_after
        or assessment.decision
        is not PatchDraftShadowDecision.PROPOSED_FOR_ETERNIAN_REVIEW
        or assessment.manifest_id != manifest.manifest_id
        or report["assessment_chain_valid"] is not True
        or report["maximum_decision"] != MAXIMUM_PATCH_DRAFT_SHADOW_DECISION
        or any(report[field] is not False for field in forbidden_report_fields)
    ):
        raise SystemExit("synthetic patch draft shadow evidence boundary failed")

    output = ROOT / "build/synthetic-patch-draft-shadow-evidence.json"
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode("utf-8")).hexdigest()
    output.with_suffix(".json.sha256").write_text(digest + "\n", encoding="ascii")
    print(f"synthetic patch draft shadow: PASS {digest}")


if __name__ == "__main__":
    main()
