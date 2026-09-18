"""Synthetic shadow evaluation for reviewed patch draft promotion plans."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest
from .synthetic_patch_draft_limited_promotion_review_docket import (
    SyntheticPatchDraftLimitedPromotionReviewDocket,
)


MAXIMUM_LIMITED_PROMOTION_SHADOW_DECISION = "PROPOSED_FOR_ETERNIAN_REVIEW"
REQUIRED_ROLLBACK_TRIGGERS = (
    "ANY_SAFETY_INVARIANT_FAILURE",
    "ANY_EVIDENCE_CHAIN_FAILURE",
    "ANY_SYNTHETIC_REGRESSION",
    "ANY_UNEXPECTED_SIDE_EFFECT",
)


class LimitedPromotionShadowItemDecision(StrEnum):
    PASS = "PASS"
    ROLLBACK_REQUIRED = "ROLLBACK_REQUIRED"


class LimitedPromotionShadowDecision(StrEnum):
    PROPOSED_FOR_ETERNIAN_REVIEW = "PROPOSED_FOR_ETERNIAN_REVIEW"
    ROLLBACK_REQUIRED = "ROLLBACK_REQUIRED"


def _valid_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _valid_prefixed(value: object, prefix: str) -> bool:
    return isinstance(value, str) and value.startswith(prefix) and len(value) > len(prefix)


@dataclass(frozen=True)
class SyntheticPatchDraftLimitedPromotionObservation:
    ordinal: int
    observation_id: str
    plan_id: str
    plan_digest: str
    candidate_digest: str
    cohort_digest: str
    synthetic_input_only: bool
    plan_binding_verified: bool
    candidate_binding_verified: bool
    cohort_binding_verified: bool
    safety_invariants_passed: bool
    evidence_chain_passed: bool
    synthetic_regression_detected: bool
    unexpected_side_effect_detected: bool
    rollback_trigger_evaluated: bool
    candidate_content_present: bool
    patch_content_present: bool
    diff_content_present: bool
    source_code_changed: bool
    filesystem_written: bool
    network_access_used: bool
    production_access_used: bool
    credentials_used: bool
    personal_data_used: bool
    money_movement_executed: bool
    observation_digest: str

    def __post_init__(self) -> None:
        booleans = (
            self.synthetic_input_only,
            self.plan_binding_verified,
            self.candidate_binding_verified,
            self.cohort_binding_verified,
            self.safety_invariants_passed,
            self.evidence_chain_passed,
            self.synthetic_regression_detected,
            self.unexpected_side_effect_detected,
            self.rollback_trigger_evaluated,
            self.candidate_content_present,
            self.patch_content_present,
            self.diff_content_present,
            self.source_code_changed,
            self.filesystem_written,
            self.network_access_used,
            self.production_access_used,
            self.credentials_used,
            self.personal_data_used,
            self.money_movement_executed,
        )
        if (
            self.ordinal <= 0
            or not _valid_prefixed(
                self.observation_id,
                "synthetic:patch-draft-limited-promotion-observation:",
            )
            or not _valid_prefixed(
                self.plan_id,
                "synthetic:patch-draft-limited-promotion-plan:",
            )
            or not _valid_digest(self.plan_digest)
            or not _valid_digest(self.candidate_digest)
            or not _valid_digest(self.cohort_digest)
            or self.candidate_digest == self.cohort_digest
            or not all(isinstance(value, bool) for value in booleans)
            or self.observation_digest != canonical_digest(self.digest_value())
        ):
            raise GovernanceRejected(
                "valid synthetic limited promotion observation required"
            )

    def digest_value(self) -> dict[str, object]:
        return {
            "ordinal": self.ordinal,
            "observation_id": self.observation_id,
            "plan_id": self.plan_id,
            "plan_digest": self.plan_digest,
            "candidate_digest": self.candidate_digest,
            "cohort_digest": self.cohort_digest,
            "synthetic_input_only": self.synthetic_input_only,
            "plan_binding_verified": self.plan_binding_verified,
            "candidate_binding_verified": self.candidate_binding_verified,
            "cohort_binding_verified": self.cohort_binding_verified,
            "safety_invariants_passed": self.safety_invariants_passed,
            "evidence_chain_passed": self.evidence_chain_passed,
            "synthetic_regression_detected": self.synthetic_regression_detected,
            "unexpected_side_effect_detected": (
                self.unexpected_side_effect_detected
            ),
            "rollback_trigger_evaluated": self.rollback_trigger_evaluated,
            "candidate_content_present": self.candidate_content_present,
            "patch_content_present": self.patch_content_present,
            "diff_content_present": self.diff_content_present,
            "source_code_changed": self.source_code_changed,
            "filesystem_written": self.filesystem_written,
            "network_access_used": self.network_access_used,
            "production_access_used": self.production_access_used,
            "credentials_used": self.credentials_used,
            "personal_data_used": self.personal_data_used,
            "money_movement_executed": self.money_movement_executed,
        }


@dataclass(frozen=True)
class SyntheticPatchDraftLimitedPromotionObservationResult:
    ordinal: int
    observation_id: str
    observation_digest: str
    decision: LimitedPromotionShadowItemDecision
    triggered_rollback_conditions: tuple[str, ...]
    reason: str
    result_digest: str

    def __post_init__(self) -> None:
        if (
            self.ordinal <= 0
            or not _valid_prefixed(
                self.observation_id,
                "synthetic:patch-draft-limited-promotion-observation:",
            )
            or not _valid_digest(self.observation_digest)
            or not isinstance(self.decision, LimitedPromotionShadowItemDecision)
            or self.reason not in {
                "all_limited_promotion_shadow_controls_passed",
                "limited_promotion_rollback_triggered",
            }
            or (
                self.decision is LimitedPromotionShadowItemDecision.PASS
                and (
                    self.triggered_rollback_conditions
                    or self.reason
                    != "all_limited_promotion_shadow_controls_passed"
                )
            )
            or (
                self.decision
                is LimitedPromotionShadowItemDecision.ROLLBACK_REQUIRED
                and (
                    not self.triggered_rollback_conditions
                    or self.reason != "limited_promotion_rollback_triggered"
                )
            )
            or len(self.triggered_rollback_conditions)
            != len(set(self.triggered_rollback_conditions))
            or self.triggered_rollback_conditions
            != tuple(
                item
                for item in REQUIRED_ROLLBACK_TRIGGERS
                if item in self.triggered_rollback_conditions
            )
            or self.result_digest != canonical_digest(self.digest_value())
        ):
            raise GovernanceRejected(
                "valid synthetic limited promotion observation result required"
            )

    def digest_value(self) -> dict[str, object]:
        return {
            "ordinal": self.ordinal,
            "observation_id": self.observation_id,
            "observation_digest": self.observation_digest,
            "decision": self.decision.value,
            "triggered_rollback_conditions": list(
                self.triggered_rollback_conditions
            ),
            "reason": self.reason,
        }


def _shadow_id(
    plan_id: str,
    plan_digest: str,
    source_review_digest: str,
    observation_digests: tuple[str, ...],
) -> str:
    identity = canonical_digest(
        {
            "plan_id": plan_id,
            "plan_digest": plan_digest,
            "source_review_digest": source_review_digest,
            "observation_digests": list(observation_digests),
        }
    )
    return "synthetic:patch-draft-limited-promotion-shadow:" + identity[:32]


@dataclass(frozen=True)
class SyntheticPatchDraftLimitedPromotionShadowAssessment:
    sequence: int
    shadow_id: str
    plan_id: str
    plan_digest: str
    source_review_digest: str
    candidate_digest: str
    cohort_digest: str
    synthetic_sample_size: int
    observation_window_seconds: int
    item_results: tuple[
        SyntheticPatchDraftLimitedPromotionObservationResult, ...
    ]
    decision: LimitedPromotionShadowDecision
    reason: str
    evaluated_at: datetime
    previous_digest: str
    assessment_digest: str
    source_docket_state_changed: bool = False
    candidate_content_present: bool = False
    patch_content_present: bool = False
    diff_content_present: bool = False
    source_code_changed: bool = False
    filesystem_written: bool = False
    automatic_application_allowed: bool = False
    safety_baseline_relaxation_allowed: bool = False
    execution_allowed: bool = False
    synthetic_activation_allowed: bool = False
    network_access_allowed: bool = False
    money_movement_allowed: bool = False
    production_activation_allowed: bool = False

    def __post_init__(self) -> None:
        if (
            self.sequence <= 0
            or self.shadow_id
            != _shadow_id(
                self.plan_id,
                self.plan_digest,
                self.source_review_digest,
                tuple(item.observation_digest for item in self.item_results),
            )
            or not _valid_prefixed(
                self.plan_id,
                "synthetic:patch-draft-limited-promotion-plan:",
            )
            or not _valid_digest(self.plan_digest)
            or not _valid_digest(self.source_review_digest)
            or not _valid_digest(self.candidate_digest)
            or not _valid_digest(self.cohort_digest)
            or self.candidate_digest == self.cohort_digest
            or self.synthetic_sample_size <= 0
            or len(self.item_results) != self.synthetic_sample_size
            or any(
                not isinstance(
                    item,
                    SyntheticPatchDraftLimitedPromotionObservationResult,
                )
                for item in self.item_results
            )
            or tuple(item.ordinal for item in self.item_results)
            != tuple(range(1, self.synthetic_sample_size + 1))
            or len({item.observation_id for item in self.item_results})
            != len(self.item_results)
            or len({item.observation_digest for item in self.item_results})
            != len(self.item_results)
            or any(
                item.result_digest != canonical_digest(item.digest_value())
                for item in self.item_results
            )
            or self.observation_window_seconds <= 0
            or not isinstance(self.decision, LimitedPromotionShadowDecision)
            or self.reason not in {
                "limited_promotion_shadow_ready_for_eternian_review",
                "limited_promotion_shadow_requires_rollback",
            }
            or (
                self.decision
                is LimitedPromotionShadowDecision.PROPOSED_FOR_ETERNIAN_REVIEW
                and (
                    self.reason
                    != "limited_promotion_shadow_ready_for_eternian_review"
                    or any(
                        item.decision
                        is not LimitedPromotionShadowItemDecision.PASS
                        for item in self.item_results
                    )
                )
            )
            or (
                self.decision is LimitedPromotionShadowDecision.ROLLBACK_REQUIRED
                and (
                    self.reason != "limited_promotion_shadow_requires_rollback"
                    or all(
                        item.decision
                        is LimitedPromotionShadowItemDecision.PASS
                        for item in self.item_results
                    )
                )
            )
            or self.evaluated_at.tzinfo is None
            or not _valid_digest(self.previous_digest)
            or any(
                (
                    self.source_docket_state_changed,
                    self.candidate_content_present,
                    self.patch_content_present,
                    self.diff_content_present,
                    self.source_code_changed,
                    self.filesystem_written,
                    self.automatic_application_allowed,
                    self.safety_baseline_relaxation_allowed,
                    self.execution_allowed,
                    self.synthetic_activation_allowed,
                    self.network_access_allowed,
                    self.money_movement_allowed,
                    self.production_activation_allowed,
                )
            )
            or self.assessment_digest != canonical_digest(self.digest_value())
        ):
            raise GovernanceRejected(
                "valid non-activating synthetic limited promotion shadow required"
            )

    def digest_value(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "shadow_id": self.shadow_id,
            "plan_id": self.plan_id,
            "plan_digest": self.plan_digest,
            "source_review_digest": self.source_review_digest,
            "candidate_digest": self.candidate_digest,
            "cohort_digest": self.cohort_digest,
            "synthetic_sample_size": self.synthetic_sample_size,
            "observation_window_seconds": self.observation_window_seconds,
            "item_result_digests": [
                item.result_digest for item in self.item_results
            ],
            "decision": self.decision.value,
            "reason": self.reason,
            "evaluated_at": self.evaluated_at.isoformat(),
            "previous_digest": self.previous_digest,
            "source_docket_state_changed": False,
            "candidate_content_present": False,
            "patch_content_present": False,
            "diff_content_present": False,
            "source_code_changed": False,
            "filesystem_written": False,
            "automatic_application_allowed": False,
            "safety_baseline_relaxation_allowed": False,
            "execution_allowed": False,
            "synthetic_activation_allowed": False,
            "network_access_allowed": False,
            "money_movement_allowed": False,
            "production_activation_allowed": False,
        }


class SyntheticPatchDraftLimitedPromotionShadowBook:
    """Evaluates precomputed synthetic observations without activating a candidate."""

    def __init__(self) -> None:
        self._assessments: list[
            SyntheticPatchDraftLimitedPromotionShadowAssessment
        ] = []
        self._by_plan: dict[
            str, SyntheticPatchDraftLimitedPromotionShadowAssessment
        ] = {}
        self._lock = RLock()

    @property
    def assessments(
        self,
    ) -> tuple[SyntheticPatchDraftLimitedPromotionShadowAssessment, ...]:
        with self._lock:
            return tuple(self._assessments)

    def evaluate(
        self,
        docket: SyntheticPatchDraftLimitedPromotionReviewDocket,
        plan_id: str,
        observations: tuple[
            SyntheticPatchDraftLimitedPromotionObservation, ...
        ],
        *,
        evaluated_at: datetime,
    ) -> SyntheticPatchDraftLimitedPromotionShadowAssessment:
        if evaluated_at.tzinfo is None:
            raise GovernanceRejected(
                "timezone-aware limited promotion shadow time required"
            )
        if not isinstance(
            docket, SyntheticPatchDraftLimitedPromotionReviewDocket
        ):
            raise GovernanceRejected(
                "typed limited promotion review docket required"
            )
        if not isinstance(observations, tuple) or not observations:
            raise GovernanceRejected("synthetic observations required")
        if any(
            not isinstance(
                item, SyntheticPatchDraftLimitedPromotionObservation
            )
            for item in observations
        ):
            raise GovernanceRejected("typed synthetic observations required")

        before = docket.evidence()["report_digest"]
        source = docket.ready_source(plan_id)
        if source.reviewed_at is None or source.review_digest is None:
            raise GovernanceRejected("completed Eternian plan review required")
        if evaluated_at < source.reviewed_at:
            raise GovernanceRejected("shadow cannot predate plan review")
        plan = source.plan
        self._validate_observation_set(plan, observations)
        results = tuple(self._evaluate_item(item) for item in observations)
        if all(
            item.decision is LimitedPromotionShadowItemDecision.PASS
            for item in results
        ):
            decision = LimitedPromotionShadowDecision.PROPOSED_FOR_ETERNIAN_REVIEW
            reason = "limited_promotion_shadow_ready_for_eternian_review"
        else:
            decision = LimitedPromotionShadowDecision.ROLLBACK_REQUIRED
            reason = "limited_promotion_shadow_requires_rollback"
        observation_digests = tuple(
            item.observation_digest for item in results
        )

        with self._lock:
            created = False
            existing = self._by_plan.get(plan_id)
            if existing is not None:
                if (
                    tuple(
                        item.observation_digest
                        for item in existing.item_results
                    )
                    != observation_digests
                    or existing.plan_digest != plan.plan_digest
                    or existing.source_review_digest != source.review_digest
                    or existing.candidate_digest != plan.candidate_digest
                    or existing.cohort_digest != plan.cohort_digest
                ):
                    raise GovernanceRejected(
                        "limited promotion shadow idempotency mismatch"
                    )
                if not self.verify_assessment_chain():
                    raise GovernanceRejected(
                        "existing limited promotion shadow is invalid"
                    )
                assessment = existing
            else:
                sequence = len(self._assessments) + 1
                previous = (
                    self._assessments[-1].assessment_digest
                    if self._assessments
                    else "0" * 64
                )
                shadow_id = _shadow_id(
                    plan.plan_id,
                    plan.plan_digest,
                    source.review_digest,
                    observation_digests,
                )
                value = {
                    "sequence": sequence,
                    "shadow_id": shadow_id,
                    "plan_id": plan.plan_id,
                    "plan_digest": plan.plan_digest,
                    "source_review_digest": source.review_digest,
                    "candidate_digest": plan.candidate_digest,
                    "cohort_digest": plan.cohort_digest,
                    "synthetic_sample_size": plan.synthetic_sample_size,
                    "observation_window_seconds": (
                        plan.observation_window_seconds
                    ),
                    "item_result_digests": [
                        item.result_digest for item in results
                    ],
                    "decision": decision.value,
                    "reason": reason,
                    "evaluated_at": evaluated_at.isoformat(),
                    "previous_digest": previous,
                    "source_docket_state_changed": False,
                    "candidate_content_present": False,
                    "patch_content_present": False,
                    "diff_content_present": False,
                    "source_code_changed": False,
                    "filesystem_written": False,
                    "automatic_application_allowed": False,
                    "safety_baseline_relaxation_allowed": False,
                    "execution_allowed": False,
                    "synthetic_activation_allowed": False,
                    "network_access_allowed": False,
                    "money_movement_allowed": False,
                    "production_activation_allowed": False,
                }
                assessment = (
                    SyntheticPatchDraftLimitedPromotionShadowAssessment(
                        sequence,
                        shadow_id,
                        plan.plan_id,
                        plan.plan_digest,
                        source.review_digest,
                        plan.candidate_digest,
                        plan.cohort_digest,
                        plan.synthetic_sample_size,
                        plan.observation_window_seconds,
                        results,
                        decision,
                        reason,
                        evaluated_at,
                        previous,
                        canonical_digest(value),
                    )
                )
                self._assessments.append(assessment)
                self._by_plan[plan_id] = assessment
                created = True

        if before != docket.evidence()["report_digest"]:
            with self._lock:
                if created and self._by_plan.get(plan_id) is assessment:
                    self._assessments.pop()
                    self._by_plan.pop(plan_id, None)
            raise GovernanceRejected(
                "limited promotion review changed during shadow evaluation"
            )
        return assessment

    @staticmethod
    def _validate_observation_set(plan, observations) -> None:
        if len(observations) != plan.synthetic_sample_size:
            raise GovernanceRejected(
                "observation count must equal synthetic cohort size"
            )
        if tuple(item.ordinal for item in observations) != tuple(
            range(1, plan.synthetic_sample_size + 1)
        ):
            raise GovernanceRejected("ordered observation ordinals required")
        if len({item.observation_id for item in observations}) != len(
            observations
        ) or len({item.observation_digest for item in observations}) != len(
            observations
        ):
            raise GovernanceRejected("unique synthetic observations required")
        for item in observations:
            if (
                item.observation_digest
                != canonical_digest(item.digest_value())
                or item.plan_id != plan.plan_id
                or item.plan_digest != plan.plan_digest
                or item.candidate_digest != plan.candidate_digest
                or item.cohort_digest != plan.cohort_digest
            ):
                raise GovernanceRejected(
                    "observation is not bound to reviewed promotion plan"
                )

    @staticmethod
    def _evaluate_item(
        observation: SyntheticPatchDraftLimitedPromotionObservation,
    ) -> SyntheticPatchDraftLimitedPromotionObservationResult:
        triggers = []
        if not observation.safety_invariants_passed:
            triggers.append("ANY_SAFETY_INVARIANT_FAILURE")
        if not observation.evidence_chain_passed:
            triggers.append("ANY_EVIDENCE_CHAIN_FAILURE")
        if observation.synthetic_regression_detected:
            triggers.append("ANY_SYNTHETIC_REGRESSION")
        forbidden_side_effect = any(
            (
                observation.unexpected_side_effect_detected,
                not observation.synthetic_input_only,
                not observation.plan_binding_verified,
                not observation.candidate_binding_verified,
                not observation.cohort_binding_verified,
                not observation.rollback_trigger_evaluated,
                observation.candidate_content_present,
                observation.patch_content_present,
                observation.diff_content_present,
                observation.source_code_changed,
                observation.filesystem_written,
                observation.network_access_used,
                observation.production_access_used,
                observation.credentials_used,
                observation.personal_data_used,
                observation.money_movement_executed,
            )
        )
        if forbidden_side_effect:
            triggers.append("ANY_UNEXPECTED_SIDE_EFFECT")
        triggered = tuple(triggers)
        if triggered:
            decision = LimitedPromotionShadowItemDecision.ROLLBACK_REQUIRED
            reason = "limited_promotion_rollback_triggered"
        else:
            decision = LimitedPromotionShadowItemDecision.PASS
            reason = "all_limited_promotion_shadow_controls_passed"
        value = {
            "ordinal": observation.ordinal,
            "observation_id": observation.observation_id,
            "observation_digest": observation.observation_digest,
            "decision": decision.value,
            "triggered_rollback_conditions": list(triggered),
            "reason": reason,
        }
        return SyntheticPatchDraftLimitedPromotionObservationResult(
            observation.ordinal,
            observation.observation_id,
            observation.observation_digest,
            decision,
            triggered,
            reason,
            canonical_digest(value),
        )

    def verify_assessment_chain(self) -> bool:
        with self._lock:
            previous = "0" * 64
            for sequence, assessment in enumerate(
                self._assessments, start=1
            ):
                if (
                    assessment.sequence != sequence
                    or assessment.previous_digest != previous
                    or assessment.shadow_id
                    != _shadow_id(
                        assessment.plan_id,
                        assessment.plan_digest,
                        assessment.source_review_digest,
                        tuple(
                            item.observation_digest
                            for item in assessment.item_results
                        ),
                    )
                    or assessment.assessment_digest
                    != canonical_digest(assessment.digest_value())
                    or len(assessment.item_results)
                    != assessment.synthetic_sample_size
                    or tuple(
                        item.ordinal for item in assessment.item_results
                    )
                    != tuple(range(1, assessment.synthetic_sample_size + 1))
                    or len(
                        {
                            item.observation_digest
                            for item in assessment.item_results
                        }
                    )
                    != len(assessment.item_results)
                    or any(
                        item.result_digest
                        != canonical_digest(item.digest_value())
                        for item in assessment.item_results
                    )
                    or (
                        assessment.decision
                        is LimitedPromotionShadowDecision
                        .PROPOSED_FOR_ETERNIAN_REVIEW
                        and any(
                            item.decision
                            is not LimitedPromotionShadowItemDecision.PASS
                            for item in assessment.item_results
                        )
                    )
                    or (
                        assessment.decision
                        is LimitedPromotionShadowDecision.ROLLBACK_REQUIRED
                        and all(
                            item.decision
                            is LimitedPromotionShadowItemDecision.PASS
                            for item in assessment.item_results
                        )
                    )
                    or any(
                        (
                            assessment.source_docket_state_changed,
                            assessment.candidate_content_present,
                            assessment.patch_content_present,
                            assessment.diff_content_present,
                            assessment.source_code_changed,
                            assessment.filesystem_written,
                            assessment.automatic_application_allowed,
                            assessment.safety_baseline_relaxation_allowed,
                            assessment.execution_allowed,
                            assessment.synthetic_activation_allowed,
                            assessment.network_access_allowed,
                            assessment.money_movement_allowed,
                            assessment.production_activation_allowed,
                        )
                    )
                ):
                    return False
                previous = assessment.assessment_digest
            return len(self._by_plan) == len(self._assessments) and all(
                self._by_plan.get(item.plan_id) is item
                for item in self._assessments
            )

    def evidence(self) -> dict[str, object]:
        with self._lock:
            counts = {
                decision.value: 0 for decision in LimitedPromotionShadowDecision
            }
            for assessment in self._assessments:
                counts[assessment.decision.value] += 1
            value = {
                "schema": (
                    "nurion.pg.synthetic-patch-draft-limited-promotion-shadow-"
                    "evidence.v1"
                ),
                "assessment_count": len(self._assessments),
                "assessment_digests": [
                    item.assessment_digest for item in self._assessments
                ],
                "decision_counts": counts,
                "assessment_chain_valid": self.verify_assessment_chain(),
                "maximum_decision": MAXIMUM_LIMITED_PROMOTION_SHADOW_DECISION,
                "source_docket_state_changed": False,
                "candidate_content_present": False,
                "patch_content_present": False,
                "diff_content_present": False,
                "source_code_changed": False,
                "filesystem_written": False,
                "application_method_present": False,
                "safety_baseline_relaxation_method_present": False,
                "execution_method_present": False,
                "synthetic_activation_allowed": False,
                "network_access_method_present": False,
                "personal_data_used": False,
                "credentials_used": False,
                "money_movement_executed": False,
                "production_activation_allowed": False,
            }
            return {**value, "report_digest": canonical_digest(value)}
