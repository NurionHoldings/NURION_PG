"""Generate deterministic non-executable remediation proposal evidence."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

from nurion_pg.durable_webhook_inbox import SyntheticSQLiteWebhookInbox
from nurion_pg.payment_lifecycle import PaymentEngine
from nurion_pg.proposal_review_docket import SyntheticProposalReviewDocket
from nurion_pg.reconciliation_case_docket import (
    ReconciliationCaseReviewDecision,
    SyntheticReconciliationCaseDocket,
)
from nurion_pg.reconciliation_monitor import SyntheticReconciliationMonitor
from nurion_pg.reconciliation_remediation_proposals import (
    RemediationProposalDecision,
    SyntheticRemediationProposalBook,
)
from nurion_pg.webhook_command_proposals import SyntheticWebhookProposalBook
from nurion_pg.webhook_intake import (
    SyntheticKeyRegistry,
    SyntheticVerificationKey,
    WebhookEnvelope,
    WebhookEventType,
    sign_envelope,
)


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 17, tzinfo=UTC)
SECRET = "synthetic:remediation-proposal-secret:evidence:0001"
POLICY = sha256(b"synthetic remediation proposal evidence policy").hexdigest()
REVIEW_FINDINGS = sha256(b"synthetic confirmed case review findings").hexdigest()


def main() -> None:
    policy = json.loads(
        (ROOT / "config/reconciliation-remediation-proposal-policy.json").read_text(
            encoding="utf-8"
        )
    )
    forbidden = (
        "code_change_allowed",
        "automatic_application_allowed",
        "safety_baseline_relaxation_allowed",
        "operator_decision_allowed",
        "payment_execution_allowed",
        "production_activation_allowed",
        "real_credentials_allowed",
        "real_personal_data_allowed",
    )
    if (
        policy["mode"] != "UNREGISTERED_SYNTHETIC_ONLY"
        or policy["required_case_state"] != "READY_FOR_REMEDIATION_PROPOSAL"
        or policy["destination"] != "ETERNIAN_REVIEW"
        or policy["unknown_finding_decision"] != "HUMAN_REVIEW"
        or len(policy["action_types"]) != 4
        or any(policy[field] is not False for field in forbidden)
    ):
        raise SystemExit("remediation proposal policy drift detected")

    registry = SyntheticKeyRegistry()
    registry.register(
        SyntheticVerificationKey(
            "remediation-proposal-evidence.invalid",
            "synthetic:key:remediation-proposal-evidence:1",
            SECRET,
            NOW - timedelta(days=1),
            NOW + timedelta(days=1),
        )
    )
    inbox = SyntheticSQLiteWebhookInbox(":memory:", registry)
    payment = PaymentEngine()
    payment.create(
        intent_id="synthetic:intent:remediation-proposal-evidence:1",
        merchant_ref="synthetic:merchant:remediation-proposal-evidence",
        customer_ref="synthetic:customer:remediation-proposal-evidence",
        amount_minor=5300,
        currency="KRW",
        policy_digest=POLICY,
        idempotency_key="synthetic:create:remediation-proposal-evidence:1",
        now=NOW,
    )
    unsigned = WebhookEnvelope(
        "remediation-proposal-evidence.invalid",
        "synthetic:key:remediation-proposal-evidence:1",
        "synthetic:event:remediation-proposal-evidence:1",
        "synthetic:nonce:remediation-proposal-evidence:1",
        "synthetic:intent:remediation-proposal-evidence:1",
        1,
        WebhookEventType.AUTHORIZATION_RESULT,
        NOW,
        {
            "intent_id": "synthetic:intent:remediation-proposal-evidence:1",
            "expected_version": 1,
            "outcome": "SUCCEEDED",
        },
        "sha256=" + "0" * 64,
    )
    envelope = replace(unsigned, signature=sign_envelope(unsigned, SECRET))
    inbox.submit(envelope, received_at=NOW)
    command_book = SyntheticWebhookProposalBook()
    command_book.assess(inbox, payment, envelope.event_id, now=NOW)
    proposal_docket = SyntheticProposalReviewDocket(":memory:")
    source_report = SyntheticReconciliationMonitor().inspect(
        payment, inbox, command_book, proposal_docket, observed_at=NOW
    )
    case_docket = SyntheticReconciliationCaseDocket(":memory:")
    case = case_docket.submit_report(source_report, submitted_at=NOW)
    case_docket.record_eternian_review(
        case.case_id,
        review_id="synthetic:reconciliation-review:remediation-evidence:1",
        reviewer_id="synthetic:eternian-reviewer:remediation-evidence:1",
        decision=ReconciliationCaseReviewDecision.CONFIRM,
        findings_digest=REVIEW_FINDINGS,
        reviewed_at=NOW,
    )
    before = case_docket.evidence()["report_digest"]
    remediation_book = SyntheticRemediationProposalBook()
    assessment = remediation_book.draft(case_docket, case.case_id, now=NOW)
    after = case_docket.evidence()["report_digest"]
    report = remediation_book.evidence()
    case_docket.close()
    proposal_docket.close()
    inbox.close()
    proposal = assessment.proposal
    if (
        assessment.decision
        is not RemediationProposalDecision.PROPOSED_FOR_ETERNIAN_REVIEW
        or proposal is None
        or not proposal.review_required
        or proposal.code_change_allowed
        or proposal.automatic_application_allowed
        or proposal.safety_baseline_relaxation_allowed
        or proposal.operator_approval_recorded
        or proposal.execution_allowed
        or before != after
        or report["assessment_chain_valid"] is not True
        or report["code_change_method_present"] is not False
        or report["application_method_present"] is not False
        or report["safety_baseline_relaxation_method_present"] is not False
        or report["operator_decision_method_present"] is not False
        or report["execution_method_present"] is not False
        or report["production_activation_allowed"] is not False
    ):
        raise SystemExit("synthetic remediation proposal evidence boundary failed")

    output = ROOT / "build/synthetic-remediation-proposal-evidence.json"
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode("utf-8")).hexdigest()
    output.with_suffix(".json.sha256").write_text(digest + "\n", encoding="ascii")
    print(f"synthetic remediation proposals: PASS {digest}")


if __name__ == "__main__":
    main()
