"""Non-authorizing operator packets for reviewed patch draft shadow evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest
from .operator_decision_packets import OperatorGovernanceSnapshot
from .synthetic_patch_draft_shadow_review_docket import (
    SyntheticPatchDraftShadowReviewDocket,
)


PATCH_DRAFT_PROMOTION_PACKET_VALIDITY = timedelta(days=7)
PATCH_DRAFT_PROMOTION_PACKET_SCOPE = (
    "SYNTHETIC_PATCH_DRAFT_LIMITED_PROMOTION_ONLY"
)
PATCH_DRAFT_PROMOTION_ALLOWED_DECISIONS = (
    "AUTHORIZE_SYNTHETIC_PATCH_DRAFT_LIMITED_PROMOTION",
    "HOLD",
    "REJECT",
)
PATCH_DRAFT_PROMOTION_REQUIRED_ACKNOWLEDGEMENTS = (
    "SYNTHETIC_ONLY",
    "METADATA_ONLY_PACKET",
    "NO_PATCH_OR_DIFF_CONTENT",
    "NO_SOURCE_OR_FILESYSTEM_CHANGE",
    "NO_AUTOMATIC_APPLICATION",
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
    return "synthetic:patch-draft-promotion-operator-packet:" + identity[:32]


@dataclass(frozen=True)
class PatchDraftPromotionOperatorPacket:
    sequence: int
    packet_id: str
    shadow_id: str
    manifest_id: str
    manifest_digest: str
    source_review_digest: str
    shadow_assessment_digest: str
    shadow_review_digest: str
    governance_digest: str
    blocker_ids: tuple[str, ...]
    draft_scopes: tuple[str, ...]
    target_path_digests: tuple[str, ...]
    item_result_digests: tuple[str, ...]
    requested_scope: str
    allowed_decisions: tuple[str, ...]
    required_acknowledgements: tuple[str, ...]
    generated_at: datetime
    valid_until: datetime
    previous_digest: str
    packet_digest: str
    release_status: str = "BLOCKED"
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
        forbidden = (
            self.operator_decision_recorded,
            self.patch_content_present,
            self.diff_content_present,
            self.source_code_changed,
            self.filesystem_written,
            self.automatic_application_allowed,
            self.safety_baseline_relaxation_allowed,
            self.execution_allowed,
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
            or not self.shadow_id.startswith("synthetic:patch-draft-shadow:")
            or not self.manifest_id.startswith("synthetic:patch-draft-manifest:")
            or not all(
                _valid_digest(value)
                for value in (
                    self.manifest_digest,
                    self.source_review_digest,
                    self.shadow_assessment_digest,
                    self.shadow_review_digest,
                    self.governance_digest,
                    self.previous_digest,
                )
            )
            or not self.blocker_ids
            or len(set(self.blocker_ids)) != len(self.blocker_ids)
            or any(not item.startswith("EXT-PG-") for item in self.blocker_ids)
            or not self.draft_scopes
            or len(set(self.draft_scopes)) != len(self.draft_scopes)
            or any(not scope.endswith("_DRAFT_ONLY") for scope in self.draft_scopes)
            or len(self.target_path_digests) != len(self.draft_scopes)
            or len(self.item_result_digests) != len(self.draft_scopes)
            or not all(_valid_digest(item) for item in self.target_path_digests)
            or not all(_valid_digest(item) for item in self.item_result_digests)
            or self.requested_scope != PATCH_DRAFT_PROMOTION_PACKET_SCOPE
            or self.allowed_decisions != PATCH_DRAFT_PROMOTION_ALLOWED_DECISIONS
            or self.required_acknowledgements
            != PATCH_DRAFT_PROMOTION_REQUIRED_ACKNOWLEDGEMENTS
            or self.generated_at.tzinfo is None
            or self.valid_until
            != self.generated_at + PATCH_DRAFT_PROMOTION_PACKET_VALIDITY
            or self.release_status != "BLOCKED"
            or any(forbidden)
            or self.packet_digest != canonical_digest(self.digest_value())
        ):
            raise GovernanceRejected(
                "valid non-authorizing patch draft promotion packet required"
            )

    def digest_value(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "packet_id": self.packet_id,
            "shadow_id": self.shadow_id,
            "manifest_id": self.manifest_id,
            "manifest_digest": self.manifest_digest,
            "source_review_digest": self.source_review_digest,
            "shadow_assessment_digest": self.shadow_assessment_digest,
            "shadow_review_digest": self.shadow_review_digest,
            "governance_digest": self.governance_digest,
            "blocker_ids": list(self.blocker_ids),
            "draft_scopes": list(self.draft_scopes),
            "target_path_digests": list(self.target_path_digests),
            "item_result_digests": list(self.item_result_digests),
            "requested_scope": self.requested_scope,
            "allowed_decisions": list(self.allowed_decisions),
            "required_acknowledgements": list(self.required_acknowledgements),
            "generated_at": self.generated_at.isoformat(),
            "valid_until": self.valid_until.isoformat(),
            "previous_digest": self.previous_digest,
            "release_status": self.release_status,
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


class SyntheticPatchDraftPromotionOperatorPacketBook:
    """Builds immutable review material without recording an operator decision."""

    def __init__(self) -> None:
        self._packets: list[PatchDraftPromotionOperatorPacket] = []
        self._by_shadow: dict[str, PatchDraftPromotionOperatorPacket] = {}
        self._lock = RLock()

    @property
    def packets(self) -> tuple[PatchDraftPromotionOperatorPacket, ...]:
        with self._lock:
            return tuple(self._packets)

    def prepare(
        self,
        docket: SyntheticPatchDraftShadowReviewDocket,
        shadow_id: str,
        governance: OperatorGovernanceSnapshot,
        *,
        generated_at: datetime,
    ) -> PatchDraftPromotionOperatorPacket:
        if generated_at.tzinfo is None:
            raise GovernanceRejected("timezone-aware promotion packet time required")
        if not isinstance(docket, SyntheticPatchDraftShadowReviewDocket):
            raise GovernanceRejected("typed patch draft shadow review docket required")
        if not isinstance(governance, OperatorGovernanceSnapshot):
            raise GovernanceRejected("verified operator governance snapshot required")
        if governance.governance_digest != canonical_digest(
            governance.digest_value()
        ):
            raise GovernanceRejected("operator governance snapshot digest mismatch")
        before = docket.evidence()["report_digest"]
        source = docket.ready_source(shadow_id)
        if generated_at < source.reviewed_at:
            raise GovernanceRejected("promotion packet cannot predate Eternian review")
        try:
            assessment = json.loads(source.assessment_json)
        except (TypeError, ValueError) as exc:
            raise GovernanceRejected("ready patch draft shadow JSON is invalid") from exc
        results = assessment.get("item_results") if isinstance(assessment, dict) else None
        if not isinstance(results, list) or not results:
            raise GovernanceRejected("patch draft shadow item results required")
        try:
            draft_scopes = tuple(str(item["draft_scope"]) for item in results)
            target_digests = tuple(str(item["target_path_digest"]) for item in results)
            result_digests = tuple(str(item["result_digest"]) for item in results)
            decisions = tuple(str(item["decision"]) for item in results)
        except (KeyError, TypeError) as exc:
            raise GovernanceRejected("complete patch draft shadow item results required") from exc
        if (
            assessment.get("shadow_id") != source.shadow_id
            or assessment.get("manifest_id") != source.manifest_id
            or assessment.get("manifest_digest") != source.manifest_digest
            or assessment.get("source_review_digest") != source.source_review_digest
            or assessment.get("assessment_digest") != source.shadow_assessment_digest
            or len(set(draft_scopes)) != len(draft_scopes)
            or any(not scope.endswith("_DRAFT_ONLY") for scope in draft_scopes)
            or any(decision != "PASS" for decision in decisions)
            or not all(_valid_digest(item) for item in target_digests)
            or not all(_valid_digest(item) for item in result_digests)
        ):
            raise GovernanceRejected("bound passing patch draft shadow results required")
        packet_id = _packet_id(
            source.shadow_id,
            source.shadow_assessment_digest,
            source.review_digest,
            governance.governance_digest,
            generated_at,
        )
        with self._lock:
            created = False
            if not self.verify_packet_chain():
                raise GovernanceRejected("existing promotion packet chain is invalid")
            existing = self._by_shadow.get(shadow_id)
            if existing is not None:
                if (
                    existing.shadow_assessment_digest
                    != source.shadow_assessment_digest
                    or existing.shadow_review_digest != source.review_digest
                    or existing.governance_digest != governance.governance_digest
                ):
                    raise GovernanceRejected("promotion packet source collision")
                packet = existing
            else:
                sequence = len(self._packets) + 1
                previous = self._packets[-1].packet_digest if self._packets else "0" * 64
                values = {
                    "sequence": sequence,
                    "packet_id": packet_id,
                    "shadow_id": source.shadow_id,
                    "manifest_id": source.manifest_id,
                    "manifest_digest": source.manifest_digest,
                    "source_review_digest": source.source_review_digest,
                    "shadow_assessment_digest": source.shadow_assessment_digest,
                    "shadow_review_digest": source.review_digest,
                    "governance_digest": governance.governance_digest,
                    "blocker_ids": list(governance.blocker_ids),
                    "draft_scopes": list(draft_scopes),
                    "target_path_digests": list(target_digests),
                    "item_result_digests": list(result_digests),
                    "requested_scope": PATCH_DRAFT_PROMOTION_PACKET_SCOPE,
                    "allowed_decisions": list(
                        PATCH_DRAFT_PROMOTION_ALLOWED_DECISIONS
                    ),
                    "required_acknowledgements": list(
                        PATCH_DRAFT_PROMOTION_REQUIRED_ACKNOWLEDGEMENTS
                    ),
                    "generated_at": generated_at.isoformat(),
                    "valid_until": (
                        generated_at + PATCH_DRAFT_PROMOTION_PACKET_VALIDITY
                    ).isoformat(),
                    "previous_digest": previous,
                    "release_status": "BLOCKED",
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
                packet = PatchDraftPromotionOperatorPacket(
                    sequence,
                    packet_id,
                    source.shadow_id,
                    source.manifest_id,
                    source.manifest_digest,
                    source.source_review_digest,
                    source.shadow_assessment_digest,
                    source.review_digest,
                    governance.governance_digest,
                    governance.blocker_ids,
                    draft_scopes,
                    target_digests,
                    result_digests,
                    PATCH_DRAFT_PROMOTION_PACKET_SCOPE,
                    PATCH_DRAFT_PROMOTION_ALLOWED_DECISIONS,
                    PATCH_DRAFT_PROMOTION_REQUIRED_ACKNOWLEDGEMENTS,
                    generated_at,
                    generated_at + PATCH_DRAFT_PROMOTION_PACKET_VALIDITY,
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
                    "patch draft shadow review changed during packet preparation"
                )
        return packet

    def current_packet(
        self, shadow_id: str, *, now: datetime
    ) -> PatchDraftPromotionOperatorPacket:
        if now.tzinfo is None:
            raise GovernanceRejected("timezone-aware promotion packet lookup required")
        with self._lock:
            packet = self._by_shadow.get(shadow_id)
            if packet is None:
                raise GovernanceRejected("unknown patch draft promotion packet")
            if now > packet.valid_until:
                raise GovernanceRejected("patch draft promotion packet is stale")
            if not self.verify_packet_chain():
                raise GovernanceRejected("patch draft promotion packet integrity failure")
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
                    or packet.packet_digest != canonical_digest(packet.digest_value())
                    or any((
                        packet.operator_decision_recorded,
                        packet.patch_content_present,
                        packet.diff_content_present,
                        packet.source_code_changed,
                        packet.filesystem_written,
                        packet.automatic_application_allowed,
                        packet.safety_baseline_relaxation_allowed,
                        packet.execution_allowed,
                        packet.production_activation_allowed,
                    ))
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
                    "nurion.pg.synthetic-patch-draft-promotion-operator-packet-"
                    "evidence.v1"
                ),
                "packet_count": len(self._packets),
                "packet_digests": [packet.packet_digest for packet in self._packets],
                "packet_chain_valid": self.verify_packet_chain(),
                "maximum_state": "AWAITING_PATCH_DRAFT_PROMOTION_OPERATOR_DECISION",
                "requested_scope": PATCH_DRAFT_PROMOTION_PACKET_SCOPE,
                "operator_decision_method_present": False,
                "patch_content_present": False,
                "diff_content_present": False,
                "source_code_change_method_present": False,
                "filesystem_write_method_present": False,
                "application_method_present": False,
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
