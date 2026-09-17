"""Prove restart, transaction and replay controls using synthetic SQLite only."""

from __future__ import annotations

import json
import tempfile
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

from nurion_pg.durable_webhook_inbox import SyntheticSQLiteWebhookInbox
from nurion_pg.webhook_intake import (
    SyntheticKeyRegistry,
    SyntheticVerificationKey,
    WebhookDecision,
    WebhookEnvelope,
    WebhookEventType,
    sign_envelope,
)


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 17, tzinfo=UTC)
SECRET = "synthetic:durable-webhook-secret:evidence:0001"


def envelope(*, event_id: str, nonce: str, sequence: int) -> WebhookEnvelope:
    value = WebhookEnvelope(
        "durable-evidence-provider.invalid",
        "synthetic:key:durable-evidence:1",
        event_id,
        nonce,
        "synthetic:intent:durable-evidence:1",
        sequence,
        WebhookEventType.AUTHORIZATION_RESULT,
        NOW,
        {
            "intent_id": "synthetic:intent:durable-evidence:1",
            "expected_version": sequence,
            "outcome": "SUCCEEDED",
        },
        "sha256=" + "0" * 64,
    )
    return replace(value, signature=sign_envelope(value, SECRET))


def key_registry() -> SyntheticKeyRegistry:
    registry = SyntheticKeyRegistry()
    registry.register(
        SyntheticVerificationKey(
            "durable-evidence-provider.invalid",
            "synthetic:key:durable-evidence:1",
            SECRET,
            NOW - timedelta(days=1),
            NOW + timedelta(days=1),
        )
    )
    return registry


def main() -> None:
    policy = json.loads(
        (ROOT / "config/durable-webhook-inbox-policy.json").read_text(encoding="utf-8")
    )
    if (
        policy["mode"] != "UNREGISTERED_SYNTHETIC_ONLY"
        or policy["database_engine"] != "SQLite"
        or policy["server_database_allowed"] is not False
        or policy["automatic_payment_application_allowed"] is not False
        or policy["money_movement_allowed"] is not False
        or policy["production_activation_allowed"] is not False
    ):
        raise SystemExit("durable webhook inbox policy drift detected")

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "synthetic-evidence.sqlite3"
        inbox = SyntheticSQLiteWebhookInbox(path, key_registry())
        second = envelope(
            event_id="synthetic:event:durable-evidence:2",
            nonce="synthetic:nonce:durable-evidence:2",
            sequence=2,
        )
        if inbox.submit(second, received_at=NOW).decision is not WebhookDecision.QUARANTINED:
            raise SystemExit("sequence gap was not durably quarantined")
        inbox.close()

        restarted = SyntheticSQLiteWebhookInbox(path, key_registry())
        first = envelope(
            event_id="synthetic:event:durable-evidence:1",
            nonce="synthetic:nonce:durable-evidence:1",
            sequence=1,
        )
        if restarted.submit(first, received_at=NOW).decision is not WebhookDecision.ACCEPTED:
            raise SystemExit("first sequence was not accepted")
        if restarted.retry_quarantined(second.event_id, now=NOW).decision is not WebhookDecision.ACCEPTED:
            raise SystemExit("durable quarantine was not released")
        restarted.close()

        replay_check = SyntheticSQLiteWebhookInbox(path, key_registry())
        if replay_check.submit(first, received_at=NOW).decision is not WebhookDecision.DUPLICATE:
            raise SystemExit("restart replay was not detected")
        report = replay_check.evidence()
        replay_check.close()

    if (
        report["receipt_chain_valid"] is not True
        or report["restart_replay_control_present"] is not True
        or report["payment_state_automatically_changed"] is not False
        or report["money_movement_executed"] is not False
        or report["production_activation_allowed"] is not False
    ):
        raise SystemExit("durable webhook inbox evidence boundary failed")
    output = ROOT / "build/synthetic-durable-webhook-inbox-evidence.json"
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode("utf-8")).hexdigest()
    output.with_suffix(".json.sha256").write_text(digest + "\n", encoding="ascii")
    print(f"synthetic durable webhook inbox: PASS {digest}")


if __name__ == "__main__":
    main()
