"""Synthetic-only release canary observation controls #1301-#1500.

This in-memory model never delivers data or performs a payment, ledger, network,
credential, deployment, merge, or runtime-policy operation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest


WORKSTREAMS = (
    (1301, 1325, "CANARY_INTAKE"),
    (1326, 1350, "BOUNDED_BATCH"),
    (1351, 1375, "NO_DELIVERY_OBSERVATION"),
    (1376, 1400, "THRESHOLD_DECISION"),
    (1401, 1425, "INDEPENDENT_REVIEW"),
    (1426, 1450, "REGRESSION_AUTO_HOLD"),
    (1451, 1475, "COMPLETION_RECEIPT_REPLAY_DEFENSE"),
    (1476, 1500, "AUDIT_EVIDENCE"),
)
MAX_CANARY_BATCH = 10
ALLOWED_HOLD_REASONS = {"ERROR_RATE_REGRESSION", "LATENCY_REGRESSION", "REVIEW_REJECTED", "INTEGRITY_DRIFT"}


def _synthetic(value: object, namespace: str) -> bool:
    return isinstance(value, str) and value.startswith(f"synthetic:{namespace}:")


def _digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None


@dataclass(frozen=True)
class CanaryRecord:
    canary_id: str
    release_attestation_digest: str
    status: str
    version: int
    error_budget_bps: int
    latency_budget_ms: int
    observer: str | None
    hold_reason: str | None
    previous_digest: str | None
    digest: str


@dataclass(frozen=True)
class CanaryBatch:
    batch_id: str
    requested_limit: int
    canary_ids: tuple[str, ...]
    digest: str


@dataclass(frozen=True)
class ObservationReceipt:
    canary_id: str
    source_version: int
    resulting_version: int
    observer: str
    sample_count: int
    error_count: int
    p95_latency_ms: int
    observation_digest: str
    digest: str


@dataclass(frozen=True)
class ReviewReceipt:
    canary_id: str
    source_version: int
    resulting_version: int
    reviewer: str
    approved: bool
    review_digest: str
    digest: str


@dataclass(frozen=True)
class CompletionReceipt:
    canary_id: str
    source_version: int
    resulting_version: int
    issuer: str
    review_receipt_digest: str
    issued_at: datetime
    digest: str


class SyntheticReleaseCanaryObservation:
    """Thread-safe, bounded, role-separated synthetic canary state machine."""

    def __init__(self) -> None:
        self._rows: dict[str, CanaryRecord] = {}
        self._history: list[CanaryRecord] = []
        self._events: list[dict[str, object]] = []
        self._batches: dict[str, CanaryBatch] = {}
        self._observations: dict[str, ObservationReceipt] = {}
        self._reviews: dict[str, ReviewReceipt] = {}
        self._receipts: dict[str, CompletionReceipt] = {}
        self._used_receipts: dict[str, str] = {}
        self._holds: list[dict[str, object]] = []
        self._lock = RLock()

    @staticmethod
    def _record_digest(canary_id: str, release_digest: str, status: str, version: int,
                       error_budget_bps: int, latency_budget_ms: int, observer: str | None,
                       hold_reason: str | None, previous_digest: str | None) -> str:
        return canonical_digest({"canary_id": canary_id, "release_attestation_digest": release_digest,
            "status": status, "version": version, "error_budget_bps": error_budget_bps,
            "latency_budget_ms": latency_budget_ms, "observer": observer,
            "hold_reason": hold_reason, "previous_digest": previous_digest})

    def _make(self, canary_id: str, release_digest: str, status: str, version: int,
              error_budget_bps: int, latency_budget_ms: int, observer: str | None = None,
              hold_reason: str | None = None, previous_digest: str | None = None) -> CanaryRecord:
        if (not _synthetic(canary_id, "canary") or not _digest(release_digest)
                or not isinstance(version, int) or isinstance(version, bool) or version < 1
                or not isinstance(error_budget_bps, int) or isinstance(error_budget_bps, bool)
                or not 0 <= error_budget_bps <= 10_000
                or not isinstance(latency_budget_ms, int) or isinstance(latency_budget_ms, bool)
                or not 1 <= latency_budget_ms <= 60_000
                or (observer is not None and not _synthetic(observer, "observer"))
                or (hold_reason is not None and hold_reason not in ALLOWED_HOLD_REASONS)):
            raise GovernanceRejected("valid synthetic canary record required")
        value = self._record_digest(canary_id, release_digest, status, version, error_budget_bps,
                                    latency_budget_ms, observer, hold_reason, previous_digest)
        return CanaryRecord(canary_id, release_digest, status, version, error_budget_bps,
                            latency_budget_ms, observer, hold_reason, previous_digest, value)

    def _append(self, action: str, item: CanaryRecord, attachment: str | None = None) -> CanaryRecord:
        previous = self._events[-1]["digest"] if self._events else None
        payload = {"sequence": len(self._events) + 1, "action": action,
                   "record_digest": item.digest, "attachment_digest": attachment,
                   "previous_digest": previous}
        self._history.append(item)
        self._events.append({**payload, "digest": canonical_digest(payload)})
        self._rows[item.canary_id] = item
        return item

    def _transition(self, old: CanaryRecord, action: str, status: str, *, observer: str | None = None,
                    hold_reason: str | None = None, attachment: str | None = None) -> CanaryRecord:
        item = self._make(old.canary_id, old.release_attestation_digest, status, old.version + 1,
                          old.error_budget_bps, old.latency_budget_ms,
                          old.observer if observer is None else observer, hold_reason, old.digest)
        return self._append(action, item, attachment)

    def _require(self, canary_id: str, version: int, status: str | None = None) -> CanaryRecord:
        item = self._rows.get(canary_id)
        if item is None or item.version != version or (status is not None and item.status != status):
            raise GovernanceRejected("current canary state and version required")
        return item

    def intake(self, canary_id: str, release_attestation_digest: str,
               error_budget_bps: int, latency_budget_ms: int) -> CanaryRecord:
        with self._lock:
            existing = self._rows.get(canary_id)
            if existing:
                if (existing.release_attestation_digest, existing.error_budget_bps,
                    existing.latency_budget_ms) == (release_attestation_digest, error_budget_bps, latency_budget_ms):
                    return existing
                raise GovernanceRejected("canary intake conflict")
            return self._append("INTAKE", self._make(canary_id, release_attestation_digest,
                "INTAKE", 1, error_budget_bps, latency_budget_ms))

    def reserve_batch(self, batch_id: str, limit: int) -> CanaryBatch:
        if (not _synthetic(batch_id, "canary-batch") or not isinstance(limit, int)
                or isinstance(limit, bool) or not 1 <= limit <= MAX_CANARY_BATCH):
            raise GovernanceRejected("bounded synthetic canary batch required")
        with self._lock:
            existing = self._batches.get(batch_id)
            if existing:
                if existing.requested_limit == limit:
                    return existing
                raise GovernanceRejected("canary batch conflict")
            chosen = sorted((r for r in self._rows.values() if r.status == "INTAKE"),
                            key=lambda r: (r.version, r.canary_id))[:limit]
            ids = tuple(r.canary_id for r in chosen)
            batch_digest = canonical_digest({"batch_id": batch_id, "requested_limit": limit, "canary_ids": ids})
            batch = CanaryBatch(batch_id, limit, ids, batch_digest)
            self._batches[batch_id] = batch
            for row in chosen:
                self._transition(row, "BATCHED", "BATCHED", attachment=batch.digest)
            return batch

    def observe(self, canary_id: str, expected_version: int, observer: str, sample_count: int,
                error_count: int, p95_latency_ms: int, observation_digest: str) -> CanaryRecord:
        if (not _synthetic(observer, "observer") or not _digest(observation_digest)
                or not isinstance(sample_count, int) or isinstance(sample_count, bool) or sample_count < 1
                or not isinstance(error_count, int) or isinstance(error_count, bool)
                or not 0 <= error_count <= sample_count
                or not isinstance(p95_latency_ms, int) or isinstance(p95_latency_ms, bool)
                or not 0 <= p95_latency_ms <= 60_000):
            raise GovernanceRejected("valid no-delivery synthetic observation required")
        with self._lock:
            prior = self._observations.get(canary_id)
            fields = (expected_version, observer, sample_count, error_count, p95_latency_ms, observation_digest)
            if prior:
                if fields == (prior.source_version, prior.observer, prior.sample_count, prior.error_count,
                              prior.p95_latency_ms, prior.observation_digest):
                    return self._rows[canary_id]
                raise GovernanceRejected("observation conflict")
            old = self._require(canary_id, expected_version, "BATCHED")
            resulting = expected_version + 1
            receipt_digest = canonical_digest({"canary_id": canary_id, "source_version": expected_version,
                "resulting_version": resulting, "observer": observer, "sample_count": sample_count,
                "error_count": error_count, "p95_latency_ms": p95_latency_ms,
                "observation_digest": observation_digest})
            receipt = ObservationReceipt(canary_id, expected_version, resulting, observer, sample_count,
                                         error_count, p95_latency_ms, observation_digest, receipt_digest)
            self._observations[canary_id] = receipt
            if error_count * 10_000 > old.error_budget_bps * sample_count:
                return self._auto_hold(old, observer, "ERROR_RATE_REGRESSION", receipt.digest)
            if p95_latency_ms > old.latency_budget_ms:
                return self._auto_hold(old, observer, "LATENCY_REGRESSION", receipt.digest)
            return self._transition(old, "THRESHOLD_PASSED", "THRESHOLD_PASSED",
                                    observer=observer, attachment=receipt.digest)

    def _auto_hold(self, old: CanaryRecord, actor: str, reason: str, attachment: str) -> CanaryRecord:
        item = self._transition(old, "AUTO_HELD", "HELD",
                                hold_reason=reason, attachment=attachment)
        previous = self._holds[-1]["digest"] if self._holds else None
        payload = {"sequence": len(self._holds) + 1, "canary_id": old.canary_id,
                   "reason": reason, "actor": actor, "record_digest": item.digest,
                   "previous_digest": previous}
        self._holds.append({**payload, "digest": canonical_digest(payload)})
        return item

    def review(self, canary_id: str, expected_version: int, reviewer: str,
               approved: bool, review_digest: str) -> CanaryRecord:
        if (not _synthetic(reviewer, "reviewer") or not isinstance(approved, bool) or not _digest(review_digest)):
            raise GovernanceRejected("valid independent review required")
        with self._lock:
            prior = self._reviews.get(canary_id)
            fields = (expected_version, reviewer, approved, review_digest)
            if prior:
                if fields == (prior.source_version, prior.reviewer, prior.approved, prior.review_digest):
                    return self._rows[canary_id]
                raise GovernanceRejected("review conflict")
            old = self._require(canary_id, expected_version, "THRESHOLD_PASSED")
            observation = self._observations[canary_id]
            if reviewer.replace("synthetic:reviewer:", "") == observation.observer.replace("synthetic:observer:", ""):
                raise GovernanceRejected("observer and reviewer must be independent")
            resulting = expected_version + 1
            value = canonical_digest({"canary_id": canary_id, "source_version": expected_version,
                "resulting_version": resulting, "reviewer": reviewer, "approved": approved,
                "review_digest": review_digest})
            receipt = ReviewReceipt(canary_id, expected_version, resulting, reviewer, approved, review_digest, value)
            self._reviews[canary_id] = receipt
            if not approved:
                return self._auto_hold(old, reviewer, "REVIEW_REJECTED", receipt.digest)
            return self._transition(old, "REVIEW_APPROVED", "REVIEW_APPROVED", attachment=receipt.digest)

    def issue_completion(self, canary_id: str, expected_version: int, issuer: str,
                         issued_at: datetime) -> CanaryRecord:
        if not _synthetic(issuer, "issuer") or not _aware(issued_at):
            raise GovernanceRejected("valid synthetic issuer and timestamp required")
        with self._lock:
            prior = self._receipts.get(canary_id)
            if prior:
                if (prior.source_version, prior.issuer, prior.issued_at) == (expected_version, issuer, issued_at):
                    return self._rows[canary_id]
                raise GovernanceRejected("completion receipt conflict")
            old = self._require(canary_id, expected_version, "REVIEW_APPROVED")
            if not self._integrity():
                raise GovernanceRejected("integral canary evidence required")
            observation = self._observations[canary_id]
            review = self._reviews[canary_id]
            if issuer.endswith(observation.observer.rsplit(":", 1)[-1]) or issuer.endswith(review.reviewer.rsplit(":", 1)[-1]):
                raise GovernanceRejected("issuer must be independent")
            resulting = expected_version + 1
            value = canonical_digest({"canary_id": canary_id, "source_version": expected_version,
                "resulting_version": resulting, "issuer": issuer,
                "review_receipt_digest": review.digest, "issued_at": issued_at.isoformat()})
            if value in self._used_receipts:
                raise GovernanceRejected("completion receipt replay")
            receipt = CompletionReceipt(canary_id, expected_version, resulting, issuer,
                                        review.digest, issued_at, value)
            self._receipts[canary_id] = receipt
            return self._transition(old, "RECEIPT_ISSUED", "RECEIPT_ISSUED", attachment=value)

    def complete(self, canary_id: str, expected_version: int, receipt_digest: str) -> CanaryRecord:
        with self._lock:
            old = self._require(canary_id, expected_version, "RECEIPT_ISSUED")
            receipt = self._receipts.get(canary_id)
            if (receipt is None or receipt.digest != receipt_digest or not self._integrity()
                    or receipt.resulting_version != old.version):
                raise GovernanceRejected("current integral completion receipt required")
            owner = self._used_receipts.get(receipt_digest)
            if owner is not None and owner != canary_id:
                raise GovernanceRejected("completion receipt replay")
            self._used_receipts[receipt_digest] = canary_id
            return self._transition(old, "OBSERVATION_COMPLETE", "OBSERVATION_COMPLETE", attachment=receipt_digest)

    def get(self, canary_id: str) -> CanaryRecord:
        return self._rows[canary_id]

    def _integrity(self) -> bool:
        previous_by_canary: dict[str, str] = {}
        latest_by_canary: dict[str, CanaryRecord] = {}
        for row in self._history:
            expected_previous = previous_by_canary.get(row.canary_id)
            if row.previous_digest != expected_previous or row.digest != self._record_digest(
                    row.canary_id, row.release_attestation_digest, row.status, row.version,
                    row.error_budget_bps, row.latency_budget_ms, row.observer, row.hold_reason,
                    row.previous_digest):
                return False
            previous_by_canary[row.canary_id] = row.digest
            latest_by_canary[row.canary_id] = row
        if self._rows != latest_by_canary:
            return False
        observations = {
            receipt.digest: (receipt.canary_id, receipt.resulting_version)
            for receipt in self._observations.values()
        }
        reviews = {
            receipt.digest: (receipt.canary_id, receipt.resulting_version)
            for receipt in self._reviews.values()
        }
        completions = {
            receipt.digest: (receipt.canary_id, receipt.resulting_version)
            for receipt in self._receipts.values()
        }
        batches = {batch.digest: set(batch.canary_ids) for batch in self._batches.values()}
        history = {row.digest: row for row in self._history}
        previous = None
        for i, event in enumerate(self._events, 1):
            payload = {k: event[k] for k in ("sequence", "action", "record_digest", "attachment_digest", "previous_digest")}
            if event["sequence"] != i or event["previous_digest"] != previous or event["digest"] != canonical_digest(payload):
                return False
            row = history.get(event["record_digest"])
            attachment = event["attachment_digest"]
            action = event["action"]
            if row is None:
                return False
            if action == "INTAKE":
                if attachment is not None or row.status != "INTAKE":
                    return False
            elif action == "BATCHED":
                if row.status != "BATCHED" or row.canary_id not in batches.get(attachment, set()):
                    return False
            elif action == "THRESHOLD_PASSED":
                if row.status != "THRESHOLD_PASSED" or observations.get(attachment) != (row.canary_id, row.version):
                    return False
            elif action == "REVIEW_APPROVED":
                if row.status != "REVIEW_APPROVED" or reviews.get(attachment) != (row.canary_id, row.version):
                    return False
            elif action == "RECEIPT_ISSUED":
                if row.status != "RECEIPT_ISSUED" or completions.get(attachment) != (row.canary_id, row.version):
                    return False
            elif action == "OBSERVATION_COMPLETE":
                if row.status != "OBSERVATION_COMPLETE" or attachment not in completions:
                    return False
            elif action == "AUTO_HELD":
                expected = observations.get(attachment) or reviews.get(attachment)
                if row.status != "HELD" or expected != (row.canary_id, row.version):
                    return False
            else:
                return False
            previous = event["digest"]
        return self._receipt_integrity() and self._batch_integrity() and self._hold_integrity()

    def _receipt_integrity(self) -> bool:
        for key, r in self._observations.items():
            if (key != r.canary_id or not _synthetic(r.observer, "observer")
                    or not 1 <= r.sample_count or not 0 <= r.error_count <= r.sample_count
                    or not 0 <= r.p95_latency_ms <= 60_000
                    or not _digest(r.observation_digest)
                    or r.resulting_version != r.source_version + 1
                    or r.digest != canonical_digest({"canary_id": r.canary_id, "source_version": r.source_version,
                    "resulting_version": r.resulting_version, "observer": r.observer, "sample_count": r.sample_count,
                    "error_count": r.error_count, "p95_latency_ms": r.p95_latency_ms,
                    "observation_digest": r.observation_digest})): return False
        for key, r in self._reviews.items():
            observation = self._observations.get(key)
            if (key != r.canary_id or observation is None
                    or not _synthetic(r.reviewer, "reviewer") or not isinstance(r.approved, bool)
                    or not _digest(r.review_digest) or r.source_version != observation.resulting_version
                    or r.resulting_version != r.source_version + 1
                    or r.reviewer.rsplit(":", 1)[-1] == observation.observer.rsplit(":", 1)[-1]
                    or r.digest != canonical_digest({"canary_id": r.canary_id, "source_version": r.source_version,
                    "resulting_version": r.resulting_version, "reviewer": r.reviewer, "approved": r.approved,
                    "review_digest": r.review_digest})): return False
        for key, r in self._receipts.items():
            observation = self._observations.get(key)
            review = self._reviews.get(key)
            if (key != r.canary_id or observation is None or review is None or not review.approved
                    or not _synthetic(r.issuer, "issuer") or not _aware(r.issued_at)
                    or r.review_receipt_digest != review.digest
                    or r.source_version != review.resulting_version
                    or r.resulting_version != r.source_version + 1
                    or r.issuer.rsplit(":", 1)[-1] in {
                        observation.observer.rsplit(":", 1)[-1], review.reviewer.rsplit(":", 1)[-1]
                    }
                    or r.digest != canonical_digest({"canary_id": r.canary_id, "source_version": r.source_version,
                    "resulting_version": r.resulting_version, "issuer": r.issuer,
                    "review_receipt_digest": r.review_receipt_digest, "issued_at": r.issued_at.isoformat()})): return False
        return True

    def _batch_integrity(self) -> bool:
        return all(k == b.batch_id and len(b.canary_ids) <= b.requested_limit <= MAX_CANARY_BATCH
                   and len(set(b.canary_ids)) == len(b.canary_ids)
                   and b.digest == canonical_digest({"batch_id": b.batch_id, "requested_limit": b.requested_limit,
                                                     "canary_ids": b.canary_ids})
                   for k, b in self._batches.items())

    def _hold_integrity(self) -> bool:
        previous = None
        history = {row.digest: row for row in self._history}
        for i, h in enumerate(self._holds, 1):
            payload = {k: h[k] for k in ("sequence", "canary_id", "reason", "actor", "record_digest", "previous_digest")}
            row = history.get(h["record_digest"])
            actor_valid = (
                _synthetic(h["actor"], "observer")
                if h["reason"] in {"ERROR_RATE_REGRESSION", "LATENCY_REGRESSION"}
                else _synthetic(h["actor"], "reviewer")
            )
            if (h["sequence"] != i or h["previous_digest"] != previous
                    or h["reason"] not in ALLOWED_HOLD_REASONS or not actor_valid
                    or row is None or row.canary_id != h["canary_id"] or row.status != "HELD"
                    or row.hold_reason != h["reason"] or h["digest"] != canonical_digest(payload)): return False
            previous = h["digest"]
        return True

    def evidence(self) -> dict[str, object]:
        valid = self._integrity()
        receipt_digests = {r.digest for r in self._receipts.values()}
        replay_valid = all(
            d in receipt_digests
            and c in self._receipts
            and self._receipts[c].canary_id == c
            and self._receipts[c].digest == d
            for d, c in self._used_receipts.items()
        )
        return {"features": list(range(1301, 1501)), "feature_count": 200,
            "workstreams": [{"start": a, "end": b, "name": n, "control_count": b-a+1} for a,b,n in WORKSTREAMS],
            "max_canary_batch": MAX_CANARY_BATCH, "record_count": len(self._rows),
            "history_chain_valid": valid, "event_chain_valid": valid,
            "receipt_integrity_valid": self._receipt_integrity(), "batch_integrity_valid": self._batch_integrity(),
            "hold_chain_valid": self._hold_integrity(),
            "replay_index_valid": replay_valid,
            "automatic_approval_allowed": False, "external_delivery_used": False,
            "external_pg_api_used": False, "production_outcome_recorded": False,
            "production_credentials_accessed": False, "payment_or_ledger_effect_allowed": False,
            "runtime_policy_change_allowed": False, "merge_allowed": False, "deployment_allowed": False}
