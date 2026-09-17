from __future__ import annotations

import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.patch_operator_decision_intake import SyntheticPatchOperatorDecisionIntake
from nurion_pg.patch_operator_decision_receipt_ledger import (
    PATCH_RECEIPT_STATE,
    SyntheticPatchDecisionReceiptLedger,
)
from tests.test_operator_decision_intake import key_registry
from tests.test_patch_operator_decision_intake import (
    NOW,
    decision_envelope,
    packet_source,
)
from tests.test_synthetic_patch_shadow_review_docket import close_resources


def validated_intake():
    resources, docket, record, packet_book, packet = packet_source()
    intake = SyntheticPatchOperatorDecisionIntake(key_registry())
    envelope = decision_envelope(packet)
    assessment = intake.assess(
        packet_book, record.shadow_id, envelope, received_at=NOW
    )
    return resources, docket, intake, envelope, assessment


class PatchDecisionReceiptLedgerTests(unittest.TestCase):
    def test_requires_synthetic_sqlite_target_and_typed_intake(self):
        with self.assertRaises(GovernanceRejected):
            SyntheticPatchDecisionReceiptLedger("patch-receipts.sqlite3")
        with self.assertRaises(GovernanceRejected):
            SyntheticPatchDecisionReceiptLedger("postgresql://prod/patch")
        ledger = SyntheticPatchDecisionReceiptLedger(":memory:")
        with self.assertRaises(GovernanceRejected):
            ledger.record_from_intake(
                object(), "synthetic:patch-operator-decision-envelope:fake",
                recorded_at=NOW,
            )
        ledger.close()

    def test_validated_intent_is_receipted_without_patch_authority(self):
        resources, docket, intake, envelope, assessment = validated_intake()
        ledger = SyntheticPatchDecisionReceiptLedger(":memory:")
        receipt = ledger.record_from_intake(
            intake, envelope.envelope_id, recorded_at=NOW
        )
        self.assertEqual(receipt.assessment_digest, assessment.assessment_digest)
        self.assertEqual(receipt.state, PATCH_RECEIPT_STATE)
        for value in (
            receipt.actual_operator_decision_recorded,
            receipt.packet_state_changed,
            receipt.patch_content_present,
            receipt.code_change_allowed,
            receipt.automatic_application_allowed,
            receipt.safety_baseline_relaxation_allowed,
            receipt.execution_allowed,
            receipt.production_activation_allowed,
        ):
            self.assertFalse(value)
        self.assertTrue(ledger.verify_record_bindings())
        ledger.close()
        close_resources(resources, docket)

    def test_unknown_tampered_and_invalid_times_are_blocked(self):
        resources, docket, intake, envelope, assessment = validated_intake()
        ledger = SyntheticPatchDecisionReceiptLedger(":memory:")
        with self.assertRaises(GovernanceRejected):
            ledger.record_from_intake(
                intake, "synthetic:patch-operator-decision-envelope:unknown",
                recorded_at=NOW,
            )
        with self.assertRaises(GovernanceRejected):
            ledger.record_from_intake(
                intake, envelope.envelope_id,
                recorded_at=NOW - timedelta(seconds=1),
            )
        with self.assertRaises(GovernanceRejected):
            ledger.record_from_intake(
                intake, envelope.envelope_id, recorded_at=NOW.replace(tzinfo=None)
            )
        object.__setattr__(assessment, "patch_content_present", True)
        with self.assertRaises(GovernanceRejected):
            ledger.record_from_intake(intake, envelope.envelope_id, recorded_at=NOW)
        ledger.close()
        close_resources(resources, docket)

    def test_exact_replay_is_idempotent_and_concurrent(self):
        resources, docket, intake, envelope, _ = validated_intake()
        ledger = SyntheticPatchDecisionReceiptLedger(":memory:")

        def record(_):
            return ledger.record_from_intake(
                intake, envelope.envelope_id, recorded_at=NOW
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            receipts = list(pool.map(record, range(8)))
        self.assertTrue(all(item == receipts[0] for item in receipts))
        self.assertEqual(
            ledger._connection.execute(
                "SELECT COUNT(*) FROM synthetic_patch_decision_receipts"
            ).fetchone()[0],
            1,
        )
        ledger.close()
        close_resources(resources, docket)

    def test_one_packet_cannot_create_multiple_receipts(self):
        resources, docket, record, packet_book, packet = packet_source()
        intake = SyntheticPatchOperatorDecisionIntake(key_registry())
        first = decision_envelope(packet)
        second = decision_envelope(
            packet,
            envelope_id="synthetic:patch-operator-decision-envelope:test-2",
            nonce="synthetic:patch-operator-nonce:test-2",
        )
        intake.assess(packet_book, record.shadow_id, first, received_at=NOW)
        intake.assess(packet_book, record.shadow_id, second, received_at=NOW)
        ledger = SyntheticPatchDecisionReceiptLedger(":memory:")
        ledger.record_from_intake(intake, first.envelope_id, recorded_at=NOW)
        with self.assertRaises(GovernanceRejected):
            ledger.record_from_intake(intake, second.envelope_id, recorded_at=NOW)
        self.assertEqual(
            ledger._connection.execute(
                "SELECT COUNT(*) FROM synthetic_patch_decision_receipts"
            ).fetchone()[0],
            1,
        )
        ledger.close()
        close_resources(resources, docket)

    def test_restart_preserves_receipt_and_evidence(self):
        resources, docket, intake, envelope, _ = validated_intake()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic-patch-decision-receipts.sqlite3"
            ledger = SyntheticPatchDecisionReceiptLedger(path)
            receipt = ledger.record_from_intake(
                intake, envelope.envelope_id, recorded_at=NOW
            )
            report = ledger.evidence()
            ledger.close()
            reopened = SyntheticPatchDecisionReceiptLedger(path)
            self.assertEqual(reopened.get(receipt.receipt_id), receipt)
            self.assertEqual(reopened.evidence(), report)
            reopened.close()
        close_resources(resources, docket)

    def test_audit_failure_rolls_back_receipt(self):
        resources, docket, intake, envelope, _ = validated_intake()
        ledger = SyntheticPatchDecisionReceiptLedger(":memory:")

        def fail(*_):
            raise sqlite3.IntegrityError("synthetic audit failure")

        ledger._append_audit = fail
        with self.assertRaises(GovernanceRejected):
            ledger.record_from_intake(intake, envelope.envelope_id, recorded_at=NOW)
        self.assertEqual(
            ledger._connection.execute(
                "SELECT COUNT(*) FROM synthetic_patch_decision_receipts"
            ).fetchone()[0],
            0,
        )
        ledger.close()
        close_resources(resources, docket)

    def test_stored_assessment_and_audit_tampering_are_detected(self):
        resources, docket, intake, envelope, _ = validated_intake()
        ledger = SyntheticPatchDecisionReceiptLedger(":memory:")
        receipt = ledger.record_from_intake(
            intake, envelope.envelope_id, recorded_at=NOW
        )
        ledger._connection.execute(
            "UPDATE synthetic_patch_decision_receipt_audit SET audit_digest = ?",
            ("f" * 64,),
        )
        self.assertFalse(ledger.verify_audit_chain())
        self.assertFalse(ledger.verify_record_bindings())
        with self.assertRaises(GovernanceRejected):
            ledger.record_from_intake(intake, envelope.envelope_id, recorded_at=NOW)
        ledger._connection.execute(
            "UPDATE synthetic_patch_decision_receipts SET assessment_json = '{}'"
        )
        with self.assertRaises(GovernanceRejected):
            ledger.get(receipt.receipt_id)
        ledger.close()
        close_resources(resources, docket)

    def test_evidence_proves_synthetic_receipt_only(self):
        resources, docket, intake, envelope, _ = validated_intake()
        ledger = SyntheticPatchDecisionReceiptLedger(":memory:")
        receipt = ledger.record_from_intake(
            intake, envelope.envelope_id, recorded_at=NOW
        )
        evidence = ledger.evidence()
        self.assertEqual(evidence["receipt_digests"], [receipt.receipt_digest()])
        self.assertEqual(evidence["maximum_state"], PATCH_RECEIPT_STATE)
        self.assertTrue(evidence["synthetic_evidence_only"])
        self.assertTrue(evidence["audit_chain_valid"])
        self.assertTrue(evidence["record_bindings_valid"])
        for field in (
            "actual_operator_decision_recording_method_present",
            "packet_state_change_method_present", "patch_content_present",
            "code_change_method_present", "application_method_present",
            "safety_baseline_relaxation_allowed", "execution_method_present",
            "network_access_method_present", "personal_data_used",
            "credentials_used", "money_movement_executed",
            "production_activation_allowed",
        ):
            self.assertFalse(evidence[field])
        ledger.close()
        close_resources(resources, docket)

    def test_deleted_metadata_fails_closed(self):
        resources, docket, intake, envelope, _ = validated_intake()
        ledger = SyntheticPatchDecisionReceiptLedger(":memory:")
        ledger._connection.execute(
            "DELETE FROM synthetic_patch_decision_receipt_metadata"
        )
        self.assertFalse(ledger.verify_metadata())
        with self.assertRaises(GovernanceRejected):
            ledger.record_from_intake(intake, envelope.envelope_id, recorded_at=NOW)
        ledger.close()
        close_resources(resources, docket)


if __name__ == "__main__":
    unittest.main()
