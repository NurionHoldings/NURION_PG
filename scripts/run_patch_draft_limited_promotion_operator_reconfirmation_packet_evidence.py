"""Generate evidence for limited promotion operator reconfirmation packets."""

from __future__ import annotations

import json
from hashlib import sha256

from nurion_pg.operator_decision_packets import OperatorGovernanceSnapshot
from nurion_pg.patch_draft_limited_promotion_operator_reconfirmation_packets import (
    LIMITED_PROMOTION_RECONFIRMATION_ALLOWED_DECISIONS,
    LIMITED_PROMOTION_RECONFIRMATION_PACKET_SCOPE,
    LIMITED_PROMOTION_RECONFIRMATION_REQUIRED_ACKNOWLEDGEMENTS,
    SyntheticPatchDraftLimitedPromotionOperatorReconfirmationPacketBook,
)
from nurion_pg.synthetic_patch_draft_limited_promotion_shadow_review_docket import (
    LimitedPromotionShadowReviewState,
)
from run_operator_decision_intake_evidence import NOW, ROOT, read_json
from run_synthetic_patch_draft_limited_promotion_shadow_review_evidence import (
    main as build_limited_promotion_shadow_review_source,
)


def main() -> (
    SyntheticPatchDraftLimitedPromotionOperatorReconfirmationPacketBook
):
    policy = read_json(
        "config/patch-draft-limited-promotion-operator-"
        "reconfirmation-packet-policy.json"
    )
    forbidden = (
        "operator_reconfirmation_recording_allowed",
        "candidate_content_allowed",
        "patch_content_allowed",
        "diff_content_allowed",
        "source_code_change_allowed",
        "filesystem_write_allowed",
        "automatic_application_allowed",
        "safety_baseline_relaxation_allowed",
        "execution_allowed",
        "synthetic_activation_allowed",
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
        or policy["required_source_state"]
        != LimitedPromotionShadowReviewState.READY_FOR_PATCH_DRAFT_LIMITED_PROMOTION_OPERATOR_RECONFIRMATION.value
        or policy["maximum_state"]
        != "AWAITING_PATCH_DRAFT_LIMITED_PROMOTION_OPERATOR_RECONFIRMATION"
        or policy["validity_hours"] != 24
        or policy["requested_scope"]
        != LIMITED_PROMOTION_RECONFIRMATION_PACKET_SCOPE
        or tuple(policy["allowed_decisions"])
        != LIMITED_PROMOTION_RECONFIRMATION_ALLOWED_DECISIONS
        or tuple(policy["required_acknowledgements"])
        != LIMITED_PROMOTION_RECONFIRMATION_REQUIRED_ACKNOWLEDGEMENTS
        or any(policy[field] is not False for field in forbidden)
    ):
        raise SystemExit(
            "limited promotion operator reconfirmation policy drift detected"
        )

    docket, shadow_id = build_limited_promotion_shadow_review_source()
    governance = OperatorGovernanceSnapshot.from_documents(
        read_json("config/external-blockers.json"),
        read_json("governance/authority-policy.json"),
        read_json("governance/promotion-policy.json"),
    )
    before = docket.evidence()["report_digest"]
    source = docket.ready_source(shadow_id)
    book = (
        SyntheticPatchDraftLimitedPromotionOperatorReconfirmationPacketBook()
    )
    packet = book.prepare(
        docket,
        shadow_id,
        governance,
        generated_at=NOW,
    )
    after = docket.evidence()["report_digest"]
    report = book.evidence()
    docket.close()

    forbidden_report_fields = (
        "operator_reconfirmation_method_present",
        "operator_reconfirmation_recorded",
        "candidate_content_present",
        "patch_content_present",
        "diff_content_present",
        "source_code_change_method_present",
        "filesystem_write_method_present",
        "application_method_present",
        "safety_baseline_relaxation_method_present",
        "execution_method_present",
        "synthetic_activation_allowed",
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
        before != after
        or packet.shadow_assessment_digest
        != source.assessment.assessment_digest
        or packet.shadow_review_digest != source.review_digest
        or packet.requested_scope
        != LIMITED_PROMOTION_RECONFIRMATION_PACKET_SCOPE
        or packet.release_status != "BLOCKED"
        or report["packet_chain_valid"] is not True
        or report["maximum_state"]
        != "AWAITING_PATCH_DRAFT_LIMITED_PROMOTION_OPERATOR_RECONFIRMATION"
        or any(report[field] is not False for field in forbidden_report_fields)
    ):
        raise SystemExit(
            "limited promotion operator reconfirmation packet boundary failed"
        )

    output = (
        ROOT
        / "build/patch-draft-limited-promotion-operator-"
        "reconfirmation-packet-evidence.json"
    )
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode("utf-8")).hexdigest()
    output.with_suffix(".json.sha256").write_text(
        digest + "\n", encoding="ascii"
    )
    print(
        "patch draft limited promotion operator reconfirmation packet: "
        f"PASS {digest}"
    )
    return book


if __name__ == "__main__":
    main()
