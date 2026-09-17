"""Synthetic-only verification of signed patch operator intent envelopes."""

from __future__ import annotations

import hmac
import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest
from .operator_decision_intake import (
    DECISION_ENVELOPE_VALIDITY,
    MAX_FUTURE_SKEW,
    SYNTHETIC_OPERATOR_ID,
    SyntheticOperatorKeyRegistry,
)
from .patch_operator_decision_packets import (
    PATCH_ALLOWED_OPERATOR_DECISIONS,
    PATCH_PACKET_SCOPE,
    PATCH_REQUIRED_ACKNOWLEDGEMENTS,
    SyntheticPatchOperatorDecisionPacketBook,
)


class SyntheticPatchOperatorDecision(StrEnum):
    AUTHORIZE_SYNTHETIC_PATCH_DRAFT = "AUTHORIZE_SYNTHETIC_PATCH_DRAFT"
    HOLD = "HOLD"
    REJECT = "REJECT"


def _valid_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _assessment_id(envelope_digest: str) -> str:
    return "synthetic:patch-operator-decision-assessment:" + envelope_digest[:32]


@dataclass(frozen=True)
class SyntheticPatchOperatorDecisionEnvelope:
    envelope_id: str
    packet_id: str
    packet_digest: str
    operator_id: str
    decision: SyntheticPatchOperatorDecision
    requested_scope: str
    acknowledgements: tuple[str, ...]
    issued_at: datetime
    expires_at: datetime
    nonce: str
    key_id: str
    signature: str

    def __post_init__(self) -> None:
        if (
            not self.envelope_id.startswith(
                "synthetic:patch-operator-decision-envelope:"
            )
            or len(self.envelope_id)
            <= len("synthetic:patch-operator-decision-envelope:")
            or not self.packet_id.startswith(
                "synthetic:patch-operator-decision-packet:"
            )
            or not _valid_digest(self.packet_digest)
            or self.operator_id != SYNTHETIC_OPERATOR_ID
            or not isinstance(self.decision, SyntheticPatchOperatorDecision)
            or self.decision.value not in PATCH_ALLOWED_OPERATOR_DECISIONS
            or self.requested_scope != PATCH_PACKET_SCOPE
            or self.acknowledgements != PATCH_REQUIRED_ACKNOWLEDGEMENTS
            or self.issued_at.tzinfo is None
            or self.expires_at != self.issued_at + DECISION_ENVELOPE_VALIDITY
            or not self.nonce.startswith("synthetic:patch-operator-nonce:")
            or len(self.nonce) <= len("synthetic:patch-operator-nonce:")
            or not self.key_id.startswith("synthetic:key:operator-decision:")
            or not self.signature.startswith("sha256=")
            or not _valid_digest(self.signature.removeprefix("sha256="))
        ):
            raise GovernanceRejected(
                "complete synthetic patch operator envelope required"
            )

    def signing_value(self) -> dict[str, object]:
        return {
            "envelope_id": self.envelope_id,
            "packet_id": self.packet_id,
            "packet_digest": self.packet_digest,
            "operator_id": self.operator_id,
            "decision": self.decision.value,
            "requested_scope": self.requested_scope,
            "acknowledgements": list(self.acknowledgements),
            "issued_at": self.issued_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "nonce": self.nonce,
            "key_id": self.key_id,
        }

    def envelope_digest(self) -> str:
        return canonical_digest({**self.signing_value(), "signature": self.signature})


@dataclass(frozen=True)
class PatchOperatorDecisionIntentAssessment:
    sequence: int
    assessment_id: str
    envelope_id: str
    envelope_digest: str
    nonce: str
    packet_id: str
    packet_digest: str
    operator_id: str
    decision: SyntheticPatchOperatorDecision
    assessed_at: datetime
    previous_digest: str
    assessment_digest: str
    validation_state: str = "SYNTHETIC_PATCH_DECISION_VALIDATED"
    packet_state_changed: bool = False
    operator_decision_recorded: bool = False
    patch_content_present: bool = False
    code_change_allowed: bool = False
    automatic_application_allowed: bool = False
    safety_baseline_relaxation_allowed: bool = False
    execution_allowed: bool = False
    production_activation_allowed: bool = False

    def __post_init__(self) -> None:
        if (
            self.sequence <= 0
            or self.assessment_id != _assessment_id(self.envelope_digest)
            or not self.envelope_id.startswith(
                "synthetic:patch-operator-decision-envelope:"
            )
            or not _valid_digest(self.envelope_digest)
            or not self.nonce.startswith("synthetic:patch-operator-nonce:")
            or not self.packet_id.startswith(
                "synthetic:patch-operator-decision-packet:"
            )
            or not _valid_digest(self.packet_digest)
            or self.operator_id != SYNTHETIC_OPERATOR_ID
            or not isinstance(self.decision, SyntheticPatchOperatorDecision)
            or self.assessed_at.tzinfo is None
            or not _valid_digest(self.previous_digest)
            or self.validation_state != "SYNTHETIC_PATCH_DECISION_VALIDATED"
            or self.packet_state_changed
            or self.operator_decision_recorded
            or self.patch_content_present
            or self.code_change_allowed
            or self.automatic_application_allowed
            or self.safety_baseline_relaxation_allowed
            or self.execution_allowed
            or self.production_activation_allowed
            or self.assessment_digest != canonical_digest(self.digest_value())
        ):
            raise GovernanceRejected(
                "valid non-recording patch decision assessment required"
            )

    def digest_value(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "assessment_id": self.assessment_id,
            "envelope_id": self.envelope_id,
            "envelope_digest": self.envelope_digest,
            "nonce": self.nonce,
            "packet_id": self.packet_id,
            "packet_digest": self.packet_digest,
            "operator_id": self.operator_id,
            "decision": self.decision.value,
            "assessed_at": self.assessed_at.isoformat(),
            "previous_digest": self.previous_digest,
            "validation_state": self.validation_state,
            "packet_state_changed": self.packet_state_changed,
            "operator_decision_recorded": self.operator_decision_recorded,
            "patch_content_present": self.patch_content_present,
            "code_change_allowed": self.code_change_allowed,
            "automatic_application_allowed": self.automatic_application_allowed,
            "safety_baseline_relaxation_allowed": (
                self.safety_baseline_relaxation_allowed
            ),
            "execution_allowed": self.execution_allowed,
            "production_activation_allowed": self.production_activation_allowed,
        }


class SyntheticPatchOperatorDecisionIntake:
    """Validates patch intent envelopes without recording an operator decision."""

    def __init__(self, registry: SyntheticOperatorKeyRegistry) -> None:
        if not isinstance(registry, SyntheticOperatorKeyRegistry):
            raise GovernanceRejected("typed synthetic operator key registry required")
        self._registry = registry
        self._assessments: list[PatchOperatorDecisionIntentAssessment] = []
        self._by_envelope: dict[str, PatchOperatorDecisionIntentAssessment] = {}
        self._nonces: dict[str, str] = {}
        self._lock = RLock()

    @property
    def assessments(self) -> tuple[PatchOperatorDecisionIntentAssessment, ...]:
        with self._lock:
            return tuple(self._assessments)

    def assess(
        self,
        packet_book: SyntheticPatchOperatorDecisionPacketBook,
        shadow_id: str,
        envelope: SyntheticPatchOperatorDecisionEnvelope,
        *,
        received_at: datetime,
    ) -> PatchOperatorDecisionIntentAssessment:
        if received_at.tzinfo is None:
            raise GovernanceRejected("timezone-aware patch decision receipt required")
        if not isinstance(packet_book, SyntheticPatchOperatorDecisionPacketBook):
            raise GovernanceRejected("typed patch operator packet book required")
        if not isinstance(envelope, SyntheticPatchOperatorDecisionEnvelope):
            raise GovernanceRejected("typed synthetic patch decision envelope required")
        if received_at < envelope.issued_at - MAX_FUTURE_SKEW:
            raise GovernanceRejected("patch decision envelope is from the future")
        if received_at > envelope.expires_at:
            raise GovernanceRejected("patch decision envelope has expired")
        before = packet_book.evidence()["report_digest"]
        packet = packet_book.current_packet(shadow_id, now=received_at)
        if (
            envelope.packet_id != packet.packet_id
            or envelope.packet_digest != packet.packet_digest
            or envelope.requested_scope != packet.requested_scope
            or envelope.decision.value not in packet.allowed_decisions
            or envelope.acknowledgements != packet.required_acknowledgements
        ):
            raise GovernanceRejected(
                "patch decision envelope is not bound to current packet"
            )
        key = self._registry.resolve(envelope.key_id, issued_at=envelope.issued_at)
        if key.operator_id != envelope.operator_id:
            raise GovernanceRejected("patch decision key identity mismatch")
        expected = "sha256=" + hmac.new(
            key.secret.encode("utf-8"),
            json.dumps(
                envelope.signing_value(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8"),
            sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, envelope.signature):
            raise GovernanceRejected("patch decision signature mismatch")
        envelope_digest = envelope.envelope_digest()
        with self._lock:
            created = False
            if not self.verify_assessment_chain():
                raise GovernanceRejected("existing patch intent evidence is invalid")
            existing = self._by_envelope.get(envelope.envelope_id)
            if existing is not None:
                if existing.envelope_digest != envelope_digest:
                    raise GovernanceRejected("patch envelope idempotency mismatch")
                assessment = existing
            else:
                if envelope.nonce in self._nonces:
                    raise GovernanceRejected("patch decision nonce replay")
                sequence = len(self._assessments) + 1
                previous = (
                    self._assessments[-1].assessment_digest
                    if self._assessments
                    else "0" * 64
                )
                assessment_id = _assessment_id(envelope_digest)
                values = {
                    "sequence": sequence,
                    "assessment_id": assessment_id,
                    "envelope_id": envelope.envelope_id,
                    "envelope_digest": envelope_digest,
                    "nonce": envelope.nonce,
                    "packet_id": packet.packet_id,
                    "packet_digest": packet.packet_digest,
                    "operator_id": envelope.operator_id,
                    "decision": envelope.decision.value,
                    "assessed_at": received_at.isoformat(),
                    "previous_digest": previous,
                    "validation_state": "SYNTHETIC_PATCH_DECISION_VALIDATED",
                    "packet_state_changed": False,
                    "operator_decision_recorded": False,
                    "patch_content_present": False,
                    "code_change_allowed": False,
                    "automatic_application_allowed": False,
                    "safety_baseline_relaxation_allowed": False,
                    "execution_allowed": False,
                    "production_activation_allowed": False,
                }
                assessment = PatchOperatorDecisionIntentAssessment(
                    sequence,
                    assessment_id,
                    envelope.envelope_id,
                    envelope_digest,
                    envelope.nonce,
                    packet.packet_id,
                    packet.packet_digest,
                    envelope.operator_id,
                    envelope.decision,
                    received_at,
                    previous,
                    canonical_digest(values),
                )
                self._assessments.append(assessment)
                self._by_envelope[envelope.envelope_id] = assessment
                self._nonces[envelope.nonce] = envelope_digest
                created = True
            after = packet_book.evidence()["report_digest"]
            if before != after:
                if created:
                    self._assessments.pop()
                    self._by_envelope.pop(envelope.envelope_id, None)
                    self._nonces.pop(envelope.nonce, None)
                raise GovernanceRejected(
                    "patch operator packet changed during validation"
                )
        return assessment

    def verify_assessment_chain(self) -> bool:
        with self._lock:
            previous = "0" * 64
            for sequence, assessment in enumerate(self._assessments, start=1):
                if (
                    assessment.sequence != sequence
                    or assessment.previous_digest != previous
                    or assessment.assessment_id
                    != _assessment_id(assessment.envelope_digest)
                    or assessment.assessment_digest
                    != canonical_digest(assessment.digest_value())
                    or assessment.validation_state
                    != "SYNTHETIC_PATCH_DECISION_VALIDATED"
                    or assessment.packet_state_changed
                    or assessment.operator_decision_recorded
                    or assessment.patch_content_present
                    or assessment.code_change_allowed
                    or assessment.automatic_application_allowed
                    or assessment.safety_baseline_relaxation_allowed
                    or assessment.execution_allowed
                    or assessment.production_activation_allowed
                    or self._by_envelope.get(assessment.envelope_id)
                    is not assessment
                    or self._nonces.get(assessment.nonce)
                    != assessment.envelope_digest
                ):
                    return False
                previous = assessment.assessment_digest
            return (
                len(self._assessments) == len(self._by_envelope)
                and len(self._assessments) == len(self._nonces)
            )

    def evidence(self) -> dict[str, object]:
        with self._lock:
            counts = {
                decision.value: 0 for decision in SyntheticPatchOperatorDecision
            }
            for assessment in self._assessments:
                counts[assessment.decision.value] += 1
            value = {
                "schema": "nurion.pg.synthetic-patch-operator-intake-evidence.v1",
                "decision_counts": counts,
                "assessment_chain_valid": self.verify_assessment_chain(),
                "maximum_state": "SYNTHETIC_PATCH_DECISION_VALIDATED",
                "synthetic_verification_only": True,
                "signing_method_present": False,
                "operator_decision_recording_method_present": False,
                "packet_state_changed": False,
                "patch_content_present": False,
                "code_change_method_present": False,
                "application_method_present": False,
                "safety_baseline_relaxation_allowed": False,
                "execution_method_present": False,
                "network_access_method_present": False,
                "personal_data_used": False,
                "credentials_used": False,
                "money_movement_executed": False,
                "production_activation_allowed": False,
            }
            return {**value, "report_digest": canonical_digest(value)}
