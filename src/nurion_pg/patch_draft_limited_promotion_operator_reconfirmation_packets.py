"""Non-authorizing operator reconfirmation packets for limited promotion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest
from .operator_decision_packets import OperatorGovernanceSnapshot
from .synthetic_patch_draft_limited_promotion_shadow import (
    LimitedPromotionShadowDecision,
    LimitedPromotionShadowItemDecision,
)
from .synthetic_patch_draft_limited_promotion_shadow_review_docket import (
    LimitedPromotionShadowReviewDecision,
    LimitedPromotionShadowReviewState,
    SyntheticPatchDraftLimitedPromotionShadowReviewDocket,
)


LIMITED_PROMOTION_RECONFIRMATION_PACKET_VALIDITY = timedelta(hours=24)
LIMITED_PROMOTION_RECONFIRMATION_PACKET_SCOPE = (
    "SYNTHETIC_PATCH_DRAFT_LIMITED_PROMOTION_RECONFIRMATION_ONLY"
)
LIMITED_PROMOTION_RECONFIRMATION_ALLOWED_DECISIONS = (
    "RECONFIRM_SYNTHETIC_PATCH_DRAFT_LIMITED_PROMOTION",
    "HOLD",
    "REJECT",
)
LIMITED_PROMOTION_RECONFIRMATION_REQUIRED_ACKNOWLEDGEMENTS = (
    "SYNTHETIC_ONLY",
    "EXACT_REVIEWED_COHORT_ONLY",
    "EXACT_REVIEWED_OBSERVATION_WINDOW_ONLY",
    "ROLLBACK_CONDITIONS_REMAIN_MANDATORY",
    "METADATA_ONLY_PACKET",
    "NO_CANDIDATE_PATCH_OR_DIFF_CONTENT",
    "NO_SOURCE_OR_FILESYSTEM_CHANGE",
    "NO_AUTOMATIC_APPLICATION_OR_ACTIVATION",
    "NO_SAFETY_BASELINE_RELAXATION",
    "NO_PAYMENT_EXECUTION_OR_MONEY_MOVEMENT",
    "NO_REAL_DATA_OR_CREDENTIALS",
    "NO_MAIN_MERGE_OR_DEPLOYMENT",
    "EXPLICIT_OPERATOR_RECONFIRMATION_REQUIRED",
    "NO_PRODUCTION_PROMOTION",
)


def _valid_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _packet_id(
    shadow_id: str,
    shadow_assessment_digest: str,
    shadow_review_digest: str,
    governance_digest: str,
    generated_at: datetime,
) -> str:
    identity = canonical_digest(
        {
            "shadow_id": shadow_id,
            "shadow_assessment_digest": shadow_assessment_digest,
            "shadow_review_digest": shadow_review_digest,
            "governance_digest": governance_digest,
            "generated_at": generated_at.isoformat(),
        }
    )
    return "synthetic:patch-draft-limited-promotion-reconfirmation:" + identity[:32]


@dataclass(frozen=True)
class PatchDraftLimitedPromotionOperatorReconfirmationPacket:
    sequence: int
    packet_id: str
    shadow_id: str
    plan_id: str
    plan_digest: str
    source_plan_review_digest: str
    candidate_digest: str
    cohort_digest: str
    shadow_assessment_digest: str
    shadow_review_digest: str
    governance_digest: str
    blocker_ids: tuple[str, ...]
    synthetic_sample_size: int
    observation_window_seconds: int
    observation_result_digests: tuple[str, ...]
    requested_scope: str
    allowed_decisions: tuple[str, ...]
    required_acknowledgements: tuple[str, ...]
    generated_at: datetime
    valid_until: datetime
    previous_digest: str
    packet_digest: str
    release_status: str = "BLOCKED"
    operator_reconfirmation_recorded: bool = False
    candidate_content_present: bool = False
    patch_content_present: bool = False
    diff_content_present: bool = False
    source_code_changed: bool = False
    filesystem_written: bool = False
    automatic_application_allowed: bool = False
    safety_baseline_relaxation_allowed: bool = False
    execution_allowed: bool = False
    synthetic_activation_allowed: bool = False
    production_activation_allowed: bool = False

    def __post_init__(self) -> None:
        forbidden = (
            self.operator_reconfirmation_recorded,
            self.candidate_content_present,
            self.patch_content_present,
            self.diff_content_present,
            self.source_code_changed,
            self.filesystem_written,
            self.automatic_application_allowed,
            self.safety_baseline_relaxation_allowed,
            self.execution_allowed,
            self.synthetic_activation_allowed,
            self.production_activation_allowed,
        )
        if (
            self.sequence <= 0
            or self.packet_id
            != _packet_id(
                self.shadow_id,
                self.shadow_assessment_digest,
                self.shadow_review_digest,
                self.governance_digest,
                self.generated_at,
            )
            or not self.shadow_id.startswith(
                "synthetic:patch-draft-limited-promotion-shadow:"
            )
            or not self.plan_id.startswith(
                "synthetic:patch-draft-limited-promotion-plan:"
            )
            or not all(
                _valid_digest(value)
                for value in (
                    self.plan_digest,
                    self.source_plan_review_digest,
                    self.candidate_digest,
                    self.cohort_digest,
                    self.shadow_assessment_digest,
                    self.shadow_review_digest,
                    self.governance_digest,
                    self.previous_digest,
                )
            )
            or not self.blocker_ids
            or len(set(self.blocker_ids)) != len(self.blocker_ids)
            or any(not item.startswith("EXT-PG-") for item in self.blocker_ids)
            or self.synthetic_sample_size <= 0
            or self.observation_window_seconds <= 0
            or not self.observation_result_digests
            or not all(
                _valid_digest(value) for value in self.observation_result_digests
            )
            or self.requested_scope
            != LIMITED_PROMOTION_RECONFIRMATION_PACKET_SCOPE
            or self.allowed_decisions
            != LIMITED_PROMOTION_RECONFIRMATION_ALLOWED_DECISIONS
            or self.required_acknowledgements
            != LIMITED_PROMOTION_RECONFIRMATION_REQUIRED_ACKNOWLEDGEMENTS
            or self.generated_at.tzinfo is None
            or self.valid_until
            != self.generated_at
            + LIMITED_PROMOTION_RECONFIRMATION_PACKET_VALIDITY
            or self.release_status != "BLOCKED"
            or any(forbidden)
            or self.packet_digest != canonical_digest(self.digest_value())
        ):
            raise GovernanceRejected(
                "valid non-authorizing limited promotion reconfirmation packet required"
            )

    def digest_value(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "packet_id": self.packet_id,
            "shadow_id": self.shadow_id,
            "plan_id": self.plan_id,
            "plan_digest": self.plan_digest,
            "source_plan_review_digest": self.source_plan_review_digest,
            "candidate_digest": self.candidate_digest,
            "cohort_digest": self.cohort_digest,
            "shadow_assessment_digest": self.shadow_assessment_digest,
            "shadow_review_digest": self.shadow_review_digest,
            "governance_digest": self.governance_digest,
            "blocker_ids": list(self.blocker_ids),
            "synthetic_sample_size": self.synthetic_sample_size,
            "observation_window_seconds": self.observation_window_seconds,
            "observation_result_digests": list(
                self.observation_result_digests
            ),
            "requested_scope": self.requested_scope,
            "allowed_decisions": list(self.allowed_decisions),
            "required_acknowledgements": list(
                self.required_acknowledgements
            ),
            "generated_at": self.generated_at.isoformat(),
            "valid_until": self.valid_until.isoformat(),
            "previous_digest": self.previous_digest,
            "release_status": self.release_status,
            "operator_reconfirmation_recorded": False,
            "candidate_content_present": False,
            "patch_content_present": False,
            "diff_content_present": False,
            "source_code_changed": False,
            "filesystem_written": False,
            "automatic_application_allowed": False,
            "safety_baseline_relaxation_allowed": False,
            "execution_allowed": False,
            "synthetic_activation_allowed": False,
            "production_activation_allowed": False,
        }


class SyntheticPatchDraftLimitedPromotionOperatorReconfirmationPacketBook:
    """Builds immutable operator review material without recording a decision."""

    def __init__(self) -> None:
        self._packets: list[
            PatchDraftLimitedPromotionOperatorReconfirmationPacket
        ] = []
        self._by_shadow: dict[
            str, PatchDraftLimitedPromotionOperatorReconfirmationPacket
        ] = {}
        self._lock = RLock()

    @property
    def packets(
        self,
    ) -> tuple[PatchDraftLimitedPromotionOperatorReconfirmationPacket, ...]:
        with self._lock:
            return tuple(self._packets)

    def prepare(
        self,
        docket: SyntheticPatchDraftLimitedPromotionShadowReviewDocket,
        shadow_id: str,
        governance: OperatorGovernanceSnapshot,
        *,
        generated_at: datetime,
    ) -> PatchDraftLimitedPromotionOperatorReconfirmationPacket:
        if generated_at.tzinfo is None:
            raise GovernanceRejected(
                "timezone-aware operator reconfirmation packet time required"
            )
        if not isinstance(
            docket,
            SyntheticPatchDraftLimitedPromotionShadowReviewDocket,
        ):
            raise GovernanceRejected(
                "typed limited promotion shadow review docket required"
            )
        if not isinstance(governance, OperatorGovernanceSnapshot):
            raise GovernanceRejected(
                "verified operator governance snapshot required"
            )
        if governance.governance_digest != canonical_digest(
            governance.digest_value()
        ):
            raise GovernanceRejected("operator governance snapshot digest mismatch")

        before = docket.evidence()["report_digest"]
        source = docket.ready_source(shadow_id)
        assessment = source.assessment
        if (
            source.state
            is not LimitedPromotionShadowReviewState.READY_FOR_PATCH_DRAFT_LIMITED_PROMOTION_OPERATOR_RECONFIRMATION
            or source.review_decision
            is not LimitedPromotionShadowReviewDecision.PASS
            or source.review_digest is None
            or source.reviewed_at is None
            or generated_at < source.reviewed_at
            or assessment.decision
            is not LimitedPromotionShadowDecision.PROPOSED_FOR_ETERNIAN_REVIEW
            or not assessment.item_results
            or any(
                item.decision is not LimitedPromotionShadowItemDecision.PASS
                or item.triggered_rollback_conditions
                for item in assessment.item_results
            )
            or assessment.assessment_digest
            != canonical_digest(assessment.digest_value())
        ):
            raise GovernanceRejected(
                "bound passing limited promotion shadow review required"
            )

        packet_id = _packet_id(
            assessment.shadow_id,
            assessment.assessment_digest,
            source.review_digest,
            governance.governance_digest,
            generated_at,
        )
        result_digests = tuple(
            item.result_digest for item in assessment.item_results
        )
        with self._lock:
            created = False
            if not self.verify_packet_chain():
                raise GovernanceRejected(
                    "existing operator reconfirmation packet chain is invalid"
                )
            existing = self._by_shadow.get(shadow_id)
            if existing is not None:
                if (
                    existing.shadow_assessment_digest
                    != assessment.assessment_digest
                    or existing.shadow_review_digest != source.review_digest
                    or existing.governance_digest != governance.governance_digest
                ):
                    raise GovernanceRejected(
                        "operator reconfirmation packet source collision"
                    )
                packet = existing
            else:
                sequence = len(self._packets) + 1
                previous = (
                    self._packets[-1].packet_digest
                    if self._packets
                    else "0" * 64
                )
                values = {
                    "sequence": sequence,
                    "packet_id": packet_id,
                    "shadow_id": assessment.shadow_id,
                    "plan_id": assessment.plan_id,
                    "plan_digest": assessment.plan_digest,
                    "source_plan_review_digest": assessment.source_review_digest,
                    "candidate_digest": assessment.candidate_digest,
                    "cohort_digest": assessment.cohort_digest,
                    "shadow_assessment_digest": assessment.assessment_digest,
                    "shadow_review_digest": source.review_digest,
                    "governance_digest": governance.governance_digest,
                    "blocker_ids": list(governance.blocker_ids),
                    "synthetic_sample_size": assessment.synthetic_sample_size,
                    "observation_window_seconds": (
                        assessment.observation_window_seconds
                    ),
                    "observation_result_digests": list(result_digests),
                    "requested_scope": (
                        LIMITED_PROMOTION_RECONFIRMATION_PACKET_SCOPE
                    ),
                    "allowed_decisions": list(
                        LIMITED_PROMOTION_RECONFIRMATION_ALLOWED_DECISIONS
                    ),
                    "required_acknowledgements": list(
                        LIMITED_PROMOTION_RECONFIRMATION_REQUIRED_ACKNOWLEDGEMENTS
                    ),
                    "generated_at": generated_at.isoformat(),
                    "valid_until": (
                        generated_at
                        + LIMITED_PROMOTION_RECONFIRMATION_PACKET_VALIDITY
                    ).isoformat(),
                    "previous_digest": previous,
                    "release_status": "BLOCKED",
                    "operator_reconfirmation_recorded": False,
                    "candidate_content_present": False,
                    "patch_content_present": False,
                    "diff_content_present": False,
                    "source_code_changed": False,
                    "filesystem_written": False,
                    "automatic_application_allowed": False,
                    "safety_baseline_relaxation_allowed": False,
                    "execution_allowed": False,
                    "synthetic_activation_allowed": False,
                    "production_activation_allowed": False,
                }
                packet = PatchDraftLimitedPromotionOperatorReconfirmationPacket(
                    sequence,
                    packet_id,
                    assessment.shadow_id,
                    assessment.plan_id,
                    assessment.plan_digest,
                    assessment.source_review_digest,
                    assessment.candidate_digest,
                    assessment.cohort_digest,
                    assessment.assessment_digest,
                    source.review_digest,
                    governance.governance_digest,
                    governance.blocker_ids,
                    assessment.synthetic_sample_size,
                    assessment.observation_window_seconds,
                    result_digests,
                    LIMITED_PROMOTION_RECONFIRMATION_PACKET_SCOPE,
                    LIMITED_PROMOTION_RECONFIRMATION_ALLOWED_DECISIONS,
                    LIMITED_PROMOTION_RECONFIRMATION_REQUIRED_ACKNOWLEDGEMENTS,
                    generated_at,
                    generated_at
                    + LIMITED_PROMOTION_RECONFIRMATION_PACKET_VALIDITY,
                    previous,
                    canonical_digest(values),
                )
                self._packets.append(packet)
                self._by_shadow[shadow_id] = packet
                created = True
            if before != docket.evidence()["report_digest"]:
                if created:
                    self._packets.pop()
                    self._by_shadow.pop(shadow_id, None)
                raise GovernanceRejected(
                    "limited promotion shadow review changed during packet preparation"
                )
        return packet

    def current_packet(
        self, shadow_id: str, *, now: datetime
    ) -> PatchDraftLimitedPromotionOperatorReconfirmationPacket:
        if now.tzinfo is None:
            raise GovernanceRejected(
                "timezone-aware operator reconfirmation packet lookup required"
            )
        with self._lock:
            packet = self._by_shadow.get(shadow_id)
            if packet is None:
                raise GovernanceRejected(
                    "unknown limited promotion operator reconfirmation packet"
                )
            if now > packet.valid_until:
                raise GovernanceRejected(
                    "limited promotion operator reconfirmation packet is stale"
                )
            if not self.verify_packet_chain():
                raise GovernanceRejected(
                    "limited promotion operator reconfirmation packet integrity failure"
                )
            return packet

    def verify_packet_chain(self) -> bool:
        with self._lock:
            previous = "0" * 64
            for sequence, packet in enumerate(self._packets, start=1):
                if (
                    packet.sequence != sequence
                    or packet.previous_digest != previous
                    or packet.packet_id
                    != _packet_id(
                        packet.shadow_id,
                        packet.shadow_assessment_digest,
                        packet.shadow_review_digest,
                        packet.governance_digest,
                        packet.generated_at,
                    )
                    or packet.packet_digest
                    != canonical_digest(packet.digest_value())
                    or any(
                        (
                            packet.operator_reconfirmation_recorded,
                            packet.candidate_content_present,
                            packet.patch_content_present,
                            packet.diff_content_present,
                            packet.source_code_changed,
                            packet.filesystem_written,
                            packet.automatic_application_allowed,
                            packet.safety_baseline_relaxation_allowed,
                            packet.execution_allowed,
                            packet.synthetic_activation_allowed,
                            packet.production_activation_allowed,
                        )
                    )
                ):
                    return False
                previous = packet.packet_digest
            return len(self._packets) == len(self._by_shadow) and all(
                self._by_shadow.get(packet.shadow_id) is packet
                for packet in self._packets
            )

    def evidence(self) -> dict[str, object]:
        with self._lock:
            value = {
                "schema": (
                    "nurion.pg.patch-draft-limited-promotion-operator-"
                    "reconfirmation-packet-evidence.v1"
                ),
                "mode": "UNREGISTERED_SYNTHETIC_ONLY",
                "packet_count": len(self._packets),
                "packet_digests": [
                    packet.packet_digest for packet in self._packets
                ],
                "packet_chain_valid": self.verify_packet_chain(),
                "maximum_state": (
                    "AWAITING_PATCH_DRAFT_LIMITED_PROMOTION_OPERATOR_RECONFIRMATION"
                ),
                "requested_scope": (
                    LIMITED_PROMOTION_RECONFIRMATION_PACKET_SCOPE
                ),
                "operator_reconfirmation_method_present": False,
                "operator_reconfirmation_recorded": False,
                "candidate_content_present": False,
                "patch_content_present": False,
                "diff_content_present": False,
                "source_code_change_method_present": False,
                "filesystem_write_method_present": False,
                "application_method_present": False,
                "safety_baseline_relaxation_method_present": False,
                "execution_method_present": False,
                "synthetic_activation_allowed": False,
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
