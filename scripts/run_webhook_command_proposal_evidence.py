"""Generate deterministic non-executing webhook command proposal evidence."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

from nurion_pg.durable_webhook_inbox import SyntheticSQLiteWebhookInbox
from nurion_pg.payment_lifecycle import PaymentEngine, PaymentState
from nurion_pg.webhook_command_proposals import (
    ProposalDecision,
    SyntheticWebhookProposalBook,
)
from nurion_pg.webhook_intake import (
    SyntheticKeyRegistry,
    SyntheticVerificationKey,
    WebhookEnvelope,
    WebhookEventType,
    sign_envelope,
)


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 17, tzinfo=UTC)
SECRET = "synthetic:webhook-proposal-secret:evidence:0001"
POLICY = sha256(b"synthetic webhook proposal evidence policy").hexdigest()


def main() -> None:
    policy = json.loads(
        (ROOT / "config/webhook-command-proposal-policy.json").read_text(encoding="utf-8")
    )
    if (
        policy["mode"] != "UNREGISTERED_SYNTHETIC_ONLY"
        or policy["accepted_durable_receipt_required"] is not True
        or policy["review_required"] is not True
        or policy["automatic_payment_application_allowed"] is not False
        or policy["execution_method_allowed"] is not False
        or policy["money_movement_allowed"] is not False
        or policy["production_activation_allowed"] is not False
    ):
        raise SystemExit("webhook command proposal policy drift detected")

    registry = SyntheticKeyRegistry()
    registry.register(
        SyntheticVerificationKey(
            "proposal-evidence-provider.invalid",
            "synthetic:key:proposal-evidence:1",
            SECRET,
            NOW - timedelta(days=1),
            NOW + timedelta(days=1),
        )
    )
    inbox = SyntheticSQLiteWebhookInbox(":memory:", registry)
    unsigned = WebhookEnvelope(
        "proposal-evidence-provider.invalid",
        "synthetic:key:proposal-evidence:1",
        "synthetic:event:proposal-evidence:1",
        "synthetic:nonce:proposal-evidence:1",
        "synthetic:intent:proposal-evidence:1",
        1,
        WebhookEventType.AUTHORIZATION_RESULT,
        NOW,
        {
            "intent_id": "synthetic:intent:proposal-evidence:1",
            "expected_version": 1,
            "outcome": "SUCCEEDED",
        },
        "sha256=" + "0" * 64,
    )
    value = replace(unsigned, signature=sign_envelope(unsigned, SECRET))
    inbox.submit(value, received_at=NOW)

    payment = PaymentEngine()
    payment.create(
        intent_id=value.aggregate_id,
        merchant_ref="synthetic:merchant:proposal-evidence",
        customer_ref="synthetic:customer:proposal-evidence",
        amount_minor=1000,
        currency="KRW",
        policy_digest=POLICY,
        idempotency_key="synthetic:create:proposal-evidence:1",
        now=NOW,
    )
    book = SyntheticWebhookProposalBook(
        max_source_age_seconds=policy["max_source_age_seconds"]
    )
    assessment = book.assess(inbox, payment, value.event_id, now=NOW)
    if (
        assessment.decision is not ProposalDecision.PROPOSED_FOR_HUMAN_REVIEW
        or assessment.proposal is None
        or assessment.proposal.execution_allowed
        or payment.get(value.aggregate_id).state is not PaymentState.CREATED
        or payment.get(value.aggregate_id).version != 1
    ):
        raise SystemExit("proposal unexpectedly executed or changed Payment Intent")
    report = book.evidence()
    inbox.close()
    if (
        report["assessment_chain_valid"] is not True
        or report["review_required"] is not True
        or report["execution_method_present"] is not False
        or report["payment_state_automatically_changed"] is not False
        or report["money_movement_executed"] is not False
        or report["production_activation_allowed"] is not False
    ):
        raise SystemExit("webhook command proposal evidence boundary failed")
    output = ROOT / "build/synthetic-webhook-command-proposal-evidence.json"
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode("utf-8")).hexdigest()
    output.with_suffix(".json.sha256").write_text(digest + "\n", encoding="ascii")
    print(f"synthetic webhook command proposals: PASS {digest}")


if __name__ == "__main__":
    main()
