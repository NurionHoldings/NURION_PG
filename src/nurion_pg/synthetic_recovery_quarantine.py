"""Synthetic-only recovery quarantine and release controls #1101-#1300.

No method performs delivery, payment processing, ledger mutation, external I/O,
or production policy changes.  The service models fail-closed, in-memory gates
between a recovered packet and a synthetic release observation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest


WORKSTREAMS = (
    (1101, 1125, "QUARANTINE_INTAKE"),
    (1126, 1150, "BOUNDED_PROBE_SCHEDULING"),
    (1151, 1175, "INDEPENDENT_PROBE_REVIEW"),
    (1176, 1200, "COOLDOWN_ENFORCEMENT"),
    (1201, 1225, "RELEASE_ATTESTATION"),
    (1226, 1250, "REPLAY_PREVENTION"),
    (1251, 1275, "EMERGENCY_HOLD"),
    (1276, 1300, "AUDIT_EVIDENCE"),
)
SEVERITY_SCORE = {"LOW": 10, "MEDIUM": 20, "HIGH": 30, "CRITICAL": 40}
MAX_PROBE_BATCH = 20
MIN_COOLDOWN = timedelta(minutes=5)
MAX_COOLDOWN = timedelta(hours=24)
HOLD_REASONS = {"INTEGRITY_DRIFT", "RELAY_REGRESSION", "REVIEW_CONFLICT"}


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None


def _hex_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(ch in "0123456789abcdef" for ch in value)
    )


def _synthetic(value: object, namespace: str) -> bool:
    return isinstance(value, str) and value.startswith(f"synthetic:{namespace}:")


@dataclass(frozen=True)
class QuarantineRecord:
    packet_id: str
    recovery_receipt_digest: str
    severity: str
    status: str
    version: int
    entered_at: datetime
    cooldown_until: datetime
    hold_reason: str | None
    previous_digest: str | None
    digest: str


@dataclass(frozen=True)
class ProbeBatch:
    batch_id: str
    limit: int
    packet_ids: tuple[str, ...]
    digest: str


@dataclass(frozen=True)
class ProbeReceipt:
    packet_id: str
    source_version: int
    resulting_version: int
    reviewer: str
    passed: bool
    observation_digest: str
    digest: str


@dataclass(frozen=True)
class ReviewReceipt:
    packet_id: str
    source_version: int
    resulting_version: int
    reviewer: str
    approved: bool
    review_digest: str
    digest: str


@dataclass(frozen=True)
class ReleaseAttestation:
    packet_id: str
    source_version: int
    resulting_version: int
    issuer: str
    attestation_digest: str
    issued_at: datetime
    digest: str


class SyntheticRecoveryQuarantine:
    """Thread-safe, in-memory recovery quarantine with role-separated release."""

    def __init__(self) -> None:
        self._rows: dict[str, QuarantineRecord] = {}
        self._history: list[QuarantineRecord] = []
        self._events: list[dict[str, object]] = []
        self._batches: dict[str, ProbeBatch] = {}
        self._probe_receipts: dict[str, ProbeReceipt] = {}
        self._review_receipts: dict[str, ReviewReceipt] = {}
        self._attestations: dict[str, ReleaseAttestation] = {}
        self._used_attestation_digests: dict[str, str] = {}
        self._hold: tuple[str, str, datetime] | None = None
        self._hold_history: list[dict[str, object]] = []
        self._lock = RLock()

    @staticmethod
    def _record_digest(
        packet_id: str,
        recovery_receipt_digest: str,
        severity: str,
        status: str,
        version: int,
        entered_at: datetime,
        cooldown_until: datetime,
        hold_reason: str | None,
        previous_digest: str | None,
    ) -> str:
        return canonical_digest(
            {
                "packet_id": packet_id,
                "recovery_receipt_digest": recovery_receipt_digest,
                "severity": severity,
                "status": status,
                "version": version,
                "entered_at": entered_at.isoformat(),
                "cooldown_until": cooldown_until.isoformat(),
                "hold_reason": hold_reason,
                "previous_digest": previous_digest,
            }
        )

    def _make(
        self,
        packet_id: str,
        recovery_receipt_digest: str,
        severity: str,
        status: str,
        version: int,
        entered_at: datetime,
        cooldown_until: datetime,
        hold_reason: str | None = None,
        previous_digest: str | None = None,
    ) -> QuarantineRecord:
        if (
            not _synthetic(packet_id, "packet")
            or not _hex_digest(recovery_receipt_digest)
            or severity not in SEVERITY_SCORE
            or not _aware(entered_at)
            or not _aware(cooldown_until)
            or not MIN_COOLDOWN <= cooldown_until - entered_at <= MAX_COOLDOWN
            or not isinstance(version, int)
            or isinstance(version, bool)
            or version < 1
        ):
            raise GovernanceRejected("valid synthetic quarantine record required")
        digest = self._record_digest(
            packet_id,
            recovery_receipt_digest,
            severity,
            status,
            version,
            entered_at,
            cooldown_until,
            hold_reason,
            previous_digest,
        )
        return QuarantineRecord(
            packet_id,
            recovery_receipt_digest,
            severity,
            status,
            version,
            entered_at,
            cooldown_until,
            hold_reason,
            previous_digest,
            digest,
        )

    def _append(
        self,
        action: str,
        item: QuarantineRecord,
        attachment_digest: str | None = None,
    ) -> QuarantineRecord:
        previous = self._events[-1]["digest"] if self._events else None
        payload = {
            "action": action,
            "record_digest": item.digest,
            "attachment_digest": attachment_digest,
            "previous_digest": previous,
            "sequence": len(self._events) + 1,
        }
        self._history.append(item)
        self._events.append({**payload, "digest": canonical_digest(payload)})
        self._rows[item.packet_id] = item
        return item

    def _transition(
        self,
        old: QuarantineRecord,
        action: str,
        status: str,
        *,
        hold_reason: str | None = None,
        attachment_digest: str | None = None,
    ) -> QuarantineRecord:
        item = self._make(
            old.packet_id,
            old.recovery_receipt_digest,
            old.severity,
            status,
            old.version + 1,
            old.entered_at,
            old.cooldown_until,
            hold_reason,
            old.digest,
        )
        return self._append(action, item, attachment_digest)

    def _require(self, packet_id: str, expected_version: int) -> QuarantineRecord:
        item = self._rows.get(packet_id)
        if item is None or item.version != expected_version:
            raise GovernanceRejected("current quarantine version required")
        return item

    def quarantine(
        self,
        packet_id: str,
        recovery_receipt_digest: str,
        severity: str,
        entered_at: datetime,
        cooldown: timedelta,
    ) -> QuarantineRecord:
        if not isinstance(cooldown, timedelta):
            raise GovernanceRejected("bounded quarantine cooldown required")
        with self._lock:
            existing = self._rows.get(packet_id)
            if existing is not None:
                if (
                    existing.recovery_receipt_digest == recovery_receipt_digest
                    and existing.severity == severity
                    and existing.entered_at == entered_at
                    and existing.cooldown_until == entered_at + cooldown
                ):
                    return existing
                raise GovernanceRejected("quarantine packet conflict")
            item = self._make(
                packet_id,
                recovery_receipt_digest,
                severity,
                "QUARANTINED",
                1,
                entered_at,
                entered_at + cooldown,
            )
            return self._append("QUARANTINED", item)

    def reserve_probe_batch(self, batch_id: str, limit: int) -> ProbeBatch:
        if (
            not _synthetic(batch_id, "probe-batch")
            or not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= MAX_PROBE_BATCH
        ):
            raise GovernanceRejected("bounded synthetic probe batch required")
        with self._lock:
            existing = self._batches.get(batch_id)
            if existing is not None:
                if existing.limit == limit:
                    return existing
                raise GovernanceRejected("probe batch conflict")
            candidates = [r for r in self._rows.values() if r.status == "QUARANTINED"]
            candidates.sort(
                key=lambda r: (-SEVERITY_SCORE[r.severity], r.entered_at, r.packet_id)
            )
            selected = []
            for old in candidates[:limit]:
                selected.append(
                    self._transition(old, "PROBE_RESERVED", "PROBE_RESERVED").packet_id
                )
            payload = {"batch_id": batch_id, "limit": limit, "packet_ids": selected}
            batch = ProbeBatch(batch_id, limit, tuple(selected), canonical_digest(payload))
            self._batches[batch_id] = batch
            return batch

    @staticmethod
    def _probe_valid(receipt: object) -> bool:
        if (
            not isinstance(receipt, ProbeReceipt)
            or not _synthetic(receipt.packet_id, "packet")
            or not _synthetic(receipt.reviewer, "reviewer")
            or not isinstance(receipt.passed, bool)
            or not _hex_digest(receipt.observation_digest)
            or not isinstance(receipt.source_version, int)
            or isinstance(receipt.source_version, bool)
            or receipt.source_version < 1
            or receipt.resulting_version != receipt.source_version + 1
        ):
            return False
        payload = {
            "packet_id": receipt.packet_id,
            "source_version": receipt.source_version,
            "resulting_version": receipt.resulting_version,
            "reviewer": receipt.reviewer,
            "passed": receipt.passed,
            "observation_digest": receipt.observation_digest,
        }
        return receipt.digest == canonical_digest(payload)

    def record_probe(
        self,
        packet_id: str,
        expected_version: int,
        reviewer: str,
        passed: bool,
        observation_digest: str,
    ) -> QuarantineRecord:
        with self._lock:
            existing = self._probe_receipts.get(packet_id)
            if existing is not None:
                if (
                    existing.source_version == expected_version
                    and existing.reviewer == reviewer
                    and existing.passed == passed
                    and existing.observation_digest == observation_digest
                    and self._probe_valid(existing)
                ):
                    return self._rows[packet_id]
                raise GovernanceRejected("probe receipt conflict")
            old = self._require(packet_id, expected_version)
            if (
                old.status != "PROBE_RESERVED"
                or not _synthetic(reviewer, "reviewer")
                or not isinstance(passed, bool)
                or not _hex_digest(observation_digest)
            ):
                raise GovernanceRejected("valid independent probe required")
            payload = {
                "packet_id": packet_id,
                "source_version": old.version,
                "resulting_version": old.version + 1,
                "reviewer": reviewer,
                "passed": passed,
                "observation_digest": observation_digest,
            }
            receipt = ProbeReceipt(**payload, digest=canonical_digest(payload))
            item = self._transition(
                old,
                "PROBE_PASSED" if passed else "PROBE_FAILED",
                "PROBE_PASSED" if passed else "HELD",
                hold_reason=None if passed else "REVIEW_CONFLICT",
                attachment_digest=receipt.digest,
            )
            self._probe_receipts[packet_id] = receipt
            return item

    @staticmethod
    def _review_valid(receipt: object) -> bool:
        if (
            not isinstance(receipt, ReviewReceipt)
            or not _synthetic(receipt.packet_id, "packet")
            or not _synthetic(receipt.reviewer, "reviewer")
            or not isinstance(receipt.approved, bool)
            or not _hex_digest(receipt.review_digest)
            or not isinstance(receipt.source_version, int)
            or isinstance(receipt.source_version, bool)
            or receipt.source_version < 1
            or receipt.resulting_version != receipt.source_version + 1
        ):
            return False
        payload = {
            "packet_id": receipt.packet_id,
            "source_version": receipt.source_version,
            "resulting_version": receipt.resulting_version,
            "reviewer": receipt.reviewer,
            "approved": receipt.approved,
            "review_digest": receipt.review_digest,
        }
        return receipt.digest == canonical_digest(payload)

    def review_probe(
        self,
        packet_id: str,
        expected_version: int,
        reviewer: str,
        approved: bool,
        review_digest: str,
        observed_at: datetime,
    ) -> QuarantineRecord:
        if not _aware(observed_at):
            raise GovernanceRejected("aware review time required")
        with self._lock:
            existing = self._review_receipts.get(packet_id)
            if existing is not None:
                if (
                    existing.source_version == expected_version
                    and existing.reviewer == reviewer
                    and existing.approved == approved
                    and existing.review_digest == review_digest
                    and self._review_valid(existing)
                ):
                    return self._rows[packet_id]
                raise GovernanceRejected("review receipt conflict")
            old = self._require(packet_id, expected_version)
            probe = self._probe_receipts.get(packet_id)
            if (
                old.status != "PROBE_PASSED"
                or probe is None
                or not self._probe_valid(probe)
                or not _synthetic(reviewer, "reviewer")
                or reviewer == probe.reviewer
                or not isinstance(approved, bool)
                or not _hex_digest(review_digest)
                or observed_at < old.cooldown_until
            ):
                raise GovernanceRejected("separated review after cooldown required")
            payload = {
                "packet_id": packet_id,
                "source_version": old.version,
                "resulting_version": old.version + 1,
                "reviewer": reviewer,
                "approved": approved,
                "review_digest": review_digest,
            }
            receipt = ReviewReceipt(**payload, digest=canonical_digest(payload))
            item = self._transition(
                old,
                "REVIEW_APPROVED" if approved else "REVIEW_REJECTED",
                "REVIEW_APPROVED" if approved else "HELD",
                hold_reason=None if approved else "REVIEW_CONFLICT",
                attachment_digest=receipt.digest,
            )
            self._review_receipts[packet_id] = receipt
            return item

    @staticmethod
    def _attestation_valid(attestation: object) -> bool:
        if (
            not isinstance(attestation, ReleaseAttestation)
            or not _synthetic(attestation.packet_id, "packet")
            or not _synthetic(attestation.issuer, "issuer")
            or not _hex_digest(attestation.attestation_digest)
            or not _aware(attestation.issued_at)
            or not isinstance(attestation.source_version, int)
            or isinstance(attestation.source_version, bool)
            or attestation.source_version < 1
            or attestation.resulting_version != attestation.source_version + 1
        ):
            return False
        payload = {
            "packet_id": attestation.packet_id,
            "source_version": attestation.source_version,
            "resulting_version": attestation.resulting_version,
            "issuer": attestation.issuer,
            "attestation_digest": attestation.attestation_digest,
            "issued_at": attestation.issued_at.isoformat(),
        }
        return attestation.digest == canonical_digest(payload)

    def attest_release(
        self,
        packet_id: str,
        expected_version: int,
        issuer: str,
        attestation_digest: str,
        issued_at: datetime,
    ) -> QuarantineRecord:
        with self._lock:
            existing = self._attestations.get(packet_id)
            if existing is not None:
                if (
                    existing.source_version == expected_version
                    and existing.issuer == issuer
                    and existing.attestation_digest == attestation_digest
                    and existing.issued_at == issued_at
                    and self._attestation_valid(existing)
                ):
                    return self._rows[packet_id]
                raise GovernanceRejected("release attestation conflict")
            old = self._require(packet_id, expected_version)
            used_by = self._used_attestation_digests.get(attestation_digest)
            if (
                old.status != "REVIEW_APPROVED"
                or self._hold is not None
                or not _synthetic(issuer, "issuer")
                or not _hex_digest(attestation_digest)
                or not _aware(issued_at)
                or issued_at < old.cooldown_until
                or used_by not in {None, packet_id}
            ):
                raise GovernanceRejected("unique synthetic release attestation required")
            review = self._review_receipts.get(packet_id)
            probe = self._probe_receipts.get(packet_id)
            if (
                review is None
                or probe is None
                or issuer in {review.reviewer, probe.reviewer}
                or not self._review_valid(review)
                or not self._probe_valid(probe)
            ):
                raise GovernanceRejected("three-role separation required")
            payload = {
                "packet_id": packet_id,
                "source_version": old.version,
                "resulting_version": old.version + 1,
                "issuer": issuer,
                "attestation_digest": attestation_digest,
                "issued_at": issued_at.isoformat(),
            }
            attestation = ReleaseAttestation(**{**payload, "issued_at": issued_at}, digest=canonical_digest(payload))
            item = self._transition(
                old,
                "RELEASE_ATTESTED",
                "RELEASE_ATTESTED",
                attachment_digest=attestation.digest,
            )
            self._attestations[packet_id] = attestation
            self._used_attestation_digests[attestation_digest] = packet_id
            return item

    def release(
        self,
        packet_id: str,
        expected_version: int,
        attestation_digest: str,
    ) -> QuarantineRecord:
        with self._lock:
            old = self._require(packet_id, expected_version)
            attestation = self._attestations.get(packet_id)
            review = self._review_receipts.get(packet_id)
            probe = self._probe_receipts.get(packet_id)
            if (
                old.status != "RELEASE_ATTESTED"
                or self._hold is not None
                or attestation is None
                or review is None
                or probe is None
                or attestation.attestation_digest != attestation_digest
                or not self._attestation_valid(attestation)
                or not self._review_valid(review)
                or not self._probe_valid(probe)
                or attestation.issuer in {review.reviewer, probe.reviewer}
                or review.reviewer == probe.reviewer
                or probe.resulting_version + 1 != review.resulting_version
                or review.resulting_version + 1 != attestation.resulting_version
                or self._used_attestation_digests.get(attestation_digest) != packet_id
                or attestation.resulting_version != old.version
                or not self._history_valid()
                or not self._events_valid()
                or not self._hold_history_valid()
            ):
                raise GovernanceRejected("current unheld synthetic attestation required")
            return self._transition(old, "SYNTHETIC_RELEASED", "SYNTHETIC_RELEASED")

    def place_hold(self, hold_id: str, reason: str, placed_at: datetime) -> tuple[str, str, datetime]:
        if not _synthetic(hold_id, "hold") or reason not in HOLD_REASONS or not _aware(placed_at):
            raise GovernanceRejected("bounded synthetic hold required")
        with self._lock:
            value = (hold_id, reason, placed_at)
            if self._hold is not None:
                if self._hold == value:
                    return value
                raise GovernanceRejected("hold already active")
            payload = {
                "action": "HOLD_PLACED",
                "hold_id": hold_id,
                "reason": reason,
                "at": placed_at.isoformat(),
                "previous_digest": self._hold_history[-1]["digest"] if self._hold_history else None,
                "sequence": len(self._hold_history) + 1,
            }
            self._hold = value
            self._hold_history.append({**payload, "digest": canonical_digest(payload)})
            return value

    def clear_hold(
        self, hold_id: str, reviewer: str, clearance_digest: str, cleared_at: datetime
    ) -> None:
        if not _synthetic(reviewer, "hold-reviewer") or not _hex_digest(clearance_digest) or not _aware(cleared_at):
            raise GovernanceRejected("independent synthetic hold clearance required")
        with self._lock:
            if self._hold is None or self._hold[0] != hold_id or cleared_at < self._hold[2]:
                raise GovernanceRejected("matching active hold required")
            payload = {
                "action": "HOLD_CLEARED",
                "hold_id": hold_id,
                "reviewer": reviewer,
                "clearance_digest": clearance_digest,
                "at": cleared_at.isoformat(),
                "previous_digest": self._hold_history[-1]["digest"] if self._hold_history else None,
                "sequence": len(self._hold_history) + 1,
            }
            self._hold_history.append({**payload, "digest": canonical_digest(payload)})
            self._hold = None

    def get(self, packet_id: str) -> QuarantineRecord | None:
        with self._lock:
            return self._rows.get(packet_id)

    def _history_valid(self) -> bool:
        tips: dict[str, QuarantineRecord] = {}
        for item in self._history:
            previous = tips.get(item.packet_id)
            if item.previous_digest != (previous.digest if previous else None):
                return False
            if item.digest != self._record_digest(
                item.packet_id,
                item.recovery_receipt_digest,
                item.severity,
                item.status,
                item.version,
                item.entered_at,
                item.cooldown_until,
                item.hold_reason,
                item.previous_digest,
            ):
                return False
            tips[item.packet_id] = item
        return len(tips) == len(self._rows) and all(tips.get(k) == v for k, v in self._rows.items())

    def _attachments(self) -> dict[str, tuple[str, str, int]]:
        attachments: dict[str, tuple[str, str, int]] = {}
        for key, value in self._probe_receipts.items():
            if key == value.packet_id and self._probe_valid(value):
                attachments[value.digest] = ("PROBE", key, value.resulting_version)
        for key, value in self._review_receipts.items():
            if key == value.packet_id and self._review_valid(value):
                attachments[value.digest] = ("REVIEW", key, value.resulting_version)
        for key, value in self._attestations.items():
            if key == value.packet_id and self._attestation_valid(value):
                attachments[value.digest] = ("ATTESTATION", key, value.resulting_version)
        return attachments

    def _events_valid(self) -> bool:
        history = {item.digest: item for item in self._history}
        attachments = self._attachments()
        expected_types = {
            "PROBE_PASSED": "PROBE",
            "PROBE_FAILED": "PROBE",
            "REVIEW_APPROVED": "REVIEW",
            "REVIEW_REJECTED": "REVIEW",
            "RELEASE_ATTESTED": "ATTESTATION",
        }
        previous = None
        for sequence, event in enumerate(self._events, 1):
            item = history.get(event.get("record_digest"))
            if item is None or event.get("previous_digest") != previous:
                return False
            attachment = event.get("attachment_digest")
            expected = expected_types.get(event.get("action"))
            if expected is None:
                if attachment is not None:
                    return False
            elif attachments.get(attachment) != (expected, item.packet_id, item.version):
                return False
            payload = {
                "action": event.get("action"),
                "record_digest": event.get("record_digest"),
                "attachment_digest": attachment,
                "previous_digest": previous,
                "sequence": sequence,
            }
            if event.get("digest") != canonical_digest(payload):
                return False
            previous = event["digest"]
        return len(self._events) == len(self._history)

    def _hold_history_valid(self) -> bool:
        active: tuple[str, str, datetime] | None = None
        previous = None
        for sequence, event in enumerate(self._hold_history, 1):
            if event.get("previous_digest") != previous or event.get("sequence") != sequence:
                return False
            if event.get("action") == "HOLD_PLACED":
                if (
                    active is not None
                    or not _synthetic(event.get("hold_id"), "hold")
                    or event.get("reason") not in HOLD_REASONS
                ):
                    return False
                payload = {k: event[k] for k in ("action", "hold_id", "reason", "at", "previous_digest", "sequence")}
                try:
                    at = datetime.fromisoformat(event["at"])
                except (TypeError, ValueError):
                    return False
                if not _aware(at):
                    return False
                active = (event["hold_id"], event["reason"], at)
            elif event.get("action") == "HOLD_CLEARED":
                if (
                    active is None
                    or active[0] != event.get("hold_id")
                    or not _synthetic(event.get("reviewer"), "hold-reviewer")
                    or not _hex_digest(event.get("clearance_digest"))
                ):
                    return False
                payload = {k: event[k] for k in ("action", "hold_id", "reviewer", "clearance_digest", "at", "previous_digest", "sequence")}
                try:
                    cleared_at = datetime.fromisoformat(event["at"])
                except (TypeError, ValueError):
                    return False
                if not _aware(cleared_at) or cleared_at < active[2]:
                    return False
                active = None
            else:
                return False
            if event.get("digest") != canonical_digest(payload):
                return False
            previous = event["digest"]
        return active == self._hold

    def evidence(self) -> dict[str, object]:
        with self._lock:
            batches_valid = all(
                key == batch.batch_id
                and 1 <= batch.limit <= MAX_PROBE_BATCH
                and len(batch.packet_ids) <= batch.limit
                and batch.digest == canonical_digest(
                    {"batch_id": batch.batch_id, "limit": batch.limit, "packet_ids": list(batch.packet_ids)}
                )
                for key, batch in self._batches.items()
            )
            receipts_valid = (
                all(k == v.packet_id and self._probe_valid(v) for k, v in self._probe_receipts.items())
                and all(k == v.packet_id and self._review_valid(v) for k, v in self._review_receipts.items())
                and all(k == v.packet_id and self._attestation_valid(v) for k, v in self._attestations.items())
            )
            replay_index_valid = (
                len(self._used_attestation_digests) == len(self._attestations)
                and all(
                    self._used_attestation_digests.get(value.attestation_digest) == key
                    for key, value in self._attestations.items()
                )
            )
            statuses = {
                status: sum(row.status == status for row in self._rows.values())
                for status in sorted({row.status for row in self._rows.values()})
            }
            return {
                "schema": "nurion.pg.synthetic-recovery-quarantine.v1",
                "features": list(range(1101, 1301)),
                "feature_count": 200,
                "workstreams": [
                    {"start": start, "end": end, "name": name, "control_count": end - start + 1}
                    for start, end, name in WORKSTREAMS
                ],
                "max_probe_batch": MAX_PROBE_BATCH,
                "min_cooldown_seconds": int(MIN_COOLDOWN.total_seconds()),
                "max_cooldown_seconds": int(MAX_COOLDOWN.total_seconds()),
                "record_count": len(self._rows),
                "history_count": len(self._history),
                "event_count": len(self._events),
                "statuses": statuses,
                "probe_receipt_count": len(self._probe_receipts),
                "review_receipt_count": len(self._review_receipts),
                "attestation_count": len(self._attestations),
                "hold_active": self._hold is not None,
                "hold_event_count": len(self._hold_history),
                "history_chain_valid": self._history_valid(),
                "event_chain_valid": self._events_valid(),
                "receipt_integrity_valid": receipts_valid,
                "batch_integrity_valid": batches_valid,
                "replay_index_valid": replay_index_valid,
                "hold_history_valid": self._hold_history_valid(),
                "automatic_approval_allowed": False,
                "external_delivery_used": False,
                "external_pg_api_used": False,
                "production_outcome_recorded": False,
                "production_credentials_accessed": False,
                "payment_or_ledger_effect_allowed": False,
                "runtime_policy_change_allowed": False,
                "pattern_promotion_allowed": False,
                "merge_allowed": False,
                "deployment_allowed": False,
            }
