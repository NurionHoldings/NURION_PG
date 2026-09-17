from __future__ import annotations

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
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


NOW = datetime(2026, 9, 17, tzinfo=UTC)
SECRET = "synthetic:proposal-docket-secret:unit-tests:0001"
POLICY = sha256(b"synthetic docket policy").hexdigest()
FINDINGS = sha256(b"synthetic Eternian findings").hexdigest()


def proposal_fixture(*, outcome: str = "SUCCEEDED"):
    registry = SyntheticKeyRegistry()
    registry.register(
        SyntheticVerificationKey(
            "docket-provider.invalid",
            "synthetic:key:docket:1",
            SECRET,
            NOW - timedelta(days=1),
            NOW + timedelta(days=1),
        )
    )
    inbox = SyntheticSQLiteWebhookInbox(":memory:", registry)
    unsigned = WebhookEnvelope(
        "docket-provider.invalid",
        "synthetic:key:docket:1",
        "synthetic:event:docket:1",
        "synthetic:nonce:docket:1",
        "synthetic:intent:docket:1",
        1,
        WebhookEventType.AUTHORIZATION_RESULT,
        NOW,
        {
            "intent_id": "synthetic:intent:docket:1",
            "expected_version": 1,
            "outcome": outcome,
        },
        "sha256=" + "0" * 64,
    )
    value = replace(unsigned, signature=sign_envelope(unsigned, SECRET))
    inbox.submit(value, received_at=NOW)
    payment = PaymentEngine()
    payment.create(
        intent_id=value.aggregate_id,
        merchant_ref="synthetic:merchant:docket",
        customer_ref="synthetic:customer:docket",
        amount_minor=1000,
        currency="KRW",
        policy_digest=POLICY,
        idempotency_key="synthetic:create:docket:1",
        now=NOW,
    )
    book = SyntheticWebhookProposalBook()
    assessment = book.assess(inbox, payment, value.event_id, now=NOW)
    return inbox, book, assessment


class ProposalReviewDocketTests(unittest.TestCase):
    def test_only_synthetic_sqlite_targets_are_allowed(self):
        SyntheticProposalReviewDocket(":memory:").close()
        for target in ("reviews.sqlite3", "file:synthetic-review.sqlite3", "postgres://db"):
            with self.assertRaises(GovernanceRejected):
                SyntheticProposalReviewDocket(target)

    def test_arkaon_proposal_is_durably_pending_eternian_review(self):
        inbox, book, assessment = proposal_fixture()
        docket = SyntheticProposalReviewDocket(":memory:")
        record = docket.submit_from_book(book, assessment.source_event_id, submitted_at=NOW)
        self.assertEqual(record.state, DocketState.PENDING_ETERNIAN_REVIEW)
        self.assertFalse(record.automatic_review_allowed)
        self.assertFalse(record.operator_approval_recorded)
        self.assertFalse(record.execution_allowed)
        self.assertTrue(docket.verify_audit_chain())
        docket.close()
        inbox.close()

    def test_nonproposal_assessment_cannot_enter_docket(self):
        inbox, book, assessment = proposal_fixture(outcome="FAILED")
        docket = SyntheticProposalReviewDocket(":memory:")
        with self.assertRaises(GovernanceRejected):
            docket.submit_from_book(book, assessment.source_event_id, submitted_at=NOW)
        docket.close()
        inbox.close()

    def test_tampered_assessment_chain_cannot_enter_docket(self):
        inbox, book, assessment = proposal_fixture()
        original = book._assessments[0]
        book._assessments[0] = replace(original, reason="tampered")
        docket = SyntheticProposalReviewDocket(":memory:")
        with self.assertRaises(GovernanceRejected):
            docket.submit_from_book(book, assessment.source_event_id, submitted_at=NOW)
        docket.close()
        inbox.close()

    def test_pass_stops_at_ready_for_operator_decision(self):
        inbox, book, assessment = proposal_fixture()
        docket = SyntheticProposalReviewDocket(":memory:")
        submitted = docket.submit_from_book(book, assessment.source_event_id, submitted_at=NOW)
        reviewed = docket.record_eternian_review(
            submitted.proposal_id,
            review_id="synthetic:review:1",
            reviewer_id="synthetic:eternian-reviewer:1",
            decision=EternianReviewDecision.PASS,
            findings_digest=FINDINGS,
            reviewed_at=NOW,
        )
        self.assertEqual(reviewed.state, DocketState.READY_FOR_OPERATOR_DECISION)
        self.assertFalse(reviewed.operator_approval_recorded)
        self.assertFalse(reviewed.execution_allowed)
        self.assertFalse(docket.evidence()["operator_decision_method_present"])
        docket.close()
        inbox.close()

    def test_hold_and_reject_are_terminal_review_results(self):
        for number, decision, expected in (
            (1, EternianReviewDecision.HOLD, DocketState.HELD),
            (2, EternianReviewDecision.REJECT, DocketState.REJECTED),
        ):
            inbox, book, assessment = proposal_fixture()
            docket = SyntheticProposalReviewDocket(":memory:")
            submitted = docket.submit_from_book(book, assessment.source_event_id, submitted_at=NOW)
            reviewed = docket.record_eternian_review(
                submitted.proposal_id,
                review_id=f"synthetic:review:{number}",
                reviewer_id=f"synthetic:eternian-reviewer:{number}",
                decision=decision,
                findings_digest=FINDINGS,
                reviewed_at=NOW,
            )
            self.assertEqual(reviewed.state, expected)
            with self.assertRaises(GovernanceRejected):
                docket.record_eternian_review(
                    submitted.proposal_id,
                    review_id=f"synthetic:review:second:{number}",
                    reviewer_id="synthetic:eternian-reviewer:other",
                    decision=EternianReviewDecision.PASS,
                    findings_digest=FINDINGS,
                    reviewed_at=NOW,
                )
            docket.close()
            inbox.close()

    def test_invalid_reviewer_and_review_metadata_are_rejected(self):
        inbox, book, assessment = proposal_fixture()
        docket = SyntheticProposalReviewDocket(":memory:")
        submitted = docket.submit_from_book(book, assessment.source_event_id, submitted_at=NOW)
        invalid = (
            {"review_id": "real-review", "reviewer_id": "synthetic:eternian-reviewer:1", "findings_digest": FINDINGS},
            {"review_id": "synthetic:review:1", "reviewer_id": "synthetic:arkaon:NURION_PG", "findings_digest": FINDINGS},
            {"review_id": "synthetic:review:1", "reviewer_id": "synthetic:eternian-reviewer:1", "findings_digest": "bad"},
        )
        for item in invalid:
            with self.assertRaises(GovernanceRejected):
                docket.record_eternian_review(
                    submitted.proposal_id,
                    decision=EternianReviewDecision.PASS,
                    reviewed_at=NOW,
                    **item,
                )
        docket.close()
        inbox.close()

    def test_submission_and_review_times_cannot_move_backwards(self):
        inbox, book, assessment = proposal_fixture()
        docket = SyntheticProposalReviewDocket(":memory:")
        with self.assertRaises(GovernanceRejected):
            docket.submit_from_book(
                book,
                assessment.source_event_id,
                submitted_at=NOW - timedelta(seconds=1),
            )
        submitted = docket.submit_from_book(book, assessment.source_event_id, submitted_at=NOW)
        with self.assertRaises(GovernanceRejected):
            docket.record_eternian_review(
                submitted.proposal_id,
                review_id="synthetic:review:backdated",
                reviewer_id="synthetic:eternian-reviewer:backdated",
                decision=EternianReviewDecision.PASS,
                findings_digest=FINDINGS,
                reviewed_at=NOW - timedelta(seconds=1),
            )
        docket.close()
        inbox.close()

    def test_review_idempotency_and_payload_mismatch(self):
        inbox, book, assessment = proposal_fixture()
        docket = SyntheticProposalReviewDocket(":memory:")
        submitted = docket.submit_from_book(book, assessment.source_event_id, submitted_at=NOW)
        first = docket.record_eternian_review(
            submitted.proposal_id,
            review_id="synthetic:review:1",
            reviewer_id="synthetic:eternian-reviewer:1",
            decision=EternianReviewDecision.PASS,
            findings_digest=FINDINGS,
            reviewed_at=NOW,
        )
        replay = docket.record_eternian_review(
            submitted.proposal_id,
            review_id="synthetic:review:1",
            reviewer_id="synthetic:eternian-reviewer:1",
            decision=EternianReviewDecision.PASS,
            findings_digest=FINDINGS,
            reviewed_at=NOW,
        )
        self.assertEqual(first, replay)
        with self.assertRaises(GovernanceRejected):
            docket.record_eternian_review(
                submitted.proposal_id,
                review_id="synthetic:review:1",
                reviewer_id="synthetic:eternian-reviewer:1",
                decision=EternianReviewDecision.HOLD,
                findings_digest=FINDINGS,
                reviewed_at=NOW,
            )
        docket.close()
        inbox.close()

    def test_restart_preserves_docket_and_review_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic-docket.sqlite3"
            inbox, book, assessment = proposal_fixture()
            docket = SyntheticProposalReviewDocket(path)
            submitted = docket.submit_from_book(book, assessment.source_event_id, submitted_at=NOW)
            docket.close()
            restarted = SyntheticProposalReviewDocket(path)
            self.assertEqual(
                restarted.get(submitted.proposal_id).state,
                DocketState.PENDING_ETERNIAN_REVIEW,
            )
            restarted.record_eternian_review(
                submitted.proposal_id,
                review_id="synthetic:review:restart",
                reviewer_id="synthetic:eternian-reviewer:restart",
                decision=EternianReviewDecision.PASS,
                findings_digest=FINDINGS,
                reviewed_at=NOW,
            )
            restarted.close()
            final = SyntheticProposalReviewDocket(path)
            self.assertEqual(
                final.get(submitted.proposal_id).state,
                DocketState.READY_FOR_OPERATOR_DECISION,
            )
            self.assertTrue(final.verify_audit_chain())
            final.close()
            inbox.close()

    def test_concurrent_reviews_allow_one_transition(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic-review-race.sqlite3"
            inbox, book, assessment = proposal_fixture()
            setup = SyntheticProposalReviewDocket(path)
            submitted = setup.submit_from_book(book, assessment.source_event_id, submitted_at=NOW)
            setup.close()
            first = SyntheticProposalReviewDocket(path)
            second = SyntheticProposalReviewDocket(path)

            def review(number_and_docket):
                number, value = number_and_docket
                try:
                    value.record_eternian_review(
                        submitted.proposal_id,
                        review_id=f"synthetic:review:race:{number}",
                        reviewer_id=f"synthetic:eternian-reviewer:race:{number}",
                        decision=EternianReviewDecision.PASS,
                        findings_digest=FINDINGS,
                        reviewed_at=NOW,
                    )
                    return "accepted"
                except GovernanceRejected:
                    return "rejected"

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(review, ((1, first), (2, second))))
            self.assertEqual(results.count("accepted"), 1)
            self.assertEqual(results.count("rejected"), 1)
            self.assertTrue(first.verify_audit_chain())
            first.close()
            second.close()
            inbox.close()

    def test_audit_failure_rolls_back_submission_and_tampering_is_detected(self):
        inbox, book, assessment = proposal_fixture()
        docket = SyntheticProposalReviewDocket(":memory:")
        docket._connection.executescript(
            """
            CREATE TRIGGER synthetic_test_fail_audit
            BEFORE INSERT ON synthetic_docket_audit
            BEGIN SELECT RAISE(ABORT, 'synthetic audit failure'); END;
            """
        )
        with self.assertRaises(GovernanceRejected):
            docket.submit_from_book(book, assessment.source_event_id, submitted_at=NOW)
        docket._connection.execute("DROP TRIGGER synthetic_test_fail_audit")
        submitted = docket.submit_from_book(book, assessment.source_event_id, submitted_at=NOW)
        docket._connection.execute(
            "UPDATE synthetic_docket_audit SET action = 'tampered' WHERE audit_sequence = 1"
        )
        self.assertFalse(docket.verify_audit_chain())
        self.assertEqual(docket.get(submitted.proposal_id).state, DocketState.PENDING_ETERNIAN_REVIEW)
        docket.close()
        inbox.close()

    def test_stored_proposal_and_review_binding_tampering_is_detected(self):
        inbox, book, assessment = proposal_fixture()
        docket = SyntheticProposalReviewDocket(":memory:")
        submitted = docket.submit_from_book(book, assessment.source_event_id, submitted_at=NOW)
        docket._connection.execute(
            "UPDATE synthetic_proposal_dockets SET proposal_json = '{}' WHERE proposal_id = ?",
            (submitted.proposal_id,),
        )
        with self.assertRaises(GovernanceRejected):
            docket.get(submitted.proposal_id)
        self.assertFalse(docket.verify_record_bindings())
        docket.close()
        inbox.close()

        inbox, book, assessment = proposal_fixture()
        docket = SyntheticProposalReviewDocket(":memory:")
        submitted = docket.submit_from_book(book, assessment.source_event_id, submitted_at=NOW)
        docket.record_eternian_review(
            submitted.proposal_id,
            review_id="synthetic:review:binding",
            reviewer_id="synthetic:eternian-reviewer:binding",
            decision=EternianReviewDecision.PASS,
            findings_digest=FINDINGS,
            reviewed_at=NOW,
        )
        docket._connection.execute(
            "UPDATE synthetic_eternian_reviews SET reviewer_id = ? WHERE proposal_id = ?",
            ("synthetic:eternian-reviewer:tampered", submitted.proposal_id),
        )
        self.assertTrue(docket.verify_audit_chain())
        self.assertFalse(docket.verify_record_bindings())
        docket.close()
        inbox.close()

    def test_evidence_caps_state_and_has_no_operator_or_execution_method(self):
        inbox, book, assessment = proposal_fixture()
        docket = SyntheticProposalReviewDocket(":memory:")
        docket.submit_from_book(book, assessment.source_event_id, submitted_at=NOW)
        report = docket.evidence()
        self.assertEqual(report["maximum_automatic_state"], "READY_FOR_OPERATOR_DECISION")
        self.assertFalse(report["operator_decision_method_present"])
        self.assertTrue(report["record_bindings_valid"])
        self.assertFalse(report["execution_method_present"])
        self.assertFalse(report["operator_approval_automatically_recorded"])
        self.assertFalse(report["money_movement_executed"])
        self.assertFalse(report["production_activation_allowed"])
        docket.close()
        inbox.close()


if __name__ == "__main__":
    unittest.main()
