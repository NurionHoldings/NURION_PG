"""Synthetic-only readiness decision intent controls #1701-#1900.

An intent is an inert observation.  It is never an approval, authorization,
deployment instruction, payment instruction, or runtime-policy mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest


WORKSTREAMS = (
    (1701, 1725, "READINESS_DOCKET_INTAKE"),
    (1726, 1750, "BOUNDED_INTENT_BATCH"),
    (1751, 1775, "OPERATOR_INTENT_DRAFT"),
    (1776, 1800, "INDEPENDENT_INTENT_REVIEW"),
    (1801, 1825, "NON_AUTHORIZING_BOUNDARY"),
    (1826, 1850, "REJECTION_INTEGRITY_AUTO_HOLD"),
    (1851, 1875, "INTENT_RECEIPT_REPLAY_DEFENSE"),
    (1876, 1900, "AUDIT_EVIDENCE"),
)
MAX_INTENT_BATCH = 20
INTENT_KINDS = frozenset({
    "PROCEED_TO_SYNTHETIC_PLANNING",
    "HOLD_FOR_REVIEW",
    "REJECT_SYNTHETIC_PATH",
})
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
class IntentRecord:
    docket_id: str
    readiness_digest: str
    status: str
    version: int
    operator: str | None
    intent_kind: str | None
    hold_reason: str | None
    previous_digest: str | None
    digest: str


@dataclass(frozen=True)
class IntentBatch:
    batch_id: str
    requested_limit: int
    docket_ids: tuple[str, ...]
    digest: str


@dataclass(frozen=True)
class IntentDraft:
    draft_id: str
    docket_id: str
    source_version: int
    resulting_version: int
    operator: str
    intent_kind: str
    rationale_digest: str
    readiness_digest: str
    non_authorizing: bool
    non_executable: bool
    digest: str


@dataclass(frozen=True)
class IntentReview:
    review_id: str
    docket_id: str
    source_version: int
    resulting_version: int
    reviewer: str
    accepted: bool
    review_digest: str
    draft_digest: str
    digest: str


@dataclass(frozen=True)
class IntentReceipt:
    receipt_id: str
    docket_id: str
    source_version: int
    resulting_version: int
    verifier: str
    draft_digest: str
    review_digest: str
    non_authorizing: bool
    non_executable: bool
    digest: str


@dataclass(frozen=True)
class IntegrityFinding:
    finding_id: str
    docket_id: str
    source_version: int
    resulting_version: int
    auditor: str
    finding_digest: str
    digest: str


class SyntheticReadinessDecisionIntent:
    """Thread-safe append-only model for inert readiness decision intents."""

    def __init__(self) -> None:
        self._rows: dict[str, IntentRecord] = {}
        self._history: list[IntentRecord] = []
        self._events: list[dict[str, object]] = []
        self._batches: dict[str, IntentBatch] = {}
        self._drafts: dict[str, IntentDraft] = {}
        self._docket_drafts: dict[str, str] = {}
        self._reviews: dict[str, IntentReview] = {}
        self._docket_reviews: dict[str, str] = {}
        self._receipts: dict[str, IntentReceipt] = {}
        self._docket_receipts: dict[str, str] = {}
        self._used_review_digests: dict[str, str] = {}
        self._findings: dict[str, IntegrityFinding] = {}
        self._docket_findings: dict[str, str] = {}
        self._holds: list[dict[str, object]] = []
        self._lock = RLock()

    @staticmethod
    def _record_digest(docket_id: str, readiness_digest: str, status: str, version: int,
                       operator: str | None, intent_kind: str | None,
                       hold_reason: str | None, previous_digest: str | None) -> str:
        return canonical_digest({"docket_id": docket_id, "readiness_digest": readiness_digest,
            "status": status, "version": version, "operator": operator,
            "intent_kind": intent_kind, "hold_reason": hold_reason,
            "previous_digest": previous_digest})

    def _make(self, docket_id: str, readiness_digest: str, status: str, version: int,
              operator: str | None = None, intent_kind: str | None = None,
              hold_reason: str | None = None,
              previous_digest: str | None = None) -> IntentRecord:
        if (not _synthetic(docket_id, "readiness-docket") or not _digest(readiness_digest)
                or not _integer(version, 1, 1_000_000)
                or (operator is not None and not _synthetic(operator, "operator"))
                or (intent_kind is not None and intent_kind not in INTENT_KINDS)
                or (hold_reason is not None and hold_reason not in HOLD_REASONS)
                or (previous_digest is not None and not _digest(previous_digest))):
            raise GovernanceRejected("valid synthetic intent record required")
        value = self._record_digest(docket_id, readiness_digest, status, version, operator,
                                    intent_kind, hold_reason, previous_digest)
        return IntentRecord(docket_id, readiness_digest, status, version, operator,
                            intent_kind, hold_reason, previous_digest, value)

    def _append(self, action: str, row: IntentRecord,
                attachment: str | None = None) -> IntentRecord:
        previous = self._events[-1]["digest"] if self._events else None
        payload = {"sequence": len(self._events) + 1, "action": action,
                   "record_digest": row.digest, "attachment_digest": attachment,
                   "previous_digest": previous}
        self._history.append(row)
        self._events.append({**payload, "digest": canonical_digest(payload)})
        self._rows[row.docket_id] = row
        return row

    def _transition(self, old: IntentRecord, action: str, status: str, *,
                    operator: str | None = None, intent_kind: str | None = None,
                    hold_reason: str | None = None,
                    attachment: str | None = None) -> IntentRecord:
        row = self._make(old.docket_id, old.readiness_digest, status, old.version + 1,
            old.operator if operator is None else operator,
            old.intent_kind if intent_kind is None else intent_kind,
            hold_reason, old.digest)
        return self._append(action, row, attachment)

    def _require(self, docket_id: str, version: int, status: str) -> IntentRecord:
        row = self._rows.get(docket_id)
        if row is None or row.version != version or row.status != status:
            raise GovernanceRejected("current synthetic intent state and version required")
        return row

    def intake(self, docket_id: str, readiness_digest: str) -> IntentRecord:
        with self._lock:
            prior = self._rows.get(docket_id)
            if prior:
                if prior.readiness_digest == readiness_digest:
                    return prior
                raise GovernanceRejected("readiness docket intake conflict")
            return self._append("INTAKE", self._make(
                docket_id, readiness_digest, "DOCKET_RECEIVED", 1))

    def reserve_batch(self, batch_id: str, limit: int) -> IntentBatch:
        if not _synthetic(batch_id, "intent-batch") or not _integer(limit, 1, MAX_INTENT_BATCH):
            raise GovernanceRejected("bounded synthetic intent batch required")
        with self._lock:
            prior = self._batches.get(batch_id)
            if prior:
                if prior.requested_limit == limit:
                    return prior
                raise GovernanceRejected("intent batch conflict")
            selected = sorted((r for r in self._rows.values() if r.status == "DOCKET_RECEIVED"),
                              key=lambda r: (r.version, r.docket_id))[:limit]
            docket_ids = tuple(r.docket_id for r in selected)
            value = canonical_digest({"batch_id": batch_id, "requested_limit": limit,
                                      "docket_ids": docket_ids})
            batch = IntentBatch(batch_id, limit, docket_ids, value)
            self._batches[batch_id] = batch
            for row in selected:
                self._transition(row, "BATCH_RESERVED", "BATCHED", attachment=value)
            return batch

    def draft(self, draft_id: str, docket_id: str, expected_version: int, operator: str,
              intent_kind: str, rationale_digest: str) -> IntentRecord:
        if (not _synthetic(draft_id, "intent-draft") or not _synthetic(operator, "operator")
                or intent_kind not in INTENT_KINDS or not _digest(rationale_digest)):
            raise GovernanceRejected("valid inert synthetic intent draft required")
        with self._lock:
            prior = self._drafts.get(draft_id)
            fields = (docket_id, expected_version, operator, intent_kind, rationale_digest)
            if prior:
                if fields == (prior.docket_id, prior.source_version, prior.operator,
                              prior.intent_kind, prior.rationale_digest):
                    return self._rows[docket_id]
                raise GovernanceRejected("intent draft conflict")
            if docket_id in self._docket_drafts:
                raise GovernanceRejected("docket already has an intent draft")
            old = self._require(docket_id, expected_version, "BATCHED")
            if not self._integrity():
                raise GovernanceRejected("integral synthetic evidence required")
            resulting = expected_version + 1
            value = canonical_digest({"draft_id": draft_id, "docket_id": docket_id,
                "source_version": expected_version, "resulting_version": resulting,
                "operator": operator, "intent_kind": intent_kind,
                "rationale_digest": rationale_digest, "readiness_digest": old.readiness_digest,
                "non_authorizing": True, "non_executable": True})
            draft = IntentDraft(draft_id, docket_id, expected_version, resulting, operator,
                intent_kind, rationale_digest, old.readiness_digest, True, True, value)
            self._drafts[draft_id] = draft
            self._docket_drafts[docket_id] = draft_id
            return self._transition(old, "INTENT_DRAFTED", "INTENT_DRAFTED",
                operator=operator, intent_kind=intent_kind, attachment=value)

    def review(self, review_id: str, docket_id: str, expected_version: int, reviewer: str,
               accepted: bool, review_digest: str) -> IntentRecord:
        if (not _synthetic(review_id, "intent-review") or not _synthetic(reviewer, "reviewer")
                or not isinstance(accepted, bool) or not _digest(review_digest)):
            raise GovernanceRejected("valid independent synthetic review required")
        with self._lock:
            prior = self._reviews.get(review_id)
            fields = (docket_id, expected_version, reviewer, accepted, review_digest)
            if prior:
                if fields == (prior.docket_id, prior.source_version, prior.reviewer,
                              prior.accepted, prior.review_digest):
                    return self._rows[docket_id]
                raise GovernanceRejected("intent review conflict")
            if docket_id in self._docket_reviews:
                raise GovernanceRejected("docket already has an intent review")
            old = self._require(docket_id, expected_version, "INTENT_DRAFTED")
            draft = self._drafts.get(self._docket_drafts.get(docket_id, ""))
            if draft is None or _identity(reviewer) == _identity(draft.operator) or not self._integrity():
                raise GovernanceRejected("independent reviewer and integral draft required")
            resulting = expected_version + 1
            value = canonical_digest({"review_id": review_id, "docket_id": docket_id,
                "source_version": expected_version, "resulting_version": resulting,
                "reviewer": reviewer, "accepted": accepted, "review_digest": review_digest,
                "draft_digest": draft.digest})
            review = IntentReview(review_id, docket_id, expected_version, resulting, reviewer,
                                  accepted, review_digest, draft.digest, value)
            self._reviews[review_id] = review
            self._docket_reviews[docket_id] = review_id
            if not accepted:
                return self._auto_hold(old, reviewer, "REVIEW_REJECTED", value)
            return self._transition(old, "INTENT_REVIEWED", "INTENT_REVIEWED", attachment=value)

    def record_receipt(self, receipt_id: str, docket_id: str, expected_version: int,
                       review_digest: str, verifier: str) -> IntentRecord:
        if (not _synthetic(receipt_id, "intent-receipt") or not _digest(review_digest)
                or not _synthetic(verifier, "verifier")):
            raise GovernanceRejected("valid inert synthetic intent receipt required")
        with self._lock:
            prior = self._receipts.get(receipt_id)
            fields = (docket_id, expected_version, review_digest, verifier)
            if prior:
                if fields == (prior.docket_id, prior.source_version, prior.review_digest, prior.verifier):
                    return self._rows[docket_id]
                raise GovernanceRejected("intent receipt conflict")
            if docket_id in self._docket_receipts or review_digest in self._used_review_digests:
                raise GovernanceRejected("intent receipt reuse blocked")
            old = self._require(docket_id, expected_version, "INTENT_REVIEWED")
            draft = self._drafts.get(self._docket_drafts.get(docket_id, ""))
            review = self._reviews.get(self._docket_reviews.get(docket_id, ""))
            if (draft is None or review is None or not review.accepted
                    or review.digest != review_digest or review.docket_id != docket_id
                    or _identity(verifier) in {_identity(draft.operator), _identity(review.reviewer)}
                    or not self._integrity()):
                raise GovernanceRejected("current integral independently reviewed intent required")
            resulting = expected_version + 1
            value = canonical_digest({"receipt_id": receipt_id, "docket_id": docket_id,
                "source_version": expected_version, "resulting_version": resulting,
                "verifier": verifier, "draft_digest": draft.digest,
                "review_digest": review.digest, "non_authorizing": True,
                "non_executable": True})
            receipt = IntentReceipt(receipt_id, docket_id, expected_version, resulting, verifier,
                                    draft.digest, review.digest, True, True, value)
            self._receipts[receipt_id] = receipt
            self._docket_receipts[docket_id] = receipt_id
            self._used_review_digests[review.digest] = docket_id
            return self._transition(old, "INTENT_RECORDED", "SYNTHETIC_INTENT_RECORDED",
                                    attachment=value)

    def _auto_hold(self, old: IntentRecord, actor: str, reason: str,
                   attachment: str) -> IntentRecord:
        row = self._transition(old, "AUTO_HELD", "HELD", hold_reason=reason,
                               attachment=attachment)
        previous = self._holds[-1]["digest"] if self._holds else None
        payload = {"sequence": len(self._holds) + 1, "docket_id": old.docket_id,
                   "reason": reason, "actor": actor, "record_digest": row.digest,
                   "attachment_digest": attachment, "previous_digest": previous}
        self._holds.append({**payload, "digest": canonical_digest(payload)})
        return row

    def hold_integrity_drift(self, finding_id: str, docket_id: str, expected_version: int,
                             auditor: str, finding_digest: str) -> IntentRecord:
        if (not _synthetic(finding_id, "integrity-finding")
                or not _synthetic(auditor, "auditor") or not _digest(finding_digest)):
            raise GovernanceRejected("valid synthetic integrity finding required")
        with self._lock:
            prior = self._findings.get(finding_id)
            fields = (docket_id, expected_version, auditor, finding_digest)
            if prior:
                if fields == (prior.docket_id, prior.source_version, prior.auditor,
                              prior.finding_digest):
                    return self._rows[docket_id]
                raise GovernanceRejected("integrity finding conflict")
            if docket_id in self._docket_findings or not self._integrity():
                raise GovernanceRejected("unique finding over integral evidence required")
            old = self._rows.get(docket_id)
            if old is None or old.version != expected_version or old.status not in {
                    "BATCHED", "INTENT_DRAFTED", "INTENT_REVIEWED"}:
                raise GovernanceRejected("holdable current synthetic intent required")
            review = self._reviews.get(self._docket_reviews.get(docket_id, ""))
            identities = {
                _identity(value) for value in (
                    old.operator,
                    review.reviewer if review is not None else None,
                ) if value is not None
            }
            if _identity(auditor) in identities:
                raise GovernanceRejected("independent synthetic auditor required")
            resulting = expected_version + 1
            value = canonical_digest({"finding_id": finding_id, "docket_id": docket_id,
                "source_version": expected_version, "resulting_version": resulting,
                "auditor": auditor, "finding_digest": finding_digest})
            finding = IntegrityFinding(finding_id, docket_id, expected_version,
                                       resulting, auditor, finding_digest, value)
            self._findings[finding_id] = finding
            self._docket_findings[docket_id] = finding_id
            return self._auto_hold(old, auditor, "INTEGRITY_DRIFT", value)

    def get(self, docket_id: str) -> IntentRecord:
        return self._rows[docket_id]

    def receipt(self, receipt_id: str) -> IntentReceipt:
        return self._receipts[receipt_id]

    def review_receipt(self, review_id: str) -> IntentReview:
        return self._reviews[review_id]

    def _record_integrity(self) -> bool:
        previous: dict[str, str] = {}
        versions: dict[str, int] = {}
        latest: dict[str, IntentRecord] = {}
        for row in self._history:
            if (row.version != versions.get(row.docket_id, 0) + 1
                    or row.previous_digest != previous.get(row.docket_id)
                    or row.digest != self._record_digest(row.docket_id, row.readiness_digest,
                    row.status, row.version, row.operator, row.intent_kind,
                    row.hold_reason, row.previous_digest)):
                return False
            previous[row.docket_id] = row.digest
            versions[row.docket_id] = row.version
            latest[row.docket_id] = row
        return latest == self._rows

    def _batch_integrity(self) -> bool:
        seen: set[str] = set()
        for key, batch in self._batches.items():
            if (key != batch.batch_id or not _synthetic(key, "intent-batch")
                    or not _integer(batch.requested_limit, 1, MAX_INTENT_BATCH)
                    or len(batch.docket_ids) > batch.requested_limit
                    or len(set(batch.docket_ids)) != len(batch.docket_ids)
                    or seen.intersection(batch.docket_ids)
                    or batch.digest != canonical_digest({"batch_id": batch.batch_id,
                       "requested_limit": batch.requested_limit, "docket_ids": batch.docket_ids})):
                return False
            seen.update(batch.docket_ids)
        return True

    def _artifact_integrity(self) -> bool:
        history = {(row.docket_id, row.version): row for row in self._history}
        for key, draft in self._drafts.items():
            source = history.get((draft.docket_id, draft.source_version))
            result = history.get((draft.docket_id, draft.resulting_version))
            if (key != draft.draft_id or not _synthetic(draft.draft_id, "intent-draft")
                    or self._docket_drafts.get(draft.docket_id) != key
                    or draft.intent_kind not in INTENT_KINDS or not draft.non_authorizing
                    or not draft.non_executable or not _synthetic(draft.operator, "operator")
                    or not _digest(draft.rationale_digest) or not _digest(draft.readiness_digest)
                    or draft.resulting_version != draft.source_version + 1
                    or source is None or source.status != "BATCHED"
                    or source.readiness_digest != draft.readiness_digest
                    or result is None or result.status != "INTENT_DRAFTED"
                    or result.operator != draft.operator or result.intent_kind != draft.intent_kind
                    or draft.digest != canonical_digest({"draft_id": draft.draft_id,
                    "docket_id": draft.docket_id, "source_version": draft.source_version,
                    "resulting_version": draft.resulting_version, "operator": draft.operator,
                    "intent_kind": draft.intent_kind, "rationale_digest": draft.rationale_digest,
                    "readiness_digest": draft.readiness_digest,
                    "non_authorizing": True, "non_executable": True})):
                return False
        for key, review in self._reviews.items():
            draft = self._drafts.get(self._docket_drafts.get(review.docket_id, ""))
            result = history.get((review.docket_id, review.resulting_version))
            if (key != review.review_id or not _synthetic(review.review_id, "intent-review")
                    or draft is None
                    or self._docket_reviews.get(review.docket_id) != key
                    or review.source_version != draft.resulting_version
                    or review.resulting_version != review.source_version + 1
                    or review.draft_digest != draft.digest
                    or not _synthetic(review.reviewer, "reviewer")
                    or not isinstance(review.accepted, bool) or not _digest(review.review_digest)
                    or _identity(review.reviewer) == _identity(draft.operator)
                    or result is None
                    or result.status != ("INTENT_REVIEWED" if review.accepted else "HELD")
                    or review.digest != canonical_digest({"review_id": review.review_id,
                    "docket_id": review.docket_id, "source_version": review.source_version,
                    "resulting_version": review.resulting_version, "reviewer": review.reviewer,
                    "accepted": review.accepted, "review_digest": review.review_digest,
                    "draft_digest": review.draft_digest})):
                return False
        for key, receipt in self._receipts.items():
            draft = self._drafts.get(self._docket_drafts.get(receipt.docket_id, ""))
            review = self._reviews.get(self._docket_reviews.get(receipt.docket_id, ""))
            result = history.get((receipt.docket_id, receipt.resulting_version))
            if (key != receipt.receipt_id or not _synthetic(receipt.receipt_id, "intent-receipt")
                    or draft is None or review is None or not review.accepted
                    or self._docket_receipts.get(receipt.docket_id) != key
                    or receipt.source_version != review.resulting_version
                    or receipt.resulting_version != receipt.source_version + 1
                    or receipt.draft_digest != draft.digest or receipt.review_digest != review.digest
                    or not receipt.non_authorizing or not receipt.non_executable
                    or not _synthetic(receipt.verifier, "verifier")
                    or result is None or result.status != "SYNTHETIC_INTENT_RECORDED"
                    or _identity(receipt.verifier) in {
                        _identity(draft.operator), _identity(review.reviewer)}
                    or receipt.digest != canonical_digest({"receipt_id": receipt.receipt_id,
                    "docket_id": receipt.docket_id, "source_version": receipt.source_version,
                    "resulting_version": receipt.resulting_version, "verifier": receipt.verifier,
                    "draft_digest": receipt.draft_digest, "review_digest": receipt.review_digest,
                    "non_authorizing": True, "non_executable": True})):
                return False
        for key, finding in self._findings.items():
            source = history.get((finding.docket_id, finding.source_version))
            result = history.get((finding.docket_id, finding.resulting_version))
            review = self._reviews.get(self._docket_reviews.get(finding.docket_id, ""))
            if (key != finding.finding_id or not _synthetic(finding.finding_id, "integrity-finding")
                    or self._docket_findings.get(finding.docket_id) != key
                    or finding.resulting_version != finding.source_version + 1
                    or not _synthetic(finding.auditor, "auditor")
                    or not _digest(finding.finding_digest) or source is None
                    or source.status not in {"BATCHED", "INTENT_DRAFTED", "INTENT_REVIEWED"}
                    or _identity(finding.auditor) in {
                        _identity(value) for value in (
                            source.operator,
                            review.reviewer if review is not None else None,
                        ) if value is not None
                    }
                    or result is None
                    or result.status != "HELD" or result.hold_reason != "INTEGRITY_DRIFT"
                    or finding.digest != canonical_digest({"finding_id": finding.finding_id,
                    "docket_id": finding.docket_id, "source_version": finding.source_version,
                    "resulting_version": finding.resulting_version, "auditor": finding.auditor,
                    "finding_digest": finding.finding_digest})):
                return False
        return (len(self._docket_drafts) == len(self._drafts)
                and len(self._docket_reviews) == len(self._reviews)
                and len(self._docket_receipts) == len(self._receipts)
                and len(self._docket_findings) == len(self._findings))

    def _hold_integrity(self) -> bool:
        previous = None
        history = {row.digest: row for row in self._history}
        reviews = {review.digest: review for review in self._reviews.values()}
        findings = {finding.digest: finding for finding in self._findings.values()}
        for index, hold in enumerate(self._holds, 1):
            payload = {k: hold[k] for k in ("sequence", "docket_id", "reason", "actor",
                "record_digest", "attachment_digest", "previous_digest")}
            row = history.get(hold["record_digest"])
            review = reviews.get(hold["attachment_digest"])
            finding = findings.get(hold["attachment_digest"])
            attachment_valid = (
                hold["reason"] == "REVIEW_REJECTED" and review is not None
                and not review.accepted and review.docket_id == hold["docket_id"]
                and review.reviewer == hold["actor"]
            ) or (
                hold["reason"] == "INTEGRITY_DRIFT" and finding is not None
                and finding.docket_id == hold["docket_id"] and finding.auditor == hold["actor"]
            )
            if (hold["sequence"] != index or hold["previous_digest"] != previous
                    or hold["reason"] not in HOLD_REASONS or row is None
                    or row.docket_id != hold["docket_id"] or row.status != "HELD"
                    or row.hold_reason != hold["reason"] or not attachment_valid
                    or hold["digest"] != canonical_digest(payload)):
                return False
            previous = hold["digest"]
        return True

    def _event_integrity(self) -> bool:
        history = {row.digest: row for row in self._history}
        batches = {b.digest: set(b.docket_ids) for b in self._batches.values()}
        drafts = {d.digest: (d.docket_id, d.resulting_version) for d in self._drafts.values()}
        reviews = {r.digest: (r.docket_id, r.resulting_version, r.accepted)
                   for r in self._reviews.values()}
        receipts = {r.digest: (r.docket_id, r.resulting_version) for r in self._receipts.values()}
        findings = {f.digest: (f.docket_id, f.resulting_version) for f in self._findings.values()}
        previous = None
        for index, event in enumerate(self._events, 1):
            payload = {k: event[k] for k in ("sequence", "action", "record_digest",
                                             "attachment_digest", "previous_digest")}
            row = history.get(event["record_digest"])
            action, attachment = event["action"], event["attachment_digest"]
            valid = row is not None and (
                (action == "INTAKE" and row.status == "DOCKET_RECEIVED" and attachment is None)
                or (action == "BATCH_RESERVED" and row.status == "BATCHED"
                    and row.docket_id in batches.get(attachment, set()))
                or (action == "INTENT_DRAFTED" and row.status == "INTENT_DRAFTED"
                    and drafts.get(attachment) == (row.docket_id, row.version))
                or (action == "INTENT_REVIEWED" and row.status == "INTENT_REVIEWED"
                    and reviews.get(attachment) == (row.docket_id, row.version, True))
                or (action == "AUTO_HELD" and row.status == "HELD"
                    and (reviews.get(attachment) == (row.docket_id, row.version, False)
                         or findings.get(attachment) == (row.docket_id, row.version)))
                or (action == "INTENT_RECORDED" and row.status == "SYNTHETIC_INTENT_RECORDED"
                    and receipts.get(attachment) == (row.docket_id, row.version)))
            if (event["sequence"] != index or event["previous_digest"] != previous
                    or event["digest"] != canonical_digest(payload) or not valid):
                return False
            previous = event["digest"]
        return True

    def _replay_integrity(self) -> bool:
        if set(self._used_review_digests) != {r.review_digest for r in self._receipts.values()}:
            return False
        for digest, docket_id in self._used_review_digests.items():
            receipt = self._receipts.get(self._docket_receipts.get(docket_id, ""))
            if receipt is None or receipt.review_digest != digest or receipt.docket_id != docket_id:
                return False
        return True

    def _integrity(self) -> bool:
        return (self._record_integrity() and self._batch_integrity()
                and self._artifact_integrity() and self._hold_integrity()
                and self._event_integrity() and self._replay_integrity())

    def evidence(self) -> dict[str, object]:
        return {"features": list(range(1701, 1901)), "feature_count": 200,
            "workstreams": [{"start": a, "end": b, "name": n, "control_count": b-a+1}
                            for a, b, n in WORKSTREAMS],
            "intent_kind_allowlist": sorted(INTENT_KINDS),
            "max_intent_batch": MAX_INTENT_BATCH, "record_count": len(self._rows),
            "history_chain_valid": self._record_integrity(),
            "event_chain_valid": self._event_integrity(),
            "artifact_integrity_valid": self._artifact_integrity(),
            "batch_integrity_valid": self._batch_integrity(),
            "hold_chain_valid": self._hold_integrity(),
            "receipt_replay_index_valid": self._replay_integrity(),
            "maximum_state": "SYNTHETIC_INTENT_RECORDED",
            "approval_authority_allowed": False, "deployment_authority_allowed": False,
            "execution_authority_allowed": False, "external_pg_api_used": False,
            "production_credentials_accessed": False,
            "payment_or_ledger_effect_allowed": False,
            "runtime_policy_change_allowed": False, "prompt_change_allowed": False,
            "weight_change_allowed": False, "merge_allowed": False,
            "deployment_allowed": False}
