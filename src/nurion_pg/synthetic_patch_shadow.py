"""Synthetic-only patch shadow evaluation for reviewed implementation proposals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest
from .synthetic_implementation_review_docket import (
    SyntheticImplementationReviewDocket,
)


MAXIMUM_PATCH_SHADOW_DECISION = "PROPOSED_FOR_ETERNIAN_REVIEW"


class PatchShadowItemDecision(StrEnum):
    PASS = "PASS"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    BLOCKED = "BLOCKED"


class PatchShadowDecision(StrEnum):
    PROPOSED_FOR_ETERNIAN_REVIEW = "PROPOSED_FOR_ETERNIAN_REVIEW"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class SyntheticPatchShadowFixture:
    fixture_id: str
    proposal_id: str
    proposal_digest: str
    draft_scope: str
    base_snapshot_digest: str
    candidate_patch_digest: str
    synthetic_input_only: bool
    expected_change_observed: bool
    fail_closed_baseline_preserved: bool
    regression_test_passed: bool
    concurrency_failure_tests_passed: bool
    sha256_evidence_reproduced: bool
    eternian_review_retained: bool
    source_code_changed: bool
    filesystem_written: bool
    network_access_used: bool
    production_access_used: bool
    credentials_used: bool
    personal_data_used: bool
    money_movement_executed: bool
    fixture_digest: str

    def __post_init__(self) -> None:
        booleans = (
            self.synthetic_input_only,
            self.expected_change_observed,
            self.fail_closed_baseline_preserved,
            self.regression_test_passed,
            self.concurrency_failure_tests_passed,
            self.sha256_evidence_reproduced,
            self.eternian_review_retained,
            self.source_code_changed,
            self.filesystem_written,
            self.network_access_used,
            self.production_access_used,
            self.credentials_used,
            self.personal_data_used,
            self.money_movement_executed,
        )
        if (
            not _valid_prefixed(self.fixture_id, "synthetic:patch-shadow-fixture:")
            or not _valid_prefixed(
                self.proposal_id, "synthetic:implementation-proposal-draft:"
            )
            or not _valid_digest(self.proposal_digest)
            or not self.draft_scope.endswith("_DRAFT_ONLY")
            or not _valid_digest(self.base_snapshot_digest)
            or not _valid_digest(self.candidate_patch_digest)
            or not all(isinstance(value, bool) for value in booleans)
            or self.fixture_digest != canonical_digest(self.digest_value())
        ):
            raise GovernanceRejected("valid synthetic patch shadow fixture required")

    def digest_value(self) -> dict[str, object]:
        return {
            "fixture_id": self.fixture_id,
            "proposal_id": self.proposal_id,
            "proposal_digest": self.proposal_digest,
            "draft_scope": self.draft_scope,
            "base_snapshot_digest": self.base_snapshot_digest,
            "candidate_patch_digest": self.candidate_patch_digest,
            "synthetic_input_only": self.synthetic_input_only,
            "expected_change_observed": self.expected_change_observed,
            "fail_closed_baseline_preserved": self.fail_closed_baseline_preserved,
            "regression_test_passed": self.regression_test_passed,
            "concurrency_failure_tests_passed": (
                self.concurrency_failure_tests_passed
            ),
            "sha256_evidence_reproduced": self.sha256_evidence_reproduced,
            "eternian_review_retained": self.eternian_review_retained,
            "source_code_changed": self.source_code_changed,
            "filesystem_written": self.filesystem_written,
            "network_access_used": self.network_access_used,
            "production_access_used": self.production_access_used,
            "credentials_used": self.credentials_used,
            "personal_data_used": self.personal_data_used,
            "money_movement_executed": self.money_movement_executed,
        }


@dataclass(frozen=True)
class SyntheticPatchShadowItemResult:
    ordinal: int
    draft_scope: str
    fixture_digest: str
    decision: PatchShadowItemDecision
    reason: str
    result_digest: str

    def __post_init__(self) -> None:
        if (
            self.ordinal <= 0
            or not self.draft_scope.endswith("_DRAFT_ONLY")
            or not _valid_digest(self.fixture_digest)
            or not isinstance(self.decision, PatchShadowItemDecision)
            or self.reason not in {
                "all_patch_shadow_controls_passed",
                "incomplete_patch_shadow_controls",
                "forbidden_patch_shadow_side_effect_detected",
            }
            or self.result_digest != canonical_digest(self.digest_value())
        ):
            raise GovernanceRejected("valid synthetic patch shadow result required")

    def digest_value(self) -> dict[str, object]:
        return {
            "ordinal": self.ordinal,
            "draft_scope": self.draft_scope,
            "fixture_digest": self.fixture_digest,
            "decision": self.decision.value,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class SyntheticPatchShadowAssessment:
    sequence: int
    shadow_id: str
    proposal_id: str
    proposal_digest: str
    source_review_digest: str
    item_results: tuple[SyntheticPatchShadowItemResult, ...]
    decision: PatchShadowDecision
    reason: str
    evaluated_at: datetime
    previous_digest: str
    assessment_digest: str
    source_docket_state_changed: bool = False
    patch_content_present: bool = False
    code_change_allowed: bool = False
    automatic_application_allowed: bool = False
    safety_baseline_relaxation_allowed: bool = False
    execution_allowed: bool = False
    production_activation_allowed: bool = False

    def __post_init__(self) -> None:
        if (
            self.sequence <= 0
            or self.shadow_id
            != _shadow_id(
                self.proposal_id,
                self.proposal_digest,
                self.source_review_digest,
                tuple(result.fixture_digest for result in self.item_results),
            )
            or not _valid_prefixed(
                self.proposal_id, "synthetic:implementation-proposal-draft:"
            )
            or not _valid_digest(self.proposal_digest)
            or not _valid_digest(self.source_review_digest)
            or not self.item_results
            or not isinstance(self.decision, PatchShadowDecision)
            or self.reason not in {
                "patch_shadow_ready_for_eternian_review",
                "patch_shadow_requires_human_review",
                "patch_shadow_blocked_by_forbidden_side_effect",
            }
            or self.evaluated_at.tzinfo is None
            or not _valid_digest(self.previous_digest)
            or self.source_docket_state_changed
            or self.patch_content_present
            or self.code_change_allowed
            or self.automatic_application_allowed
            or self.safety_baseline_relaxation_allowed
            or self.execution_allowed
            or self.production_activation_allowed
            or self.assessment_digest != canonical_digest(self.digest_value())
        ):
            raise GovernanceRejected("valid non-executing patch shadow assessment required")

    def digest_value(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "shadow_id": self.shadow_id,
            "proposal_id": self.proposal_id,
            "proposal_digest": self.proposal_digest,
            "source_review_digest": self.source_review_digest,
            "item_result_digests": [item.result_digest for item in self.item_results],
            "decision": self.decision.value,
            "reason": self.reason,
            "evaluated_at": self.evaluated_at.isoformat(),
            "previous_digest": self.previous_digest,
            "source_docket_state_changed": False,
            "patch_content_present": False,
            "code_change_allowed": False,
            "automatic_application_allowed": False,
            "safety_baseline_relaxation_allowed": False,
            "execution_allowed": False,
            "production_activation_allowed": False,
        }


def _valid_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _valid_prefixed(value: object, prefix: str) -> bool:
    return (
        isinstance(value, str)
        and value.startswith(prefix)
        and len(value) > len(prefix)
    )


def _shadow_id(
    proposal_id: str,
    proposal_digest: str,
    source_review_digest: str,
    fixture_digests: tuple[str, ...],
) -> str:
    identity = canonical_digest(
        {
            "proposal_id": proposal_id,
            "proposal_digest": proposal_digest,
            "source_review_digest": source_review_digest,
            "fixture_digests": list(fixture_digests),
        }
    )
    return "synthetic:patch-shadow:" + identity[:32]


class SyntheticPatchShadowBook:
    """Evaluates synthetic patch metadata without generating or applying a patch."""

    def __init__(self) -> None:
        self._assessments: list[SyntheticPatchShadowAssessment] = []
        self._by_proposal: dict[str, SyntheticPatchShadowAssessment] = {}
        self._lock = RLock()

    @property
    def assessments(self) -> tuple[SyntheticPatchShadowAssessment, ...]:
        with self._lock:
            return tuple(self._assessments)

    def evaluate(
        self,
        docket: SyntheticImplementationReviewDocket,
        proposal_id: str,
        fixtures: tuple[SyntheticPatchShadowFixture, ...],
        *,
        evaluated_at: datetime,
    ) -> SyntheticPatchShadowAssessment:
        if evaluated_at.tzinfo is None:
            raise GovernanceRejected("timezone-aware patch shadow time required")
        if not isinstance(docket, SyntheticImplementationReviewDocket):
            raise GovernanceRejected("typed implementation review docket required")
        if not isinstance(fixtures, tuple) or not fixtures:
            raise GovernanceRejected("one or more synthetic patch fixtures required")
        if any(not isinstance(item, SyntheticPatchShadowFixture) for item in fixtures):
            raise GovernanceRejected("typed synthetic patch fixtures required")
        before = docket.evidence()["report_digest"]
        source = docket.ready_source(proposal_id)
        if source.reviewed_at is None or source.review_digest is None:
            raise GovernanceRejected("completed Eternian review evidence required")
        if evaluated_at < source.reviewed_at:
            raise GovernanceRejected("patch shadow cannot predate independent review")
        proposal = source.proposal
        results = self._evaluate_scopes(proposal, fixtures)
        decision, reason = self._overall_decision(results)
        fixture_digests = tuple(result.fixture_digest for result in results)
        created = False
        with self._lock:
            existing = self._by_proposal.get(proposal_id)
            if existing is not None:
                existing_fixtures = tuple(
                    result.fixture_digest for result in existing.item_results
                )
                if (
                    existing_fixtures != fixture_digests
                    or existing.proposal_digest != proposal.proposal_digest
                    or existing.source_review_digest != source.review_digest
                ):
                    raise GovernanceRejected("patch shadow idempotency mismatch")
                if not self.verify_assessment_chain():
                    raise GovernanceRejected("existing patch shadow evidence is invalid")
                assessment = existing
            else:
                sequence = len(self._assessments) + 1
                previous = (
                    self._assessments[-1].assessment_digest
                    if self._assessments
                    else "0" * 64
                )
                shadow_id = _shadow_id(
                    proposal.proposal_id,
                    proposal.proposal_digest,
                    source.review_digest,
                    fixture_digests,
                )
                value = {
                    "sequence": sequence,
                    "shadow_id": shadow_id,
                    "proposal_id": proposal.proposal_id,
                    "proposal_digest": proposal.proposal_digest,
                    "source_review_digest": source.review_digest,
                    "item_result_digests": [item.result_digest for item in results],
                    "decision": decision.value,
                    "reason": reason,
                    "evaluated_at": evaluated_at.isoformat(),
                    "previous_digest": previous,
                    "source_docket_state_changed": False,
                    "patch_content_present": False,
                    "code_change_allowed": False,
                    "automatic_application_allowed": False,
                    "safety_baseline_relaxation_allowed": False,
                    "execution_allowed": False,
                    "production_activation_allowed": False,
                }
                assessment = SyntheticPatchShadowAssessment(
                    sequence,
                    shadow_id,
                    proposal.proposal_id,
                    proposal.proposal_digest,
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
            raise GovernanceRejected("implementation review changed during patch shadow")
        return assessment

    @staticmethod
    def _evaluate_scopes(
        proposal,
        fixtures: tuple[SyntheticPatchShadowFixture, ...],
    ) -> tuple[SyntheticPatchShadowItemResult, ...]:
        by_scope: dict[str, SyntheticPatchShadowFixture] = {}
        for fixture in fixtures:
            if fixture.fixture_digest != canonical_digest(fixture.digest_value()):
                raise GovernanceRejected("synthetic patch fixture digest mismatch")
            if fixture.draft_scope in by_scope:
                raise GovernanceRejected("duplicate synthetic patch scope fixture")
            if (
                fixture.proposal_id != proposal.proposal_id
                or fixture.proposal_digest != proposal.proposal_digest
            ):
                raise GovernanceRejected("patch fixture proposal binding mismatch")
            by_scope[fixture.draft_scope] = fixture
        if set(by_scope) != set(proposal.draft_scopes):
            raise GovernanceRejected("exactly one fixture per implementation scope required")
        results = []
        for ordinal, scope in enumerate(proposal.draft_scopes, start=1):
            fixture = by_scope[scope]
            forbidden = any(
                (
                    fixture.source_code_changed,
                    fixture.filesystem_written,
                    fixture.network_access_used,
                    fixture.production_access_used,
                    fixture.credentials_used,
                    fixture.personal_data_used,
                    fixture.money_movement_executed,
                )
            )
            complete = all(
                (
                    fixture.synthetic_input_only,
                    fixture.expected_change_observed,
                    fixture.fail_closed_baseline_preserved,
                    fixture.regression_test_passed,
                    fixture.concurrency_failure_tests_passed,
                    fixture.sha256_evidence_reproduced,
                    fixture.eternian_review_retained,
                    fixture.base_snapshot_digest != fixture.candidate_patch_digest,
                )
            )
            if forbidden:
                decision = PatchShadowItemDecision.BLOCKED
                reason = "forbidden_patch_shadow_side_effect_detected"
            elif not complete:
                decision = PatchShadowItemDecision.HUMAN_REVIEW
                reason = "incomplete_patch_shadow_controls"
            else:
                decision = PatchShadowItemDecision.PASS
                reason = "all_patch_shadow_controls_passed"
            value = {
                "ordinal": ordinal,
                "draft_scope": scope,
                "fixture_digest": fixture.fixture_digest,
                "decision": decision.value,
                "reason": reason,
            }
            results.append(
                SyntheticPatchShadowItemResult(
                    ordinal,
                    scope,
                    fixture.fixture_digest,
                    decision,
                    reason,
                    canonical_digest(value),
                )
            )
        return tuple(results)

    @staticmethod
    def _overall_decision(
        results: tuple[SyntheticPatchShadowItemResult, ...],
    ) -> tuple[PatchShadowDecision, str]:
        decisions = {result.decision for result in results}
        if PatchShadowItemDecision.BLOCKED in decisions:
            return (
                PatchShadowDecision.BLOCKED,
                "patch_shadow_blocked_by_forbidden_side_effect",
            )
        if PatchShadowItemDecision.HUMAN_REVIEW in decisions:
            return (
                PatchShadowDecision.HUMAN_REVIEW,
                "patch_shadow_requires_human_review",
            )
        return (
            PatchShadowDecision.PROPOSED_FOR_ETERNIAN_REVIEW,
            "patch_shadow_ready_for_eternian_review",
        )

    def verify_assessment_chain(self) -> bool:
        with self._lock:
            previous = "0" * 64
            for sequence, assessment in enumerate(self._assessments, start=1):
                try:
                    expected_decision, expected_reason = self._overall_decision(
                        assessment.item_results
                    )
                    results_valid = all(
                        result.result_digest == canonical_digest(result.digest_value())
                        and result.reason
                        == {
                            PatchShadowItemDecision.PASS: (
                                "all_patch_shadow_controls_passed"
                            ),
                            PatchShadowItemDecision.HUMAN_REVIEW: (
                                "incomplete_patch_shadow_controls"
                            ),
                            PatchShadowItemDecision.BLOCKED: (
                                "forbidden_patch_shadow_side_effect_detected"
                            ),
                        }[result.decision]
                        for result in assessment.item_results
                    )
                except (GovernanceRejected, KeyError, TypeError, ValueError):
                    return False
                if (
                    assessment.sequence != sequence
                    or assessment.previous_digest != previous
                    or assessment.shadow_id
                    != _shadow_id(
                        assessment.proposal_id,
                        assessment.proposal_digest,
                        assessment.source_review_digest,
                        tuple(
                            result.fixture_digest
                            for result in assessment.item_results
                        ),
                    )
                    or not results_valid
                    or assessment.decision is not expected_decision
                    or assessment.reason != expected_reason
                    or assessment.assessment_digest
                    != canonical_digest(assessment.digest_value())
                    or assessment.source_docket_state_changed
                    or assessment.patch_content_present
                    or assessment.code_change_allowed
                    or assessment.automatic_application_allowed
                    or assessment.safety_baseline_relaxation_allowed
                    or assessment.execution_allowed
                    or assessment.production_activation_allowed
                ):
                    return False
                previous = assessment.assessment_digest
            return len(self._by_proposal) == len(self._assessments) and all(
                self._by_proposal.get(assessment.proposal_id) is assessment
                for assessment in self._assessments
            )

    def evidence(self) -> dict[str, object]:
        with self._lock:
            counts = {decision.value: 0 for decision in PatchShadowDecision}
            digests = []
            for assessment in self._assessments:
                counts[assessment.decision.value] += 1
                digests.append(assessment.assessment_digest)
            value = {
                "schema": "nurion.pg.synthetic-patch-shadow-evidence.v1",
                "decision_counts": counts,
                "assessment_digests": digests,
                "assessment_chain_valid": self.verify_assessment_chain(),
                "maximum_decision": MAXIMUM_PATCH_SHADOW_DECISION,
                "source_docket_state_changed": False,
                "patch_content_present": False,
                "file_write_method_present": False,
                "network_access_method_present": False,
                "code_change_method_present": False,
                "application_method_present": False,
                "safety_baseline_relaxation_method_present": False,
                "operator_decision_method_present": False,
                "execution_method_present": False,
                "personal_data_used": False,
                "credentials_used": False,
                "money_movement_executed": False,
                "production_activation_allowed": False,
            }
            return {**value, "report_digest": canonical_digest(value)}
