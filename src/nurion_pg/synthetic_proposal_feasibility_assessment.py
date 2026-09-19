"""Synthetic-only proposal feasibility controls #2101-#2500.

An intent is an inert observation.  It is never an approval, authorization,
deployment instruction, payment instruction, or runtime-policy mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest


WORKSTREAMS = (
    (2101, 2125, "RECORDED_PROPOSAL_INTAKE"),
    (2126, 2150, "BOUNDED_ASSESSMENT_BATCH"),
    (2151, 2175, "DEPENDENCY_ASSESSMENT"),
    (2176, 2200, "RISK_ROLLBACK_ASSESSMENT"),
    (2201, 2225, "EVIDENCE_SUFFICIENCY"),
    (2226, 2250, "INDEPENDENT_ASSESSMENT_REVIEW"),
    (2251, 2275, "REJECTION_INTEGRITY_AUTO_HOLD"),
    (2276, 2300, "FEASIBILITY_RECEIPT_AUDIT"),
    (2301, 2325, "PORTFOLIO_INTAKE"),
    (2326, 2350, "BOUNDED_PORTFOLIO_BATCH"),
    (2351, 2375, "PORTFOLIO_DEPENDENCY_COHORT"),
    (2376, 2400, "PORTFOLIO_RISK_COHORT"),
    (2401, 2425, "PORTFOLIO_ROLLBACK_COHORT"),
    (2426, 2450, "INDEPENDENT_PORTFOLIO_REVIEW"),
    (2451, 2475, "PORTFOLIO_REPLAY_AUTO_HOLD"),
    (2476, 2500, "PORTFOLIO_AUDIT_EVIDENCE"),
)
MAX_PROPOSAL_BATCH = 20
PROPOSAL_KINDS = frozenset({
    "SELF_CONTAINED",
    "BOUNDED_INTERNAL",
    "SYNTHETIC_FIXTURE_ONLY",
})
RISK_LEVELS = frozenset({"LOW", "MEDIUM", "HIGH"})
ACCEPTED_RISK_LEVELS = frozenset({"LOW", "MEDIUM"})
MIN_EVIDENCE_COUNT = 2
HOLD_REASONS = frozenset({"REVIEW_REJECTED", "INTEGRITY_DRIFT"})


def _synthetic(value: object, namespace: str) -> bool:
    return isinstance(value, str) and value.startswith(f"synthetic:{namespace}:")


def _digest(value: object) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(c in "0123456789abcdef" for c in value))


def _integer(value: object, low: int, high: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


def _identity(value: str) -> str:
    return value.rsplit(":", 1)[-1]


@dataclass(frozen=True)
class ProposalRecord:
    intent_id: str
    intent_digest: str
    status: str
    version: int
    planner: str | None
    proposal_kind: str | None
    hold_reason: str | None
    previous_digest: str | None
    digest: str


@dataclass(frozen=True)
class ProposalBatch:
    batch_id: str
    requested_limit: int
    intent_ids: tuple[str, ...]
    digest: str


@dataclass(frozen=True)
class PlanningProposal:
    proposal_id: str
    intent_id: str
    source_version: int
    resulting_version: int
    planner: str
    proposal_kind: str
    rationale_digest: str
    risk_level: str
    rollback_possible: bool
    evidence_count: int
    intent_digest: str
    non_authorizing: bool
    non_deployable: bool
    non_executable: bool
    digest: str


@dataclass(frozen=True)
class ProposalReview:
    review_id: str
    intent_id: str
    source_version: int
    resulting_version: int
    reviewer: str
    accepted: bool
    review_digest: str
    proposal_digest: str
    digest: str


@dataclass(frozen=True)
class ProposalReceipt:
    receipt_id: str
    intent_id: str
    source_version: int
    resulting_version: int
    verifier: str
    proposal_digest: str
    review_digest: str
    non_authorizing: bool
    non_deployable: bool
    non_executable: bool
    digest: str


@dataclass(frozen=True)
class IntegrityFinding:
    finding_id: str
    intent_id: str
    source_version: int
    resulting_version: int
    auditor: str
    finding_digest: str
    digest: str


@dataclass(frozen=True)
class PortfolioObservation:
    portfolio_id: str
    observer: str
    intent_ids: tuple[str, ...]
    risk_counts: tuple[tuple[str, int], ...]
    kind_counts: tuple[tuple[str, int], ...]
    all_rollback_possible: bool
    minimum_evidence_count: int
    digest: str


class SyntheticProposalFeasibilityAssessment:
    """Thread-safe append-only model for inert intent planning proposals."""

    def __init__(self) -> None:
        self._rows: dict[str, ProposalRecord] = {}
        self._history: list[ProposalRecord] = []
        self._events: list[dict[str, object]] = []
        self._batches: dict[str, ProposalBatch] = {}
        self._proposals: dict[str, PlanningProposal] = {}
        self._intent_proposals: dict[str, str] = {}
        self._reviews: dict[str, ProposalReview] = {}
        self._intent_reviews: dict[str, str] = {}
        self._receipts: dict[str, ProposalReceipt] = {}
        self._intent_receipts: dict[str, str] = {}
        self._used_review_digests: dict[str, str] = {}
        self._findings: dict[str, IntegrityFinding] = {}
        self._intent_findings: dict[str, str] = {}
        self._holds: list[dict[str, object]] = []
        self._portfolios: dict[str, PortfolioObservation] = {}
        self._portfolio_members: dict[str, str] = {}
        self._lock = RLock()

    @staticmethod
    def _record_digest(intent_id: str, intent_digest: str, status: str, version: int,
                       planner: str | None, proposal_kind: str | None,
                       hold_reason: str | None, previous_digest: str | None) -> str:
        return canonical_digest({"intent_id": intent_id, "intent_digest": intent_digest,
            "status": status, "version": version, "planner": planner,
            "proposal_kind": proposal_kind, "hold_reason": hold_reason,
            "previous_digest": previous_digest})

    def _make(self, intent_id: str, intent_digest: str, status: str, version: int,
              planner: str | None = None, proposal_kind: str | None = None,
              hold_reason: str | None = None,
              previous_digest: str | None = None) -> ProposalRecord:
        if (not _synthetic(intent_id, "decision-intent") or not _digest(intent_digest)
                or not _integer(version, 1, 1_000_000)
                or (planner is not None and not _synthetic(planner, "planner"))
                or (proposal_kind is not None and proposal_kind not in PROPOSAL_KINDS)
                or (hold_reason is not None and hold_reason not in HOLD_REASONS)
                or (previous_digest is not None and not _digest(previous_digest))):
            raise GovernanceRejected("valid synthetic proposal record required")
        value = self._record_digest(intent_id, intent_digest, status, version, planner,
                                    proposal_kind, hold_reason, previous_digest)
        return ProposalRecord(intent_id, intent_digest, status, version, planner,
                            proposal_kind, hold_reason, previous_digest, value)

    def _append(self, action: str, row: ProposalRecord,
                attachment: str | None = None) -> ProposalRecord:
        previous = self._events[-1]["digest"] if self._events else None
        payload = {"sequence": len(self._events) + 1, "action": action,
                   "record_digest": row.digest, "attachment_digest": attachment,
                   "previous_digest": previous}
        self._history.append(row)
        self._events.append({**payload, "digest": canonical_digest(payload)})
        self._rows[row.intent_id] = row
        return row

    def _transition(self, old: ProposalRecord, action: str, status: str, *,
                    planner: str | None = None, proposal_kind: str | None = None,
                    hold_reason: str | None = None,
                    attachment: str | None = None) -> ProposalRecord:
        row = self._make(old.intent_id, old.intent_digest, status, old.version + 1,
            old.planner if planner is None else planner,
            old.proposal_kind if proposal_kind is None else proposal_kind,
            hold_reason, old.digest)
        return self._append(action, row, attachment)

    def _require(self, intent_id: str, version: int, status: str) -> ProposalRecord:
        row = self._rows.get(intent_id)
        if row is None or row.version != version or row.status != status:
            raise GovernanceRejected("current synthetic proposal state and version required")
        return row

    def intake(self, intent_id: str, intent_digest: str) -> ProposalRecord:
        with self._lock:
            prior = self._rows.get(intent_id)
            if prior:
                if prior.intent_digest == intent_digest:
                    return prior
                raise GovernanceRejected("recorded intent intake conflict")
            return self._append("INTAKE", self._make(
                intent_id, intent_digest, "INTENT_RECEIVED", 1))

    def reserve_batch(self, batch_id: str, limit: int) -> ProposalBatch:
        if not _synthetic(batch_id, "proposal-batch") or not _integer(limit, 1, MAX_PROPOSAL_BATCH):
            raise GovernanceRejected("bounded synthetic proposal batch required")
        with self._lock:
            prior = self._batches.get(batch_id)
            if prior:
                if prior.requested_limit == limit:
                    return prior
                raise GovernanceRejected("proposal batch conflict")
            selected = sorted((r for r in self._rows.values() if r.status == "INTENT_RECEIVED"),
                              key=lambda r: (r.version, r.intent_id))[:limit]
            intent_ids = tuple(r.intent_id for r in selected)
            value = canonical_digest({"batch_id": batch_id, "requested_limit": limit,
                                      "intent_ids": intent_ids})
            batch = ProposalBatch(batch_id, limit, intent_ids, value)
            self._batches[batch_id] = batch
            for row in selected:
                self._transition(row, "PROPOSAL_BATCH_RESERVED", "PROPOSAL_BATCHED", attachment=value)
            return batch

    def propose(self, proposal_id: str, intent_id: str, expected_version: int, planner: str,
              proposal_kind: str, rationale_digest: str, risk_level: str = "LOW",
              rollback_possible: bool = True,
              evidence_count: int = MIN_EVIDENCE_COUNT) -> ProposalRecord:
        if (not _synthetic(proposal_id, "planning-proposal") or not _synthetic(planner, "planner")
                or proposal_kind not in PROPOSAL_KINDS or not _digest(rationale_digest)
                or risk_level not in RISK_LEVELS or not isinstance(rollback_possible, bool)
                or not _integer(evidence_count, 0, 100)):
            raise GovernanceRejected("valid inert synthetic planning proposal required")
        with self._lock:
            prior = self._proposals.get(proposal_id)
            fields = (intent_id, expected_version, planner, proposal_kind, rationale_digest,
                      risk_level, rollback_possible, evidence_count)
            if prior:
                if fields == (prior.intent_id, prior.source_version, prior.planner,
                              prior.proposal_kind, prior.rationale_digest, prior.risk_level,
                              prior.rollback_possible, prior.evidence_count):
                    return self._rows[intent_id]
                raise GovernanceRejected("planning proposal conflict")
            if intent_id in self._intent_proposals:
                raise GovernanceRejected("intent already has a planning proposal")
            old = self._require(intent_id, expected_version, "PROPOSAL_BATCHED")
            if risk_level == "HIGH" or not rollback_possible or evidence_count < MIN_EVIDENCE_COUNT:
                raise GovernanceRejected("bounded risk, rollback and sufficient evidence required")
            if not self._integrity():
                raise GovernanceRejected("integral synthetic evidence required")
            resulting = expected_version + 1
            value = canonical_digest({"proposal_id": proposal_id, "intent_id": intent_id,
                "source_version": expected_version, "resulting_version": resulting,
                "planner": planner, "proposal_kind": proposal_kind,
                "rationale_digest": rationale_digest, "risk_level": risk_level,
                "rollback_possible": rollback_possible, "evidence_count": evidence_count,
                "intent_digest": old.intent_digest,
                "non_authorizing": True, "non_deployable": True,
                "non_executable": True})
            propose = PlanningProposal(proposal_id, intent_id, expected_version, resulting, planner,
                proposal_kind, rationale_digest, risk_level, rollback_possible, evidence_count,
                old.intent_digest, True, True, True, value)
            self._proposals[proposal_id] = propose
            self._intent_proposals[intent_id] = proposal_id
            return self._transition(old, "PROPOSAL_DRAFTED", "PROPOSAL_DRAFTED",
                planner=planner, proposal_kind=proposal_kind, attachment=value)

    def review(self, review_id: str, intent_id: str, expected_version: int, reviewer: str,
               accepted: bool, review_digest: str) -> ProposalRecord:
        if (not _synthetic(review_id, "proposal-review") or not _synthetic(reviewer, "reviewer")
                or not isinstance(accepted, bool) or not _digest(review_digest)):
            raise GovernanceRejected("valid independent synthetic review required")
        with self._lock:
            prior = self._reviews.get(review_id)
            fields = (intent_id, expected_version, reviewer, accepted, review_digest)
            if prior:
                if fields == (prior.intent_id, prior.source_version, prior.reviewer,
                              prior.accepted, prior.review_digest):
                    return self._rows[intent_id]
                raise GovernanceRejected("proposal review conflict")
            if intent_id in self._intent_reviews:
                raise GovernanceRejected("intent already has an proposal review")
            old = self._require(intent_id, expected_version, "PROPOSAL_DRAFTED")
            propose = self._proposals.get(self._intent_proposals.get(intent_id, ""))
            if propose is None or _identity(reviewer) == _identity(propose.planner) or not self._integrity():
                raise GovernanceRejected("independent reviewer and integral propose required")
            resulting = expected_version + 1
            value = canonical_digest({"review_id": review_id, "intent_id": intent_id,
                "source_version": expected_version, "resulting_version": resulting,
                "reviewer": reviewer, "accepted": accepted, "review_digest": review_digest,
                "proposal_digest": propose.digest})
            review = ProposalReview(review_id, intent_id, expected_version, resulting, reviewer,
                                  accepted, review_digest, propose.digest, value)
            self._reviews[review_id] = review
            self._intent_reviews[intent_id] = review_id
            if not accepted:
                return self._auto_hold(old, reviewer, "REVIEW_REJECTED", value)
            return self._transition(old, "PROPOSAL_REVIEWED", "PROPOSAL_REVIEWED", attachment=value)

    def record_receipt(self, receipt_id: str, intent_id: str, expected_version: int,
                       review_digest: str, verifier: str) -> ProposalRecord:
        if (not _synthetic(receipt_id, "proposal-receipt") or not _digest(review_digest)
                or not _synthetic(verifier, "verifier")):
            raise GovernanceRejected("valid inert synthetic proposal receipt required")
        with self._lock:
            prior = self._receipts.get(receipt_id)
            fields = (intent_id, expected_version, review_digest, verifier)
            if prior:
                if fields == (prior.intent_id, prior.source_version, prior.review_digest, prior.verifier):
                    return self._rows[intent_id]
                raise GovernanceRejected("proposal receipt conflict")
            if intent_id in self._intent_receipts or review_digest in self._used_review_digests:
                raise GovernanceRejected("proposal receipt reuse blocked")
            old = self._require(intent_id, expected_version, "PROPOSAL_REVIEWED")
            propose = self._proposals.get(self._intent_proposals.get(intent_id, ""))
            review = self._reviews.get(self._intent_reviews.get(intent_id, ""))
            if (propose is None or review is None or not review.accepted
                    or review.digest != review_digest or review.intent_id != intent_id
                    or _identity(verifier) in {_identity(propose.planner), _identity(review.reviewer)}
                    or not self._integrity()):
                raise GovernanceRejected("current integral independently reviewed intent required")
            resulting = expected_version + 1
            value = canonical_digest({"receipt_id": receipt_id, "intent_id": intent_id,
                "source_version": expected_version, "resulting_version": resulting,
                "verifier": verifier, "proposal_digest": propose.digest,
                "review_digest": review.digest, "non_authorizing": True,
                "non_deployable": True, "non_executable": True})
            receipt = ProposalReceipt(receipt_id, intent_id, expected_version, resulting, verifier,
                                    propose.digest, review.digest, True, True, True, value)
            self._receipts[receipt_id] = receipt
            self._intent_receipts[intent_id] = receipt_id
            self._used_review_digests[review.digest] = intent_id
            return self._transition(old, "PROPOSAL_RECORDED", "SYNTHETIC_FEASIBILITY_RECORDED",
                                    attachment=value)

    def _auto_hold(self, old: ProposalRecord, actor: str, reason: str,
                   attachment: str) -> ProposalRecord:
        row = self._transition(old, "AUTO_HELD", "HELD", hold_reason=reason,
                               attachment=attachment)
        previous = self._holds[-1]["digest"] if self._holds else None
        payload = {"sequence": len(self._holds) + 1, "intent_id": old.intent_id,
                   "reason": reason, "actor": actor, "record_digest": row.digest,
                   "attachment_digest": attachment, "previous_digest": previous}
        self._holds.append({**payload, "digest": canonical_digest(payload)})
        return row

    def hold_integrity_drift(self, finding_id: str, intent_id: str, expected_version: int,
                             auditor: str, finding_digest: str) -> ProposalRecord:
        if (not _synthetic(finding_id, "integrity-finding")
                or not _synthetic(auditor, "auditor") or not _digest(finding_digest)):
            raise GovernanceRejected("valid synthetic integrity finding required")
        with self._lock:
            prior = self._findings.get(finding_id)
            fields = (intent_id, expected_version, auditor, finding_digest)
            if prior:
                if fields == (prior.intent_id, prior.source_version, prior.auditor,
                              prior.finding_digest):
                    return self._rows[intent_id]
                raise GovernanceRejected("integrity finding conflict")
            if intent_id in self._intent_findings or not self._integrity():
                raise GovernanceRejected("unique finding over integral evidence required")
            old = self._rows.get(intent_id)
            if old is None or old.version != expected_version or old.status not in {
                    "PROPOSAL_BATCHED", "PROPOSAL_DRAFTED", "PROPOSAL_REVIEWED",
                    "SYNTHETIC_FEASIBILITY_RECORDED"}:
                raise GovernanceRejected("holdable current synthetic proposal required")
            review = self._reviews.get(self._intent_reviews.get(intent_id, ""))
            receipt = self._receipts.get(self._intent_receipts.get(intent_id, ""))
            identities = {
                _identity(value) for value in (
                    old.planner,
                    review.reviewer if review is not None else None,
                    receipt.verifier if receipt is not None else None,
                ) if value is not None
            }
            if _identity(auditor) in identities:
                raise GovernanceRejected("independent synthetic auditor required")
            resulting = expected_version + 1
            value = canonical_digest({"finding_id": finding_id, "intent_id": intent_id,
                "source_version": expected_version, "resulting_version": resulting,
                "auditor": auditor, "finding_digest": finding_digest})
            finding = IntegrityFinding(finding_id, intent_id, expected_version,
                                       resulting, auditor, finding_digest, value)
            self._findings[finding_id] = finding
            self._intent_findings[intent_id] = finding_id
            return self._auto_hold(old, auditor, "INTEGRITY_DRIFT", value)

    def observe_portfolio(self, portfolio_id: str, observer: str,
                          limit: int) -> PortfolioObservation:
        if (not _synthetic(portfolio_id, "feasibility-portfolio")
                or not _synthetic(observer, "portfolio-observer")
                or not _integer(limit, 1, MAX_PROPOSAL_BATCH)):
            raise GovernanceRejected("bounded synthetic feasibility portfolio required")
        with self._lock:
            prior = self._portfolios.get(portfolio_id)
            if prior is not None:
                if prior.observer == observer and len(prior.intent_ids) <= limit:
                    return prior
                raise GovernanceRejected("feasibility portfolio conflict")
            if not self._integrity():
                raise GovernanceRejected("integral feasibility evidence required")
            candidates = sorted(
                (row for row in self._rows.values()
                 if row.status == "SYNTHETIC_FEASIBILITY_RECORDED"
                 and row.intent_id not in self._portfolio_members),
                key=lambda row: row.intent_id,
            )[:limit]
            if not candidates:
                raise GovernanceRejected("recorded feasibility members required")
            intent_ids = tuple(row.intent_id for row in candidates)
            artifacts = [
                self._proposals[self._intent_proposals[intent_id]]
                for intent_id in intent_ids
            ]
            for intent_id, artifact in zip(intent_ids, artifacts):
                review = self._reviews[self._intent_reviews[intent_id]]
                receipt = self._receipts[self._intent_receipts[intent_id]]
                if _identity(observer) in {
                    _identity(artifact.planner), _identity(review.reviewer),
                    _identity(receipt.verifier),
                }:
                    raise GovernanceRejected("independent portfolio observer required")
            risk_counts = tuple(sorted(
                (risk, sum(item.risk_level == risk for item in artifacts))
                for risk in ACCEPTED_RISK_LEVELS
            ))
            kind_counts = tuple(sorted(
                (kind, sum(item.proposal_kind == kind for item in artifacts))
                for kind in PROPOSAL_KINDS
            ))
            all_rollback = all(item.rollback_possible for item in artifacts)
            minimum_evidence = min(item.evidence_count for item in artifacts)
            payload = {
                "portfolio_id": portfolio_id, "observer": observer,
                "intent_ids": intent_ids, "risk_counts": risk_counts,
                "kind_counts": kind_counts,
                "all_rollback_possible": all_rollback,
                "minimum_evidence_count": minimum_evidence,
            }
            observation = PortfolioObservation(
                portfolio_id, observer, intent_ids, risk_counts, kind_counts,
                all_rollback, minimum_evidence, canonical_digest(payload),
            )
            self._portfolios[portfolio_id] = observation
            for intent_id in intent_ids:
                self._portfolio_members[intent_id] = portfolio_id
            return observation

    def get(self, intent_id: str) -> ProposalRecord:
        return self._rows[intent_id]

    def receipt(self, receipt_id: str) -> ProposalReceipt:
        return self._receipts[receipt_id]

    def review_receipt(self, review_id: str) -> ProposalReview:
        return self._reviews[review_id]

    def _record_integrity(self) -> bool:
        previous: dict[str, str] = {}
        versions: dict[str, int] = {}
        latest: dict[str, ProposalRecord] = {}
        for row in self._history:
            if (row.version != versions.get(row.intent_id, 0) + 1
                    or row.previous_digest != previous.get(row.intent_id)
                    or row.digest != self._record_digest(row.intent_id, row.intent_digest,
                    row.status, row.version, row.planner, row.proposal_kind,
                    row.hold_reason, row.previous_digest)):
                return False
            previous[row.intent_id] = row.digest
            versions[row.intent_id] = row.version
            latest[row.intent_id] = row
        return latest == self._rows

    def _batch_integrity(self) -> bool:
        seen: set[str] = set()
        for key, batch in self._batches.items():
            if (key != batch.batch_id or not _synthetic(key, "proposal-batch")
                    or not _integer(batch.requested_limit, 1, MAX_PROPOSAL_BATCH)
                    or len(batch.intent_ids) > batch.requested_limit
                    or len(set(batch.intent_ids)) != len(batch.intent_ids)
                    or seen.intersection(batch.intent_ids)
                    or batch.digest != canonical_digest({"batch_id": batch.batch_id,
                       "requested_limit": batch.requested_limit, "intent_ids": batch.intent_ids})):
                return False
            seen.update(batch.intent_ids)
        return True

    def _artifact_integrity(self) -> bool:
        history = {(row.intent_id, row.version): row for row in self._history}
        for key, propose in self._proposals.items():
            source = history.get((propose.intent_id, propose.source_version))
            result = history.get((propose.intent_id, propose.resulting_version))
            if (key != propose.proposal_id or not _synthetic(propose.proposal_id, "planning-proposal")
                    or self._intent_proposals.get(propose.intent_id) != key
                    or propose.proposal_kind not in PROPOSAL_KINDS or not propose.non_authorizing
                    or propose.risk_level not in {"LOW", "MEDIUM"}
                    or not propose.rollback_possible
                    or propose.evidence_count < MIN_EVIDENCE_COUNT
                    or not propose.non_deployable or not propose.non_executable
                    or not _synthetic(propose.planner, "planner")
                    or not _digest(propose.rationale_digest) or not _digest(propose.intent_digest)
                    or propose.resulting_version != propose.source_version + 1
                    or source is None or source.status != "PROPOSAL_BATCHED"
                    or source.intent_digest != propose.intent_digest
                    or result is None or result.status != "PROPOSAL_DRAFTED"
                    or result.planner != propose.planner or result.proposal_kind != propose.proposal_kind
                    or propose.digest != canonical_digest({"proposal_id": propose.proposal_id,
                    "intent_id": propose.intent_id, "source_version": propose.source_version,
                    "resulting_version": propose.resulting_version, "planner": propose.planner,
                    "proposal_kind": propose.proposal_kind, "rationale_digest": propose.rationale_digest,
                    "risk_level": propose.risk_level,
                    "rollback_possible": propose.rollback_possible,
                    "evidence_count": propose.evidence_count,
                    "intent_digest": propose.intent_digest,
                    "non_authorizing": True, "non_deployable": True,
                    "non_executable": True})):
                return False
        for key, review in self._reviews.items():
            propose = self._proposals.get(self._intent_proposals.get(review.intent_id, ""))
            result = history.get((review.intent_id, review.resulting_version))
            if (key != review.review_id or not _synthetic(review.review_id, "proposal-review")
                    or propose is None
                    or self._intent_reviews.get(review.intent_id) != key
                    or review.source_version != propose.resulting_version
                    or review.resulting_version != review.source_version + 1
                    or review.proposal_digest != propose.digest
                    or not _synthetic(review.reviewer, "reviewer")
                    or not isinstance(review.accepted, bool) or not _digest(review.review_digest)
                    or _identity(review.reviewer) == _identity(propose.planner)
                    or result is None
                    or result.status != ("PROPOSAL_REVIEWED" if review.accepted else "HELD")
                    or review.digest != canonical_digest({"review_id": review.review_id,
                    "intent_id": review.intent_id, "source_version": review.source_version,
                    "resulting_version": review.resulting_version, "reviewer": review.reviewer,
                    "accepted": review.accepted, "review_digest": review.review_digest,
                    "proposal_digest": review.proposal_digest})):
                return False
        for key, receipt in self._receipts.items():
            propose = self._proposals.get(self._intent_proposals.get(receipt.intent_id, ""))
            review = self._reviews.get(self._intent_reviews.get(receipt.intent_id, ""))
            result = history.get((receipt.intent_id, receipt.resulting_version))
            if (key != receipt.receipt_id or not _synthetic(receipt.receipt_id, "proposal-receipt")
                    or propose is None or review is None or not review.accepted
                    or self._intent_receipts.get(receipt.intent_id) != key
                    or receipt.source_version != review.resulting_version
                    or receipt.resulting_version != receipt.source_version + 1
                    or receipt.proposal_digest != propose.digest or receipt.review_digest != review.digest
                    or not receipt.non_authorizing or not receipt.non_deployable
                    or not receipt.non_executable
                    or not _synthetic(receipt.verifier, "verifier")
                    or result is None or result.status != "SYNTHETIC_FEASIBILITY_RECORDED"
                    or _identity(receipt.verifier) in {
                        _identity(propose.planner), _identity(review.reviewer)}
                    or receipt.digest != canonical_digest({"receipt_id": receipt.receipt_id,
                    "intent_id": receipt.intent_id, "source_version": receipt.source_version,
                    "resulting_version": receipt.resulting_version, "verifier": receipt.verifier,
                    "proposal_digest": receipt.proposal_digest, "review_digest": receipt.review_digest,
                    "non_authorizing": True, "non_deployable": True,
                    "non_executable": True})):
                return False
        for key, finding in self._findings.items():
            source = history.get((finding.intent_id, finding.source_version))
            result = history.get((finding.intent_id, finding.resulting_version))
            review = self._reviews.get(self._intent_reviews.get(finding.intent_id, ""))
            receipt = self._receipts.get(self._intent_receipts.get(finding.intent_id, ""))
            if (key != finding.finding_id or not _synthetic(finding.finding_id, "integrity-finding")
                    or self._intent_findings.get(finding.intent_id) != key
                    or finding.resulting_version != finding.source_version + 1
                    or not _synthetic(finding.auditor, "auditor")
                    or not _digest(finding.finding_digest) or source is None
                    or source.status not in {"PROPOSAL_BATCHED", "PROPOSAL_DRAFTED",
                        "PROPOSAL_REVIEWED", "SYNTHETIC_FEASIBILITY_RECORDED"}
                    or _identity(finding.auditor) in {
                        _identity(value) for value in (
                            source.planner,
                            review.reviewer if review is not None else None,
                            receipt.verifier if receipt is not None else None,
                        ) if value is not None
                    }
                    or result is None
                    or result.status != "HELD" or result.hold_reason != "INTEGRITY_DRIFT"
                    or finding.digest != canonical_digest({"finding_id": finding.finding_id,
                    "intent_id": finding.intent_id, "source_version": finding.source_version,
                    "resulting_version": finding.resulting_version, "auditor": finding.auditor,
                    "finding_digest": finding.finding_digest})):
                return False
        return (len(self._intent_proposals) == len(self._proposals)
                and len(self._intent_reviews) == len(self._reviews)
                and len(self._intent_receipts) == len(self._receipts)
                and len(self._intent_findings) == len(self._findings))

    def _hold_integrity(self) -> bool:
        previous = None
        history = {row.digest: row for row in self._history}
        reviews = {review.digest: review for review in self._reviews.values()}
        findings = {finding.digest: finding for finding in self._findings.values()}
        for index, hold in enumerate(self._holds, 1):
            payload = {k: hold[k] for k in ("sequence", "intent_id", "reason", "actor",
                "record_digest", "attachment_digest", "previous_digest")}
            row = history.get(hold["record_digest"])
            review = reviews.get(hold["attachment_digest"])
            finding = findings.get(hold["attachment_digest"])
            attachment_valid = (
                hold["reason"] == "REVIEW_REJECTED" and review is not None
                and not review.accepted and review.intent_id == hold["intent_id"]
                and review.reviewer == hold["actor"]
            ) or (
                hold["reason"] == "INTEGRITY_DRIFT" and finding is not None
                and finding.intent_id == hold["intent_id"] and finding.auditor == hold["actor"]
            )
            if (hold["sequence"] != index or hold["previous_digest"] != previous
                    or hold["reason"] not in HOLD_REASONS or row is None
                    or row.intent_id != hold["intent_id"] or row.status != "HELD"
                    or row.hold_reason != hold["reason"] or not attachment_valid
                    or hold["digest"] != canonical_digest(payload)):
                return False
            previous = hold["digest"]
        return True

    def _event_integrity(self) -> bool:
        history = {row.digest: row for row in self._history}
        batches = {b.digest: set(b.intent_ids) for b in self._batches.values()}
        drafts = {d.digest: (d.intent_id, d.resulting_version) for d in self._proposals.values()}
        reviews = {r.digest: (r.intent_id, r.resulting_version, r.accepted)
                   for r in self._reviews.values()}
        receipts = {r.digest: (r.intent_id, r.resulting_version) for r in self._receipts.values()}
        findings = {f.digest: (f.intent_id, f.resulting_version) for f in self._findings.values()}
        previous = None
        for index, event in enumerate(self._events, 1):
            payload = {k: event[k] for k in ("sequence", "action", "record_digest",
                                             "attachment_digest", "previous_digest")}
            row = history.get(event["record_digest"])
            action, attachment = event["action"], event["attachment_digest"]
            valid = row is not None and (
                (action == "INTAKE" and row.status == "INTENT_RECEIVED" and attachment is None)
                or (action == "PROPOSAL_BATCH_RESERVED" and row.status == "PROPOSAL_BATCHED"
                    and row.intent_id in batches.get(attachment, set()))
                or (action == "PROPOSAL_DRAFTED" and row.status == "PROPOSAL_DRAFTED"
                    and drafts.get(attachment) == (row.intent_id, row.version))
                or (action == "PROPOSAL_REVIEWED" and row.status == "PROPOSAL_REVIEWED"
                    and reviews.get(attachment) == (row.intent_id, row.version, True))
                or (action == "AUTO_HELD" and row.status == "HELD"
                    and (reviews.get(attachment) == (row.intent_id, row.version, False)
                         or findings.get(attachment) == (row.intent_id, row.version)))
                or (action == "PROPOSAL_RECORDED" and row.status == "SYNTHETIC_FEASIBILITY_RECORDED"
                    and receipts.get(attachment) == (row.intent_id, row.version)))
            if (event["sequence"] != index or event["previous_digest"] != previous
                    or event["digest"] != canonical_digest(payload) or not valid):
                return False
            previous = event["digest"]
        return True

    def _replay_integrity(self) -> bool:
        if set(self._used_review_digests) != {r.review_digest for r in self._receipts.values()}:
            return False
        for digest, intent_id in self._used_review_digests.items():
            receipt = self._receipts.get(self._intent_receipts.get(intent_id, ""))
            if receipt is None or receipt.review_digest != digest or receipt.intent_id != intent_id:
                return False
        return True

    def _portfolio_integrity(self) -> bool:
        seen: set[str] = set()
        for key, portfolio in self._portfolios.items():
            if (key != portfolio.portfolio_id
                    or not _synthetic(portfolio.portfolio_id, "feasibility-portfolio")
                    or not _synthetic(portfolio.observer, "portfolio-observer")
                    or not 1 <= len(portfolio.intent_ids) <= MAX_PROPOSAL_BATCH
                    or len(set(portfolio.intent_ids)) != len(portfolio.intent_ids)
                    or seen.intersection(portfolio.intent_ids)):
                return False
            artifacts = []
            for intent_id in portfolio.intent_ids:
                row = self._rows.get(intent_id)
                proposal_id = self._intent_proposals.get(intent_id)
                review_id = self._intent_reviews.get(intent_id)
                receipt_id = self._intent_receipts.get(intent_id)
                artifact = self._proposals.get(proposal_id or "")
                review = self._reviews.get(review_id or "")
                receipt = self._receipts.get(receipt_id or "")
                if (row is None or row.status != "SYNTHETIC_FEASIBILITY_RECORDED"
                        or artifact is None or review is None or receipt is None
                        or self._portfolio_members.get(intent_id) != key
                        or _identity(portfolio.observer) in {
                            _identity(artifact.planner), _identity(review.reviewer),
                            _identity(receipt.verifier),
                        }):
                    return False
                artifacts.append(artifact)
            risk_counts = tuple(sorted(
                (risk, sum(item.risk_level == risk for item in artifacts))
                for risk in ACCEPTED_RISK_LEVELS
            ))
            kind_counts = tuple(sorted(
                (kind, sum(item.proposal_kind == kind for item in artifacts))
                for kind in PROPOSAL_KINDS
            ))
            all_rollback = all(item.rollback_possible for item in artifacts)
            minimum_evidence = min(item.evidence_count for item in artifacts)
            payload = {
                "portfolio_id": key, "observer": portfolio.observer,
                "intent_ids": portfolio.intent_ids, "risk_counts": risk_counts,
                "kind_counts": kind_counts,
                "all_rollback_possible": all_rollback,
                "minimum_evidence_count": minimum_evidence,
            }
            if (portfolio.risk_counts != risk_counts or portfolio.kind_counts != kind_counts
                    or portfolio.all_rollback_possible != all_rollback
                    or portfolio.minimum_evidence_count != minimum_evidence
                    or minimum_evidence < MIN_EVIDENCE_COUNT
                    or portfolio.digest != canonical_digest(payload)):
                return False
            seen.update(portfolio.intent_ids)
        return set(self._portfolio_members) == seen

    def _integrity(self) -> bool:
        return (self._record_integrity() and self._batch_integrity()
                and self._artifact_integrity() and self._hold_integrity()
                and self._event_integrity() and self._replay_integrity()
                and self._portfolio_integrity())

    def evidence(self) -> dict[str, object]:
        return {"features": list(range(2101, 2501)), "feature_count": 400,
            "assessment_features": list(range(2101, 2301)),
            "portfolio_features": list(range(2301, 2501)),
            "portfolio_observation_only": True,
            "workstreams": [{"start": a, "end": b, "name": n, "control_count": b-a+1}
                            for a, b, n in WORKSTREAMS],
            "proposal_kind_allowlist": sorted(PROPOSAL_KINDS),
            "risk_classification_levels": sorted(RISK_LEVELS),
            "accepted_risk_levels": sorted(ACCEPTED_RISK_LEVELS),
            "minimum_evidence_count": MIN_EVIDENCE_COUNT,
            "max_proposal_batch": MAX_PROPOSAL_BATCH, "record_count": len(self._rows),
            "history_chain_valid": self._record_integrity(),
            "event_chain_valid": self._event_integrity(),
            "artifact_integrity_valid": self._artifact_integrity(),
            "batch_integrity_valid": self._batch_integrity(),
            "hold_chain_valid": self._hold_integrity(),
            "receipt_replay_index_valid": self._replay_integrity(),
            "portfolio_count": len(self._portfolios),
            "portfolio_integrity_valid": self._portfolio_integrity(),
            "maximum_state": "SYNTHETIC_FEASIBILITY_RECORDED",
            "synthetic_only": True, "in_memory_only": True,
            "automatic_approval_allowed": False, "external_delivery_used": False,
            "production_outcome_recorded": False, "pattern_promotion_allowed": False,
            "approval_authority_allowed": False, "deployment_authority_allowed": False,
            "execution_authority_allowed": False, "external_pg_api_used": False,
            "production_credentials_accessed": False,
            "payment_or_ledger_effect_allowed": False,
            "runtime_policy_change_allowed": False, "prompt_change_allowed": False,
            "weight_change_allowed": False, "merge_allowed": False,
            "deployment_allowed": False}
