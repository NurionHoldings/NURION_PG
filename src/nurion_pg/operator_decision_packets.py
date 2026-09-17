"""Non-authorizing operator decision packets for reviewed synthetic shadow evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import RLock
from typing import Mapping

from .arkaon.governance import GovernanceRejected, canonical_digest
from .remediation_shadow_review_docket import SyntheticRemediationShadowReviewDocket


PACKET_VALIDITY = timedelta(days=7)
PACKET_SCOPE = "SYNTHETIC_IMPLEMENTATION_PROPOSAL_DRAFT_ONLY"
ALLOWED_OPERATOR_DECISIONS = (
    "AUTHORIZE_SYNTHETIC_IMPLEMENTATION_PROPOSAL_DRAFT",
    "HOLD",
    "REJECT",
)
REQUIRED_ACKNOWLEDGEMENTS = (
    "SYNTHETIC_ONLY",
    "NO_CODE_CHANGE_OR_APPLICATION",
    "NO_PAYMENT_EXECUTION_OR_MONEY_MOVEMENT",
    "EXPLICIT_OPERATOR_DECISION_REQUIRED",
    "SEPARATE_IMPLEMENTATION_REVIEW_REQUIRED",
    "NO_PRODUCTION_PROMOTION",
)
REQUIRED_FORBIDDEN_ACTIONS = {
    "run_live_payment",
    "run_refund",
    "run_payout",
    "access_production_secret",
    "access_real_personal_data",
    "approve_merchant",
    "sign_contract",
    "change_fee_or_settlement",
    "contact_external_party",
    "merge_main",
    "deploy_production",
    "modify_self",
    "lower_safety_threshold",
    "delete_failed_test",
    "auto_learn_internet",
}
SAFE_SYNTHETIC_ACTIONS = {
    "read_public_official_source",
    "create_draft",
    "propose_change",
    "run_synthetic_test",
    "generate_evidence",
}
REQUIRED_PROMOTION_STAGES = (
    "BASELINE",
    "PROPOSAL",
    "SYNTHETIC_SHADOW",
    "ETHERNIAN_REVIEW",
    "OPERATOR_APPROVED",
    "LIMITED_PROMOTION",
    "ROLLED_BACK",
)


def _valid_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


@dataclass(frozen=True)
class OperatorGovernanceSnapshot:
    external_blockers_digest: str
    authority_policy_digest: str
    promotion_policy_digest: str
    blocker_ids: tuple[str, ...]
    governance_digest: str
    release_status: str = "BLOCKED"
    automatic_blocker_close_allowed: bool = False
    production_promotion_allowed: bool = False
    automatic_merge_allowed: bool = False
    automatic_deploy_allowed: bool = False

    def __post_init__(self) -> None:
        if (
            not _valid_digest(self.external_blockers_digest)
            or not _valid_digest(self.authority_policy_digest)
            or not _valid_digest(self.promotion_policy_digest)
            or not self.blocker_ids
            or len(set(self.blocker_ids)) != len(self.blocker_ids)
            or any(not item.startswith("EXT-PG-") for item in self.blocker_ids)
            or self.release_status != "BLOCKED"
            or self.automatic_blocker_close_allowed
            or self.production_promotion_allowed
            or self.automatic_merge_allowed
            or self.automatic_deploy_allowed
            or self.governance_digest != canonical_digest(self.digest_value())
        ):
            raise GovernanceRejected("valid fail-closed operator governance snapshot required")

    def digest_value(self) -> dict[str, object]:
        return {
            "external_blockers_digest": self.external_blockers_digest,
            "authority_policy_digest": self.authority_policy_digest,
            "promotion_policy_digest": self.promotion_policy_digest,
            "blocker_ids": list(self.blocker_ids),
            "release_status": self.release_status,
            "automatic_blocker_close_allowed": self.automatic_blocker_close_allowed,
            "production_promotion_allowed": self.production_promotion_allowed,
            "automatic_merge_allowed": self.automatic_merge_allowed,
            "automatic_deploy_allowed": self.automatic_deploy_allowed,
        }

    @classmethod
    def from_documents(
        cls,
        external_blockers: Mapping[str, object],
        authority_policy: Mapping[str, object],
        promotion_policy: Mapping[str, object],
    ) -> "OperatorGovernanceSnapshot":
        blockers = external_blockers.get("blockers")
        if (
            external_blockers.get("schema") != "nurion.pg.external-blockers.v1"
            or external_blockers.get("release_status") != "BLOCKED"
            or external_blockers.get("automatic_close_allowed") is not False
            or not isinstance(blockers, list)
            or not blockers
        ):
            raise GovernanceRejected("current pending external blocker registry required")
        blocker_ids = []
        for blocker in blockers:
            if (
                not isinstance(blocker, dict)
                or not isinstance(blocker.get("id"), str)
                or not str(blocker["id"]).startswith("EXT-PG-")
                or blocker.get("status") != "PENDING"
                or not isinstance(blocker.get("name"), str)
                or not blocker["name"]
            ):
                raise GovernanceRejected("all external blockers must remain pending")
            blocker_ids.append(str(blocker["id"]))
        forbidden = authority_policy.get("forbidden_actions")
        allowed = authority_policy.get("allowed_synthetic_actions")
        review_only = authority_policy.get("review_only_actions")
        if (
            authority_policy.get("schema") != "nurion.pg.arkaon-authority.v1"
            or authority_policy.get("platform_id") != "NURION_PG"
            or authority_policy.get("default_decision") != "BLOCKED"
            or authority_policy.get("operator_final_authority") is not True
            or authority_policy.get("internet_is_untrusted_input") is not True
            or not isinstance(forbidden, list)
            or not REQUIRED_FORBIDDEN_ACTIONS.issubset(set(forbidden))
            or not isinstance(allowed, list)
            or set(allowed) != SAFE_SYNTHETIC_ACTIONS
            or set(allowed).intersection(forbidden)
            or review_only != ["request_ethernian_review"]
        ):
            raise GovernanceRejected("fail-closed ARKAON authority policy required")
        duties = promotion_policy.get("separation_of_duties")
        if (
            promotion_policy.get("schema") != "nurion.pg.arkaon-promotion.v1"
            or tuple(promotion_policy.get("stages", ())) != REQUIRED_PROMOTION_STAGES
            or not isinstance(duties, dict)
            or duties.get("proposal_actor") != "ARKAON"
            or duties.get("independent_reviewer") != "ETHERNIAN"
            or duties.get("final_decider") != "CHOI_IN_SEOK_OPERATOR"
            or promotion_policy.get("limited_scope_prefix") != "synthetic:"
            or promotion_policy.get("production_promotion_allowed") is not False
            or promotion_policy.get("automatic_merge_allowed") is not False
            or promotion_policy.get("automatic_deploy_allowed") is not False
        ):
            raise GovernanceRejected("separated fail-closed promotion policy required")
        values = {
            "external_blockers_digest": canonical_digest(dict(external_blockers)),
            "authority_policy_digest": canonical_digest(dict(authority_policy)),
            "promotion_policy_digest": canonical_digest(dict(promotion_policy)),
            "blocker_ids": sorted(blocker_ids),
            "release_status": "BLOCKED",
            "automatic_blocker_close_allowed": False,
            "production_promotion_allowed": False,
            "automatic_merge_allowed": False,
            "automatic_deploy_allowed": False,
        }
        return cls(
            str(values["external_blockers_digest"]),
            str(values["authority_policy_digest"]),
            str(values["promotion_policy_digest"]),
            tuple(values["blocker_ids"]),
            canonical_digest(values),
        )


@dataclass(frozen=True)
class OperatorDecisionPacket:
    sequence: int
    packet_id: str
    shadow_id: str
    proposal_id: str
    proposal_digest: str
    shadow_assessment_digest: str
    eternian_review_digest: str
    governance_digest: str
    blocker_ids: tuple[str, ...]
    action_types: tuple[str, ...]
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
    code_change_allowed: bool = False
    automatic_application_allowed: bool = False
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if (
            self.sequence <= 0
            or not self.packet_id.startswith("synthetic:operator-decision-packet:")
            or not self.shadow_id.startswith("synthetic:remediation-shadow:")
            or not self.proposal_id.startswith("synthetic:remediation-proposal:")
            or not _valid_digest(self.proposal_digest)
            or not _valid_digest(self.shadow_assessment_digest)
            or not _valid_digest(self.eternian_review_digest)
            or not _valid_digest(self.governance_digest)
            or not self.blocker_ids
            or not self.action_types
            or not self.item_result_digests
            or not all(_valid_digest(item) for item in self.item_result_digests)
            or self.requested_scope != PACKET_SCOPE
            or self.allowed_decisions != ALLOWED_OPERATOR_DECISIONS
            or self.required_acknowledgements != REQUIRED_ACKNOWLEDGEMENTS
            or self.generated_at.tzinfo is None
            or self.valid_until != self.generated_at + PACKET_VALIDITY
            or not _valid_digest(self.previous_digest)
            or self.release_status != "BLOCKED"
            or self.operator_decision_recorded
            or self.code_change_allowed
            or self.automatic_application_allowed
            or self.execution_allowed
            or self.packet_digest != canonical_digest(self.digest_value())
        ):
            raise GovernanceRejected("valid non-authorizing operator packet required")

    def digest_value(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "packet_id": self.packet_id,
            "shadow_id": self.shadow_id,
            "proposal_id": self.proposal_id,
            "proposal_digest": self.proposal_digest,
            "shadow_assessment_digest": self.shadow_assessment_digest,
            "eternian_review_digest": self.eternian_review_digest,
            "governance_digest": self.governance_digest,
            "blocker_ids": list(self.blocker_ids),
            "action_types": list(self.action_types),
            "item_result_digests": list(self.item_result_digests),
            "requested_scope": self.requested_scope,
            "allowed_decisions": list(self.allowed_decisions),
            "required_acknowledgements": list(self.required_acknowledgements),
            "generated_at": self.generated_at.isoformat(),
            "valid_until": self.valid_until.isoformat(),
            "previous_digest": self.previous_digest,
            "release_status": self.release_status,
            "operator_decision_recorded": self.operator_decision_recorded,
            "code_change_allowed": self.code_change_allowed,
            "automatic_application_allowed": self.automatic_application_allowed,
            "execution_allowed": self.execution_allowed,
        }


class SyntheticOperatorDecisionPacketBook:
    """Builds immutable decision material but exposes no decision method."""

    def __init__(self) -> None:
        self._packets: list[OperatorDecisionPacket] = []
        self._by_shadow: dict[str, OperatorDecisionPacket] = {}
        self._lock = RLock()

    @property
    def packets(self) -> tuple[OperatorDecisionPacket, ...]:
        with self._lock:
            return tuple(self._packets)

    def prepare(
        self,
        docket: SyntheticRemediationShadowReviewDocket,
        shadow_id: str,
        governance: OperatorGovernanceSnapshot,
        *,
        generated_at: datetime,
    ) -> OperatorDecisionPacket:
        if generated_at.tzinfo is None:
            raise GovernanceRejected("timezone-aware operator packet time required")
        if not isinstance(governance, OperatorGovernanceSnapshot):
            raise GovernanceRejected("verified operator governance snapshot required")
        if governance.governance_digest != canonical_digest(governance.digest_value()):
            raise GovernanceRejected("operator governance snapshot digest mismatch")
        before = docket.evidence()["report_digest"]
        source = docket.ready_source(shadow_id)
        if generated_at < source.reviewed_at:
            raise GovernanceRejected("operator packet cannot predate Eternian review")
        try:
            assessment = json.loads(source.assessment_json)
        except (TypeError, ValueError) as exc:
            raise GovernanceRejected("ready shadow assessment JSON is invalid") from exc
        results = assessment.get("item_results") if isinstance(assessment, dict) else None
        if not isinstance(results, list) or not results:
            raise GovernanceRejected("shadow item results required for operator packet")
        action_types = tuple(sorted({str(item["action_type"]) for item in results}))
        result_digests = tuple(str(item["result_digest"]) for item in results)
        identity_value = {
            "shadow_id": source.shadow_id,
            "shadow_assessment_digest": source.shadow_assessment_digest,
            "eternian_review_digest": source.review_digest,
            "governance_digest": governance.governance_digest,
            "generated_at": generated_at.isoformat(),
        }
        packet_id = (
            "synthetic:operator-decision-packet:"
            + canonical_digest(identity_value)[:32]
        )
        created = False
        with self._lock:
            existing = self._by_shadow.get(shadow_id)
            if existing is not None:
                if (
                    existing.shadow_assessment_digest != source.shadow_assessment_digest
                    or existing.eternian_review_digest != source.review_digest
                    or existing.governance_digest != governance.governance_digest
                ):
                    raise GovernanceRejected("operator packet source collision")
                packet = existing
            else:
                sequence = len(self._packets) + 1
                previous = self._packets[-1].packet_digest if self._packets else "0" * 64
                values = {
                    "sequence": sequence,
                    "packet_id": packet_id,
                    "shadow_id": source.shadow_id,
                    "proposal_id": source.proposal_id,
                    "proposal_digest": source.proposal_digest,
                    "shadow_assessment_digest": source.shadow_assessment_digest,
                    "eternian_review_digest": source.review_digest,
                    "governance_digest": governance.governance_digest,
                    "blocker_ids": list(governance.blocker_ids),
                    "action_types": list(action_types),
                    "item_result_digests": list(result_digests),
                    "requested_scope": PACKET_SCOPE,
                    "allowed_decisions": list(ALLOWED_OPERATOR_DECISIONS),
                    "required_acknowledgements": list(REQUIRED_ACKNOWLEDGEMENTS),
                    "generated_at": generated_at.isoformat(),
                    "valid_until": (generated_at + PACKET_VALIDITY).isoformat(),
                    "previous_digest": previous,
                    "release_status": "BLOCKED",
                    "operator_decision_recorded": False,
                    "code_change_allowed": False,
                    "automatic_application_allowed": False,
                    "execution_allowed": False,
                }
                packet = OperatorDecisionPacket(
                    sequence,
                    packet_id,
                    source.shadow_id,
                    source.proposal_id,
                    source.proposal_digest,
                    source.shadow_assessment_digest,
                    source.review_digest,
                    governance.governance_digest,
                    governance.blocker_ids,
                    action_types,
                    result_digests,
                    PACKET_SCOPE,
                    ALLOWED_OPERATOR_DECISIONS,
                    REQUIRED_ACKNOWLEDGEMENTS,
                    generated_at,
                    generated_at + PACKET_VALIDITY,
                    previous,
                    canonical_digest(values),
                )
                self._packets.append(packet)
                self._by_shadow[shadow_id] = packet
                created = True
        after = docket.evidence()["report_digest"]
        if before != after:
            with self._lock:
                if (
                    created
                    and self._by_shadow.get(shadow_id) is packet
                    and packet is self._packets[-1]
                ):
                    self._packets.pop()
                    self._by_shadow.pop(shadow_id, None)
            raise GovernanceRejected("source shadow review changed during packet preparation")
        return packet

    def current_packet(self, shadow_id: str, *, now: datetime) -> OperatorDecisionPacket:
        if now.tzinfo is None:
            raise GovernanceRejected("timezone-aware operator packet lookup required")
        with self._lock:
            packet = self._by_shadow.get(shadow_id)
            if packet is None:
                raise GovernanceRejected("unknown operator decision packet")
            if now > packet.valid_until:
                raise GovernanceRejected("operator decision packet is stale")
            if packet.packet_digest != canonical_digest(packet.digest_value()):
                raise GovernanceRejected("operator decision packet integrity failure")
            return packet

    def verify_packet_chain(self) -> bool:
        with self._lock:
            previous = "0" * 64
            for sequence, packet in enumerate(self._packets, start=1):
                if (
                    packet.sequence != sequence
                    or packet.previous_digest != previous
                    or packet.packet_digest != canonical_digest(packet.digest_value())
                    or packet.operator_decision_recorded
                    or packet.code_change_allowed
                    or packet.automatic_application_allowed
                    or packet.execution_allowed
                ):
                    return False
                previous = packet.packet_digest
            return True

    def evidence(self) -> dict[str, object]:
        with self._lock:
            value = {
                "schema": "nurion.pg.synthetic-operator-decision-packet-evidence.v1",
                "packet_count": len(self._packets),
                "packet_digests": [packet.packet_digest for packet in self._packets],
                "packet_chain_valid": self.verify_packet_chain(),
                "maximum_state": "AWAITING_OPERATOR_DECISION",
                "requested_scope": PACKET_SCOPE,
                "operator_decision_method_present": False,
                "code_change_method_present": False,
                "application_method_present": False,
                "execution_method_present": False,
                "external_blocker_close_method_present": False,
                "money_movement_executed": False,
                "production_activation_allowed": False,
            }
            return {**value, "report_digest": canonical_digest(value)}
