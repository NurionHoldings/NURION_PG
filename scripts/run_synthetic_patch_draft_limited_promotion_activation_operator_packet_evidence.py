"""Generate evidence for non-authorizing activation operator packets."""

from __future__ import annotations

import json
from hashlib import sha256

from nurion_pg.operator_decision_packets import OperatorGovernanceSnapshot
from nurion_pg.synthetic_patch_draft_limited_promotion_activation_operator_packets import (
    ACTIVATION_OPERATOR_ALLOWED_DECISIONS,
    ACTIVATION_OPERATOR_PACKET_SCOPE,
    ACTIVATION_OPERATOR_REQUIRED_ACKNOWLEDGEMENTS,
    SyntheticPatchDraftLimitedPromotionActivationOperatorPacketBook,
)
from nurion_pg.synthetic_patch_draft_limited_promotion_activation_review_docket import (
    ActivationManifestReviewState,
)
from run_operator_decision_intake_evidence import NOW, ROOT, read_json
from run_synthetic_patch_draft_limited_promotion_activation_review_evidence import (
    main as build_activation_review_source,
)


def main() -> SyntheticPatchDraftLimitedPromotionActivationOperatorPacketBook:
    policy = read_json(
        "config/patch-draft-limited-promotion-activation-operator-packet-policy.json"
    )
    forbidden = (
        "operator_decision_recording_allowed",
        "candidate_content_allowed",
        "patch_content_allowed",
        "diff_content_allowed",
        "source_code_change_allowed",
        "filesystem_write_allowed",
        "automatic_application_allowed",
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
        or policy["required_source_state"]
        != ActivationManifestReviewState.READY_FOR_SYNTHETIC_LIMITED_PROMOTION_OPERATOR_DECISION.value
        or policy["maximum_state"]
        != "AWAITING_SYNTHETIC_LIMITED_PROMOTION_ACTIVATION_OPERATOR_DECISION"
        or policy["validity_hours"] != 24
        or policy["requested_scope"] != ACTIVATION_OPERATOR_PACKET_SCOPE
        or tuple(policy["allowed_decisions"])
        != ACTIVATION_OPERATOR_ALLOWED_DECISIONS
        or tuple(policy["required_acknowledgements"])
        != ACTIVATION_OPERATOR_REQUIRED_ACKNOWLEDGEMENTS
        or any(policy[field] is not False for field in forbidden)
    ):
        raise SystemExit("activation operator packet policy drift detected")

    docket, manifest_id = build_activation_review_source()
    governance = OperatorGovernanceSnapshot.from_documents(
        read_json("config/external-blockers.json"),
        read_json("governance/authority-policy.json"),
        read_json("governance/promotion-policy.json"),
    )
    before = docket.evidence()["report_digest"]
    source = docket.ready_source(manifest_id)
    book = SyntheticPatchDraftLimitedPromotionActivationOperatorPacketBook()
    packet = book.prepare(
        docket,
        manifest_id,
        governance,
        generated_at=NOW,
    )
    after = docket.evidence()["report_digest"]
    report = book.evidence()
    docket.close()

    forbidden_report_fields = (
        "operator_decision_method_present",
        "operator_decision_recorded",
        "candidate_content_present",
        "patch_content_present",
        "diff_content_present",
        "source_code_change_method_present",
        "filesystem_write_method_present",
        "application_method_present",
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
        before != after
        or packet.manifest_digest != source.manifest.manifest_digest
        or packet.final_review_digest != source.review_digest
        or packet.requested_scope != ACTIVATION_OPERATOR_PACKET_SCOPE
        or packet.release_status != "BLOCKED"
        or report["packet_chain_valid"] is not True
        or report["maximum_state"]
        != "AWAITING_SYNTHETIC_LIMITED_PROMOTION_ACTIVATION_OPERATOR_DECISION"
        or any(report[field] is not False for field in forbidden_report_fields)
    ):
        raise SystemExit("activation operator packet boundary failed")

    output = (
        ROOT
        / "build/synthetic-patch-draft-limited-promotion-activation-"
        "operator-packet-evidence.json"
    )
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode("utf-8")).hexdigest()
    output.with_suffix(".json.sha256").write_text(
        digest + "\n", encoding="ascii"
    )
    print(f"synthetic activation operator packet: PASS {digest}")
    return book


if __name__ == "__main__":
    main()
