"""Synthetic-only validation of limited promotion activation intent."""

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
from .synthetic_patch_draft_limited_promotion_activation_operator_packets import (
    ACTIVATION_OPERATOR_ALLOWED_DECISIONS,
    ACTIVATION_OPERATOR_PACKET_SCOPE,
    ACTIVATION_OPERATOR_REQUIRED_ACKNOWLEDGEMENTS,
    SyntheticPatchDraftLimitedPromotionActivationOperatorPacketBook,
)


ACTIVATION_INTENT_VALIDATION_STATE = (
    "SYNTHETIC_PATCH_DRAFT_LIMITED_PROMOTION_ACTIVATION_INTENT_VALIDATED"
)


class SyntheticPatchDraftLimitedPromotionActivationDecision(StrEnum):
    AUTHORIZE_SYNTHETIC_LIMITED_PROMOTION_ACTIVATION = (
        "AUTHORIZE_SYNTHETIC_LIMITED_PROMOTION_ACTIVATION"
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
        "synthetic:limited-promotion-activation-intent-assessment:"
        + envelope_digest[:32]
    )


@dataclass(frozen=True)
class SyntheticPatchDraftLimitedPromotionActivationEnvelope:
    envelope_id: str
    packet_id: str
    packet_digest: str
    operator_id: str
    decision: SyntheticPatchDraftLimitedPromotionActivationDecision
    requested_scope: str
    acknowledgements: tuple[str, ...]
    issued_at: datetime
    expires_at: datetime
    nonce: str
    key_id: str
    signature: str

    def __post_init__(self) -> None:
        envelope_prefix = "synthetic:limited-promotion-activation-envelope:"
        packet_prefix = "synthetic:limited-promotion-activation-operator-packet:"
        nonce_prefix = "synthetic:limited-promotion-activation-nonce:"
        if (
            not self.envelope_id.startswith(envelope_prefix)
            or len(self.envelope_id) <= len(envelope_prefix)
            or not self.packet_id.startswith(packet_prefix)
            or not _valid_digest(self.packet_digest)
            or self.operator_id != SYNTHETIC_OPERATOR_ID
            or not isinstance(
                self.decision,
                SyntheticPatchDraftLimitedPromotionActivationDecision,
            )
            or self.decision.value not in ACTIVATION_OPERATOR_ALLOWED_DECISIONS
            or self.requested_scope != ACTIVATION_OPERATOR_PACKET_SCOPE
            or self.acknowledgements
            != ACTIVATION_OPERATOR_REQUIRED_ACKNOWLEDGEMENTS
            or self.issued_at.tzinfo is None
            or self.expires_at != self.issued_at + DECISION_ENVELOPE_VALIDITY
            or not self.nonce.startswith(nonce_prefix)
            or len(self.nonce) <= len(nonce_prefix)
            or not self.key_id.startswith("synthetic:key:operator-decision:")
            or not self.signature.startswith("sha256=")
            or not _valid_digest(self.signature.removeprefix("sha256="))
        ):
            raise GovernanceRejected(
                "complete synthetic limited promotion activation envelope required"
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
        return canonical_digest(
            {**self.signing_value(), "signature": self.signature}
        )


@dataclass(frozen=True)
class PatchDraftLimitedPromotionActivationIntentAssessment:
    sequence: int
    assessment_id: str
    envelope_id: str
    envelope_digest: str
    nonce: str
    packet_id: str
    packet_digest: str
    manifest_id: str
    operator_id: str
    decision: SyntheticPatchDraftLimitedPromotionActivationDecision
    assessed_at: datetime
    previous_digest: str
    assessment_digest: str
    validation_state: str = ACTIVATION_INTENT_VALIDATION_STATE
    packet_state_changed: bool = False
    operator_decision_recorded: bool = False
    activation_recorded: bool = False
    candidate_content_present: bool = False
    patch_content_present: bool = False
    diff_content_present: bool = False
    source_code_changed: bool = False
    filesystem_written: bool = False
    automatic_application_allowed: bool = False
    rollback_execution_allowed: bool = False
    safety_baseline_relaxation_allowed: bool = False
    execution_allowed: bool = False
    production_activation_allowed: bool = False

    def __post_init__(self) -> None:
        forbidden = (
            self.packet_state_changed,
            self.operator_decision_recorded,
            self.activation_recorded,
            self.candidate_content_present,
            self.patch_content_present,
            self.diff_content_present,
            self.source_code_changed,
            self.filesystem_written,
            self.automatic_application_allowed,
            self.rollback_execution_allowed,
            self.safety_baseline_relaxation_allowed,
            self.execution_allowed,
            self.production_activation_allowed,
        )
        if (
            self.sequence <= 0
            or self.assessment_id != _assessment_id(self.envelope_digest)
            or not self.envelope_id.startswith(
                "synthetic:limited-promotion-activation-envelope:"
            )
            or not _valid_digest(self.envelope_digest)
            or not self.nonce.startswith(
                "synthetic:limited-promotion-activation-nonce:"
            )
            or not self.packet_id.startswith(
                "synthetic:limited-promotion-activation-operator-packet:"
            )
            or not _valid_digest(self.packet_digest)
            or not self.manifest_id.startswith(
                "synthetic:limited-promotion-activation-manifest:"
            )
            or self.operator_id != SYNTHETIC_OPERATOR_ID
            or not isinstance(
                self.decision,
                SyntheticPatchDraftLimitedPromotionActivationDecision,
            )
            or self.assessed_at.tzinfo is None
            or not _valid_digest(self.previous_digest)
            or self.validation_state != ACTIVATION_INTENT_VALIDATION_STATE
            or any(forbidden)
            or self.assessment_digest != canonical_digest(self.digest_value())
        ):
            raise GovernanceRejected(
                "valid non-recording activation intent assessment required"
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
            "manifest_id": self.manifest_id,
            "operator_id": self.operator_id,
            "decision": self.decision.value,
            "assessed_at": self.assessed_at.isoformat(),
            "previous_digest": self.previous_digest,
            "validation_state": self.validation_state,
            "packet_state_changed": False,
            "operator_decision_recorded": False,
            "activation_recorded": False,
            "candidate_content_present": False,
            "patch_content_present": False,
            "diff_content_present": False,
            "source_code_changed": False,
            "filesystem_written": False,
            "automatic_application_allowed": False,
            "rollback_execution_allowed": False,
            "safety_baseline_relaxation_allowed": False,
            "execution_allowed": False,
            "production_activation_allowed": False,
        }


class SyntheticPatchDraftLimitedPromotionActivationIntake:
    """Validates signed synthetic intent without signing or recording it."""

    def __init__(self, registry: SyntheticOperatorKeyRegistry) -> None:
        if not isinstance(registry, SyntheticOperatorKeyRegistry):
            raise GovernanceRejected("typed synthetic operator key registry required")
        self._registry = registry
        self._assessments: list[
            PatchDraftLimitedPromotionActivationIntentAssessment
        ] = []
        self._by_envelope: dict[
            str, PatchDraftLimitedPromotionActivationIntentAssessment
        ] = {}
        self._nonces: dict[str, str] = {}
        self._lock = RLock()

    @property
    def assessments(
        self,
    ) -> tuple[PatchDraftLimitedPromotionActivationIntentAssessment, ...]:
        with self._lock:
            return tuple(self._assessments)

    def assess(
        self,
        packet_book: SyntheticPatchDraftLimitedPromotionActivationOperatorPacketBook,
        manifest_id: str,
        envelope: SyntheticPatchDraftLimitedPromotionActivationEnvelope,
        *,
        received_at: datetime,
    ) -> PatchDraftLimitedPromotionActivationIntentAssessment:
        if received_at.tzinfo is None:
            raise GovernanceRejected("timezone-aware activation intent receipt required")
        if not isinstance(
            packet_book,
            SyntheticPatchDraftLimitedPromotionActivationOperatorPacketBook,
        ):
            raise GovernanceRejected("typed activation operator packet book required")
        if not isinstance(
            envelope,
            SyntheticPatchDraftLimitedPromotionActivationEnvelope,
        ):
            raise GovernanceRejected("typed synthetic activation envelope required")
        if received_at < envelope.issued_at - MAX_FUTURE_SKEW:
            raise GovernanceRejected("activation envelope is from the future")
        if received_at > envelope.expires_at:
            raise GovernanceRejected("activation envelope has expired")

        before = packet_book.evidence()["report_digest"]
        packet = packet_book.current_packet(manifest_id, now=received_at)
        if (
            envelope.packet_id != packet.packet_id
            or envelope.packet_digest != packet.packet_digest
            or envelope.requested_scope != packet.requested_scope
            or envelope.decision.value not in packet.allowed_decisions
            or envelope.acknowledgements != packet.required_acknowledgements
        ):
            raise GovernanceRejected(
                "activation envelope is not bound to current packet"
            )
        key = self._registry.resolve(
            envelope.key_id, issued_at=envelope.issued_at
        )
        if key.operator_id != envelope.operator_id:
            raise GovernanceRejected("activation key identity mismatch")
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
            raise GovernanceRejected("activation signature mismatch")

        envelope_digest = envelope.envelope_digest()
        with self._lock:
            created = False
            if not self.verify_assessment_chain():
                raise GovernanceRejected("existing activation intent evidence is invalid")
            existing = self._by_envelope.get(envelope.envelope_id)
            if existing is not None:
                if existing.envelope_digest != envelope_digest:
                    raise GovernanceRejected(
                        "activation envelope idempotency mismatch"
                    )
                assessment = existing
            else:
                if envelope.nonce in self._nonces:
                    raise GovernanceRejected("activation nonce replay")
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
                    "manifest_id": packet.manifest_id,
                    "operator_id": envelope.operator_id,
                    "decision": envelope.decision.value,
                    "assessed_at": received_at.isoformat(),
                    "previous_digest": previous,
                    "validation_state": ACTIVATION_INTENT_VALIDATION_STATE,
                    "packet_state_changed": False,
                    "operator_decision_recorded": False,
                    "activation_recorded": False,
                    "candidate_content_present": False,
                    "patch_content_present": False,
                    "diff_content_present": False,
                    "source_code_changed": False,
                    "filesystem_written": False,
                    "automatic_application_allowed": False,
                    "rollback_execution_allowed": False,
                    "safety_baseline_relaxation_allowed": False,
                    "execution_allowed": False,
                    "production_activation_allowed": False,
                }
                assessment = PatchDraftLimitedPromotionActivationIntentAssessment(
                    sequence,
                    assessment_id,
                    envelope.envelope_id,
                    envelope_digest,
                    envelope.nonce,
                    packet.packet_id,
                    packet.packet_digest,
                    packet.manifest_id,
                    envelope.operator_id,
                    envelope.decision,
                    received_at,
                    previous,
                    canonical_digest(values),
                )
                self._assessments.append(assessment)
                self._by_envelope[envelope.envelope_id] = assessment
                self._nonces[envelope.nonce] = envelope.envelope_id
                created = True
            if before != packet_book.evidence()["report_digest"]:
                if created:
                    self._assessments.pop()
                    self._by_envelope.pop(envelope.envelope_id, None)
                    self._nonces.pop(envelope.nonce, None)
                raise GovernanceRejected(
                    "activation packet changed during intent validation"
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
                    != ACTIVATION_INTENT_VALIDATION_STATE
                    or any(
                        (
                            assessment.packet_state_changed,
                            assessment.operator_decision_recorded,
                            assessment.activation_recorded,
                            assessment.candidate_content_present,
                            assessment.patch_content_present,
                            assessment.diff_content_present,
                            assessment.source_code_changed,
                            assessment.filesystem_written,
                            assessment.automatic_application_allowed,
                            assessment.rollback_execution_allowed,
                            assessment.safety_baseline_relaxation_allowed,
                            assessment.execution_allowed,
                            assessment.production_activation_allowed,
                        )
                    )
                ):
                    return False
                previous = assessment.assessment_digest
            return (
                len(self._assessments)
                == len(self._by_envelope)
                == len(self._nonces)
                and all(
                    self._by_envelope.get(item.envelope_id) is item
                    and self._nonces.get(item.nonce) == item.envelope_id
                    for item in self._assessments
                )
            )

    def evidence(self) -> dict[str, object]:
        with self._lock:
            value = {
                "schema": (
                    "nurion.pg.synthetic-limited-promotion-activation-"
                    "intent-validation-evidence.v1"
                ),
                "mode": "UNREGISTERED_SYNTHETIC_ONLY",
                "assessment_count": len(self._assessments),
                "assessment_digests": [
                    item.assessment_digest for item in self._assessments
                ],
                "assessment_chain_valid": self.verify_assessment_chain(),
                "maximum_state": ACTIVATION_INTENT_VALIDATION_STATE,
                "synthetic_verification_only": True,
                "signing_method_present": False,
                "operator_decision_recording_method_present": False,
                "activation_recording_method_present": False,
                "packet_state_changed": False,
                "candidate_content_present": False,
                "patch_content_present": False,
                "diff_content_present": False,
                "source_code_change_method_present": False,
                "filesystem_write_method_present": False,
                "application_method_present": False,
                "activation_method_present": False,
                "rollback_execution_method_present": False,
                "safety_baseline_relaxation_method_present": False,
                "execution_method_present": False,
                "network_access_method_present": False,
                "external_blocker_close_method_present": False,
                "automatic_merge_method_present": False,
                "automatic_deploy_method_present": False,
                "personal_data_used": False,
                "credentials_used": False,
                "money_movement_executed": False,
                "production_activation_allowed": False,
            }
            return {**value, "report_digest": canonical_digest(value)}
