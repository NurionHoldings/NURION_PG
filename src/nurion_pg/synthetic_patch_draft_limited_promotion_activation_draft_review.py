"""Independent, non-executing Eternian review of synthetic activation drafts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest
from .synthetic_patch_draft_limited_promotion_activation_drafts import (
    ACTIVATION_DRAFT_SCOPE,
    ACTIVATION_DRAFT_STATE,
    SyntheticPatchDraftLimitedPromotionActivationDraft,
    SyntheticPatchDraftLimitedPromotionActivationDraftBook,
)


ACTIVATION_DRAFT_REVIEW_MAXIMUM_STATE = "READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_DESIGN"
_REVIEW_PREFIX = "synthetic:limited-promotion-activation-draft-review:"
_REVIEWER_PREFIX = "synthetic:eternian-reviewer:activation-draft:"


class ActivationDraftReviewDecision(StrEnum):
    PASS = "PASS"
    HOLD = "HOLD"
    REJECT = "REJECT"


class ActivationDraftReviewState(StrEnum):
    PENDING_ETERNIAN_REVIEW = "PENDING_ETERNIAN_REVIEW"
    READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_DESIGN = ACTIVATION_DRAFT_REVIEW_MAXIMUM_STATE
    HELD = "HELD"
    REJECTED = "REJECTED"


_STATE_BY_DECISION = {
    ActivationDraftReviewDecision.PASS: ActivationDraftReviewState.READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_DESIGN,
    ActivationDraftReviewDecision.HOLD: ActivationDraftReviewState.HELD,
    ActivationDraftReviewDecision.REJECT: ActivationDraftReviewState.REJECTED,
}


def _valid_digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


@dataclass(frozen=True)
class SyntheticActivationDraftReviewRecord:
    sequence: int
    draft: SyntheticPatchDraftLimitedPromotionActivationDraft
    submitted_at: datetime
    state: ActivationDraftReviewState
    previous_digest: str
    record_digest: str
    review_id: str | None = None
    reviewer_id: str | None = None
    decision: ActivationDraftReviewDecision | None = None
    findings_digest: str | None = None
    reviewed_at: datetime | None = None
    review_digest: str | None = None

    def __post_init__(self) -> None:
        pending = self.state is ActivationDraftReviewState.PENDING_ETERNIAN_REVIEW
        review_fields = (self.review_id, self.reviewer_id, self.decision, self.findings_digest, self.reviewed_at, self.review_digest)
        if (
            self.sequence <= 0
            or not isinstance(self.draft, SyntheticPatchDraftLimitedPromotionActivationDraft)
            or self.draft.state != ACTIVATION_DRAFT_STATE
            or self.draft.activation_scope != ACTIVATION_DRAFT_SCOPE
            or self.draft.draft_digest != canonical_digest(self.draft.digest_value())
            or self.submitted_at.tzinfo is None
            or self.submitted_at < self.draft.drafted_at
            or not _valid_digest(self.previous_digest)
            or (pending and any(v is not None for v in review_fields))
            or (not pending and any(v is None for v in review_fields))
            or self.record_digest != canonical_digest(self.record_value())
        ):
            raise GovernanceRejected("valid activation draft review record required")
        if not pending and (
            not self.review_id.startswith(_REVIEW_PREFIX)  # type: ignore[union-attr]
            or not self.reviewer_id.startswith(_REVIEWER_PREFIX)  # type: ignore[union-attr]
            or not isinstance(self.decision, ActivationDraftReviewDecision)
            or self.state is not _STATE_BY_DECISION[self.decision]
            or not _valid_digest(self.findings_digest)
            or self.reviewed_at.tzinfo is None  # type: ignore[union-attr]
            or self.reviewed_at < self.submitted_at  # type: ignore[operator]
            or self.review_digest != canonical_digest(self.review_value())
        ):
            raise GovernanceRejected("valid independent Eternian review required")

    def review_value(self) -> dict[str, object]:
        return {
            "draft_id": self.draft.draft_id, "draft_digest": self.draft.draft_digest,
            "review_id": self.review_id, "reviewer_id": self.reviewer_id,
            "decision": self.decision.value if self.decision else None,
            "findings_digest": self.findings_digest,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "resulting_state": self.state.value,
            "activation_allowed": False, "rollback_execution_allowed": False,
            "execution_allowed": False, "production_activation_allowed": False,
        }

    def record_value(self) -> dict[str, object]:
        return {
            "sequence": self.sequence, "draft_id": self.draft.draft_id,
            "draft_digest": self.draft.draft_digest, "submitted_at": self.submitted_at.isoformat(),
            "submission_state": ActivationDraftReviewState.PENDING_ETERNIAN_REVIEW.value,
            "previous_digest": self.previous_digest,
        }


class SyntheticActivationDraftReviewDocket:
    """Append-only review docket; PASS authorizes only a later dry-run design."""

    def __init__(self) -> None:
        self._records: list[SyntheticActivationDraftReviewRecord] = []
        self._by_draft: dict[str, SyntheticActivationDraftReviewRecord] = {}
        self._lock = RLock()

    @property
    def records(self) -> tuple[SyntheticActivationDraftReviewRecord, ...]:
        with self._lock:
            return tuple(self._records)

    def submit(self, book: SyntheticPatchDraftLimitedPromotionActivationDraftBook, draft_id: str, *, submitted_at: datetime) -> SyntheticActivationDraftReviewRecord:
        if not isinstance(book, SyntheticPatchDraftLimitedPromotionActivationDraftBook) or not book.verify_draft_chain():
            raise GovernanceRejected("intact typed activation draft book required")
        if submitted_at.tzinfo is None:
            raise GovernanceRejected("timezone-aware review submission required")
        matches = [item for item in book.drafts if item.draft_id == draft_id]
        if len(matches) != 1:
            raise GovernanceRejected("exactly one activation draft required")
        draft = matches[0]
        before = book.evidence()["report_digest"]
        with self._lock:
            if not self.verify_chain():
                raise GovernanceRejected("existing activation draft review chain invalid")
            existing = self._by_draft.get(draft_id)
            if existing is not None:
                return existing
            values = {
                "sequence": len(self._records) + 1, "draft_id": draft.draft_id,
                "draft_digest": draft.draft_digest, "submitted_at": submitted_at.isoformat(),
                "submission_state": ActivationDraftReviewState.PENDING_ETERNIAN_REVIEW.value,
                "previous_digest": self._records[-1].record_digest if self._records else "0" * 64,
            }
            record = SyntheticActivationDraftReviewRecord(
                values["sequence"], draft, submitted_at,
                ActivationDraftReviewState.PENDING_ETERNIAN_REVIEW,
                values["previous_digest"], canonical_digest(values),
            )
            if before != book.evidence()["report_digest"]:
                raise GovernanceRejected("activation draft source changed during submission")
            self._records.append(record); self._by_draft[draft_id] = record
            return record

    def record_eternian_review(self, draft_id: str, *, review_id: str, reviewer_id: str, decision: ActivationDraftReviewDecision, findings_digest: str, reviewed_at: datetime) -> SyntheticActivationDraftReviewRecord:
        if (not isinstance(review_id, str) or not review_id.startswith(_REVIEW_PREFIX) or
            not isinstance(reviewer_id, str) or not reviewer_id.startswith(_REVIEWER_PREFIX) or
            not isinstance(decision, ActivationDraftReviewDecision) or not _valid_digest(findings_digest) or reviewed_at.tzinfo is None):
            raise GovernanceRejected("valid Eternian activation draft review metadata required")
        with self._lock:
            if not self.verify_chain():
                raise GovernanceRejected("existing activation draft review chain invalid")
            current = self._by_draft.get(draft_id)
            if current is None:
                raise GovernanceRejected("unknown activation draft")
            review_value = {
                "draft_id": current.draft.draft_id, "draft_digest": current.draft.draft_digest,
                "review_id": review_id, "reviewer_id": reviewer_id, "decision": decision.value,
                "findings_digest": findings_digest, "reviewed_at": reviewed_at.isoformat(),
                "resulting_state": _STATE_BY_DECISION[decision].value,
                "activation_allowed": False, "rollback_execution_allowed": False,
                "execution_allowed": False, "production_activation_allowed": False,
            }
            review_digest = canonical_digest(review_value)
            if current.state is not ActivationDraftReviewState.PENDING_ETERNIAN_REVIEW:
                if current.review_digest == review_digest:
                    return current
                raise GovernanceRejected("activation draft review is immutable")
            updated = SyntheticActivationDraftReviewRecord(
                current.sequence, current.draft, current.submitted_at, _STATE_BY_DECISION[decision],
                current.previous_digest, current.record_digest, review_id, reviewer_id, decision,
                findings_digest, reviewed_at, review_digest,
            )
            self._records[current.sequence - 1] = updated; self._by_draft[draft_id] = updated
            return updated

    def ready_source(self, draft_id: str) -> SyntheticActivationDraftReviewRecord:
        with self._lock:
            record = self._by_draft.get(draft_id)
            if record is None or record.state is not ActivationDraftReviewState.READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_DESIGN or not self.verify_chain():
                raise GovernanceRejected("passed activation draft review required")
            return record

    def verify_chain(self) -> bool:
        with self._lock:
            previous = "0" * 64
            for index, record in enumerate(self._records, 1):
                if record.sequence != index or record.previous_digest != previous or record.record_digest != canonical_digest(record.record_value()):
                    return False
                previous = record.record_digest
            return len(self._records) == len(self._by_draft) and all(self._by_draft.get(r.draft.draft_id) is r for r in self._records)

    def evidence(self) -> dict[str, object]:
        with self._lock:
            value = {
                "schema": "nurion.pg.synthetic-activation-draft-review-evidence.v1",
                "mode": "UNREGISTERED_SYNTHETIC_ONLY", "record_count": len(self._records),
                "record_digests": [r.record_digest for r in self._records], "review_chain_valid": self.verify_chain(),
                "review_digests": [r.review_digest for r in self._records if r.review_digest],
                "maximum_state": ACTIVATION_DRAFT_REVIEW_MAXIMUM_STATE,
                "actual_operator_decision_recorded": False, "activation_recorded": False,
                "activation_method_present": False, "rollback_execution_method_present": False,
                "execution_method_present": False, "network_access_method_present": False,
                "automatic_merge_method_present": False, "automatic_deploy_method_present": False,
                "credentials_used": False, "personal_data_used": False,
                "money_movement_executed": False, "production_activation_allowed": False,
            }
            return {**value, "report_digest": canonical_digest(value)}
