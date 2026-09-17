"""Synthetic-only verification of patch draft promotion operator intent."""

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
from .patch_draft_promotion_operator_packets import (
    PATCH_DRAFT_PROMOTION_ALLOWED_DECISIONS,
    PATCH_DRAFT_PROMOTION_PACKET_SCOPE,
    PATCH_DRAFT_PROMOTION_REQUIRED_ACKNOWLEDGEMENTS,
    SyntheticPatchDraftPromotionOperatorPacketBook,
)


PATCH_DRAFT_PROMOTION_VALIDATION_STATE = (
    "SYNTHETIC_PATCH_DRAFT_PROMOTION_DECISION_VALIDATED"
)


class SyntheticPatchDraftPromotionDecision(StrEnum):
    AUTHORIZE_SYNTHETIC_PATCH_DRAFT_LIMITED_PROMOTION = (
        "AUTHORIZE_SYNTHETIC_PATCH_DRAFT_LIMITED_PROMOTION"
    )
    HOLD = "HOLD"
    REJECT = "REJECT"


def _valid_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _assessment_id(envelope_digest: str) -> str:
    return (
        "synthetic:patch-draft-promotion-decision-assessment:"
        + envelope_digest[:32]
    )


@dataclass(frozen=True)
class SyntheticPatchDraftPromotionDecisionEnvelope:
    envelope_id: str
    packet_id: str
    packet_digest: str
    operator_id: str
    decision: SyntheticPatchDraftPromotionDecision
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
                "synthetic:patch-draft-promotion-decision-envelope:"
            )
            or len(self.envelope_id)
            <= len("synthetic:patch-draft-promotion-decision-envelope:")
            or not self.packet_id.startswith(
                "synthetic:patch-draft-promotion-operator-packet:"
            )
            or not _valid_digest(self.packet_digest)
            or self.operator_id != SYNTHETIC_OPERATOR_ID
            or not isinstance(self.decision, SyntheticPatchDraftPromotionDecision)
            or self.decision.value not in PATCH_DRAFT_PROMOTION_ALLOWED_DECISIONS
            or self.requested_scope != PATCH_DRAFT_PROMOTION_PACKET_SCOPE
            or self.acknowledgements
            != PATCH_DRAFT_PROMOTION_REQUIRED_ACKNOWLEDGEMENTS
            or self.issued_at.tzinfo is None
            or self.expires_at != self.issued_at + DECISION_ENVELOPE_VALIDITY
            or not self.nonce.startswith(
                "synthetic:patch-draft-promotion-operator-nonce:"
            )
            or len(self.nonce)
            <= len("synthetic:patch-draft-promotion-operator-nonce:")
            or not self.key_id.startswith("synthetic:key:operator-decision:")
            or not self.signature.startswith("sha256=")
            or not _valid_digest(self.signature.removeprefix("sha256="))
        ):
            raise GovernanceRejected(
                "complete synthetic patch draft promotion envelope required"
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
class PatchDraftPromotionDecisionIntentAssessment:
    sequence: int
    assessment_id: str
    envelope_id: str
    envelope_digest: str
    nonce: str
    packet_id: str
    packet_digest: str
    operator_id: str
    decision: SyntheticPatchDraftPromotionDecision
    assessed_at: datetime
    previous_digest: str
    assessment_digest: str
    validation_state: str = PATCH_DRAFT_PROMOTION_VALIDATION_STATE
    packet_state_changed: bool = False
    operator_decision_recorded: bool = False
    patch_content_present: bool = False
    diff_content_present: bool = False
    source_code_changed: bool = False
    filesystem_written: bool = False
    automatic_application_allowed: bool = False
    safety_baseline_relaxation_allowed: bool = False
    execution_allowed: bool = False
    production_activation_allowed: bool = False

    def __post_init__(self) -> None:
        if (
            self.sequence <= 0
            or self.assessment_id != _assessment_id(self.envelope_digest)
            or not self.envelope_id.startswith(
                "synthetic:patch-draft-promotion-decision-envelope:"
            )
            or not _valid_digest(self.envelope_digest)
            or not self.nonce.startswith(
                "synthetic:patch-draft-promotion-operator-nonce:"
            )
            or not self.packet_id.startswith(
                "synthetic:patch-draft-promotion-operator-packet:"
            )
            or not _valid_digest(self.packet_digest)
            or self.operator_id != SYNTHETIC_OPERATOR_ID
            or not isinstance(self.decision, SyntheticPatchDraftPromotionDecision)
            or self.assessed_at.tzinfo is None
            or not _valid_digest(self.previous_digest)
            or self.validation_state != PATCH_DRAFT_PROMOTION_VALIDATION_STATE
            or any((
                self.packet_state_changed,
                self.operator_decision_recorded,
                self.patch_content_present,
                self.diff_content_present,
                self.source_code_changed,
                self.filesystem_written,
                self.automatic_application_allowed,
                self.safety_baseline_relaxation_allowed,
                self.execution_allowed,
                self.production_activation_allowed,
            ))
            or self.assessment_digest != canonical_digest(self.digest_value())
        ):
            raise GovernanceRejected(
                "valid non-recording patch draft promotion assessment required"
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
            "packet_state_changed": False,
            "operator_decision_recorded": False,
            "patch_content_present": False,
            "diff_content_present": False,
            "source_code_changed": False,
            "filesystem_written": False,
            "automatic_application_allowed": False,
            "safety_baseline_relaxation_allowed": False,
            "execution_allowed": False,
            "production_activation_allowed": False,
        }


class SyntheticPatchDraftPromotionDecisionIntake:
    """Validates signed synthetic intent without signing or recording a decision."""

    def __init__(self, registry: SyntheticOperatorKeyRegistry) -> None:
        if not isinstance(registry, SyntheticOperatorKeyRegistry):
            raise GovernanceRejected("typed synthetic operator key registry required")
        self._registry = registry
        self._assessments: list[PatchDraftPromotionDecisionIntentAssessment] = []
        self._by_envelope: dict[str, PatchDraftPromotionDecisionIntentAssessment] = {}
        self._nonces: dict[str, str] = {}
        self._lock = RLock()

    @property
    def assessments(self) -> tuple[PatchDraftPromotionDecisionIntentAssessment, ...]:
        with self._lock:
            return tuple(self._assessments)

    def assess(
        self,
        packet_book: SyntheticPatchDraftPromotionOperatorPacketBook,
        shadow_id: str,
        envelope: SyntheticPatchDraftPromotionDecisionEnvelope,
        *,
        received_at: datetime,
    ) -> PatchDraftPromotionDecisionIntentAssessment:
        if received_at.tzinfo is None:
            raise GovernanceRejected("timezone-aware promotion intent receipt required")
        if not isinstance(
            packet_book, SyntheticPatchDraftPromotionOperatorPacketBook
        ):
            raise GovernanceRejected("typed patch draft promotion packet book required")
        if not isinstance(envelope, SyntheticPatchDraftPromotionDecisionEnvelope):
            raise GovernanceRejected("typed synthetic promotion envelope required")
        if received_at < envelope.issued_at - MAX_FUTURE_SKEW:
            raise GovernanceRejected("promotion intent envelope is from the future")
        if received_at > envelope.expires_at:
            raise GovernanceRejected("promotion intent envelope has expired")
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
                "promotion intent envelope is not bound to current packet"
            )
        key = self._registry.resolve(envelope.key_id, issued_at=envelope.issued_at)
        if key.operator_id != envelope.operator_id:
            raise GovernanceRejected("promotion intent key identity mismatch")
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
            raise GovernanceRejected("promotion intent signature mismatch")
        envelope_digest = envelope.envelope_digest()
        with self._lock:
            created = False
            if not self.verify_assessment_chain():
                raise GovernanceRejected("existing promotion intent evidence is invalid")
            existing = self._by_envelope.get(envelope.envelope_id)
            if existing is not None:
                if existing.envelope_digest != envelope_digest:
                    raise GovernanceRejected("promotion envelope idempotency mismatch")
                assessment = existing
            else:
                if envelope.nonce in self._nonces:
                    raise GovernanceRejected("promotion decision nonce replay")
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
                    "validation_state": PATCH_DRAFT_PROMOTION_VALIDATION_STATE,
                    "packet_state_changed": False,
                    "operator_decision_recorded": False,
                    "patch_content_present": False,
                    "diff_content_present": False,
                    "source_code_changed": False,
                    "filesystem_written": False,
                    "automatic_application_allowed": False,
                    "safety_baseline_relaxation_allowed": False,
                    "execution_allowed": False,
                    "production_activation_allowed": False,
                }
                assessment = PatchDraftPromotionDecisionIntentAssessment(
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
            if before != packet_book.evidence()["report_digest"]:
                if created:
                    self._assessments.pop()
                    self._by_envelope.pop(envelope.envelope_id, None)
                    self._nonces.pop(envelope.nonce, None)
                raise GovernanceRejected("promotion packet changed during validation")
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
                    != PATCH_DRAFT_PROMOTION_VALIDATION_STATE
                    or any((
                        assessment.packet_state_changed,
                        assessment.operator_decision_recorded,
                        assessment.patch_content_present,
                        assessment.diff_content_present,
                        assessment.source_code_changed,
                        assessment.filesystem_written,
                        assessment.automatic_application_allowed,
                        assessment.safety_baseline_relaxation_allowed,
                        assessment.execution_allowed,
                        assessment.production_activation_allowed,
                    ))
                    or self._by_envelope.get(assessment.envelope_id) is not assessment
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
                decision.value: 0
                for decision in SyntheticPatchDraftPromotionDecision
            }
            for assessment in self._assessments:
                counts[assessment.decision.value] += 1
            value = {
                "schema": (
                    "nurion.pg.synthetic-patch-draft-promotion-decision-"
                    "intake-evidence.v1"
                ),
                "decision_counts": counts,
                "assessment_chain_valid": self.verify_assessment_chain(),
                "maximum_state": PATCH_DRAFT_PROMOTION_VALIDATION_STATE,
                "synthetic_verification_only": True,
                "signing_method_present": False,
                "operator_decision_recording_method_present": False,
                "packet_state_changed": False,
                "patch_content_present": False,
                "diff_content_present": False,
                "source_code_change_method_present": False,
                "filesystem_write_method_present": False,
                "application_method_present": False,
                "safety_baseline_relaxation_method_present": False,
                "execution_method_present": False,
                "network_access_method_present": False,
                "personal_data_used": False,
                "credentials_used": False,
                "money_movement_executed": False,
                "production_activation_allowed": False,
            }
            return {**value, "report_digest": canonical_digest(value)}
