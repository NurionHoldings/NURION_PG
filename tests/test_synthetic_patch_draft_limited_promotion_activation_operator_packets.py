from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_patch_draft_limited_promotion_activation_operator_packets import (
    ACTIVATION_OPERATOR_ALLOWED_DECISIONS,
    ACTIVATION_OPERATOR_PACKET_SCOPE,
    ACTIVATION_OPERATOR_REQUIRED_ACKNOWLEDGEMENTS,
    SyntheticPatchDraftLimitedPromotionActivationOperatorPacketBook,
)
from nurion_pg.synthetic_patch_draft_limited_promotion_activation_review_docket import (
    ActivationManifestReviewDecision,
    SyntheticPatchDraftLimitedPromotionActivationReviewDocket,
)
from tests.test_operator_decision_packets import governance_snapshot
from tests.test_patch_draft_limited_promotion_reconfirmation_intake import NOW
from tests.test_synthetic_patch_draft_limited_promotion_activation_review_docket import (
    close_all,
    manifest_source,
    review,
)


def reviewed_manifest(*, decision=ActivationManifestReviewDecision.PASS):
    resources, source_book, manifest = manifest_source()
    docket = SyntheticPatchDraftLimitedPromotionActivationReviewDocket(":memory:")
    docket.submit_from_book(source_book, manifest.manifest_id, submitted_at=NOW)
    review(docket, manifest.manifest_id, decision)
    return resources, docket, manifest


class ActivationOperatorPacketTests(unittest.TestCase):
    def test_packet_is_non_authorizing_and_binds_full_final_review(self):
        resources, docket, manifest = reviewed_manifest()
        before = docket.evidence()["report_digest"]
        book = SyntheticPatchDraftLimitedPromotionActivationOperatorPacketBook()
        packet = book.prepare(
            docket,
            manifest.manifest_id,
            governance_snapshot(),
            generated_at=NOW,
        )
        source = docket.get(manifest.manifest_id)
        self.assertEqual(before, docket.evidence()["report_digest"])
        self.assertEqual(packet.manifest_digest, manifest.manifest_digest)
        self.assertEqual(packet.final_review_digest, source.review_digest)
        self.assertEqual(packet.source_receipt_digest, manifest.source_receipt_digest)
        self.assertEqual(packet.source_packet_digest, manifest.source_packet_digest)
        self.assertEqual(packet.candidate_digest, manifest.candidate_digest)
        self.assertEqual(packet.cohort_digest, manifest.cohort_digest)
        self.assertEqual(
            packet.observation_result_digests,
            manifest.observation_result_digests,
        )
        self.assertEqual(packet.rollback_triggers, manifest.rollback_triggers)
        self.assertEqual(packet.requested_scope, ACTIVATION_OPERATOR_PACKET_SCOPE)
        self.assertEqual(packet.allowed_decisions, ACTIVATION_OPERATOR_ALLOWED_DECISIONS)
        self.assertEqual(
            packet.required_acknowledgements,
            ACTIVATION_OPERATOR_REQUIRED_ACKNOWLEDGEMENTS,
        )
        self.assertFalse(packet.operator_decision_recorded)
        self.assertFalse(packet.activation_allowed)
        self.assertFalse(packet.production_activation_allowed)
        close_all(resources, docket)

    def test_pending_held_and_rejected_sources_are_blocked(self):
        resources, source_book, manifest = manifest_source()
        docket = SyntheticPatchDraftLimitedPromotionActivationReviewDocket(":memory:")
        docket.submit_from_book(source_book, manifest.manifest_id, submitted_at=NOW)
        packet_book = SyntheticPatchDraftLimitedPromotionActivationOperatorPacketBook()
        with self.assertRaises(GovernanceRejected):
            packet_book.prepare(
                docket, manifest.manifest_id, governance_snapshot(), generated_at=NOW
            )
        close_all(resources, docket)

        for decision in (
            ActivationManifestReviewDecision.HOLD,
            ActivationManifestReviewDecision.REJECT,
        ):
            resources, docket, manifest = reviewed_manifest(decision=decision)
            with self.assertRaises(GovernanceRejected):
                packet_book.prepare(
                    docket,
                    manifest.manifest_id,
                    governance_snapshot(),
                    generated_at=NOW,
                )
            close_all(resources, docket)

    def test_typed_inputs_time_and_governance_fail_closed(self):
        resources, docket, manifest = reviewed_manifest()
        book = SyntheticPatchDraftLimitedPromotionActivationOperatorPacketBook()
        with self.assertRaises(GovernanceRejected):
            book.prepare(
                object(), manifest.manifest_id, governance_snapshot(), generated_at=NOW
            )
        with self.assertRaises(GovernanceRejected):
            book.prepare(docket, manifest.manifest_id, object(), generated_at=NOW)
        for value in (NOW - timedelta(seconds=1), datetime(2026, 9, 17)):
            with self.assertRaises(GovernanceRejected):
                book.prepare(
                    docket,
                    manifest.manifest_id,
                    governance_snapshot(),
                    generated_at=value,
                )
        changed = governance_snapshot()
        object.__setattr__(changed, "blocker_ids", changed.blocker_ids[:-1])
        with self.assertRaises(GovernanceRejected):
            book.prepare(docket, manifest.manifest_id, changed, generated_at=NOW)
        close_all(resources, docket)

    def test_packet_expires_without_automatic_refresh(self):
        resources, docket, manifest = reviewed_manifest()
        book = SyntheticPatchDraftLimitedPromotionActivationOperatorPacketBook()
        packet = book.prepare(
            docket, manifest.manifest_id, governance_snapshot(), generated_at=NOW
        )
        self.assertEqual(
            book.current_packet(manifest.manifest_id, now=packet.valid_until),
            packet,
        )
        with self.assertRaises(GovernanceRejected):
            book.current_packet(
                manifest.manifest_id,
                now=packet.valid_until + timedelta(microseconds=1),
            )
        replay = book.prepare(
            docket,
            manifest.manifest_id,
            governance_snapshot(),
            generated_at=packet.valid_until + timedelta(days=1),
        )
        self.assertEqual(replay, packet)
        close_all(resources, docket)

    def test_concurrent_preparation_is_idempotent(self):
        resources, docket, manifest = reviewed_manifest()
        book = SyntheticPatchDraftLimitedPromotionActivationOperatorPacketBook()
        snapshot = governance_snapshot()

        def prepare(_):
            return book.prepare(
                docket, manifest.manifest_id, snapshot, generated_at=NOW
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            packets = list(pool.map(prepare, range(8)))
        self.assertTrue(all(packet == packets[0] for packet in packets))
        self.assertEqual(len(book.packets), 1)
        close_all(resources, docket)

    def test_changed_governance_after_creation_fails_closed(self):
        resources, docket, manifest = reviewed_manifest()
        book = SyntheticPatchDraftLimitedPromotionActivationOperatorPacketBook()
        snapshot = governance_snapshot()
        book.prepare(docket, manifest.manifest_id, snapshot, generated_at=NOW)
        object.__setattr__(snapshot, "blocker_ids", snapshot.blocker_ids[:-1])
        with self.assertRaises(GovernanceRejected):
            book.prepare(docket, manifest.manifest_id, snapshot, generated_at=NOW)
        close_all(resources, docket)

    def test_packet_tampering_breaks_chain_and_lookup(self):
        resources, docket, manifest = reviewed_manifest()
        book = SyntheticPatchDraftLimitedPromotionActivationOperatorPacketBook()
        packet = book.prepare(
            docket, manifest.manifest_id, governance_snapshot(), generated_at=NOW
        )
        object.__setattr__(packet, "requested_scope", "PRODUCTION")
        self.assertFalse(book.verify_packet_chain())
        with self.assertRaises(GovernanceRejected):
            book.current_packet(manifest.manifest_id, now=NOW)
        close_all(resources, docket)

    def test_rehashed_identity_tamper_breaks_chain(self):
        resources, docket, manifest = reviewed_manifest()
        book = SyntheticPatchDraftLimitedPromotionActivationOperatorPacketBook()
        packet = book.prepare(
            docket, manifest.manifest_id, governance_snapshot(), generated_at=NOW
        )
        object.__setattr__(
            packet,
            "packet_id",
            "synthetic:limited-promotion-activation-operator-packet:" + "f" * 32,
        )
        object.__setattr__(packet, "packet_digest", "f" * 64)
        self.assertFalse(book.verify_packet_chain())
        close_all(resources, docket)

    def test_source_tampering_blocks_packet_creation(self):
        resources, docket, manifest = reviewed_manifest()
        docket._connection.execute(
            "UPDATE synthetic_activation_manifest_review_records "
            "SET manifest_json = '{}' WHERE manifest_id = ?",
            (manifest.manifest_id,),
        )
        with self.assertRaises(GovernanceRejected):
            SyntheticPatchDraftLimitedPromotionActivationOperatorPacketBook().prepare(
                docket,
                manifest.manifest_id,
                governance_snapshot(),
                generated_at=NOW,
            )
        close_all(resources, docket)

    def test_evidence_proves_non_activating_boundary(self):
        resources, docket, manifest = reviewed_manifest()
        book = SyntheticPatchDraftLimitedPromotionActivationOperatorPacketBook()
        book.prepare(docket, manifest.manifest_id, governance_snapshot(), generated_at=NOW)
        evidence = book.evidence()
        self.assertTrue(evidence["packet_chain_valid"])
        self.assertEqual(
            evidence["maximum_state"],
            "AWAITING_SYNTHETIC_LIMITED_PROMOTION_ACTIVATION_OPERATOR_DECISION",
        )
        for field in (
            "operator_decision_method_present",
            "operator_decision_recorded",
            "candidate_content_present",
            "patch_content_present",
            "diff_content_present",
            "source_code_change_method_present",
            "filesystem_write_method_present",
            "application_method_present",
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
        close_all(resources, docket)


if __name__ == "__main__":
    unittest.main()
