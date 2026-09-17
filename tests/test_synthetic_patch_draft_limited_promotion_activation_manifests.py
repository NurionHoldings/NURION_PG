from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.patch_draft_limited_promotion_reconfirmation_intake import (
    SyntheticPatchDraftLimitedPromotionReconfirmationDecision,
    SyntheticPatchDraftLimitedPromotionReconfirmationIntake,
)
from nurion_pg.patch_draft_limited_promotion_reconfirmation_receipt_ledger import (
    SyntheticPatchDraftLimitedPromotionReconfirmationReceiptLedger,
)
from nurion_pg.synthetic_patch_draft_limited_promotion_activation_manifests import (
    LIMITED_PROMOTION_ACTIVATION_MANIFEST_STATE,
    LIMITED_PROMOTION_ACTIVATION_SCOPE,
    REQUIRED_ACTIVATION_PREFLIGHT_CHECKS,
    SyntheticPatchDraftLimitedPromotionActivationManifestBook,
)
from nurion_pg.synthetic_patch_draft_limited_promotion_plans import (
    REQUIRED_ROLLBACK_TRIGGERS,
)
from tests.test_operator_decision_intake import key_registry
from tests.test_patch_draft_limited_promotion_reconfirmation_intake import (
    NOW,
    packet_source,
    reconfirmation_envelope,
)
from tests.test_synthetic_patch_draft_limited_promotion_shadow_review_docket import (
    close_resources,
)


def activation_sources(*, decision=None):
    resources, docket, record, packet_book, packet = packet_source()
    intake = SyntheticPatchDraftLimitedPromotionReconfirmationIntake(
        key_registry()
    )
    envelope = reconfirmation_envelope(
        packet,
        decision=(
            decision
            or SyntheticPatchDraftLimitedPromotionReconfirmationDecision
            .RECONFIRM_SYNTHETIC_PATCH_DRAFT_LIMITED_PROMOTION
        ),
    )
    intake.assess(
        packet_book,
        record.assessment.shadow_id,
        envelope,
        received_at=NOW,
    )
    ledger = (
        SyntheticPatchDraftLimitedPromotionReconfirmationReceiptLedger(
            ":memory:"
        )
    )
    receipt = ledger.record_from_intake(
        intake, envelope.envelope_id, recorded_at=NOW
    )
    return resources, docket, ledger, packet_book, packet, receipt


class SyntheticPatchDraftLimitedPromotionActivationManifestTests(
    unittest.TestCase
):
    def test_manifest_binds_full_lineage_without_activation(self):
        resources, docket, ledger, packet_book, packet, receipt = (
            activation_sources()
        )
        ledger_before = ledger.evidence()["report_digest"]
        packet_before = packet_book.evidence()["report_digest"]
        book = SyntheticPatchDraftLimitedPromotionActivationManifestBook()
        manifest = book.draft_from_receipt(
            ledger, receipt.receipt_id, packet_book, drafted_at=NOW
        )
        self.assertEqual(ledger_before, ledger.evidence()["report_digest"])
        self.assertEqual(
            packet_before, packet_book.evidence()["report_digest"]
        )
        self.assertEqual(manifest.source_receipt_id, receipt.receipt_id)
        self.assertEqual(manifest.source_packet_id, packet.packet_id)
        self.assertEqual(manifest.shadow_id, packet.shadow_id)
        self.assertEqual(manifest.plan_id, packet.plan_id)
        self.assertEqual(manifest.plan_digest, packet.plan_digest)
        self.assertEqual(manifest.candidate_digest, packet.candidate_digest)
        self.assertEqual(manifest.cohort_digest, packet.cohort_digest)
        self.assertEqual(
            manifest.observation_result_digests,
            packet.observation_result_digests,
        )
        self.assertEqual(
            manifest.activation_scope, LIMITED_PROMOTION_ACTIVATION_SCOPE
        )
        self.assertEqual(manifest.rollback_triggers, REQUIRED_ROLLBACK_TRIGGERS)
        self.assertEqual(
            manifest.required_checks, REQUIRED_ACTIVATION_PREFLIGHT_CHECKS
        )
        self.assertFalse(manifest.actual_operator_reconfirmation_recorded)
        self.assertFalse(manifest.activation_allowed)
        self.assertFalse(manifest.rollback_execution_allowed)
        ledger.close()
        close_resources(resources, docket)

    def test_hold_and_reject_receipts_cannot_draft_manifest(self):
        for decision in (
            SyntheticPatchDraftLimitedPromotionReconfirmationDecision.HOLD,
            SyntheticPatchDraftLimitedPromotionReconfirmationDecision.REJECT,
        ):
            resources, docket, ledger, packet_book, _, receipt = (
                activation_sources(decision=decision)
            )
            with self.assertRaises(GovernanceRejected):
                SyntheticPatchDraftLimitedPromotionActivationManifestBook().draft_from_receipt(
                    ledger, receipt.receipt_id, packet_book, drafted_at=NOW
                )
            ledger.close()
            close_resources(resources, docket)

    def test_typed_sources_time_and_current_packet_are_required(self):
        resources, docket, ledger, packet_book, packet, receipt = (
            activation_sources()
        )
        book = SyntheticPatchDraftLimitedPromotionActivationManifestBook()
        with self.assertRaises(GovernanceRejected):
            book.draft_from_receipt(
                object(), receipt.receipt_id, packet_book, drafted_at=NOW
            )
        with self.assertRaises(GovernanceRejected):
            book.draft_from_receipt(
                ledger, receipt.receipt_id, object(), drafted_at=NOW
            )
        for value in (NOW - timedelta(seconds=1), datetime(2026, 9, 17)):
            with self.assertRaises(GovernanceRejected):
                book.draft_from_receipt(
                    ledger, receipt.receipt_id, packet_book, drafted_at=value
                )
        with self.assertRaises(GovernanceRejected):
            book.draft_from_receipt(
                ledger,
                receipt.receipt_id,
                packet_book,
                drafted_at=packet.valid_until + timedelta(seconds=1),
            )
        ledger.close()
        close_resources(resources, docket)

    def test_exact_replay_is_idempotent(self):
        resources, docket, ledger, packet_book, _, receipt = (
            activation_sources()
        )
        book = SyntheticPatchDraftLimitedPromotionActivationManifestBook()
        first = book.draft_from_receipt(
            ledger, receipt.receipt_id, packet_book, drafted_at=NOW
        )
        second = book.draft_from_receipt(
            ledger,
            receipt.receipt_id,
            packet_book,
            drafted_at=NOW + timedelta(minutes=1),
        )
        self.assertEqual(first, second)
        self.assertEqual(len(book.manifests), 1)
        ledger.close()
        close_resources(resources, docket)

    def test_concurrent_drafting_records_once(self):
        resources, docket, ledger, packet_book, _, receipt = (
            activation_sources()
        )
        book = SyntheticPatchDraftLimitedPromotionActivationManifestBook()

        def draft(_):
            return book.draft_from_receipt(
                ledger, receipt.receipt_id, packet_book, drafted_at=NOW
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            manifests = list(pool.map(draft, range(8)))
        self.assertTrue(all(item == manifests[0] for item in manifests))
        self.assertEqual(len(book.manifests), 1)
        ledger.close()
        close_resources(resources, docket)

    def test_receipt_ledger_tampering_blocks_drafting(self):
        resources, docket, ledger, packet_book, _, receipt = (
            activation_sources()
        )
        ledger._connection.execute(
            "UPDATE synthetic_limited_promotion_reconfirmation_audit "
            "SET audit_digest = ?",
            ("f" * 64,),
        )
        with self.assertRaises(GovernanceRejected):
            SyntheticPatchDraftLimitedPromotionActivationManifestBook().draft_from_receipt(
                ledger, receipt.receipt_id, packet_book, drafted_at=NOW
            )
        ledger.close()
        close_resources(resources, docket)

    def test_packet_tampering_blocks_drafting(self):
        resources, docket, ledger, packet_book, packet, receipt = (
            activation_sources()
        )
        object.__setattr__(packet, "cohort_digest", "f" * 64)
        with self.assertRaises(GovernanceRejected):
            SyntheticPatchDraftLimitedPromotionActivationManifestBook().draft_from_receipt(
                ledger, receipt.receipt_id, packet_book, drafted_at=NOW
            )
        ledger.close()
        close_resources(resources, docket)

    def test_manifest_tampering_breaks_chain(self):
        resources, docket, ledger, packet_book, _, receipt = (
            activation_sources()
        )
        book = SyntheticPatchDraftLimitedPromotionActivationManifestBook()
        manifest = book.draft_from_receipt(
            ledger, receipt.receipt_id, packet_book, drafted_at=NOW
        )
        object.__setattr__(manifest, "activation_scope", "PRODUCTION")
        self.assertFalse(book.verify_manifest_chain())
        with self.assertRaises(GovernanceRejected):
            book.draft_from_receipt(
                ledger, receipt.receipt_id, packet_book, drafted_at=NOW
            )
        ledger.close()
        close_resources(resources, docket)

    def test_rehashed_manifest_identity_tamper_breaks_chain(self):
        resources, docket, ledger, packet_book, _, receipt = (
            activation_sources()
        )
        book = SyntheticPatchDraftLimitedPromotionActivationManifestBook()
        manifest = book.draft_from_receipt(
            ledger, receipt.receipt_id, packet_book, drafted_at=NOW
        )
        object.__setattr__(
            manifest,
            "manifest_id",
            "synthetic:limited-promotion-activation-manifest:" + "f" * 32,
        )
        object.__setattr__(
            manifest,
            "manifest_digest",
            canonical_digest(manifest.digest_value()),
        )
        self.assertFalse(book.verify_manifest_chain())
        ledger.close()
        close_resources(resources, docket)

    def test_evidence_proves_preflight_only_boundary(self):
        resources, docket, ledger, packet_book, _, receipt = (
            activation_sources()
        )
        book = SyntheticPatchDraftLimitedPromotionActivationManifestBook()
        book.draft_from_receipt(
            ledger, receipt.receipt_id, packet_book, drafted_at=NOW
        )
        evidence = book.evidence()
        self.assertTrue(evidence["manifest_chain_valid"])
        self.assertEqual(
            evidence["maximum_state"],
            LIMITED_PROMOTION_ACTIVATION_MANIFEST_STATE,
        )
        self.assertTrue(evidence["synthetic_only"])
        self.assertTrue(evidence["eternian_final_review_required"])
        self.assertTrue(evidence["validated_reconfirmation_receipt_only"])
        for field in (
            "actual_operator_reconfirmation_recorded",
            "candidate_content_present",
            "patch_content_present",
            "diff_content_present",
            "source_code_changed",
            "filesystem_written",
            "activation_method_present",
            "rollback_execution_method_present",
            "safety_baseline_relaxation_allowed",
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
        close_resources(resources, docket)


if __name__ == "__main__":
    unittest.main()
