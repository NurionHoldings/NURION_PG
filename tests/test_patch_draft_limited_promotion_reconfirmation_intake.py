from __future__ import annotations

import hmac
import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from hashlib import sha256

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.operator_decision_intake import (
    DECISION_ENVELOPE_VALIDITY,
    SYNTHETIC_OPERATOR_ID,
    SyntheticOperatorKeyRegistry,
)
from nurion_pg.patch_draft_limited_promotion_operator_reconfirmation_packets import (
    LIMITED_PROMOTION_RECONFIRMATION_PACKET_SCOPE,
    LIMITED_PROMOTION_RECONFIRMATION_REQUIRED_ACKNOWLEDGEMENTS,
    SyntheticPatchDraftLimitedPromotionOperatorReconfirmationPacketBook,
)
from nurion_pg.patch_draft_limited_promotion_reconfirmation_intake import (
    LIMITED_PROMOTION_RECONFIRMATION_VALIDATION_STATE,
    SyntheticPatchDraftLimitedPromotionReconfirmationDecision,
    SyntheticPatchDraftLimitedPromotionReconfirmationEnvelope,
    SyntheticPatchDraftLimitedPromotionReconfirmationIntake,
)
from tests.test_operator_decision_intake import (
    KEY_ID,
    SECRET,
    key_registry,
)
from tests.test_operator_decision_packets import governance_snapshot
from tests.test_patch_draft_limited_promotion_operator_reconfirmation_packets import (
    reviewed_shadow,
)
from tests.test_patch_draft_promotion_decision_intake import NOW
from tests.test_synthetic_patch_draft_limited_promotion_shadow_review_docket import (
    close_resources,
)


def reconfirmation_envelope(
    packet,
    *,
    envelope_id=(
        "synthetic:patch-draft-limited-promotion-"
        "reconfirmation-envelope:test-1"
    ),
    nonce=(
        "synthetic:patch-draft-limited-promotion-"
        "reconfirmation-nonce:test-1"
    ),
    decision=(
        SyntheticPatchDraftLimitedPromotionReconfirmationDecision
        .RECONFIRM_SYNTHETIC_PATCH_DRAFT_LIMITED_PROMOTION
    ),
    issued_at=NOW,
    packet_digest: str | None = None,
    secret: str = SECRET,
    key_id: str = KEY_ID,
):
    value = {
        "envelope_id": envelope_id,
        "packet_id": packet.packet_id,
        "packet_digest": packet_digest or packet.packet_digest,
        "operator_id": SYNTHETIC_OPERATOR_ID,
        "decision": decision.value,
        "requested_scope": LIMITED_PROMOTION_RECONFIRMATION_PACKET_SCOPE,
        "acknowledgements": list(
            LIMITED_PROMOTION_RECONFIRMATION_REQUIRED_ACKNOWLEDGEMENTS
        ),
        "issued_at": issued_at.isoformat(),
        "expires_at": (issued_at + DECISION_ENVELOPE_VALIDITY).isoformat(),
        "nonce": nonce,
        "key_id": key_id,
    }
    signature = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8"),
        sha256,
    ).hexdigest()
    return SyntheticPatchDraftLimitedPromotionReconfirmationEnvelope(
        envelope_id,
        packet.packet_id,
        value["packet_digest"],
        SYNTHETIC_OPERATOR_ID,
        decision,
        LIMITED_PROMOTION_RECONFIRMATION_PACKET_SCOPE,
        LIMITED_PROMOTION_RECONFIRMATION_REQUIRED_ACKNOWLEDGEMENTS,
        issued_at,
        issued_at + DECISION_ENVELOPE_VALIDITY,
        nonce,
        key_id,
        signature,
    )


def packet_source():
    resources, docket, record, assessment = reviewed_shadow()
    packet_book = (
        SyntheticPatchDraftLimitedPromotionOperatorReconfirmationPacketBook()
    )
    packet = packet_book.prepare(
        docket,
        assessment.shadow_id,
        governance_snapshot(),
        generated_at=NOW,
    )
    return resources, docket, record, packet_book, packet


class PatchDraftLimitedPromotionReconfirmationIntakeTests(
    unittest.TestCase
):
    def test_valid_intent_is_verified_without_recording_or_change(self):
        resources, docket, record, packet_book, packet = packet_source()
        intake = SyntheticPatchDraftLimitedPromotionReconfirmationIntake(
            key_registry()
        )
        before = packet_book.evidence()["report_digest"]
        assessment = intake.assess(
            packet_book,
            record.assessment.shadow_id,
            reconfirmation_envelope(packet),
            received_at=NOW,
        )
        self.assertEqual(before, packet_book.evidence()["report_digest"])
        self.assertEqual(assessment.packet_id, packet.packet_id)
        self.assertEqual(assessment.shadow_id, packet.shadow_id)
        self.assertEqual(
            assessment.validation_state,
            LIMITED_PROMOTION_RECONFIRMATION_VALIDATION_STATE,
        )
        self.assertFalse(assessment.operator_reconfirmation_recorded)
        self.assertFalse(assessment.synthetic_activation_allowed)
        close_resources(resources, docket)

    def test_all_allowed_decisions_can_be_validated(self):
        for index, decision in enumerate(
            SyntheticPatchDraftLimitedPromotionReconfirmationDecision,
            start=1,
        ):
            resources, docket, record, packet_book, packet = packet_source()
            assessment = (
                SyntheticPatchDraftLimitedPromotionReconfirmationIntake(
                    key_registry()
                ).assess(
                    packet_book,
                    record.assessment.shadow_id,
                    reconfirmation_envelope(
                        packet,
                        envelope_id=(
                            "synthetic:patch-draft-limited-promotion-"
                            f"reconfirmation-envelope:decision-{index}"
                        ),
                        nonce=(
                            "synthetic:patch-draft-limited-promotion-"
                            f"reconfirmation-nonce:decision-{index}"
                        ),
                        decision=decision,
                    ),
                    received_at=NOW,
                )
            )
            self.assertEqual(assessment.decision, decision)
            self.assertFalse(assessment.operator_reconfirmation_recorded)
            close_resources(resources, docket)

    def test_signature_unknown_revoked_and_untyped_registry_are_rejected(self):
        resources, docket, record, packet_book, packet = packet_source()
        with self.assertRaises(GovernanceRejected):
            SyntheticPatchDraftLimitedPromotionReconfirmationIntake(object())
        with self.assertRaises(GovernanceRejected):
            SyntheticPatchDraftLimitedPromotionReconfirmationIntake(
                key_registry()
            ).assess(
                packet_book,
                record.assessment.shadow_id,
                reconfirmation_envelope(packet, secret=SECRET + "tampered"),
                received_at=NOW,
            )
        with self.assertRaises(GovernanceRejected):
            SyntheticPatchDraftLimitedPromotionReconfirmationIntake(
                SyntheticOperatorKeyRegistry()
            ).assess(
                packet_book,
                record.assessment.shadow_id,
                reconfirmation_envelope(packet),
                received_at=NOW,
            )
        with self.assertRaises(GovernanceRejected):
            SyntheticPatchDraftLimitedPromotionReconfirmationIntake(
                key_registry(revoked=True)
            ).assess(
                packet_book,
                record.assessment.shadow_id,
                reconfirmation_envelope(packet),
                received_at=NOW,
            )
        close_resources(resources, docket)

    def test_expired_future_untyped_and_packet_mismatch_fail_closed(self):
        resources, docket, record, packet_book, packet = packet_source()
        intake = SyntheticPatchDraftLimitedPromotionReconfirmationIntake(
            key_registry()
        )
        with self.assertRaises(GovernanceRejected):
            intake.assess(
                object(),
                record.assessment.shadow_id,
                reconfirmation_envelope(packet),
                received_at=NOW,
            )
        with self.assertRaises(GovernanceRejected):
            intake.assess(
                packet_book,
                record.assessment.shadow_id,
                reconfirmation_envelope(packet),
                received_at=datetime(2026, 9, 17),
            )
        with self.assertRaises(GovernanceRejected):
            intake.assess(
                packet_book,
                record.assessment.shadow_id,
                reconfirmation_envelope(packet),
                received_at=(
                    NOW + DECISION_ENVELOPE_VALIDITY + timedelta(seconds=1)
                ),
            )
        with self.assertRaises(GovernanceRejected):
            intake.assess(
                packet_book,
                record.assessment.shadow_id,
                reconfirmation_envelope(
                    packet, issued_at=NOW + timedelta(minutes=2)
                ),
                received_at=NOW,
            )
        with self.assertRaises(GovernanceRejected):
            intake.assess(
                packet_book,
                record.assessment.shadow_id,
                reconfirmation_envelope(packet, packet_digest="0" * 64),
                received_at=NOW,
            )
        close_resources(resources, docket)

    def test_exact_replay_is_idempotent_and_collision_is_blocked(self):
        resources, docket, record, packet_book, packet = packet_source()
        intake = SyntheticPatchDraftLimitedPromotionReconfirmationIntake(
            key_registry()
        )
        envelope = reconfirmation_envelope(packet)
        first = intake.assess(
            packet_book,
            record.assessment.shadow_id,
            envelope,
            received_at=NOW,
        )
        second = intake.assess(
            packet_book,
            record.assessment.shadow_id,
            envelope,
            received_at=NOW,
        )
        self.assertEqual(first, second)
        collision = reconfirmation_envelope(
            packet,
            decision=(
                SyntheticPatchDraftLimitedPromotionReconfirmationDecision.HOLD
            ),
        )
        with self.assertRaises(GovernanceRejected):
            intake.assess(
                packet_book,
                record.assessment.shadow_id,
                collision,
                received_at=NOW,
            )
        self.assertEqual(len(intake.assessments), 1)
        close_resources(resources, docket)

    def test_nonce_replay_with_new_envelope_is_blocked(self):
        resources, docket, record, packet_book, packet = packet_source()
        intake = SyntheticPatchDraftLimitedPromotionReconfirmationIntake(
            key_registry()
        )
        intake.assess(
            packet_book,
            record.assessment.shadow_id,
            reconfirmation_envelope(packet),
            received_at=NOW,
        )
        replay = reconfirmation_envelope(
            packet,
            envelope_id=(
                "synthetic:patch-draft-limited-promotion-"
                "reconfirmation-envelope:test-2"
            ),
        )
        with self.assertRaises(GovernanceRejected):
            intake.assess(
                packet_book,
                record.assessment.shadow_id,
                replay,
                received_at=NOW,
            )
        close_resources(resources, docket)

    def test_concurrent_exact_replay_records_once(self):
        resources, docket, record, packet_book, packet = packet_source()
        intake = SyntheticPatchDraftLimitedPromotionReconfirmationIntake(
            key_registry()
        )
        envelope = reconfirmation_envelope(packet)

        def assess(_):
            return intake.assess(
                packet_book,
                record.assessment.shadow_id,
                envelope,
                received_at=NOW,
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(assess, range(8)))
        self.assertTrue(all(result == results[0] for result in results))
        self.assertEqual(len(intake.assessments), 1)
        close_resources(resources, docket)

    def test_assessment_and_rehashed_identity_tampering_break_chain(self):
        resources, docket, record, packet_book, packet = packet_source()
        intake = SyntheticPatchDraftLimitedPromotionReconfirmationIntake(
            key_registry()
        )
        assessment = intake.assess(
            packet_book,
            record.assessment.shadow_id,
            reconfirmation_envelope(packet),
            received_at=NOW,
        )
        object.__setattr__(assessment, "assessment_id", "synthetic:tampered")
        object.__setattr__(
            assessment,
            "assessment_digest",
            canonical_digest(assessment.digest_value()),
        )
        self.assertFalse(intake.verify_assessment_chain())
        with self.assertRaises(GovernanceRejected):
            intake.assess(
                packet_book,
                record.assessment.shadow_id,
                reconfirmation_envelope(packet),
                received_at=NOW,
            )
        close_resources(resources, docket)

    def test_nonce_index_tampering_breaks_chain(self):
        resources, docket, record, packet_book, packet = packet_source()
        intake = SyntheticPatchDraftLimitedPromotionReconfirmationIntake(
            key_registry()
        )
        assessment = intake.assess(
            packet_book,
            record.assessment.shadow_id,
            reconfirmation_envelope(packet),
            received_at=NOW,
        )
        intake._nonces[assessment.nonce] = "f" * 64
        self.assertFalse(intake.verify_assessment_chain())
        close_resources(resources, docket)

    def test_evidence_is_verification_only(self):
        resources, docket, record, packet_book, packet = packet_source()
        intake = SyntheticPatchDraftLimitedPromotionReconfirmationIntake(
            key_registry()
        )
        intake.assess(
            packet_book,
            record.assessment.shadow_id,
            reconfirmation_envelope(packet),
            received_at=NOW,
        )
        evidence = intake.evidence()
        self.assertTrue(evidence["synthetic_verification_only"])
        self.assertTrue(evidence["assessment_chain_valid"])
        self.assertEqual(
            evidence["maximum_state"],
            LIMITED_PROMOTION_RECONFIRMATION_VALIDATION_STATE,
        )
        for field in (
            "signing_method_present",
            "operator_reconfirmation_recording_method_present",
            "packet_state_changed",
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
