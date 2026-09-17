"""Metadata-only plans for a synthetic patch draft limited promotion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest
from .patch_draft_promotion_decision_intake import (
    SyntheticPatchDraftPromotionDecision,
)
from .patch_draft_promotion_receipt_ledger import (
    SyntheticPatchDraftPromotionDecisionReceiptLedger,
)


PATCH_DRAFT_LIMITED_PROMOTION_PLAN_STATE = (
    "SYNTHETIC_PATCH_DRAFT_LIMITED_PROMOTION_PLAN_DRAFTED"
)
PATCH_DRAFT_LIMITED_PROMOTION_SCOPE = "SYNTHETIC_FIXTURE_COHORT_ONLY"
MIN_SYNTHETIC_SAMPLE_SIZE = 1
MAX_SYNTHETIC_SAMPLE_SIZE = 100
MIN_OBSERVATION_WINDOW_SECONDS = 60
MAX_OBSERVATION_WINDOW_SECONDS = 3600
REQUIRED_ROLLBACK_TRIGGERS = (
    "ANY_SAFETY_INVARIANT_FAILURE",
    "ANY_EVIDENCE_CHAIN_FAILURE",
    "ANY_SYNTHETIC_REGRESSION",
    "ANY_UNEXPECTED_SIDE_EFFECT",
)
REQUIRED_LIMITED_PROMOTION_CHECKS = (
    "PRESERVE_FAIL_CLOSED_BASELINE",
    "REPRODUCE_SOURCE_SHA256_EVIDENCE",
    "USE_SYNTHETIC_FIXTURES_ONLY",
    "DECLARE_OPAQUE_CANDIDATE_AND_COHORT_DIGESTS_ONLY",
    "CAP_SYNTHETIC_COHORT_AND_OBSERVATION_WINDOW",
    "ROLLBACK_ON_ANY_REQUIRED_TRIGGER",
    "NO_PATCH_CONTENT_OR_DIFF",
    "NO_SOURCE_OR_FILESYSTEM_CHANGE",
    "ETERNIAN_REVIEW_REQUIRED_BEFORE_SYNTHETIC_ACTIVATION",
    "OPERATOR_RECONFIRMATION_REQUIRED_BEFORE_ANY_NON_SYNTHETIC_USE",
)


def _valid_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _valid_limits(sample_size: int, observation_window_seconds: int) -> bool:
    return (
        isinstance(sample_size, int)
        and not isinstance(sample_size, bool)
        and MIN_SYNTHETIC_SAMPLE_SIZE <= sample_size <= MAX_SYNTHETIC_SAMPLE_SIZE
        and isinstance(observation_window_seconds, int)
        and not isinstance(observation_window_seconds, bool)
        and MIN_OBSERVATION_WINDOW_SECONDS
        <= observation_window_seconds
        <= MAX_OBSERVATION_WINDOW_SECONDS
        and observation_window_seconds % 60 == 0
    )


def _plan_id(
    source_receipt_id: str,
    source_receipt_digest: str,
    candidate_digest: str,
    cohort_digest: str,
    synthetic_sample_size: int,
    observation_window_seconds: int,
) -> str:
    identity = canonical_digest(
        {
            "source_receipt_id": source_receipt_id,
            "source_receipt_digest": source_receipt_digest,
            "promotion_scope": PATCH_DRAFT_LIMITED_PROMOTION_SCOPE,
            "candidate_digest": candidate_digest,
            "cohort_digest": cohort_digest,
            "synthetic_sample_size": synthetic_sample_size,
            "observation_window_seconds": observation_window_seconds,
        }
    )
    return "synthetic:patch-draft-limited-promotion-plan:" + identity[:32]


@dataclass(frozen=True)
class SyntheticPatchDraftLimitedPromotionPlan:
    sequence: int
    plan_id: str
    source_receipt_id: str
    source_receipt_digest: str
    source_assessment_id: str
    source_packet_id: str
    operator_id: str
    decision: SyntheticPatchDraftPromotionDecision
    promotion_scope: str
    candidate_digest: str
    cohort_digest: str
    synthetic_sample_size: int
    observation_window_seconds: int
    rollback_triggers: tuple[str, ...]
    required_checks: tuple[str, ...]
    drafted_at: datetime
    previous_digest: str
    plan_digest: str
    state: str = PATCH_DRAFT_LIMITED_PROMOTION_PLAN_STATE
    synthetic_only: bool = True
    rollback_required: bool = True
    eternian_review_required: bool = True
    operator_reconfirmation_required: bool = True
    candidate_content_present: bool = False
    patch_content_present: bool = False
    diff_content_present: bool = False
    source_code_changed: bool = False
    filesystem_written: bool = False
    automatic_application_allowed: bool = False
    safety_baseline_relaxation_allowed: bool = False
    execution_allowed: bool = False
    network_access_allowed: bool = False
    money_movement_allowed: bool = False
    production_activation_allowed: bool = False

    def __post_init__(self) -> None:
        if (
            self.sequence <= 0
            or self.plan_id
            != _plan_id(
                self.source_receipt_id,
                self.source_receipt_digest,
                self.candidate_digest,
                self.cohort_digest,
                self.synthetic_sample_size,
                self.observation_window_seconds,
            )
            or not self.source_receipt_id.startswith(
                "synthetic:patch-draft-promotion-decision-receipt:"
            )
            or not _valid_digest(self.source_receipt_digest)
            or not self.source_assessment_id.startswith(
                "synthetic:patch-draft-promotion-decision-assessment:"
            )
            or not self.source_packet_id.startswith(
                "synthetic:patch-draft-promotion-operator-packet:"
            )
            or self.operator_id != "synthetic:operator:CHOI_IN_SEOK"
            or self.decision
            is not SyntheticPatchDraftPromotionDecision.AUTHORIZE_SYNTHETIC_PATCH_DRAFT_LIMITED_PROMOTION
            or self.promotion_scope != PATCH_DRAFT_LIMITED_PROMOTION_SCOPE
            or not _valid_digest(self.candidate_digest)
            or not _valid_digest(self.cohort_digest)
            or self.candidate_digest == self.cohort_digest
            or not _valid_limits(
                self.synthetic_sample_size, self.observation_window_seconds
            )
            or self.rollback_triggers != REQUIRED_ROLLBACK_TRIGGERS
            or self.required_checks != REQUIRED_LIMITED_PROMOTION_CHECKS
            or self.drafted_at.tzinfo is None
            or not _valid_digest(self.previous_digest)
            or self.state != PATCH_DRAFT_LIMITED_PROMOTION_PLAN_STATE
            or not self.synthetic_only
            or not self.rollback_required
            or not self.eternian_review_required
            or not self.operator_reconfirmation_required
            or any(
                (
                    self.candidate_content_present,
                    self.patch_content_present,
                    self.diff_content_present,
                    self.source_code_changed,
                    self.filesystem_written,
                    self.automatic_application_allowed,
                    self.safety_baseline_relaxation_allowed,
                    self.execution_allowed,
                    self.network_access_allowed,
                    self.money_movement_allowed,
                    self.production_activation_allowed,
                )
            )
            or self.plan_digest != canonical_digest(self.digest_value())
        ):
            raise GovernanceRejected(
                "valid metadata-only synthetic limited promotion plan required"
            )

    def digest_value(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "plan_id": self.plan_id,
            "source_receipt_id": self.source_receipt_id,
            "source_receipt_digest": self.source_receipt_digest,
            "source_assessment_id": self.source_assessment_id,
            "source_packet_id": self.source_packet_id,
            "operator_id": self.operator_id,
            "decision": self.decision.value,
            "promotion_scope": PATCH_DRAFT_LIMITED_PROMOTION_SCOPE,
            "candidate_digest": self.candidate_digest,
            "cohort_digest": self.cohort_digest,
            "synthetic_sample_size": self.synthetic_sample_size,
            "observation_window_seconds": self.observation_window_seconds,
            "rollback_triggers": list(self.rollback_triggers),
            "required_checks": list(self.required_checks),
            "drafted_at": self.drafted_at.isoformat(),
            "previous_digest": self.previous_digest,
            "state": PATCH_DRAFT_LIMITED_PROMOTION_PLAN_STATE,
            "synthetic_only": True,
            "rollback_required": True,
            "eternian_review_required": True,
            "operator_reconfirmation_required": True,
            "candidate_content_present": False,
            "patch_content_present": False,
            "diff_content_present": False,
            "source_code_changed": False,
            "filesystem_written": False,
            "automatic_application_allowed": False,
            "safety_baseline_relaxation_allowed": False,
            "execution_allowed": False,
            "network_access_allowed": False,
            "money_movement_allowed": False,
            "production_activation_allowed": False,
        }


class SyntheticPatchDraftLimitedPromotionPlanBook:
    """Drafts bounded synthetic plans and exposes no activation method."""

    def __init__(self) -> None:
        self._plans: list[SyntheticPatchDraftLimitedPromotionPlan] = []
        self._by_receipt: dict[str, SyntheticPatchDraftLimitedPromotionPlan] = {}
        self._lock = RLock()

    @property
    def plans(self) -> tuple[SyntheticPatchDraftLimitedPromotionPlan, ...]:
        with self._lock:
            return tuple(self._plans)

    def draft_from_receipt(
        self,
        ledger: SyntheticPatchDraftPromotionDecisionReceiptLedger,
        receipt_id: str,
        *,
        candidate_digest: str,
        cohort_digest: str,
        synthetic_sample_size: int,
        observation_window_seconds: int,
        rollback_triggers: tuple[str, ...],
        drafted_at: datetime,
    ) -> SyntheticPatchDraftLimitedPromotionPlan:
        if drafted_at.tzinfo is None:
            raise GovernanceRejected("timezone-aware limited promotion plan required")
        if not isinstance(
            ledger, SyntheticPatchDraftPromotionDecisionReceiptLedger
        ):
            raise GovernanceRejected("typed promotion receipt ledger required")
        if (
            not _valid_digest(candidate_digest)
            or not _valid_digest(cohort_digest)
            or candidate_digest == cohort_digest
        ):
            raise GovernanceRejected("distinct opaque candidate and cohort digests required")
        if not _valid_limits(synthetic_sample_size, observation_window_seconds):
            raise GovernanceRejected("bounded synthetic cohort and window required")
        if rollback_triggers != REQUIRED_ROLLBACK_TRIGGERS:
            raise GovernanceRejected("complete immutable rollback triggers required")
        if (
            not ledger.verify_metadata()
            or not ledger.verify_audit_chain()
            or not ledger.verify_record_bindings()
        ):
            raise GovernanceRejected("intact promotion receipt ledger required")
        before = ledger.evidence()["report_digest"]
        receipt = ledger.get(receipt_id)
        if (
            receipt.decision
            is not SyntheticPatchDraftPromotionDecision.AUTHORIZE_SYNTHETIC_PATCH_DRAFT_LIMITED_PROMOTION
        ):
            raise GovernanceRejected("promotion receipt does not authorize plan drafting")
        if drafted_at < receipt.recorded_at:
            raise GovernanceRejected("limited promotion plan cannot predate receipt")
        source_digest = receipt.receipt_digest()

        with self._lock:
            if not self.verify_plan_chain():
                raise GovernanceRejected("existing limited promotion plan chain is invalid")
            existing = self._by_receipt.get(receipt_id)
            if existing is not None:
                if (
                    existing.source_receipt_digest != source_digest
                    or existing.source_assessment_id != receipt.assessment_id
                    or existing.source_packet_id != receipt.packet_id
                    or existing.operator_id != receipt.operator_id
                    or existing.decision is not receipt.decision
                    or existing.candidate_digest != candidate_digest
                    or existing.cohort_digest != cohort_digest
                    or existing.synthetic_sample_size != synthetic_sample_size
                    or existing.observation_window_seconds
                    != observation_window_seconds
                    or existing.rollback_triggers != rollback_triggers
                ):
                    raise GovernanceRejected("limited promotion plan idempotency mismatch")
                plan = existing
                created = False
            else:
                sequence = len(self._plans) + 1
                previous = self._plans[-1].plan_digest if self._plans else "0" * 64
                plan_id = _plan_id(
                    receipt.receipt_id,
                    source_digest,
                    candidate_digest,
                    cohort_digest,
                    synthetic_sample_size,
                    observation_window_seconds,
                )
                value = {
                    "sequence": sequence,
                    "plan_id": plan_id,
                    "source_receipt_id": receipt.receipt_id,
                    "source_receipt_digest": source_digest,
                    "source_assessment_id": receipt.assessment_id,
                    "source_packet_id": receipt.packet_id,
                    "operator_id": receipt.operator_id,
                    "decision": receipt.decision.value,
                    "promotion_scope": PATCH_DRAFT_LIMITED_PROMOTION_SCOPE,
                    "candidate_digest": candidate_digest,
                    "cohort_digest": cohort_digest,
                    "synthetic_sample_size": synthetic_sample_size,
                    "observation_window_seconds": observation_window_seconds,
                    "rollback_triggers": list(rollback_triggers),
                    "required_checks": list(REQUIRED_LIMITED_PROMOTION_CHECKS),
                    "drafted_at": drafted_at.isoformat(),
                    "previous_digest": previous,
                    "state": PATCH_DRAFT_LIMITED_PROMOTION_PLAN_STATE,
                    "synthetic_only": True,
                    "rollback_required": True,
                    "eternian_review_required": True,
                    "operator_reconfirmation_required": True,
                    "candidate_content_present": False,
                    "patch_content_present": False,
                    "diff_content_present": False,
                    "source_code_changed": False,
                    "filesystem_written": False,
                    "automatic_application_allowed": False,
                    "safety_baseline_relaxation_allowed": False,
                    "execution_allowed": False,
                    "network_access_allowed": False,
                    "money_movement_allowed": False,
                    "production_activation_allowed": False,
                }
                plan = SyntheticPatchDraftLimitedPromotionPlan(
                    sequence,
                    plan_id,
                    receipt.receipt_id,
                    source_digest,
                    receipt.assessment_id,
                    receipt.packet_id,
                    receipt.operator_id,
                    receipt.decision,
                    PATCH_DRAFT_LIMITED_PROMOTION_SCOPE,
                    candidate_digest,
                    cohort_digest,
                    synthetic_sample_size,
                    observation_window_seconds,
                    rollback_triggers,
                    REQUIRED_LIMITED_PROMOTION_CHECKS,
                    drafted_at,
                    previous,
                    canonical_digest(value),
                )
                self._plans.append(plan)
                self._by_receipt[receipt_id] = plan
                created = True

        if before != ledger.evidence()["report_digest"]:
            with self._lock:
                if created and self._by_receipt.get(receipt_id) is plan:
                    self._plans.pop()
                    self._by_receipt.pop(receipt_id, None)
            raise GovernanceRejected("promotion receipt changed during plan drafting")
        return plan

    def verify_plan_chain(self) -> bool:
        with self._lock:
            previous = "0" * 64
            for sequence, plan in enumerate(self._plans, start=1):
                if (
                    plan.sequence != sequence
                    or plan.previous_digest != previous
                    or plan.plan_id
                    != _plan_id(
                        plan.source_receipt_id,
                        plan.source_receipt_digest,
                        plan.candidate_digest,
                        plan.cohort_digest,
                        plan.synthetic_sample_size,
                        plan.observation_window_seconds,
                    )
                    or plan.plan_digest != canonical_digest(plan.digest_value())
                    or plan.state != PATCH_DRAFT_LIMITED_PROMOTION_PLAN_STATE
                    or plan.promotion_scope != PATCH_DRAFT_LIMITED_PROMOTION_SCOPE
                    or not _valid_digest(plan.candidate_digest)
                    or not _valid_digest(plan.cohort_digest)
                    or plan.candidate_digest == plan.cohort_digest
                    or not _valid_limits(
                        plan.synthetic_sample_size,
                        plan.observation_window_seconds,
                    )
                    or plan.rollback_triggers != REQUIRED_ROLLBACK_TRIGGERS
                    or plan.required_checks != REQUIRED_LIMITED_PROMOTION_CHECKS
                    or not plan.synthetic_only
                    or not plan.rollback_required
                    or not plan.eternian_review_required
                    or not plan.operator_reconfirmation_required
                    or any(
                        (
                            plan.candidate_content_present,
                            plan.patch_content_present,
                            plan.diff_content_present,
                            plan.source_code_changed,
                            plan.filesystem_written,
                            plan.automatic_application_allowed,
                            plan.safety_baseline_relaxation_allowed,
                            plan.execution_allowed,
                            plan.network_access_allowed,
                            plan.money_movement_allowed,
                            plan.production_activation_allowed,
                        )
                    )
                ):
                    return False
                previous = plan.plan_digest
            return len(self._by_receipt) == len(self._plans) and all(
                self._by_receipt.get(item.source_receipt_id) is item
                for item in self._plans
            )

    def evidence(self) -> dict[str, object]:
        with self._lock:
            value = {
                "schema": (
                    "nurion.pg.synthetic-patch-draft-limited-promotion-plan-"
                    "evidence.v1"
                ),
                "plan_count": len(self._plans),
                "plan_digests": [item.plan_digest for item in self._plans],
                "plan_chain_valid": self.verify_plan_chain(),
                "maximum_state": PATCH_DRAFT_LIMITED_PROMOTION_PLAN_STATE,
                "promotion_scope": PATCH_DRAFT_LIMITED_PROMOTION_SCOPE,
                "maximum_synthetic_sample_size": MAX_SYNTHETIC_SAMPLE_SIZE,
                "maximum_observation_window_seconds": (
                    MAX_OBSERVATION_WINDOW_SECONDS
                ),
                "synthetic_only": True,
                "rollback_required": True,
                "eternian_review_required": True,
                "operator_reconfirmation_required": True,
                "candidate_content_present": False,
                "patch_content_present": False,
                "diff_content_present": False,
                "source_code_changed": False,
                "filesystem_written": False,
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
