from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.webhook_intake import (
    SyntheticKeyRegistry,
    SyntheticVerificationKey,
    SyntheticWebhookIntake,
    WebhookDecision,
    WebhookEnvelope,
    WebhookEventType,
    sign_envelope,
)


NOW = datetime(2026, 9, 17, tzinfo=UTC)
SECRET = "synthetic:webhook-secret:unit-tests:0001"


def registry(*, revoked: bool = False) -> SyntheticKeyRegistry:
    value = SyntheticKeyRegistry()
    value.register(
        SyntheticVerificationKey(
            "provider.invalid",
            "synthetic:key:1",
            SECRET,
            NOW - timedelta(days=1),
            NOW + timedelta(days=1),
            revoked=revoked,
        )
    )
    return value


def envelope(
    *,
    event_id: str = "synthetic:event:1",
    nonce: str = "synthetic:nonce:1",
    sequence: int = 1,
    event_type: WebhookEventType = WebhookEventType.AUTHORIZATION_RESULT,
    occurred_at: datetime = NOW,
    payload: dict | None = None,
) -> WebhookEnvelope:
    if payload is None:
        payload = {
            "intent_id": "synthetic:intent:1",
            "expected_version": sequence,
            "outcome": "SUCCEEDED",
            **(
                {"amount_minor": 1000}
                if event_type in {WebhookEventType.CAPTURE_RESULT, WebhookEventType.REFUND_RESULT}
                else {}
            ),
        }
    value = WebhookEnvelope(
        "provider.invalid",
        "synthetic:key:1",
        event_id,
        nonce,
        "synthetic:intent:1",
        sequence,
        event_type,
        occurred_at,
        payload,
        "sha256=" + "0" * 64,
    )
    return replace(value, signature=sign_envelope(value, SECRET))


class WebhookIntakeTests(unittest.TestCase):
    def test_valid_signature_is_accepted_without_payment_application(self):
        intake = SyntheticWebhookIntake(registry())
        receipt = intake.ingest(envelope(), received_at=NOW)
        self.assertEqual(receipt.decision, WebhookDecision.ACCEPTED)
        report = intake.evidence()
        self.assertFalse(report["payment_state_automatically_changed"])
        self.assertFalse(report["network_listener_present"])

    def test_signature_tampering_unknown_revoked_and_expired_keys_are_blocked(self):
        bad = replace(envelope(), signature="sha256=" + "f" * 64)
        self.assertEqual(
            SyntheticWebhookIntake(registry()).ingest(bad, received_at=NOW).decision,
            WebhookDecision.BLOCKED,
        )
        unknown = replace(envelope(), key_id="synthetic:key:unknown")
        unknown = replace(unknown, signature=sign_envelope(unknown, SECRET))
        self.assertEqual(
            SyntheticWebhookIntake(registry()).ingest(unknown, received_at=NOW).decision,
            WebhookDecision.BLOCKED,
        )
        self.assertEqual(
            SyntheticWebhookIntake(registry(revoked=True)).ingest(envelope(), received_at=NOW).decision,
            WebhookDecision.BLOCKED,
        )
        expired_registry = SyntheticKeyRegistry()
        expired_registry.register(
            SyntheticVerificationKey(
                "provider.invalid", "synthetic:key:1", SECRET,
                NOW - timedelta(days=2), NOW - timedelta(days=1),
            )
        )
        self.assertEqual(
            SyntheticWebhookIntake(expired_registry).ingest(envelope(), received_at=NOW).decision,
            WebhookDecision.BLOCKED,
        )

    def test_exact_duplicate_is_idempotent_but_event_id_collision_is_blocked(self):
        intake = SyntheticWebhookIntake(registry())
        value = envelope()
        self.assertEqual(intake.ingest(value, received_at=NOW).decision, WebhookDecision.ACCEPTED)
        self.assertEqual(intake.ingest(value, received_at=NOW).decision, WebhookDecision.DUPLICATE)
        collision = envelope(payload={
            "intent_id": "synthetic:intent:1", "expected_version": 1, "outcome": "FAILED"
        })
        self.assertEqual(intake.ingest(collision, received_at=NOW).decision, WebhookDecision.BLOCKED)

    def test_nonce_reuse_with_new_event_is_blocked(self):
        intake = SyntheticWebhookIntake(registry())
        self.assertEqual(intake.ingest(envelope(), received_at=NOW).decision, WebhookDecision.ACCEPTED)
        replay = envelope(event_id="synthetic:event:2", nonce="synthetic:nonce:1", sequence=2)
        self.assertEqual(intake.ingest(replay, received_at=NOW).decision, WebhookDecision.BLOCKED)

    def test_sequence_gap_is_quarantined_then_released_in_order(self):
        intake = SyntheticWebhookIntake(registry())
        second = envelope(event_id="synthetic:event:2", nonce="synthetic:nonce:2", sequence=2)
        self.assertEqual(intake.ingest(second, received_at=NOW).decision, WebhookDecision.QUARANTINED)
        first = envelope()
        self.assertEqual(intake.ingest(first, received_at=NOW).decision, WebhookDecision.ACCEPTED)
        self.assertEqual(
            intake.retry_quarantined(second.event_id, now=NOW).decision,
            WebhookDecision.ACCEPTED,
        )
        self.assertEqual(intake.evidence()["accepted_event_ids"], [first.event_id, second.event_id])

    def test_sequence_replay_and_unresolved_gap_fail_closed(self):
        intake = SyntheticWebhookIntake(registry())
        third = envelope(event_id="synthetic:event:3", nonce="synthetic:nonce:3", sequence=3)
        intake.ingest(third, received_at=NOW)
        self.assertEqual(
            intake.retry_quarantined(third.event_id, now=NOW).decision,
            WebhookDecision.QUARANTINED,
        )
        first = envelope()
        intake.ingest(first, received_at=NOW)
        replay = envelope(event_id="synthetic:event:old", nonce="synthetic:nonce:old", sequence=1)
        self.assertEqual(intake.ingest(replay, received_at=NOW).decision, WebhookDecision.BLOCKED)

    def test_quarantined_event_expires_and_naive_retry_time_is_rejected(self):
        intake = SyntheticWebhookIntake(registry())
        second = envelope(event_id="synthetic:event:2", nonce="synthetic:nonce:2", sequence=2)
        intake.ingest(second, received_at=NOW)
        with self.assertRaises(GovernanceRejected):
            intake.retry_quarantined(second.event_id, now=datetime(2026, 9, 17))
        receipt = intake.retry_quarantined(second.event_id, now=NOW + timedelta(minutes=11))
        self.assertEqual(receipt.decision, WebhookDecision.BLOCKED)
        self.assertEqual(receipt.reason, "expired_or_future_event")

    def test_expired_future_and_naive_receipt_times_are_rejected(self):
        intake = SyntheticWebhookIntake(registry())
        old = envelope(occurred_at=NOW - timedelta(hours=1))
        self.assertEqual(intake.ingest(old, received_at=NOW).decision, WebhookDecision.BLOCKED)
        future = envelope(occurred_at=NOW + timedelta(minutes=2))
        self.assertEqual(intake.ingest(future, received_at=NOW).decision, WebhookDecision.BLOCKED)
        with self.assertRaises(GovernanceRejected):
            intake.ingest(envelope(), received_at=datetime(2026, 9, 17))

    def test_payload_schema_amount_and_pii_fields_are_blocked(self):
        invalid_payloads = (
            {"intent_id": "synthetic:intent:1", "expected_version": 1, "outcome": "SUCCEEDED", "email": "x@example.invalid"},
            {"intent_id": "real-intent", "expected_version": 1, "outcome": "SUCCEEDED"},
            {"intent_id": "synthetic:intent:1", "expected_version": True, "outcome": "SUCCEEDED"},
        )
        for number, payload in enumerate(invalid_payloads):
            value = envelope(event_id=f"synthetic:event:bad:{number}", nonce=f"synthetic:nonce:bad:{number}", payload=payload)
            self.assertEqual(
                SyntheticWebhookIntake(registry()).ingest(value, received_at=NOW).decision,
                WebhookDecision.BLOCKED,
            )
        capture = envelope(event_type=WebhookEventType.CAPTURE_RESULT, payload={
            "intent_id": "synthetic:intent:1", "expected_version": 1,
            "outcome": "SUCCEEDED", "amount_minor": 0,
        })
        self.assertEqual(
            SyntheticWebhookIntake(registry()).ingest(capture, received_at=NOW).decision,
            WebhookDecision.BLOCKED,
        )

    def test_payload_is_immutable_and_actual_encoded_size_is_bounded(self):
        source = {
            "intent_id": "synthetic:intent:1",
            "expected_version": 1,
            "outcome": "SUCCEEDED",
        }
        value = envelope(payload=source)
        source["outcome"] = "FAILED"
        self.assertEqual(value.payload["outcome"], "SUCCEEDED")
        with self.assertRaises(TypeError):
            value.payload["outcome"] = "FAILED"
        self.assertEqual(
            SyntheticWebhookIntake(registry(), max_payload_bytes=32)
            .ingest(value, received_at=NOW)
            .reason,
            "payload_too_large",
        )
        with self.assertRaises(GovernanceRejected):
            envelope(payload={
                "intent_id": "synthetic:intent:1",
                "expected_version": 1,
                "outcome": object(),
            })

    def test_concurrent_exact_replays_have_one_acceptance(self):
        intake = SyntheticWebhookIntake(registry())
        value = envelope()
        with ThreadPoolExecutor(max_workers=8) as pool:
            decisions = list(
                pool.map(lambda _: intake.ingest(value, received_at=NOW).decision, range(8))
            )
        self.assertEqual(decisions.count(WebhookDecision.ACCEPTED), 1)
        self.assertEqual(decisions.count(WebhookDecision.DUPLICATE), 7)
        self.assertTrue(intake.verify_receipts())

    def test_real_provider_and_automatic_application_envelopes_are_rejected(self):
        with self.assertRaises(GovernanceRejected):
            replace(envelope(), provider_id="real-provider.example.com")
        with self.assertRaises(GovernanceRejected):
            replace(envelope(), automatic_application_allowed=True)

    def test_receipt_chain_detects_tampering(self):
        intake = SyntheticWebhookIntake(registry())
        intake.ingest(envelope(), received_at=NOW)
        intake.ingest(envelope(), received_at=NOW)
        self.assertTrue(intake.verify_receipts())
        first = intake.receipts[0]
        intake.receipts[0] = replace(first, reason="tampered")
        self.assertFalse(intake.verify_receipts())


if __name__ == "__main__":
    unittest.main()
