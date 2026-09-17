"""Independent review docket for synthetic activation dry-run designs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest
from .synthetic_activation_dry_run_designs import (
    DRY_RUN_DESIGN_SCOPE, DRY_RUN_DESIGN_STATE,
    SyntheticActivationDryRunDesign, SyntheticActivationDryRunDesignBook,
)


DESIGN_REVIEW_MAXIMUM_STATE = "READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_PROPOSAL"
_REVIEW_PREFIX = "synthetic:activation-dry-run-design-review:"
_REVIEWER_PREFIX = "synthetic:eternian-reviewer:activation-dry-run-design:"


class DryRunDesignReviewDecision(StrEnum):
    PASS = "PASS"
    HOLD = "HOLD"
    REJECT = "REJECT"


class DryRunDesignReviewState(StrEnum):
    PENDING_ETERNIAN_REVIEW = "PENDING_ETERNIAN_REVIEW"
    READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_PROPOSAL = DESIGN_REVIEW_MAXIMUM_STATE
    HELD = "HELD"
    REJECTED = "REJECTED"


_STATE_BY_DECISION = {
    DryRunDesignReviewDecision.PASS: DryRunDesignReviewState.READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_PROPOSAL,
    DryRunDesignReviewDecision.HOLD: DryRunDesignReviewState.HELD,
    DryRunDesignReviewDecision.REJECT: DryRunDesignReviewState.REJECTED,
}


def _valid_digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


@dataclass(frozen=True)
class SyntheticActivationDryRunDesignReviewRecord:
    sequence: int
    design: SyntheticActivationDryRunDesign
    submitted_at: datetime
    state: DryRunDesignReviewState
    previous_digest: str
    submission_digest: str
    review_id: str | None = None
    reviewer_id: str | None = None
    decision: DryRunDesignReviewDecision | None = None
    findings_digest: str | None = None
    reviewed_at: datetime | None = None
    review_digest: str | None = None

    def __post_init__(self) -> None:
        pending = self.state is DryRunDesignReviewState.PENDING_ETERNIAN_REVIEW
        review_fields = (self.review_id, self.reviewer_id, self.decision, self.findings_digest, self.reviewed_at, self.review_digest)
        if (
            self.sequence <= 0 or not isinstance(self.design, SyntheticActivationDryRunDesign)
            or self.design.state != DRY_RUN_DESIGN_STATE or self.design.scope != DRY_RUN_DESIGN_SCOPE
            or self.design.design_digest != canonical_digest(self.design.digest_value())
            or self.submitted_at.tzinfo is None or self.submitted_at < self.design.designed_at
            or not _valid_digest(self.previous_digest)
            or self.submission_digest != canonical_digest(self.submission_value())
            or (pending and any(v is not None for v in review_fields))
            or (not pending and any(v is None for v in review_fields))
        ): raise GovernanceRejected("valid activation dry-run design review record required")
        if not pending and (
            not self.review_id.startswith(_REVIEW_PREFIX)  # type: ignore[union-attr]
            or not self.reviewer_id.startswith(_REVIEWER_PREFIX)  # type: ignore[union-attr]
            or not isinstance(self.decision, DryRunDesignReviewDecision)
            or self.state is not _STATE_BY_DECISION[self.decision]
            or not _valid_digest(self.findings_digest)
            or self.reviewed_at.tzinfo is None or self.reviewed_at < self.submitted_at  # type: ignore[union-attr,operator]
            or self.review_digest != canonical_digest(self.review_value())
        ): raise GovernanceRejected("valid independent dry-run design review required")

    def submission_value(self) -> dict[str, object]:
        return {"sequence": self.sequence, "design_id": self.design.design_id,
                "design_digest": self.design.design_digest, "submitted_at": self.submitted_at.isoformat(),
                "submission_state": DryRunDesignReviewState.PENDING_ETERNIAN_REVIEW.value,
                "previous_digest": self.previous_digest}

    def review_value(self) -> dict[str, object]:
        return {"design_id": self.design.design_id, "design_digest": self.design.design_digest,
                "review_id": self.review_id, "reviewer_id": self.reviewer_id,
                "decision": self.decision.value if self.decision else None,
                "findings_digest": self.findings_digest,
                "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
                "resulting_state": self.state.value, "dry_run_execution_allowed": False,
                "activation_allowed": False, "rollback_execution_allowed": False,
                "production_activation_allowed": False}


class SyntheticActivationDryRunDesignReviewDocket:
    """Records independent design review without producing or running fixtures."""

    def __init__(self) -> None:
        self._records: list[SyntheticActivationDryRunDesignReviewRecord] = []
        self._by_design: dict[str, SyntheticActivationDryRunDesignReviewRecord] = {}
        self._lock = RLock()

    @property
    def records(self) -> tuple[SyntheticActivationDryRunDesignReviewRecord, ...]:
        with self._lock: return tuple(self._records)

    def submit(self, book: SyntheticActivationDryRunDesignBook, design_id: str, *, submitted_at: datetime) -> SyntheticActivationDryRunDesignReviewRecord:
        if not isinstance(book, SyntheticActivationDryRunDesignBook) or not book.verify_design_chain():
            raise GovernanceRejected("intact typed activation dry-run design book required")
        if submitted_at.tzinfo is None: raise GovernanceRejected("timezone-aware design review submission required")
        matches = [item for item in book.designs if item.design_id == design_id]
        if len(matches) != 1: raise GovernanceRejected("exactly one activation dry-run design required")
        design = matches[0]; before = book.evidence()["report_digest"]
        with self._lock:
            if not self.verify_chain(): raise GovernanceRejected("existing design review chain invalid")
            existing = self._by_design.get(design_id)
            if existing is not None: return existing
            previous = self._records[-1].submission_digest if self._records else "0" * 64
            values = {"sequence": len(self._records)+1, "design_id": design.design_id,
                      "design_digest": design.design_digest, "submitted_at": submitted_at.isoformat(),
                      "submission_state": DryRunDesignReviewState.PENDING_ETERNIAN_REVIEW.value,
                      "previous_digest": previous}
            record = SyntheticActivationDryRunDesignReviewRecord(len(self._records)+1, design, submitted_at,
                DryRunDesignReviewState.PENDING_ETERNIAN_REVIEW, previous, canonical_digest(values))
            if before != book.evidence()["report_digest"]: raise GovernanceRejected("dry-run design changed during submission")
            self._records.append(record); self._by_design[design_id] = record; return record

    def record_eternian_review(self, design_id: str, *, review_id: str, reviewer_id: str,
                               decision: DryRunDesignReviewDecision, findings_digest: str,
                               reviewed_at: datetime) -> SyntheticActivationDryRunDesignReviewRecord:
        if (not isinstance(review_id,str) or not review_id.startswith(_REVIEW_PREFIX)
            or not isinstance(reviewer_id,str) or not reviewer_id.startswith(_REVIEWER_PREFIX)
            or not isinstance(decision,DryRunDesignReviewDecision) or not _valid_digest(findings_digest)
            or reviewed_at.tzinfo is None): raise GovernanceRejected("valid Eternian dry-run design review metadata required")
        with self._lock:
            if not self.verify_chain(): raise GovernanceRejected("existing design review chain invalid")
            current = self._by_design.get(design_id)
            if current is None: raise GovernanceRejected("unknown activation dry-run design")
            values = {"design_id": current.design.design_id, "design_digest": current.design.design_digest,
                      "review_id": review_id, "reviewer_id": reviewer_id, "decision": decision.value,
                      "findings_digest": findings_digest, "reviewed_at": reviewed_at.isoformat(),
                      "resulting_state": _STATE_BY_DECISION[decision].value,
                      "dry_run_execution_allowed": False, "activation_allowed": False,
                      "rollback_execution_allowed": False, "production_activation_allowed": False}
            digest = canonical_digest(values)
            if current.state is not DryRunDesignReviewState.PENDING_ETERNIAN_REVIEW:
                if current.review_digest == digest: return current
                raise GovernanceRejected("dry-run design review is immutable")
            updated = SyntheticActivationDryRunDesignReviewRecord(current.sequence,current.design,current.submitted_at,
                _STATE_BY_DECISION[decision],current.previous_digest,current.submission_digest,
                review_id,reviewer_id,decision,findings_digest,reviewed_at,digest)
            self._records[current.sequence-1]=updated; self._by_design[design_id]=updated; return updated

    def ready_source(self, design_id: str) -> SyntheticActivationDryRunDesignReviewRecord:
        with self._lock:
            item=self._by_design.get(design_id)
            if item is None or item.state is not DryRunDesignReviewState.READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_PROPOSAL or not self.verify_chain():
                raise GovernanceRejected("passed dry-run design review required")
            return item

    def verify_chain(self) -> bool:
        with self._lock:
            previous="0"*64
            for sequence,item in enumerate(self._records,1):
                if (item.sequence!=sequence or item.previous_digest!=previous
                    or item.submission_digest!=canonical_digest(item.submission_value())
                    or item.design.design_digest!=canonical_digest(item.design.digest_value())): return False
                previous=item.submission_digest
            return len(self._records)==len(self._by_design) and all(self._by_design.get(i.design.design_id) is i for i in self._records)

    def evidence(self) -> dict[str,object]:
        with self._lock:
            value={"schema":"nurion.pg.synthetic-activation-dry-run-design-review-evidence.v1",
                   "mode":"UNREGISTERED_SYNTHETIC_ONLY","record_count":len(self._records),
                   "submission_digests":[i.submission_digest for i in self._records],
                   "review_digests":[i.review_digest for i in self._records if i.review_digest],
                   "review_chain_valid":self.verify_chain(),"maximum_state":DESIGN_REVIEW_MAXIMUM_STATE,
                   "fixture_production_method_present":False,"dry_run_execution_method_present":False,
                   "activation_method_present":False,"rollback_execution_method_present":False,
                   "filesystem_write_method_present":False,"network_access_method_present":False,
                   "automatic_merge_method_present":False,"automatic_deploy_method_present":False,
                   "credentials_used":False,"personal_data_used":False,"money_movement_executed":False,
                   "production_activation_allowed":False}
            return {**value,"report_digest":canonical_digest(value)}
