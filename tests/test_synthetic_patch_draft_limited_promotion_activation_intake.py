from __future__ import annotations

import hmac
import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from hashlib import sha256

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.operator_decision_intake import (
    DECISION_ENVELOPE_VALIDITY,
    SYNTHETIC_OPERATOR_ID,
    SyntheticOperatorKeyRegistry,
)
from nurion_pg.synthetic_patch_draft_limited_promotion_activation_intake import (
    ACTIVATION_INTENT_VALIDATION_STATE,
    SyntheticPatchDraftLimitedPromotionActivationDecision,
    SyntheticPatchDraftLimitedPromotionActivationEnvelope,
    SyntheticPatchDraftLimitedPromotionActivationIntake,
)
from nurion_pg.synthetic_patch_draft_limited_promotion_activation_operator_packets import (
    ACTIVATION_OPERATOR_PACKET_SCOPE,
    ACTIVATION_OPERATOR_REQUIRED_ACKNOWLEDGEMENTS,
    SyntheticPatchDraftLimitedPromotionActivationOperatorPacketBook,
)
from tests.test_operator_decision_intake import (
    KEY_ID,
    SECRET,
    key_registry,
)
from tests.test_operator_decision_packets import governance_snapshot
from tests.test_patch_draft_limited_promotion_reconfirmation_intake import NOW
from tests.test_synthetic_patch_draft_limited_promotion_activation_operator_packets import (
    reviewed_manifest,
)
from tests.test_synthetic_patch_draft_limited_promotion_activation_review_docket import (
    close_all,
)


def activation_envelope(
    packet,
    *,
    envelope_id="synthetic:limited-promotion-activation-envelope:test-1",
    nonce="synthetic:limited-promotion-activation-nonce:test-1",
    decision=(
        SyntheticPatchDraftLimitedPromotionActivationDecision
        .AUTHORIZE_SYNTHETIC_LIMITED_PROMOTION_ACTIVATION
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
        "requested_scope": ACTIVATION_OPERATOR_PACKET_SCOPE,
        "acknowledgements": list(
            ACTIVATION_OPERATOR_REQUIRED_ACKNOWLEDGEMENTS
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
    return SyntheticPatchDraftLimitedPromotionActivationEnvelope(
        envelope_id,
        packet.packet_id,
        value["packet_digest"],
        SYNTHETIC_OPERATOR_ID,
        decision,
        ACTIVATION_OPERATOR_PACKET_SCOPE,
        ACTIVATION_OPERATOR_REQUIRED_ACKNOWLEDGEMENTS,
        issued_at,
        issued_at + DECISION_ENVELOPE_VALIDITY,
        nonce,
        key_id,
        signature,
    )


def packet_source():
    resources, docket, manifest = reviewed_manifest()
    packet_book = SyntheticPatchDraftLimitedPromotionActivationOperatorPacketBook()
    packet = packet_book.prepare(
        docket,
        manifest.manifest_id,
        governance_snapshot(),
        generated_at=NOW,
    )
    return resources, docket, manifest, packet_book, packet


class ActivationIntentIntakeTests(unittest.TestCase):
    def test_valid_intent_is_verified_without_recording_or_change(self):
        resources, docket, manifest, packet_book, packet = packet_source()
        intake = SyntheticPatchDraftLimitedPromotionActivationIntake(key_registry())
        before = packet_book.evidence()["report_digest"]
        assessment = intake.assess(
            packet_book,
            manifest.manifest_id,
            activation_envelope(packet),
            received_at=NOW,
        )
        self.assertEqual(before, packet_book.evidence()["report_digest"])
        self.assertEqual(assessment.packet_id, packet.packet_id)
        self.assertEqual(assessment.manifest_id, manifest.manifest_id)
        self.assertEqual(
            assessment.validation_state,
            ACTIVATION_INTENT_VALIDATION_STATE,
        )
        self.assertFalse(assessment.operator_decision_recorded)
        self.assertFalse(assessment.activation_recorded)
        close_all(resources, docket)

    def test_all_allowed_decisions_can_be_validated(self):
        for index, decision in enumerate(
            SyntheticPatchDraftLimitedPromotionActivationDecision,
            start=1,
        ):
            resources, docket, manifest, packet_book, packet = packet_source()
            assessment = SyntheticPatchDraftLimitedPromotionActivationIntake(
                key_registry()
            ).assess(
                packet_book,
                manifest.manifest_id,
                activation_envelope(
                    packet,
                    envelope_id=(
                        "synthetic:limited-promotion-activation-envelope:"
                        f"decision-{index}"
                    ),
                    nonce=(
                        "synthetic:limited-promotion-activation-nonce:"
                        f"decision-{index}"
                    ),
                    decision=decision,
                ),
                received_at=NOW,
            )
            self.assertEqual(assessment.decision, decision)
            self.assertFalse(assessment.operator_decision_recorded)
            close_all(resources, docket)

    def test_signature_unknown_revoked_and_untyped_registry_are_rejected(self):
        resources, docket, manifest, packet_book, packet = packet_source()
        with self.assertRaises(GovernanceRejected):
            SyntheticPatchDraftLimitedPromotionActivationIntake(object())
        with self.assertRaises(GovernanceRejected):
            SyntheticPatchDraftLimitedPromotionActivationIntake(
                key_registry()
            ).assess(
                packet_book,
                manifest.manifest_id,
                activation_envelope(packet, secret=SECRET + "tampered"),
                received_at=NOW,
            )
        with self.assertRaises(GovernanceRejected):
            SyntheticPatchDraftLimitedPromotionActivationIntake(
                SyntheticOperatorKeyRegistry()
            ).assess(
                packet_book,
                manifest.manifest_id,
                activation_envelope(packet),
                received_at=NOW,
            )
        with self.assertRaises(GovernanceRejected):
            SyntheticPatchDraftLimitedPromotionActivationIntake(
                key_registry(revoked=True)
            ).assess(
                packet_book,
                manifest.manifest_id,
                activation_envelope(packet),
                received_at=NOW,
            )
        close_all(resources, docket)

    def test_expired_future_untyped_and_packet_mismatch_fail_closed(self):
        resources, docket, manifest, packet_book, packet = packet_source()
        intake = SyntheticPatchDraftLimitedPromotionActivationIntake(key_registry())
        with self.assertRaises(GovernanceRejected):
            intake.assess(
                object(), manifest.manifest_id, activation_envelope(packet), received_at=NOW
            )
        with self.assertRaises(GovernanceRejected):
            intake.assess(
                packet_book,
                manifest.manifest_id,
                activation_envelope(packet),
                received_at=datetime(2026, 9, 17),
            )
        with self.assertRaises(GovernanceRejected):
            intake.assess(
                packet_book,
                manifest.manifest_id,
                activation_envelope(packet),
                received_at=NOW + DECISION_ENVELOPE_VALIDITY + timedelta(seconds=1),
            )
        with self.assertRaises(GovernanceRejected):
            intake.assess(
                packet_book,
                manifest.manifest_id,
                activation_envelope(packet, issued_at=NOW + timedelta(minutes=2)),
                received_at=NOW,
            )
        with self.assertRaises(GovernanceRejected):
            intake.assess(
                packet_book,
                manifest.manifest_id,
                activation_envelope(packet, packet_digest="0" * 64),
                received_at=NOW,
            )
        close_all(resources, docket)

    def test_exact_replay_is_idempotent_and_collision_is_blocked(self):
        resources, docket, manifest, packet_book, packet = packet_source()
        intake = SyntheticPatchDraftLimitedPromotionActivationIntake(key_registry())
        envelope = activation_envelope(packet)
        first = intake.assess(
            packet_book, manifest.manifest_id, envelope, received_at=NOW
        )
        second = intake.assess(
            packet_book, manifest.manifest_id, envelope, received_at=NOW
        )
        self.assertEqual(first, second)
        collision = activation_envelope(
            packet,
            decision=SyntheticPatchDraftLimitedPromotionActivationDecision.HOLD,
        )
        with self.assertRaises(GovernanceRejected):
            intake.assess(
                packet_book, manifest.manifest_id, collision, received_at=NOW
            )
        self.assertEqual(len(intake.assessments), 1)
        close_all(resources, docket)

    def test_nonce_replay_with_new_envelope_is_blocked(self):
        resources, docket, manifest, packet_book, packet = packet_source()
        intake = SyntheticPatchDraftLimitedPromotionActivationIntake(key_registry())
        intake.assess(
            packet_book,
            manifest.manifest_id,
            activation_envelope(packet),
            received_at=NOW,
        )
        replay = activation_envelope(
            packet,
            envelope_id="synthetic:limited-promotion-activation-envelope:test-2",
        )
        with self.assertRaises(GovernanceRejected):
            intake.assess(
                packet_book, manifest.manifest_id, replay, received_at=NOW
            )
        close_all(resources, docket)

    def test_concurrent_exact_replay_creates_one_assessment(self):
        resources, docket, manifest, packet_book, packet = packet_source()
        intake = SyntheticPatchDraftLimitedPromotionActivationIntake(key_registry())
        envelope = activation_envelope(packet)

        def assess(_):
            return intake.assess(
                packet_book, manifest.manifest_id, envelope, received_at=NOW
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            assessments = list(pool.map(assess, range(8)))
        self.assertTrue(all(item == assessments[0] for item in assessments))
        self.assertEqual(len(intake.assessments), 1)
        close_all(resources, docket)

    def test_assessment_tampering_breaks_chain(self):
        resources, docket, manifest, packet_book, packet = packet_source()
        intake = SyntheticPatchDraftLimitedPromotionActivationIntake(key_registry())
        assessment = intake.assess(
            packet_book,
            manifest.manifest_id,
            activation_envelope(packet),
            received_at=NOW,
        )
        object.__setattr__(assessment, "manifest_id", "synthetic:tampered")
        self.assertFalse(intake.verify_assessment_chain())
        close_all(resources, docket)

    def test_packet_tampering_blocks_validation(self):
        resources, docket, manifest, packet_book, packet = packet_source()
        object.__setattr__(packet, "requested_scope", "PRODUCTION")
        with self.assertRaises(GovernanceRejected):
            SyntheticPatchDraftLimitedPromotionActivationIntake(
                key_registry()
            ).assess(
                packet_book,
                manifest.manifest_id,
                activation_envelope(packet),
                received_at=NOW,
            )
        close_all(resources, docket)

    def test_evidence_proves_verification_only_boundary(self):
        resources, docket, manifest, packet_book, packet = packet_source()
        intake = SyntheticPatchDraftLimitedPromotionActivationIntake(key_registry())
        intake.assess(
            packet_book,
            manifest.manifest_id,
            activation_envelope(packet),
            received_at=NOW,
        )
        evidence = intake.evidence()
        self.assertTrue(evidence["assessment_chain_valid"])
        self.assertTrue(evidence["synthetic_verification_only"])
        self.assertEqual(
            evidence["maximum_state"], ACTIVATION_INTENT_VALIDATION_STATE
        )
        for field in (
            "signing_method_present",
            "operator_decision_recording_method_present",
            "activation_recording_method_present",
            "packet_state_changed",
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
