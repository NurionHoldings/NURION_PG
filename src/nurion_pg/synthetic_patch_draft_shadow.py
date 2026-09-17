"""Synthetic shadow evaluation of reviewed metadata-only patch draft manifests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest
from .synthetic_patch_draft_review_docket import SyntheticPatchDraftReviewDocket


MAXIMUM_PATCH_DRAFT_SHADOW_DECISION = "PROPOSED_FOR_ETERNIAN_REVIEW"


class PatchDraftShadowItemDecision(StrEnum):
    PASS = "PASS"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    BLOCKED = "BLOCKED"


class PatchDraftShadowDecision(StrEnum):
    PROPOSED_FOR_ETERNIAN_REVIEW = "PROPOSED_FOR_ETERNIAN_REVIEW"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    BLOCKED = "BLOCKED"


def _valid_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _valid_prefixed(value: object, prefix: str) -> bool:
    return isinstance(value, str) and value.startswith(prefix) and len(value) > len(prefix)


@dataclass(frozen=True)
class SyntheticPatchDraftShadowFixture:
    fixture_id: str
    manifest_id: str
    manifest_digest: str
    draft_scope: str
    target_path_digest: str
    candidate_artifact_digest: str
    synthetic_input_only: bool
    manifest_binding_verified: bool
    expected_metadata_change_observed: bool
    fail_closed_baseline_preserved: bool
    regression_test_passed: bool
    concurrency_failure_tests_passed: bool
    sha256_evidence_reproduced: bool
    eternian_review_retained: bool
    patch_content_present: bool
    diff_content_present: bool
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
            self.manifest_binding_verified,
            self.expected_metadata_change_observed,
            self.fail_closed_baseline_preserved,
            self.regression_test_passed,
            self.concurrency_failure_tests_passed,
            self.sha256_evidence_reproduced,
            self.eternian_review_retained,
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
            not _valid_prefixed(
                self.fixture_id, "synthetic:patch-draft-shadow-fixture:"
            )
            or not _valid_prefixed(
                self.manifest_id, "synthetic:patch-draft-manifest:"
            )
            or not _valid_digest(self.manifest_digest)
            or not self.draft_scope.endswith("_DRAFT_ONLY")
            or not _valid_digest(self.target_path_digest)
            or not _valid_digest(self.candidate_artifact_digest)
            or not all(isinstance(value, bool) for value in booleans)
            or self.fixture_digest != canonical_digest(self.digest_value())
        ):
            raise GovernanceRejected("valid synthetic patch draft shadow fixture required")

    def digest_value(self) -> dict[str, object]:
        return {
            "fixture_id": self.fixture_id,
            "manifest_id": self.manifest_id,
            "manifest_digest": self.manifest_digest,
            "draft_scope": self.draft_scope,
            "target_path_digest": self.target_path_digest,
            "candidate_artifact_digest": self.candidate_artifact_digest,
            "synthetic_input_only": self.synthetic_input_only,
            "manifest_binding_verified": self.manifest_binding_verified,
            "expected_metadata_change_observed": self.expected_metadata_change_observed,
            "fail_closed_baseline_preserved": self.fail_closed_baseline_preserved,
            "regression_test_passed": self.regression_test_passed,
            "concurrency_failure_tests_passed": self.concurrency_failure_tests_passed,
            "sha256_evidence_reproduced": self.sha256_evidence_reproduced,
            "eternian_review_retained": self.eternian_review_retained,
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
class SyntheticPatchDraftShadowItemResult:
    ordinal: int
    draft_scope: str
    target_path_digest: str
    fixture_digest: str
    decision: PatchDraftShadowItemDecision
    reason: str
    result_digest: str

    def __post_init__(self) -> None:
        if (
            self.ordinal <= 0
            or not self.draft_scope.endswith("_DRAFT_ONLY")
            or not _valid_digest(self.target_path_digest)
            or not _valid_digest(self.fixture_digest)
            or not isinstance(self.decision, PatchDraftShadowItemDecision)
            or self.reason not in {
                "all_patch_draft_shadow_controls_passed",
                "incomplete_patch_draft_shadow_controls",
                "forbidden_patch_draft_shadow_side_effect_detected",
            }
            or self.result_digest != canonical_digest(self.digest_value())
        ):
            raise GovernanceRejected("valid patch draft shadow result required")

    def digest_value(self) -> dict[str, object]:
        return {
            "ordinal": self.ordinal,
            "draft_scope": self.draft_scope,
            "target_path_digest": self.target_path_digest,
            "fixture_digest": self.fixture_digest,
            "decision": self.decision.value,
            "reason": self.reason,
        }


def _shadow_id(
    manifest_id: str,
    manifest_digest: str,
    source_review_digest: str,
    fixture_digests: tuple[str, ...],
) -> str:
    identity = canonical_digest(
        {
            "manifest_id": manifest_id,
            "manifest_digest": manifest_digest,
            "source_review_digest": source_review_digest,
            "fixture_digests": list(fixture_digests),
        }
    )
    return "synthetic:patch-draft-shadow:" + identity[:32]


@dataclass(frozen=True)
class SyntheticPatchDraftShadowAssessment:
    sequence: int
    shadow_id: str
    manifest_id: str
    manifest_digest: str
    source_review_digest: str
    item_results: tuple[SyntheticPatchDraftShadowItemResult, ...]
    decision: PatchDraftShadowDecision
    reason: str
    evaluated_at: datetime
    previous_digest: str
    assessment_digest: str
    source_docket_state_changed: bool = False
    patch_content_present: bool = False
    diff_content_present: bool = False
    source_code_changed: bool = False
    filesystem_written: bool = False
    automatic_application_allowed: bool = False
    safety_baseline_relaxation_allowed: bool = False
    execution_allowed: bool = False
    production_activation_allowed: bool = False

    def __post_init__(self) -> None:
        if (
            self.sequence <= 0
            or self.shadow_id
            != _shadow_id(
                self.manifest_id,
                self.manifest_digest,
                self.source_review_digest,
                tuple(item.fixture_digest for item in self.item_results),
            )
            or not _valid_prefixed(
                self.manifest_id, "synthetic:patch-draft-manifest:"
            )
            or not _valid_digest(self.manifest_digest)
            or not _valid_digest(self.source_review_digest)
            or not self.item_results
            or not isinstance(self.decision, PatchDraftShadowDecision)
            or self.reason not in {
                "patch_draft_shadow_ready_for_eternian_review",
                "patch_draft_shadow_requires_human_review",
                "patch_draft_shadow_blocked_by_forbidden_side_effect",
            }
            or self.evaluated_at.tzinfo is None
            or not _valid_digest(self.previous_digest)
            or self.source_docket_state_changed
            or self.patch_content_present
            or self.diff_content_present
            or self.source_code_changed
            or self.filesystem_written
            or self.automatic_application_allowed
            or self.safety_baseline_relaxation_allowed
            or self.execution_allowed
            or self.production_activation_allowed
            or self.assessment_digest != canonical_digest(self.digest_value())
        ):
            raise GovernanceRejected("valid non-executing patch draft shadow required")

    def digest_value(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "shadow_id": self.shadow_id,
            "manifest_id": self.manifest_id,
            "manifest_digest": self.manifest_digest,
            "source_review_digest": self.source_review_digest,
            "item_result_digests": [item.result_digest for item in self.item_results],
            "decision": self.decision.value,
            "reason": self.reason,
            "evaluated_at": self.evaluated_at.isoformat(),
            "previous_digest": self.previous_digest,
            "source_docket_state_changed": False,
            "patch_content_present": False,
            "diff_content_present": False,
            "source_code_changed": False,
            "filesystem_written": False,
            "automatic_application_allowed": False,
            "safety_baseline_relaxation_allowed": False,
            "execution_allowed": False,
            "production_activation_allowed": False,
        }


class SyntheticPatchDraftShadowBook:
    """Evaluates synthetic fixture metadata without creating patch content."""

    def __init__(self) -> None:
        self._assessments: list[SyntheticPatchDraftShadowAssessment] = []
        self._by_manifest: dict[str, SyntheticPatchDraftShadowAssessment] = {}
        self._lock = RLock()

    @property
    def assessments(self) -> tuple[SyntheticPatchDraftShadowAssessment, ...]:
        with self._lock:
            return tuple(self._assessments)

    def evaluate(
        self,
        docket: SyntheticPatchDraftReviewDocket,
        manifest_id: str,
        fixtures: tuple[SyntheticPatchDraftShadowFixture, ...],
        *,
        evaluated_at: datetime,
    ) -> SyntheticPatchDraftShadowAssessment:
        if evaluated_at.tzinfo is None:
            raise GovernanceRejected("timezone-aware patch draft shadow time required")
        if not isinstance(docket, SyntheticPatchDraftReviewDocket):
            raise GovernanceRejected("typed patch draft review docket required")
        if not isinstance(fixtures, tuple) or not fixtures:
            raise GovernanceRejected("one or more patch draft fixtures required")
        if any(not isinstance(item, SyntheticPatchDraftShadowFixture) for item in fixtures):
            raise GovernanceRejected("typed patch draft fixtures required")
        before = docket.evidence()["report_digest"]
        source = docket.ready_source(manifest_id)
        if source.reviewed_at is None or source.review_digest is None:
            raise GovernanceRejected("completed Eternian review required")
        if evaluated_at < source.reviewed_at:
            raise GovernanceRejected("patch draft shadow cannot predate review")
        manifest = source.manifest
        results = self._evaluate_scopes(manifest, fixtures)
        decision, reason = self._overall_decision(results)
        fixture_digests = tuple(item.fixture_digest for item in results)
        with self._lock:
            created = False
            existing = self._by_manifest.get(manifest_id)
            if existing is not None:
                if (
                    tuple(item.fixture_digest for item in existing.item_results)
                    != fixture_digests
                    or existing.manifest_digest != manifest.manifest_digest
                    or existing.source_review_digest != source.review_digest
                ):
                    raise GovernanceRejected("patch draft shadow idempotency mismatch")
                if not self.verify_assessment_chain():
                    raise GovernanceRejected("existing patch draft shadow is invalid")
                assessment = existing
            else:
                sequence = len(self._assessments) + 1
                previous = self._assessments[-1].assessment_digest if self._assessments else "0" * 64
                shadow_id = _shadow_id(
                    manifest.manifest_id, manifest.manifest_digest,
                    source.review_digest, fixture_digests,
                )
                value = {
                    "sequence": sequence,
                    "shadow_id": shadow_id,
                    "manifest_id": manifest.manifest_id,
                    "manifest_digest": manifest.manifest_digest,
                    "source_review_digest": source.review_digest,
                    "item_result_digests": [item.result_digest for item in results],
                    "decision": decision.value,
                    "reason": reason,
                    "evaluated_at": evaluated_at.isoformat(),
                    "previous_digest": previous,
                    "source_docket_state_changed": False,
                    "patch_content_present": False,
                    "diff_content_present": False,
                    "source_code_changed": False,
                    "filesystem_written": False,
                    "automatic_application_allowed": False,
                    "safety_baseline_relaxation_allowed": False,
                    "execution_allowed": False,
                    "production_activation_allowed": False,
                }
                assessment = SyntheticPatchDraftShadowAssessment(
                    sequence, shadow_id, manifest.manifest_id,
                    manifest.manifest_digest, source.review_digest, results,
                    decision, reason, evaluated_at, previous, canonical_digest(value),
                )
                self._assessments.append(assessment)
                self._by_manifest[manifest_id] = assessment
                created = True
            if before != docket.evidence()["report_digest"]:
                if created:
                    self._assessments.pop()
                    self._by_manifest.pop(manifest_id, None)
                raise GovernanceRejected("patch draft review changed during shadow")
        return assessment

    @staticmethod
    def _evaluate_scopes(
        manifest,
        fixtures: tuple[SyntheticPatchDraftShadowFixture, ...],
    ) -> tuple[SyntheticPatchDraftShadowItemResult, ...]:
        by_scope: dict[str, SyntheticPatchDraftShadowFixture] = {}
        for fixture in fixtures:
            if fixture.fixture_digest != canonical_digest(fixture.digest_value()):
                raise GovernanceRejected("patch draft fixture digest mismatch")
            if fixture.draft_scope in by_scope:
                raise GovernanceRejected("duplicate patch draft scope fixture")
            if (
                fixture.manifest_id != manifest.manifest_id
                or fixture.manifest_digest != manifest.manifest_digest
            ):
                raise GovernanceRejected("fixture manifest binding mismatch")
            by_scope[fixture.draft_scope] = fixture
        if set(by_scope) != set(manifest.draft_scopes):
            raise GovernanceRejected("exactly one fixture per patch draft scope required")

        results = []
        for ordinal, (scope, target_digest) in enumerate(
            zip(manifest.draft_scopes, manifest.target_path_digests, strict=True), start=1
        ):
            fixture = by_scope[scope]
            if fixture.target_path_digest != target_digest:
                raise GovernanceRejected("fixture target digest mismatch")
            forbidden = any((
                fixture.patch_content_present, fixture.diff_content_present,
                fixture.source_code_changed, fixture.filesystem_written,
                fixture.network_access_used, fixture.production_access_used,
                fixture.credentials_used, fixture.personal_data_used,
                fixture.money_movement_executed,
            ))
            complete = all((
                fixture.synthetic_input_only, fixture.manifest_binding_verified,
                fixture.expected_metadata_change_observed,
                fixture.fail_closed_baseline_preserved,
                fixture.regression_test_passed,
                fixture.concurrency_failure_tests_passed,
                fixture.sha256_evidence_reproduced,
                fixture.eternian_review_retained,
                fixture.candidate_artifact_digest != fixture.target_path_digest,
            ))
            if forbidden:
                item_decision = PatchDraftShadowItemDecision.BLOCKED
                item_reason = "forbidden_patch_draft_shadow_side_effect_detected"
            elif not complete:
                item_decision = PatchDraftShadowItemDecision.HUMAN_REVIEW
                item_reason = "incomplete_patch_draft_shadow_controls"
            else:
                item_decision = PatchDraftShadowItemDecision.PASS
                item_reason = "all_patch_draft_shadow_controls_passed"
            value = {
                "ordinal": ordinal,
                "draft_scope": scope,
                "target_path_digest": target_digest,
                "fixture_digest": fixture.fixture_digest,
                "decision": item_decision.value,
                "reason": item_reason,
            }
            results.append(SyntheticPatchDraftShadowItemResult(
                ordinal, scope, target_digest, fixture.fixture_digest,
                item_decision, item_reason, canonical_digest(value),
            ))
        return tuple(results)

    @staticmethod
    def _overall_decision(
        results: tuple[SyntheticPatchDraftShadowItemResult, ...],
    ) -> tuple[PatchDraftShadowDecision, str]:
        decisions = {item.decision for item in results}
        if PatchDraftShadowItemDecision.BLOCKED in decisions:
            return (
                PatchDraftShadowDecision.BLOCKED,
                "patch_draft_shadow_blocked_by_forbidden_side_effect",
            )
        if PatchDraftShadowItemDecision.HUMAN_REVIEW in decisions:
            return (
                PatchDraftShadowDecision.HUMAN_REVIEW,
                "patch_draft_shadow_requires_human_review",
            )
        return (
            PatchDraftShadowDecision.PROPOSED_FOR_ETERNIAN_REVIEW,
            "patch_draft_shadow_ready_for_eternian_review",
        )

    def verify_assessment_chain(self) -> bool:
        with self._lock:
            previous = "0" * 64
            reasons = {
                PatchDraftShadowItemDecision.PASS: "all_patch_draft_shadow_controls_passed",
                PatchDraftShadowItemDecision.HUMAN_REVIEW: "incomplete_patch_draft_shadow_controls",
                PatchDraftShadowItemDecision.BLOCKED: "forbidden_patch_draft_shadow_side_effect_detected",
            }
            for sequence, assessment in enumerate(self._assessments, start=1):
                try:
                    decision, reason = self._overall_decision(assessment.item_results)
                    results_valid = all(
                        item.result_digest == canonical_digest(item.digest_value())
                        and item.reason == reasons[item.decision]
                        for item in assessment.item_results
                    )
                except (GovernanceRejected, KeyError, TypeError, ValueError):
                    return False
                if (
                    assessment.sequence != sequence
                    or assessment.previous_digest != previous
                    or assessment.shadow_id != _shadow_id(
                        assessment.manifest_id, assessment.manifest_digest,
                        assessment.source_review_digest,
                        tuple(item.fixture_digest for item in assessment.item_results),
                    )
                    or not results_valid
                    or assessment.decision is not decision
                    or assessment.reason != reason
                    or assessment.assessment_digest
                    != canonical_digest(assessment.digest_value())
                    or assessment.source_docket_state_changed
                    or assessment.patch_content_present
                    or assessment.diff_content_present
                    or assessment.source_code_changed
                    or assessment.filesystem_written
                    or assessment.automatic_application_allowed
                    or assessment.safety_baseline_relaxation_allowed
                    or assessment.execution_allowed
                    or assessment.production_activation_allowed
                ):
                    return False
                previous = assessment.assessment_digest
            return len(self._by_manifest) == len(self._assessments) and all(
                self._by_manifest.get(item.manifest_id) is item
                for item in self._assessments
            )

    def evidence(self) -> dict[str, object]:
        with self._lock:
            counts = {item.value: 0 for item in PatchDraftShadowDecision}
            for assessment in self._assessments:
                counts[assessment.decision.value] += 1
            value = {
                "schema": "nurion.pg.synthetic-patch-draft-shadow-evidence.v1",
                "decision_counts": counts,
                "assessment_digests": [item.assessment_digest for item in self._assessments],
                "assessment_chain_valid": self.verify_assessment_chain(),
                "maximum_decision": MAXIMUM_PATCH_DRAFT_SHADOW_DECISION,
                "source_docket_state_changed": False,
                "patch_content_present": False,
                "diff_content_present": False,
                "source_code_changed": False,
                "filesystem_written": False,
                "application_method_present": False,
                "safety_baseline_relaxation_method_present": False,
                "execution_method_present": False,
                "network_access_method_present": False,
                "personal_data_used": False,
                "credentials_used": False,
                "money_movement_executed": False,
                "production_activation_allowed": False,
            }
            return {**value, "report_digest": canonical_digest(value)}
