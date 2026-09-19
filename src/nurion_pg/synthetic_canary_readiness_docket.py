"""Synthetic-only canary readiness docket controls #1501-#1700.

Readiness is an observation, never approval, deployment authority, or permission
to affect payments, a ledger, credentials, networks, or runtime policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest


WORKSTREAMS = (
    (1501, 1525, "COMPLETED_CANARY_INTAKE"),
    (1526, 1550, "BOUNDED_PORTFOLIO_BATCH"),
    (1551, 1575, "SAMPLE_COMPLETION_VALIDATION"),
    (1576, 1600, "ERROR_P95_AGGREGATION"),
    (1601, 1625, "INDEPENDENT_READINESS_REVIEW"),
    (1626, 1650, "REGRESSION_INTEGRITY_AUTO_HOLD"),
    (1651, 1675, "DOCKET_AUTHORITY_REPLAY_DEFENSE"),
    (1676, 1700, "AUDIT_EVIDENCE"),
)
MAX_PORTFOLIO_BATCH = 20
HOLD_REASONS = {"INSUFFICIENT_SAMPLE", "COMPLETION_REGRESSION", "ERROR_REGRESSION",
                "LATENCY_REGRESSION", "REVIEW_REJECTED", "INTEGRITY_DRIFT"}


def _synthetic(value: object, namespace: str) -> bool:
    return isinstance(value, str) and value.startswith(f"synthetic:{namespace}:")


def _digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _integer(value: object, low: int, high: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


@dataclass(frozen=True)
class ReadinessRecord:
    canary_id: str
    completion_digest: str
    status: str
    version: int
    minimum_sample: int
    minimum_completion_bps: int
    error_budget_bps: int
    latency_budget_ms: int
    aggregator: str | None
    hold_reason: str | None
    previous_digest: str | None
    digest: str


@dataclass(frozen=True)
class PortfolioBatch:
    batch_id: str
    requested_limit: int
    canary_ids: tuple[str, ...]
    digest: str


@dataclass(frozen=True)
class MetricsReceipt:
    canary_id: str
    source_version: int
    resulting_version: int
    aggregator: str
    sample_count: int
    completed_count: int
    error_count: int
    p95_latency_ms: int
    source_digest: str
    digest: str


@dataclass(frozen=True)
class ReadinessDocket:
    docket_id: str
    canary_id: str
    source_version: int
    resulting_version: int
    reviewer: str
    ready: bool
    review_digest: str
    metrics_receipt_digest: str
    digest: str


class SyntheticCanaryReadinessDocket:
    """Thread-safe, bounded and append-only synthetic readiness model."""

    def __init__(self) -> None:
        self._rows: dict[str, ReadinessRecord] = {}
        self._history: list[ReadinessRecord] = []
        self._events: list[dict[str, object]] = []
        self._batches: dict[str, PortfolioBatch] = {}
        self._metrics: dict[str, MetricsReceipt] = {}
        self._dockets: dict[str, ReadinessDocket] = {}
        self._canary_dockets: dict[str, str] = {}
        self._used_dockets: dict[str, str] = {}
        self._docket_verifiers: dict[str, str] = {}
        self._holds: list[dict[str, object]] = []
        self._lock = RLock()

    @staticmethod
    def _record_digest(canary_id: str, completion_digest: str, status: str, version: int,
                       minimum_sample: int, minimum_completion_bps: int, error_budget_bps: int,
                       latency_budget_ms: int, aggregator: str | None, hold_reason: str | None,
                       previous_digest: str | None) -> str:
        return canonical_digest({"canary_id": canary_id, "completion_digest": completion_digest,
            "status": status, "version": version, "minimum_sample": minimum_sample,
            "minimum_completion_bps": minimum_completion_bps, "error_budget_bps": error_budget_bps,
            "latency_budget_ms": latency_budget_ms, "aggregator": aggregator,
            "hold_reason": hold_reason, "previous_digest": previous_digest})

    def _make(self, canary_id: str, completion_digest: str, status: str, version: int,
              minimum_sample: int, minimum_completion_bps: int, error_budget_bps: int,
              latency_budget_ms: int, aggregator: str | None = None,
              hold_reason: str | None = None, previous_digest: str | None = None) -> ReadinessRecord:
        if (not _synthetic(canary_id, "completed-canary") or not _digest(completion_digest)
                or not _integer(version, 1, 1_000_000) or not _integer(minimum_sample, 1, 1_000_000)
                or not _integer(minimum_completion_bps, 0, 10_000)
                or not _integer(error_budget_bps, 0, 10_000)
                or not _integer(latency_budget_ms, 1, 60_000)
                or (aggregator is not None and not _synthetic(aggregator, "aggregator"))
                or (hold_reason is not None and hold_reason not in HOLD_REASONS)):
            raise GovernanceRejected("valid synthetic readiness record required")
        value = self._record_digest(canary_id, completion_digest, status, version, minimum_sample,
            minimum_completion_bps, error_budget_bps, latency_budget_ms, aggregator,
            hold_reason, previous_digest)
        return ReadinessRecord(canary_id, completion_digest, status, version, minimum_sample,
            minimum_completion_bps, error_budget_bps, latency_budget_ms, aggregator,
            hold_reason, previous_digest, value)

    def _append(self, action: str, row: ReadinessRecord, attachment: str | None = None) -> ReadinessRecord:
        previous = self._events[-1]["digest"] if self._events else None
        payload = {"sequence": len(self._events) + 1, "action": action,
                   "record_digest": row.digest, "attachment_digest": attachment,
                   "previous_digest": previous}
        self._history.append(row)
        self._events.append({**payload, "digest": canonical_digest(payload)})
        self._rows[row.canary_id] = row
        return row

    def _transition(self, old: ReadinessRecord, action: str, status: str, *,
                    aggregator: str | None = None, hold_reason: str | None = None,
                    attachment: str | None = None) -> ReadinessRecord:
        row = self._make(old.canary_id, old.completion_digest, status, old.version + 1,
            old.minimum_sample, old.minimum_completion_bps, old.error_budget_bps,
            old.latency_budget_ms, old.aggregator if aggregator is None else aggregator,
            hold_reason, old.digest)
        return self._append(action, row, attachment)

    def _require(self, canary_id: str, version: int, status: str) -> ReadinessRecord:
        row = self._rows.get(canary_id)
        if row is None or row.version != version or row.status != status:
            raise GovernanceRejected("current readiness state and version required")
        return row

    def intake(self, canary_id: str, completion_digest: str, minimum_sample: int,
               minimum_completion_bps: int, error_budget_bps: int,
               latency_budget_ms: int) -> ReadinessRecord:
        with self._lock:
            existing = self._rows.get(canary_id)
            fields = (completion_digest, minimum_sample, minimum_completion_bps,
                      error_budget_bps, latency_budget_ms)
            if existing:
                if fields == (existing.completion_digest, existing.minimum_sample,
                              existing.minimum_completion_bps, existing.error_budget_bps,
                              existing.latency_budget_ms):
                    return existing
                raise GovernanceRejected("completed canary intake conflict")
            return self._append("INTAKE", self._make(canary_id, completion_digest, "INTAKE", 1,
                minimum_sample, minimum_completion_bps, error_budget_bps, latency_budget_ms))

    def reserve_portfolio(self, batch_id: str, limit: int) -> PortfolioBatch:
        if not _synthetic(batch_id, "readiness-batch") or not _integer(limit, 1, MAX_PORTFOLIO_BATCH):
            raise GovernanceRejected("bounded synthetic readiness batch required")
        with self._lock:
            existing = self._batches.get(batch_id)
            if existing:
                if existing.requested_limit == limit:
                    return existing
                raise GovernanceRejected("portfolio batch conflict")
            selected = sorted((r for r in self._rows.values() if r.status == "INTAKE"),
                              key=lambda r: (r.version, r.canary_id))[:limit]
            ids = tuple(r.canary_id for r in selected)
            value = canonical_digest({"batch_id": batch_id, "requested_limit": limit, "canary_ids": ids})
            batch = PortfolioBatch(batch_id, limit, ids, value)
            self._batches[batch_id] = batch
            for row in selected:
                self._transition(row, "PORTFOLIO_BATCHED", "PORTFOLIO_BATCHED", attachment=value)
            return batch

    def aggregate(self, canary_id: str, expected_version: int, aggregator: str, sample_count: int,
                  completed_count: int, error_count: int, p95_latency_ms: int,
                  source_digest: str) -> ReadinessRecord:
        if (not _synthetic(aggregator, "aggregator") or not _integer(sample_count, 1, 1_000_000)
                or not _integer(completed_count, 0, sample_count)
                or not _integer(error_count, 0, completed_count)
                or not _integer(p95_latency_ms, 0, 60_000) or not _digest(source_digest)):
            raise GovernanceRejected("valid synthetic aggregate required")
        with self._lock:
            prior = self._metrics.get(canary_id)
            fields = (expected_version, aggregator, sample_count, completed_count,
                      error_count, p95_latency_ms, source_digest)
            if prior:
                if fields == (prior.source_version, prior.aggregator, prior.sample_count,
                              prior.completed_count, prior.error_count, prior.p95_latency_ms,
                              prior.source_digest):
                    return self._rows[canary_id]
                raise GovernanceRejected("metrics aggregate conflict")
            old = self._require(canary_id, expected_version, "PORTFOLIO_BATCHED")
            resulting = expected_version + 1
            value = canonical_digest({"canary_id": canary_id, "source_version": expected_version,
                "resulting_version": resulting, "aggregator": aggregator, "sample_count": sample_count,
                "completed_count": completed_count, "error_count": error_count,
                "p95_latency_ms": p95_latency_ms, "source_digest": source_digest})
            receipt = MetricsReceipt(canary_id, expected_version, resulting, aggregator, sample_count,
                completed_count, error_count, p95_latency_ms, source_digest, value)
            self._metrics[canary_id] = receipt
            if sample_count < old.minimum_sample:
                return self._auto_hold(old, aggregator, "INSUFFICIENT_SAMPLE", value)
            if completed_count * 10_000 < old.minimum_completion_bps * sample_count:
                return self._auto_hold(old, aggregator, "COMPLETION_REGRESSION", value)
            if error_count * 10_000 > old.error_budget_bps * sample_count:
                return self._auto_hold(old, aggregator, "ERROR_REGRESSION", value)
            if p95_latency_ms > old.latency_budget_ms:
                return self._auto_hold(old, aggregator, "LATENCY_REGRESSION", value)
            return self._transition(old, "METRICS_ACCEPTED", "METRICS_ACCEPTED",
                                    aggregator=aggregator, attachment=value)

    def _auto_hold(self, old: ReadinessRecord, actor: str, reason: str, attachment: str) -> ReadinessRecord:
        row = self._transition(old, "AUTO_HELD", "HELD", hold_reason=reason, attachment=attachment)
        previous = self._holds[-1]["digest"] if self._holds else None
        payload = {"sequence": len(self._holds) + 1, "canary_id": old.canary_id, "reason": reason,
                   "actor": actor, "record_digest": row.digest, "previous_digest": previous}
        self._holds.append({**payload, "digest": canonical_digest(payload)})
        return row

    def review(self, docket_id: str, canary_id: str, expected_version: int, reviewer: str,
               ready: bool, review_digest: str) -> ReadinessRecord:
        if (not _synthetic(docket_id, "readiness-docket") or not _synthetic(reviewer, "reviewer")
                or not isinstance(ready, bool) or not _digest(review_digest)):
            raise GovernanceRejected("authorized synthetic readiness review required")
        with self._lock:
            prior = self._dockets.get(docket_id)
            if prior:
                fields = (canary_id, expected_version, reviewer, ready, review_digest)
                if fields == (prior.canary_id, prior.source_version, prior.reviewer,
                              prior.ready, prior.review_digest):
                    return self._rows[canary_id]
                raise GovernanceRejected("readiness docket conflict")
            if canary_id in self._canary_dockets:
                raise GovernanceRejected("canary already has a readiness docket")
            old = self._require(canary_id, expected_version, "METRICS_ACCEPTED")
            if not self._integrity():
                raise GovernanceRejected("integral synthetic readiness evidence required")
            metrics = self._metrics[canary_id]
            if reviewer.rsplit(":", 1)[-1] == metrics.aggregator.rsplit(":", 1)[-1]:
                raise GovernanceRejected("aggregator and reviewer must be independent")
            resulting = expected_version + 1
            value = canonical_digest({"docket_id": docket_id, "canary_id": canary_id,
                "source_version": expected_version, "resulting_version": resulting,
                "reviewer": reviewer, "ready": ready, "review_digest": review_digest,
                "metrics_receipt_digest": metrics.digest})
            docket = ReadinessDocket(docket_id, canary_id, expected_version, resulting, reviewer,
                                     ready, review_digest, metrics.digest, value)
            self._dockets[docket_id] = docket
            self._canary_dockets[canary_id] = docket_id
            if not ready:
                return self._auto_hold(old, reviewer, "REVIEW_REJECTED", value)
            return self._transition(old, "READINESS_REVIEWED", "SYNTHETIC_READINESS_REVIEWED",
                                    attachment=value)

    def verify_docket(self, canary_id: str, expected_version: int, docket_digest: str,
                      verifier: str) -> ReadinessRecord:
        if not _synthetic(verifier, "verifier") or not _digest(docket_digest):
            raise GovernanceRejected("synthetic verifier and docket digest required")
        with self._lock:
            row = self._require(canary_id, expected_version, "SYNTHETIC_READINESS_REVIEWED")
            docket_id = self._canary_dockets.get(canary_id)
            docket = self._dockets.get(docket_id or "")
            if (docket is None or docket.digest != docket_digest or not docket.ready
                    or docket.resulting_version != row.version or not self._integrity()):
                raise GovernanceRejected("current integral readiness docket required")
            if docket_digest in self._used_dockets:
                raise GovernanceRejected("readiness docket reuse blocked")
            if verifier.rsplit(":", 1)[-1] in {
                docket.reviewer.rsplit(":", 1)[-1], row.aggregator.rsplit(":", 1)[-1]
            }:
                raise GovernanceRejected("verifier must be independent")
            self._used_dockets[docket_digest] = canary_id
            self._docket_verifiers[docket_digest] = verifier
            return row

    def get(self, canary_id: str) -> ReadinessRecord:
        return self._rows[canary_id]

    def docket(self, docket_id: str) -> ReadinessDocket:
        return self._dockets[docket_id]

    def _record_integrity(self) -> bool:
        previous: dict[str, str] = {}
        versions: dict[str, int] = {}
        latest: dict[str, ReadinessRecord] = {}
        for row in self._history:
            if (row.version != versions.get(row.canary_id, 0) + 1
                    or row.previous_digest != previous.get(row.canary_id)
                    or row.digest != self._record_digest(row.canary_id, row.completion_digest,
                    row.status, row.version, row.minimum_sample, row.minimum_completion_bps,
                    row.error_budget_bps, row.latency_budget_ms, row.aggregator,
                    row.hold_reason, row.previous_digest)):
                return False
            previous[row.canary_id] = row.digest
            versions[row.canary_id] = row.version
            latest[row.canary_id] = row
        return latest == self._rows

    def _receipt_integrity(self) -> bool:
        for key, r in self._metrics.items():
            if (key != r.canary_id or key not in self._rows
                    or r.resulting_version != r.source_version + 1
                    or not _synthetic(r.aggregator, "aggregator")
                    or not _integer(r.sample_count, 1, 1_000_000)
                    or not _integer(r.completed_count, 0, r.sample_count)
                    or not _integer(r.error_count, 0, r.completed_count)
                    or not _integer(r.p95_latency_ms, 0, 60_000) or not _digest(r.source_digest)
                    or r.digest != canonical_digest({"canary_id": r.canary_id,
                    "source_version": r.source_version, "resulting_version": r.resulting_version,
                    "aggregator": r.aggregator, "sample_count": r.sample_count,
                    "completed_count": r.completed_count, "error_count": r.error_count,
                    "p95_latency_ms": r.p95_latency_ms, "source_digest": r.source_digest})):
                return False
        for key, d in self._dockets.items():
            metrics = self._metrics.get(d.canary_id)
            if (key != d.docket_id or not _synthetic(d.docket_id, "readiness-docket")
                    or metrics is None or self._canary_dockets.get(d.canary_id) != key
                    or d.source_version != metrics.resulting_version
                    or d.resulting_version != d.source_version + 1
                    or not _synthetic(d.reviewer, "reviewer") or not isinstance(d.ready, bool)
                    or not _digest(d.review_digest) or d.metrics_receipt_digest != metrics.digest
                    or d.reviewer.rsplit(":", 1)[-1] == metrics.aggregator.rsplit(":", 1)[-1]
                    or d.digest != canonical_digest({"docket_id": d.docket_id,
                    "canary_id": d.canary_id, "source_version": d.source_version,
                    "resulting_version": d.resulting_version, "reviewer": d.reviewer,
                    "ready": d.ready, "review_digest": d.review_digest,
                    "metrics_receipt_digest": d.metrics_receipt_digest})):
                return False
        return len(self._canary_dockets) == len(self._dockets)

    def _batch_integrity(self) -> bool:
        seen: set[str] = set()
        for key, b in self._batches.items():
            if (key != b.batch_id or not _synthetic(b.batch_id, "readiness-batch")
                    or not 1 <= b.requested_limit <= MAX_PORTFOLIO_BATCH
                    or len(b.canary_ids) > b.requested_limit or len(set(b.canary_ids)) != len(b.canary_ids)
                    or seen.intersection(b.canary_ids)
                    or b.digest != canonical_digest({"batch_id": b.batch_id,
                    "requested_limit": b.requested_limit, "canary_ids": b.canary_ids})):
                return False
            seen.update(b.canary_ids)
        return True

    def _hold_integrity(self) -> bool:
        previous = None
        history = {r.digest: r for r in self._history}
        for index, hold in enumerate(self._holds, 1):
            payload = {k: hold[k] for k in ("sequence", "canary_id", "reason", "actor",
                                             "record_digest", "previous_digest")}
            row = history.get(hold["record_digest"])
            namespace = "reviewer" if hold["reason"] == "REVIEW_REJECTED" else "aggregator"
            if (hold["sequence"] != index or hold["previous_digest"] != previous
                    or hold["reason"] not in HOLD_REASONS or not _synthetic(hold["actor"], namespace)
                    or row is None or row.canary_id != hold["canary_id"] or row.status != "HELD"
                    or row.hold_reason != hold["reason"] or hold["digest"] != canonical_digest(payload)):
                return False
            previous = hold["digest"]
        return True

    def _event_integrity(self) -> bool:
        history = {r.digest: r for r in self._history}
        batches = {b.digest: set(b.canary_ids) for b in self._batches.values()}
        metrics = {m.digest: (m.canary_id, m.resulting_version) for m in self._metrics.values()}
        dockets = {d.digest: (d.canary_id, d.resulting_version, d.ready) for d in self._dockets.values()}
        previous = None
        for index, event in enumerate(self._events, 1):
            payload = {k: event[k] for k in ("sequence", "action", "record_digest",
                                              "attachment_digest", "previous_digest")}
            row = history.get(event["record_digest"])
            action, attachment = event["action"], event["attachment_digest"]
            valid = row is not None and (
                (action == "INTAKE" and row.status == "INTAKE" and attachment is None)
                or (action == "PORTFOLIO_BATCHED" and row.status == "PORTFOLIO_BATCHED"
                    and row.canary_id in batches.get(attachment, set()))
                or (action == "METRICS_ACCEPTED" and row.status == "METRICS_ACCEPTED"
                    and metrics.get(attachment) == (row.canary_id, row.version))
                or (action == "READINESS_REVIEWED" and row.status == "SYNTHETIC_READINESS_REVIEWED"
                    and dockets.get(attachment) == (row.canary_id, row.version, True))
                or (action == "AUTO_HELD" and row.status == "HELD"
                    and ((metrics.get(attachment) == (row.canary_id, row.version))
                         or (dockets.get(attachment) == (row.canary_id, row.version, False)))))
            if (event["sequence"] != index or event["previous_digest"] != previous
                    or event["digest"] != canonical_digest(payload) or not valid):
                return False
            previous = event["digest"]
        return True

    def _integrity(self) -> bool:
        return (self._record_integrity() and self._event_integrity() and self._receipt_integrity()
                and self._batch_integrity() and self._hold_integrity())

    def evidence(self) -> dict[str, object]:
        docket_digests = {d.digest for d in self._dockets.values()}
        used_valid = True
        for digest, canary_id in self._used_dockets.items():
            docket_id = self._canary_dockets.get(canary_id)
            docket = self._dockets.get(docket_id or "")
            metrics = self._metrics.get(canary_id)
            verifier = self._docket_verifiers.get(digest)
            if (digest not in docket_digests or docket is None or docket.digest != digest
                    or metrics is None or not _synthetic(verifier, "verifier")
                    or verifier.rsplit(":", 1)[-1] in {
                        docket.reviewer.rsplit(":", 1)[-1],
                        metrics.aggregator.rsplit(":", 1)[-1],
                    }):
                used_valid = False
                break
        if set(self._docket_verifiers) != set(self._used_dockets):
            used_valid = False
        return {"features": list(range(1501, 1701)), "feature_count": 200,
            "workstreams": [{"start": a, "end": b, "name": n, "control_count": b-a+1}
                            for a,b,n in WORKSTREAMS],
            "max_portfolio_batch": MAX_PORTFOLIO_BATCH, "record_count": len(self._rows),
            "history_chain_valid": self._record_integrity(),
            "event_chain_valid": self._event_integrity(),
            "receipt_integrity_valid": self._receipt_integrity(),
            "batch_integrity_valid": self._batch_integrity(),
            "hold_chain_valid": self._hold_integrity(), "docket_replay_index_valid": used_valid,
            "maximum_state": "SYNTHETIC_READINESS_REVIEWED",
            "approval_authority_allowed": False, "deployment_authority_allowed": False,
            "external_pg_api_used": False, "production_credentials_accessed": False,
            "payment_or_ledger_effect_allowed": False, "runtime_policy_change_allowed": False,
            "merge_allowed": False, "deployment_allowed": False}
