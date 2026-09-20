"""Generate deterministic evidence for the synthetic decision receipt ledger."""

from __future__ import annotations

import hmac
import json
import tempfile
from datetime import timedelta
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
from nurion_pg.operator_decision_receipt_ledger import (
    RECEIPT_STATE,
    SyntheticOperatorDecisionReceiptLedger,
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
from run_operator_decision_intake_evidence import (
    KEY_ID,
    NOW,
    ROOT,
    SECRET,
    read_json,
    source_report,
)


def main() -> None:
    policy = read_json("config/operator-decision-receipt-ledger-policy.json")
    forbidden = (
        "actual_operator_decision_recording_allowed",
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
        or policy["required_input_state"] != "SYNTHETIC_DECISION_VALIDATED"
        or policy["maximum_state"] != RECEIPT_STATE
        or policy["database_engine"] != "SQLite"
        or policy["synthetic_evidence_only"] is not True
        or any(policy[field] is not False for field in forbidden)
    ):
        raise SystemExit("operator decision receipt ledger policy drift detected")

    findings = sha256(b"operator decision receipt ledger evidence").hexdigest()
    case_docket = SyntheticReconciliationCaseDocket(":memory:")
    case = case_docket.submit_report(source_report(), submitted_at=NOW)
    case_docket.record_eternian_review(
        case.case_id,
        review_id="synthetic:reconciliation-review:decision-receipt",
        reviewer_id="synthetic:eternian-reviewer:decision-receipt-case",
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
        review_id="synthetic:remediation-review:decision-receipt",
        reviewer_id="synthetic:eternian-reviewer:decision-receipt-proposal",
        decision=RemediationReviewDecision.PASS,
        findings_digest=findings,
        reviewed_at=NOW,
    )
    item = proposal.plan_items[0]
    fixture_value = {
        "fixture_id": "synthetic:remediation-shadow-fixture:decision-receipt",
        "plan_item_digest": item.item_digest,
        "action_type": item.action_type.value,
        "fixture_seed_digest": sha256(b"decision receipt fixture").hexdigest(),
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
        review_id="synthetic:shadow-review:decision-receipt",
        reviewer_id="synthetic:eternian-reviewer:decision-receipt-shadow",
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
        "envelope_id": "synthetic:operator-decision-envelope:receipt-evidence",
        "packet_id": packet.packet_id,
        "packet_digest": packet.packet_digest,
        "operator_id": SYNTHETIC_OPERATOR_ID,
        "decision": decision.value,
        "requested_scope": PACKET_SCOPE,
        "acknowledgements": list(REQUIRED_ACKNOWLEDGEMENTS),
        "issued_at": NOW.isoformat(),
        "expires_at": (NOW + DECISION_ENVELOPE_VALIDITY).isoformat(),
        "nonce": "synthetic:operator-nonce:receipt-evidence",
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
    intake = SyntheticOperatorDecisionIntake(registry)
    assessment = intake.assess(
        packet_book, shadow_record.shadow_id, envelope, received_at=NOW
    )
    source_before = intake.evidence()["report_digest"]

    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "synthetic-decision-receipts.sqlite3"
        ledger = SyntheticOperatorDecisionReceiptLedger(database)
        receipt = ledger.record_from_intake(
            intake, envelope.envelope_id, recorded_at=NOW
        )
        first_report = ledger.evidence()
        ledger.close()
        reopened = SyntheticOperatorDecisionReceiptLedger(database)
        persisted = reopened.get(receipt.receipt_id)
        report = reopened.evidence()
        reopened.close()

    source_after = intake.evidence()["report_digest"]
    shadow_docket.close()
    remediation_docket.close()
    case_docket.close()

    if (
        source_before != source_after
        or persisted != receipt
        or receipt.assessment_digest != assessment.assessment_digest
        or receipt.state != RECEIPT_STATE
        or receipt.actual_operator_decision_recorded
        or receipt.packet_state_changed
        or receipt.code_change_allowed
        or receipt.automatic_application_allowed
        or receipt.execution_allowed
        or first_report != report
        or report["metadata_valid"] is not True
        or report["audit_chain_valid"] is not True
        or report["record_bindings_valid"] is not True
        or report["synthetic_evidence_only"] is not True
        or report["maximum_state"] != RECEIPT_STATE
        or report["actual_operator_decision_recording_method_present"] is not False
        or report["packet_state_change_method_present"] is not False
        or report["code_change_method_present"] is not False
        or report["application_method_present"] is not False
        or report["execution_method_present"] is not False
        or report["money_movement_executed"] is not False
        or report["production_activation_allowed"] is not False
    ):
        raise SystemExit("operator decision receipt ledger evidence boundary failed")

    output = ROOT / "build/synthetic-decision-receipt-ledger-evidence.json"
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode("utf-8")).hexdigest()
    output.with_suffix(".json.sha256").write_text(digest + "\n", encoding="ascii")
    print(f"synthetic decision receipt ledger: PASS {digest}")


if __name__ == "__main__":
    main()
