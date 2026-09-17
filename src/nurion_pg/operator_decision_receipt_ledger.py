"""Durable synthetic receipts for validated operator decision intent assessments."""

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
from .operator_decision_intake import (
    SYNTHETIC_OPERATOR_ID,
    OperatorDecisionIntentAssessment,
    SyntheticOperatorDecision,
    SyntheticOperatorDecisionIntake,
)


DECISION_RECEIPT_SCHEMA_VERSION = 1
RECEIPT_STATE = "SYNTHETIC_RECEIPT_RECORDED"
DECISION_RECEIPT_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS synthetic_decision_receipt_metadata (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    schema_version INTEGER NOT NULL CHECK (schema_version = 1),
    synthetic_only INTEGER NOT NULL CHECK (synthetic_only = 1)
);
CREATE TABLE IF NOT EXISTS synthetic_decision_receipts (
    receipt_id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL UNIQUE,
    assessment_digest TEXT NOT NULL UNIQUE,
    envelope_id TEXT NOT NULL UNIQUE,
    envelope_digest TEXT NOT NULL UNIQUE,
    packet_id TEXT NOT NULL UNIQUE,
    packet_digest TEXT NOT NULL,
    operator_id TEXT NOT NULL
        CHECK (operator_id = 'synthetic:operator:CHOI_IN_SEOK'),
    decision TEXT NOT NULL CHECK (decision IN (
        'AUTHORIZE_SYNTHETIC_IMPLEMENTATION_PROPOSAL_DRAFT',
        'HOLD',
        'REJECT'
    )),
    assessment_json TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state = 'SYNTHETIC_RECEIPT_RECORDED'),
    recorded_at TEXT NOT NULL,
    actual_operator_decision_recorded INTEGER NOT NULL DEFAULT 0
        CHECK (actual_operator_decision_recorded = 0),
    packet_state_changed INTEGER NOT NULL DEFAULT 0 CHECK (packet_state_changed = 0),
    code_change_allowed INTEGER NOT NULL DEFAULT 0 CHECK (code_change_allowed = 0),
    automatic_application_allowed INTEGER NOT NULL DEFAULT 0
        CHECK (automatic_application_allowed = 0),
    execution_allowed INTEGER NOT NULL DEFAULT 0 CHECK (execution_allowed = 0)
);
CREATE TABLE IF NOT EXISTS synthetic_decision_receipt_audit (
    audit_sequence INTEGER PRIMARY KEY,
    receipt_id TEXT NOT NULL UNIQUE,
    action TEXT NOT NULL CHECK (action = 'SYNTHETIC_DECISION_INTENT_RECEIPTED'),
    actor_id TEXT NOT NULL CHECK (actor_id = 'synthetic:system:decision-receipt-ledger'),
    evidence_digest TEXT NOT NULL,
    previous_digest TEXT NOT NULL,
    audit_digest TEXT NOT NULL UNIQUE,
    recorded_at TEXT NOT NULL
);
""".strip()


@dataclass(frozen=True)
class SyntheticDecisionReceipt:
    receipt_id: str
    assessment_id: str
    assessment_digest: str
    envelope_id: str
    envelope_digest: str
    packet_id: str
    packet_digest: str
    operator_id: str
    decision: SyntheticOperatorDecision
    state: str
    recorded_at: datetime
    actual_operator_decision_recorded: bool = False
    packet_state_changed: bool = False
    code_change_allowed: bool = False
    automatic_application_allowed: bool = False
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if (
            not self.receipt_id.startswith("synthetic:operator-decision-receipt:")
            or not self.assessment_id.startswith(
                "synthetic:operator-decision-assessment:"
            )
            or not _valid_digest(self.assessment_digest)
            or not self.envelope_id.startswith("synthetic:operator-decision-envelope:")
            or not _valid_digest(self.envelope_digest)
            or not self.packet_id.startswith("synthetic:operator-decision-packet:")
            or not _valid_digest(self.packet_digest)
            or self.operator_id != SYNTHETIC_OPERATOR_ID
            or not isinstance(self.decision, SyntheticOperatorDecision)
            or self.state != RECEIPT_STATE
            or self.recorded_at.tzinfo is None
            or self.actual_operator_decision_recorded
            or self.packet_state_changed
            or self.code_change_allowed
            or self.automatic_application_allowed
            or self.execution_allowed
        ):
            raise GovernanceRejected("valid non-authorizing synthetic receipt required")


def _valid_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


class SyntheticOperatorDecisionReceiptLedger:
    """Persists synthetic validation evidence, never an actual operator decision."""

    def __init__(self, database: str | Path) -> None:
        database_value = str(database)
        self._validate_database_target(database_value)
        self._connection = sqlite3.connect(
            database_value,
            isolation_level=None,
            timeout=5,
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA busy_timeout = 5000")
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
            raise GovernanceRejected("synthetic SQLite decision receipt target required")

    def _initialize_schema(self) -> None:
        with self._lock:
            self._connection.executescript(DECISION_RECEIPT_SCHEMA_SQL)
            self._connection.execute(
                """
                INSERT OR IGNORE INTO synthetic_decision_receipt_metadata
                    (singleton, schema_version, synthetic_only) VALUES (1, ?, 1)
                """,
                (DECISION_RECEIPT_SCHEMA_VERSION,),
            )
            row = self._connection.execute(
                """
                SELECT schema_version, synthetic_only
                FROM synthetic_decision_receipt_metadata WHERE singleton = 1
                """
            ).fetchone()
            if (
                row is None
                or row["schema_version"] != DECISION_RECEIPT_SCHEMA_VERSION
                or row["synthetic_only"] != 1
            ):
                raise GovernanceRejected("unsupported decision receipt schema")

    def verify_metadata(self) -> bool:
        with self._lock:
            rows = self._connection.execute(
                "SELECT singleton, schema_version, synthetic_only "
                "FROM synthetic_decision_receipt_metadata"
            ).fetchall()
            return (
                len(rows) == 1
                and rows[0]["singleton"] == 1
                and rows[0]["schema_version"] == DECISION_RECEIPT_SCHEMA_VERSION
                and rows[0]["synthetic_only"] == 1
            )

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

    def record_from_intake(
        self,
        intake: SyntheticOperatorDecisionIntake,
        envelope_id: str,
        *,
        recorded_at: datetime,
    ) -> SyntheticDecisionReceipt:
        if recorded_at.tzinfo is None:
            raise GovernanceRejected("timezone-aware synthetic receipt time required")
        if not intake.verify_assessment_chain():
            raise GovernanceRejected("operator intent assessment chain is invalid")
        matches = [
            assessment
            for assessment in intake.assessments
            if assessment.envelope_id == envelope_id
        ]
        if len(matches) != 1:
            raise GovernanceRejected("one validated operator intent assessment required")
        assessment = matches[0]
        self._validate_assessment(assessment)
        if recorded_at < assessment.assessed_at:
            raise GovernanceRejected("synthetic receipt cannot predate assessment")
        receipt_id = (
            "synthetic:operator-decision-receipt:"
            + assessment.assessment_digest[:32]
        )
        payload = {**assessment.digest_value(), "assessment_digest": assessment.assessment_digest}
        before = intake.evidence()["report_digest"]
        with self._lock:
            try:
                with self._transaction():
                    if not self.verify_metadata():
                        raise GovernanceRejected(
                            "synthetic decision receipt metadata is invalid"
                        )
                    existing = self._connection.execute(
                        "SELECT * FROM synthetic_decision_receipts WHERE receipt_id = ?",
                        (receipt_id,),
                    ).fetchone()
                    if existing is not None:
                        if (
                            existing["assessment_digest"]
                            != assessment.assessment_digest
                            or existing["envelope_id"] != envelope_id
                        ):
                            raise GovernanceRejected("synthetic receipt identity collision")
                        if (
                            not self.verify_audit_chain()
                            or not self.verify_record_bindings()
                        ):
                            raise GovernanceRejected("existing synthetic receipt is invalid")
                        if before != intake.evidence()["report_digest"]:
                            raise GovernanceRejected(
                                "operator intent assessment changed during receipting"
                            )
                        return self._record_from_row(existing)
                    self._connection.execute(
                        """
                        INSERT INTO synthetic_decision_receipts (
                            receipt_id, assessment_id, assessment_digest,
                            envelope_id, envelope_digest, packet_id, packet_digest,
                            operator_id, decision, assessment_json, state, recorded_at,
                            actual_operator_decision_recorded, packet_state_changed,
                            code_change_allowed, automatic_application_allowed,
                            execution_allowed
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0)
                        """,
                        (
                            receipt_id,
                            assessment.assessment_id,
                            assessment.assessment_digest,
                            assessment.envelope_id,
                            assessment.envelope_digest,
                            assessment.packet_id,
                            assessment.packet_digest,
                            assessment.operator_id,
                            assessment.decision.value,
                            json.dumps(
                                payload,
                                ensure_ascii=False,
                                sort_keys=True,
                                separators=(",", ":"),
                            ),
                            RECEIPT_STATE,
                            recorded_at.isoformat(),
                        ),
                    )
                    self._append_audit(
                        receipt_id,
                        assessment.assessment_digest,
                        recorded_at,
                    )
                    if before != intake.evidence()["report_digest"]:
                        raise GovernanceRejected(
                            "operator intent assessment changed during receipting"
                        )
                    return self._get_record(receipt_id)
            except sqlite3.Error as exc:
                raise GovernanceRejected("synthetic decision receipt transaction failed") from exc

    @staticmethod
    def _validate_assessment(assessment: OperatorDecisionIntentAssessment) -> None:
        if (
            assessment.validation_state != "SYNTHETIC_DECISION_VALIDATED"
            or assessment.assessment_digest != canonical_digest(assessment.digest_value())
            or assessment.packet_state_changed
            or assessment.operator_decision_recorded
            or assessment.code_change_allowed
            or assessment.automatic_application_allowed
            or assessment.execution_allowed
        ):
            raise GovernanceRejected("intact synthetic-only decision assessment required")

    def _append_audit(
        self, receipt_id: str, evidence_digest: str, recorded_at: datetime
    ) -> None:
        latest = self._connection.execute(
            """
            SELECT audit_sequence, audit_digest FROM synthetic_decision_receipt_audit
            ORDER BY audit_sequence DESC LIMIT 1
            """
        ).fetchone()
        sequence = (latest["audit_sequence"] if latest is not None else 0) + 1
        previous = latest["audit_digest"] if latest is not None else "0" * 64
        value = {
            "audit_sequence": sequence,
            "receipt_id": receipt_id,
            "action": "SYNTHETIC_DECISION_INTENT_RECEIPTED",
            "actor_id": "synthetic:system:decision-receipt-ledger",
            "evidence_digest": evidence_digest,
            "previous_digest": previous,
            "recorded_at": recorded_at.isoformat(),
        }
        self._connection.execute(
            """
            INSERT INTO synthetic_decision_receipt_audit (
                audit_sequence, receipt_id, action, actor_id, evidence_digest,
                previous_digest, audit_digest, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sequence,
                receipt_id,
                value["action"],
                value["actor_id"],
                evidence_digest,
                previous,
                canonical_digest(value),
                recorded_at.isoformat(),
            ),
        )

    @staticmethod
    def _validate_stored_assessment(payload: object) -> None:
        if not isinstance(payload, dict):
            raise GovernanceRejected("stored synthetic assessment object required")
        assessment = OperatorDecisionIntentAssessment(
            int(payload["sequence"]),
            str(payload["assessment_id"]),
            str(payload["envelope_id"]),
            str(payload["envelope_digest"]),
            str(payload["packet_id"]),
            str(payload["packet_digest"]),
            str(payload["operator_id"]),
            SyntheticOperatorDecision(str(payload["decision"])),
            datetime.fromisoformat(str(payload["assessed_at"])),
            str(payload["previous_digest"]),
            str(payload["assessment_digest"]),
            str(payload["validation_state"]),
            bool(payload["packet_state_changed"]),
            bool(payload["operator_decision_recorded"]),
            bool(payload["code_change_allowed"]),
            bool(payload["automatic_application_allowed"]),
            bool(payload["execution_allowed"]),
        )
        if assessment.assessment_digest != payload["assessment_digest"]:
            raise GovernanceRejected("stored synthetic assessment digest mismatch")

    @classmethod
    def _record_from_row(cls, row: sqlite3.Row) -> SyntheticDecisionReceipt:
        try:
            payload = json.loads(row["assessment_json"])
            cls._validate_stored_assessment(payload)
        except (GovernanceRejected, KeyError, TypeError, ValueError) as exc:
            raise GovernanceRejected("stored synthetic decision receipt is invalid") from exc
        expected_id = (
            "synthetic:operator-decision-receipt:"
            + row["assessment_digest"][:32]
        )
        if (
            row["receipt_id"] != expected_id
            or payload["assessment_id"] != row["assessment_id"]
            or payload["assessment_digest"] != row["assessment_digest"]
            or payload["envelope_id"] != row["envelope_id"]
            or payload["envelope_digest"] != row["envelope_digest"]
            or payload["packet_id"] != row["packet_id"]
            or payload["packet_digest"] != row["packet_digest"]
            or payload["operator_id"] != row["operator_id"]
            or payload["decision"] != row["decision"]
        ):
            raise GovernanceRejected("stored synthetic receipt binding is invalid")
        return SyntheticDecisionReceipt(
            row["receipt_id"],
            row["assessment_id"],
            row["assessment_digest"],
            row["envelope_id"],
            row["envelope_digest"],
            row["packet_id"],
            row["packet_digest"],
            row["operator_id"],
            SyntheticOperatorDecision(row["decision"]),
            row["state"],
            datetime.fromisoformat(row["recorded_at"]),
            bool(row["actual_operator_decision_recorded"]),
            bool(row["packet_state_changed"]),
            bool(row["code_change_allowed"]),
            bool(row["automatic_application_allowed"]),
            bool(row["execution_allowed"]),
        )

    def _get_record(self, receipt_id: str) -> SyntheticDecisionReceipt:
        row = self._connection.execute(
            "SELECT * FROM synthetic_decision_receipts WHERE receipt_id = ?",
            (receipt_id,),
        ).fetchone()
        if row is None:
            raise GovernanceRejected("unknown synthetic decision receipt")
        return self._record_from_row(row)

    def get(self, receipt_id: str) -> SyntheticDecisionReceipt:
        with self._lock:
            return self._get_record(receipt_id)

    def verify_audit_chain(self) -> bool:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM synthetic_decision_receipt_audit ORDER BY audit_sequence"
            ).fetchall()
            previous = "0" * 64
            for sequence, row in enumerate(rows, start=1):
                value = {
                    "audit_sequence": sequence,
                    "receipt_id": row["receipt_id"],
                    "action": row["action"],
                    "actor_id": row["actor_id"],
                    "evidence_digest": row["evidence_digest"],
                    "previous_digest": previous,
                    "recorded_at": row["recorded_at"],
                }
                if (
                    row["audit_sequence"] != sequence
                    or row["previous_digest"] != previous
                    or row["audit_digest"] != canonical_digest(value)
                ):
                    return False
                previous = row["audit_digest"]
            return True

    def verify_record_bindings(self) -> bool:
        with self._lock:
            if not self.verify_metadata() or not self.verify_audit_chain():
                return False
            receipts = self._connection.execute(
                "SELECT * FROM synthetic_decision_receipts ORDER BY receipt_id"
            ).fetchall()
            audits = self._connection.execute(
                "SELECT * FROM synthetic_decision_receipt_audit ORDER BY audit_sequence"
            ).fetchall()
            if len(receipts) != len(audits):
                return False
            audit_by_receipt = {row["receipt_id"]: row for row in audits}
            try:
                for receipt in receipts:
                    self._record_from_row(receipt)
                    audit = audit_by_receipt.get(receipt["receipt_id"])
                    if (
                        audit is None
                        or audit["action"] != "SYNTHETIC_DECISION_INTENT_RECEIPTED"
                        or audit["actor_id"]
                        != "synthetic:system:decision-receipt-ledger"
                        or audit["evidence_digest"] != receipt["assessment_digest"]
                        or audit["recorded_at"] != receipt["recorded_at"]
                    ):
                        return False
            except (GovernanceRejected, KeyError, TypeError, ValueError):
                return False
            return True

    def evidence(self) -> dict[str, object]:
        with self._lock:
            counts = {decision.value: 0 for decision in SyntheticOperatorDecision}
            for row in self._connection.execute(
                "SELECT decision, COUNT(*) AS count FROM synthetic_decision_receipts "
                "GROUP BY decision"
            ):
                counts[row["decision"]] = row["count"]
            value = {
                "schema": "nurion.pg.synthetic-decision-receipt-ledger-evidence.v1",
                "database_engine": "SQLite",
                "schema_version": DECISION_RECEIPT_SCHEMA_VERSION,
                "schema_digest": canonical_digest(DECISION_RECEIPT_SCHEMA_SQL),
                "metadata_valid": self.verify_metadata(),
                "decision_counts": counts,
                "audit_chain_valid": self.verify_audit_chain(),
                "record_bindings_valid": self.verify_record_bindings(),
                "maximum_state": RECEIPT_STATE,
                "synthetic_evidence_only": True,
                "actual_operator_decision_recording_method_present": False,
                "packet_state_change_method_present": False,
                "code_change_method_present": False,
                "application_method_present": False,
                "execution_method_present": False,
                "money_movement_executed": False,
                "production_activation_allowed": False,
            }
            return {**value, "report_digest": canonical_digest(value)}
