"""Synthetic-only validation of signed operator decision intent envelopes."""

from __future__ import annotations

import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from hashlib import sha256
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest
from .operator_decision_packets import (
    ALLOWED_OPERATOR_DECISIONS,
    PACKET_SCOPE,
    REQUIRED_ACKNOWLEDGEMENTS,
    SyntheticOperatorDecisionPacketBook,
)


SYNTHETIC_OPERATOR_ID = "synthetic:operator:CHOI_IN_SEOK"
DECISION_ENVELOPE_VALIDITY = timedelta(minutes=10)
MAX_FUTURE_SKEW = timedelta(seconds=30)


class SyntheticOperatorDecision(StrEnum):
    AUTHORIZE_SYNTHETIC_IMPLEMENTATION_PROPOSAL_DRAFT = (
        "AUTHORIZE_SYNTHETIC_IMPLEMENTATION_PROPOSAL_DRAFT"
    )
    HOLD = "HOLD"
    REJECT = "REJECT"


@dataclass(frozen=True)
class SyntheticOperatorVerificationKey:
    key_id: str
    operator_id: str
    secret: str
    valid_from: datetime
    valid_until: datetime
    revoked: bool = False

    def __post_init__(self) -> None:
        if (
            not self.key_id.startswith("synthetic:key:operator-decision:")
            or self.operator_id != SYNTHETIC_OPERATOR_ID
            or not self.secret.startswith("synthetic:operator-secret:")
            or len(self.secret) < 32
            or self.valid_from.tzinfo is None
            or self.valid_until.tzinfo is None
            or self.valid_until <= self.valid_from
            or not isinstance(self.revoked, bool)
        ):
            raise GovernanceRejected("valid synthetic operator verification key required")


class SyntheticOperatorKeyRegistry:
    """In-memory synthetic verification keys; never loads production credentials."""

    def __init__(self) -> None:
        self._keys: dict[str, SyntheticOperatorVerificationKey] = {}
        self._lock = RLock()

    def register(self, key: SyntheticOperatorVerificationKey) -> None:
        if not isinstance(key, SyntheticOperatorVerificationKey):
            raise GovernanceRejected("typed synthetic operator key required")
        with self._lock:
            existing = self._keys.get(key.key_id)
            if existing is not None and existing != key:
                raise GovernanceRejected("operator verification key identity collision")
            self._keys[key.key_id] = key

    def resolve(self, key_id: str, *, issued_at: datetime) -> SyntheticOperatorVerificationKey:
        with self._lock:
            key = self._keys.get(key_id)
            if (
                key is None
                or not key.key_id.startswith("synthetic:key:operator-decision:")
                or key.operator_id != SYNTHETIC_OPERATOR_ID
                or not key.secret.startswith("synthetic:operator-secret:")
                or len(key.secret) < 32
                or key.valid_from.tzinfo is None
                or key.valid_until.tzinfo is None
                or key.valid_until <= key.valid_from
                or not isinstance(key.revoked, bool)
                or key.revoked
                or issued_at < key.valid_from
                or issued_at > key.valid_until
            ):
                raise GovernanceRejected("current synthetic operator verification key required")
            return key


@dataclass(frozen=True)
class SyntheticOperatorDecisionEnvelope:
    envelope_id: str
    packet_id: str
    packet_digest: str
    operator_id: str
    decision: SyntheticOperatorDecision
    requested_scope: str
    acknowledgements: tuple[str, ...]
    issued_at: datetime
    expires_at: datetime
    nonce: str
    key_id: str
    signature: str

    def __post_init__(self) -> None:
        if (
            not self.envelope_id.startswith("synthetic:operator-decision-envelope:")
            or len(self.envelope_id)
            <= len("synthetic:operator-decision-envelope:")
            or not self.packet_id.startswith("synthetic:operator-decision-packet:")
            or not _valid_digest(self.packet_digest)
            or self.operator_id != SYNTHETIC_OPERATOR_ID
            or not isinstance(self.decision, SyntheticOperatorDecision)
            or self.decision.value not in ALLOWED_OPERATOR_DECISIONS
            or self.requested_scope != PACKET_SCOPE
            or self.acknowledgements != REQUIRED_ACKNOWLEDGEMENTS
            or self.issued_at.tzinfo is None
            or self.expires_at != self.issued_at + DECISION_ENVELOPE_VALIDITY
            or not self.nonce.startswith("synthetic:operator-nonce:")
            or len(self.nonce) <= len("synthetic:operator-nonce:")
            or not self.key_id.startswith("synthetic:key:operator-decision:")
            or not self.signature.startswith("sha256=")
            or not _valid_digest(self.signature.removeprefix("sha256="))
        ):
            raise GovernanceRejected("complete synthetic operator decision envelope required")

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
class OperatorDecisionIntentAssessment:
    sequence: int
    assessment_id: str
    envelope_id: str
    envelope_digest: str
    packet_id: str
    packet_digest: str
    operator_id: str
    decision: SyntheticOperatorDecision
    assessed_at: datetime
    previous_digest: str
    assessment_digest: str
    validation_state: str = "SYNTHETIC_DECISION_VALIDATED"
    packet_state_changed: bool = False
    operator_decision_recorded: bool = False
    code_change_allowed: bool = False
    automatic_application_allowed: bool = False
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if (
            self.sequence <= 0
            or not self.assessment_id.startswith(
                "synthetic:operator-decision-assessment:"
            )
            or not self.envelope_id.startswith("synthetic:operator-decision-envelope:")
            or not _valid_digest(self.envelope_digest)
            or not self.packet_id.startswith("synthetic:operator-decision-packet:")
            or not _valid_digest(self.packet_digest)
            or self.operator_id != SYNTHETIC_OPERATOR_ID
            or not isinstance(self.decision, SyntheticOperatorDecision)
            or self.assessed_at.tzinfo is None
            or not _valid_digest(self.previous_digest)
            or self.validation_state != "SYNTHETIC_DECISION_VALIDATED"
            or self.packet_state_changed
            or self.operator_decision_recorded
            or self.code_change_allowed
            or self.automatic_application_allowed
            or self.execution_allowed
            or self.assessment_digest != canonical_digest(self.digest_value())
        ):
            raise GovernanceRejected("valid non-recording decision assessment required")

    def digest_value(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "assessment_id": self.assessment_id,
            "envelope_id": self.envelope_id,
            "envelope_digest": self.envelope_digest,
            "packet_id": self.packet_id,
            "packet_digest": self.packet_digest,
            "operator_id": self.operator_id,
            "decision": self.decision.value,
            "assessed_at": self.assessed_at.isoformat(),
            "previous_digest": self.previous_digest,
            "validation_state": self.validation_state,
            "packet_state_changed": self.packet_state_changed,
            "operator_decision_recorded": self.operator_decision_recorded,
            "code_change_allowed": self.code_change_allowed,
            "automatic_application_allowed": self.automatic_application_allowed,
            "execution_allowed": self.execution_allowed,
        }


def _valid_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


class SyntheticOperatorDecisionIntake:
    """Validates synthetic intent envelopes and never records an operator decision."""

    def __init__(self, registry: SyntheticOperatorKeyRegistry) -> None:
        self._registry = registry
        self._assessments: list[OperatorDecisionIntentAssessment] = []
        self._by_envelope: dict[str, OperatorDecisionIntentAssessment] = {}
        self._nonces: dict[str, str] = {}
        self._lock = RLock()

    @property
    def assessments(self) -> tuple[OperatorDecisionIntentAssessment, ...]:
        with self._lock:
            return tuple(self._assessments)

    def assess(
        self,
        packet_book: SyntheticOperatorDecisionPacketBook,
        shadow_id: str,
        envelope: SyntheticOperatorDecisionEnvelope,
        *,
        received_at: datetime,
    ) -> OperatorDecisionIntentAssessment:
        if received_at.tzinfo is None:
            raise GovernanceRejected("timezone-aware decision receipt required")
        if not isinstance(envelope, SyntheticOperatorDecisionEnvelope):
            raise GovernanceRejected("typed synthetic decision envelope required")
        if received_at < envelope.issued_at - MAX_FUTURE_SKEW:
            raise GovernanceRejected("operator decision envelope is from the future")
        if received_at > envelope.expires_at:
            raise GovernanceRejected("operator decision envelope has expired")
        before = packet_book.evidence()["report_digest"]
        packet = packet_book.current_packet(shadow_id, now=received_at)
        if (
            envelope.packet_id != packet.packet_id
            or envelope.packet_digest != packet.packet_digest
            or envelope.requested_scope != packet.requested_scope
            or envelope.decision.value not in packet.allowed_decisions
            or envelope.acknowledgements != packet.required_acknowledgements
        ):
            raise GovernanceRejected("decision envelope is not bound to current packet")
        key = self._registry.resolve(envelope.key_id, issued_at=envelope.issued_at)
        if key.operator_id != envelope.operator_id:
            raise GovernanceRejected("operator decision key identity mismatch")
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
            raise GovernanceRejected("operator decision signature mismatch")
        envelope_digest = envelope.envelope_digest()
        created = False
        with self._lock:
            existing = self._by_envelope.get(envelope.envelope_id)
            if existing is not None:
                if existing.envelope_digest != envelope_digest:
                    raise GovernanceRejected("operator envelope idempotency mismatch")
                if not self.verify_assessment_chain():
                    raise GovernanceRejected(
                        "existing operator intent evidence is invalid"
                    )
                assessment = existing
            else:
                nonce_digest = self._nonces.get(envelope.nonce)
                if nonce_digest is not None:
                    raise GovernanceRejected("operator decision nonce replay")
                sequence = len(self._assessments) + 1
                previous = (
                    self._assessments[-1].assessment_digest
                    if self._assessments
                    else "0" * 64
                )
                assessment_id = (
                    "synthetic:operator-decision-assessment:"
                    + envelope_digest[:32]
                )
                values = {
                    "sequence": sequence,
                    "assessment_id": assessment_id,
                    "envelope_id": envelope.envelope_id,
                    "envelope_digest": envelope_digest,
                    "packet_id": packet.packet_id,
                    "packet_digest": packet.packet_digest,
                    "operator_id": envelope.operator_id,
                    "decision": envelope.decision.value,
                    "assessed_at": received_at.isoformat(),
                    "previous_digest": previous,
                    "validation_state": "SYNTHETIC_DECISION_VALIDATED",
                    "packet_state_changed": False,
                    "operator_decision_recorded": False,
                    "code_change_allowed": False,
                    "automatic_application_allowed": False,
                    "execution_allowed": False,
                }
                assessment = OperatorDecisionIntentAssessment(
                    sequence,
                    assessment_id,
                    envelope.envelope_id,
                    envelope_digest,
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
                with self._lock:
                    self._assessments.pop()
                    self._by_envelope.pop(envelope.envelope_id, None)
                    self._nonces.pop(envelope.nonce, None)
            raise GovernanceRejected("operator decision packet changed during validation")
        return assessment

    def verify_assessment_chain(self) -> bool:
        with self._lock:
            previous = "0" * 64
            for sequence, assessment in enumerate(self._assessments, start=1):
                if (
                    assessment.sequence != sequence
                    or assessment.previous_digest != previous
                    or assessment.assessment_digest
                    != canonical_digest(assessment.digest_value())
                    or assessment.validation_state != "SYNTHETIC_DECISION_VALIDATED"
                    or assessment.packet_state_changed
                    or assessment.operator_decision_recorded
                    or assessment.code_change_allowed
                    or assessment.automatic_application_allowed
                    or assessment.execution_allowed
                ):
                    return False
                previous = assessment.assessment_digest
            return True

    def evidence(self) -> dict[str, object]:
        with self._lock:
            counts = {decision.value: 0 for decision in SyntheticOperatorDecision}
            for assessment in self._assessments:
                counts[assessment.decision.value] += 1
            value = {
                "schema": "nurion.pg.synthetic-operator-decision-intake-evidence.v1",
                "decision_counts": counts,
                "assessment_chain_valid": self.verify_assessment_chain(),
                "maximum_state": "SYNTHETIC_DECISION_VALIDATED",
                "synthetic_verification_only": True,
                "signing_method_present": False,
                "operator_decision_recording_method_present": False,
                "packet_state_changed": False,
                "code_change_method_present": False,
                "application_method_present": False,
                "execution_method_present": False,
                "money_movement_executed": False,
                "production_activation_allowed": False,
            }
            return {**value, "report_digest": canonical_digest(value)}
