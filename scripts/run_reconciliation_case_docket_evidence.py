"""Generate deterministic synthetic reconciliation case docket evidence."""

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
    ReconciliationCaseState,
    SyntheticReconciliationCaseDocket,
)
from nurion_pg.reconciliation_monitor import SyntheticReconciliationMonitor
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
SECRET = "synthetic:reconciliation-case-secret:evidence:0001"
POLICY = sha256(b"synthetic reconciliation case evidence policy").hexdigest()
REVIEW_FINDINGS = sha256(b"synthetic reconciliation case Eternian review").hexdigest()


def main() -> None:
    policy = json.loads(
        (ROOT / "config/reconciliation-case-docket-policy.json").read_text(
            encoding="utf-8"
        )
    )
    forbidden = (
        "remediation_proposal_generation_allowed",
        "automatic_repair_allowed",
        "operator_decision_allowed",
        "payment_execution_allowed",
        "production_activation_allowed",
        "real_credentials_allowed",
        "real_personal_data_allowed",
    )
    if (
        policy["mode"] != "UNREGISTERED_SYNTHETIC_ONLY"
        or policy["maximum_state"] != "READY_FOR_REMEDIATION_PROPOSAL"
        or policy["eternian_review_required"] is not True
        or any(policy[field] is not False for field in forbidden)
    ):
        raise SystemExit("reconciliation case docket policy drift detected")

    registry = SyntheticKeyRegistry()
    registry.register(
        SyntheticVerificationKey(
            "reconciliation-case-evidence.invalid",
            "synthetic:key:reconciliation-case-evidence:1",
            SECRET,
            NOW - timedelta(days=1),
            NOW + timedelta(days=1),
        )
    )
    inbox = SyntheticSQLiteWebhookInbox(":memory:", registry)
    payment = PaymentEngine()
    payment.create(
        intent_id="synthetic:intent:reconciliation-case-evidence:1",
        merchant_ref="synthetic:merchant:reconciliation-case-evidence",
        customer_ref="synthetic:customer:reconciliation-case-evidence",
        amount_minor=4200,
        currency="KRW",
        policy_digest=POLICY,
        idempotency_key="synthetic:create:reconciliation-case-evidence:1",
        now=NOW,
    )
    unsigned = WebhookEnvelope(
        "reconciliation-case-evidence.invalid",
        "synthetic:key:reconciliation-case-evidence:1",
        "synthetic:event:reconciliation-case-evidence:1",
        "synthetic:nonce:reconciliation-case-evidence:1",
        "synthetic:intent:reconciliation-case-evidence:1",
        1,
        WebhookEventType.AUTHORIZATION_RESULT,
        NOW,
        {
            "intent_id": "synthetic:intent:reconciliation-case-evidence:1",
            "expected_version": 1,
            "outcome": "SUCCEEDED",
        },
        "sha256=" + "0" * 64,
    )
    envelope = replace(unsigned, signature=sign_envelope(unsigned, SECRET))
    inbox.submit(envelope, received_at=NOW)
    book = SyntheticWebhookProposalBook()
    book.assess(inbox, payment, envelope.event_id, now=NOW)
    proposal_docket = SyntheticProposalReviewDocket(":memory:")
    source_report = SyntheticReconciliationMonitor().inspect(
        payment, inbox, book, proposal_docket, observed_at=NOW
    )
    if source_report["status"] != "HUMAN_REVIEW":
        raise SystemExit("expected an undocketed proposal review finding")

    case_docket = SyntheticReconciliationCaseDocket(":memory:")
    submitted = case_docket.submit_report(source_report, submitted_at=NOW)
    reviewed = case_docket.record_eternian_review(
        submitted.case_id,
        review_id="synthetic:reconciliation-review:evidence:1",
        reviewer_id="synthetic:eternian-reviewer:case-evidence:1",
        decision=ReconciliationCaseReviewDecision.CONFIRM,
        findings_digest=REVIEW_FINDINGS,
        reviewed_at=NOW,
    )
    report = case_docket.evidence()
    case_docket.close()
    proposal_docket.close()
    inbox.close()
    if (
        reviewed.state is not ReconciliationCaseState.READY_FOR_REMEDIATION_PROPOSAL
        or reviewed.automatic_repair_allowed
        or reviewed.operator_approval_recorded
        or reviewed.execution_allowed
        or report["audit_chain_valid"] is not True
        or report["record_bindings_valid"] is not True
        or report["remediation_proposal_method_present"] is not False
        or report["automatic_repair_method_present"] is not False
        or report["operator_decision_method_present"] is not False
        or report["execution_method_present"] is not False
        or report["money_movement_executed"] is not False
        or report["production_activation_allowed"] is not False
    ):
        raise SystemExit("synthetic reconciliation case boundary failed")

    output = ROOT / "build/synthetic-reconciliation-case-docket-evidence.json"
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode("utf-8")).hexdigest()
    output.with_suffix(".json.sha256").write_text(digest + "\n", encoding="ascii")
    print(f"synthetic reconciliation case docket: PASS {digest}")


if __name__ == "__main__":
    main()
