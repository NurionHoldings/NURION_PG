"""Durable synthetic receipts for validated patch draft promotion intents."""

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
from .operator_decision_intake import SYNTHETIC_OPERATOR_ID
from .patch_draft_promotion_decision_intake import (
    PATCH_DRAFT_PROMOTION_VALIDATION_STATE,
    PatchDraftPromotionDecisionIntentAssessment,
    SyntheticPatchDraftPromotionDecision,
    SyntheticPatchDraftPromotionDecisionIntake,
)


PATCH_DRAFT_PROMOTION_RECEIPT_SCHEMA_VERSION = 1
PATCH_DRAFT_PROMOTION_RECEIPT_STATE = (
    "SYNTHETIC_PATCH_DRAFT_PROMOTION_DECISION_RECEIPT_RECORDED"
)
_RECEIPT_PREFIX = "synthetic:patch-draft-promotion-decision-receipt:"
_ACTOR_ID = "synthetic:system:patch-draft-promotion-receipt-ledger"


PATCH_DRAFT_PROMOTION_RECEIPT_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS synthetic_patch_draft_promotion_receipt_metadata (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    schema_version INTEGER NOT NULL CHECK (schema_version = 1),
    synthetic_only INTEGER NOT NULL CHECK (synthetic_only = 1)
);
CREATE TABLE IF NOT EXISTS synthetic_patch_draft_promotion_receipts (
    receipt_id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL UNIQUE,
    assessment_digest TEXT NOT NULL UNIQUE,
    envelope_id TEXT NOT NULL UNIQUE,
    envelope_digest TEXT NOT NULL UNIQUE,
    nonce TEXT NOT NULL UNIQUE,
    packet_id TEXT NOT NULL UNIQUE,
    packet_digest TEXT NOT NULL,
    operator_id TEXT NOT NULL CHECK (
        operator_id = 'synthetic:operator:CHOI_IN_SEOK'
    ),
    decision TEXT NOT NULL CHECK (decision IN (
        'AUTHORIZE_SYNTHETIC_PATCH_DRAFT_LIMITED_PROMOTION', 'HOLD', 'REJECT'
    )),
    assessment_json TEXT NOT NULL,
    state TEXT NOT NULL CHECK (
        state = 'SYNTHETIC_PATCH_DRAFT_PROMOTION_DECISION_RECEIPT_RECORDED'
    ),
    recorded_at TEXT NOT NULL,
    actual_operator_decision_recorded INTEGER NOT NULL DEFAULT 0
        CHECK (actual_operator_decision_recorded = 0),
    packet_state_changed INTEGER NOT NULL DEFAULT 0 CHECK (packet_state_changed = 0),
    patch_content_present INTEGER NOT NULL DEFAULT 0 CHECK (patch_content_present = 0),
    diff_content_present INTEGER NOT NULL DEFAULT 0 CHECK (diff_content_present = 0),
    source_code_changed INTEGER NOT NULL DEFAULT 0 CHECK (source_code_changed = 0),
    filesystem_written INTEGER NOT NULL DEFAULT 0 CHECK (filesystem_written = 0),
    automatic_application_allowed INTEGER NOT NULL DEFAULT 0
        CHECK (automatic_application_allowed = 0),
    safety_baseline_relaxation_allowed INTEGER NOT NULL DEFAULT 0
        CHECK (safety_baseline_relaxation_allowed = 0),
    execution_allowed INTEGER NOT NULL DEFAULT 0 CHECK (execution_allowed = 0),
    production_activation_allowed INTEGER NOT NULL DEFAULT 0
        CHECK (production_activation_allowed = 0)
);
CREATE TABLE IF NOT EXISTS synthetic_patch_draft_promotion_receipt_audit (
    audit_sequence INTEGER PRIMARY KEY,
    receipt_id TEXT NOT NULL UNIQUE,
    action TEXT NOT NULL CHECK (
        action = 'SYNTHETIC_PATCH_DRAFT_PROMOTION_INTENT_RECEIPTED'
    ),
    actor_id TEXT NOT NULL CHECK (
        actor_id = 'synthetic:system:patch-draft-promotion-receipt-ledger'
    ),
    evidence_digest TEXT NOT NULL,
    previous_digest TEXT NOT NULL,
    audit_digest TEXT NOT NULL UNIQUE,
    recorded_at TEXT NOT NULL
);
""".strip()


def _valid_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


@dataclass(frozen=True)
class SyntheticPatchDraftPromotionDecisionReceipt:
    receipt_id: str
    assessment_id: str
    assessment_digest: str
    envelope_id: str
    envelope_digest: str
    nonce: str
    packet_id: str
    packet_digest: str
    operator_id: str
    decision: SyntheticPatchDraftPromotionDecision
    state: str
    recorded_at: datetime
    actual_operator_decision_recorded: bool = False
    packet_state_changed: bool = False
    patch_content_present: bool = False
    diff_content_present: bool = False
    source_code_changed: bool = False
    filesystem_written: bool = False
    automatic_application_allowed: bool = False
    safety_baseline_relaxation_allowed: bool = False
    execution_allowed: bool = False
    production_activation_allowed: bool = False

    def __post_init__(self) -> None:
        if (
            not self.receipt_id.startswith(_RECEIPT_PREFIX)
            or not self.assessment_id.startswith(
                "synthetic:patch-draft-promotion-decision-assessment:"
            )
            or not _valid_digest(self.assessment_digest)
            or not self.envelope_id.startswith(
                "synthetic:patch-draft-promotion-decision-envelope:"
            )
            or not _valid_digest(self.envelope_digest)
            or not self.nonce.startswith(
                "synthetic:patch-draft-promotion-operator-nonce:"
            )
            or not self.packet_id.startswith(
                "synthetic:patch-draft-promotion-operator-packet:"
            )
            or not _valid_digest(self.packet_digest)
            or self.operator_id != SYNTHETIC_OPERATOR_ID
            or not isinstance(self.decision, SyntheticPatchDraftPromotionDecision)
            or self.state != PATCH_DRAFT_PROMOTION_RECEIPT_STATE
            or self.recorded_at.tzinfo is None
            or any((
                self.actual_operator_decision_recorded,
                self.packet_state_changed,
                self.patch_content_present,
                self.diff_content_present,
                self.source_code_changed,
                self.filesystem_written,
                self.automatic_application_allowed,
                self.safety_baseline_relaxation_allowed,
                self.execution_allowed,
                self.production_activation_allowed,
            ))
        ):
            raise GovernanceRejected(
                "valid non-authorizing patch draft promotion receipt required"
            )

    def digest_value(self) -> dict[str, object]:
        return {
            "receipt_id": self.receipt_id,
            "assessment_id": self.assessment_id,
            "assessment_digest": self.assessment_digest,
            "envelope_id": self.envelope_id,
            "envelope_digest": self.envelope_digest,
            "nonce": self.nonce,
            "packet_id": self.packet_id,
            "packet_digest": self.packet_digest,
            "operator_id": self.operator_id,
            "decision": self.decision.value,
            "state": self.state,
            "recorded_at": self.recorded_at.isoformat(),
            "actual_operator_decision_recorded": False,
            "packet_state_changed": False,
            "patch_content_present": False,
            "diff_content_present": False,
            "source_code_changed": False,
            "filesystem_written": False,
            "automatic_application_allowed": False,
            "safety_baseline_relaxation_allowed": False,
            "execution_allowed": False,
            "production_activation_allowed": False,
        }

    def receipt_digest(self) -> str:
        return canonical_digest(self.digest_value())


class SyntheticPatchDraftPromotionDecisionReceiptLedger:
    """Persists validated intent evidence without recording an actual decision."""

    def __init__(self, database: str | Path) -> None:
        value = str(database)
        self._validate_database_target(value)
        self._connection = sqlite3.connect(
            value, isolation_level=None, timeout=5, check_same_thread=False
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
        path = Path(database)
        if not path.name.startswith("synthetic-") or path.suffix not in {
            ".db", ".sqlite", ".sqlite3"
        }:
            raise GovernanceRejected(
                "synthetic SQLite patch draft promotion receipt target required"
            )

    def _initialize_schema(self) -> None:
        with self._lock:
            self._connection.executescript(PATCH_DRAFT_PROMOTION_RECEIPT_SCHEMA_SQL)
            self._connection.execute(
                "INSERT OR IGNORE INTO "
                "synthetic_patch_draft_promotion_receipt_metadata "
                "(singleton, schema_version, synthetic_only) VALUES (1, ?, 1)",
                (PATCH_DRAFT_PROMOTION_RECEIPT_SCHEMA_VERSION,),
            )
            if not self.verify_metadata():
                raise GovernanceRejected("unsupported promotion receipt schema")

    def verify_metadata(self) -> bool:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM synthetic_patch_draft_promotion_receipt_metadata"
            ).fetchall()
            return (
                len(rows) == 1
                and rows[0]["singleton"] == 1
                and rows[0]["schema_version"]
                == PATCH_DRAFT_PROMOTION_RECEIPT_SCHEMA_VERSION
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
        intake: SyntheticPatchDraftPromotionDecisionIntake,
        envelope_id: str,
        *,
        recorded_at: datetime,
    ) -> SyntheticPatchDraftPromotionDecisionReceipt:
        if recorded_at.tzinfo is None:
            raise GovernanceRejected("timezone-aware promotion receipt time required")
        if not isinstance(intake, SyntheticPatchDraftPromotionDecisionIntake):
            raise GovernanceRejected("typed promotion decision intake required")
        if not intake.verify_assessment_chain():
            raise GovernanceRejected("promotion assessment chain is invalid")
        matches = [
            item for item in intake.assessments if item.envelope_id == envelope_id
        ]
        if len(matches) != 1:
            raise GovernanceRejected("one validated promotion assessment required")
        assessment = matches[0]
        self._validate_assessment(assessment)
        if recorded_at < assessment.assessed_at:
            raise GovernanceRejected("promotion receipt cannot predate assessment")
        receipt_id = _RECEIPT_PREFIX + assessment.assessment_digest[:32]
        payload = {
            **assessment.digest_value(),
            "assessment_digest": assessment.assessment_digest,
        }
        before = intake.evidence()["report_digest"]
        with self._lock:
            try:
                with self._transaction():
                    if not self.verify_metadata():
                        raise GovernanceRejected("promotion receipt metadata is invalid")
                    existing = self._connection.execute(
                        "SELECT * FROM synthetic_patch_draft_promotion_receipts "
                        "WHERE receipt_id = ?", (receipt_id,),
                    ).fetchone()
                    if existing is not None:
                        if (
                            existing["assessment_digest"]
                            != assessment.assessment_digest
                            or existing["envelope_id"] != envelope_id
                        ):
                            raise GovernanceRejected("promotion receipt collision")
                        if not self.verify_record_bindings():
                            raise GovernanceRejected("existing promotion receipt is invalid")
                        if before != intake.evidence()["report_digest"]:
                            raise GovernanceRejected("assessment changed during receipting")
                        return self._record_from_row(existing)
                    self._connection.execute(
                        """
                        INSERT INTO synthetic_patch_draft_promotion_receipts (
                            receipt_id, assessment_id, assessment_digest, envelope_id,
                            envelope_digest, nonce, packet_id, packet_digest, operator_id,
                            decision, assessment_json, state, recorded_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            receipt_id, assessment.assessment_id,
                            assessment.assessment_digest, assessment.envelope_id,
                            assessment.envelope_digest, assessment.nonce,
                            assessment.packet_id, assessment.packet_digest,
                            assessment.operator_id, assessment.decision.value,
                            json.dumps(
                                payload, ensure_ascii=False, sort_keys=True,
                                separators=(",", ":"),
                            ),
                            PATCH_DRAFT_PROMOTION_RECEIPT_STATE,
                            recorded_at.isoformat(),
                        ),
                    )
                    self._append_audit(
                        receipt_id, assessment.assessment_digest, recorded_at
                    )
                    if before != intake.evidence()["report_digest"]:
                        raise GovernanceRejected("assessment changed during receipting")
                    return self._get_record(receipt_id)
            except sqlite3.Error as exc:
                raise GovernanceRejected("promotion receipt transaction failed") from exc

    @staticmethod
    def _validate_assessment(
        assessment: PatchDraftPromotionDecisionIntentAssessment,
    ) -> None:
        if (
            not isinstance(assessment, PatchDraftPromotionDecisionIntentAssessment)
            or assessment.validation_state != PATCH_DRAFT_PROMOTION_VALIDATION_STATE
            or assessment.assessment_digest
            != canonical_digest(assessment.digest_value())
            or any((
                assessment.packet_state_changed,
                assessment.operator_decision_recorded,
                assessment.patch_content_present,
                assessment.diff_content_present,
                assessment.source_code_changed,
                assessment.filesystem_written,
                assessment.automatic_application_allowed,
                assessment.safety_baseline_relaxation_allowed,
                assessment.execution_allowed,
                assessment.production_activation_allowed,
            ))
        ):
            raise GovernanceRejected("intact synthetic promotion assessment required")

    def _append_audit(
        self, receipt_id: str, evidence_digest: str, recorded_at: datetime
    ) -> None:
        latest = self._connection.execute(
            "SELECT * FROM synthetic_patch_draft_promotion_receipt_audit "
            "ORDER BY audit_sequence DESC LIMIT 1"
        ).fetchone()
        sequence = (latest["audit_sequence"] if latest else 0) + 1
        previous = latest["audit_digest"] if latest else "0" * 64
        value = {
            "audit_sequence": sequence,
            "receipt_id": receipt_id,
            "action": "SYNTHETIC_PATCH_DRAFT_PROMOTION_INTENT_RECEIPTED",
            "actor_id": _ACTOR_ID,
            "evidence_digest": evidence_digest,
            "previous_digest": previous,
            "recorded_at": recorded_at.isoformat(),
        }
        self._connection.execute(
            "INSERT INTO synthetic_patch_draft_promotion_receipt_audit VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?)",
            (
                sequence, receipt_id, value["action"], _ACTOR_ID,
                evidence_digest, previous, canonical_digest(value),
                recorded_at.isoformat(),
            ),
        )

    @staticmethod
    def _validate_stored_assessment(payload: object) -> None:
        if not isinstance(payload, dict):
            raise GovernanceRejected("stored promotion assessment object required")
        assessment = PatchDraftPromotionDecisionIntentAssessment(
            int(payload["sequence"]),
            str(payload["assessment_id"]),
            str(payload["envelope_id"]),
            str(payload["envelope_digest"]),
            str(payload["nonce"]),
            str(payload["packet_id"]),
            str(payload["packet_digest"]),
            str(payload["operator_id"]),
            SyntheticPatchDraftPromotionDecision(str(payload["decision"])),
            datetime.fromisoformat(str(payload["assessed_at"])),
            str(payload["previous_digest"]),
            str(payload["assessment_digest"]),
            str(payload["validation_state"]),
            bool(payload["packet_state_changed"]),
            bool(payload["operator_decision_recorded"]),
            bool(payload["patch_content_present"]),
            bool(payload["diff_content_present"]),
            bool(payload["source_code_changed"]),
            bool(payload["filesystem_written"]),
            bool(payload["automatic_application_allowed"]),
            bool(payload["safety_baseline_relaxation_allowed"]),
            bool(payload["execution_allowed"]),
            bool(payload["production_activation_allowed"]),
        )
        if assessment.assessment_digest != payload["assessment_digest"]:
            raise GovernanceRejected("stored promotion assessment digest mismatch")

    @classmethod
    def _record_from_row(
        cls, row: sqlite3.Row
    ) -> SyntheticPatchDraftPromotionDecisionReceipt:
        try:
            payload = json.loads(row["assessment_json"])
            cls._validate_stored_assessment(payload)
        except (GovernanceRejected, KeyError, TypeError, ValueError) as exc:
            raise GovernanceRejected("stored promotion receipt is invalid") from exc
        expected = _RECEIPT_PREFIX + row["assessment_digest"][:32]
        bindings = (
            ("receipt_id", expected),
            ("assessment_id", payload["assessment_id"]),
            ("assessment_digest", payload["assessment_digest"]),
            ("envelope_id", payload["envelope_id"]),
            ("envelope_digest", payload["envelope_digest"]),
            ("nonce", payload["nonce"]),
            ("packet_id", payload["packet_id"]),
            ("packet_digest", payload["packet_digest"]),
            ("operator_id", payload["operator_id"]),
            ("decision", payload["decision"]),
        )
        if any(row[field] != value for field, value in bindings):
            raise GovernanceRejected("stored promotion receipt binding is invalid")
        return SyntheticPatchDraftPromotionDecisionReceipt(
            row["receipt_id"], row["assessment_id"], row["assessment_digest"],
            row["envelope_id"], row["envelope_digest"], row["nonce"],
            row["packet_id"], row["packet_digest"], row["operator_id"],
            SyntheticPatchDraftPromotionDecision(row["decision"]), row["state"],
            datetime.fromisoformat(row["recorded_at"]),
            bool(row["actual_operator_decision_recorded"]),
            bool(row["packet_state_changed"]), bool(row["patch_content_present"]),
            bool(row["diff_content_present"]), bool(row["source_code_changed"]),
            bool(row["filesystem_written"]),
            bool(row["automatic_application_allowed"]),
            bool(row["safety_baseline_relaxation_allowed"]),
            bool(row["execution_allowed"]), bool(row["production_activation_allowed"]),
        )

    def _get_record(
        self, receipt_id: str
    ) -> SyntheticPatchDraftPromotionDecisionReceipt:
        row = self._connection.execute(
            "SELECT * FROM synthetic_patch_draft_promotion_receipts "
            "WHERE receipt_id = ?", (receipt_id,),
        ).fetchone()
        if row is None:
            raise GovernanceRejected("unknown promotion decision receipt")
        return self._record_from_row(row)

    def get(self, receipt_id: str) -> SyntheticPatchDraftPromotionDecisionReceipt:
        with self._lock:
            return self._get_record(receipt_id)

    def verify_audit_chain(self) -> bool:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM synthetic_patch_draft_promotion_receipt_audit "
                "ORDER BY audit_sequence"
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
            rows = self._connection.execute(
                "SELECT * FROM synthetic_patch_draft_promotion_receipts"
            ).fetchall()
            try:
                records = [self._record_from_row(row) for row in rows]
            except (GovernanceRejected, ValueError):
                return False
            audits = self._connection.execute(
                "SELECT receipt_id, evidence_digest FROM "
                "synthetic_patch_draft_promotion_receipt_audit"
            ).fetchall()
            audit_by_receipt = {
                row["receipt_id"]: row["evidence_digest"] for row in audits
            }
            return len(records) == len(audits) and all(
                audit_by_receipt.get(record.receipt_id) == record.assessment_digest
                for record in records
            )

    def evidence(self) -> dict[str, object]:
        with self._lock:
            counts = {
                item.value: 0 for item in SyntheticPatchDraftPromotionDecision
            }
            for row in self._connection.execute(
                "SELECT decision, COUNT(*) AS count FROM "
                "synthetic_patch_draft_promotion_receipts GROUP BY decision"
            ):
                counts[row["decision"]] = row["count"]
            receipts = [
                self._record_from_row(row)
                for row in self._connection.execute(
                    "SELECT * FROM synthetic_patch_draft_promotion_receipts "
                    "ORDER BY receipt_id"
                )
            ]
            latest = self._connection.execute(
                "SELECT audit_digest FROM "
                "synthetic_patch_draft_promotion_receipt_audit "
                "ORDER BY audit_sequence DESC LIMIT 1"
            ).fetchone()
            value = {
                "schema": (
                    "nurion.pg.synthetic-patch-draft-promotion-receipt-ledger-"
                    "evidence.v1"
                ),
                "database_engine": "SQLite",
                "schema_version": PATCH_DRAFT_PROMOTION_RECEIPT_SCHEMA_VERSION,
                "schema_digest": canonical_digest(
                    PATCH_DRAFT_PROMOTION_RECEIPT_SCHEMA_SQL
                ),
                "metadata_valid": self.verify_metadata(),
                "decision_counts": counts,
                "receipt_digests": [item.receipt_digest() for item in receipts],
                "audit_head_digest": latest["audit_digest"] if latest else "0" * 64,
                "audit_chain_valid": self.verify_audit_chain(),
                "record_bindings_valid": self.verify_record_bindings(),
                "maximum_state": PATCH_DRAFT_PROMOTION_RECEIPT_STATE,
                "synthetic_evidence_only": True,
                "actual_operator_decision_recording_method_present": False,
                "packet_state_change_method_present": False,
                "patch_content_present": False,
                "diff_content_present": False,
                "source_code_change_method_present": False,
                "filesystem_write_method_present": False,
                "application_method_present": False,
                "safety_baseline_relaxation_method_present": False,
                "execution_method_present": False,
                "network_access_method_present": False,
                "personal_data_used": False,
                "credentials_used": False,
                "money_movement_executed": False,
                "production_activation_allowed": False,
            }
            return {**value, "report_digest": canonical_digest(value)}
