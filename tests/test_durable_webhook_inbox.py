from __future__ import annotations

import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.durable_webhook_inbox import SyntheticSQLiteWebhookInbox
from nurion_pg.webhook_intake import (
    SyntheticKeyRegistry,
    SyntheticVerificationKey,
    WebhookDecision,
    WebhookEnvelope,
    WebhookEventType,
    sign_envelope,
)


NOW = datetime(2026, 9, 17, tzinfo=UTC)
SECRET = "synthetic:durable-webhook-secret:unit-tests:0001"


def registry() -> SyntheticKeyRegistry:
    value = SyntheticKeyRegistry()
    value.register(
        SyntheticVerificationKey(
            "durable-provider.invalid",
            "synthetic:key:durable:1",
            SECRET,
            NOW - timedelta(days=1),
            NOW + timedelta(days=1),
        )
    )
    return value


def envelope(
    *,
    event_id: str = "synthetic:event:durable:1",
    nonce: str = "synthetic:nonce:durable:1",
    sequence: int = 1,
    outcome: str = "SUCCEEDED",
) -> WebhookEnvelope:
    value = WebhookEnvelope(
        "durable-provider.invalid",
        "synthetic:key:durable:1",
        event_id,
        nonce,
        "synthetic:intent:durable:1",
        sequence,
        WebhookEventType.AUTHORIZATION_RESULT,
        NOW,
        {
            "intent_id": "synthetic:intent:durable:1",
            "expected_version": sequence,
            "outcome": outcome,
        },
        "sha256=" + "0" * 64,
    )
    return replace(value, signature=sign_envelope(value, SECRET))


class DurableWebhookInboxTests(unittest.TestCase):
    def test_only_synthetic_sqlite_targets_are_allowed(self):
        SyntheticSQLiteWebhookInbox(":memory:", registry()).close()
        for target in ("payments.sqlite3", "file:synthetic-test.sqlite3", "postgres://db"):
            with self.assertRaises(GovernanceRejected):
                SyntheticSQLiteWebhookInbox(target, registry())

    def test_acceptance_is_durable_without_payment_application(self):
        inbox = SyntheticSQLiteWebhookInbox(":memory:", registry())
        receipt = inbox.submit(envelope(), received_at=NOW)
        self.assertEqual(receipt.decision, WebhookDecision.ACCEPTED)
        report = inbox.evidence()
        self.assertTrue(report["receipt_chain_valid"])
        self.assertFalse(report["payment_state_automatically_changed"])
        self.assertFalse(report["money_movement_executed"])
        inbox.close()

    def test_restart_preserves_duplicate_nonce_and_sequence_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic-restart.sqlite3"
            first = SyntheticSQLiteWebhookInbox(path, registry())
            value = envelope()
            first.submit(value, received_at=NOW)
            first.close()

            restarted = SyntheticSQLiteWebhookInbox(path, registry())
            self.assertEqual(
                restarted.submit(value, received_at=NOW).decision,
                WebhookDecision.DUPLICATE,
            )
            nonce_replay = envelope(
                event_id="synthetic:event:durable:nonce-replay",
                nonce=value.nonce,
                sequence=2,
            )
            self.assertEqual(
                restarted.submit(nonce_replay, received_at=NOW).decision,
                WebhookDecision.BLOCKED,
            )
            second = envelope(
                event_id="synthetic:event:durable:2",
                nonce="synthetic:nonce:durable:2",
                sequence=2,
            )
            self.assertEqual(
                restarted.submit(second, received_at=NOW).decision,
                WebhookDecision.ACCEPTED,
            )
            self.assertTrue(restarted.verify_receipt_chain())
            restarted.close()

    def test_quarantine_survives_restart_and_releases_in_order(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic-quarantine.sqlite3"
            inbox = SyntheticSQLiteWebhookInbox(path, registry())
            second = envelope(
                event_id="synthetic:event:durable:2",
                nonce="synthetic:nonce:durable:2",
                sequence=2,
            )
            self.assertEqual(
                inbox.submit(second, received_at=NOW).decision,
                WebhookDecision.QUARANTINED,
            )
            inbox.close()

            restarted = SyntheticSQLiteWebhookInbox(path, registry())
            restarted.submit(envelope(), received_at=NOW)
            self.assertEqual(
                restarted.retry_quarantined(second.event_id, now=NOW).decision,
                WebhookDecision.ACCEPTED,
            )
            self.assertEqual(
                restarted.current_decision(second.event_id),
                WebhookDecision.ACCEPTED,
            )
            restarted.close()

    def test_expired_quarantine_is_blocked_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic-expired.sqlite3"
            inbox = SyntheticSQLiteWebhookInbox(path, registry())
            second = envelope(
                event_id="synthetic:event:durable:2",
                nonce="synthetic:nonce:durable:2",
                sequence=2,
            )
            inbox.submit(second, received_at=NOW)
            inbox.close()
            restarted = SyntheticSQLiteWebhookInbox(path, registry())
            receipt = restarted.retry_quarantined(
                second.event_id, now=NOW + timedelta(minutes=11)
            )
            self.assertEqual(receipt.decision, WebhookDecision.BLOCKED)
            restarted.close()

    def test_tampered_persisted_quarantine_fails_closed_and_is_receipted(self):
        inbox = SyntheticSQLiteWebhookInbox(":memory:", registry())
        second = envelope(
            event_id="synthetic:event:durable:2",
            nonce="synthetic:nonce:durable:2",
            sequence=2,
        )
        inbox.submit(second, received_at=NOW)
        inbox._connection.execute(
            "UPDATE synthetic_webhook_events SET payload_json = '{' WHERE event_id = ?",
            (second.event_id,),
        )
        receipt = inbox.retry_quarantined(second.event_id, now=NOW)
        self.assertEqual(receipt.decision, WebhookDecision.BLOCKED)
        self.assertEqual(receipt.reason, "stored_envelope_corruption")
        self.assertEqual(
            inbox.current_decision(second.event_id), WebhookDecision.BLOCKED
        )
        self.assertTrue(inbox.verify_receipt_chain())
        inbox.close()

    def test_event_id_and_aggregate_sequence_collisions_are_blocked(self):
        inbox = SyntheticSQLiteWebhookInbox(":memory:", registry())
        first = envelope()
        inbox.submit(first, received_at=NOW)
        collision = envelope(outcome="FAILED")
        self.assertEqual(
            inbox.submit(collision, received_at=NOW).reason,
            "event_id_collision",
        )
        sequence_collision = envelope(
            event_id="synthetic:event:durable:other",
            nonce="synthetic:nonce:durable:other",
            sequence=1,
        )
        self.assertEqual(
            inbox.submit(sequence_collision, received_at=NOW).reason,
            "aggregate_sequence_collision",
        )
        inbox.close()

    def test_tampered_signature_is_receipted_but_not_stored_as_event(self):
        inbox = SyntheticSQLiteWebhookInbox(":memory:", registry())
        bad = replace(envelope(), signature="sha256=" + "f" * 64)
        receipt = inbox.submit(bad, received_at=NOW)
        self.assertEqual(receipt.decision, WebhookDecision.BLOCKED)
        with self.assertRaises(GovernanceRejected):
            inbox.current_decision(bad.event_id)
        self.assertEqual(inbox.evidence()["receipt_count"], 1)
        inbox.close()

    def test_receipt_failure_rolls_back_event_and_cursor_atomically(self):
        inbox = SyntheticSQLiteWebhookInbox(":memory:", registry())
        inbox._connection.executescript(
            """
            CREATE TRIGGER synthetic_test_fail_receipt
            BEFORE INSERT ON synthetic_webhook_receipts
            BEGIN SELECT RAISE(ABORT, 'synthetic receipt failure'); END;
            """
        )
        with self.assertRaises(GovernanceRejected):
            inbox.submit(envelope(), received_at=NOW)
        inbox._connection.execute("DROP TRIGGER synthetic_test_fail_receipt")
        self.assertEqual(
            inbox.submit(envelope(), received_at=NOW).decision,
            WebhookDecision.ACCEPTED,
        )
        inbox.close()

    def test_two_connections_serialize_exact_duplicate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic-concurrent.sqlite3"
            first = SyntheticSQLiteWebhookInbox(path, registry())
            second = SyntheticSQLiteWebhookInbox(path, registry())
            value = envelope()
            with ThreadPoolExecutor(max_workers=2) as pool:
                decisions = list(
                    pool.map(
                        lambda inbox: inbox.submit(value, received_at=NOW).decision,
                        (first, second),
                    )
                )
            self.assertEqual(decisions.count(WebhookDecision.ACCEPTED), 1)
            self.assertEqual(decisions.count(WebhookDecision.DUPLICATE), 1)
            self.assertTrue(first.verify_receipt_chain())
            first.close()
            second.close()

    def test_receipt_chain_detects_database_tampering(self):
        inbox = SyntheticSQLiteWebhookInbox(":memory:", registry())
        inbox.submit(envelope(), received_at=NOW)
        inbox._connection.execute(
            "UPDATE synthetic_webhook_receipts SET reason = 'tampered' WHERE receipt_sequence = 1"
        )
        self.assertFalse(inbox.verify_receipt_chain())
        inbox.close()

    def test_receipt_chain_covers_recorded_time(self):
        inbox = SyntheticSQLiteWebhookInbox(":memory:", registry())
        inbox.submit(envelope(), received_at=NOW)
        inbox._connection.execute(
            "UPDATE synthetic_webhook_receipts SET recorded_at = ? WHERE receipt_sequence = 1",
            ((NOW + timedelta(seconds=1)).isoformat(),),
        )
        self.assertFalse(inbox.verify_receipt_chain())
        inbox.close()


if __name__ == "__main__":
    unittest.main()
