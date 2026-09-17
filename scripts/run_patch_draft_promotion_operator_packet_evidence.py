"""Generate deterministic evidence for patch draft promotion operator packets."""

from __future__ import annotations

import json
from hashlib import sha256

from nurion_pg.operator_decision_packets import OperatorGovernanceSnapshot
from nurion_pg.patch_draft_promotion_operator_packets import (
    PATCH_DRAFT_PROMOTION_ALLOWED_DECISIONS,
    PATCH_DRAFT_PROMOTION_PACKET_SCOPE,
    PATCH_DRAFT_PROMOTION_REQUIRED_ACKNOWLEDGEMENTS,
    SyntheticPatchDraftPromotionOperatorPacketBook,
)
from nurion_pg.synthetic_patch_draft_shadow_review_docket import (
    PatchDraftShadowReviewState,
)
from run_operator_decision_intake_evidence import NOW, ROOT, read_json
from run_synthetic_patch_draft_shadow_review_docket_evidence import (
    main as build_patch_draft_shadow_review_source,
)


def main() -> SyntheticPatchDraftPromotionOperatorPacketBook:
    policy = read_json("config/patch-draft-promotion-operator-packet-policy.json")
    forbidden = (
        "operator_decision_recording_allowed", "patch_content_allowed",
        "diff_content_allowed", "source_code_change_allowed",
        "filesystem_write_allowed", "automatic_application_allowed",
        "safety_baseline_relaxation_allowed", "external_blocker_auto_close_allowed",
        "payment_execution_allowed", "money_movement_allowed",
        "automatic_merge_allowed", "automatic_deploy_allowed",
        "production_activation_allowed", "network_access_allowed",
        "real_credentials_allowed", "real_personal_data_allowed",
    )
    if (
        policy["mode"] != "UNREGISTERED_SYNTHETIC_ONLY"
        or policy["required_source_state"]
        != PatchDraftShadowReviewState.READY_FOR_PATCH_DRAFT_OPERATOR_DECISION.value
        or policy["maximum_state"]
        != "AWAITING_PATCH_DRAFT_PROMOTION_OPERATOR_DECISION"
        or policy["validity_days"] != 7
        or policy["requested_scope"] != PATCH_DRAFT_PROMOTION_PACKET_SCOPE
        or tuple(policy["allowed_decisions"])
        != PATCH_DRAFT_PROMOTION_ALLOWED_DECISIONS
        or tuple(policy["required_acknowledgements"])
        != PATCH_DRAFT_PROMOTION_REQUIRED_ACKNOWLEDGEMENTS
        or any(policy[field] is not False for field in forbidden)
    ):
        raise SystemExit("patch draft promotion packet policy drift detected")

    docket, shadow_id = build_patch_draft_shadow_review_source()
    governance = OperatorGovernanceSnapshot.from_documents(
        read_json("config/external-blockers.json"),
        read_json("governance/authority-policy.json"),
        read_json("governance/promotion-policy.json"),
    )
    before = docket.evidence()["report_digest"]
    book = SyntheticPatchDraftPromotionOperatorPacketBook()
    packet = book.prepare(docket, shadow_id, governance, generated_at=NOW)
    after = docket.evidence()["report_digest"]
    report = book.evidence()
    docket.close()

    forbidden_report_fields = (
        "operator_decision_method_present", "patch_content_present",
        "diff_content_present", "source_code_change_method_present",
        "filesystem_write_method_present", "application_method_present",
        "safety_baseline_relaxation_method_present", "execution_method_present",
        "network_access_method_present", "external_blocker_close_method_present",
        "automatic_merge_method_present", "automatic_deploy_method_present",
        "personal_data_used", "credentials_used", "money_movement_executed",
        "production_activation_allowed",
    )
    if (
        before != after
        or packet.requested_scope != PATCH_DRAFT_PROMOTION_PACKET_SCOPE
        or packet.release_status != "BLOCKED"
        or report["packet_chain_valid"] is not True
        or report["maximum_state"]
        != "AWAITING_PATCH_DRAFT_PROMOTION_OPERATOR_DECISION"
        or any(report[field] is not False for field in forbidden_report_fields)
    ):
        raise SystemExit("patch draft promotion packet evidence boundary failed")

    output = ROOT / "build/patch-draft-promotion-operator-packet-evidence.json"
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode("utf-8")).hexdigest()
    output.with_suffix(".json.sha256").write_text(digest + "\n", encoding="ascii")
    print(f"patch draft promotion operator packet: PASS {digest}")
    return book


if __name__ == "__main__":
    main()
