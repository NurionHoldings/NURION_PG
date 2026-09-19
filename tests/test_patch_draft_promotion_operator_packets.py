from __future__ import annotations

import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.patch_draft_promotion_operator_packets import (
    PATCH_DRAFT_PROMOTION_ALLOWED_DECISIONS,
    PATCH_DRAFT_PROMOTION_PACKET_SCOPE,
    PATCH_DRAFT_PROMOTION_REQUIRED_ACKNOWLEDGEMENTS,
    SyntheticPatchDraftPromotionOperatorPacketBook,
)
from nurion_pg.synthetic_patch_draft_shadow_review_docket import (
    PatchDraftShadowReviewDecision,
    SyntheticPatchDraftShadowReviewDocket,
)
from tests.test_operator_decision_packets import governance_snapshot
from tests.test_patch_operator_decision_intake import NOW
from tests.test_synthetic_patch_draft_shadow_review_docket import (
    FINDINGS,
    close_resources,
    shadow_source,
)


def reviewed_shadow(*, pass_review: bool = True):
    resources, book, assessment = shadow_source()
    docket = SyntheticPatchDraftShadowReviewDocket(":memory:")
    record = docket.submit_from_book(book, assessment.manifest_id, submitted_at=NOW)
    if pass_review:
        docket.record_eternian_review(
            record.shadow_id,
            review_id="synthetic:patch-draft-shadow-review:promotion-packet",
            reviewer_id=(
                "synthetic:eternian-reviewer:patch-draft-shadow:promotion-packet"
            ),
            decision=PatchDraftShadowReviewDecision.PASS,
            findings_digest=FINDINGS,
            reviewed_at=NOW,
        )
    return resources, docket, record, assessment


class PatchDraftPromotionOperatorPacketTests(unittest.TestCase):
    def test_packet_is_non_authorizing_and_full_lineage_bound(self):
        resources, docket, record, assessment = reviewed_shadow()
        before = docket.evidence()["report_digest"]
        book = SyntheticPatchDraftPromotionOperatorPacketBook()
        packet = book.prepare(
            docket, record.shadow_id, governance_snapshot(), generated_at=NOW
        )
        self.assertEqual(before, docket.evidence()["report_digest"])
        self.assertEqual(packet.shadow_id, assessment.shadow_id)
        self.assertEqual(packet.manifest_id, assessment.manifest_id)
        self.assertEqual(packet.manifest_digest, assessment.manifest_digest)
        self.assertEqual(packet.source_review_digest, assessment.source_review_digest)
        self.assertEqual(packet.shadow_assessment_digest, assessment.assessment_digest)
        self.assertEqual(packet.requested_scope, PATCH_DRAFT_PROMOTION_PACKET_SCOPE)
        self.assertEqual(
            packet.allowed_decisions, PATCH_DRAFT_PROMOTION_ALLOWED_DECISIONS
        )
        self.assertEqual(
            packet.required_acknowledgements,
            PATCH_DRAFT_PROMOTION_REQUIRED_ACKNOWLEDGEMENTS,
        )
        self.assertFalse(packet.operator_decision_recorded)
        self.assertFalse(packet.patch_content_present)
        self.assertFalse(packet.diff_content_present)
        self.assertFalse(packet.source_code_changed)
        self.assertFalse(packet.filesystem_written)
        close_resources(resources, docket)

    def test_pending_or_nonpass_review_cannot_create_packet(self):
        resources, docket, record, _ = reviewed_shadow(pass_review=False)
        with self.assertRaises(GovernanceRejected):
            SyntheticPatchDraftPromotionOperatorPacketBook().prepare(
                docket, record.shadow_id, governance_snapshot(), generated_at=NOW
            )
        close_resources(resources, docket)

    def test_typed_inputs_and_time_are_required(self):
        resources, docket, record, _ = reviewed_shadow()
        book = SyntheticPatchDraftPromotionOperatorPacketBook()
        with self.assertRaises(GovernanceRejected):
            book.prepare(object(), record.shadow_id, governance_snapshot(), generated_at=NOW)
        with self.assertRaises(GovernanceRejected):
            book.prepare(docket, record.shadow_id, object(), generated_at=NOW)
        for value in (NOW - timedelta(seconds=1), datetime(2026, 9, 17)):
            with self.assertRaises(GovernanceRejected):
                book.prepare(
                    docket, record.shadow_id, governance_snapshot(), generated_at=value
                )
        close_resources(resources, docket)

    def test_packet_expires_without_automatic_refresh(self):
        resources, docket, record, _ = reviewed_shadow()
        book = SyntheticPatchDraftPromotionOperatorPacketBook()
        packet = book.prepare(
            docket, record.shadow_id, governance_snapshot(), generated_at=NOW
        )
        self.assertEqual(
            book.current_packet(record.shadow_id, now=packet.valid_until), packet
        )
        with self.assertRaises(GovernanceRejected):
            book.current_packet(
                record.shadow_id,
                now=packet.valid_until + timedelta(microseconds=1),
            )
        replay = book.prepare(
            docket,
            record.shadow_id,
            governance_snapshot(),
            generated_at=packet.valid_until + timedelta(days=1),
        )
        self.assertEqual(replay, packet)
        close_resources(resources, docket)

    def test_concurrent_preparation_is_idempotent(self):
        resources, docket, record, _ = reviewed_shadow()
        book = SyntheticPatchDraftPromotionOperatorPacketBook()
        snapshot = governance_snapshot()

        def prepare(_):
            return book.prepare(
                docket, record.shadow_id, snapshot, generated_at=NOW
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            packets = list(pool.map(prepare, range(8)))
        self.assertTrue(all(packet == packets[0] for packet in packets))
        self.assertEqual(len(book.packets), 1)
        close_resources(resources, docket)

    def test_changed_governance_is_an_idempotency_collision(self):
        resources, docket, record, _ = reviewed_shadow()
        book = SyntheticPatchDraftPromotionOperatorPacketBook()
        snapshot = governance_snapshot()
        book.prepare(docket, record.shadow_id, snapshot, generated_at=NOW)
        object.__setattr__(snapshot, "blocker_ids", snapshot.blocker_ids[:-1])
        with self.assertRaises(GovernanceRejected):
            book.prepare(docket, record.shadow_id, snapshot, generated_at=NOW)
        close_resources(resources, docket)

    def test_packet_and_source_tampering_fail_closed(self):
        resources, docket, record, _ = reviewed_shadow()
        book = SyntheticPatchDraftPromotionOperatorPacketBook()
        packet = book.prepare(
            docket, record.shadow_id, governance_snapshot(), generated_at=NOW
        )
        object.__setattr__(packet, "requested_scope", "PRODUCTION")
        self.assertFalse(book.verify_packet_chain())
        with self.assertRaises(GovernanceRejected):
            book.current_packet(record.shadow_id, now=NOW)

        clean = SyntheticPatchDraftPromotionOperatorPacketBook()
        docket._connection.execute(
            "UPDATE synthetic_patch_draft_shadow_review_audit "
            "SET actor_id = 'synthetic:tampered'"
        )
        with self.assertRaises(GovernanceRejected):
            clean.prepare(
                docket, record.shadow_id, governance_snapshot(), generated_at=NOW
            )
        close_resources(resources, docket)

    def test_rehashed_packet_identity_tamper_breaks_chain(self):
        resources, docket, record, _ = reviewed_shadow()
        book = SyntheticPatchDraftPromotionOperatorPacketBook()
        packet = book.prepare(
            docket, record.shadow_id, governance_snapshot(), generated_at=NOW
        )
        object.__setattr__(
            packet,
            "packet_id",
            "synthetic:patch-draft-promotion-operator-packet:" + "f" * 32,
        )
        object.__setattr__(packet, "packet_digest", canonical_digest(packet.digest_value()))
        self.assertFalse(book.verify_packet_chain())
        with self.assertRaises(GovernanceRejected):
            book.prepare(
                docket, record.shadow_id, governance_snapshot(), generated_at=NOW
            )
        close_resources(resources, docket)

    def test_stored_scope_and_target_tampering_are_rejected(self):
        resources, docket, record, _ = reviewed_shadow()
        row = docket._connection.execute(
            "SELECT assessment_json FROM synthetic_patch_draft_shadow_review_records "
            "WHERE shadow_id = ?", (record.shadow_id,),
        ).fetchone()
        payload = json.loads(row[0])
        payload["item_results"][0]["target_path_digest"] = "f" * 64
        docket._connection.execute(
            "UPDATE synthetic_patch_draft_shadow_review_records SET assessment_json = ? "
            "WHERE shadow_id = ?",
            (json.dumps(payload, sort_keys=True, separators=(",", ":")), record.shadow_id),
        )
        with self.assertRaises(GovernanceRejected):
            SyntheticPatchDraftPromotionOperatorPacketBook().prepare(
                docket, record.shadow_id, governance_snapshot(), generated_at=NOW
            )
        close_resources(resources, docket)

    def test_evidence_exposes_no_decision_change_apply_or_execution(self):
        resources, docket, record, _ = reviewed_shadow()
        book = SyntheticPatchDraftPromotionOperatorPacketBook()
        book.prepare(docket, record.shadow_id, governance_snapshot(), generated_at=NOW)
        evidence = book.evidence()
        self.assertTrue(evidence["packet_chain_valid"])
        self.assertEqual(
            evidence["maximum_state"],
            "AWAITING_PATCH_DRAFT_PROMOTION_OPERATOR_DECISION",
        )
        self.assertEqual(evidence["requested_scope"], PATCH_DRAFT_PROMOTION_PACKET_SCOPE)
        for field in (
            "operator_decision_method_present", "patch_content_present",
            "diff_content_present", "source_code_change_method_present",
            "filesystem_write_method_present", "application_method_present",
            "safety_baseline_relaxation_method_present", "execution_method_present",
            "network_access_method_present", "external_blocker_close_method_present",
            "automatic_merge_method_present", "automatic_deploy_method_present",
            "personal_data_used", "credentials_used", "money_movement_executed",
            "production_activation_allowed",
        ):
            self.assertFalse(evidence[field])
        close_resources(resources, docket)


if __name__ == "__main__":
    unittest.main()
