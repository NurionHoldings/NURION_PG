"""Non-authorizing operator packets for reviewed synthetic activation manifests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest
from .operator_decision_packets import OperatorGovernanceSnapshot
from .synthetic_patch_draft_limited_promotion_activation_review_docket import (
    ActivationManifestReviewDecision,
    ActivationManifestReviewState,
    SyntheticPatchDraftLimitedPromotionActivationReviewDocket,
)


ACTIVATION_OPERATOR_PACKET_VALIDITY = timedelta(hours=24)
ACTIVATION_OPERATOR_PACKET_SCOPE = (
    "SYNTHETIC_PATCH_DRAFT_LIMITED_PROMOTION_ACTIVATION_ONLY"
)
ACTIVATION_OPERATOR_ALLOWED_DECISIONS = (
    "AUTHORIZE_SYNTHETIC_LIMITED_PROMOTION_ACTIVATION",
    "HOLD",
    "REJECT",
)
ACTIVATION_OPERATOR_REQUIRED_ACKNOWLEDGEMENTS = (
    "SYNTHETIC_ONLY",
    "EXACT_FINAL_REVIEWED_MANIFEST_ONLY",
    "EXACT_CANDIDATE_AND_COHORT_DIGESTS_ONLY",
    "EXACT_SAMPLE_SIZE_AND_OBSERVATION_WINDOW_ONLY",
    "EXACT_OBSERVATION_RESULTS_ONLY",
    "ROLLBACK_TRIGGERS_REMAIN_MANDATORY",
    "METADATA_ONLY_PACKET",
    "NO_OPERATOR_DECISION_RECORDED",
    "NO_CANDIDATE_PATCH_OR_DIFF_CONTENT",
    "NO_SOURCE_OR_FILESYSTEM_CHANGE",
    "NO_AUTOMATIC_APPLICATION_OR_ACTIVATION",
    "NO_SAFETY_BASELINE_RELAXATION",
    "NO_PAYMENT_EXECUTION_OR_MONEY_MOVEMENT",
    "NO_REAL_DATA_OR_CREDENTIALS",
    "NO_MAIN_MERGE_OR_DEPLOYMENT",
    "EXPLICIT_OPERATOR_DECISION_REQUIRED",
    "NO_PRODUCTION_PROMOTION",
)


def _valid_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _packet_id(
    manifest_id: str,
    manifest_digest: str,
    final_review_digest: str,
    governance_digest: str,
    generated_at: datetime,
) -> str:
    identity = canonical_digest(
        {
            "manifest_id": manifest_id,
            "manifest_digest": manifest_digest,
            "final_review_digest": final_review_digest,
            "governance_digest": governance_digest,
            "generated_at": generated_at.isoformat(),
        }
    )
    return "synthetic:limited-promotion-activation-operator-packet:" + identity[:32]


@dataclass(frozen=True)
class SyntheticPatchDraftLimitedPromotionActivationOperatorPacket:
    sequence: int
    packet_id: str
    manifest_id: str
    manifest_digest: str
    final_review_digest: str
    source_receipt_id: str
    source_receipt_digest: str
    source_packet_id: str
    source_packet_digest: str
    shadow_id: str
    plan_id: str
    plan_digest: str
    candidate_digest: str
    cohort_digest: str
    shadow_assessment_digest: str
    shadow_review_digest: str
    governance_digest: str
    blocker_ids: tuple[str, ...]
    synthetic_sample_size: int
    observation_window_seconds: int
    observation_result_digests: tuple[str, ...]
    rollback_triggers: tuple[str, ...]
    requested_scope: str
    allowed_decisions: tuple[str, ...]
    required_acknowledgements: tuple[str, ...]
    generated_at: datetime
    valid_until: datetime
    previous_digest: str
    packet_digest: str
    release_status: str = "BLOCKED"
    operator_decision_recorded: bool = False
    candidate_content_present: bool = False
    patch_content_present: bool = False
    diff_content_present: bool = False
    source_code_changed: bool = False
    filesystem_written: bool = False
    automatic_application_allowed: bool = False
    activation_allowed: bool = False
    rollback_execution_allowed: bool = False
    safety_baseline_relaxation_allowed: bool = False
    execution_allowed: bool = False
    production_activation_allowed: bool = False

    def __post_init__(self) -> None:
        forbidden = (
            self.operator_decision_recorded,
            self.candidate_content_present,
            self.patch_content_present,
            self.diff_content_present,
            self.source_code_changed,
            self.filesystem_written,
            self.automatic_application_allowed,
            self.activation_allowed,
            self.rollback_execution_allowed,
            self.safety_baseline_relaxation_allowed,
            self.execution_allowed,
            self.production_activation_allowed,
        )
        if (
            self.sequence <= 0
            or self.packet_id
            != _packet_id(
                self.manifest_id,
                self.manifest_digest,
                self.final_review_digest,
                self.governance_digest,
                self.generated_at,
            )
            or not self.manifest_id.startswith(
                "synthetic:limited-promotion-activation-manifest:"
            )
            or not self.source_receipt_id.startswith(
                "synthetic:patch-draft-limited-promotion-reconfirmation-receipt:"
            )
            or not self.source_packet_id.startswith(
                "synthetic:patch-draft-limited-promotion-reconfirmation:"
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
                    self.manifest_digest,
                    self.final_review_digest,
                    self.source_receipt_digest,
                    self.source_packet_digest,
                    self.plan_digest,
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
            or not self.rollback_triggers
            or self.requested_scope != ACTIVATION_OPERATOR_PACKET_SCOPE
            or self.allowed_decisions != ACTIVATION_OPERATOR_ALLOWED_DECISIONS
            or self.required_acknowledgements
            != ACTIVATION_OPERATOR_REQUIRED_ACKNOWLEDGEMENTS
            or self.generated_at.tzinfo is None
            or self.valid_until
            != self.generated_at + ACTIVATION_OPERATOR_PACKET_VALIDITY
            or self.release_status != "BLOCKED"
            or any(forbidden)
            or self.packet_digest != canonical_digest(self.digest_value())
        ):
            raise GovernanceRejected(
                "valid non-authorizing activation operator packet required"
            )

    def digest_value(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "packet_id": self.packet_id,
            "manifest_id": self.manifest_id,
            "manifest_digest": self.manifest_digest,
            "final_review_digest": self.final_review_digest,
            "source_receipt_id": self.source_receipt_id,
            "source_receipt_digest": self.source_receipt_digest,
            "source_packet_id": self.source_packet_id,
            "source_packet_digest": self.source_packet_digest,
            "shadow_id": self.shadow_id,
            "plan_id": self.plan_id,
            "plan_digest": self.plan_digest,
            "candidate_digest": self.candidate_digest,
            "cohort_digest": self.cohort_digest,
            "shadow_assessment_digest": self.shadow_assessment_digest,
            "shadow_review_digest": self.shadow_review_digest,
            "governance_digest": self.governance_digest,
            "blocker_ids": list(self.blocker_ids),
            "synthetic_sample_size": self.synthetic_sample_size,
            "observation_window_seconds": self.observation_window_seconds,
            "observation_result_digests": list(self.observation_result_digests),
            "rollback_triggers": list(self.rollback_triggers),
            "requested_scope": self.requested_scope,
            "allowed_decisions": list(self.allowed_decisions),
            "required_acknowledgements": list(self.required_acknowledgements),
            "generated_at": self.generated_at.isoformat(),
            "valid_until": self.valid_until.isoformat(),
            "previous_digest": self.previous_digest,
            "release_status": "BLOCKED",
            "operator_decision_recorded": False,
            "candidate_content_present": False,
            "patch_content_present": False,
            "diff_content_present": False,
            "source_code_changed": False,
            "filesystem_written": False,
            "automatic_application_allowed": False,
            "activation_allowed": False,
            "rollback_execution_allowed": False,
            "safety_baseline_relaxation_allowed": False,
            "execution_allowed": False,
            "production_activation_allowed": False,
        }


class SyntheticPatchDraftLimitedPromotionActivationOperatorPacketBook:
    """Builds immutable operator material without recording a decision."""

    def __init__(self) -> None:
        self._packets: list[
            SyntheticPatchDraftLimitedPromotionActivationOperatorPacket
        ] = []
        self._by_manifest: dict[
            str, SyntheticPatchDraftLimitedPromotionActivationOperatorPacket
        ] = {}
        self._lock = RLock()

    @property
    def packets(
        self,
    ) -> tuple[SyntheticPatchDraftLimitedPromotionActivationOperatorPacket, ...]:
        with self._lock:
            return tuple(self._packets)

    def prepare(
        self,
        docket: SyntheticPatchDraftLimitedPromotionActivationReviewDocket,
        manifest_id: str,
        governance: OperatorGovernanceSnapshot,
        *,
        generated_at: datetime,
    ) -> SyntheticPatchDraftLimitedPromotionActivationOperatorPacket:
        if generated_at.tzinfo is None:
            raise GovernanceRejected("timezone-aware activation packet time required")
        if not isinstance(
            docket,
            SyntheticPatchDraftLimitedPromotionActivationReviewDocket,
        ):
            raise GovernanceRejected("typed activation final review docket required")
        if not isinstance(governance, OperatorGovernanceSnapshot):
            raise GovernanceRejected("verified operator governance snapshot required")
        if governance.governance_digest != canonical_digest(governance.digest_value()):
            raise GovernanceRejected("operator governance snapshot digest mismatch")

        before = docket.evidence()["report_digest"]
        source = docket.ready_source(manifest_id)
        manifest = source.manifest
        if (
            source.state
            is not ActivationManifestReviewState.READY_FOR_SYNTHETIC_LIMITED_PROMOTION_OPERATOR_DECISION
            or source.review_decision is not ActivationManifestReviewDecision.PASS
            or source.review_digest is None
            or source.reviewed_at is None
            or generated_at < source.reviewed_at
            or manifest.manifest_digest != canonical_digest(manifest.digest_value())
            or manifest.governance_digest != governance.governance_digest
        ):
            raise GovernanceRejected("bound passing activation final review required")

        packet_id = _packet_id(
            manifest.manifest_id,
            manifest.manifest_digest,
            source.review_digest,
            governance.governance_digest,
            generated_at,
        )
        with self._lock:
            created = False
            if not self.verify_packet_chain():
                raise GovernanceRejected("existing activation packet chain is invalid")
            existing = self._by_manifest.get(manifest_id)
            if existing is not None:
                if (
                    existing.manifest_digest != manifest.manifest_digest
                    or existing.final_review_digest != source.review_digest
                    or existing.governance_digest != governance.governance_digest
                ):
                    raise GovernanceRejected("activation packet source collision")
                packet = existing
            else:
                sequence = len(self._packets) + 1
                previous = self._packets[-1].packet_digest if self._packets else "0" * 64
                values = {
                    "sequence": sequence,
                    "packet_id": packet_id,
                    "manifest_id": manifest.manifest_id,
                    "manifest_digest": manifest.manifest_digest,
                    "final_review_digest": source.review_digest,
                    "source_receipt_id": manifest.source_receipt_id,
                    "source_receipt_digest": manifest.source_receipt_digest,
                    "source_packet_id": manifest.source_packet_id,
                    "source_packet_digest": manifest.source_packet_digest,
                    "shadow_id": manifest.shadow_id,
                    "plan_id": manifest.plan_id,
                    "plan_digest": manifest.plan_digest,
                    "candidate_digest": manifest.candidate_digest,
                    "cohort_digest": manifest.cohort_digest,
                    "shadow_assessment_digest": manifest.shadow_assessment_digest,
                    "shadow_review_digest": manifest.shadow_review_digest,
                    "governance_digest": governance.governance_digest,
                    "blocker_ids": list(governance.blocker_ids),
                    "synthetic_sample_size": manifest.synthetic_sample_size,
                    "observation_window_seconds": manifest.observation_window_seconds,
                    "observation_result_digests": list(
                        manifest.observation_result_digests
                    ),
                    "rollback_triggers": list(manifest.rollback_triggers),
                    "requested_scope": ACTIVATION_OPERATOR_PACKET_SCOPE,
                    "allowed_decisions": list(ACTIVATION_OPERATOR_ALLOWED_DECISIONS),
                    "required_acknowledgements": list(
                        ACTIVATION_OPERATOR_REQUIRED_ACKNOWLEDGEMENTS
                    ),
                    "generated_at": generated_at.isoformat(),
                    "valid_until": (
                        generated_at + ACTIVATION_OPERATOR_PACKET_VALIDITY
                    ).isoformat(),
                    "previous_digest": previous,
                    "release_status": "BLOCKED",
                    "operator_decision_recorded": False,
                    "candidate_content_present": False,
                    "patch_content_present": False,
                    "diff_content_present": False,
                    "source_code_changed": False,
                    "filesystem_written": False,
                    "automatic_application_allowed": False,
                    "activation_allowed": False,
                    "rollback_execution_allowed": False,
                    "safety_baseline_relaxation_allowed": False,
                    "execution_allowed": False,
                    "production_activation_allowed": False,
                }
                packet = SyntheticPatchDraftLimitedPromotionActivationOperatorPacket(
                    sequence,
                    packet_id,
                    manifest.manifest_id,
                    manifest.manifest_digest,
                    source.review_digest,
                    manifest.source_receipt_id,
                    manifest.source_receipt_digest,
                    manifest.source_packet_id,
                    manifest.source_packet_digest,
                    manifest.shadow_id,
                    manifest.plan_id,
                    manifest.plan_digest,
                    manifest.candidate_digest,
                    manifest.cohort_digest,
                    manifest.shadow_assessment_digest,
                    manifest.shadow_review_digest,
                    governance.governance_digest,
                    governance.blocker_ids,
                    manifest.synthetic_sample_size,
                    manifest.observation_window_seconds,
                    manifest.observation_result_digests,
                    manifest.rollback_triggers,
                    ACTIVATION_OPERATOR_PACKET_SCOPE,
                    ACTIVATION_OPERATOR_ALLOWED_DECISIONS,
                    ACTIVATION_OPERATOR_REQUIRED_ACKNOWLEDGEMENTS,
                    generated_at,
                    generated_at + ACTIVATION_OPERATOR_PACKET_VALIDITY,
                    previous,
                    canonical_digest(values),
                )
                self._packets.append(packet)
                self._by_manifest[manifest_id] = packet
                created = True
            if before != docket.evidence()["report_digest"]:
                if created:
                    self._packets.pop()
                    self._by_manifest.pop(manifest_id, None)
                raise GovernanceRejected(
                    "activation final review changed during packet preparation"
                )
        return packet

    def current_packet(
        self, manifest_id: str, *, now: datetime
    ) -> SyntheticPatchDraftLimitedPromotionActivationOperatorPacket:
        if now.tzinfo is None:
            raise GovernanceRejected("timezone-aware activation packet lookup required")
        with self._lock:
            packet = self._by_manifest.get(manifest_id)
            if packet is None:
                raise GovernanceRejected("unknown activation operator packet")
            if now > packet.valid_until:
                raise GovernanceRejected("activation operator packet is stale")
            if not self.verify_packet_chain():
                raise GovernanceRejected("activation operator packet integrity failure")
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
                        packet.manifest_id,
                        packet.manifest_digest,
                        packet.final_review_digest,
                        packet.governance_digest,
                        packet.generated_at,
                    )
                    or packet.packet_digest != canonical_digest(packet.digest_value())
                    or any(
                        (
                            packet.operator_decision_recorded,
                            packet.candidate_content_present,
                            packet.patch_content_present,
                            packet.diff_content_present,
                            packet.source_code_changed,
                            packet.filesystem_written,
                            packet.automatic_application_allowed,
                            packet.activation_allowed,
                            packet.rollback_execution_allowed,
                            packet.safety_baseline_relaxation_allowed,
                            packet.execution_allowed,
                            packet.production_activation_allowed,
                        )
                    )
                ):
                    return False
                previous = packet.packet_digest
            return len(self._packets) == len(self._by_manifest) and all(
                self._by_manifest.get(packet.manifest_id) is packet
                for packet in self._packets
            )

    def evidence(self) -> dict[str, object]:
        with self._lock:
            value = {
                "schema": (
                    "nurion.pg.synthetic-limited-promotion-activation-"
                    "operator-packet-evidence.v1"
                ),
                "mode": "UNREGISTERED_SYNTHETIC_ONLY",
                "packet_count": len(self._packets),
                "packet_digests": [packet.packet_digest for packet in self._packets],
                "packet_chain_valid": self.verify_packet_chain(),
                "maximum_state": (
                    "AWAITING_SYNTHETIC_LIMITED_PROMOTION_ACTIVATION_OPERATOR_DECISION"
                ),
                "requested_scope": ACTIVATION_OPERATOR_PACKET_SCOPE,
                "operator_decision_method_present": False,
                "operator_decision_recorded": False,
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
