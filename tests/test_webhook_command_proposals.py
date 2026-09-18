from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.durable_webhook_inbox import SyntheticSQLiteWebhookInbox
from nurion_pg.payment_lifecycle import PaymentEngine, PaymentState
from nurion_pg.webhook_command_proposals import (
    ProposalDecision,
    ProposedPaymentCommand,
    SyntheticWebhookProposalBook,
)
from nurion_pg.webhook_intake import (
    SyntheticKeyRegistry,
    SyntheticVerificationKey,
    WebhookDecision,
    WebhookEnvelope,
    WebhookEventType,
    sign_envelope,
)


NOW = datetime(2026, 9, 17, tzinfo=UTC)
SECRET = "synthetic:webhook-proposal-secret:unit-tests:0001"
POLICY = sha256(b"synthetic proposal policy").hexdigest()


def key_registry() -> SyntheticKeyRegistry:
    registry = SyntheticKeyRegistry()
    registry.register(
        SyntheticVerificationKey(
            "proposal-provider.invalid",
            "synthetic:key:proposal:1",
            SECRET,
            NOW - timedelta(days=1),
            NOW + timedelta(days=1),
        )
    )
    return registry


def engine(*, suffix: str = "1", amount_minor: int = 1000) -> PaymentEngine:
    value = PaymentEngine()
    value.create(
        intent_id=f"synthetic:intent:proposal:{suffix}",
        merchant_ref="synthetic:merchant:proposal",
        customer_ref="synthetic:customer:proposal",
        amount_minor=amount_minor,
        currency="KRW",
        policy_digest=POLICY,
        idempotency_key=f"synthetic:create:proposal:{suffix}",
        now=NOW,
    )
    return value


def envelope(
    *,
    event_id: str = "synthetic:event:proposal:1",
    intent_id: str = "synthetic:intent:proposal:1",
    event_type: WebhookEventType = WebhookEventType.AUTHORIZATION_RESULT,
    outcome: str = "SUCCEEDED",
    expected_version: int = 1,
    amount_minor: int = 1000,
    sequence: int = 1,
) -> WebhookEnvelope:
    value = WebhookEnvelope(
        "proposal-provider.invalid",
        "synthetic:key:proposal:1",
        event_id,
        f"synthetic:nonce:{event_id}",
        intent_id,
        sequence,
        event_type,
        NOW,
        {
            "intent_id": intent_id,
            "expected_version": expected_version,
            "outcome": outcome,
            **(
                {"amount_minor": amount_minor}
                if event_type in {WebhookEventType.CAPTURE_RESULT, WebhookEventType.REFUND_RESULT}
                else {}
            ),
        },
        "sha256=" + "0" * 64,
    )
    return replace(value, signature=sign_envelope(value, SECRET))


def accepted_inbox(value: WebhookEnvelope) -> SyntheticSQLiteWebhookInbox:
    inbox = SyntheticSQLiteWebhookInbox(":memory:", key_registry())
    receipt = inbox.submit(value, received_at=NOW)
    if receipt.decision is not WebhookDecision.ACCEPTED:
        raise AssertionError("fixture must be accepted")
    return inbox


class WebhookCommandProposalTests(unittest.TestCase):
    def test_authorization_result_creates_review_only_proposal_without_state_change(self):
        payment = engine()
        inbox = accepted_inbox(envelope())
        assessment = SyntheticWebhookProposalBook().assess(
            inbox, payment, "synthetic:event:proposal:1", now=NOW
        )
        self.assertEqual(assessment.decision, ProposalDecision.PROPOSED_FOR_HUMAN_REVIEW)
        self.assertEqual(assessment.proposal.command, ProposedPaymentCommand.AUTHORIZE)
        self.assertTrue(assessment.proposal.review_required)
        self.assertFalse(assessment.proposal.execution_allowed)
        self.assertFalse(assessment.proposal.automatic_application_allowed)
        self.assertEqual(payment.get("synthetic:intent:proposal:1").state, PaymentState.CREATED)
        inbox.close()

    def test_quarantined_or_unknown_source_cannot_create_proposal(self):
        payment = engine()
        second = envelope(sequence=2)
        inbox = SyntheticSQLiteWebhookInbox(":memory:", key_registry())
        inbox.submit(second, received_at=NOW)
        with self.assertRaises(GovernanceRejected):
            SyntheticWebhookProposalBook().assess(inbox, payment, second.event_id, now=NOW)
        with self.assertRaises(GovernanceRejected):
            SyntheticWebhookProposalBook().assess(
                inbox, payment, "synthetic:event:missing", now=NOW
            )
        inbox.close()

    def test_failed_outcome_and_unknown_intent_do_not_create_commands(self):
        failed = envelope(outcome="FAILED")
        inbox = accepted_inbox(failed)
        assessment = SyntheticWebhookProposalBook().assess(
            inbox, engine(), failed.event_id, now=NOW
        )
        self.assertEqual(assessment.decision, ProposalDecision.HUMAN_REVIEW)
        self.assertIsNone(assessment.proposal)
        inbox.close()

    def test_stale_source_event_requires_human_review_without_proposal(self):
        value = envelope()
        inbox = accepted_inbox(value)
        assessment = SyntheticWebhookProposalBook().assess(
            inbox,
            engine(),
            value.event_id,
            now=NOW + timedelta(minutes=11),
        )
        self.assertEqual(assessment.decision, ProposalDecision.HUMAN_REVIEW)
        self.assertEqual(assessment.reason, "stale_or_future_source_event")
        self.assertIsNone(assessment.proposal)
        inbox.close()

        missing = envelope(intent_id="synthetic:intent:proposal:missing")
        inbox = accepted_inbox(missing)
        assessment = SyntheticWebhookProposalBook().assess(
            inbox, engine(), missing.event_id, now=NOW
        )
        self.assertEqual(assessment.decision, ProposalDecision.BLOCKED)
        self.assertIsNone(assessment.proposal)
        inbox.close()

    def test_version_and_state_mismatches_require_human_review(self):
        payment = engine()
        stale = envelope(expected_version=2)
        inbox = accepted_inbox(stale)
        assessment = SyntheticWebhookProposalBook().assess(
            inbox, payment, stale.event_id, now=NOW
        )
        self.assertEqual(assessment.reason, "payment_intent_version_mismatch")
        inbox.close()

        payment.authorize(
            "synthetic:intent:proposal:1",
            expected_version=1,
            idempotency_key="synthetic:authorize:proposal:1",
            now=NOW,
        )
        wrong_state = envelope(expected_version=2)
        inbox = accepted_inbox(wrong_state)
        assessment = SyntheticWebhookProposalBook().assess(
            inbox, payment, wrong_state.event_id, now=NOW
        )
        self.assertEqual(assessment.reason, "authorization_state_mismatch")
        inbox.close()

    def test_capture_amount_and_refund_remaining_are_checked(self):
        payment = engine()
        payment.authorize(
            "synthetic:intent:proposal:1",
            expected_version=1,
            idempotency_key="synthetic:authorize:proposal:1",
            now=NOW,
        )
        capture = envelope(
            event_type=WebhookEventType.CAPTURE_RESULT,
            expected_version=2,
            amount_minor=999,
        )
        inbox = accepted_inbox(capture)
        assessment = SyntheticWebhookProposalBook().assess(
            inbox, payment, capture.event_id, now=NOW
        )
        self.assertEqual(assessment.reason, "full_capture_amount_mismatch")
        inbox.close()

        payment.capture(
            "synthetic:intent:proposal:1",
            expected_version=2,
            idempotency_key="synthetic:capture:proposal:1",
            now=NOW,
        )
        refund = envelope(
            event_type=WebhookEventType.REFUND_RESULT,
            expected_version=3,
            amount_minor=1001,
        )
        inbox = accepted_inbox(refund)
        assessment = SyntheticWebhookProposalBook().assess(
            inbox, payment, refund.event_id, now=NOW
        )
        self.assertEqual(assessment.reason, "refund_amount_mismatch")
        inbox.close()

    def test_valid_capture_cancel_and_refund_mappings_are_drafts_only(self):
        cases = []
        capture_engine = engine(suffix="capture")
        capture_engine.authorize(
            "synthetic:intent:proposal:capture", expected_version=1,
            idempotency_key="synthetic:authorize:proposal:capture", now=NOW,
        )
        cases.append((
            capture_engine,
            envelope(
                event_id="synthetic:event:proposal:capture",
                intent_id="synthetic:intent:proposal:capture",
                event_type=WebhookEventType.CAPTURE_RESULT,
                expected_version=2,
            ),
            ProposedPaymentCommand.CAPTURE,
        ))
        cancel_engine = engine(suffix="cancel")
        cases.append((
            cancel_engine,
            envelope(
                event_id="synthetic:event:proposal:cancel",
                intent_id="synthetic:intent:proposal:cancel",
                event_type=WebhookEventType.CANCEL_RESULT,
            ),
            ProposedPaymentCommand.CANCEL,
        ))
        refund_engine = engine(suffix="refund")
        refund_engine.authorize(
            "synthetic:intent:proposal:refund", expected_version=1,
            idempotency_key="synthetic:authorize:proposal:refund", now=NOW,
        )
        refund_engine.capture(
            "synthetic:intent:proposal:refund", expected_version=2,
            idempotency_key="synthetic:capture:proposal:refund", now=NOW,
        )
        cases.append((
            refund_engine,
            envelope(
                event_id="synthetic:event:proposal:refund",
                intent_id="synthetic:intent:proposal:refund",
                event_type=WebhookEventType.REFUND_RESULT,
                expected_version=3,
                amount_minor=500,
            ),
            ProposedPaymentCommand.REFUND,
        ))

        for payment, value, command in cases:
            inbox = accepted_inbox(value)
            before = payment.get(value.aggregate_id)
            assessment = SyntheticWebhookProposalBook().assess(
                inbox, payment, value.event_id, now=NOW
            )
            after = payment.get(value.aggregate_id)
            self.assertEqual(assessment.proposal.command, command)
            self.assertEqual((after.state, after.version), (before.state, before.version))
            inbox.close()

    def test_source_is_idempotent_and_concurrent_assessment_records_once(self):
        payment = engine()
        value = envelope()
        inbox = accepted_inbox(value)
        book = SyntheticWebhookProposalBook()
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(
                pool.map(
                    lambda _: book.assess(inbox, payment, value.event_id, now=NOW),
                    range(8),
                )
            )
        self.assertTrue(all(item is results[0] for item in results))
        self.assertEqual(len(book.assessments), 1)
        self.assertTrue(book.verify_assessment_chain())
        inbox.close()

    def test_tampered_inbox_receipt_chain_blocks_proposal_source(self):
        payment = engine()
        value = envelope()
        inbox = accepted_inbox(value)
        inbox._connection.execute(
            "UPDATE synthetic_webhook_receipts SET reason = 'tampered' WHERE receipt_sequence = 1"
        )
        with self.assertRaises(GovernanceRejected):
            SyntheticWebhookProposalBook().assess(inbox, payment, value.event_id, now=NOW)
        inbox.close()

    def test_evidence_confirms_no_execution_or_state_change(self):
        payment = engine()
        value = envelope()
        inbox = accepted_inbox(value)
        book = SyntheticWebhookProposalBook()
        book.assess(inbox, payment, value.event_id, now=NOW)
        report = book.evidence()
        self.assertTrue(report["assessment_chain_valid"])
        self.assertFalse(report["execution_method_present"])
        self.assertFalse(report["payment_state_automatically_changed"])
        self.assertFalse(report["money_movement_executed"])
        self.assertFalse(report["production_activation_allowed"])
        inbox.close()


if __name__ == "__main__":
    unittest.main()
