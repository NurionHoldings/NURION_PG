"""Transactional SQLite inbox for synthetic webhook evidence only."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Iterator

from .arkaon.governance import GovernanceRejected, canonical_digest
from .webhook_intake import (
    SyntheticKeyRegistry,
    SyntheticWebhookIntake,
    WebhookDecision,
    WebhookEnvelope,
    WebhookEventType,
)


SCHEMA_VERSION = 1
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS synthetic_inbox_metadata (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    schema_version INTEGER NOT NULL CHECK (schema_version = 1),
    synthetic_only INTEGER NOT NULL CHECK (synthetic_only = 1)
);
CREATE TABLE IF NOT EXISTS synthetic_webhook_events (
    event_id TEXT PRIMARY KEY,
    provider_id TEXT NOT NULL,
    key_id TEXT NOT NULL,
    nonce TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    aggregate_sequence INTEGER NOT NULL CHECK (aggregate_sequence > 0),
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    signature TEXT NOT NULL,
    envelope_digest TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('ACCEPTED', 'QUARANTINED', 'BLOCKED')),
    reason TEXT NOT NULL,
    received_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    automatic_application_allowed INTEGER NOT NULL DEFAULT 0
        CHECK (automatic_application_allowed = 0),
    UNIQUE (provider_id, nonce),
    UNIQUE (aggregate_id, aggregate_sequence)
);
CREATE TABLE IF NOT EXISTS synthetic_webhook_cursors (
    aggregate_id TEXT PRIMARY KEY,
    last_sequence INTEGER NOT NULL CHECK (last_sequence > 0),
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS synthetic_webhook_receipts (
    receipt_sequence INTEGER PRIMARY KEY,
    event_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL,
    envelope_digest TEXT NOT NULL,
    previous_digest TEXT NOT NULL,
    receipt_digest TEXT NOT NULL UNIQUE,
    recorded_at TEXT NOT NULL,
    automatic_application_allowed INTEGER NOT NULL DEFAULT 0
        CHECK (automatic_application_allowed = 0)
);
""".strip()


@dataclass(frozen=True)
class DurableInboxReceipt:
    receipt_sequence: int
    event_id: str
    decision: WebhookDecision
    reason: str
    envelope_digest: str
    previous_digest: str
    receipt_digest: str
    automatic_application_allowed: bool = False


@dataclass(frozen=True)
class AcceptedDurableWebhook:
    envelope: WebhookEnvelope
    acceptance_receipt_digest: str
    automatic_application_allowed: bool = False


class SyntheticSQLiteWebhookInbox:
    """Durable synthetic inbox; acceptance never applies a payment result."""

    def __init__(
        self,
        database: str | Path,
        key_registry: SyntheticKeyRegistry,
        *,
        max_age_seconds: int = 600,
        future_skew_seconds: int = 60,
        max_payload_bytes: int = 8192,
    ) -> None:
        database_value = str(database)
        self._validate_database_target(database_value)
        self._connection = sqlite3.connect(
            database_value,
            isolation_level=None,
            timeout=5,
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA busy_timeout = 5000")
        self._verifier = SyntheticWebhookIntake(
            key_registry,
            max_age_seconds=max_age_seconds,
            future_skew_seconds=future_skew_seconds,
            max_payload_bytes=max_payload_bytes,
        )
        self._lock = RLock()
        self._initialize_schema()

    @staticmethod
    def _validate_database_target(database: str) -> None:
        if database == ":memory:":
            return
        if database.startswith("file:") or "://" in database:
            raise GovernanceRejected("URI and server database targets are forbidden")
        name = Path(database).name
        if not name.startswith("synthetic-") or Path(name).suffix not in {
            ".db",
            ".sqlite",
            ".sqlite3",
        }:
            raise GovernanceRejected("synthetic SQLite database target required")

    def _initialize_schema(self) -> None:
        with self._lock:
            self._connection.executescript(SCHEMA_SQL)
            self._connection.execute(
                """
                INSERT OR IGNORE INTO synthetic_inbox_metadata
                    (singleton, schema_version, synthetic_only)
                VALUES (1, ?, 1)
                """,
                (SCHEMA_VERSION,),
            )
            row = self._connection.execute(
                "SELECT schema_version, synthetic_only FROM synthetic_inbox_metadata WHERE singleton = 1"
            ).fetchone()
            if row is None or row["schema_version"] != SCHEMA_VERSION or row["synthetic_only"] != 1:
                raise GovernanceRejected("unsupported or non-synthetic inbox schema")

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            yield
        except Exception:
            self._connection.execute("ROLLBACK")
            raise
        else:
            self._connection.execute("COMMIT")

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def submit(
        self, envelope: WebhookEnvelope, *, received_at: datetime
    ) -> DurableInboxReceipt:
        if received_at.tzinfo is None:
            raise GovernanceRejected("timezone-aware receipt time required")
        try:
            self._verifier.verify_only(envelope, received_at=received_at)
        except GovernanceRejected as exc:
            return self._record_blocked(envelope, str(exc), recorded_at=received_at)

        with self._lock:
            try:
                with self._transaction():
                    existing = self._connection.execute(
                        "SELECT envelope_digest, decision FROM synthetic_webhook_events WHERE event_id = ?",
                        (envelope.event_id,),
                    ).fetchone()
                    if existing is not None:
                        if existing["envelope_digest"] != envelope.envelope_digest:
                            return self._append_receipt(
                                envelope,
                                WebhookDecision.BLOCKED,
                                "event_id_collision",
                                recorded_at=received_at,
                            )
                        decision = WebhookDecision(existing["decision"])
                        if decision is WebhookDecision.ACCEPTED:
                            return self._append_receipt(
                                envelope,
                                WebhookDecision.DUPLICATE,
                                "exact_duplicate_after_restart_safe_lookup",
                                recorded_at=received_at,
                            )
                        return self._append_receipt(
                            envelope,
                            decision,
                            "already_quarantined" if decision is WebhookDecision.QUARANTINED else "already_blocked",
                            recorded_at=received_at,
                        )

                    nonce = self._connection.execute(
                        "SELECT event_id FROM synthetic_webhook_events WHERE provider_id = ? AND nonce = ?",
                        (envelope.provider_id, envelope.nonce),
                    ).fetchone()
                    if nonce is not None:
                        return self._append_receipt(
                            envelope,
                            WebhookDecision.BLOCKED,
                            "nonce_replay",
                            recorded_at=received_at,
                        )

                    occupied = self._connection.execute(
                        """
                        SELECT event_id FROM synthetic_webhook_events
                        WHERE aggregate_id = ? AND aggregate_sequence = ?
                        """,
                        (envelope.aggregate_id, envelope.sequence),
                    ).fetchone()
                    if occupied is not None:
                        return self._append_receipt(
                            envelope,
                            WebhookDecision.BLOCKED,
                            "aggregate_sequence_collision",
                            recorded_at=received_at,
                        )

                    cursor = self._connection.execute(
                        "SELECT last_sequence FROM synthetic_webhook_cursors WHERE aggregate_id = ?",
                        (envelope.aggregate_id,),
                    ).fetchone()
                    expected = (cursor["last_sequence"] if cursor is not None else 0) + 1
                    if envelope.sequence < expected:
                        return self._append_receipt(
                            envelope,
                            WebhookDecision.BLOCKED,
                            "sequence_replay",
                            recorded_at=received_at,
                        )
                    decision = (
                        WebhookDecision.QUARANTINED
                        if envelope.sequence > expected
                        else WebhookDecision.ACCEPTED
                    )
                    reason = "sequence_gap" if decision is WebhookDecision.QUARANTINED else "verified_envelope_only"
                    self._insert_event(
                        envelope,
                        decision,
                        reason,
                        received_at=received_at,
                    )
                    if decision is WebhookDecision.ACCEPTED:
                        self._advance_cursor(envelope, updated_at=received_at)
                    return self._append_receipt(
                        envelope, decision, reason, recorded_at=received_at
                    )
            except sqlite3.Error as exc:
                raise GovernanceRejected("synthetic inbox transaction failed") from exc

    def retry_quarantined(
        self, event_id: str, *, now: datetime
    ) -> DurableInboxReceipt:
        if now.tzinfo is None:
            raise GovernanceRejected("timezone-aware retry time required")
        with self._lock:
            try:
                with self._transaction():
                    row = self._connection.execute(
                        "SELECT * FROM synthetic_webhook_events WHERE event_id = ?",
                        (event_id,),
                    ).fetchone()
                    if row is None or row["decision"] != WebhookDecision.QUARANTINED.value:
                        raise GovernanceRejected("durable quarantined event required")
                    try:
                        envelope = self._envelope_from_row(row)
                    except (GovernanceRejected, KeyError, TypeError, ValueError):
                        self._update_event_decision(
                            event_id,
                            WebhookDecision.BLOCKED,
                            "stored_envelope_corruption",
                            updated_at=now,
                        )
                        return self._append_receipt_material(
                            event_id=event_id,
                            envelope_digest=row["envelope_digest"],
                            decision=WebhookDecision.BLOCKED,
                            reason="stored_envelope_corruption",
                            recorded_at=now,
                        )
                    if envelope.envelope_digest != row["envelope_digest"]:
                        self._update_event_decision(
                            event_id,
                            WebhookDecision.BLOCKED,
                            "stored_envelope_digest_mismatch",
                            updated_at=now,
                        )
                        return self._append_receipt_material(
                            event_id=event_id,
                            envelope_digest=row["envelope_digest"],
                            decision=WebhookDecision.BLOCKED,
                            reason="stored_envelope_digest_mismatch",
                            recorded_at=now,
                        )
                    try:
                        self._verifier.verify_quarantined_only(envelope, now=now)
                    except GovernanceRejected as exc:
                        self._update_event_decision(
                            event_id,
                            WebhookDecision.BLOCKED,
                            str(exc),
                            updated_at=now,
                        )
                        return self._append_receipt(
                            envelope,
                            WebhookDecision.BLOCKED,
                            str(exc),
                            recorded_at=now,
                        )
                    cursor = self._connection.execute(
                        "SELECT last_sequence FROM synthetic_webhook_cursors WHERE aggregate_id = ?",
                        (envelope.aggregate_id,),
                    ).fetchone()
                    expected = (cursor["last_sequence"] if cursor is not None else 0) + 1
                    if envelope.sequence > expected:
                        return self._append_receipt(
                            envelope,
                            WebhookDecision.QUARANTINED,
                            "sequence_gap",
                            recorded_at=now,
                        )
                    if envelope.sequence < expected:
                        self._update_event_decision(
                            event_id,
                            WebhookDecision.BLOCKED,
                            "sequence_replay",
                            updated_at=now,
                        )
                        return self._append_receipt(
                            envelope,
                            WebhookDecision.BLOCKED,
                            "sequence_replay",
                            recorded_at=now,
                        )
                    self._update_event_decision(
                        event_id,
                        WebhookDecision.ACCEPTED,
                        "quarantine_released",
                        updated_at=now,
                    )
                    self._advance_cursor(envelope, updated_at=now)
                    return self._append_receipt(
                        envelope,
                        WebhookDecision.ACCEPTED,
                        "quarantine_released",
                        recorded_at=now,
                    )
            except sqlite3.Error as exc:
                raise GovernanceRejected("synthetic inbox transaction failed") from exc

    def _record_blocked(
        self, envelope: WebhookEnvelope, reason: str, *, recorded_at: datetime
    ) -> DurableInboxReceipt:
        with self._lock:
            try:
                with self._transaction():
                    return self._append_receipt(
                        envelope,
                        WebhookDecision.BLOCKED,
                        reason,
                        recorded_at=recorded_at,
                    )
            except sqlite3.Error as exc:
                raise GovernanceRejected("synthetic inbox transaction failed") from exc

    def _insert_event(
        self,
        envelope: WebhookEnvelope,
        decision: WebhookDecision,
        reason: str,
        *,
        received_at: datetime,
    ) -> None:
        self._connection.execute(
            """
            INSERT INTO synthetic_webhook_events (
                event_id, provider_id, key_id, nonce, aggregate_id,
                aggregate_sequence, event_type, occurred_at, payload_json,
                signature, envelope_digest, decision, reason, received_at,
                updated_at, automatic_application_allowed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                envelope.event_id,
                envelope.provider_id,
                envelope.key_id,
                envelope.nonce,
                envelope.aggregate_id,
                envelope.sequence,
                envelope.event_type.value,
                envelope.occurred_at.isoformat(),
                json.dumps(
                    dict(envelope.payload),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                envelope.signature,
                envelope.envelope_digest,
                decision.value,
                reason,
                received_at.isoformat(),
                received_at.isoformat(),
            ),
        )

    def _advance_cursor(self, envelope: WebhookEnvelope, *, updated_at: datetime) -> None:
        self._connection.execute(
            """
            INSERT INTO synthetic_webhook_cursors (aggregate_id, last_sequence, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(aggregate_id) DO UPDATE SET
                last_sequence = excluded.last_sequence,
                updated_at = excluded.updated_at
            """,
            (envelope.aggregate_id, envelope.sequence, updated_at.isoformat()),
        )

    def _update_event_decision(
        self,
        event_id: str,
        decision: WebhookDecision,
        reason: str,
        *,
        updated_at: datetime,
    ) -> None:
        self._connection.execute(
            """
            UPDATE synthetic_webhook_events
            SET decision = ?, reason = ?, updated_at = ?
            WHERE event_id = ?
            """,
            (decision.value, reason, updated_at.isoformat(), event_id),
        )

    @staticmethod
    def _envelope_from_row(row: sqlite3.Row) -> WebhookEnvelope:
        return WebhookEnvelope(
            provider_id=row["provider_id"],
            key_id=row["key_id"],
            event_id=row["event_id"],
            nonce=row["nonce"],
            aggregate_id=row["aggregate_id"],
            sequence=row["aggregate_sequence"],
            event_type=WebhookEventType(row["event_type"]),
            occurred_at=datetime.fromisoformat(row["occurred_at"]),
            payload=json.loads(row["payload_json"]),
            signature=row["signature"],
        )

    def _append_receipt(
        self,
        envelope: WebhookEnvelope,
        decision: WebhookDecision,
        reason: str,
        *,
        recorded_at: datetime,
    ) -> DurableInboxReceipt:
        return self._append_receipt_material(
            event_id=envelope.event_id,
            envelope_digest=envelope.envelope_digest,
            decision=decision,
            reason=reason,
            recorded_at=recorded_at,
        )

    def _append_receipt_material(
        self,
        *,
        event_id: str,
        envelope_digest: str,
        decision: WebhookDecision,
        reason: str,
        recorded_at: datetime,
    ) -> DurableInboxReceipt:
        latest = self._connection.execute(
            """
            SELECT receipt_sequence, receipt_digest
            FROM synthetic_webhook_receipts
            ORDER BY receipt_sequence DESC LIMIT 1
            """
        ).fetchone()
        sequence = (latest["receipt_sequence"] if latest is not None else 0) + 1
        previous = latest["receipt_digest"] if latest is not None else "0" * 64
        value = {
            "receipt_sequence": sequence,
            "event_id": event_id,
            "decision": decision.value,
            "reason": reason,
            "envelope_digest": envelope_digest,
            "previous_digest": previous,
            "recorded_at": recorded_at.isoformat(),
            "automatic_application_allowed": False,
        }
        receipt = DurableInboxReceipt(
            sequence,
            event_id,
            decision,
            reason,
            envelope_digest,
            previous,
            canonical_digest(value),
        )
        self._connection.execute(
            """
            INSERT INTO synthetic_webhook_receipts (
                receipt_sequence, event_id, decision, reason, envelope_digest,
                previous_digest, receipt_digest, recorded_at,
                automatic_application_allowed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                receipt.receipt_sequence,
                receipt.event_id,
                receipt.decision.value,
                receipt.reason,
                receipt.envelope_digest,
                receipt.previous_digest,
                receipt.receipt_digest,
                recorded_at.isoformat(),
            ),
        )
        return receipt

    def current_decision(self, event_id: str) -> WebhookDecision:
        with self._lock:
            row = self._connection.execute(
                "SELECT decision FROM synthetic_webhook_events WHERE event_id = ?",
                (event_id,),
            ).fetchone()
            if row is None:
                raise GovernanceRejected("unknown durable inbox event")
            return WebhookDecision(row["decision"])

    def accepted_event(self, event_id: str) -> AcceptedDurableWebhook:
        """Return an integrity-bound accepted event without applying it."""
        with self._lock:
            if not self.verify_receipt_chain():
                raise GovernanceRejected("durable inbox receipt chain is invalid")
            row = self._connection.execute(
                "SELECT * FROM synthetic_webhook_events WHERE event_id = ?",
                (event_id,),
            ).fetchone()
            if row is None or row["decision"] != WebhookDecision.ACCEPTED.value:
                raise GovernanceRejected("accepted durable inbox event required")
            try:
                envelope = self._envelope_from_row(row)
            except (GovernanceRejected, KeyError, TypeError, ValueError) as exc:
                raise GovernanceRejected("stored accepted envelope is corrupt") from exc
            if envelope.envelope_digest != row["envelope_digest"]:
                raise GovernanceRejected("stored accepted envelope digest mismatch")
            receipt = self._connection.execute(
                """
                SELECT receipt_digest, envelope_digest, automatic_application_allowed
                FROM synthetic_webhook_receipts
                WHERE event_id = ? AND decision = ?
                ORDER BY receipt_sequence DESC LIMIT 1
                """,
                (event_id, WebhookDecision.ACCEPTED.value),
            ).fetchone()
            if (
                receipt is None
                or receipt["envelope_digest"] != envelope.envelope_digest
                or receipt["automatic_application_allowed"] != 0
            ):
                raise GovernanceRejected("accepted event receipt binding is invalid")
            return AcceptedDurableWebhook(envelope, receipt["receipt_digest"])

    def verify_receipt_chain(self) -> bool:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM synthetic_webhook_receipts ORDER BY receipt_sequence"
            ).fetchall()
            previous = "0" * 64
            for sequence, row in enumerate(rows, start=1):
                expected = canonical_digest(
                    {
                        "receipt_sequence": sequence,
                        "event_id": row["event_id"],
                        "decision": row["decision"],
                        "reason": row["reason"],
                        "envelope_digest": row["envelope_digest"],
                        "previous_digest": previous,
                        "recorded_at": row["recorded_at"],
                        "automatic_application_allowed": False,
                    }
                )
                if (
                    row["receipt_sequence"] != sequence
                    or row["previous_digest"] != previous
                    or row["receipt_digest"] != expected
                    or row["automatic_application_allowed"] != 0
                ):
                    return False
                previous = row["receipt_digest"]
            return True

    def evidence(self) -> dict[str, object]:
        with self._lock:
            event_counts = {
                decision.value: 0
                for decision in (
                    WebhookDecision.ACCEPTED,
                    WebhookDecision.QUARANTINED,
                    WebhookDecision.BLOCKED,
                )
            }
            for row in self._connection.execute(
                "SELECT decision, COUNT(*) AS count FROM synthetic_webhook_events GROUP BY decision"
            ):
                event_counts[row["decision"]] = row["count"]
            receipt_count = self._connection.execute(
                "SELECT COUNT(*) AS count FROM synthetic_webhook_receipts"
            ).fetchone()["count"]
            value = {
                "schema": "nurion.pg.synthetic-durable-webhook-inbox-evidence.v1",
                "database_engine": "SQLite",
                "schema_version": SCHEMA_VERSION,
                "schema_digest": canonical_digest(SCHEMA_SQL),
                "transaction_begin_mode": "IMMEDIATE",
                "event_counts": event_counts,
                "receipt_count": receipt_count,
                "receipt_chain_valid": self.verify_receipt_chain(),
                "restart_replay_control_present": True,
                "unique_event_nonce_sequence_constraints_present": True,
                "synthetic_only": True,
                "payment_state_automatically_changed": False,
                "money_movement_executed": False,
                "production_activation_allowed": False,
            }
            return {**value, "report_digest": canonical_digest(value)}
