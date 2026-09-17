"""Deterministic synthetic shadow evaluation for reviewed remediation proposals."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest
from .reconciliation_remediation_proposals import RemediationActionType
from .remediation_review_docket import SyntheticRemediationReviewDocket


class ShadowItemDecision(StrEnum):
    PASS = "PASS"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    BLOCKED = "BLOCKED"


class RemediationShadowDecision(StrEnum):
    PROPOSED_FOR_ETERNIAN_REVIEW = "PROPOSED_FOR_ETERNIAN_REVIEW"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class SyntheticRemediationShadowFixture:
    fixture_id: str
    plan_item_digest: str
    action_type: RemediationActionType
    fixture_seed_digest: str
    trigger_observed: bool
    fail_closed_baseline_preserved: bool
    regression_test_passed: bool
    sha256_evidence_reproduced: bool
    eternian_review_retained: bool
    payment_state_changed: bool
    money_movement_executed: bool
    production_access_used: bool
    fixture_digest: str

    def __post_init__(self) -> None:
        boolean_values = (
            self.trigger_observed,
            self.fail_closed_baseline_preserved,
            self.regression_test_passed,
            self.sha256_evidence_reproduced,
            self.eternian_review_retained,
            self.payment_state_changed,
            self.money_movement_executed,
            self.production_access_used,
        )
        if (
            not self.fixture_id.startswith("synthetic:remediation-shadow-fixture:")
            or len(self.fixture_id)
            <= len("synthetic:remediation-shadow-fixture:")
            or not _valid_digest(self.plan_item_digest)
            or not isinstance(self.action_type, RemediationActionType)
            or not _valid_digest(self.fixture_seed_digest)
            or not all(isinstance(value, bool) for value in boolean_values)
            or self.fixture_digest != canonical_digest(self.digest_value())
        ):
            raise GovernanceRejected("valid synthetic remediation shadow fixture required")

    def digest_value(self) -> dict[str, object]:
        return {
            "fixture_id": self.fixture_id,
            "plan_item_digest": self.plan_item_digest,
            "action_type": self.action_type.value,
            "fixture_seed_digest": self.fixture_seed_digest,
            "trigger_observed": self.trigger_observed,
            "fail_closed_baseline_preserved": self.fail_closed_baseline_preserved,
            "regression_test_passed": self.regression_test_passed,
            "sha256_evidence_reproduced": self.sha256_evidence_reproduced,
            "eternian_review_retained": self.eternian_review_retained,
            "payment_state_changed": self.payment_state_changed,
            "money_movement_executed": self.money_movement_executed,
            "production_access_used": self.production_access_used,
        }


@dataclass(frozen=True)
class RemediationShadowItemResult:
    ordinal: int
    plan_item_digest: str
    action_type: RemediationActionType
    fixture_digest: str
    decision: ShadowItemDecision
    reason: str
    result_digest: str

    def __post_init__(self) -> None:
        if (
            self.ordinal <= 0
            or not _valid_digest(self.plan_item_digest)
            or not isinstance(self.action_type, RemediationActionType)
            or not _valid_digest(self.fixture_digest)
            or not isinstance(self.decision, ShadowItemDecision)
            or self.reason not in {
                "all_synthetic_shadow_controls_passed",
                "incomplete_synthetic_shadow_controls",
                "forbidden_shadow_side_effect_detected",
            }
            or self.result_digest != canonical_digest(self.digest_value())
        ):
            raise GovernanceRejected("valid remediation shadow item result required")

    def digest_value(self) -> dict[str, object]:
        return {
            "ordinal": self.ordinal,
            "plan_item_digest": self.plan_item_digest,
            "action_type": self.action_type.value,
            "fixture_digest": self.fixture_digest,
            "decision": self.decision.value,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class RemediationShadowAssessment:
    sequence: int
    proposal_id: str
    proposal_digest: str
    source_review_digest: str
    item_results: tuple[RemediationShadowItemResult, ...]
    decision: RemediationShadowDecision
    reason: str
    evaluated_at: datetime
    previous_digest: str
    assessment_digest: str
    source_docket_state_changed: bool = False
    code_change_allowed: bool = False
    automatic_application_allowed: bool = False
    operator_decision_recorded: bool = False
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if (
            self.sequence <= 0
            or not self.proposal_id.startswith("synthetic:remediation-proposal:")
            or not _valid_digest(self.proposal_digest)
            or not _valid_digest(self.source_review_digest)
            or not self.item_results
            or self.evaluated_at.tzinfo is None
            or not isinstance(self.decision, RemediationShadowDecision)
            or self.reason not in {
                "synthetic_shadow_ready_for_eternian_review",
                "synthetic_shadow_requires_human_review",
                "synthetic_shadow_blocked_by_forbidden_side_effect",
            }
            or not _valid_digest(self.previous_digest)
            or self.source_docket_state_changed
            or self.code_change_allowed
            or self.automatic_application_allowed
            or self.operator_decision_recorded
            or self.execution_allowed
            or self.assessment_digest != canonical_digest(self.digest_value())
        ):
            raise GovernanceRejected("valid non-executing shadow assessment required")

    def digest_value(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "proposal_id": self.proposal_id,
            "proposal_digest": self.proposal_digest,
            "source_review_digest": self.source_review_digest,
            "item_result_digests": [item.result_digest for item in self.item_results],
            "decision": self.decision.value,
            "reason": self.reason,
            "evaluated_at": self.evaluated_at.isoformat(),
            "previous_digest": self.previous_digest,
            "source_docket_state_changed": False,
            "code_change_allowed": False,
            "automatic_application_allowed": False,
            "operator_decision_recorded": False,
            "execution_allowed": False,
        }


def _valid_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


class SyntheticRemediationShadowBook:
    """Evaluates supplied synthetic fixtures without applying a remediation."""

    def __init__(self) -> None:
        self._assessments: list[RemediationShadowAssessment] = []
        self._by_proposal: dict[str, RemediationShadowAssessment] = {}
        self._lock = RLock()

    @property
    def assessments(self) -> tuple[RemediationShadowAssessment, ...]:
        with self._lock:
            return tuple(self._assessments)

    def evaluate(
        self,
        docket: SyntheticRemediationReviewDocket,
        proposal_id: str,
        fixtures: tuple[SyntheticRemediationShadowFixture, ...],
        *,
        evaluated_at: datetime,
    ) -> RemediationShadowAssessment:
        if evaluated_at.tzinfo is None:
            raise GovernanceRejected("timezone-aware synthetic shadow time required")
        if not isinstance(fixtures, tuple) or not fixtures:
            raise GovernanceRejected("one or more synthetic shadow fixtures required")
        if any(not isinstance(item, SyntheticRemediationShadowFixture) for item in fixtures):
            raise GovernanceRejected("typed synthetic shadow fixtures required")
        before = docket.evidence()["report_digest"]
        source = docket.ready_source(proposal_id)
        if evaluated_at < source.reviewed_at:
            raise GovernanceRejected("synthetic shadow cannot predate independent review")
        try:
            proposal = json.loads(source.proposal_json)
        except (TypeError, ValueError) as exc:
            raise GovernanceRejected("ready remediation proposal JSON is invalid") from exc
        plan_items = proposal.get("plan_items") if isinstance(proposal, dict) else None
        if not isinstance(plan_items, list) or not plan_items:
            raise GovernanceRejected("ready remediation proposal plan items required")
        results = self._evaluate_items(plan_items, fixtures)
        decision, reason = self._overall_decision(results)
        fixture_digests = tuple(item.fixture_digest for item in results)
        created = False
        with self._lock:
            existing = self._by_proposal.get(proposal_id)
            if existing is not None:
                existing_fixtures = tuple(
                    item.fixture_digest for item in existing.item_results
                )
                if existing_fixtures != fixture_digests:
                    raise GovernanceRejected("synthetic shadow idempotency payload mismatch")
                assessment = existing
            else:
                previous = (
                    self._assessments[-1].assessment_digest
                    if self._assessments
                    else "0" * 64
                )
                sequence = len(self._assessments) + 1
                value = {
                    "sequence": sequence,
                    "proposal_id": source.proposal_id,
                    "proposal_digest": source.proposal_digest,
                    "source_review_digest": source.review_digest,
                    "item_result_digests": [item.result_digest for item in results],
                    "decision": decision.value,
                    "reason": reason,
                    "evaluated_at": evaluated_at.isoformat(),
                    "previous_digest": previous,
                    "source_docket_state_changed": False,
                    "code_change_allowed": False,
                    "automatic_application_allowed": False,
                    "operator_decision_recorded": False,
                    "execution_allowed": False,
                }
                assessment = RemediationShadowAssessment(
                    sequence,
                    source.proposal_id,
                    source.proposal_digest,
                    source.review_digest,
                    results,
                    decision,
                    reason,
                    evaluated_at,
                    previous,
                    canonical_digest(value),
                )
                self._assessments.append(assessment)
                self._by_proposal[proposal_id] = assessment
                created = True
        after = docket.evidence()["report_digest"]
        if before != after:
            if created:
                with self._lock:
                    self._assessments.pop()
                    self._by_proposal.pop(proposal_id, None)
            raise GovernanceRejected("source remediation docket changed during shadow")
        return assessment

    @staticmethod
    def _evaluate_items(
        plan_items: list[object],
        fixtures: tuple[SyntheticRemediationShadowFixture, ...],
    ) -> tuple[RemediationShadowItemResult, ...]:
        by_digest: dict[str, SyntheticRemediationShadowFixture] = {}
        for fixture in fixtures:
            if fixture.fixture_digest != canonical_digest(fixture.digest_value()):
                raise GovernanceRejected("synthetic shadow fixture digest mismatch")
            if fixture.plan_item_digest in by_digest:
                raise GovernanceRejected("duplicate synthetic shadow fixture")
            by_digest[fixture.plan_item_digest] = fixture
        expected = {
            str(item.get("item_digest"))
            for item in plan_items
            if isinstance(item, dict)
        }
        if len(expected) != len(plan_items) or set(by_digest) != expected:
            raise GovernanceRejected("exactly one fixture per remediation plan item required")
        results = []
        for item in sorted(plan_items, key=lambda value: int(value["ordinal"])):
            if not isinstance(item, dict):
                raise GovernanceRejected("structured remediation plan item required")
            fixture = by_digest[str(item["item_digest"])]
            action_type = RemediationActionType(str(item["action_type"]))
            if fixture.action_type is not action_type:
                raise GovernanceRejected("shadow fixture action binding mismatch")
            forbidden = (
                fixture.payment_state_changed
                or fixture.money_movement_executed
                or fixture.production_access_used
            )
            complete = all(
                (
                    fixture.trigger_observed,
                    fixture.fail_closed_baseline_preserved,
                    fixture.regression_test_passed,
                    fixture.sha256_evidence_reproduced,
                    fixture.eternian_review_retained,
                )
            )
            if forbidden:
                decision = ShadowItemDecision.BLOCKED
                reason = "forbidden_shadow_side_effect_detected"
            elif not complete:
                decision = ShadowItemDecision.HUMAN_REVIEW
                reason = "incomplete_synthetic_shadow_controls"
            else:
                decision = ShadowItemDecision.PASS
                reason = "all_synthetic_shadow_controls_passed"
            value = {
                "ordinal": int(item["ordinal"]),
                "plan_item_digest": fixture.plan_item_digest,
                "action_type": action_type.value,
                "fixture_digest": fixture.fixture_digest,
                "decision": decision.value,
                "reason": reason,
            }
            results.append(
                RemediationShadowItemResult(
                    int(item["ordinal"]),
                    fixture.plan_item_digest,
                    action_type,
                    fixture.fixture_digest,
                    decision,
                    reason,
                    canonical_digest(value),
                )
            )
        return tuple(results)

    @staticmethod
    def _overall_decision(
        results: tuple[RemediationShadowItemResult, ...],
    ) -> tuple[RemediationShadowDecision, str]:
        decisions = {item.decision for item in results}
        if ShadowItemDecision.BLOCKED in decisions:
            return (
                RemediationShadowDecision.BLOCKED,
                "synthetic_shadow_blocked_by_forbidden_side_effect",
            )
        if ShadowItemDecision.HUMAN_REVIEW in decisions:
            return (
                RemediationShadowDecision.HUMAN_REVIEW,
                "synthetic_shadow_requires_human_review",
            )
        return (
            RemediationShadowDecision.PROPOSED_FOR_ETERNIAN_REVIEW,
            "synthetic_shadow_ready_for_eternian_review",
        )

    def verify_assessment_chain(self) -> bool:
        with self._lock:
            previous = "0" * 64
            for sequence, assessment in enumerate(self._assessments, start=1):
                try:
                    result_valid = all(
                        item.result_digest == canonical_digest(item.digest_value())
                        and item.reason
                        == {
                            ShadowItemDecision.PASS:
                                "all_synthetic_shadow_controls_passed",
                            ShadowItemDecision.HUMAN_REVIEW:
                                "incomplete_synthetic_shadow_controls",
                            ShadowItemDecision.BLOCKED:
                                "forbidden_shadow_side_effect_detected",
                        }[item.decision]
                        for item in assessment.item_results
                    )
                    expected_decision, expected_reason = self._overall_decision(
                        assessment.item_results
                    )
                except (GovernanceRejected, TypeError, ValueError):
                    return False
                if (
                    assessment.sequence != sequence
                    or assessment.previous_digest != previous
                    or not result_valid
                    or assessment.decision is not expected_decision
                    or assessment.reason != expected_reason
                    or assessment.assessment_digest
                    != canonical_digest(assessment.digest_value())
                    or assessment.source_docket_state_changed
                    or assessment.code_change_allowed
                    or assessment.automatic_application_allowed
                    or assessment.operator_decision_recorded
                    or assessment.execution_allowed
                ):
                    return False
                previous = assessment.assessment_digest
            return True

    def evidence(self) -> dict[str, object]:
        with self._lock:
            counts = {decision.value: 0 for decision in RemediationShadowDecision}
            digests = []
            for assessment in self._assessments:
                counts[assessment.decision.value] += 1
                digests.append(assessment.assessment_digest)
            value = {
                "schema": "nurion.pg.synthetic-remediation-shadow-evidence.v1",
                "decision_counts": counts,
                "assessment_digests": digests,
                "assessment_chain_valid": self.verify_assessment_chain(),
                "maximum_decision": "PROPOSED_FOR_ETERNIAN_REVIEW",
                "source_docket_state_changed": False,
                "code_change_method_present": False,
                "application_method_present": False,
                "operator_decision_method_present": False,
                "execution_method_present": False,
                "payment_state_changed": False,
                "money_movement_executed": False,
                "production_activation_allowed": False,
            }
            return {**value, "report_digest": canonical_digest(value)}
