"""Generate deterministic ARKAON-to-Eternian synthetic review docket evidence."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

from nurion_pg.durable_webhook_inbox import SyntheticSQLiteWebhookInbox
from nurion_pg.payment_lifecycle import PaymentEngine
from nurion_pg.proposal_review_docket import (
    DocketState,
    EternianReviewDecision,
    SyntheticProposalReviewDocket,
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
SECRET = "synthetic:proposal-docket-secret:evidence:0001"
POLICY = sha256(b"synthetic proposal docket evidence policy").hexdigest()
FINDINGS = sha256(b"synthetic Eternian review findings").hexdigest()


def main() -> None:
    policy = json.loads(
        (ROOT / "config/proposal-review-docket-policy.json").read_text(encoding="utf-8")
    )
    if (
        policy["mode"] != "UNREGISTERED_SYNTHETIC_ONLY"
        or policy["maximum_automatic_state"] != "READY_FOR_OPERATOR_DECISION"
        or policy["automatic_review_allowed"] is not False
        or policy["operator_decision_method_allowed"] is not False
        or policy["execution_method_allowed"] is not False
        or policy["production_activation_allowed"] is not False
    ):
        raise SystemExit("proposal review docket policy drift detected")

    registry = SyntheticKeyRegistry()
    registry.register(
        SyntheticVerificationKey(
            "docket-evidence-provider.invalid",
            "synthetic:key:docket-evidence:1",
            SECRET,
            NOW - timedelta(days=1),
            NOW + timedelta(days=1),
        )
    )
    inbox = SyntheticSQLiteWebhookInbox(":memory:", registry)
    unsigned = WebhookEnvelope(
        "docket-evidence-provider.invalid",
        "synthetic:key:docket-evidence:1",
        "synthetic:event:docket-evidence:1",
        "synthetic:nonce:docket-evidence:1",
        "synthetic:intent:docket-evidence:1",
        1,
        WebhookEventType.AUTHORIZATION_RESULT,
        NOW,
        {
            "intent_id": "synthetic:intent:docket-evidence:1",
            "expected_version": 1,
            "outcome": "SUCCEEDED",
        },
        "sha256=" + "0" * 64,
    )
    envelope = replace(unsigned, signature=sign_envelope(unsigned, SECRET))
    inbox.submit(envelope, received_at=NOW)
    payment = PaymentEngine()
    payment.create(
        intent_id=envelope.aggregate_id,
        merchant_ref="synthetic:merchant:docket-evidence",
        customer_ref="synthetic:customer:docket-evidence",
        amount_minor=1000,
        currency="KRW",
        policy_digest=POLICY,
        idempotency_key="synthetic:create:docket-evidence:1",
        now=NOW,
    )
    book = SyntheticWebhookProposalBook()
    assessment = book.assess(inbox, payment, envelope.event_id, now=NOW)
    docket = SyntheticProposalReviewDocket(":memory:")
    submitted = docket.submit_from_book(book, assessment.source_event_id, submitted_at=NOW)
    reviewed = docket.record_eternian_review(
        submitted.proposal_id,
        review_id="synthetic:review:docket-evidence:1",
        reviewer_id="synthetic:eternian-reviewer:evidence:1",
        decision=EternianReviewDecision.PASS,
        findings_digest=FINDINGS,
        reviewed_at=NOW,
    )
    report = docket.evidence()
    docket.close()
    inbox.close()
    if (
        reviewed.state is not DocketState.READY_FOR_OPERATOR_DECISION
        or reviewed.operator_approval_recorded
        or reviewed.execution_allowed
        or report["audit_chain_valid"] is not True
        or report["record_bindings_valid"] is not True
        or report["operator_decision_method_present"] is not False
        or report["execution_method_present"] is not False
        or report["production_activation_allowed"] is not False
    ):
        raise SystemExit("proposal review docket evidence boundary failed")
    output = ROOT / "build/synthetic-proposal-review-docket-evidence.json"
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode("utf-8")).hexdigest()
    output.with_suffix(".json.sha256").write_text(digest + "\n", encoding="ascii")
    print(f"synthetic proposal review docket: PASS {digest}")


if __name__ == "__main__":
    main()
