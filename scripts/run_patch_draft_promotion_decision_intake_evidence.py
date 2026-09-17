"""Generate evidence for synthetic patch draft promotion intent validation."""

from __future__ import annotations

import hmac
import json
from datetime import timedelta
from hashlib import sha256

from nurion_pg.operator_decision_intake import (
    DECISION_ENVELOPE_VALIDITY,
    MAX_FUTURE_SKEW,
    SYNTHETIC_OPERATOR_ID,
    SyntheticOperatorKeyRegistry,
    SyntheticOperatorVerificationKey,
)
from nurion_pg.patch_draft_promotion_decision_intake import (
    PATCH_DRAFT_PROMOTION_VALIDATION_STATE,
    SyntheticPatchDraftPromotionDecision,
    SyntheticPatchDraftPromotionDecisionEnvelope,
    SyntheticPatchDraftPromotionDecisionIntake,
)
from nurion_pg.patch_draft_promotion_operator_packets import (
    PATCH_DRAFT_PROMOTION_ALLOWED_DECISIONS,
    PATCH_DRAFT_PROMOTION_PACKET_SCOPE,
    PATCH_DRAFT_PROMOTION_REQUIRED_ACKNOWLEDGEMENTS,
)
from run_operator_decision_intake_evidence import (
    KEY_ID,
    NOW,
    ROOT,
    SECRET,
    read_json,
)
from run_patch_draft_promotion_operator_packet_evidence import (
    main as build_promotion_packet_source,
)


def main() -> tuple[
    SyntheticPatchDraftPromotionDecisionIntake,
    SyntheticPatchDraftPromotionDecisionEnvelope,
]:
    policy = read_json("config/patch-draft-promotion-decision-intake-policy.json")
    forbidden = (
        "signing_allowed", "operator_decision_recording_allowed",
        "packet_state_change_allowed", "patch_content_allowed",
        "diff_content_allowed", "source_code_change_allowed",
        "filesystem_write_allowed", "automatic_application_allowed",
        "safety_baseline_relaxation_allowed", "payment_execution_allowed",
        "money_movement_allowed", "production_activation_allowed",
        "network_access_allowed", "real_credentials_allowed",
        "real_personal_data_allowed",
    )
    if (
        policy["mode"] != "UNREGISTERED_SYNTHETIC_ONLY"
        or policy["operator_id"] != SYNTHETIC_OPERATOR_ID
        or policy["signature_algorithm"] != "HMAC-SHA256_SYNTHETIC_ONLY"
        or policy["envelope_validity_minutes"]
        != int(DECISION_ENVELOPE_VALIDITY.total_seconds() / 60)
        or policy["maximum_future_skew_seconds"]
        != int(MAX_FUTURE_SKEW.total_seconds())
        or policy["required_packet_scope"] != PATCH_DRAFT_PROMOTION_PACKET_SCOPE
        or tuple(policy["allowed_decisions"])
        != PATCH_DRAFT_PROMOTION_ALLOWED_DECISIONS
        or policy["maximum_state"] != PATCH_DRAFT_PROMOTION_VALIDATION_STATE
        or policy["synthetic_verification_only"] is not True
        or any(policy[field] is not False for field in forbidden)
    ):
        raise SystemExit("patch draft promotion intake policy drift detected")

    packet_book = build_promotion_packet_source()
    packet = packet_book.packets[0]
    decision = (
        SyntheticPatchDraftPromotionDecision
        .AUTHORIZE_SYNTHETIC_PATCH_DRAFT_LIMITED_PROMOTION
    )
    signing_value = {
        "envelope_id": "synthetic:patch-draft-promotion-decision-envelope:evidence",
        "packet_id": packet.packet_id,
        "packet_digest": packet.packet_digest,
        "operator_id": SYNTHETIC_OPERATOR_ID,
        "decision": decision.value,
        "requested_scope": PATCH_DRAFT_PROMOTION_PACKET_SCOPE,
        "acknowledgements": list(
            PATCH_DRAFT_PROMOTION_REQUIRED_ACKNOWLEDGEMENTS
        ),
        "issued_at": NOW.isoformat(),
        "expires_at": (NOW + DECISION_ENVELOPE_VALIDITY).isoformat(),
        "nonce": "synthetic:patch-draft-promotion-operator-nonce:evidence",
        "key_id": KEY_ID,
    }
    signature = "sha256=" + hmac.new(
        SECRET.encode("utf-8"),
        json.dumps(
            signing_value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8"),
        sha256,
    ).hexdigest()
    envelope = SyntheticPatchDraftPromotionDecisionEnvelope(
        signing_value["envelope_id"],
        packet.packet_id,
        packet.packet_digest,
        SYNTHETIC_OPERATOR_ID,
        decision,
        PATCH_DRAFT_PROMOTION_PACKET_SCOPE,
        PATCH_DRAFT_PROMOTION_REQUIRED_ACKNOWLEDGEMENTS,
        NOW,
        NOW + DECISION_ENVELOPE_VALIDITY,
        signing_value["nonce"],
        KEY_ID,
        signature,
    )
    registry = SyntheticOperatorKeyRegistry()
    registry.register(SyntheticOperatorVerificationKey(
        KEY_ID, SYNTHETIC_OPERATOR_ID, SECRET,
        NOW - timedelta(days=1), NOW + timedelta(days=1),
    ))
    intake = SyntheticPatchDraftPromotionDecisionIntake(registry)
    before = packet_book.evidence()["report_digest"]
    assessment = intake.assess(
        packet_book, packet.shadow_id, envelope, received_at=NOW
    )
    after = packet_book.evidence()["report_digest"]
    report = intake.evidence()
    forbidden_report_fields = (
        "signing_method_present", "operator_decision_recording_method_present",
        "packet_state_changed", "patch_content_present", "diff_content_present",
        "source_code_change_method_present", "filesystem_write_method_present",
        "application_method_present", "safety_baseline_relaxation_method_present",
        "execution_method_present", "network_access_method_present",
        "personal_data_used", "credentials_used", "money_movement_executed",
        "production_activation_allowed",
    )
    if (
        before != after
        or assessment.packet_id != packet.packet_id
        or assessment.packet_digest != packet.packet_digest
        or assessment.decision is not decision
        or assessment.validation_state != PATCH_DRAFT_PROMOTION_VALIDATION_STATE
        or report["assessment_chain_valid"] is not True
        or report["maximum_state"] != PATCH_DRAFT_PROMOTION_VALIDATION_STATE
        or report["synthetic_verification_only"] is not True
        or any(report[field] is not False for field in forbidden_report_fields)
    ):
        raise SystemExit("patch draft promotion intake evidence boundary failed")

    output = ROOT / "build/patch-draft-promotion-decision-intake-evidence.json"
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode("utf-8")).hexdigest()
    output.with_suffix(".json.sha256").write_text(digest + "\n", encoding="ascii")
    print(f"patch draft promotion intent intake: PASS {digest}")
    return intake, envelope


if __name__ == "__main__":
    main()
