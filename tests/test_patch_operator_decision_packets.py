from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.patch_operator_decision_packets import (
    PATCH_ALLOWED_OPERATOR_DECISIONS,
    PATCH_PACKET_SCOPE,
    PATCH_REQUIRED_ACKNOWLEDGEMENTS,
    SyntheticPatchOperatorDecisionPacketBook,
)
from nurion_pg.synthetic_patch_shadow_review_docket import (
    PatchShadowReviewDecision,
    SyntheticPatchShadowReviewDocket,
)
from tests.test_operator_decision_intake import NOW
from tests.test_operator_decision_packets import governance_snapshot
from tests.test_synthetic_patch_shadow_review_docket import (
    FINDINGS,
    close_resources,
    shadow_source,
)


def reviewed_patch_shadow(*, pass_review: bool = True):
    resources, book, assessment = shadow_source()
    docket = SyntheticPatchShadowReviewDocket(":memory:")
    record = docket.submit_from_book(
        book, assessment.proposal_id, submitted_at=NOW
    )
    if pass_review:
        docket.record_eternian_review(
            record.shadow_id,
            review_id="synthetic:patch-shadow-review:operator-packet",
            reviewer_id="synthetic:eternian-reviewer:patch-operator-packet",
            decision=PatchShadowReviewDecision.PASS,
            findings_digest=FINDINGS,
            reviewed_at=NOW,
        )
    return resources, docket, record, assessment


class PatchOperatorDecisionPacketTests(unittest.TestCase):
    def test_packet_is_non_authorizing_and_full_lineage_bound(self):
        resources, docket, record, assessment = reviewed_patch_shadow()
        before = docket.evidence()["report_digest"]
        book = SyntheticPatchOperatorDecisionPacketBook()
        packet = book.prepare(
            docket, record.shadow_id, governance_snapshot(), generated_at=NOW
        )
        self.assertEqual(before, docket.evidence()["report_digest"])
        self.assertEqual(packet.shadow_id, assessment.shadow_id)
        self.assertEqual(packet.proposal_id, assessment.proposal_id)
        self.assertEqual(packet.proposal_digest, assessment.proposal_digest)
        self.assertEqual(
            packet.implementation_review_digest,
            assessment.source_review_digest,
        )
        self.assertEqual(
            packet.shadow_assessment_digest, assessment.assessment_digest
        )
        self.assertEqual(packet.requested_scope, PATCH_PACKET_SCOPE)
        self.assertEqual(packet.allowed_decisions, PATCH_ALLOWED_OPERATOR_DECISIONS)
        self.assertEqual(
            packet.required_acknowledgements,
            PATCH_REQUIRED_ACKNOWLEDGEMENTS,
        )
        self.assertFalse(packet.operator_decision_recorded)
        self.assertFalse(packet.patch_content_present)
        self.assertFalse(packet.code_change_allowed)
        self.assertFalse(packet.production_activation_allowed)
        self.assertTrue(book.verify_packet_chain())
        close_resources(resources, docket)

    def test_pending_patch_review_cannot_create_packet(self):
        resources, docket, record, _ = reviewed_patch_shadow(pass_review=False)
        with self.assertRaises(GovernanceRejected):
            SyntheticPatchOperatorDecisionPacketBook().prepare(
                docket, record.shadow_id, governance_snapshot(), generated_at=NOW
            )
        close_resources(resources, docket)

    def test_typed_inputs_and_time_are_required(self):
        resources, docket, record, _ = reviewed_patch_shadow()
        book = SyntheticPatchOperatorDecisionPacketBook()
        with self.assertRaises(GovernanceRejected):
            book.prepare(
                object(), record.shadow_id, governance_snapshot(), generated_at=NOW
            )
        with self.assertRaises(GovernanceRejected):
            book.prepare(docket, record.shadow_id, object(), generated_at=NOW)
        with self.assertRaises(GovernanceRejected):
            book.prepare(
                docket,
                record.shadow_id,
                governance_snapshot(),
                generated_at=NOW - timedelta(seconds=1),
            )
        with self.assertRaises(GovernanceRejected):
            book.prepare(
                docket,
                record.shadow_id,
                governance_snapshot(),
                generated_at=datetime(2026, 9, 17),
            )
        close_resources(resources, docket)

    def test_packet_expires_without_automatic_refresh(self):
        resources, docket, record, _ = reviewed_patch_shadow()
        book = SyntheticPatchOperatorDecisionPacketBook()
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
        resources, docket, record, _ = reviewed_patch_shadow()
        book = SyntheticPatchOperatorDecisionPacketBook()
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
        resources, docket, record, _ = reviewed_patch_shadow()
        book = SyntheticPatchOperatorDecisionPacketBook()
        snapshot = governance_snapshot()
        book.prepare(docket, record.shadow_id, snapshot, generated_at=NOW)
        object.__setattr__(snapshot, "blocker_ids", snapshot.blocker_ids[:-1])
        with self.assertRaises(GovernanceRejected):
            book.prepare(docket, record.shadow_id, snapshot, generated_at=NOW)
        close_resources(resources, docket)

    def test_packet_and_source_tampering_fail_closed(self):
        resources, docket, record, _ = reviewed_patch_shadow()
        book = SyntheticPatchOperatorDecisionPacketBook()
        packet = book.prepare(
            docket, record.shadow_id, governance_snapshot(), generated_at=NOW
        )
        object.__setattr__(packet, "requested_scope", "PRODUCTION")
        self.assertFalse(book.verify_packet_chain())
        with self.assertRaises(GovernanceRejected):
            book.current_packet(record.shadow_id, now=NOW)

        clean = SyntheticPatchOperatorDecisionPacketBook()
        docket._connection.execute(
            "UPDATE synthetic_patch_shadow_review_audit "
            "SET actor_id = 'synthetic:tampered'"
        )
        with self.assertRaises(GovernanceRejected):
            clean.prepare(
                docket, record.shadow_id, governance_snapshot(), generated_at=NOW
            )
        close_resources(resources, docket)

    def test_rehashed_packet_identity_tamper_breaks_chain(self):
        resources, docket, record, _ = reviewed_patch_shadow()
        book = SyntheticPatchOperatorDecisionPacketBook()
        packet = book.prepare(
            docket, record.shadow_id, governance_snapshot(), generated_at=NOW
        )
        object.__setattr__(
            packet,
            "packet_id",
            "synthetic:patch-operator-decision-packet:" + "f" * 32,
        )
        object.__setattr__(
            packet,
            "packet_digest",
            canonical_digest(packet.digest_value()),
        )
        self.assertFalse(book.verify_packet_chain())
        with self.assertRaises(GovernanceRejected):
            book.prepare(
                docket, record.shadow_id, governance_snapshot(), generated_at=NOW
            )
        close_resources(resources, docket)

    def test_stored_scope_tampering_is_rejected(self):
        resources, docket, record, _ = reviewed_patch_shadow()
        docket._connection.execute(
            "UPDATE synthetic_patch_shadow_review_dockets "
            "SET assessment_json = '{}' WHERE shadow_id = ?",
            (record.shadow_id,),
        )
        with self.assertRaises(GovernanceRejected):
            SyntheticPatchOperatorDecisionPacketBook().prepare(
                docket, record.shadow_id, governance_snapshot(), generated_at=NOW
            )
        close_resources(resources, docket)

    def test_evidence_exposes_no_decision_patch_apply_or_execution(self):
        resources, docket, record, _ = reviewed_patch_shadow()
        book = SyntheticPatchOperatorDecisionPacketBook()
        book.prepare(docket, record.shadow_id, governance_snapshot(), generated_at=NOW)
        evidence = book.evidence()
        self.assertTrue(evidence["packet_chain_valid"])
        self.assertEqual(evidence["maximum_state"], "AWAITING_OPERATOR_DECISION")
        self.assertEqual(evidence["requested_scope"], PATCH_PACKET_SCOPE)
        for field in (
            "operator_decision_method_present",
            "patch_content_present",
            "code_change_method_present",
            "application_method_present",
            "safety_baseline_relaxation_allowed",
            "execution_method_present",
            "network_access_method_present",
            "external_blocker_close_method_present",
            "personal_data_used",
            "credentials_used",
            "money_movement_executed",
            "production_activation_allowed",
        ):
            self.assertFalse(evidence[field])
        close_resources(resources, docket)


if __name__ == "__main__":
    unittest.main()
