"""Generate deterministic evidence for synthetic operator decision intent intake."""

from __future__ import annotations

import hmac
import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

from nurion_pg.arkaon.governance import canonical_digest
from nurion_pg.operator_decision_intake import (
    DECISION_ENVELOPE_VALIDITY,
    SYNTHETIC_OPERATOR_ID,
    SyntheticOperatorDecision,
    SyntheticOperatorDecisionEnvelope,
    SyntheticOperatorDecisionIntake,
    SyntheticOperatorKeyRegistry,
    SyntheticOperatorVerificationKey,
)
from nurion_pg.operator_decision_packets import (
    PACKET_SCOPE,
    REQUIRED_ACKNOWLEDGEMENTS,
    OperatorGovernanceSnapshot,
    SyntheticOperatorDecisionPacketBook,
)
from nurion_pg.reconciliation_case_docket import (
    ReconciliationCaseReviewDecision,
    SyntheticReconciliationCaseDocket,
)
from nurion_pg.reconciliation_remediation_proposals import SyntheticRemediationProposalBook
from nurion_pg.remediation_review_docket import (
    RemediationReviewDecision,
    SyntheticRemediationReviewDocket,
)
from nurion_pg.remediation_shadow_review_docket import (
    ShadowReviewDecision,
    SyntheticRemediationShadowReviewDocket,
)
from nurion_pg.remediation_synthetic_shadow import (
    SyntheticRemediationShadowBook,
    SyntheticRemediationShadowFixture,
)


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 17, tzinfo=UTC)
KEY_ID = "synthetic:key:operator-decision:evidence"
SECRET = "synthetic:operator-secret:evidence-only-0000000001"


def read_json(path: str) -> dict[str, object]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def source_report() -> dict[str, object]:
    value: dict[str, object] = {
        "schema": "nurion.pg.synthetic-reconciliation-report.v1",
        "observed_at": NOW.isoformat(),
        "status": "BLOCKED",
        "component_snapshot_digests": {
            name: sha256(f"decision-intake:{name}".encode("ascii")).hexdigest()
            for name in ("payment", "inbox", "proposals", "docket")
        },
        "findings": [
            {
                "code": "PROPOSAL_MISSING_DOCKET",
                "severity": "BLOCKED",
                "subject_id": "synthetic:proposal:decision-intake-evidence",
                "detail": "synthetic proposal is absent from review docket",
                "suggested_action": "Eternian review required",
                "automatic_repair_allowed": False,
            }
        ],
        "finding_counts": {"WARNING": 0, "BLOCKED": 1},
        "read_only_verified": True,
        "synthetic_only": True,
        "automatic_repair_allowed": False,
        "operator_decision_recorded": False,
        "payment_state_changed": False,
        "money_movement_executed": False,
        "production_activation_allowed": False,
    }
    return {**value, "report_digest": canonical_digest(value)}


def main() -> None:
    policy = read_json("config/operator-decision-intake-policy.json")
    forbidden = (
        "signing_allowed",
        "operator_decision_recording_allowed",
        "packet_state_change_allowed",
        "code_change_allowed",
        "automatic_application_allowed",
        "payment_execution_allowed",
        "money_movement_allowed",
        "production_activation_allowed",
        "real_credentials_allowed",
        "real_personal_data_allowed",
    )
    if (
        policy["mode"] != "UNREGISTERED_SYNTHETIC_ONLY"
        or policy["operator_id"] != SYNTHETIC_OPERATOR_ID
        or policy["signature_algorithm"] != "HMAC-SHA256_SYNTHETIC_ONLY"
        or policy["envelope_validity_minutes"] != 10
        or policy["maximum_future_skew_seconds"] != 30
        or policy["maximum_state"] != "SYNTHETIC_DECISION_VALIDATED"
        or policy["synthetic_verification_only"] is not True
        or any(policy[field] is not False for field in forbidden)
    ):
        raise SystemExit("operator decision intake policy drift detected")

    findings = sha256(b"operator decision intake evidence").hexdigest()
    case_docket = SyntheticReconciliationCaseDocket(":memory:")
    case = case_docket.submit_report(source_report(), submitted_at=NOW)
    case_docket.record_eternian_review(
        case.case_id,
        review_id="synthetic:reconciliation-review:decision-intake",
        reviewer_id="synthetic:eternian-reviewer:decision-intake-case",
        decision=ReconciliationCaseReviewDecision.CONFIRM,
        findings_digest=findings,
        reviewed_at=NOW,
    )
    proposal_book = SyntheticRemediationProposalBook()
    proposal = proposal_book.draft(case_docket, case.case_id, now=NOW).proposal
    if proposal is None:
        raise SystemExit("synthetic remediation proposal was not created")
    remediation_docket = SyntheticRemediationReviewDocket(":memory:")
    remediation = remediation_docket.submit_from_book(
        proposal_book, case.case_id, submitted_at=NOW
    )
    remediation_docket.record_eternian_review(
        remediation.proposal_id,
        review_id="synthetic:remediation-review:decision-intake",
        reviewer_id="synthetic:eternian-reviewer:decision-intake-proposal",
        decision=RemediationReviewDecision.PASS,
        findings_digest=findings,
        reviewed_at=NOW,
    )
    item = proposal.plan_items[0]
    fixture_value = {
        "fixture_id": "synthetic:remediation-shadow-fixture:decision-intake",
        "plan_item_digest": item.item_digest,
        "action_type": item.action_type.value,
        "fixture_seed_digest": sha256(b"decision intake fixture").hexdigest(),
        "trigger_observed": True,
        "fail_closed_baseline_preserved": True,
        "regression_test_passed": True,
        "sha256_evidence_reproduced": True,
        "eternian_review_retained": True,
        "payment_state_changed": False,
        "money_movement_executed": False,
        "production_access_used": False,
    }
    fixture = SyntheticRemediationShadowFixture(
        fixture_value["fixture_id"],
        fixture_value["plan_item_digest"],
        item.action_type,
        fixture_value["fixture_seed_digest"],
        True,
        True,
        True,
        True,
        True,
        False,
        False,
        False,
        canonical_digest(fixture_value),
    )
    shadow_book = SyntheticRemediationShadowBook()
    shadow_book.evaluate(
        remediation_docket, proposal.proposal_id, (fixture,), evaluated_at=NOW
    )
    shadow_docket = SyntheticRemediationShadowReviewDocket(":memory:")
    shadow_record = shadow_docket.submit_from_book(
        shadow_book, proposal.proposal_id, submitted_at=NOW
    )
    shadow_docket.record_eternian_review(
        shadow_record.shadow_id,
        review_id="synthetic:shadow-review:decision-intake",
        reviewer_id="synthetic:eternian-reviewer:decision-intake-shadow",
        decision=ShadowReviewDecision.PASS,
        findings_digest=findings,
        reviewed_at=NOW,
    )
    governance = OperatorGovernanceSnapshot.from_documents(
        read_json("config/external-blockers.json"),
        read_json("governance/authority-policy.json"),
        read_json("governance/promotion-policy.json"),
    )
    packet_book = SyntheticOperatorDecisionPacketBook()
    packet = packet_book.prepare(
        shadow_docket, shadow_record.shadow_id, governance, generated_at=NOW
    )
    registry = SyntheticOperatorKeyRegistry()
    registry.register(
        SyntheticOperatorVerificationKey(
            KEY_ID,
            SYNTHETIC_OPERATOR_ID,
            SECRET,
            NOW - timedelta(days=1),
            NOW + timedelta(days=1),
        )
    )
    decision = (
        SyntheticOperatorDecision.AUTHORIZE_SYNTHETIC_IMPLEMENTATION_PROPOSAL_DRAFT
    )
    signing_value = {
        "envelope_id": "synthetic:operator-decision-envelope:evidence",
        "packet_id": packet.packet_id,
        "packet_digest": packet.packet_digest,
        "operator_id": SYNTHETIC_OPERATOR_ID,
        "decision": decision.value,
        "requested_scope": PACKET_SCOPE,
        "acknowledgements": list(REQUIRED_ACKNOWLEDGEMENTS),
        "issued_at": NOW.isoformat(),
        "expires_at": (NOW + DECISION_ENVELOPE_VALIDITY).isoformat(),
        "nonce": "synthetic:operator-nonce:evidence",
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
    envelope = SyntheticOperatorDecisionEnvelope(
        signing_value["envelope_id"],
        packet.packet_id,
        packet.packet_digest,
        SYNTHETIC_OPERATOR_ID,
        decision,
        PACKET_SCOPE,
        REQUIRED_ACKNOWLEDGEMENTS,
        NOW,
        NOW + DECISION_ENVELOPE_VALIDITY,
        signing_value["nonce"],
        KEY_ID,
        signature,
    )
    before = packet_book.evidence()["report_digest"]
    intake = SyntheticOperatorDecisionIntake(registry)
    assessment = intake.assess(
        packet_book, shadow_record.shadow_id, envelope, received_at=NOW
    )
    after = packet_book.evidence()["report_digest"]
    report = intake.evidence()
    shadow_docket.close()
    remediation_docket.close()
    case_docket.close()

    if (
        before != after
        or assessment.validation_state != "SYNTHETIC_DECISION_VALIDATED"
        or assessment.packet_state_changed
        or assessment.operator_decision_recorded
        or assessment.code_change_allowed
        or assessment.automatic_application_allowed
        or assessment.execution_allowed
        or report["assessment_chain_valid"] is not True
        or report["synthetic_verification_only"] is not True
        or report["maximum_state"] != "SYNTHETIC_DECISION_VALIDATED"
        or report["signing_method_present"] is not False
        or report["operator_decision_recording_method_present"] is not False
        or report["packet_state_changed"] is not False
        or report["code_change_method_present"] is not False
        or report["application_method_present"] is not False
        or report["execution_method_present"] is not False
        or report["money_movement_executed"] is not False
        or report["production_activation_allowed"] is not False
    ):
        raise SystemExit("operator decision intake evidence boundary failed")

    output = ROOT / "build/synthetic-operator-decision-intake-evidence.json"
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode("utf-8")).hexdigest()
    output.with_suffix(".json.sha256").write_text(digest + "\n", encoding="ascii")
    print(f"synthetic operator decision intake: PASS {digest}")


if __name__ == "__main__":
    main()
