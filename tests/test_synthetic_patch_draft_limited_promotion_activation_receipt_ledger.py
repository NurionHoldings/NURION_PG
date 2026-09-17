from __future__ import annotations

import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_patch_draft_limited_promotion_activation_intake import (
    SyntheticPatchDraftLimitedPromotionActivationDecision,
    SyntheticPatchDraftLimitedPromotionActivationIntake,
)
from nurion_pg.synthetic_patch_draft_limited_promotion_activation_receipt_ledger import (
    ACTIVATION_RECEIPT_STATE,
    SyntheticPatchDraftLimitedPromotionActivationReceiptLedger,
)
from tests.test_operator_decision_intake import key_registry
from tests.test_patch_draft_limited_promotion_reconfirmation_intake import NOW
from tests.test_synthetic_patch_draft_limited_promotion_activation_intake import (
    activation_envelope,
    packet_source,
)
from tests.test_synthetic_patch_draft_limited_promotion_activation_review_docket import (
    close_all,
)


def validated_intake(
    decision=(
        SyntheticPatchDraftLimitedPromotionActivationDecision
        .AUTHORIZE_SYNTHETIC_LIMITED_PROMOTION_ACTIVATION
    ),
):
    resources, docket, manifest, packet_book, packet = packet_source()
    envelope = activation_envelope(packet, decision=decision)
    intake = SyntheticPatchDraftLimitedPromotionActivationIntake(key_registry())
    assessment = intake.assess(
        packet_book,
        manifest.manifest_id,
        envelope,
        received_at=NOW,
    )
    return resources, docket, intake, envelope, assessment


class ActivationReceiptLedgerTests(unittest.TestCase):
    def test_records_validated_evidence_without_real_decision(self):
        resources, docket, intake, envelope, assessment = validated_intake()
        ledger = SyntheticPatchDraftLimitedPromotionActivationReceiptLedger(
            ":memory:"
        )
        before = intake.evidence()["report_digest"]
        receipt = ledger.record_from_intake(
            intake, envelope.envelope_id, recorded_at=NOW
        )
        self.assertEqual(before, intake.evidence()["report_digest"])
        self.assertEqual(receipt.assessment_digest, assessment.assessment_digest)
        self.assertEqual(receipt.manifest_id, assessment.manifest_id)
        self.assertEqual(receipt.state, ACTIVATION_RECEIPT_STATE)
        self.assertFalse(receipt.actual_operator_decision_recorded)
        self.assertFalse(receipt.activation_recorded)
        self.assertFalse(receipt.activation_allowed)
        ledger.close()
        close_all(resources, docket)

    def test_all_decision_types_remain_evidence_only(self):
        for decision in SyntheticPatchDraftLimitedPromotionActivationDecision:
            resources, docket, intake, envelope, _ = validated_intake(decision)
            ledger = SyntheticPatchDraftLimitedPromotionActivationReceiptLedger(
                ":memory:"
            )
            receipt = ledger.record_from_intake(
                intake, envelope.envelope_id, recorded_at=NOW
            )
            self.assertEqual(receipt.decision, decision)
            self.assertFalse(receipt.actual_operator_decision_recorded)
            ledger.close()
            close_all(resources, docket)

    def test_database_type_and_time_fail_closed(self):
        for target in (
            "receipt.sqlite3",
            "file:synthetic-receipt.sqlite3",
            "postgres://prod",
        ):
            with self.assertRaises(GovernanceRejected):
                SyntheticPatchDraftLimitedPromotionActivationReceiptLedger(target)
        resources, docket, intake, envelope, _ = validated_intake()
        ledger = SyntheticPatchDraftLimitedPromotionActivationReceiptLedger(
            ":memory:"
        )
        with self.assertRaises(GovernanceRejected):
            ledger.record_from_intake(
                object(), envelope.envelope_id, recorded_at=NOW
            )
        for value in (NOW - timedelta(seconds=1), datetime(2026, 9, 17)):
            with self.assertRaises(GovernanceRejected):
                ledger.record_from_intake(
                    intake, envelope.envelope_id, recorded_at=value
                )
        with self.assertRaises(GovernanceRejected):
            ledger.record_from_intake(intake, "unknown", recorded_at=NOW)
        ledger.close()
        close_all(resources, docket)

    def test_exact_replay_and_concurrency_are_idempotent(self):
        resources, docket, intake, envelope, _ = validated_intake()
        ledger = SyntheticPatchDraftLimitedPromotionActivationReceiptLedger(
            ":memory:"
        )

        def record(_):
            return ledger.record_from_intake(
                intake, envelope.envelope_id, recorded_at=NOW
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            receipts = list(pool.map(record, range(8)))
        self.assertTrue(all(item == receipts[0] for item in receipts))
        self.assertEqual(
            ledger._connection.execute(
                "SELECT COUNT(*) FROM synthetic_activation_receipts"
            ).fetchone()[0],
            1,
        )
        ledger.close()
        close_all(resources, docket)

    def test_restart_preserves_receipt_and_evidence(self):
        resources, docket, intake, envelope, _ = validated_intake()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic-activation-receipts.sqlite3"
            ledger = SyntheticPatchDraftLimitedPromotionActivationReceiptLedger(
                path
            )
            receipt = ledger.record_from_intake(
                intake, envelope.envelope_id, recorded_at=NOW
            )
            report = ledger.evidence()
            ledger.close()
            reopened = SyntheticPatchDraftLimitedPromotionActivationReceiptLedger(
                path
            )
            self.assertEqual(reopened.get(receipt.receipt_id), receipt)
            self.assertEqual(reopened.evidence(), report)
            reopened.close()
        close_all(resources, docket)

    def test_audit_failure_rolls_back_receipt(self):
        resources, docket, intake, envelope, _ = validated_intake()
        ledger = SyntheticPatchDraftLimitedPromotionActivationReceiptLedger(
            ":memory:"
        )

        def fail(*_):
            raise sqlite3.IntegrityError("audit failure")

        ledger._append_audit = fail
        with self.assertRaises(GovernanceRejected):
            ledger.record_from_intake(
                intake, envelope.envelope_id, recorded_at=NOW
            )
        self.assertEqual(
            ledger._connection.execute(
                "SELECT COUNT(*) FROM synthetic_activation_receipts"
            ).fetchone()[0],
            0,
        )
        ledger.close()
        close_all(resources, docket)

    def test_stored_assessment_tampering_is_detected(self):
        resources, docket, intake, envelope, _ = validated_intake()
        ledger = SyntheticPatchDraftLimitedPromotionActivationReceiptLedger(
            ":memory:"
        )
        receipt = ledger.record_from_intake(
            intake, envelope.envelope_id, recorded_at=NOW
        )
        ledger._connection.execute(
            "UPDATE synthetic_activation_receipts SET assessment_json = '{}'"
        )
        with self.assertRaises(GovernanceRejected):
            ledger.get(receipt.receipt_id)
        self.assertFalse(ledger.verify_record_bindings())
        ledger.close()
        close_all(resources, docket)

    def test_audit_tampering_is_detected(self):
        resources, docket, intake, envelope, _ = validated_intake()
        ledger = SyntheticPatchDraftLimitedPromotionActivationReceiptLedger(
            ":memory:"
        )
        ledger.record_from_intake(intake, envelope.envelope_id, recorded_at=NOW)
        ledger._connection.execute(
            "UPDATE synthetic_activation_receipt_audit "
            "SET evidence_digest = ?",
            ("f" * 64,),
        )
        self.assertFalse(ledger.verify_audit_chain())
        self.assertFalse(ledger.verify_record_bindings())
        ledger.close()
        close_all(resources, docket)

    def test_tampered_intake_chain_is_rejected(self):
        resources, docket, intake, envelope, assessment = validated_intake()
        object.__setattr__(assessment, "manifest_id", "synthetic:tampered")
        ledger = SyntheticPatchDraftLimitedPromotionActivationReceiptLedger(
            ":memory:"
        )
        with self.assertRaises(GovernanceRejected):
            ledger.record_from_intake(
                intake, envelope.envelope_id, recorded_at=NOW
            )
        ledger.close()
        close_all(resources, docket)

    def test_evidence_proves_non_activating_boundary(self):
        resources, docket, intake, envelope, _ = validated_intake()
        ledger = SyntheticPatchDraftLimitedPromotionActivationReceiptLedger(
            ":memory:"
        )
        ledger.record_from_intake(intake, envelope.envelope_id, recorded_at=NOW)
        evidence = ledger.evidence()
        self.assertTrue(evidence["metadata_valid"])
        self.assertTrue(evidence["audit_chain_valid"])
        self.assertTrue(evidence["record_bindings_valid"])
        self.assertTrue(evidence["synthetic_evidence_only"])
        self.assertEqual(evidence["maximum_state"], ACTIVATION_RECEIPT_STATE)
        for field in (
            "actual_operator_decision_recording_method_present",
            "activation_recording_method_present",
            "packet_state_change_method_present",
            "source_code_change_method_present",
            "filesystem_write_method_present",
            "activation_method_present",
            "rollback_execution_method_present",
            "safety_baseline_relaxation_method_present",
            "execution_method_present",
            "network_access_method_present",
            "external_blocker_close_method_present",
            "automatic_merge_method_present",
            "automatic_deploy_method_present",
            "personal_data_used",
            "credentials_used",
            "money_movement_executed",
            "production_activation_allowed",
        ):
            self.assertFalse(evidence[field])
        ledger.close()
        close_all(resources, docket)


if __name__ == "__main__":
    unittest.main()
