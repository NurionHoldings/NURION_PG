from __future__ import annotations

import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.operator_decision_intake import SyntheticOperatorDecisionIntake
from nurion_pg.operator_decision_receipt_ledger import (
    RECEIPT_STATE,
    SyntheticOperatorDecisionReceiptLedger,
)
from tests.test_operator_decision_intake import (
    NOW,
    decision_envelope,
    key_registry,
    packet_source,
)


def validated_intake():
    case, remediation, docket, record, packet_book, packet = packet_source()
    intake = SyntheticOperatorDecisionIntake(key_registry())
    envelope = decision_envelope(packet)
    assessment = intake.assess(
        packet_book, record.shadow_id, envelope, received_at=NOW
    )
    return case, remediation, docket, intake, envelope, assessment


class OperatorDecisionReceiptLedgerTests(unittest.TestCase):
    def test_requires_synthetic_sqlite_target(self):
        with self.assertRaises(GovernanceRejected):
            SyntheticOperatorDecisionReceiptLedger("operator.sqlite")
        with self.assertRaises(GovernanceRejected):
            SyntheticOperatorDecisionReceiptLedger("postgresql://prod/operator")

    def test_requires_typed_validated_intake(self):
        ledger = SyntheticOperatorDecisionReceiptLedger(":memory:")
        with self.assertRaises(GovernanceRejected):
            ledger.record_from_intake(
                object(),
                "synthetic:operator-decision-envelope:fake",
                recorded_at=NOW,
            )
        ledger.close()

    def test_validated_intent_is_durably_receipted_without_authority(self):
        case, remediation, docket, intake, envelope, assessment = validated_intake()
        ledger = SyntheticOperatorDecisionReceiptLedger(":memory:")
        receipt = ledger.record_from_intake(
            intake, envelope.envelope_id, recorded_at=NOW
        )
        self.assertEqual(receipt.assessment_digest, assessment.assessment_digest)
        self.assertEqual(receipt.state, RECEIPT_STATE)
        self.assertFalse(receipt.actual_operator_decision_recorded)
        self.assertFalse(receipt.packet_state_changed)
        self.assertFalse(receipt.code_change_allowed)
        self.assertFalse(receipt.automatic_application_allowed)
        self.assertFalse(receipt.execution_allowed)
        self.assertTrue(ledger.verify_audit_chain())
        self.assertTrue(ledger.verify_record_bindings())
        ledger.close()
        docket.close()
        remediation.close()
        case.close()

    def test_unknown_and_tampered_assessments_are_blocked(self):
        case, remediation, docket, intake, envelope, assessment = validated_intake()
        ledger = SyntheticOperatorDecisionReceiptLedger(":memory:")
        with self.assertRaises(GovernanceRejected):
            ledger.record_from_intake(
                intake,
                "synthetic:operator-decision-envelope:unknown",
                recorded_at=NOW,
            )
        object.__setattr__(assessment, "operator_decision_recorded", True)
        with self.assertRaises(GovernanceRejected):
            ledger.record_from_intake(intake, envelope.envelope_id, recorded_at=NOW)
        ledger.close()
        docket.close()
        remediation.close()
        case.close()

    def test_receipt_cannot_predate_assessment_or_use_naive_time(self):
        case, remediation, docket, intake, envelope, _ = validated_intake()
        ledger = SyntheticOperatorDecisionReceiptLedger(":memory:")
        with self.assertRaises(GovernanceRejected):
            ledger.record_from_intake(
                intake, envelope.envelope_id, recorded_at=NOW - timedelta(seconds=1)
            )
        with self.assertRaises(GovernanceRejected):
            ledger.record_from_intake(
                intake, envelope.envelope_id, recorded_at=NOW.replace(tzinfo=None)
            )
        ledger.close()
        docket.close()
        remediation.close()
        case.close()

    def test_exact_receipt_replay_is_idempotent(self):
        case, remediation, docket, intake, envelope, _ = validated_intake()
        ledger = SyntheticOperatorDecisionReceiptLedger(":memory:")
        first = ledger.record_from_intake(intake, envelope.envelope_id, recorded_at=NOW)
        second = ledger.record_from_intake(intake, envelope.envelope_id, recorded_at=NOW)
        self.assertEqual(first, second)
        count = ledger._connection.execute(
            "SELECT COUNT(*) FROM synthetic_decision_receipts"
        ).fetchone()[0]
        self.assertEqual(count, 1)
        ledger.close()
        docket.close()
        remediation.close()
        case.close()

    def test_concurrent_exact_receipt_records_once(self):
        case, remediation, docket, intake, envelope, _ = validated_intake()
        ledger = SyntheticOperatorDecisionReceiptLedger(":memory:")

        def record(_):
            return ledger.record_from_intake(
                intake, envelope.envelope_id, recorded_at=NOW
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            receipts = list(pool.map(record, range(8)))
        self.assertTrue(all(receipt == receipts[0] for receipt in receipts))
        self.assertEqual(
            ledger._connection.execute(
                "SELECT COUNT(*) FROM synthetic_decision_receipts"
            ).fetchone()[0],
            1,
        )
        ledger.close()
        docket.close()
        remediation.close()
        case.close()

    def test_one_packet_cannot_create_multiple_receipts(self):
        case, remediation, docket, record, packet_book, packet = packet_source()
        intake = SyntheticOperatorDecisionIntake(key_registry())
        first_envelope = decision_envelope(packet)
        second_envelope = decision_envelope(
            packet,
            envelope_id="synthetic:operator-decision-envelope:test-2",
            nonce="synthetic:operator-nonce:test-2",
        )
        intake.assess(packet_book, record.shadow_id, first_envelope, received_at=NOW)
        intake.assess(packet_book, record.shadow_id, second_envelope, received_at=NOW)
        ledger = SyntheticOperatorDecisionReceiptLedger(":memory:")
        ledger.record_from_intake(intake, first_envelope.envelope_id, recorded_at=NOW)
        with self.assertRaises(GovernanceRejected):
            ledger.record_from_intake(
                intake, second_envelope.envelope_id, recorded_at=NOW
            )
        self.assertEqual(
            ledger._connection.execute(
                "SELECT COUNT(*) FROM synthetic_decision_receipts"
            ).fetchone()[0],
            1,
        )
        self.assertTrue(ledger.verify_audit_chain())
        ledger.close()
        docket.close()
        remediation.close()
        case.close()

    def test_restart_preserves_receipt_and_evidence(self):
        case, remediation, docket, intake, envelope, _ = validated_intake()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic-decision-receipts.sqlite3"
            ledger = SyntheticOperatorDecisionReceiptLedger(path)
            receipt = ledger.record_from_intake(
                intake, envelope.envelope_id, recorded_at=NOW
            )
            ledger.close()
            reopened = SyntheticOperatorDecisionReceiptLedger(path)
            self.assertEqual(reopened.get(receipt.receipt_id), receipt)
            self.assertTrue(reopened.verify_audit_chain())
            self.assertTrue(reopened.verify_record_bindings())
            reopened.close()
        docket.close()
        remediation.close()
        case.close()

    def test_audit_failure_rolls_back_receipt(self):
        case, remediation, docket, intake, envelope, _ = validated_intake()
        ledger = SyntheticOperatorDecisionReceiptLedger(":memory:")

        def fail(*_):
            raise sqlite3.IntegrityError("synthetic audit failure")

        ledger._append_audit = fail
        with self.assertRaises(GovernanceRejected):
            ledger.record_from_intake(intake, envelope.envelope_id, recorded_at=NOW)
        self.assertEqual(
            ledger._connection.execute(
                "SELECT COUNT(*) FROM synthetic_decision_receipts"
            ).fetchone()[0],
            0,
        )
        ledger.close()
        docket.close()
        remediation.close()
        case.close()

    def test_stored_assessment_and_audit_tampering_are_detected(self):
        case, remediation, docket, intake, envelope, _ = validated_intake()
        ledger = SyntheticOperatorDecisionReceiptLedger(":memory:")
        receipt = ledger.record_from_intake(
            intake, envelope.envelope_id, recorded_at=NOW
        )
        ledger._connection.execute(
            "UPDATE synthetic_decision_receipt_audit SET audit_digest = ?",
            ("f" * 64,),
        )
        self.assertFalse(ledger.verify_audit_chain())
        self.assertFalse(ledger.verify_record_bindings())
        with self.assertRaises(GovernanceRejected):
            ledger.record_from_intake(intake, envelope.envelope_id, recorded_at=NOW)
        ledger._connection.execute(
            "UPDATE synthetic_decision_receipts SET assessment_json = '{}'"
        )
        with self.assertRaises(GovernanceRejected):
            ledger.get(receipt.receipt_id)
        ledger.close()
        docket.close()
        remediation.close()
        case.close()

    def test_evidence_proves_synthetic_receipt_only(self):
        case, remediation, docket, intake, envelope, _ = validated_intake()
        ledger = SyntheticOperatorDecisionReceiptLedger(":memory:")
        ledger.record_from_intake(intake, envelope.envelope_id, recorded_at=NOW)
        evidence = ledger.evidence()
        self.assertTrue(evidence["metadata_valid"])
        self.assertTrue(evidence["synthetic_evidence_only"])
        self.assertTrue(evidence["audit_chain_valid"])
        self.assertTrue(evidence["record_bindings_valid"])
        self.assertEqual(evidence["maximum_state"], RECEIPT_STATE)
        for field in (
            "actual_operator_decision_recording_method_present",
            "packet_state_change_method_present",
            "code_change_method_present",
            "application_method_present",
            "execution_method_present",
            "money_movement_executed",
            "production_activation_allowed",
        ):
            self.assertFalse(evidence[field])
        ledger.close()
        docket.close()
        remediation.close()
        case.close()

    def test_deleted_synthetic_metadata_fails_closed(self):
        case, remediation, docket, intake, envelope, _ = validated_intake()
        ledger = SyntheticOperatorDecisionReceiptLedger(":memory:")
        ledger._connection.execute("DELETE FROM synthetic_decision_receipt_metadata")
        self.assertFalse(ledger.verify_metadata())
        with self.assertRaises(GovernanceRejected):
            ledger.record_from_intake(intake, envelope.envelope_id, recorded_at=NOW)
        ledger.close()
        docket.close()
        remediation.close()
        case.close()


if __name__ == "__main__":
    unittest.main()
