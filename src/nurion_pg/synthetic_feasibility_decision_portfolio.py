"""Synthetic-only feasibility decision portfolio controls #2701-#2900.

This module aggregates inert decision docket records for observation.  A
portfolio never authorizes or executes a decision and has no external I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest
from .synthetic_feasibility_decision_docket import (
    DECISIONS, HOLD_REASONS, MAXIMUM_STATE as SOURCE_RECORDED, DocketRecord,
    SyntheticFeasibilityDecisionDocket,
)


WORKSTREAMS = (
    (2701, 2725, "TYPED_DOCKET_BOUNDARY"),
    (2726, 2750, "BOUNDED_PORTFOLIO_BATCH"),
    (2751, 2775, "SOURCE_DIGEST_VERSION_BINDING"),
    (2776, 2800, "DECISION_DISTRIBUTION_OBSERVATION"),
    (2801, 2825, "HELD_RECORDED_SEPARATION"),
    (2826, 2850, "INDEPENDENT_PORTFOLIO_REVIEW"),
    (2851, 2875, "REPLAY_CONFLICT_CONCURRENCY"),
    (2876, 2900, "APPEND_ONLY_AUDIT_EVIDENCE"),
)
MAX_PORTFOLIO_BATCH = 20
SOURCE_STATES = frozenset({SOURCE_RECORDED, "HELD"})
MAXIMUM_STATE = "SYNTHETIC_DECISION_PORTFOLIO_RECORDED"


def _synthetic(value: object, namespace: str) -> bool:
    return isinstance(value, str) and value.startswith(f"synthetic:{namespace}:")


def _digest(value: object) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


def _integer(value: object, low: int, high: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


def _identity(value: str) -> str:
    return value.rsplit(":", 1)[-1]


def _source_digest(row: DocketRecord) -> str:
    return SyntheticFeasibilityDecisionDocket._record_digest(
        row.portfolio_id, row.portfolio_digest, row.source_version, row.member_count,
        row.observer, row.status, row.version, row.analyst, row.decision,
        row.hold_reason, row.previous_digest)


@dataclass(frozen=True)
class PortfolioSource:
    docket_id: str
    source_version: int
    source_digest: str
    status: str
    decision: str
    observer: str
    analyst: str
    hold_reason: str | None
    digest: str


@dataclass(frozen=True)
class DecisionPortfolio:
    portfolio_id: str
    curator: str
    requested_limit: int
    docket_ids: tuple[str, ...]
    decision_counts: tuple[tuple[str, int], ...]
    recorded_count: int
    held_count: int
    status: str
    version: int
    previous_digest: str | None
    digest: str


@dataclass(frozen=True)
class PortfolioReview:
    review_id: str
    portfolio_id: str
    source_version: int
    resulting_version: int
    reviewer: str
    accepted: bool
    finding_digest: str
    portfolio_digest: str
    digest: str


@dataclass(frozen=True)
class PortfolioReceipt:
    receipt_id: str
    portfolio_id: str
    source_version: int
    resulting_version: int
    verifier: str
    review_digest: str
    non_authorizing: bool
    non_deployable: bool
    non_executable: bool
    digest: str


class SyntheticFeasibilityDecisionPortfolio:
    """Thread-safe, in-memory and non-authorizing portfolio registry."""

    def __init__(self) -> None:
        self._sources: dict[str, PortfolioSource] = {}
        self._portfolios: dict[str, DecisionPortfolio] = {}
        self._members: dict[str, str] = {}
        self._history: list[DecisionPortfolio] = []
        self._events: list[dict[str, object]] = []
        self._reviews: dict[str, PortfolioReview] = {}
        self._portfolio_reviews: dict[str, str] = {}
        self._receipts: dict[str, PortfolioReceipt] = {}
        self._portfolio_receipts: dict[str, str] = {}
        self._used_review_digests: dict[str, str] = {}
        self._holds: list[dict[str, object]] = []
        self._lock = RLock()

    @staticmethod
    def _portfolio_digest(portfolio_id: str, curator: str, requested_limit: int,
                          docket_ids: tuple[str, ...],
                          decision_counts: tuple[tuple[str, int], ...],
                          recorded_count: int, held_count: int, status: str,
                          version: int, previous_digest: str | None) -> str:
        return canonical_digest({"portfolio_id": portfolio_id, "curator": curator,
            "requested_limit": requested_limit, "docket_ids": docket_ids,
            "decision_counts": decision_counts, "recorded_count": recorded_count,
            "held_count": held_count, "status": status, "version": version,
            "previous_digest": previous_digest})

    def intake(self, row: DocketRecord) -> PortfolioSource:
        if not isinstance(row, DocketRecord):
            raise GovernanceRejected("typed decision docket record required")
        if (not _synthetic(row.portfolio_id, "feasibility-portfolio")
                or row.status not in SOURCE_STATES or row.decision not in DECISIONS
                or row.source_version != 1
                or not _integer(row.member_count, 1, MAX_PORTFOLIO_BATCH)
                or not _integer(row.version, 1, 1_000_000)
                or not _digest(row.portfolio_digest) or not _digest(row.previous_digest)
                or not _digest(row.digest) or row.digest != _source_digest(row)
                or not _synthetic(row.observer, "portfolio-observer")
                or not _synthetic(row.analyst, "docket-analyst")
                or _identity(row.observer) == _identity(row.analyst)
                or (row.status == "HELD" and row.hold_reason not in HOLD_REASONS)
                or (row.status == SOURCE_RECORDED and row.hold_reason is not None)):
            raise GovernanceRejected("integral terminal non-authorizing docket required")
        payload = {"docket_id": row.portfolio_id, "source_version": row.version,
            "source_digest": row.digest, "status": row.status, "decision": row.decision,
            "observer": row.observer, "analyst": row.analyst,
            "hold_reason": row.hold_reason}
        source = PortfolioSource(row.portfolio_id, row.version, row.digest, row.status,
            row.decision, row.observer, row.analyst, row.hold_reason,
            canonical_digest(payload))
        with self._lock:
            prior = self._sources.get(row.portfolio_id)
            if prior is not None:
                if prior == source:
                    return prior
                raise GovernanceRejected("docket intake conflict or source drift")
            self._sources[row.portfolio_id] = source
            return source

    def _append(self, action: str, value: DecisionPortfolio,
                attachment: str | None = None) -> DecisionPortfolio:
        prior = self._events[-1]["digest"] if self._events else None
        event = {"sequence": len(self._events) + 1, "action": action,
            "portfolio_digest": value.digest, "attachment_digest": attachment,
            "previous_digest": prior}
        self._history.append(value)
        self._events.append({**event, "digest": canonical_digest(event)})
        self._portfolios[value.portfolio_id] = value
        return value

    def _transition(self, old: DecisionPortfolio, action: str, status: str,
                    attachment: str) -> DecisionPortfolio:
        value = DecisionPortfolio(old.portfolio_id, old.curator, old.requested_limit,
            old.docket_ids, old.decision_counts, old.recorded_count, old.held_count,
            status, old.version + 1, old.digest,
            self._portfolio_digest(old.portfolio_id, old.curator, old.requested_limit,
                old.docket_ids, old.decision_counts, old.recorded_count, old.held_count,
                status, old.version + 1, old.digest))
        return self._append(action, value, attachment)

    def _role_identities(self, row: DecisionPortfolio, include_artifacts: bool = True) -> set[str]:
        identities = {_identity(row.curator)}
        for docket_id in row.docket_ids:
            source = self._sources.get(docket_id)
            if source is not None:
                identities.update({_identity(source.observer), _identity(source.analyst)})
        if include_artifacts:
            review = self._reviews.get(self._portfolio_reviews.get(row.portfolio_id, ""))
            receipt = self._receipts.get(self._portfolio_receipts.get(row.portfolio_id, ""))
            if review is not None:
                identities.add(_identity(review.reviewer))
            if receipt is not None:
                identities.add(_identity(receipt.verifier))
        return identities

    def curate(self, portfolio_id: str, curator: str, limit: int) -> DecisionPortfolio:
        if (not _synthetic(portfolio_id, "decision-portfolio")
                or not _synthetic(curator, "portfolio-curator")
                or not _integer(limit, 1, MAX_PORTFOLIO_BATCH)):
            raise GovernanceRejected("bounded synthetic decision portfolio required")
        with self._lock:
            prior = self._portfolios.get(portfolio_id)
            if prior is not None:
                if prior.curator == curator and prior.requested_limit == limit:
                    return prior
                raise GovernanceRejected("decision portfolio conflict")
            selected = sorted((source for key, source in self._sources.items()
                               if key not in self._members), key=lambda item: item.docket_id)[:limit]
            if not selected:
                raise GovernanceRejected("unassigned docket source required")
            identities = {_identity(curator)}
            if any(_identity(item.observer) in identities or _identity(item.analyst) in identities
                   for item in selected):
                raise GovernanceRejected("independent portfolio curator required")
            ids = tuple(item.docket_id for item in selected)
            counts = tuple((decision, sum(item.decision == decision for item in selected))
                           for decision in sorted(DECISIONS))
            recorded = sum(item.status == SOURCE_RECORDED for item in selected)
            held = sum(item.status == "HELD" for item in selected)
            digest = self._portfolio_digest(portfolio_id, curator, limit, ids, counts,
                                            recorded, held, "CURATED", 1, None)
            value = DecisionPortfolio(portfolio_id, curator, limit, ids, counts,
                                      recorded, held, "CURATED", 1, None, digest)
            for item in selected:
                self._members[item.docket_id] = portfolio_id
            return self._append("PORTFOLIO_CURATED", value)

    def review(self, review_id: str, portfolio_id: str, expected_version: int,
               reviewer: str, accepted: bool, finding_digest: str) -> DecisionPortfolio:
        if (not _synthetic(review_id, "portfolio-review")
                or not _synthetic(reviewer, "portfolio-reviewer")
                or not isinstance(accepted, bool) or not _digest(finding_digest)):
            raise GovernanceRejected("valid independent portfolio review required")
        with self._lock:
            prior = self._reviews.get(review_id)
            fields = (portfolio_id, expected_version, reviewer, accepted, finding_digest)
            if prior is not None:
                if fields == (prior.portfolio_id, prior.source_version, prior.reviewer,
                              prior.accepted, prior.finding_digest):
                    return self._portfolios[portfolio_id]
                raise GovernanceRejected("portfolio review conflict")
            if portfolio_id in self._portfolio_reviews:
                raise GovernanceRejected("portfolio already reviewed")
            old = self._portfolios.get(portfolio_id)
            if old is None or old.version != expected_version or old.status != "CURATED":
                raise GovernanceRejected("current curated portfolio required")
            if _identity(reviewer) in self._role_identities(old) or not self._integrity():
                raise GovernanceRejected("independent reviewer and integral portfolio required")
            payload = {"review_id": review_id, "portfolio_id": portfolio_id,
                "source_version": expected_version, "resulting_version": expected_version + 1,
                "reviewer": reviewer, "accepted": accepted,
                "finding_digest": finding_digest, "portfolio_digest": old.digest}
            artifact = PortfolioReview(review_id, portfolio_id, expected_version,
                expected_version + 1, reviewer, accepted, finding_digest, old.digest,
                canonical_digest(payload))
            self._reviews[review_id] = artifact
            self._portfolio_reviews[portfolio_id] = review_id
            result = self._transition(old, "PORTFOLIO_REVIEWED" if accepted else "PORTFOLIO_HELD",
                                      "REVIEWED" if accepted else "HELD", artifact.digest)
            if not accepted:
                self._append_hold(result, reviewer, "REVIEW_REJECTED", artifact.digest)
            return result

    def _append_hold(self, row: DecisionPortfolio, actor: str, reason: str,
                     attachment: str) -> None:
        previous = self._holds[-1]["digest"] if self._holds else None
        payload = {"sequence": len(self._holds) + 1, "portfolio_id": row.portfolio_id,
            "actor": actor, "reason": reason, "portfolio_digest": row.digest,
            "attachment_digest": attachment, "previous_digest": previous}
        self._holds.append({**payload, "digest": canonical_digest(payload)})

    def record(self, receipt_id: str, portfolio_id: str, expected_version: int,
               review_digest: str, verifier: str) -> DecisionPortfolio:
        if (not _synthetic(receipt_id, "portfolio-receipt") or not _digest(review_digest)
                or not _synthetic(verifier, "portfolio-verifier")):
            raise GovernanceRejected("valid inert portfolio receipt required")
        with self._lock:
            prior = self._receipts.get(receipt_id)
            fields = (portfolio_id, expected_version, review_digest, verifier)
            if prior is not None:
                if fields == (prior.portfolio_id, prior.source_version,
                              prior.review_digest, prior.verifier):
                    return self._portfolios[portfolio_id]
                raise GovernanceRejected("portfolio receipt conflict")
            if portfolio_id in self._portfolio_receipts or review_digest in self._used_review_digests:
                raise GovernanceRejected("portfolio receipt replay blocked")
            old = self._portfolios.get(portfolio_id)
            review = self._reviews.get(self._portfolio_reviews.get(portfolio_id, ""))
            if (old is None or old.version != expected_version or old.status != "REVIEWED"
                    or review is None or not review.accepted or review.digest != review_digest
                    or _identity(verifier) in self._role_identities(old)
                    or not self._integrity()):
                raise GovernanceRejected("independently reviewed current portfolio required")
            payload = {"receipt_id": receipt_id, "portfolio_id": portfolio_id,
                "source_version": expected_version, "resulting_version": expected_version + 1,
                "verifier": verifier, "review_digest": review_digest,
                "non_authorizing": True, "non_deployable": True, "non_executable": True}
            receipt = PortfolioReceipt(receipt_id, portfolio_id, expected_version,
                expected_version + 1, verifier, review_digest, True, True, True,
                canonical_digest(payload))
            self._receipts[receipt_id] = receipt
            self._portfolio_receipts[portfolio_id] = receipt_id
            self._used_review_digests[review_digest] = portfolio_id
            return self._transition(old, "PORTFOLIO_RECEIPT_RECORDED", MAXIMUM_STATE,
                                    receipt.digest)

    def audit_hold(self, portfolio_id: str, expected_version: int, auditor: str,
                   finding_digest: str) -> DecisionPortfolio:
        if not _synthetic(auditor, "portfolio-auditor") or not _digest(finding_digest):
            raise GovernanceRejected("valid independent portfolio auditor required")
        with self._lock:
            if not self._integrity():
                raise GovernanceRejected("integral portfolio evidence required")
            old = self._portfolios.get(portfolio_id)
            if old is None or old.version != expected_version or old.status == "HELD":
                raise GovernanceRejected("current holdable portfolio required")
            if _identity(auditor) in self._role_identities(old):
                raise GovernanceRejected("independent portfolio auditor required")
            result = self._transition(old, "PORTFOLIO_HELD", "HELD", finding_digest)
            self._append_hold(result, auditor, "INTEGRITY_FINDING", finding_digest)
            return result

    def get(self, portfolio_id: str) -> DecisionPortfolio:
        return self._portfolios[portfolio_id]

    def review_artifact(self, review_id: str) -> PortfolioReview:
        return self._reviews[review_id]

    def _portfolio_integrity(self) -> bool:
        latest: dict[str, DecisionPortfolio] = {}
        versions: dict[str, int] = {}
        previous: dict[str, str] = {}
        for row in self._history:
            prior = latest.get(row.portfolio_id)
            valid = ((prior is None and row.status == "CURATED") or
                (prior is not None and ((prior.status == "CURATED" and row.status in {"REVIEWED", "HELD"})
                 or (prior.status == "REVIEWED" and row.status in {MAXIMUM_STATE, "HELD"})
                 or (prior.status == MAXIMUM_STATE and row.status == "HELD"))))
            sources = [self._sources.get(key) for key in row.docket_ids]
            counts = tuple((decision, sum(item is not None and item.decision == decision
                                          for item in sources)) for decision in sorted(DECISIONS))
            if (not valid or row.version != versions.get(row.portfolio_id, 0) + 1
                    or row.previous_digest != previous.get(row.portfolio_id)
                    or not row.docket_ids or len(row.docket_ids) > row.requested_limit
                    or not _integer(row.requested_limit, 1, MAX_PORTFOLIO_BATCH)
                    or not _synthetic(row.portfolio_id, "decision-portfolio")
                    or not _synthetic(row.curator, "portfolio-curator")
                    or len(set(row.docket_ids)) != len(row.docket_ids)
                    or any(item is None for item in sources) or row.decision_counts != counts
                    or row.recorded_count != sum(item.status == SOURCE_RECORDED for item in sources)
                    or row.held_count != sum(item.status == "HELD" for item in sources)
                    or row.recorded_count + row.held_count != len(sources)
                    or row.digest != self._portfolio_digest(row.portfolio_id, row.curator,
                        row.requested_limit, row.docket_ids, row.decision_counts,
                        row.recorded_count, row.held_count, row.status, row.version,
                        row.previous_digest)):
                return False
            latest[row.portfolio_id] = row; versions[row.portfolio_id] = row.version
            previous[row.portfolio_id] = row.digest
        expected_members = {member: row.portfolio_id for row in self._history
                            if row.version == 1 for member in row.docket_ids}
        return latest == self._portfolios and expected_members == self._members

    def _event_integrity(self) -> bool:
        if len(self._events) != len(self._history): return False
        previous = None
        actions = {"CURATED": "PORTFOLIO_CURATED", "REVIEWED": "PORTFOLIO_REVIEWED",
                   "HELD": "PORTFOLIO_HELD", MAXIMUM_STATE: "PORTFOLIO_RECEIPT_RECORDED"}
        for sequence, (event, row) in enumerate(zip(self._events, self._history), 1):
            expected_attachment = None
            if row.status == "REVIEWED":
                review = self._reviews.get(self._portfolio_reviews.get(row.portfolio_id, ""))
                expected_attachment = review.digest if review else None
            elif row.status == MAXIMUM_STATE:
                receipt = self._receipts.get(self._portfolio_receipts.get(row.portfolio_id, ""))
                expected_attachment = receipt.digest if receipt else None
            elif row.status == "HELD":
                hold = next((item for item in self._holds
                    if item.get("portfolio_digest") == row.digest), None)
                expected_attachment = hold.get("attachment_digest") if hold else None
            payload = {"sequence": sequence, "action": event.get("action"),
                "portfolio_digest": row.digest,
                "attachment_digest": event.get("attachment_digest"),
                "previous_digest": previous}
            if (event.get("action") != actions.get(row.status)
                    or event.get("attachment_digest") != expected_attachment
                    or event != {**payload, "digest": canonical_digest(payload)}):
                return False
            previous = event["digest"]
        return True

    def _artifact_integrity(self) -> bool:
        history = {(row.portfolio_id, row.version): row for row in self._history}
        for key, review in self._reviews.items():
            source = history.get((review.portfolio_id, review.source_version))
            result = history.get((review.portfolio_id, review.resulting_version))
            payload = {"review_id": review.review_id, "portfolio_id": review.portfolio_id,
                "source_version": review.source_version, "resulting_version": review.resulting_version,
                "reviewer": review.reviewer, "accepted": review.accepted,
                "finding_digest": review.finding_digest, "portfolio_digest": review.portfolio_digest}
            if (key != review.review_id or self._portfolio_reviews.get(review.portfolio_id) != key
                    or source is None or source.status != "CURATED" or result is None
                    or result.status != ("REVIEWED" if review.accepted else "HELD")
                    or review.resulting_version != review.source_version + 1
                    or review.portfolio_digest != source.digest
                    or _identity(review.reviewer) in self._role_identities(source, False)
                    or review.digest != canonical_digest(payload)):
                return False
        for key, receipt in self._receipts.items():
            review = self._reviews.get(self._portfolio_reviews.get(receipt.portfolio_id, ""))
            result = history.get((receipt.portfolio_id, receipt.resulting_version))
            payload = {"receipt_id": receipt.receipt_id, "portfolio_id": receipt.portfolio_id,
                "source_version": receipt.source_version, "resulting_version": receipt.resulting_version,
                "verifier": receipt.verifier, "review_digest": receipt.review_digest,
                "non_authorizing": True, "non_deployable": True, "non_executable": True}
            if (key != receipt.receipt_id or review is None or not review.accepted
                    or self._portfolio_receipts.get(receipt.portfolio_id) != key
                    or receipt.review_digest != review.digest
                    or receipt.source_version != review.resulting_version
                    or receipt.resulting_version != receipt.source_version + 1
                    or result is None or result.status != MAXIMUM_STATE
                    or not all((receipt.non_authorizing, receipt.non_deployable, receipt.non_executable))
                    or _identity(receipt.verifier) in (self._role_identities(result, False)
                        | {_identity(review.reviewer)})
                    or self._used_review_digests.get(review.digest) != receipt.portfolio_id
                    or receipt.digest != canonical_digest(payload)):
                return False
        return True

    def _hold_integrity(self) -> bool:
        previous = None
        for sequence, hold in enumerate(self._holds, 1):
            payload = {"sequence": sequence, "portfolio_id": hold.get("portfolio_id"),
                "actor": hold.get("actor"), "reason": hold.get("reason"),
                "portfolio_digest": hold.get("portfolio_digest"),
                "attachment_digest": hold.get("attachment_digest"),
                "previous_digest": previous}
            matching = any(row.portfolio_id == hold.get("portfolio_id") and row.status == "HELD"
                           and row.digest == hold.get("portfolio_digest") for row in self._history)
            row = next((item for item in self._history
                        if item.digest == hold.get("portfolio_digest")), None)
            reason = hold.get("reason"); actor = hold.get("actor")
            if reason == "REVIEW_REJECTED":
                review = self._reviews.get(self._portfolio_reviews.get(str(hold.get("portfolio_id")), ""))
                semantic = (review is not None and not review.accepted
                    and actor == review.reviewer
                    and hold.get("attachment_digest") == review.digest)
            elif reason == "INTEGRITY_FINDING":
                semantic = (row is not None and _synthetic(actor, "portfolio-auditor")
                    and _identity(str(actor)) not in self._role_identities(row)
                    and _digest(hold.get("attachment_digest")))
            else:
                semantic = False
            if (not matching or not semantic
                    or hold != {**payload, "digest": canonical_digest(payload)}):
                return False
            previous = hold["digest"]
        return True

    def _source_integrity(self) -> bool:
        for key, source in self._sources.items():
            payload = {"docket_id": source.docket_id, "source_version": source.source_version,
                "source_digest": source.source_digest, "status": source.status,
                "decision": source.decision, "observer": source.observer,
                "analyst": source.analyst, "hold_reason": source.hold_reason}
            if (key != source.docket_id or source.status not in SOURCE_STATES
                    or source.decision not in DECISIONS or not _digest(source.source_digest)
                    or source.source_version < 1
                    or not _synthetic(source.observer, "portfolio-observer")
                    or not _synthetic(source.analyst, "docket-analyst")
                    or _identity(source.observer) == _identity(source.analyst)
                    or (source.status == "HELD" and source.hold_reason not in HOLD_REASONS)
                    or (source.status == SOURCE_RECORDED and source.hold_reason is not None)
                    or source.digest != canonical_digest(payload)):
                return False
        return True

    def _integrity(self) -> bool:
        return all((self._source_integrity(), self._portfolio_integrity(),
                    self._event_integrity(), self._artifact_integrity(),
                    self._hold_integrity()))

    def evidence(self) -> dict[str, object]:
        source_ok = self._source_integrity(); portfolio_ok = self._portfolio_integrity()
        event_ok = self._event_integrity(); artifact_ok = self._artifact_integrity()
        hold_ok = self._hold_integrity()
        observed = [number for start, end, _ in WORKSTREAMS for number in range(start, end + 1)]
        expected = set(range(2701, 2901)); observed_set = set(observed)
        matrix_ok = (len(WORKSTREAMS) == 8 and len(observed) == 200
            and observed_set == expected and len(observed) == len(observed_set)
            and all(end - start + 1 == 25 for start, end, _ in WORKSTREAMS))
        gaps = tuple(name for name, ok in (("control_matrix", matrix_ok),
            ("source", source_ok), ("portfolio", portfolio_ok),
            ("event", event_ok), ("artifact", artifact_ok), ("hold", hold_ok)) if not ok)
        return {"control_range": [2701, 2900], "control_count": 200,
            "workstream_count": len(WORKSTREAMS),
            "exactly_25_controls_per_workstream": all(end - start + 1 == 25
                                                       for start, end, _ in WORKSTREAMS),
            "workstreams": [name for _, _, name in WORKSTREAMS],
            "control_matrix_valid": matrix_ok,
            "maximum_batch": MAX_PORTFOLIO_BATCH, "decision_allowlist": sorted(DECISIONS),
            "source_states": sorted(SOURCE_STATES), "source_count": len(self._sources),
            "portfolio_count": len(self._portfolios), "membership_count": len(self._members),
            "recorded_source_count": sum(row.status == SOURCE_RECORDED for row in self._sources.values()),
            "held_source_count": sum(row.status == "HELD" for row in self._sources.values()),
            "source_integrity_valid": source_ok, "portfolio_integrity_valid": portfolio_ok,
            "event_chain_valid": event_ok, "artifact_integrity_valid": artifact_ok,
            "hold_chain_valid": hold_ok, "integrity_valid": all((source_ok, portfolio_ok,
                event_ok, artifact_ok, hold_ok)), "capability_ready": not gaps,
            "capability_gap_evidence": {"fail_closed": bool(gaps), "gaps": gaps},
            "maximum_state": MAXIMUM_STATE, "non_authorizing": True,
            "non_deployable": True, "non_executable": True, "external_calls": 0,
            "ledger_writes": 0, "runtime_policy_mutations": 0}
