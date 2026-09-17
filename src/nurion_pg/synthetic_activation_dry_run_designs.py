"""Metadata-only designs for a later synthetic activation dry-run."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest
from .synthetic_patch_draft_limited_promotion_activation_draft_review import (
    ActivationDraftReviewState,
    SyntheticActivationDraftReviewDocket,
    SyntheticActivationDraftReviewRecord,
)


DRY_RUN_DESIGN_STATE = "SYNTHETIC_ACTIVATION_DRY_RUN_DESIGNED"
DRY_RUN_DESIGN_SCOPE = "SYNTHETIC_FIXTURE_DRY_RUN_DESIGN_ONLY"
DRY_RUN_REQUIRED_GATES = (
    "PASSED_ETERNIAN_ACTIVATION_DRAFT_REVIEW_ONLY",
    "EXACT_REVIEW_AND_DRAFT_DIGESTS_ONLY",
    "FIXED_SYNTHETIC_COHORT_AND_SAMPLE_ONLY",
    "FIXED_OBSERVATION_WINDOW_AND_RESULTS_ONLY",
    "ROLLBACK_SIMULATION_CRITERIA_REQUIRED",
    "FAIL_CLOSED_ON_SOURCE_CHANGE",
    "SEPARATE_REVIEW_REQUIRED_BEFORE_DRY_RUN",
    "NO_DRY_RUN_EXECUTION_METHOD",
    "NO_ACTIVATION_OR_ROLLBACK_EXECUTION_METHOD",
    "NO_PAYMENT_NETWORK_OR_FILESYSTEM_EFFECT",
)


def _valid_digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _design_id(review: SyntheticActivationDraftReviewRecord) -> str:
    return _design_id_values(review.draft.draft_id, review.draft.draft_digest, review.review_digest)


def _design_id_values(draft_id: str, draft_digest: str, review_digest: str) -> str:
    identity = canonical_digest({
        "draft_id": draft_id,
        "draft_digest": draft_digest,
        "review_digest": review_digest,
        "scope": DRY_RUN_DESIGN_SCOPE,
    })
    return "synthetic:limited-promotion-activation-dry-run-design:" + identity[:32]


@dataclass(frozen=True)
class SyntheticActivationDryRunDesign:
    sequence: int
    design_id: str
    source_draft_id: str
    source_draft_digest: str
    source_review_id: str
    source_review_digest: str
    manifest_digest: str
    candidate_digest: str
    cohort_digest: str
    synthetic_sample_size: int
    observation_window_seconds: int
    observation_result_digests: tuple[str, ...]
    rollback_triggers: tuple[str, ...]
    required_gates: tuple[str, ...]
    designed_at: datetime
    previous_digest: str
    design_digest: str
    state: str = DRY_RUN_DESIGN_STATE
    scope: str = DRY_RUN_DESIGN_SCOPE
    synthetic_only: bool = True
    separate_review_required: bool = True
    dry_run_executed: bool = False
    activation_recorded: bool = False
    rollback_executed: bool = False
    filesystem_written: bool = False
    network_accessed: bool = False
    money_movement_executed: bool = False
    production_activation_allowed: bool = False

    def __post_init__(self) -> None:
        if (
            self.sequence <= 0
            or not self.design_id.startswith("synthetic:limited-promotion-activation-dry-run-design:")
            or not self.source_draft_id.startswith("synthetic:limited-promotion-activation-draft:")
            or not self.source_review_id.startswith("synthetic:limited-promotion-activation-draft-review:")
            or not all(_valid_digest(v) for v in (
                self.source_draft_digest, self.source_review_digest, self.manifest_digest,
                self.candidate_digest, self.cohort_digest, self.previous_digest,
            ))
            or self.synthetic_sample_size <= 0 or self.observation_window_seconds <= 0
            or not self.observation_result_digests
            or not all(_valid_digest(v) for v in self.observation_result_digests)
            or not self.rollback_triggers
            or self.required_gates != DRY_RUN_REQUIRED_GATES
            or self.designed_at.tzinfo is None
            or self.state != DRY_RUN_DESIGN_STATE or self.scope != DRY_RUN_DESIGN_SCOPE
            or not self.synthetic_only or not self.separate_review_required
            or any((self.dry_run_executed, self.activation_recorded, self.rollback_executed,
                    self.filesystem_written, self.network_accessed, self.money_movement_executed,
                    self.production_activation_allowed))
            or self.design_digest != canonical_digest(self.digest_value())
        ):
            raise GovernanceRejected("valid metadata-only activation dry-run design required")

    def digest_value(self) -> dict[str, object]:
        return {
            "sequence": self.sequence, "design_id": self.design_id,
            "source_draft_id": self.source_draft_id, "source_draft_digest": self.source_draft_digest,
            "source_review_id": self.source_review_id, "source_review_digest": self.source_review_digest,
            "manifest_digest": self.manifest_digest, "candidate_digest": self.candidate_digest,
            "cohort_digest": self.cohort_digest, "synthetic_sample_size": self.synthetic_sample_size,
            "observation_window_seconds": self.observation_window_seconds,
            "observation_result_digests": list(self.observation_result_digests),
            "rollback_triggers": list(self.rollback_triggers), "required_gates": list(self.required_gates),
            "designed_at": self.designed_at.isoformat(), "previous_digest": self.previous_digest,
            "state": self.state, "scope": self.scope, "synthetic_only": True,
            "separate_review_required": True, "dry_run_executed": False,
            "activation_recorded": False, "rollback_executed": False,
            "filesystem_written": False, "network_accessed": False,
            "money_movement_executed": False, "production_activation_allowed": False,
        }


class SyntheticActivationDryRunDesignBook:
    """Freezes a review-approved design without running any fixture."""

    def __init__(self) -> None:
        self._designs: list[SyntheticActivationDryRunDesign] = []
        self._by_review: dict[str, SyntheticActivationDryRunDesign] = {}
        self._lock = RLock()

    @property
    def designs(self) -> tuple[SyntheticActivationDryRunDesign, ...]:
        with self._lock: return tuple(self._designs)

    def design_from_review(self, docket: SyntheticActivationDraftReviewDocket, draft_id: str, *, designed_at: datetime) -> SyntheticActivationDryRunDesign:
        if not isinstance(docket, SyntheticActivationDraftReviewDocket) or not docket.verify_chain():
            raise GovernanceRejected("intact typed activation draft review docket required")
        if designed_at.tzinfo is None:
            raise GovernanceRejected("timezone-aware dry-run design time required")
        before = docket.evidence()["report_digest"]
        review = docket.ready_source(draft_id)
        if (
            review.state is not ActivationDraftReviewState.READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_DESIGN
            or review.review_id is None or review.review_digest is None
            or designed_at < review.reviewed_at
        ):
            raise GovernanceRejected("passed current activation draft review required")
        draft = review.draft
        design_id = _design_id(review)
        with self._lock:
            if not self.verify_design_chain():
                raise GovernanceRejected("existing dry-run design chain invalid")
            existing = self._by_review.get(review.review_digest)
            if existing is not None: return existing
            values = {
                "sequence": len(self._designs) + 1, "design_id": design_id,
                "source_draft_id": draft.draft_id, "source_draft_digest": draft.draft_digest,
                "source_review_id": review.review_id, "source_review_digest": review.review_digest,
                "manifest_digest": draft.manifest_digest, "candidate_digest": draft.candidate_digest,
                "cohort_digest": draft.cohort_digest, "synthetic_sample_size": draft.synthetic_sample_size,
                "observation_window_seconds": draft.observation_window_seconds,
                "observation_result_digests": list(draft.observation_result_digests),
                "rollback_triggers": list(draft.rollback_triggers), "required_gates": list(DRY_RUN_REQUIRED_GATES),
                "designed_at": designed_at.isoformat(),
                "previous_digest": self._designs[-1].design_digest if self._designs else "0" * 64,
                "state": DRY_RUN_DESIGN_STATE, "scope": DRY_RUN_DESIGN_SCOPE,
                "synthetic_only": True, "separate_review_required": True, "dry_run_executed": False,
                "activation_recorded": False, "rollback_executed": False, "filesystem_written": False,
                "network_accessed": False, "money_movement_executed": False,
                "production_activation_allowed": False,
            }
            design = SyntheticActivationDryRunDesign(
                values["sequence"], design_id, draft.draft_id, draft.draft_digest,
                review.review_id, review.review_digest, draft.manifest_digest, draft.candidate_digest,
                draft.cohort_digest, draft.synthetic_sample_size, draft.observation_window_seconds,
                draft.observation_result_digests, draft.rollback_triggers, DRY_RUN_REQUIRED_GATES,
                designed_at, values["previous_digest"], canonical_digest(values),
            )
            if before != docket.evidence()["report_digest"]:
                raise GovernanceRejected("activation draft review changed during design")
            self._designs.append(design); self._by_review[review.review_digest] = design
            return design

    def verify_design_chain(self) -> bool:
        with self._lock:
            previous = "0" * 64
            for sequence, item in enumerate(self._designs, 1):
                if (item.sequence != sequence or item.previous_digest != previous
                    or item.design_id != _design_id_values(item.source_draft_id, item.source_draft_digest, item.source_review_digest)
                    or item.design_digest != canonical_digest(item.digest_value())
                    or item.state != DRY_RUN_DESIGN_STATE or item.scope != DRY_RUN_DESIGN_SCOPE
                    or item.required_gates != DRY_RUN_REQUIRED_GATES
                    or not all(_valid_digest(v) for v in (item.source_draft_digest, item.source_review_digest,
                        item.manifest_digest, item.candidate_digest, item.cohort_digest))
                    or item.synthetic_sample_size <= 0 or item.observation_window_seconds <= 0
                    or not item.observation_result_digests or not item.rollback_triggers
                    or not item.synthetic_only or not item.separate_review_required
                    or any((item.dry_run_executed, item.activation_recorded, item.rollback_executed,
                            item.filesystem_written, item.network_accessed, item.money_movement_executed,
                            item.production_activation_allowed))):
                    return False
                previous = item.design_digest
            return len(self._designs) == len(self._by_review) and all(self._by_review.get(i.source_review_digest) is i for i in self._designs)

    def evidence(self) -> dict[str, object]:
        with self._lock:
            value = {
                "schema": "nurion.pg.synthetic-activation-dry-run-design-evidence.v1",
                "mode": "UNREGISTERED_SYNTHETIC_ONLY", "design_count": len(self._designs),
                "design_digests": [i.design_digest for i in self._designs],
                "design_chain_valid": self.verify_design_chain(), "maximum_state": DRY_RUN_DESIGN_STATE,
                "scope": DRY_RUN_DESIGN_SCOPE, "separate_review_required": True,
                "dry_run_execution_method_present": False, "activation_method_present": False,
                "rollback_execution_method_present": False, "filesystem_write_method_present": False,
                "network_access_method_present": False, "automatic_merge_method_present": False,
                "automatic_deploy_method_present": False, "credentials_used": False,
                "personal_data_used": False, "money_movement_executed": False,
                "production_activation_allowed": False,
            }
            return {**value, "report_digest": canonical_digest(value)}
