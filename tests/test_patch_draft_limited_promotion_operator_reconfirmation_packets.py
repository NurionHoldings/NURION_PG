from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.patch_draft_limited_promotion_operator_reconfirmation_packets import (
    LIMITED_PROMOTION_RECONFIRMATION_ALLOWED_DECISIONS,
    LIMITED_PROMOTION_RECONFIRMATION_PACKET_SCOPE,
    LIMITED_PROMOTION_RECONFIRMATION_REQUIRED_ACKNOWLEDGEMENTS,
    SyntheticPatchDraftLimitedPromotionOperatorReconfirmationPacketBook,
)
from nurion_pg.synthetic_patch_draft_limited_promotion_shadow_review_docket import (
    LimitedPromotionShadowReviewDecision,
    SyntheticPatchDraftLimitedPromotionShadowReviewDocket,
)
from tests.test_operator_decision_packets import governance_snapshot
from tests.test_patch_draft_promotion_decision_intake import NOW
from tests.test_synthetic_patch_draft_limited_promotion_shadow_review_docket import (
    close_resources,
    review_record,
    shadow_source,
)


def reviewed_shadow(*, rollback: bool = False, pass_review: bool = True):
    overrides = {"synthetic_regression_detected": True} if rollback else {}
    resources, book, assessment = shadow_source(**overrides)
    docket = SyntheticPatchDraftLimitedPromotionShadowReviewDocket(":memory:")
    record = docket.submit_from_book(
        book, assessment.plan_id, submitted_at=NOW
    )
    if pass_review:
        review_record(
            docket,
            record,
            LimitedPromotionShadowReviewDecision.PASS,
        )
    return resources, docket, record, assessment


class PatchDraftLimitedPromotionOperatorReconfirmationPacketTests(
    unittest.TestCase
):
    def test_packet_is_non_authorizing_and_binds_full_reviewed_scope(self):
        resources, docket, record, assessment = reviewed_shadow()
        before = docket.evidence()["report_digest"]
        book = (
            SyntheticPatchDraftLimitedPromotionOperatorReconfirmationPacketBook()
        )
        packet = book.prepare(
            docket,
            assessment.shadow_id,
            governance_snapshot(),
            generated_at=NOW,
        )
        self.assertEqual(before, docket.evidence()["report_digest"])
        self.assertEqual(packet.shadow_id, assessment.shadow_id)
        self.assertEqual(packet.plan_id, assessment.plan_id)
        self.assertEqual(packet.plan_digest, assessment.plan_digest)
        self.assertEqual(
            packet.source_plan_review_digest,
            assessment.source_review_digest,
        )
        self.assertEqual(packet.candidate_digest, assessment.candidate_digest)
        self.assertEqual(packet.cohort_digest, assessment.cohort_digest)
        self.assertEqual(
            packet.shadow_assessment_digest, assessment.assessment_digest
        )
        self.assertEqual(
            packet.shadow_review_digest,
            docket.get(record.assessment.shadow_id).review_digest,
        )
        self.assertEqual(
            packet.observation_result_digests,
            tuple(item.result_digest for item in assessment.item_results),
        )
        self.assertEqual(
            packet.requested_scope,
            LIMITED_PROMOTION_RECONFIRMATION_PACKET_SCOPE,
        )
        self.assertEqual(
            packet.allowed_decisions,
            LIMITED_PROMOTION_RECONFIRMATION_ALLOWED_DECISIONS,
        )
        self.assertEqual(
            packet.required_acknowledgements,
            LIMITED_PROMOTION_RECONFIRMATION_REQUIRED_ACKNOWLEDGEMENTS,
        )
        self.assertFalse(packet.operator_reconfirmation_recorded)
        self.assertFalse(packet.synthetic_activation_allowed)
        self.assertFalse(packet.production_activation_allowed)
        close_resources(resources, docket)

    def test_pending_held_rejected_and_rollback_sources_are_blocked(self):
        resources, docket, record, assessment = reviewed_shadow(
            pass_review=False
        )
        packet_book = (
            SyntheticPatchDraftLimitedPromotionOperatorReconfirmationPacketBook()
        )
        with self.assertRaises(GovernanceRejected):
            packet_book.prepare(
                docket,
                assessment.shadow_id,
                governance_snapshot(),
                generated_at=NOW,
            )
        close_resources(resources, docket)

        for decision in (
            LimitedPromotionShadowReviewDecision.HOLD,
            LimitedPromotionShadowReviewDecision.REJECT,
        ):
            resources, book, assessment = shadow_source()
            docket = SyntheticPatchDraftLimitedPromotionShadowReviewDocket(
                ":memory:"
            )
            record = docket.submit_from_book(
                book, assessment.plan_id, submitted_at=NOW
            )
            review_record(docket, record, decision)
            with self.assertRaises(GovernanceRejected):
                packet_book.prepare(
                    docket,
                    assessment.shadow_id,
                    governance_snapshot(),
                    generated_at=NOW,
                )
            close_resources(resources, docket)

        resources, docket, _, assessment = reviewed_shadow(rollback=True)
        with self.assertRaises(GovernanceRejected):
            packet_book.prepare(
                docket,
                assessment.shadow_id,
                governance_snapshot(),
                generated_at=NOW,
            )
        close_resources(resources, docket)

    def test_typed_inputs_and_time_fail_closed(self):
        resources, docket, _, assessment = reviewed_shadow()
        book = (
            SyntheticPatchDraftLimitedPromotionOperatorReconfirmationPacketBook()
        )
        with self.assertRaises(GovernanceRejected):
            book.prepare(
                object(),
                assessment.shadow_id,
                governance_snapshot(),
                generated_at=NOW,
            )
        with self.assertRaises(GovernanceRejected):
            book.prepare(
                docket,
                assessment.shadow_id,
                object(),
                generated_at=NOW,
            )
        for value in (NOW - timedelta(seconds=1), datetime(2026, 9, 17)):
            with self.assertRaises(GovernanceRejected):
                book.prepare(
                    docket,
                    assessment.shadow_id,
                    governance_snapshot(),
                    generated_at=value,
                )
        close_resources(resources, docket)

    def test_packet_expires_without_automatic_refresh(self):
        resources, docket, _, assessment = reviewed_shadow()
        book = (
            SyntheticPatchDraftLimitedPromotionOperatorReconfirmationPacketBook()
        )
        packet = book.prepare(
            docket,
            assessment.shadow_id,
            governance_snapshot(),
            generated_at=NOW,
        )
        self.assertEqual(
            book.current_packet(
                assessment.shadow_id, now=packet.valid_until
            ),
            packet,
        )
        with self.assertRaises(GovernanceRejected):
            book.current_packet(
                assessment.shadow_id,
                now=packet.valid_until + timedelta(microseconds=1),
            )
        replay = book.prepare(
            docket,
            assessment.shadow_id,
            governance_snapshot(),
            generated_at=packet.valid_until + timedelta(days=1),
        )
        self.assertEqual(replay, packet)
        close_resources(resources, docket)

    def test_concurrent_preparation_is_idempotent(self):
        resources, docket, _, assessment = reviewed_shadow()
        book = (
            SyntheticPatchDraftLimitedPromotionOperatorReconfirmationPacketBook()
        )
        snapshot = governance_snapshot()

        def prepare(_):
            return book.prepare(
                docket,
                assessment.shadow_id,
                snapshot,
                generated_at=NOW,
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            packets = list(pool.map(prepare, range(8)))
        self.assertTrue(all(packet == packets[0] for packet in packets))
        self.assertEqual(len(book.packets), 1)
        close_resources(resources, docket)

    def test_changed_governance_fails_closed(self):
        resources, docket, _, assessment = reviewed_shadow()
        book = (
            SyntheticPatchDraftLimitedPromotionOperatorReconfirmationPacketBook()
        )
        snapshot = governance_snapshot()
        book.prepare(
            docket,
            assessment.shadow_id,
            snapshot,
            generated_at=NOW,
        )
        object.__setattr__(snapshot, "blocker_ids", snapshot.blocker_ids[:-1])
        with self.assertRaises(GovernanceRejected):
            book.prepare(
                docket,
                assessment.shadow_id,
                snapshot,
                generated_at=NOW,
            )
        close_resources(resources, docket)

    def test_packet_tampering_breaks_chain_and_lookup(self):
        resources, docket, _, assessment = reviewed_shadow()
        book = (
            SyntheticPatchDraftLimitedPromotionOperatorReconfirmationPacketBook()
        )
        packet = book.prepare(
            docket,
            assessment.shadow_id,
            governance_snapshot(),
            generated_at=NOW,
        )
        object.__setattr__(packet, "requested_scope", "PRODUCTION")
        self.assertFalse(book.verify_packet_chain())
        with self.assertRaises(GovernanceRejected):
            book.current_packet(assessment.shadow_id, now=NOW)
        close_resources(resources, docket)

    def test_rehashed_identity_tamper_breaks_chain(self):
        resources, docket, _, assessment = reviewed_shadow()
        book = (
            SyntheticPatchDraftLimitedPromotionOperatorReconfirmationPacketBook()
        )
        packet = book.prepare(
            docket,
            assessment.shadow_id,
            governance_snapshot(),
            generated_at=NOW,
        )
        object.__setattr__(
            packet,
            "packet_id",
            "synthetic:patch-draft-limited-promotion-reconfirmation:"
            + "f" * 32,
        )
        object.__setattr__(
            packet,
            "packet_digest",
            canonical_digest(packet.digest_value()),
        )
        self.assertFalse(book.verify_packet_chain())
        close_resources(resources, docket)

    def test_source_tampering_blocks_packet_creation(self):
        resources, docket, _, assessment = reviewed_shadow()
        docket._connection.execute(
            "UPDATE synthetic_limited_promotion_shadow_review_audit "
            "SET actor_id = 'synthetic:tampered'"
        )
        with self.assertRaises(GovernanceRejected):
            SyntheticPatchDraftLimitedPromotionOperatorReconfirmationPacketBook().prepare(
                docket,
                assessment.shadow_id,
                governance_snapshot(),
                generated_at=NOW,
            )
        close_resources(resources, docket)

    def test_evidence_exposes_no_reconfirmation_or_activation(self):
        resources, docket, _, assessment = reviewed_shadow()
        book = (
            SyntheticPatchDraftLimitedPromotionOperatorReconfirmationPacketBook()
        )
        book.prepare(
            docket,
            assessment.shadow_id,
            governance_snapshot(),
            generated_at=NOW,
        )
        evidence = book.evidence()
        self.assertTrue(evidence["packet_chain_valid"])
        self.assertEqual(
            evidence["maximum_state"],
            "AWAITING_PATCH_DRAFT_LIMITED_PROMOTION_OPERATOR_RECONFIRMATION",
        )
        self.assertEqual(
            evidence["requested_scope"],
            LIMITED_PROMOTION_RECONFIRMATION_PACKET_SCOPE,
        )
        for field in (
            "operator_reconfirmation_method_present",
            "operator_reconfirmation_recorded",
            "candidate_content_present",
            "patch_content_present",
            "diff_content_present",
            "source_code_change_method_present",
            "filesystem_write_method_present",
            "application_method_present",
            "safety_baseline_relaxation_method_present",
            "execution_method_present",
            "synthetic_activation_allowed",
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
        close_resources(resources, docket)


if __name__ == "__main__":
    unittest.main()
