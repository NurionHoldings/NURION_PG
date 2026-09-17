"""Generate deterministic read-only synthetic reconciliation evidence."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

from nurion_pg.durable_webhook_inbox import SyntheticSQLiteWebhookInbox
from nurion_pg.payment_lifecycle import PaymentEngine
from nurion_pg.proposal_review_docket import SyntheticProposalReviewDocket
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
SECRET = "synthetic:reconciliation-secret:evidence:0001"
POLICY = sha256(b"synthetic reconciliation evidence policy").hexdigest()


def main() -> None:
    policy = json.loads(
        (ROOT / "config/reconciliation-monitor-policy.json").read_text(encoding="utf-8")
    )
    required_false = (
        "automatic_repair_allowed",
        "operator_decision_allowed",
        "payment_execution_allowed",
        "production_activation_allowed",
        "real_credentials_allowed",
        "real_personal_data_allowed",
    )
    if (
        policy["mode"] != "UNREGISTERED_SYNTHETIC_ONLY"
        or policy["read_only"] is not True
        or policy["finding_destination"] != "ETERNIAN_REVIEW"
        or any(policy[field] is not False for field in required_false)
    ):
        raise SystemExit("reconciliation monitor policy drift detected")

    registry = SyntheticKeyRegistry()
    registry.register(
        SyntheticVerificationKey(
            "reconciliation-evidence.invalid",
            "synthetic:key:reconciliation-evidence:1",
            SECRET,
            NOW - timedelta(days=1),
            NOW + timedelta(days=1),
        )
    )
    inbox = SyntheticSQLiteWebhookInbox(":memory:", registry)
    payment = PaymentEngine()
    payment.create(
        intent_id="synthetic:intent:reconciliation-evidence:1",
        merchant_ref="synthetic:merchant:reconciliation-evidence",
        customer_ref="synthetic:customer:reconciliation-evidence",
        amount_minor=3100,
        currency="KRW",
        policy_digest=POLICY,
        idempotency_key="synthetic:create:reconciliation-evidence:1",
        now=NOW,
    )
    unsigned = WebhookEnvelope(
        "reconciliation-evidence.invalid",
        "synthetic:key:reconciliation-evidence:1",
        "synthetic:event:reconciliation-evidence:1",
        "synthetic:nonce:reconciliation-evidence:1",
        "synthetic:intent:reconciliation-evidence:1",
        1,
        WebhookEventType.AUTHORIZATION_RESULT,
        NOW,
        {
            "intent_id": "synthetic:intent:reconciliation-evidence:1",
            "expected_version": 1,
            "outcome": "SUCCEEDED",
        },
        "sha256=" + "0" * 64,
    )
    envelope = replace(unsigned, signature=sign_envelope(unsigned, SECRET))
    inbox.submit(envelope, received_at=NOW)
    book = SyntheticWebhookProposalBook()
    assessment = book.assess(inbox, payment, envelope.event_id, now=NOW)
    docket = SyntheticProposalReviewDocket(":memory:")
    docket.submit_from_book(book, assessment.source_event_id, submitted_at=NOW)

    before = (
        payment.evidence()["report_digest"],
        inbox.evidence()["report_digest"],
        book.evidence()["report_digest"],
        docket.evidence()["report_digest"],
    )
    report = SyntheticReconciliationMonitor().inspect(
        payment, inbox, book, docket, observed_at=NOW
    )
    after = (
        payment.evidence()["report_digest"],
        inbox.evidence()["report_digest"],
        book.evidence()["report_digest"],
        docket.evidence()["report_digest"],
    )
    docket.close()
    inbox.close()
    if (
        report["status"] != "PASS"
        or report["findings"]
        or report["read_only_verified"] is not True
        or before != after
        or report["automatic_repair_allowed"] is not False
        or report["operator_decision_recorded"] is not False
        or report["payment_state_changed"] is not False
        or report["money_movement_executed"] is not False
        or report["production_activation_allowed"] is not False
    ):
        raise SystemExit("synthetic reconciliation evidence boundary failed")

    output = ROOT / "build/synthetic-reconciliation-monitor-evidence.json"
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode("utf-8")).hexdigest()
    output.with_suffix(".json.sha256").write_text(digest + "\n", encoding="ascii")
    print(f"synthetic reconciliation monitor: PASS {digest}")


if __name__ == "__main__":
    main()
