"""Synthetic-only feasibility decision docket controls #2501-#2700.

The docket records an inert recommendation over a feasibility portfolio.  It
cannot approve, execute, deploy, pay, settle, mutate a ledger, or change any
runtime policy, prompt, or weight.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest
from .synthetic_proposal_feasibility_assessment import (
    ACCEPTED_RISK_LEVELS,
    MIN_EVIDENCE_COUNT,
    PROPOSAL_KINDS,
    PortfolioObservation,
)


WORKSTREAMS = (
    (2501, 2525, "PORTFOLIO_DOCKET_INTAKE"),
    (2526, 2550, "BOUNDED_DOCKET_BATCH"),
    (2551, 2575, "SOURCE_VERSION_DIGEST_BINDING"),
    (2576, 2600, "NON_AUTHORIZING_DECISION_DRAFT"),
    (2601, 2625, "INDEPENDENT_DOCKET_REVIEW"),
    (2626, 2650, "REPLAY_CONFLICT_AUTO_HOLD"),
    (2651, 2675, "INERT_DOCKET_RECEIPT"),
    (2676, 2700, "APPEND_ONLY_AUDIT_EVIDENCE"),
)
MAX_DOCKET_BATCH = 20
DECISIONS = frozenset({"OBSERVE", "REASSESS", "HOLD"})
HOLD_REASONS = frozenset({"REVIEW_REJECTED", "INTEGRITY_DRIFT"})
MAXIMUM_STATE = "SYNTHETIC_DECISION_DOCKET_RECORDED"


def _synthetic(value: object, namespace: str) -> bool:
    return isinstance(value, str) and value.startswith(f"synthetic:{namespace}:")


def _digest(value: object) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


def _integer(value: object, low: int, high: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


def _identity(value: str) -> str:
    return value.rsplit(":", 1)[-1]


@dataclass(frozen=True)
class DocketRecord:
    portfolio_id: str
    portfolio_digest: str
    source_version: int
    member_count: int
    observer: str
    status: str
    version: int
    analyst: str | None
    decision: str | None
    hold_reason: str | None
    previous_digest: str | None
    digest: str


@dataclass(frozen=True)
class DocketBatch:
    batch_id: str
    requested_limit: int
    portfolio_ids: tuple[str, ...]
    digest: str


@dataclass(frozen=True)
class DecisionDraft:
    draft_id: str
    portfolio_id: str
    source_record_version: int
    resulting_record_version: int
    portfolio_source_version: int
    portfolio_digest: str
    analyst: str
    decision: str
    rationale_digest: str
    non_authorizing: bool
    non_deployable: bool
    non_executable: bool
    digest: str


@dataclass(frozen=True)
class DocketReview:
    review_id: str
    portfolio_id: str
    source_record_version: int
    resulting_record_version: int
    reviewer: str
    accepted: bool
    review_digest: str
    draft_digest: str
    digest: str


@dataclass(frozen=True)
class DocketReceipt:
    receipt_id: str
    portfolio_id: str
    source_record_version: int
    resulting_record_version: int
    verifier: str
    draft_digest: str
    review_digest: str
    non_authorizing: bool
    non_deployable: bool
    non_executable: bool
    digest: str


class SyntheticFeasibilityDecisionDocket:
    """Thread-safe in-memory decision docket with no operational authority."""

    def __init__(self) -> None:
        self._rows: dict[str, DocketRecord] = {}
        self._history: list[DocketRecord] = []
        self._events: list[dict[str, object]] = []
        self._batches: dict[str, DocketBatch] = {}
        self._drafts: dict[str, DecisionDraft] = {}
        self._portfolio_drafts: dict[str, str] = {}
        self._reviews: dict[str, DocketReview] = {}
        self._portfolio_reviews: dict[str, str] = {}
        self._receipts: dict[str, DocketReceipt] = {}
        self._portfolio_receipts: dict[str, str] = {}
        self._used_review_digests: dict[str, str] = {}
        self._holds: list[dict[str, object]] = []
        self._lock = RLock()

    @staticmethod
    def _record_digest(portfolio_id: str, portfolio_digest: str, source_version: int,
                       member_count: int, observer: str, status: str, version: int,
                       analyst: str | None, decision: str | None,
                       hold_reason: str | None, previous_digest: str | None) -> str:
        return canonical_digest({"portfolio_id": portfolio_id,
            "portfolio_digest": portfolio_digest, "source_version": source_version,
            "member_count": member_count, "observer": observer, "status": status,
            "version": version, "analyst": analyst, "decision": decision,
            "hold_reason": hold_reason, "previous_digest": previous_digest})

    def _make(self, portfolio_id: str, portfolio_digest: str, source_version: int,
              member_count: int, observer: str, status: str, version: int,
              analyst: str | None = None, decision: str | None = None,
              hold_reason: str | None = None,
              previous_digest: str | None = None) -> DocketRecord:
        if (not _synthetic(portfolio_id, "feasibility-portfolio")
                or not _digest(portfolio_digest) or not _integer(source_version, 1, 1_000_000)
                or not _integer(member_count, 1, MAX_DOCKET_BATCH)
                or not _synthetic(observer, "portfolio-observer")
                or not _integer(version, 1, 1_000_000)
                or (analyst is not None and not _synthetic(analyst, "docket-analyst"))
                or (decision is not None and decision not in DECISIONS)
                or (hold_reason is not None and hold_reason not in HOLD_REASONS)
                or (previous_digest is not None and not _digest(previous_digest))):
            raise GovernanceRejected("valid synthetic docket record required")
        value = self._record_digest(portfolio_id, portfolio_digest, source_version,
            member_count, observer, status, version, analyst, decision, hold_reason,
            previous_digest)
        return DocketRecord(portfolio_id, portfolio_digest, source_version, member_count,
            observer, status, version, analyst, decision, hold_reason, previous_digest, value)

    def _append(self, action: str, row: DocketRecord,
                attachment: str | None = None) -> DocketRecord:
        previous = self._events[-1]["digest"] if self._events else None
        payload = {"sequence": len(self._events) + 1, "action": action,
            "record_digest": row.digest, "attachment_digest": attachment,
            "previous_digest": previous}
        self._history.append(row)
        self._events.append({**payload, "digest": canonical_digest(payload)})
        self._rows[row.portfolio_id] = row
        return row

    def _transition(self, old: DocketRecord, action: str, status: str, *,
                    analyst: str | None = None, decision: str | None = None,
                    hold_reason: str | None = None,
                    attachment: str | None = None) -> DocketRecord:
        row = self._make(old.portfolio_id, old.portfolio_digest, old.source_version,
            old.member_count, old.observer, status, old.version + 1,
            old.analyst if analyst is None else analyst,
            old.decision if decision is None else decision, hold_reason, old.digest)
        return self._append(action, row, attachment)

    def _require(self, portfolio_id: str, version: int, status: str) -> DocketRecord:
        row = self._rows.get(portfolio_id)
        if row is None or row.version != version or row.status != status:
            raise GovernanceRejected("current synthetic docket state and version required")
        return row

    def intake(self, portfolio_id: str, portfolio_digest: str, source_version: int,
               member_count: int, observer: str) -> DocketRecord:
        with self._lock:
            prior = self._rows.get(portfolio_id)
            fields = (portfolio_digest, source_version, member_count, observer)
            if prior is not None:
                if fields == (prior.portfolio_digest, prior.source_version,
                              prior.member_count, prior.observer):
                    return prior
                raise GovernanceRejected("portfolio docket intake conflict")
            return self._append("DOCKET_INTAKE", self._make(portfolio_id,
                portfolio_digest, source_version, member_count, observer,
                "PORTFOLIO_RECEIVED", 1))

    def intake_observation(self, observation: PortfolioObservation,
                           source_version: int = 1) -> DocketRecord:
        """Verify and intake an actual upstream portfolio observation."""
        if not isinstance(observation, PortfolioObservation):
            raise GovernanceRejected("typed feasibility portfolio observation required")
        payload = {"portfolio_id": observation.portfolio_id,
            "observer": observation.observer, "intent_ids": observation.intent_ids,
            "risk_counts": observation.risk_counts, "kind_counts": observation.kind_counts,
            "all_rollback_possible": observation.all_rollback_possible,
            "minimum_evidence_count": observation.minimum_evidence_count}
        risk_counts = dict(observation.risk_counts)
        kind_counts = dict(observation.kind_counts)
        if (source_version != 1
                or not observation.intent_ids or len(observation.intent_ids) > MAX_DOCKET_BATCH
                or len(set(observation.intent_ids)) != len(observation.intent_ids)
                or not all(_synthetic(value, "decision-intent")
                           for value in observation.intent_ids)
                or len(risk_counts) != len(observation.risk_counts)
                or set(risk_counts) != ACCEPTED_RISK_LEVELS
                or not all(_integer(value, 0, MAX_DOCKET_BATCH)
                           for value in risk_counts.values())
                or sum(risk_counts.values()) != len(observation.intent_ids)
                or len(kind_counts) != len(observation.kind_counts)
                or set(kind_counts) != PROPOSAL_KINDS
                or not all(_integer(value, 0, MAX_DOCKET_BATCH)
                           for value in kind_counts.values())
                or sum(kind_counts.values()) != len(observation.intent_ids)
                or observation.all_rollback_possible is not True
                or not _integer(observation.minimum_evidence_count,
                                MIN_EVIDENCE_COUNT, 1_000_000)
                or observation.digest != canonical_digest(payload)):
            raise GovernanceRejected("integral bounded feasibility observation required")
        return self.intake(observation.portfolio_id, observation.digest, source_version,
                           len(observation.intent_ids), observation.observer)

    def reserve_batch(self, batch_id: str, limit: int) -> DocketBatch:
        if not _synthetic(batch_id, "docket-batch") or not _integer(limit, 1, MAX_DOCKET_BATCH):
            raise GovernanceRejected("bounded synthetic docket batch required")
        with self._lock:
            prior = self._batches.get(batch_id)
            if prior is not None:
                if prior.requested_limit == limit:
                    return prior
                raise GovernanceRejected("docket batch conflict")
            selected = sorted((row for row in self._rows.values()
                if row.status == "PORTFOLIO_RECEIVED"), key=lambda row: row.portfolio_id)[:limit]
            ids = tuple(row.portfolio_id for row in selected)
            payload = {"batch_id": batch_id, "requested_limit": limit, "portfolio_ids": ids}
            batch = DocketBatch(batch_id, limit, ids, canonical_digest(payload))
            self._batches[batch_id] = batch
            for row in selected:
                self._transition(row, "DOCKET_BATCH_RESERVED", "DOCKET_BATCHED",
                                 attachment=batch.digest)
            return batch

    def draft(self, draft_id: str, portfolio_id: str, expected_version: int,
              portfolio_source_version: int, portfolio_digest: str, analyst: str,
              decision: str, rationale_digest: str) -> DocketRecord:
        if (not _synthetic(draft_id, "decision-draft")
                or not _synthetic(analyst, "docket-analyst") or decision not in DECISIONS
                or not _digest(portfolio_digest) or not _digest(rationale_digest)
                or not _integer(portfolio_source_version, 1, 1_000_000)):
            raise GovernanceRejected("valid inert synthetic decision draft required")
        with self._lock:
            prior = self._drafts.get(draft_id)
            fields = (portfolio_id, expected_version, portfolio_source_version,
                      portfolio_digest, analyst, decision, rationale_digest)
            if prior is not None:
                if fields == (prior.portfolio_id, prior.source_record_version,
                    prior.portfolio_source_version, prior.portfolio_digest, prior.analyst,
                    prior.decision, prior.rationale_digest):
                    return self._rows[portfolio_id]
                raise GovernanceRejected("decision draft conflict")
            if portfolio_id in self._portfolio_drafts:
                raise GovernanceRejected("portfolio already has a decision draft")
            old = self._require(portfolio_id, expected_version, "DOCKET_BATCHED")
            if (portfolio_source_version != old.source_version
                    or portfolio_digest != old.portfolio_digest
                    or _identity(analyst) == _identity(old.observer) or not self._integrity()):
                raise GovernanceRejected("source-bound independent analyst required")
            resulting = expected_version + 1
            payload = {"draft_id": draft_id, "portfolio_id": portfolio_id,
                "source_record_version": expected_version,
                "resulting_record_version": resulting,
                "portfolio_source_version": portfolio_source_version,
                "portfolio_digest": portfolio_digest, "analyst": analyst,
                "decision": decision, "rationale_digest": rationale_digest,
                "non_authorizing": True, "non_deployable": True, "non_executable": True}
            artifact = DecisionDraft(draft_id, portfolio_id, expected_version, resulting,
                portfolio_source_version, portfolio_digest, analyst, decision,
                rationale_digest, True, True, True, canonical_digest(payload))
            self._drafts[draft_id] = artifact
            self._portfolio_drafts[portfolio_id] = draft_id
            return self._transition(old, "DECISION_DRAFTED", "DOCKET_DRAFTED",
                analyst=analyst, decision=decision, attachment=artifact.digest)

    def review(self, review_id: str, portfolio_id: str, expected_version: int,
               reviewer: str, accepted: bool, review_digest: str) -> DocketRecord:
        if (not _synthetic(review_id, "docket-review")
                or not _synthetic(reviewer, "docket-reviewer")
                or not isinstance(accepted, bool) or not _digest(review_digest)):
            raise GovernanceRejected("valid independent docket review required")
        with self._lock:
            prior = self._reviews.get(review_id)
            fields = (portfolio_id, expected_version, reviewer, accepted, review_digest)
            if prior is not None:
                if fields == (prior.portfolio_id, prior.source_record_version,
                              prior.reviewer, prior.accepted, prior.review_digest):
                    return self._rows[portfolio_id]
                raise GovernanceRejected("docket review conflict")
            if portfolio_id in self._portfolio_reviews:
                raise GovernanceRejected("portfolio already reviewed")
            old = self._require(portfolio_id, expected_version, "DOCKET_DRAFTED")
            draft = self._drafts.get(self._portfolio_drafts.get(portfolio_id, ""))
            if (draft is None or _identity(reviewer) in {
                    _identity(old.observer), _identity(draft.analyst)} or not self._integrity()):
                raise GovernanceRejected("independent reviewer and integral draft required")
            resulting = expected_version + 1
            payload = {"review_id": review_id, "portfolio_id": portfolio_id,
                "source_record_version": expected_version,
                "resulting_record_version": resulting, "reviewer": reviewer,
                "accepted": accepted, "review_digest": review_digest,
                "draft_digest": draft.digest}
            review = DocketReview(review_id, portfolio_id, expected_version, resulting,
                reviewer, accepted, review_digest, draft.digest, canonical_digest(payload))
            self._reviews[review_id] = review
            self._portfolio_reviews[portfolio_id] = review_id
            if not accepted:
                return self._auto_hold(old, reviewer, "REVIEW_REJECTED", review.digest)
            return self._transition(old, "DOCKET_REVIEWED", "DOCKET_REVIEWED",
                                    attachment=review.digest)

    def record_receipt(self, receipt_id: str, portfolio_id: str, expected_version: int,
                       review_digest: str, verifier: str) -> DocketRecord:
        if (not _synthetic(receipt_id, "docket-receipt") or not _digest(review_digest)
                or not _synthetic(verifier, "docket-verifier")):
            raise GovernanceRejected("valid inert docket receipt required")
        with self._lock:
            prior = self._receipts.get(receipt_id)
            fields = (portfolio_id, expected_version, review_digest, verifier)
            if prior is not None:
                if fields == (prior.portfolio_id, prior.source_record_version,
                              prior.review_digest, prior.verifier):
                    return self._rows[portfolio_id]
                raise GovernanceRejected("docket receipt conflict")
            if portfolio_id in self._portfolio_receipts or review_digest in self._used_review_digests:
                raise GovernanceRejected("docket receipt replay blocked")
            old = self._require(portfolio_id, expected_version, "DOCKET_REVIEWED")
            draft = self._drafts.get(self._portfolio_drafts.get(portfolio_id, ""))
            review = self._reviews.get(self._portfolio_reviews.get(portfolio_id, ""))
            identities = {_identity(old.observer), _identity(draft.analyst) if draft else "",
                          _identity(review.reviewer) if review else ""}
            if (draft is None or review is None or not review.accepted
                    or review.digest != review_digest or review.draft_digest != draft.digest
                    or _identity(verifier) in identities or not self._integrity()):
                raise GovernanceRejected("current independently reviewed docket required")
            resulting = expected_version + 1
            payload = {"receipt_id": receipt_id, "portfolio_id": portfolio_id,
                "source_record_version": expected_version,
                "resulting_record_version": resulting, "verifier": verifier,
                "draft_digest": draft.digest, "review_digest": review.digest,
                "non_authorizing": True, "non_deployable": True, "non_executable": True}
            receipt = DocketReceipt(receipt_id, portfolio_id, expected_version, resulting,
                verifier, draft.digest, review.digest, True, True, True,
                canonical_digest(payload))
            self._receipts[receipt_id] = receipt
            self._portfolio_receipts[portfolio_id] = receipt_id
            self._used_review_digests[review.digest] = portfolio_id
            return self._transition(old, "DOCKET_RECEIPT_RECORDED", MAXIMUM_STATE,
                                    attachment=receipt.digest)

    def _auto_hold(self, old: DocketRecord, actor: str, reason: str,
                   attachment: str) -> DocketRecord:
        row = self._transition(old, "AUTO_HELD", "HELD", hold_reason=reason,
                               attachment=attachment)
        previous = self._holds[-1]["digest"] if self._holds else None
        payload = {"sequence": len(self._holds) + 1, "portfolio_id": old.portfolio_id,
            "reason": reason, "actor": actor, "record_digest": row.digest,
            "attachment_digest": attachment, "previous_digest": previous}
        self._holds.append({**payload, "digest": canonical_digest(payload)})
        return row

    def hold_integrity_drift(self, portfolio_id: str, expected_version: int,
                             auditor: str, finding_digest: str) -> DocketRecord:
        if not _synthetic(auditor, "docket-auditor") or not _digest(finding_digest):
            raise GovernanceRejected("valid independent integrity finding required")
        with self._lock:
            if not self._integrity():
                raise GovernanceRejected("integral docket evidence required")
            old = self._rows.get(portfolio_id)
            if old is None or old.version != expected_version or old.status in {"HELD"}:
                raise GovernanceRejected("current holdable docket required")
            identities = {_identity(old.observer)}
            if old.analyst:
                identities.add(_identity(old.analyst))
            review = self._reviews.get(self._portfolio_reviews.get(portfolio_id, ""))
            receipt = self._receipts.get(self._portfolio_receipts.get(portfolio_id, ""))
            if review:
                identities.add(_identity(review.reviewer))
            if receipt:
                identities.add(_identity(receipt.verifier))
            if _identity(auditor) in identities:
                raise GovernanceRejected("independent docket auditor required")
            return self._auto_hold(old, auditor, "INTEGRITY_DRIFT", finding_digest)

    def get(self, portfolio_id: str) -> DocketRecord:
        return self._rows[portfolio_id]

    def review_receipt(self, review_id: str) -> DocketReview:
        return self._reviews[review_id]

    def receipt(self, receipt_id: str) -> DocketReceipt:
        return self._receipts[receipt_id]

    def _record_integrity(self) -> bool:
        previous: dict[str, str] = {}
        versions: dict[str, int] = {}
        latest: dict[str, DocketRecord] = {}
        for row in self._history:
            prior_version = versions.get(row.portfolio_id, 0)
            prior = latest.get(row.portfolio_id)
            valid_transition = (
                (prior is None and row.status == "PORTFOLIO_RECEIVED")
                or (prior is not None and (
                    (prior.status == "PORTFOLIO_RECEIVED" and row.status == "DOCKET_BATCHED")
                    or (prior.status == "DOCKET_BATCHED" and row.status == "DOCKET_DRAFTED")
                    or (prior.status == "DOCKET_DRAFTED"
                        and row.status in {"DOCKET_REVIEWED", "HELD"})
                    or (prior.status == "DOCKET_REVIEWED"
                        and row.status in {MAXIMUM_STATE, "HELD"})
                    or (prior.status == MAXIMUM_STATE and row.status == "HELD")
                ))
            )
            if (not valid_transition or row.version != prior_version + 1
                    or row.previous_digest != previous.get(row.portfolio_id)
                    or row.digest != self._record_digest(row.portfolio_id,
                    row.portfolio_digest, row.source_version, row.member_count,
                    row.observer, row.status, row.version, row.analyst, row.decision,
                    row.hold_reason, row.previous_digest)):
                return False
            previous[row.portfolio_id] = row.digest
            versions[row.portfolio_id] = row.version
            latest[row.portfolio_id] = row
        return latest == self._rows

    def _event_integrity(self) -> bool:
        if len(self._events) != len(self._history):
            return False
        previous = None
        for sequence, (event, row) in enumerate(zip(self._events, self._history), 1):
            expected_action = {
                "PORTFOLIO_RECEIVED": "DOCKET_INTAKE",
                "DOCKET_BATCHED": "DOCKET_BATCH_RESERVED",
                "DOCKET_DRAFTED": "DECISION_DRAFTED",
                "DOCKET_REVIEWED": "DOCKET_REVIEWED",
                MAXIMUM_STATE: "DOCKET_RECEIPT_RECORDED",
                "HELD": "AUTO_HELD",
            }.get(row.status)
            payload = {"sequence": sequence, "action": event.get("action"),
                "record_digest": row.digest,
                "attachment_digest": event.get("attachment_digest"),
                "previous_digest": previous}
            if (event.get("action") != expected_action
                    or any(event.get(key) != value for key, value in payload.items())) \
                    or event.get("digest") != canonical_digest(payload):
                return False
            previous = event["digest"]
        return True

    def _batch_integrity(self) -> bool:
        seen: set[str] = set()
        for key, batch in self._batches.items():
            payload = {"batch_id": batch.batch_id, "requested_limit": batch.requested_limit,
                       "portfolio_ids": batch.portfolio_ids}
            if (key != batch.batch_id or not _synthetic(key, "docket-batch")
                    or not _integer(batch.requested_limit, 1, MAX_DOCKET_BATCH)
                    or len(batch.portfolio_ids) > batch.requested_limit
                    or len(set(batch.portfolio_ids)) != len(batch.portfolio_ids)
                    or seen.intersection(batch.portfolio_ids)
                    or batch.digest != canonical_digest(payload)):
                return False
            seen.update(batch.portfolio_ids)
        return True

    def _artifact_integrity(self) -> bool:
        history = {(row.portfolio_id, row.version): row for row in self._history}
        for key, draft in self._drafts.items():
            source = history.get((draft.portfolio_id, draft.source_record_version))
            result = history.get((draft.portfolio_id, draft.resulting_record_version))
            payload = {"draft_id": draft.draft_id, "portfolio_id": draft.portfolio_id,
                "source_record_version": draft.source_record_version,
                "resulting_record_version": draft.resulting_record_version,
                "portfolio_source_version": draft.portfolio_source_version,
                "portfolio_digest": draft.portfolio_digest, "analyst": draft.analyst,
                "decision": draft.decision, "rationale_digest": draft.rationale_digest,
                "non_authorizing": True, "non_deployable": True, "non_executable": True}
            if (key != draft.draft_id or self._portfolio_drafts.get(draft.portfolio_id) != key
                    or source is None or source.status != "DOCKET_BATCHED"
                    or result is None or result.status != "DOCKET_DRAFTED"
                    or draft.resulting_record_version != draft.source_record_version + 1
                    or draft.portfolio_source_version != source.source_version
                    or draft.portfolio_digest != source.portfolio_digest
                    or draft.decision not in DECISIONS or not _digest(draft.rationale_digest)
                    or not all((draft.non_authorizing, draft.non_deployable, draft.non_executable))
                    or _identity(draft.analyst) == _identity(source.observer)
                    or draft.digest != canonical_digest(payload)):
                return False
        for key, review in self._reviews.items():
            draft = self._drafts.get(self._portfolio_drafts.get(review.portfolio_id, ""))
            result = history.get((review.portfolio_id, review.resulting_record_version))
            payload = {"review_id": review.review_id, "portfolio_id": review.portfolio_id,
                "source_record_version": review.source_record_version,
                "resulting_record_version": review.resulting_record_version,
                "reviewer": review.reviewer, "accepted": review.accepted,
                "review_digest": review.review_digest, "draft_digest": review.draft_digest}
            if (key != review.review_id or draft is None
                    or self._portfolio_reviews.get(review.portfolio_id) != key
                    or review.source_record_version != draft.resulting_record_version
                    or review.resulting_record_version != review.source_record_version + 1
                    or review.draft_digest != draft.digest or not _digest(review.review_digest)
                    or _identity(review.reviewer) in {_identity(draft.analyst),
                        _identity(self._rows[review.portfolio_id].observer)}
                    or result is None or result.status != ("DOCKET_REVIEWED" if review.accepted else "HELD")
                    or review.digest != canonical_digest(payload)):
                return False
        for key, receipt in self._receipts.items():
            draft = self._drafts.get(self._portfolio_drafts.get(receipt.portfolio_id, ""))
            review = self._reviews.get(self._portfolio_reviews.get(receipt.portfolio_id, ""))
            result = history.get((receipt.portfolio_id, receipt.resulting_record_version))
            payload = {"receipt_id": receipt.receipt_id, "portfolio_id": receipt.portfolio_id,
                "source_record_version": receipt.source_record_version,
                "resulting_record_version": receipt.resulting_record_version,
                "verifier": receipt.verifier, "draft_digest": receipt.draft_digest,
                "review_digest": receipt.review_digest, "non_authorizing": True,
                "non_deployable": True, "non_executable": True}
            if (key != receipt.receipt_id or draft is None or review is None or not review.accepted
                    or self._portfolio_receipts.get(receipt.portfolio_id) != key
                    or receipt.draft_digest != draft.digest or receipt.review_digest != review.digest
                    or receipt.source_record_version != review.resulting_record_version
                    or receipt.resulting_record_version != receipt.source_record_version + 1
                    or result is None or result.status != MAXIMUM_STATE
                    or not all((receipt.non_authorizing, receipt.non_deployable, receipt.non_executable))
                    or _identity(receipt.verifier) in {_identity(draft.analyst),
                        _identity(review.reviewer), _identity(result.observer)}
                    or self._used_review_digests.get(review.digest) != receipt.portfolio_id
                    or receipt.digest != canonical_digest(payload)):
                return False
        return True

    def _hold_integrity(self) -> bool:
        previous = None
        for sequence, hold in enumerate(self._holds, 1):
            payload = {"sequence": sequence, "portfolio_id": hold.get("portfolio_id"),
                "reason": hold.get("reason"), "actor": hold.get("actor"),
                "record_digest": hold.get("record_digest"),
                "attachment_digest": hold.get("attachment_digest"),
                "previous_digest": previous}
            row = next((item for item in self._history
                        if item.digest == hold.get("record_digest")), None)
            event = next((item for item in self._events
                          if item.get("record_digest") == hold.get("record_digest")), None)
            identities: set[str] = set()
            if row is not None:
                identities.add(_identity(row.observer))
                if row.analyst:
                    identities.add(_identity(row.analyst))
                review = self._reviews.get(self._portfolio_reviews.get(row.portfolio_id, ""))
                receipt = self._receipts.get(self._portfolio_receipts.get(row.portfolio_id, ""))
                if review:
                    identities.add(_identity(review.reviewer))
                if receipt:
                    identities.add(_identity(receipt.verifier))
            independent_auditor = (hold.get("reason") != "INTEGRITY_DRIFT"
                or (_synthetic(hold.get("actor"), "docket-auditor")
                    and _identity(str(hold.get("actor"))) not in identities))
            if (hold.get("reason") not in HOLD_REASONS
                    or row is None or row.status != "HELD"
                    or row.hold_reason != hold.get("reason")
                    or event is None or event.get("action") != "AUTO_HELD"
                    or event.get("attachment_digest") != hold.get("attachment_digest")
                    or not independent_auditor
                    or any(hold.get(key) != value for key, value in payload.items())
                    or hold.get("digest") != canonical_digest(payload)):
                return False
            previous = hold["digest"]
        return True

    def _integrity(self) -> bool:
        return (self._record_integrity() and self._event_integrity()
                and self._batch_integrity() and self._artifact_integrity()
                and self._hold_integrity())

    def capability_gap_evidence(self) -> dict[str, object]:
        """Return deterministic, read-only self-assessment for independent audit."""
        expected = set(range(2501, 2701))
        observed: list[int] = []
        malformed = False
        for start, end, _ in WORKSTREAMS:
            if start > end:
                malformed = True
            observed.extend(range(start, end + 1))
        observed_set = set(observed)
        missing = tuple(sorted(expected - observed_set))
        unexpected = tuple(sorted(observed_set - expected))
        duplicates = tuple(sorted(value for value in observed_set
                                  if observed.count(value) > 1))
        integrity = self._integrity()
        gaps: list[str] = []
        if malformed or missing or unexpected or duplicates or len(WORKSTREAMS) != 8:
            gaps.append("CONTROL_MATRIX_GAP")
        if not integrity:
            gaps.append("INTEGRITY_OBSERVABILITY_GAP")
        boundaries = {
            "synthetic_only": True, "in_memory_only": True,
            "non_authorizing": True, "non_deployable": True,
            "non_executable": True, "external_calls": 0,
            "production_credentials": False, "ledger_writes": 0,
            "runtime_policy_mutations": 0,
        }
        payload = {"expected_range": [2501, 2700], "expected_count": 200,
            "observed_count": len(observed), "missing_controls": missing,
            "unexpected_controls": unexpected, "duplicate_controls": duplicates,
            "workstream_count": len(WORKSTREAMS), "integrity_valid": integrity,
            "boundaries": boundaries, "capability_gaps": tuple(gaps),
            "fail_closed": bool(gaps), "audit_observable": True}
        return {**payload, "digest": canonical_digest(payload)}

    def evidence(self) -> dict[str, object]:
        with self._lock:
            integral = self._integrity()
            capability = self.capability_gap_evidence()
            return {"control_range": [2501, 2700], "control_count": 200,
                "workstreams": [list(item) for item in WORKSTREAMS],
                "workstream_count": len(WORKSTREAMS),
                "exactly_25_controls_per_workstream": all(
                    end - start + 1 == 25 for start, end, _ in WORKSTREAMS),
                "synthetic_only": True, "storage": "memory",
                "external_calls": 0, "production_credentials": False,
                "ledger_writes": 0, "runtime_policy_mutations": 0,
                "maximum_batch": MAX_DOCKET_BATCH, "maximum_state": MAXIMUM_STATE,
                "decision_allowlist": sorted(DECISIONS),
                "record_count": len(self._rows), "history_count": len(self._history),
                "event_count": len(self._events), "hold_count": len(self._holds),
                "receipt_count": len(self._receipts),
                "record_integrity_valid": self._record_integrity(),
                "event_chain_valid": self._event_integrity(),
                "batch_integrity_valid": self._batch_integrity(),
                "artifact_integrity_valid": self._artifact_integrity(),
                "hold_chain_valid": self._hold_integrity(),
                "integrity_valid": integral,
                "capability_gap_evidence": capability,
                "capability_ready": not capability["fail_closed"],
                "non_authorizing": True, "non_deployable": True,
                "non_executable": True,
                "evidence_digest": canonical_digest({"rows": sorted(
                    (key, row.digest) for key, row in self._rows.items()),
                    "events": [event["digest"] for event in self._events],
                    "holds": [hold["digest"] for hold in self._holds],
                    "integrity": integral})}
