from __future__ import annotations

import hmac
import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.operator_decision_intake import (
    DECISION_ENVELOPE_VALIDITY,
    SYNTHETIC_OPERATOR_ID,
    SyntheticOperatorDecision,
    SyntheticOperatorDecisionEnvelope,
    SyntheticOperatorDecisionIntake,
    SyntheticOperatorKeyRegistry,
    SyntheticOperatorVerificationKey,
)
from nurion_pg.operator_decision_packets import (
    PACKET_SCOPE,
    REQUIRED_ACKNOWLEDGEMENTS,
    SyntheticOperatorDecisionPacketBook,
)
from tests.test_operator_decision_packets import (
    NOW,
    governance_snapshot,
    reviewed_shadow,
)


KEY_ID = "synthetic:key:operator-decision:test-1"
SECRET = "synthetic:operator-secret:test-only-000000000001"


def key_registry(*, revoked: bool = False) -> SyntheticOperatorKeyRegistry:
    registry = SyntheticOperatorKeyRegistry()
    registry.register(
        SyntheticOperatorVerificationKey(
            KEY_ID,
            SYNTHETIC_OPERATOR_ID,
            SECRET,
            NOW - timedelta(days=1),
            NOW + timedelta(days=1),
            revoked,
        )
    )
    return registry


def decision_envelope(
    packet,
    *,
    envelope_id: str = "synthetic:operator-decision-envelope:test-1",
    nonce: str = "synthetic:operator-nonce:test-1",
    decision: SyntheticOperatorDecision = (
        SyntheticOperatorDecision.AUTHORIZE_SYNTHETIC_IMPLEMENTATION_PROPOSAL_DRAFT
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
        "requested_scope": PACKET_SCOPE,
        "acknowledgements": list(REQUIRED_ACKNOWLEDGEMENTS),
        "issued_at": issued_at.isoformat(),
        "expires_at": (issued_at + DECISION_ENVELOPE_VALIDITY).isoformat(),
        "nonce": nonce,
        "key_id": key_id,
    }
    signature = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8"),
        sha256,
    ).hexdigest()
    return SyntheticOperatorDecisionEnvelope(
        envelope_id,
        packet.packet_id,
        value["packet_digest"],
        SYNTHETIC_OPERATOR_ID,
        decision,
        PACKET_SCOPE,
        REQUIRED_ACKNOWLEDGEMENTS,
        issued_at,
        issued_at + DECISION_ENVELOPE_VALIDITY,
        nonce,
        key_id,
        signature,
    )


def packet_source():
    case, remediation, shadow_docket, record, _ = reviewed_shadow()
    packet_book = SyntheticOperatorDecisionPacketBook()
    packet = packet_book.prepare(
        shadow_docket, record.shadow_id, governance_snapshot(), generated_at=NOW
    )
    return case, remediation, shadow_docket, record, packet_book, packet


class OperatorDecisionIntakeTests(unittest.TestCase):
    def test_valid_signed_intent_is_verified_without_recording_decision(self):
        case, remediation, docket, record, packet_book, packet = packet_source()
        intake = SyntheticOperatorDecisionIntake(key_registry())
        before = packet_book.evidence()["report_digest"]
        assessment = intake.assess(
            packet_book,
            record.shadow_id,
            decision_envelope(packet),
            received_at=NOW,
        )
        after = packet_book.evidence()["report_digest"]
        self.assertEqual(before, after)
        self.assertEqual(assessment.validation_state, "SYNTHETIC_DECISION_VALIDATED")
        self.assertFalse(assessment.packet_state_changed)
        self.assertFalse(assessment.operator_decision_recorded)
        self.assertFalse(assessment.code_change_allowed)
        self.assertFalse(assessment.automatic_application_allowed)
        self.assertFalse(assessment.execution_allowed)
        self.assertTrue(intake.verify_assessment_chain())
        docket.close()
        remediation.close()
        case.close()

    def test_all_packet_decision_values_can_be_synthetically_validated(self):
        for index, decision in enumerate(SyntheticOperatorDecision, start=1):
            case, remediation, docket, record, packet_book, packet = packet_source()
            intake = SyntheticOperatorDecisionIntake(key_registry())
            assessment = intake.assess(
                packet_book,
                record.shadow_id,
                decision_envelope(
                    packet,
                    envelope_id=f"synthetic:operator-decision-envelope:decision-{index}",
                    nonce=f"synthetic:operator-nonce:decision-{index}",
                    decision=decision,
                ),
                received_at=NOW,
            )
            self.assertEqual(assessment.decision, decision)
            self.assertFalse(assessment.operator_decision_recorded)
            docket.close()
            remediation.close()
            case.close()

    def test_signature_unknown_revoked_and_real_key_material_are_rejected(self):
        case, remediation, docket, record, packet_book, packet = packet_source()
        with self.assertRaises(GovernanceRejected):
            SyntheticOperatorDecisionIntake(key_registry()).assess(
                packet_book,
                record.shadow_id,
                decision_envelope(packet, secret=SECRET + "tampered"),
                received_at=NOW,
            )
        with self.assertRaises(GovernanceRejected):
            SyntheticOperatorDecisionIntake(SyntheticOperatorKeyRegistry()).assess(
                packet_book,
                record.shadow_id,
                decision_envelope(packet),
                received_at=NOW,
            )
        with self.assertRaises(GovernanceRejected):
            SyntheticOperatorDecisionIntake(key_registry(revoked=True)).assess(
                packet_book,
                record.shadow_id,
                decision_envelope(packet),
                received_at=NOW,
            )
        with self.assertRaises(GovernanceRejected):
            SyntheticOperatorVerificationKey(
                KEY_ID,
                SYNTHETIC_OPERATOR_ID,
                "real-looking-secret",
                NOW - timedelta(days=1),
                NOW + timedelta(days=1),
            )
        docket.close()
        remediation.close()
        case.close()

    def test_expired_future_and_packet_mismatch_fail_closed(self):
        case, remediation, docket, record, packet_book, packet = packet_source()
        intake = SyntheticOperatorDecisionIntake(key_registry())
        with self.assertRaises(GovernanceRejected):
            intake.assess(
                packet_book,
                record.shadow_id,
                decision_envelope(packet),
                received_at=NOW + DECISION_ENVELOPE_VALIDITY + timedelta(seconds=1),
            )
        future = NOW + timedelta(minutes=2)
        with self.assertRaises(GovernanceRejected):
            intake.assess(
                packet_book,
                record.shadow_id,
                decision_envelope(packet, issued_at=future),
                received_at=NOW,
            )
        with self.assertRaises(GovernanceRejected):
            intake.assess(
                packet_book,
                record.shadow_id,
                decision_envelope(packet, packet_digest="0" * 64),
                received_at=NOW,
            )
        docket.close()
        remediation.close()
        case.close()

    def test_exact_replay_is_idempotent_and_payload_collision_is_blocked(self):
        case, remediation, docket, record, packet_book, packet = packet_source()
        intake = SyntheticOperatorDecisionIntake(key_registry())
        envelope = decision_envelope(packet)
        first = intake.assess(packet_book, record.shadow_id, envelope, received_at=NOW)
        second = intake.assess(packet_book, record.shadow_id, envelope, received_at=NOW)
        self.assertEqual(first, second)
        collision = decision_envelope(
            packet,
            decision=SyntheticOperatorDecision.HOLD,
        )
        with self.assertRaises(GovernanceRejected):
            intake.assess(packet_book, record.shadow_id, collision, received_at=NOW)
        self.assertEqual(len(intake.assessments), 1)
        docket.close()
        remediation.close()
        case.close()

    def test_nonce_replay_with_new_envelope_is_blocked(self):
        case, remediation, docket, record, packet_book, packet = packet_source()
        intake = SyntheticOperatorDecisionIntake(key_registry())
        intake.assess(
            packet_book, record.shadow_id, decision_envelope(packet), received_at=NOW
        )
        replay = decision_envelope(
            packet,
            envelope_id="synthetic:operator-decision-envelope:test-2",
        )
        with self.assertRaises(GovernanceRejected):
            intake.assess(packet_book, record.shadow_id, replay, received_at=NOW)
        docket.close()
        remediation.close()
        case.close()

    def test_concurrent_exact_replay_records_once(self):
        case, remediation, docket, record, packet_book, packet = packet_source()
        intake = SyntheticOperatorDecisionIntake(key_registry())
        envelope = decision_envelope(packet)

        def assess(_):
            return intake.assess(
                packet_book, record.shadow_id, envelope, received_at=NOW
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(assess, range(8)))
        self.assertTrue(all(result == results[0] for result in results))
        self.assertEqual(len(intake.assessments), 1)
        docket.close()
        remediation.close()
        case.close()

    def test_assessment_tampering_breaks_chain(self):
        case, remediation, docket, record, packet_book, packet = packet_source()
        intake = SyntheticOperatorDecisionIntake(key_registry())
        assessment = intake.assess(
            packet_book, record.shadow_id, decision_envelope(packet), received_at=NOW
        )
        object.__setattr__(assessment, "operator_decision_recorded", True)
        self.assertFalse(intake.verify_assessment_chain())
        with self.assertRaises(GovernanceRejected):
            intake.assess(
                packet_book,
                record.shadow_id,
                decision_envelope(packet),
                received_at=NOW,
            )
        docket.close()
        remediation.close()
        case.close()

    def test_registered_key_mutation_fails_closed(self):
        case, remediation, docket, record, packet_book, packet = packet_source()
        registry = key_registry()
        key = registry._keys[KEY_ID]
        object.__setattr__(key, "secret", "real-secret-after-registration")
        with self.assertRaises(GovernanceRejected):
            SyntheticOperatorDecisionIntake(registry).assess(
                packet_book,
                record.shadow_id,
                decision_envelope(packet, secret="real-secret-after-registration"),
                received_at=NOW,
            )
        docket.close()
        remediation.close()
        case.close()

    def test_evidence_exposes_verification_only_and_no_sign_or_record_method(self):
        case, remediation, docket, record, packet_book, packet = packet_source()
        intake = SyntheticOperatorDecisionIntake(key_registry())
        intake.assess(
            packet_book, record.shadow_id, decision_envelope(packet), received_at=NOW
        )
        evidence = intake.evidence()
        self.assertTrue(evidence["synthetic_verification_only"])
        self.assertTrue(evidence["assessment_chain_valid"])
        self.assertEqual(evidence["maximum_state"], "SYNTHETIC_DECISION_VALIDATED")
        for field in (
            "signing_method_present",
            "operator_decision_recording_method_present",
            "packet_state_changed",
            "code_change_method_present",
            "application_method_present",
            "execution_method_present",
            "money_movement_executed",
            "production_activation_allowed",
        ):
            self.assertFalse(evidence[field])
        docket.close()
        remediation.close()
        case.close()


if __name__ == "__main__":
    unittest.main()
