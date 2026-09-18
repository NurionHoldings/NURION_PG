"""Synthetic-only priority delivery and recovery controls #901-#1100.

The model deliberately stops before any external delivery.  It schedules and
records immutable in-memory decisions so that ordering, bounded work, archive
recovery, relay stabilization and evidence integrity can be tested safely.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from threading import RLock
from typing import Iterable

from .arkaon.governance import GovernanceRejected, canonical_digest


WORKSTREAMS = (
    (901, 925, "PRIORITY_SCHEDULING"),
    (926, 950, "BOUNDED_BATCH_DELIVERY"),
    (951, 975, "DUPLICATE_FULFILLED_ARCHIVE"),
    (976, 1000, "RECOVERABLE_ARCHIVE"),
    (1001, 1025, "RELAY_STABILIZATION"),
    (1026, 1050, "GAP_REPORT_BOUNDING"),
    (1051, 1075, "RECOVERY_VERIFICATION"),
    (1076, 1100, "AUDIT_EVIDENCE"),
)
PRIORITY_SCORE = {"LOW": 10, "NORMAL": 20, "HIGH": 30, "CRITICAL": 40}
MAX_BATCH_SIZE = 30
MAX_GAP_REPORT = 50
STABLE_RELAY_STREAK = 3
RECOVERABLE_REASONS = {"RELAY_UNSTABLE", "BOUNDED_RETRY", "MANUAL_REVIEW"}


def _hex_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(ch in "0123456789abcdef" for ch in value)
    )


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None


@dataclass(frozen=True)
class DeliveryRecord:
    packet_id: str
    intent_digest: str
    priority: str
    status: str
    version: int
    created_at: datetime
    archive_reason: str | None
    previous_digest: str | None
    digest: str


@dataclass(frozen=True)
class BatchReservation:
    batch_id: str
    requested_limit: int
    packet_ids: tuple[str, ...]
    record_digest: str


@dataclass(frozen=True)
class RecoveryReceipt:
    packet_id: str
    source_version: int
    resulting_version: int
    verifier: str
    receipt_digest: str
    relay_id: str
    record_digest: str


class SyntheticPriorityDeliveryRecovery:
    """Thread-safe, in-memory scheduler with fail-closed recovery gates."""

    def __init__(self) -> None:
        self._rows: dict[str, DeliveryRecord] = {}
        self._intent_active: dict[str, str] = {}
        self._fulfilled_intents: set[str] = set()
        self._history: list[DeliveryRecord] = []
        self._events: list[dict[str, object]] = []
        self._batches: dict[str, BatchReservation] = {}
        self._receipts: dict[str, RecoveryReceipt] = {}
        self._relay: dict[str, tuple[int, int, bool]] = {}
        self._gap_reports: list[tuple[str, ...]] = []
        self._lock = RLock()

    @staticmethod
    def _record_digest(
        packet_id: str,
        intent_digest: str,
        priority: str,
        status: str,
        version: int,
        created_at: datetime,
        archive_reason: str | None,
        previous_digest: str | None,
    ) -> str:
        return canonical_digest(
            {
                "packet_id": packet_id,
                "intent_digest": intent_digest,
                "priority": priority,
                "status": status,
                "version": version,
                "created_at": created_at.isoformat(),
                "archive_reason": archive_reason,
                "previous_digest": previous_digest,
            }
        )

    def _make(
        self,
        packet_id: str,
        intent_digest: str,
        priority: str,
        status: str,
        version: int,
        created_at: datetime,
        archive_reason: str | None = None,
        previous_digest: str | None = None,
    ) -> DeliveryRecord:
        if (
            not isinstance(packet_id, str)
            or not packet_id.startswith("synthetic:packet:")
            or not _hex_digest(intent_digest)
            or priority not in PRIORITY_SCORE
            or not _aware(created_at)
            or version < 1
        ):
            raise GovernanceRejected("valid synthetic packet required")
        digest = self._record_digest(
            packet_id,
            intent_digest,
            priority,
            status,
            version,
            created_at,
            archive_reason,
            previous_digest,
        )
        return DeliveryRecord(
            packet_id,
            intent_digest,
            priority,
            status,
            version,
            created_at,
            archive_reason,
            previous_digest,
            digest,
        )

    def _append(
        self,
        action: str,
        item: DeliveryRecord,
        attachment_digest: str | None = None,
    ) -> DeliveryRecord:
        previous_event = self._events[-1]["digest"] if self._events else None
        sequence = len(self._events) + 1
        payload = {
            "action": action,
            "packet_digest": item.digest,
            "attachment_digest": attachment_digest,
            "previous_digest": previous_event,
            "sequence": sequence,
        }
        self._history.append(item)
        self._events.append({**payload, "digest": canonical_digest(payload)})
        self._rows[item.packet_id] = item
        return item

    def _transition(
        self,
        old: DeliveryRecord,
        action: str,
        *,
        status: str | None = None,
        archive_reason: str | None = None,
        attachment_digest: str | None = None,
    ) -> DeliveryRecord:
        item = self._make(
            old.packet_id,
            old.intent_digest,
            old.priority,
            status or old.status,
            old.version + 1,
            old.created_at,
            archive_reason,
            old.digest,
        )
        return self._append(action, item, attachment_digest)

    def _require(self, packet_id: str, expected_version: int) -> DeliveryRecord:
        item = self._rows.get(packet_id)
        if item is None or item.version != expected_version:
            raise GovernanceRejected("current packet version required")
        return item

    def enqueue(
        self,
        packet_id: str,
        intent_digest: str,
        priority: str,
        created_at: datetime,
    ) -> DeliveryRecord:
        """Enqueue once, or archive a new packet if its intent was fulfilled."""
        with self._lock:
            existing_id = self._intent_active.get(intent_digest)
            if existing_id is not None:
                return self._rows[existing_id]
            if packet_id in self._rows:
                existing = self._rows[packet_id]
                if (
                    existing.intent_digest == intent_digest
                    and existing.priority == priority
                    and existing.created_at == created_at
                ):
                    return existing
                raise GovernanceRejected("packet id conflict")
            status = (
                "DUPLICATE_FULFILLED_ARCHIVED"
                if intent_digest in self._fulfilled_intents
                else "QUEUED"
            )
            reason = "FULFILLED_INTENT" if status != "QUEUED" else None
            item = self._make(
                packet_id, intent_digest, priority, status, 1, created_at, reason
            )
            self._append("DUPLICATE_ARCHIVED" if reason else "ENQUEUED", item)
            if status == "QUEUED":
                self._intent_active[intent_digest] = packet_id
            return item

    def reserve_batch(self, batch_id: str, limit: int) -> BatchReservation:
        """Reserve a deterministic priority batch; no external delivery occurs."""
        if (
            not isinstance(batch_id, str)
            or not batch_id.startswith("synthetic:batch:")
            or not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= MAX_BATCH_SIZE
        ):
            raise GovernanceRejected("bounded synthetic batch required")
        with self._lock:
            existing = self._batches.get(batch_id)
            if existing is not None:
                if existing.requested_limit == limit:
                    return existing
                raise GovernanceRejected("batch idempotency conflict")
            candidates = [row for row in self._rows.values() if row.status == "QUEUED"]
            candidates.sort(
                key=lambda row: (
                    -PRIORITY_SCORE[row.priority],
                    row.created_at,
                    row.packet_id,
                )
            )
            selected: list[str] = []
            for old in candidates[:limit]:
                item = self._transition(old, "BATCH_RESERVED", status="RESERVED")
                selected.append(item.packet_id)
            payload = {
                "batch_id": batch_id,
                "requested_limit": limit,
                "packet_ids": selected,
            }
            reservation = BatchReservation(
                batch_id,
                limit,
                tuple(selected),
                canonical_digest(payload),
            )
            self._batches[batch_id] = reservation
            return reservation

    def fulfill(
        self, packet_id: str, expected_version: int, observed_at: datetime
    ) -> DeliveryRecord:
        if not _aware(observed_at):
            raise GovernanceRejected("aware observation time required")
        with self._lock:
            old = self._require(packet_id, expected_version)
            if old.status != "RESERVED":
                raise GovernanceRejected("reserved packet required")
            item = self._transition(old, "FULFILLED", status="FULFILLED")
            self._fulfilled_intents.add(item.intent_digest)
            self._intent_active.pop(item.intent_digest, None)
            return item

    def archive_recoverable(
        self, packet_id: str, expected_version: int, reason: str
    ) -> DeliveryRecord:
        if reason not in RECOVERABLE_REASONS:
            raise GovernanceRejected("bounded recoverable reason required")
        with self._lock:
            old = self._require(packet_id, expected_version)
            if old.status not in {"QUEUED", "RESERVED"}:
                raise GovernanceRejected("active packet required")
            item = self._transition(
                old,
                "RECOVERABLE_ARCHIVED",
                status="RECOVERABLE_ARCHIVED",
                archive_reason=reason,
            )
            self._intent_active.pop(item.intent_digest, None)
            return item

    def observe_relay(
        self, relay_id: str, success: bool, idempotency_key: str
    ) -> tuple[int, int, bool]:
        if (
            not isinstance(relay_id, str)
            or not relay_id.startswith("synthetic:relay:")
            or not isinstance(success, bool)
            or not isinstance(idempotency_key, str)
            or not idempotency_key.startswith("synthetic:key:")
        ):
            raise GovernanceRejected("synthetic relay observation required")
        with self._lock:
            key = f"{relay_id}|{idempotency_key}"
            if not hasattr(self, "_relay_keys"):
                self._relay_keys: dict[str, tuple[bool, tuple[int, int, bool]]] = {}
            existing = self._relay_keys.get(key)
            if existing is not None:
                if existing[0] == success:
                    return existing[1]
                raise GovernanceRejected("relay observation conflict")
            failures, streak, _stable = self._relay.get(relay_id, (0, 0, False))
            if success:
                streak += 1
            else:
                failures += 1
                streak = 0
            state = (failures, streak, streak >= STABLE_RELAY_STREAK)
            self._relay[relay_id] = state
            self._relay_keys[key] = (success, state)
            return state

    def report_gaps(self, gaps: Iterable[str]) -> tuple[str, ...]:
        normalized = tuple(gaps)
        if (
            len(normalized) > MAX_GAP_REPORT
            or len(set(normalized)) != len(normalized)
            or any(
                not isinstance(gap, str)
                or not gap
                or len(gap) > 80
                or gap.startswith("http")
                for gap in normalized
            )
        ):
            raise GovernanceRejected("bounded unique local gaps required")
        ordered = tuple(sorted(normalized))
        with self._lock:
            self._gap_reports.append(ordered)
        return ordered

    @staticmethod
    def _receipt_valid(receipt: object) -> bool:
        if (
            not isinstance(receipt, RecoveryReceipt)
            or not receipt.verifier.startswith("synthetic:verifier:")
            or not receipt.relay_id.startswith("synthetic:relay:")
            or not _hex_digest(receipt.receipt_digest)
        ):
            return False
        payload = {
            "packet_id": receipt.packet_id,
            "source_version": receipt.source_version,
            "resulting_version": receipt.resulting_version,
            "verifier": receipt.verifier,
            "receipt_digest": receipt.receipt_digest,
            "relay_id": receipt.relay_id,
        }
        return receipt.record_digest == canonical_digest(payload)

    def verify_recovery(
        self,
        packet_id: str,
        expected_version: int,
        verifier: str,
        receipt_digest: str,
        relay_id: str,
    ) -> DeliveryRecord:
        with self._lock:
            existing = self._receipts.get(packet_id)
            if existing is not None:
                if (
                    existing.source_version == expected_version
                    and existing.verifier == verifier
                    and existing.receipt_digest == receipt_digest
                    and existing.relay_id == relay_id
                    and self._receipt_valid(existing)
                ):
                    return self._rows[packet_id]
                raise GovernanceRejected("recovery receipt conflict")
            old = self._require(packet_id, expected_version)
            if (
                old.status != "RECOVERABLE_ARCHIVED"
                or not isinstance(verifier, str)
                or not verifier.startswith("synthetic:verifier:")
                or not _hex_digest(receipt_digest)
                or not self._relay.get(relay_id, (0, 0, False))[2]
            ):
                raise GovernanceRejected("stable independently verified recovery required")
            payload = {
                "packet_id": packet_id,
                "source_version": old.version,
                "resulting_version": old.version + 1,
                "verifier": verifier,
                "receipt_digest": receipt_digest,
                "relay_id": relay_id,
            }
            receipt = RecoveryReceipt(**payload, record_digest=canonical_digest(payload))
            item = self._transition(
                old,
                "RECOVERY_VERIFIED",
                status="RECOVERY_VERIFIED",
                archive_reason=old.archive_reason,
                attachment_digest=receipt.record_digest,
            )
            self._receipts[packet_id] = receipt
            return item

    def recover(self, packet_id: str, expected_version: int) -> DeliveryRecord:
        with self._lock:
            old = self._require(packet_id, expected_version)
            receipt = self._receipts.get(packet_id)
            if (
                old.status != "RECOVERY_VERIFIED"
                or receipt is None
                or receipt.resulting_version != old.version
                or receipt.packet_id != packet_id
                or not self._receipt_valid(receipt)
                or not self._relay.get(receipt.relay_id, (0, 0, False))[2]
            ):
                raise GovernanceRejected(
                    "verified recovery receipt and currently stable relay required"
                )
            if old.intent_digest in self._fulfilled_intents:
                raise GovernanceRejected("fulfilled intent cannot recover")
            active = self._intent_active.get(old.intent_digest)
            if active not in {None, packet_id}:
                raise GovernanceRejected("active intent conflict")
            item = self._transition(old, "RECOVERED", status="QUEUED")
            self._intent_active[item.intent_digest] = packet_id
            return item

    def get(self, packet_id: str) -> DeliveryRecord | None:
        with self._lock:
            return self._rows.get(packet_id)

    def _history_valid(self) -> bool:
        tips: dict[str, DeliveryRecord] = {}
        for item in self._history:
            previous = tips.get(item.packet_id)
            expected_previous = previous.digest if previous else None
            if item.previous_digest != expected_previous:
                return False
            expected_digest = self._record_digest(
                item.packet_id,
                item.intent_digest,
                item.priority,
                item.status,
                item.version,
                item.created_at,
                item.archive_reason,
                item.previous_digest,
            )
            if item.digest != expected_digest:
                return False
            tips[item.packet_id] = item
        return all(tips.get(packet_id) == item for packet_id, item in self._rows.items())

    def _event_valid(self) -> bool:
        history = {item.digest: item for item in self._history}
        receipts = {
            receipt.record_digest: receipt
            for key, receipt in self._receipts.items()
            if key == receipt.packet_id and self._receipt_valid(receipt)
        }
        previous = None
        for sequence, event in enumerate(self._events, 1):
            payload = {
                "action": event["action"],
                "packet_digest": event["packet_digest"],
                "attachment_digest": event["attachment_digest"],
                "previous_digest": previous,
                "sequence": sequence,
            }
            item = history.get(event["packet_digest"])
            attachment = event["attachment_digest"]
            if item is None or event["previous_digest"] != previous:
                return False
            if event["action"] == "RECOVERY_VERIFIED":
                receipt = receipts.get(attachment)
                if receipt is None or receipt.packet_id != item.packet_id:
                    return False
            elif attachment is not None:
                return False
            if event["digest"] != canonical_digest(payload):
                return False
            previous = event["digest"]
        return True

    def evidence(self) -> dict[str, object]:
        with self._lock:
            statuses = {
                status: sum(row.status == status for row in self._rows.values())
                for status in sorted({row.status for row in self._rows.values()})
            }
            receipt_integrity = all(
                key == receipt.packet_id and self._receipt_valid(receipt)
                for key, receipt in self._receipts.items()
            )
            batches_valid = all(
                1 <= batch.requested_limit <= MAX_BATCH_SIZE
                and len(batch.packet_ids) <= batch.requested_limit
                and batch.record_digest
                == canonical_digest(
                    {
                        "batch_id": batch.batch_id,
                        "requested_limit": batch.requested_limit,
                        "packet_ids": list(batch.packet_ids),
                    }
                )
                for batch in self._batches.values()
            )
            out = {
                "schema": "nurion.pg.synthetic-priority-delivery-recovery.v1",
                "features": list(range(901, 1101)),
                "feature_count": 200,
                "workstreams": [
                    {"start": start, "end": end, "name": name, "control_count": 25}
                    for start, end, name in WORKSTREAMS
                ],
                "packet_count": len(self._rows),
                "status_counts": statuses,
                "batch_count": len(self._batches),
                "max_batch_size": MAX_BATCH_SIZE,
                "gap_report_count": len(self._gap_reports),
                "max_gap_report": MAX_GAP_REPORT,
                "relay_count": len(self._relay),
                "recovery_receipt_count": len(self._receipts),
                "event_count": len(self._events),
                "history_count": len(self._history),
                "history_chain_valid": self._history_valid(),
                "event_chain_valid": self._event_valid(),
                "receipt_integrity_valid": receipt_integrity,
                "batch_integrity_valid": batches_valid,
                "maximum_state": "SYNTHETIC_RECOVERY_VERIFIED",
                "synthetic_only": True,
                "in_memory_only": True,
                "automatic_approval_allowed": False,
                "external_delivery_used": False,
                "external_pg_api_used": False,
                "production_outcome_recorded": False,
                "pattern_promotion_allowed": False,
                "production_credentials_accessed": False,
                "payment_or_ledger_effect_allowed": False,
                "merge_allowed": False,
                "deployment_allowed": False,
            }
        return {**out, "report_digest": canonical_digest(out)}
