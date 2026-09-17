"""Generate deterministic evidence for the patch shadow review docket."""

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
from nurion_pg.synthetic_implementation_proposals import (
    IMPLEMENTATION_PROPOSAL_STATE,
    SyntheticImplementationProposalBook,
)
from nurion_pg.synthetic_implementation_review_docket import (
    ImplementationProposalReviewDecision,
    SyntheticImplementationReviewDocket,
)
from nurion_pg.synthetic_patch_shadow import (
    MAXIMUM_PATCH_SHADOW_DECISION,
    PatchShadowDecision,
    SyntheticPatchShadowBook,
    SyntheticPatchShadowFixture,
)
from nurion_pg.synthetic_patch_shadow_review_docket import (
    PatchShadowReviewDecision,
    PatchShadowReviewState,
    SyntheticPatchShadowReviewDocket,
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
    policy = read_json(
        "config/synthetic-patch-shadow-review-docket-policy.json"
    )
    forbidden = (
        "automatic_review_allowed",
        "operator_decision_recording_allowed",
        "patch_content_allowed",
        "code_change_allowed",
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
        or policy["required_shadow_decision"] != MAXIMUM_PATCH_SHADOW_DECISION
        or policy["maximum_state"]
        != PatchShadowReviewState.READY_FOR_OPERATOR_DECISION.value
        or policy["review_authority"] != "ETERNIAN_INDEPENDENT_REVIEW"
        or policy["synthetic_sqlite_only"] is not True
        or any(policy[field] is not False for field in forbidden)
    ):
        raise SystemExit("synthetic patch shadow review policy drift detected")

    findings = sha256(b"synthetic patch shadow review evidence").hexdigest()
    case_docket = SyntheticReconciliationCaseDocket(":memory:")
    case = case_docket.submit_report(source_report(), submitted_at=NOW)
    case_docket.record_eternian_review(
        case.case_id,
        review_id="synthetic:reconciliation-review:implementation-proposal",
        reviewer_id="synthetic:eternian-reviewer:implementation-proposal-case",
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
        review_id="synthetic:remediation-review:implementation-proposal",
        reviewer_id="synthetic:eternian-reviewer:implementation-proposal-proposal",
        decision=RemediationReviewDecision.PASS,
        findings_digest=findings,
        reviewed_at=NOW,
    )
    item = proposal.plan_items[0]
    fixture_value = {
        "fixture_id": "synthetic:remediation-shadow-fixture:implementation-proposal",
        "plan_item_digest": item.item_digest,
        "action_type": item.action_type.value,
        "fixture_seed_digest": sha256(b"implementation proposal fixture").hexdigest(),
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
        review_id="synthetic:shadow-review:implementation-proposal",
        reviewer_id="synthetic:eternian-reviewer:implementation-proposal-shadow",
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
        database = Path(directory) / "synthetic-implementation-proposals.sqlite3"
        ledger = SyntheticOperatorDecisionReceiptLedger(database)
        receipt = ledger.record_from_intake(
            intake, envelope.envelope_id, recorded_at=NOW
        )
        first_report = ledger.evidence()
        ledger.close()
        reopened = SyntheticOperatorDecisionReceiptLedger(database)
        persisted = reopened.get(receipt.receipt_id)
        receipt_report = reopened.evidence()
        proposal_book = SyntheticImplementationProposalBook()
        receipt_before = reopened.evidence()["report_digest"]
        proposal = proposal_book.draft_from_receipt(
            reopened,
            receipt.receipt_id,
            draft_scopes=(
                "SYNTHETIC_FIXTURE_PATCH_DRAFT_ONLY",
                "TEST_HARDENING_PATCH_DRAFT_ONLY",
                "POLICY_CLARIFICATION_PATCH_DRAFT_ONLY",
            ),
            drafted_at=NOW,
        )
        receipt_after = reopened.evidence()["report_digest"]
        proposal_report = proposal_book.evidence()
        proposal_before = proposal_book.evidence()["report_digest"]
        review_database = Path(directory) / "synthetic-implementation-reviews.sqlite3"
        review_docket = SyntheticImplementationReviewDocket(review_database)
        pending = review_docket.submit_from_book(
            proposal_book, receipt.receipt_id, submitted_at=NOW
        )
        reviewed = review_docket.record_eternian_review(
            proposal.proposal_id,
            review_id="synthetic:implementation-proposal-review:evidence",
            reviewer_id=(
                "synthetic:eternian-reviewer:implementation-proposal:evidence"
            ),
            decision=ImplementationProposalReviewDecision.PASS,
            findings_digest=findings,
            reviewed_at=NOW,
        )
        first_review_report = review_docket.evidence()
        review_docket.close()
        reopened_review = SyntheticImplementationReviewDocket(review_database)
        persisted_review = reopened_review.get(proposal.proposal_id)
        ready = reopened_review.ready_source(proposal.proposal_id)
        review_report = reopened_review.evidence()
        review_before = reopened_review.evidence()["report_digest"]
        patch_fixtures = []
        for index, scope in enumerate(proposal.draft_scopes, start=1):
            values = {
                "fixture_id": f"synthetic:patch-shadow-fixture:evidence-{index}",
                "proposal_id": proposal.proposal_id,
                "proposal_digest": proposal.proposal_digest,
                "draft_scope": scope,
                "base_snapshot_digest": sha256(
                    f"patch-shadow-base:{index}".encode("ascii")
                ).hexdigest(),
                "candidate_patch_digest": sha256(
                    f"patch-shadow-candidate:{index}".encode("ascii")
                ).hexdigest(),
                "synthetic_input_only": True,
                "expected_change_observed": True,
                "fail_closed_baseline_preserved": True,
                "regression_test_passed": True,
                "concurrency_failure_tests_passed": True,
                "sha256_evidence_reproduced": True,
                "eternian_review_retained": True,
                "source_code_changed": False,
                "filesystem_written": False,
                "network_access_used": False,
                "production_access_used": False,
                "credentials_used": False,
                "personal_data_used": False,
                "money_movement_executed": False,
            }
            patch_fixtures.append(
                SyntheticPatchShadowFixture(
                    **values,
                    fixture_digest=canonical_digest(values),
                )
            )
        patch_book = SyntheticPatchShadowBook()
        patch_assessment = patch_book.evaluate(
            reopened_review,
            proposal.proposal_id,
            tuple(patch_fixtures),
            evaluated_at=NOW,
        )
        review_after = reopened_review.evidence()["report_digest"]
        patch_report = patch_book.evidence()
        patch_review_database = (
            Path(directory) / "synthetic-patch-shadow-reviews.sqlite3"
        )
        patch_review_docket = SyntheticPatchShadowReviewDocket(
            patch_review_database
        )
        patch_review_record = patch_review_docket.submit_from_book(
            patch_book,
            proposal.proposal_id,
            submitted_at=NOW,
        )
        patch_reviewed = patch_review_docket.record_eternian_review(
            patch_review_record.shadow_id,
            review_id="synthetic:patch-shadow-review:evidence",
            reviewer_id="synthetic:eternian-reviewer:patch-shadow:evidence",
            decision=PatchShadowReviewDecision.PASS,
            findings_digest=findings,
            reviewed_at=NOW,
        )
        first_patch_review_report = patch_review_docket.evidence()
        patch_review_docket.close()
        reopened_patch_review = SyntheticPatchShadowReviewDocket(
            patch_review_database
        )
        persisted_patch_review = reopened_patch_review.get(
            patch_review_record.shadow_id
        )
        patch_review_before = reopened_patch_review.evidence()["report_digest"]
        ready_patch_source = reopened_patch_review.ready_source(
            patch_review_record.shadow_id
        )
        patch_review_after = reopened_patch_review.evidence()["report_digest"]
        report = reopened_patch_review.evidence()
        reopened_patch_review.close()
        reopened_review.close()
        proposal_after = proposal_book.evidence()["report_digest"]
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
        or first_report != receipt_report
        or receipt_before != receipt_after
        or proposal.source_receipt_id != receipt.receipt_id
        or proposal.state != IMPLEMENTATION_PROPOSAL_STATE
        or proposal.actual_operator_decision_recorded
        or proposal.code_change_allowed
        or proposal.automatic_application_allowed
        or proposal.execution_allowed
        or proposal.money_movement_allowed
        or proposal.production_activation_allowed
        or proposal_report["proposal_chain_valid"] is not True
        or proposal_before != proposal_after
        or pending.proposal.proposal_id != proposal.proposal_id
        or persisted_review != reviewed
        or ready != reviewed
        or first_review_report != review_report
        or review_before != review_after
        or patch_assessment.proposal_id != proposal.proposal_id
        or patch_assessment.decision
        is not PatchShadowDecision.PROPOSED_FOR_ETERNIAN_REVIEW
        or patch_assessment.source_docket_state_changed
        or patch_assessment.patch_content_present
        or patch_assessment.code_change_allowed
        or patch_assessment.automatic_application_allowed
        or patch_assessment.safety_baseline_relaxation_allowed
        or patch_assessment.execution_allowed
        or patch_assessment.production_activation_allowed
        or patch_report["assessment_chain_valid"] is not True
        or patch_report["maximum_decision"] != MAXIMUM_PATCH_SHADOW_DECISION
        or patch_review_record.shadow_id != patch_assessment.shadow_id
        or patch_review_record.shadow_assessment_digest
        != patch_assessment.assessment_digest
        or patch_reviewed.state
        is not PatchShadowReviewState.READY_FOR_OPERATOR_DECISION
        or persisted_patch_review != patch_reviewed
        or ready_patch_source.shadow_id != patch_assessment.shadow_id
        or ready_patch_source.shadow_assessment_digest
        != patch_assessment.assessment_digest
        or patch_review_before != patch_review_after
        or first_patch_review_report != report
        or report["audit_chain_valid"] is not True
        or report["record_bindings_valid"] is not True
        or report["maximum_state"]
        != PatchShadowReviewState.READY_FOR_OPERATOR_DECISION.value
        or report["automatic_review_allowed"] is not False
        or report["patch_content_present"] is not False
        or report["network_access_method_present"] is not False
        or report["operator_decision_method_present"] is not False
        or report["code_change_method_present"] is not False
        or report["application_method_present"] is not False
        or report["safety_baseline_relaxation_allowed"] is not False
        or report["execution_method_present"] is not False
        or report["personal_data_used"] is not False
        or report["credentials_used"] is not False
        or report["money_movement_executed"] is not False
        or report["production_activation_allowed"] is not False
    ):
        raise SystemExit("synthetic patch shadow review evidence boundary failed")

    output = ROOT / "build/synthetic-patch-shadow-review-docket-evidence.json"
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode("utf-8")).hexdigest()
    output.with_suffix(".json.sha256").write_text(digest + "\n", encoding="ascii")
    print(f"synthetic patch shadow review docket: PASS {digest}")


if __name__ == "__main__":
    main()
