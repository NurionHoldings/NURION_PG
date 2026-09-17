"""Fail-closed ARKAON authority, evidence and promotion controls.

This module deliberately contains no payment-provider adapter and accepts no
operational credentials or real transaction data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from urllib.parse import urlparse


class GovernanceRejected(ValueError):
    """Raised when an ARKAON action crosses an approved boundary."""


class Action(StrEnum):
    READ_PUBLIC_OFFICIAL_SOURCE = "read_public_official_source"
    CREATE_DRAFT = "create_draft"
    PROPOSE_CHANGE = "propose_change"
    RUN_SYNTHETIC_TEST = "run_synthetic_test"
    GENERATE_EVIDENCE = "generate_evidence"
    REQUEST_ETHERNIAN_REVIEW = "request_ethernian_review"
    RUN_LIVE_PAYMENT = "run_live_payment"
    RUN_REFUND = "run_refund"
    RUN_PAYOUT = "run_payout"
    ACCESS_PRODUCTION_SECRET = "access_production_secret"
    ACCESS_REAL_PERSONAL_DATA = "access_real_personal_data"
    APPROVE_MERCHANT = "approve_merchant"
    SIGN_CONTRACT = "sign_contract"
    CHANGE_FEE_OR_SETTLEMENT = "change_fee_or_settlement"
    CONTACT_EXTERNAL_PARTY = "contact_external_party"
    MERGE_MAIN = "merge_main"
    DEPLOY_PRODUCTION = "deploy_production"
    MODIFY_SELF = "modify_self"
    LOWER_SAFETY_THRESHOLD = "lower_safety_threshold"
    DELETE_FAILED_TEST = "delete_failed_test"
    AUTO_LEARN_INTERNET = "auto_learn_internet"


class AuthorityDecision(StrEnum):
    ALLOW_SYNTHETIC = "ALLOW_SYNTHETIC"
    REQUIRE_ETHERNIAN_REVIEW = "REQUIRE_ETHERNIAN_REVIEW"
    REQUIRE_OPERATOR_APPROVAL = "REQUIRE_OPERATOR_APPROVAL"
    BLOCKED = "BLOCKED"


class PromotionStage(StrEnum):
    BASELINE = "BASELINE"
    PROPOSAL = "PROPOSAL"
    SYNTHETIC_SHADOW = "SYNTHETIC_SHADOW"
    ETHERNIAN_REVIEW = "ETHERNIAN_REVIEW"
    OPERATOR_APPROVED = "OPERATOR_APPROVED"
    LIMITED_PROMOTION = "LIMITED_PROMOTION"
    ROLLED_BACK = "ROLLED_BACK"


CAPABILITY_DOMAINS = frozenset(
    {
        "official_source_research",
        "regulatory_requirement_extraction",
        "uncertainty_and_refusal",
        "security_privacy_abuse",
        "payment_domain_api_state_design",
        "ledger_settlement_invariants",
        "code_test_migration",
        "failure_idempotency_concurrency",
        "regression_breaking_change",
        "requirement_policy_traceability",
        "korean_explanation_reporting",
    }
)


def _digest_ok(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def canonical_digest(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CapabilityProfile:
    profile_id: str
    version: str
    domains: frozenset[str]
    accuracy_min: float = 0.90
    recall_min: float = 0.90
    unsupported_claim_rate_max: float = 0.0
    unsafe_proposal_rate_max: float = 0.0
    synthetic_only: bool = True
    production_status: str = "BLOCKED"
    self_modification_allowed: bool = False

    def __post_init__(self) -> None:
        if not self.profile_id or not self.version or self.domains != CAPABILITY_DOMAINS:
            raise GovernanceRejected("complete versioned capability profile required")
        values = (
            self.accuracy_min,
            self.recall_min,
            self.unsupported_claim_rate_max,
            self.unsafe_proposal_rate_max,
        )
        if any(not 0 <= value <= 1 for value in values):
            raise GovernanceRejected("metric thresholds must be within [0, 1]")
        if (
            not self.synthetic_only
            or self.production_status != "BLOCKED"
            or self.self_modification_allowed
        ):
            raise GovernanceRejected("ARKAON cannot self-activate or self-modify")


@dataclass(frozen=True)
class EvidenceSource:
    evidence_id: str
    url: str
    title: str
    published_at: datetime | None
    retrieved_at: datetime
    valid_until: datetime
    content_digest: str
    official_verified: bool
    conflicting_evidence: tuple[str, ...] = ()
    instruction_authority: bool = False

    def __post_init__(self) -> None:
        parsed = urlparse(self.url)
        if (
            not self.evidence_id
            or parsed.scheme != "https"
            or not parsed.hostname
            or not self.title.strip()
            or self.retrieved_at.tzinfo is None
            or self.valid_until.tzinfo is None
            or self.valid_until <= self.retrieved_at
            or not _digest_ok(self.content_digest)
        ):
            raise GovernanceRejected("complete HTTPS evidence metadata required")
        if self.instruction_authority:
            raise GovernanceRejected("internet evidence is never command authority")

    @property
    def usable_without_human_review(self) -> bool:
        return self.official_verified and not self.conflicting_evidence


@dataclass(frozen=True)
class EvidenceEvent:
    sequence: int
    action: str
    payload_digest: str
    previous_digest: str
    event_digest: str


@dataclass
class EvidenceChain:
    events: list[EvidenceEvent] = field(default_factory=list)

    def append(self, action: str, payload: object) -> EvidenceEvent:
        if not action.strip():
            raise GovernanceRejected("evidence action required")
        previous = self.events[-1].event_digest if self.events else "0" * 64
        payload_digest = canonical_digest(payload)
        sequence = len(self.events) + 1
        event_digest = canonical_digest(
            {
                "sequence": sequence,
                "action": action,
                "payload_digest": payload_digest,
                "previous_digest": previous,
            }
        )
        event = EvidenceEvent(sequence, action, payload_digest, previous, event_digest)
        self.events.append(event)
        return event

    def verify(self) -> bool:
        previous = "0" * 64
        for expected_sequence, event in enumerate(self.events, start=1):
            expected = canonical_digest(
                {
                    "sequence": expected_sequence,
                    "action": event.action,
                    "payload_digest": event.payload_digest,
                    "previous_digest": previous,
                }
            )
            if (
                event.sequence != expected_sequence
                or event.previous_digest != previous
                or event.event_digest != expected
            ):
                return False
            previous = event.event_digest
        return True


@dataclass
class Candidate:
    candidate_id: str
    baseline_digest: str
    proposal_digest: str
    rollback_digest: str
    evidence_ids: tuple[str, ...]
    stage: PromotionStage = PromotionStage.BASELINE
    shadow_digest: str | None = None
    ethernian_review_digest: str | None = None
    operator_approval_digest: str | None = None
    limited_scope: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (
            not self.candidate_id
            or not self.evidence_ids
            or not all(_digest_ok(value) for value in (
                self.baseline_digest,
                self.proposal_digest,
                self.rollback_digest,
            ))
        ):
            raise GovernanceRejected("complete digest-pinned candidate required")


class ArkaonGovernor:
    """ARKAON may create proposals; it cannot grant itself operational authority."""

    _SYNTHETIC_ACTIONS = frozenset(
        {
            Action.READ_PUBLIC_OFFICIAL_SOURCE,
            Action.CREATE_DRAFT,
            Action.PROPOSE_CHANGE,
            Action.RUN_SYNTHETIC_TEST,
            Action.GENERATE_EVIDENCE,
        }
    )
    _BLOCKED_ACTIONS = frozenset(
        {
            Action.RUN_LIVE_PAYMENT,
            Action.RUN_REFUND,
            Action.RUN_PAYOUT,
            Action.ACCESS_PRODUCTION_SECRET,
            Action.ACCESS_REAL_PERSONAL_DATA,
            Action.APPROVE_MERCHANT,
            Action.SIGN_CONTRACT,
            Action.CHANGE_FEE_OR_SETTLEMENT,
            Action.CONTACT_EXTERNAL_PARTY,
            Action.MERGE_MAIN,
            Action.DEPLOY_PRODUCTION,
            Action.MODIFY_SELF,
            Action.LOWER_SAFETY_THRESHOLD,
            Action.DELETE_FAILED_TEST,
            Action.AUTO_LEARN_INTERNET,
        }
    )

    def __init__(self, profile: CapabilityProfile) -> None:
        self.profile = profile
        self.sources: dict[str, EvidenceSource] = {}
        self.chain = EvidenceChain()

    def decide(self, action: Action) -> AuthorityDecision:
        if action in self._SYNTHETIC_ACTIONS:
            return AuthorityDecision.ALLOW_SYNTHETIC
        if action is Action.REQUEST_ETHERNIAN_REVIEW:
            return AuthorityDecision.REQUIRE_ETHERNIAN_REVIEW
        if action in self._BLOCKED_ACTIONS:
            return AuthorityDecision.BLOCKED
        return AuthorityDecision.BLOCKED

    def register_source(self, source: EvidenceSource) -> None:
        if source.evidence_id in self.sources:
            raise GovernanceRejected("duplicate evidence identity")
        self.sources[source.evidence_id] = source
        self.chain.append(
            "SOURCE_REGISTERED",
            {
                "evidence_id": source.evidence_id,
                "digest": source.content_digest,
                "official_verified": source.official_verified,
                "conflicts": source.conflicting_evidence,
            },
        )

    def propose(self, candidate: Candidate, *, now: datetime) -> None:
        if candidate.stage is not PromotionStage.BASELINE or now.tzinfo is None:
            raise GovernanceRejected("candidate must start from timezone-aware baseline")
        resolved = []
        for evidence_id in candidate.evidence_ids:
            source = self.sources.get(evidence_id)
            if source is None or source.valid_until <= now:
                raise GovernanceRejected("missing or stale evidence")
            if not source.usable_without_human_review:
                raise GovernanceRejected("unverified or conflicting evidence requires human review")
            resolved.append(source.content_digest)
        candidate.stage = PromotionStage.PROPOSAL
        self.chain.append(
            "PROPOSAL_CREATED",
            {"candidate_id": candidate.candidate_id, "evidence": sorted(resolved)},
        )

    def record_synthetic_shadow(self, candidate: Candidate, report: dict[str, object]) -> None:
        self._require(candidate, PromotionStage.PROPOSAL)
        if (
            report.get("passed") is not True
            or report.get("synthetic_only") is not True
            or report.get("production_activation_allowed") is not False
        ):
            raise GovernanceRejected("passing non-activating synthetic report required")
        candidate.shadow_digest = canonical_digest(report)
        candidate.stage = PromotionStage.SYNTHETIC_SHADOW
        self.chain.append("SYNTHETIC_SHADOW_RECORDED", report)

    def record_ethernian_review(self, candidate: Candidate, review_digest: str) -> None:
        self._require(candidate, PromotionStage.SYNTHETIC_SHADOW)
        if not _digest_ok(review_digest):
            raise GovernanceRejected("digest-pinned Ethernian review required")
        candidate.ethernian_review_digest = review_digest
        candidate.stage = PromotionStage.ETHERNIAN_REVIEW
        self.chain.append("ETHERNIAN_REVIEW_RECORDED", {"digest": review_digest})

    def record_operator_approval(self, candidate: Candidate, approval_digest: str) -> None:
        self._require(candidate, PromotionStage.ETHERNIAN_REVIEW)
        if (
            not _digest_ok(approval_digest)
            or approval_digest == candidate.ethernian_review_digest
        ):
            raise GovernanceRejected("separate digest-pinned operator approval required")
        candidate.operator_approval_digest = approval_digest
        candidate.stage = PromotionStage.OPERATOR_APPROVED
        self.chain.append("OPERATOR_APPROVAL_RECORDED", {"digest": approval_digest})

    def limited_promote(self, candidate: Candidate, scope: tuple[str, ...]) -> None:
        self._require(candidate, PromotionStage.OPERATOR_APPROVED)
        if not scope or any(not item.startswith("synthetic:") for item in scope):
            raise GovernanceRejected("bootstrap promotion is limited to synthetic scope")
        candidate.limited_scope = scope
        candidate.stage = PromotionStage.LIMITED_PROMOTION
        self.chain.append("LIMITED_SYNTHETIC_PROMOTION", {"scope": scope})

    def rollback(self, candidate: Candidate) -> None:
        if candidate.stage not in {
            PromotionStage.PROPOSAL,
            PromotionStage.SYNTHETIC_SHADOW,
            PromotionStage.ETHERNIAN_REVIEW,
            PromotionStage.OPERATOR_APPROVED,
            PromotionStage.LIMITED_PROMOTION,
        }:
            raise GovernanceRejected("candidate is not rollback-eligible")
        candidate.stage = PromotionStage.ROLLED_BACK
        self.chain.append("ROLLED_BACK", {"rollback_digest": candidate.rollback_digest})

    @staticmethod
    def _require(candidate: Candidate, expected: PromotionStage) -> None:
        if candidate.stage is not expected:
            raise GovernanceRejected(f"expected stage {expected.value}")

