from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from nurion_pg.arkaon.governance import GovernanceRejected
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


NOW = datetime(2026, 9, 17, tzinfo=UTC)
SECRET = "synthetic:reconciliation-secret:unit-tests:0001"
POLICY = sha256(b"synthetic reconciliation policy").hexdigest()


def empty_components():
    registry = SyntheticKeyRegistry()
    registry.register(
        SyntheticVerificationKey(
            "reconciliation.invalid",
            "synthetic:key:reconciliation:1",
            SECRET,
            NOW - timedelta(days=1),
            NOW + timedelta(days=1),
        )
    )
    return (
        PaymentEngine(),
        SyntheticSQLiteWebhookInbox(":memory:", registry),
        SyntheticWebhookProposalBook(),
        SyntheticProposalReviewDocket(":memory:"),
    )


def pipeline_components(*, assess: bool = True, docketed: bool = True):
    payment, inbox, book, docket = empty_components()
    payment.create(
        intent_id="synthetic:intent:reconciliation:1",
        merchant_ref="synthetic:merchant:reconciliation",
        customer_ref="synthetic:customer:reconciliation",
        amount_minor=1700,
        currency="KRW",
        policy_digest=POLICY,
        idempotency_key="synthetic:create:reconciliation:1",
        now=NOW,
    )
    unsigned = WebhookEnvelope(
        "reconciliation.invalid",
        "synthetic:key:reconciliation:1",
        "synthetic:event:reconciliation:1",
        "synthetic:nonce:reconciliation:1",
        "synthetic:intent:reconciliation:1",
        1,
        WebhookEventType.AUTHORIZATION_RESULT,
        NOW,
        {
            "intent_id": "synthetic:intent:reconciliation:1",
            "expected_version": 1,
            "outcome": "SUCCEEDED",
        },
        "sha256=" + "0" * 64,
    )
    envelope = replace(unsigned, signature=sign_envelope(unsigned, SECRET))
    inbox.submit(envelope, received_at=NOW)
    assessment = book.assess(inbox, payment, envelope.event_id, now=NOW) if assess else None
    if assessment is not None and docketed:
        docket.submit_from_book(book, envelope.event_id, submitted_at=NOW)
    return payment, inbox, book, docket


def captured_components():
    payment, inbox, book, docket = empty_components()
    payment.create(
        intent_id="synthetic:intent:ledger-reconciliation:1",
        merchant_ref="synthetic:merchant:ledger-reconciliation",
        customer_ref="synthetic:customer:ledger-reconciliation",
        amount_minor=2500,
        currency="KRW",
        policy_digest=POLICY,
        idempotency_key="synthetic:create:ledger-reconciliation:1",
        now=NOW,
    )
    payment.authorize(
        "synthetic:intent:ledger-reconciliation:1",
        expected_version=1,
        idempotency_key="synthetic:authorize:ledger-reconciliation:1",
        now=NOW,
    )
    payment.capture(
        "synthetic:intent:ledger-reconciliation:1",
        expected_version=2,
        idempotency_key="synthetic:capture:ledger-reconciliation:1",
        now=NOW,
    )
    return payment, inbox, book, docket


class ReconciliationMonitorTests(unittest.TestCase):
    def tearDown(self):
        for item in getattr(self, "components", ()):
            if hasattr(item, "close"):
                item.close()

    def inspect(self):
        return SyntheticReconciliationMonitor().inspect(
            *self.components, observed_at=NOW
        )

    def test_complete_pipeline_is_deterministic_and_read_only(self):
        self.components = pipeline_components()
        before = [item.evidence()["report_digest"] for item in self.components]
        first = self.inspect()
        second = self.inspect()
        after = [item.evidence()["report_digest"] for item in self.components]
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "PASS")
        self.assertEqual(first["findings"], [])
        self.assertTrue(first["read_only_verified"])
        self.assertEqual(before, after)
        self.assertFalse(first["automatic_repair_allowed"])
        self.assertFalse(first["operator_decision_recorded"])
        self.assertFalse(first["payment_state_changed"])
        self.assertFalse(first["money_movement_executed"])
        self.assertFalse(first["production_activation_allowed"])

    def test_unassessed_event_and_undocketed_proposal_are_review_warnings(self):
        for components, expected in (
            (pipeline_components(assess=False), "ACCEPTED_EVENT_UNASSESSED"),
            (pipeline_components(docketed=False), "PROPOSAL_MISSING_DOCKET"),
        ):
            self.components = components
            report = self.inspect()
            self.assertEqual(report["status"], "HUMAN_REVIEW")
            self.assertIn(expected, {item["code"] for item in report["findings"]})
            for item in components:
                if hasattr(item, "close"):
                    item.close()
        self.components = ()

    def test_payment_event_chain_tamper_is_blocked(self):
        self.components = captured_components()
        payment = self.components[0]
        payment._events[0] = replace(payment._events[0], event_digest="0" * 64)
        report = self.inspect()
        self.assertEqual(report["status"], "BLOCKED")
        self.assertIn(
            "PAYMENT_EVENT_CHAIN_INVALID", {item["code"] for item in report["findings"]}
        )

    def test_missing_capture_journal_is_blocked(self):
        self.components = captured_components()
        payment = self.components[0]
        payment.ledger._journals.clear()
        payment.ledger._by_idempotency.clear()
        report = self.inspect()
        self.assertIn(
            "PAYMENT_LEDGER_JOURNAL_MISMATCH",
            {item["code"] for item in report["findings"]},
        )

    def test_inbox_receipt_tamper_is_blocked(self):
        self.components = pipeline_components()
        inbox = self.components[1]
        inbox._connection.execute(
            "UPDATE synthetic_webhook_receipts SET reason = 'tampered' WHERE receipt_sequence = 1"
        )
        report = self.inspect()
        codes = {item["code"] for item in report["findings"]}
        self.assertIn("INBOX_RECEIPT_CHAIN_INVALID", codes)
        self.assertIn("INBOX_ACCEPTED_BINDING_INVALID", codes)

    def test_assessment_chain_tamper_is_blocked(self):
        self.components = pipeline_components()
        book = self.components[2]
        book._assessments[0] = replace(book._assessments[0], reason="tampered")
        report = self.inspect()
        self.assertIn(
            "PROPOSAL_ASSESSMENT_CHAIN_INVALID",
            {item["code"] for item in report["findings"]},
        )

    def test_proposal_payload_tamper_is_blocked_even_with_original_digest(self):
        self.components = pipeline_components()
        proposal = self.components[2]._assessments[0].proposal
        object.__setattr__(proposal, "expected_version", 99)
        report = self.inspect()
        self.assertIn(
            "PROPOSAL_BINDING_INVALID",
            {item["code"] for item in report["findings"]},
        )

    def test_docket_binding_tamper_is_blocked(self):
        self.components = pipeline_components()
        docket = self.components[3]
        docket._connection.execute(
            "UPDATE synthetic_proposal_dockets SET source_assessment_digest = ?",
            ("0" * 64,),
        )
        report = self.inspect()
        codes = {item["code"] for item in report["findings"]}
        self.assertIn("DOCKET_RECORD_BINDING_INVALID", codes)
        self.assertIn("DOCKET_BINDING_MISMATCH", codes)

    def test_naive_observation_time_is_rejected(self):
        self.components = pipeline_components()
        with self.assertRaises(GovernanceRejected):
            SyntheticReconciliationMonitor().inspect(
                *self.components, observed_at=datetime(2026, 9, 17)
            )


if __name__ == "__main__":
    unittest.main()
