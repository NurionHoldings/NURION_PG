from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.payment_lifecycle import PaymentEngine, PaymentEvent, PaymentState


NOW = datetime(2026, 9, 17, tzinfo=UTC)
POLICY = sha256(b"policy").hexdigest()


def create(engine: PaymentEngine, *, suffix: str = "1"):
    return engine.create(
        intent_id=f"synthetic:intent:{suffix}",
        merchant_ref="synthetic:merchant:1",
        customer_ref="synthetic:customer:1",
        amount_minor=10000,
        currency="KRW",
        policy_digest=POLICY,
        idempotency_key=f"synthetic:create:{suffix}",
        now=NOW,
    )


def captured(engine: PaymentEngine, *, suffix: str = "1"):
    create(engine, suffix=suffix)
    engine.authorize(
        f"synthetic:intent:{suffix}",
        expected_version=1,
        idempotency_key=f"synthetic:authorize:{suffix}",
        now=NOW + timedelta(seconds=1),
    )
    return engine.capture(
        f"synthetic:intent:{suffix}",
        expected_version=2,
        idempotency_key=f"synthetic:capture:{suffix}",
        now=NOW + timedelta(seconds=2),
    )


class PaymentLifecycleTests(unittest.TestCase):
    def test_create_requires_synthetic_identifiers_and_never_external_execution(self):
        engine = PaymentEngine()
        create(engine)
        value = engine.get("synthetic:intent:1")
        self.assertEqual(value.state, PaymentState.CREATED)
        self.assertFalse(value.external_execution_allowed)
        with self.assertRaises(GovernanceRejected):
            engine.create(
                intent_id="real-intent",
                merchant_ref="synthetic:merchant",
                customer_ref="synthetic:customer",
                amount_minor=1,
                currency="KRW",
                policy_digest=POLICY,
                idempotency_key="synthetic:create:real",
                now=NOW,
            )

    def test_authorize_is_versioned_and_idempotent(self):
        engine = PaymentEngine()
        create(engine)
        first = engine.authorize(
            "synthetic:intent:1", expected_version=1,
            idempotency_key="synthetic:authorize:1", now=NOW,
        )
        replay = engine.authorize(
            "synthetic:intent:1", expected_version=1,
            idempotency_key="synthetic:authorize:1", now=NOW + timedelta(hours=1),
        )
        self.assertIs(first, replay)
        self.assertEqual(len(engine.events), 2)
        with self.assertRaises(GovernanceRejected):
            engine.authorize(
                "synthetic:intent:1", expected_version=2,
                idempotency_key="synthetic:authorize:1", now=NOW,
            )

    def test_invalid_command_metadata_is_rejected_before_state_mutation(self):
        engine = PaymentEngine()
        with self.assertRaises(GovernanceRejected):
            engine.create(
                intent_id="synthetic:intent:bad-time",
                merchant_ref="synthetic:merchant:1",
                customer_ref="synthetic:customer:1",
                amount_minor=100,
                currency="KRW",
                policy_digest=POLICY,
                idempotency_key="synthetic:create:bad-time",
                now=datetime(2026, 9, 17),
            )
        with self.assertRaises(GovernanceRejected):
            engine.get("synthetic:intent:bad-time")
        create(engine)
        with self.assertRaises(GovernanceRejected):
            engine.authorize(
                "synthetic:intent:1", expected_version=1,
                idempotency_key="not-synthetic", now=NOW,
            )
        self.assertEqual(engine.get("synthetic:intent:1").state, PaymentState.CREATED)

    def test_returned_intent_is_a_snapshot_not_mutable_engine_state(self):
        engine = PaymentEngine()
        create(engine)
        snapshot = engine.get("synthetic:intent:1")
        snapshot.state = PaymentState.CANCELLED
        self.assertEqual(engine.get("synthetic:intent:1").state, PaymentState.CREATED)

    def test_stale_version_and_invalid_transition_are_rejected(self):
        engine = PaymentEngine()
        create(engine)
        with self.assertRaises(GovernanceRejected):
            engine.authorize(
                "synthetic:intent:1", expected_version=0,
                idempotency_key="synthetic:authorize:stale", now=NOW,
            )
        with self.assertRaises(GovernanceRejected):
            engine.capture(
                "synthetic:intent:1", expected_version=1,
                idempotency_key="synthetic:capture:early", now=NOW,
            )

    def test_concurrent_authorizations_allow_exactly_one_version_winner(self):
        engine = PaymentEngine()
        create(engine)

        def authorize(number: int) -> str:
            try:
                engine.authorize(
                    "synthetic:intent:1",
                    expected_version=1,
                    idempotency_key=f"synthetic:authorize:race:{number}",
                    now=NOW,
                )
                return "accepted"
            except GovernanceRejected:
                return "rejected"

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(authorize, range(8)))
        self.assertEqual(results.count("accepted"), 1)
        self.assertEqual(results.count("rejected"), 7)
        self.assertEqual(engine.get("synthetic:intent:1").version, 2)
        self.assertTrue(engine.verify_event_chains())

    def test_capture_posts_one_balanced_synthetic_journal(self):
        engine = PaymentEngine()
        captured(engine)
        intent = engine.get("synthetic:intent:1")
        self.assertEqual(intent.state, PaymentState.SYNTHETIC_CAPTURED)
        self.assertEqual(intent.captured_minor, 10000)
        self.assertEqual(len(engine.ledger.journals), 1)
        self.assertFalse(engine.ledger.evidence()["money_movement_executed"])

    def test_cancel_before_capture_and_reject_after_capture(self):
        engine = PaymentEngine()
        create(engine)
        engine.cancel(
            "synthetic:intent:1", expected_version=1,
            idempotency_key="synthetic:cancel:1", now=NOW,
        )
        self.assertEqual(engine.get("synthetic:intent:1").state, PaymentState.CANCELLED)
        with self.assertRaises(GovernanceRejected):
            engine.authorize(
                "synthetic:intent:1", expected_version=2,
                idempotency_key="synthetic:authorize:cancelled", now=NOW,
            )
        other = PaymentEngine()
        captured(other)
        with self.assertRaises(GovernanceRejected):
            other.cancel(
                "synthetic:intent:1", expected_version=3,
                idempotency_key="synthetic:cancel:captured", now=NOW,
            )

    def test_partial_then_full_refund_posts_balanced_journals(self):
        engine = PaymentEngine()
        captured(engine)
        engine.refund(
            "synthetic:intent:1", amount_minor=2500, expected_version=3,
            idempotency_key="synthetic:refund:1", now=NOW,
        )
        self.assertEqual(engine.get("synthetic:intent:1").state, PaymentState.PARTIALLY_REFUNDED)
        engine.refund(
            "synthetic:intent:1", amount_minor=7500, expected_version=4,
            idempotency_key="synthetic:refund:2", now=NOW,
        )
        intent = engine.get("synthetic:intent:1")
        self.assertEqual(intent.state, PaymentState.REFUNDED)
        self.assertEqual(intent.refunded_minor, 10000)
        self.assertEqual(len(engine.ledger.journals), 3)

    def test_refund_before_capture_zero_and_over_refund_are_rejected(self):
        engine = PaymentEngine()
        create(engine)
        with self.assertRaises(GovernanceRejected):
            engine.refund(
                "synthetic:intent:1", amount_minor=1, expected_version=1,
                idempotency_key="synthetic:refund:early", now=NOW,
            )
        engine = PaymentEngine()
        captured(engine)
        for amount in (0, 10001):
            with self.assertRaises(GovernanceRejected):
                engine.refund(
                    "synthetic:intent:1", amount_minor=amount, expected_version=3,
                    idempotency_key=f"synthetic:refund:{amount}", now=NOW,
                )

    def test_refund_idempotency_replay_does_not_duplicate_ledger(self):
        engine = PaymentEngine()
        captured(engine)
        first = engine.refund(
            "synthetic:intent:1", amount_minor=1000, expected_version=3,
            idempotency_key="synthetic:refund:replay", now=NOW,
        )
        replay = engine.refund(
            "synthetic:intent:1", amount_minor=1000, expected_version=3,
            idempotency_key="synthetic:refund:replay", now=NOW + timedelta(days=1),
        )
        self.assertIs(first, replay)
        self.assertEqual(len(engine.ledger.journals), 2)

    def test_event_chain_is_deterministic_and_detects_tampering(self):
        engine = PaymentEngine()
        captured(engine)
        self.assertTrue(engine.verify_event_chains())
        original = engine._events[1]
        engine._events[1] = PaymentEvent(
            original.sequence,
            original.intent_id,
            original.version,
            original.event_type,
            original.resulting_state,
            original.amount_minor + 1,
            original.idempotency_key,
            original.occurred_at,
            original.payload_digest,
            original.previous_digest,
            original.event_digest,
        )
        self.assertFalse(engine.verify_event_chains())

    def test_evidence_confirms_no_provider_credentials_or_real_money(self):
        engine = PaymentEngine()
        captured(engine)
        report = engine.evidence()
        self.assertFalse(report["provider_adapter_present"])
        self.assertFalse(report["credentials_accessed"])
        self.assertFalse(report["real_money_moved"])
        self.assertFalse(report["production_activation_allowed"])


if __name__ == "__main__":
    unittest.main()
