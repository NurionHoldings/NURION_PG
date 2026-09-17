"""Durable Eternian review docket for synthetic implementation proposal drafts."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from threading import RLock
from typing import Iterator

from .arkaon.governance import GovernanceRejected, canonical_digest
from .operator_decision_intake import SyntheticOperatorDecision
from .synthetic_implementation_proposals import (
    IMPLEMENTATION_PROPOSAL_STATE,
    SyntheticImplementationProposalBook,
    SyntheticImplementationProposalDraft,
)


IMPLEMENTATION_REVIEW_SCHEMA_VERSION = 1
MAXIMUM_REVIEW_STATE = "READY_FOR_SYNTHETIC_PATCH_SHADOW"
_REVIEWER_PREFIX = "synthetic:eternian-reviewer:implementation-proposal:"
_REVIEW_ID_PREFIX = "synthetic:implementation-proposal-review:"


class ImplementationProposalReviewState(StrEnum):
    PENDING_ETERNIAN_REVIEW = "PENDING_ETERNIAN_REVIEW"
    READY_FOR_SYNTHETIC_PATCH_SHADOW = "READY_FOR_SYNTHETIC_PATCH_SHADOW"
    HELD = "HELD"
    REJECTED = "REJECTED"


class ImplementationProposalReviewDecision(StrEnum):
    PASS = "PASS"
    HOLD = "HOLD"
    REJECT = "REJECT"


_STATE_BY_DECISION = {
    ImplementationProposalReviewDecision.PASS: (
        ImplementationProposalReviewState.READY_FOR_SYNTHETIC_PATCH_SHADOW
    ),
    ImplementationProposalReviewDecision.HOLD: ImplementationProposalReviewState.HELD,
    ImplementationProposalReviewDecision.REJECT: (
        ImplementationProposalReviewState.REJECTED
    ),
}


IMPLEMENTATION_REVIEW_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS synthetic_implementation_review_metadata (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    schema_version INTEGER NOT NULL CHECK (schema_version = 1),
    synthetic_only INTEGER NOT NULL CHECK (synthetic_only = 1)
);
CREATE TABLE IF NOT EXISTS synthetic_implementation_review_records (
    proposal_id TEXT PRIMARY KEY,
    proposal_digest TEXT NOT NULL UNIQUE,
    source_receipt_id TEXT NOT NULL UNIQUE,
    source_receipt_digest TEXT NOT NULL,
    source_packet_id TEXT NOT NULL,
    proposal_json TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN (
        'PENDING_ETERNIAN_REVIEW',
        'READY_FOR_SYNTHETIC_PATCH_SHADOW',
        'HELD',
        'REJECTED'
    )),
    submitted_at TEXT NOT NULL,
    review_id TEXT UNIQUE,
    reviewer_id TEXT,
    review_decision TEXT CHECK (review_decision IN ('PASS', 'HOLD', 'REJECT')),
    findings_digest TEXT,
    reviewed_at TEXT,
    review_digest TEXT UNIQUE,
    actual_operator_decision_recorded INTEGER NOT NULL DEFAULT 0
        CHECK (actual_operator_decision_recorded = 0),
    code_change_allowed INTEGER NOT NULL DEFAULT 0 CHECK (code_change_allowed = 0),
    automatic_application_allowed INTEGER NOT NULL DEFAULT 0
        CHECK (automatic_application_allowed = 0),
    execution_allowed INTEGER NOT NULL DEFAULT 0 CHECK (execution_allowed = 0),
    production_activation_allowed INTEGER NOT NULL DEFAULT 0
        CHECK (production_activation_allowed = 0),
    CHECK (
        (state = 'PENDING_ETERNIAN_REVIEW'
            AND review_id IS NULL
            AND reviewer_id IS NULL
            AND review_decision IS NULL
            AND findings_digest IS NULL
            AND reviewed_at IS NULL
            AND review_digest IS NULL)
        OR
        (state != 'PENDING_ETERNIAN_REVIEW'
            AND review_id IS NOT NULL
            AND reviewer_id IS NOT NULL
            AND review_decision IS NOT NULL
            AND findings_digest IS NOT NULL
            AND reviewed_at IS NOT NULL
            AND review_digest IS NOT NULL)
    )
);
CREATE TABLE IF NOT EXISTS synthetic_implementation_review_audit (
    audit_sequence INTEGER PRIMARY KEY,
    proposal_id TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('SUBMITTED', 'ETERNIAN_REVIEWED')),
    actor_id TEXT NOT NULL,
    evidence_digest TEXT NOT NULL,
    previous_digest TEXT NOT NULL,
    audit_digest TEXT NOT NULL UNIQUE,
    recorded_at TEXT NOT NULL,
    UNIQUE (proposal_id, action)
);
""".strip()


def _valid_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _valid_prefixed_id(value: object, prefix: str) -> bool:
    return isinstance(value, str) and value.startswith(prefix) and len(value) > len(prefix)


@dataclass(frozen=True)
class SyntheticImplementationReviewRecord:
    proposal: SyntheticImplementationProposalDraft
    state: ImplementationProposalReviewState
    submitted_at: datetime
    review_id: str | None = None
    reviewer_id: str | None = None
    review_decision: ImplementationProposalReviewDecision | None = None
    findings_digest: str | None = None
    reviewed_at: datetime | None = None
    review_digest: str | None = None
    actual_operator_decision_recorded: bool = False
    code_change_allowed: bool = False
    automatic_application_allowed: bool = False
    execution_allowed: bool = False
    production_activation_allowed: bool = False

    def __post_init__(self) -> None:
        pending = self.state is ImplementationProposalReviewState.PENDING_ETERNIAN_REVIEW
        review_fields = (
            self.review_id,
            self.reviewer_id,
            self.review_decision,
            self.findings_digest,
            self.reviewed_at,
            self.review_digest,
        )
        if (
            not isinstance(self.proposal, SyntheticImplementationProposalDraft)
            or self.proposal.state != IMPLEMENTATION_PROPOSAL_STATE
            or self.proposal.proposal_digest
            != canonical_digest(self.proposal.digest_value())
            or self.submitted_at.tzinfo is None
            or self.submitted_at < self.proposal.drafted_at
            or self.actual_operator_decision_recorded
            or self.code_change_allowed
            or self.automatic_application_allowed
            or self.execution_allowed
            or self.production_activation_allowed
            or (pending and any(field is not None for field in review_fields))
            or (not pending and any(field is None for field in review_fields))
        ):
            raise GovernanceRejected("valid synthetic implementation review record required")
        if not pending:
            if (
                not _valid_prefixed_id(self.review_id, _REVIEW_ID_PREFIX)
                or not _valid_prefixed_id(self.reviewer_id, _REVIEWER_PREFIX)
                or not isinstance(
                    self.review_decision, ImplementationProposalReviewDecision
                )
                or self.state != _STATE_BY_DECISION[self.review_decision]
                or not _valid_digest(self.findings_digest)
                or self.reviewed_at.tzinfo is None  # type: ignore[union-attr]
                or self.reviewed_at < self.submitted_at  # type: ignore[operator]
                or self.review_digest != canonical_digest(self.review_value())
            ):
                raise GovernanceRejected("valid Eternian implementation review required")

    def review_value(self) -> dict[str, object]:
        return {
            "proposal_id": self.proposal.proposal_id,
            "proposal_digest": self.proposal.proposal_digest,
            "review_id": self.review_id,
            "reviewer_id": self.reviewer_id,
            "decision": self.review_decision.value if self.review_decision else None,
            "findings_digest": self.findings_digest,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "resulting_state": self.state.value,
            "actual_operator_decision_recorded": False,
            "code_change_allowed": False,
            "automatic_application_allowed": False,
            "execution_allowed": False,
            "production_activation_allowed": False,
        }


class SyntheticImplementationReviewDocket:
    """Persists independent review without applying an implementation proposal."""

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
            raise GovernanceRejected("synthetic SQLite implementation review target required")

    def _initialize_schema(self) -> None:
        with self._lock:
            self._connection.executescript(IMPLEMENTATION_REVIEW_SCHEMA_SQL)
            self._connection.execute(
                """
                INSERT OR IGNORE INTO synthetic_implementation_review_metadata
                    (singleton, schema_version, synthetic_only) VALUES (1, ?, 1)
                """,
                (IMPLEMENTATION_REVIEW_SCHEMA_VERSION,),
            )
            if not self.verify_metadata():
                raise GovernanceRejected("unsupported implementation review schema")

    def verify_metadata(self) -> bool:
        with self._lock:
            rows = self._connection.execute(
                "SELECT singleton, schema_version, synthetic_only "
                "FROM synthetic_implementation_review_metadata"
            ).fetchall()
            return (
                len(rows) == 1
                and rows[0]["singleton"] == 1
                and rows[0]["schema_version"] == IMPLEMENTATION_REVIEW_SCHEMA_VERSION
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

    def submit_from_book(
        self,
        book: SyntheticImplementationProposalBook,
        source_receipt_id: str,
        *,
        submitted_at: datetime,
    ) -> SyntheticImplementationReviewRecord:
        if submitted_at.tzinfo is None:
            raise GovernanceRejected("timezone-aware implementation submission required")
        if not isinstance(book, SyntheticImplementationProposalBook):
            raise GovernanceRejected("typed synthetic implementation proposal book required")
        if not book.verify_proposal_chain():
            raise GovernanceRejected("intact implementation proposal chain required")
        matches = [
            proposal
            for proposal in book.proposals
            if proposal.source_receipt_id == source_receipt_id
        ]
        if len(matches) != 1:
            raise GovernanceRejected("one synthetic implementation proposal required")
        proposal = matches[0]
        self._validate_proposal(proposal)
        if submitted_at < proposal.drafted_at:
            raise GovernanceRejected("submission cannot predate implementation draft")
        before = book.evidence()["report_digest"]
        payload = {**proposal.digest_value(), "proposal_digest": proposal.proposal_digest}
        with self._lock:
            try:
                with self._transaction():
                    if not self.verify_metadata():
                        raise GovernanceRejected("implementation review metadata is invalid")
                    existing = self._connection.execute(
                        "SELECT * FROM synthetic_implementation_review_records "
                        "WHERE proposal_id = ?",
                        (proposal.proposal_id,),
                    ).fetchone()
                    if existing is not None:
                        if (
                            existing["proposal_digest"] != proposal.proposal_digest
                            or existing["source_receipt_id"] != source_receipt_id
                        ):
                            raise GovernanceRejected("implementation submission collision")
                        if (
                            not self.verify_audit_chain()
                            or not self.verify_record_bindings()
                        ):
                            raise GovernanceRejected("existing implementation review is invalid")
                        record = self._record_from_row(existing)
                    else:
                        self._connection.execute(
                            """
                            INSERT INTO synthetic_implementation_review_records (
                                proposal_id, proposal_digest, source_receipt_id,
                                source_receipt_digest, source_packet_id, proposal_json,
                                state, submitted_at, actual_operator_decision_recorded,
                                code_change_allowed, automatic_application_allowed,
                                execution_allowed, production_activation_allowed
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0)
                            """,
                            (
                                proposal.proposal_id,
                                proposal.proposal_digest,
                                proposal.source_receipt_id,
                                proposal.source_receipt_digest,
                                proposal.source_packet_id,
                                json.dumps(
                                    payload,
                                    ensure_ascii=False,
                                    sort_keys=True,
                                    separators=(",", ":"),
                                ),
                                ImplementationProposalReviewState.PENDING_ETERNIAN_REVIEW.value,
                                submitted_at.isoformat(),
                            ),
                        )
                        self._append_audit(
                            proposal.proposal_id,
                            "SUBMITTED",
                            "synthetic:system:implementation-review-docket",
                            proposal.proposal_digest,
                            submitted_at,
                        )
                        record = self._get_record(proposal.proposal_id)
                    if before != book.evidence()["report_digest"]:
                        raise GovernanceRejected(
                            "implementation proposal changed during submission"
                        )
                    return record
            except sqlite3.Error as exc:
                raise GovernanceRejected("implementation submission transaction failed") from exc

    @staticmethod
    def _validate_proposal(proposal: SyntheticImplementationProposalDraft) -> None:
        if (
            not isinstance(proposal, SyntheticImplementationProposalDraft)
            or proposal.proposal_digest != canonical_digest(proposal.digest_value())
            or proposal.state != IMPLEMENTATION_PROPOSAL_STATE
            or not proposal.eternian_review_required
            or proposal.actual_operator_decision_recorded
            or proposal.code_change_allowed
            or proposal.automatic_application_allowed
            or proposal.execution_allowed
            or proposal.money_movement_allowed
            or proposal.production_activation_allowed
        ):
            raise GovernanceRejected("intact non-executable implementation draft required")

    def record_eternian_review(
        self,
        proposal_id: str,
        *,
        review_id: str,
        reviewer_id: str,
        decision: ImplementationProposalReviewDecision,
        findings_digest: str,
        reviewed_at: datetime,
    ) -> SyntheticImplementationReviewRecord:
        if (
            not _valid_prefixed_id(review_id, _REVIEW_ID_PREFIX)
            or not _valid_prefixed_id(reviewer_id, _REVIEWER_PREFIX)
            or not isinstance(decision, ImplementationProposalReviewDecision)
            or not _valid_digest(findings_digest)
            or reviewed_at.tzinfo is None
        ):
            raise GovernanceRejected("valid Eternian implementation review metadata required")
        with self._lock:
            try:
                with self._transaction():
                    if not self.verify_metadata():
                        raise GovernanceRejected("implementation review metadata is invalid")
                    row = self._connection.execute(
                        "SELECT * FROM synthetic_implementation_review_records "
                        "WHERE proposal_id = ?",
                        (proposal_id,),
                    ).fetchone()
                    if row is None:
                        raise GovernanceRejected("unknown implementation proposal")
                    current = self._record_from_row(row)
                    if current.review_id is not None:
                        expected = (
                            review_id,
                            reviewer_id,
                            decision,
                            findings_digest,
                            reviewed_at,
                        )
                        actual = (
                            current.review_id,
                            current.reviewer_id,
                            current.review_decision,
                            current.findings_digest,
                            current.reviewed_at,
                        )
                        if expected != actual:
                            raise GovernanceRejected("implementation review already recorded")
                        if (
                            not self.verify_audit_chain()
                            or not self.verify_record_bindings()
                        ):
                            raise GovernanceRejected("existing implementation review is invalid")
                        return current
                    if reviewed_at < current.submitted_at:
                        raise GovernanceRejected("review cannot predate submission")
                    state = _STATE_BY_DECISION[decision]
                    review_value = {
                        "proposal_id": proposal_id,
                        "proposal_digest": current.proposal.proposal_digest,
                        "review_id": review_id,
                        "reviewer_id": reviewer_id,
                        "decision": decision.value,
                        "findings_digest": findings_digest,
                        "reviewed_at": reviewed_at.isoformat(),
                        "resulting_state": state.value,
                        "actual_operator_decision_recorded": False,
                        "code_change_allowed": False,
                        "automatic_application_allowed": False,
                        "execution_allowed": False,
                        "production_activation_allowed": False,
                    }
                    review_digest = canonical_digest(review_value)
                    self._connection.execute(
                        """
                        UPDATE synthetic_implementation_review_records SET
                            state = ?, review_id = ?, reviewer_id = ?,
                            review_decision = ?, findings_digest = ?, reviewed_at = ?,
                            review_digest = ?
                        WHERE proposal_id = ? AND state = 'PENDING_ETERNIAN_REVIEW'
                        """,
                        (
                            state.value,
                            review_id,
                            reviewer_id,
                            decision.value,
                            findings_digest,
                            reviewed_at.isoformat(),
                            review_digest,
                            proposal_id,
                        ),
                    )
                    self._append_audit(
                        proposal_id,
                        "ETERNIAN_REVIEWED",
                        reviewer_id,
                        review_digest,
                        reviewed_at,
                    )
                    return self._get_record(proposal_id)
            except sqlite3.Error as exc:
                raise GovernanceRejected("implementation review transaction failed") from exc

    def _append_audit(
        self,
        proposal_id: str,
        action: str,
        actor_id: str,
        evidence_digest: str,
        recorded_at: datetime,
    ) -> None:
        latest = self._connection.execute(
            "SELECT audit_sequence, audit_digest "
            "FROM synthetic_implementation_review_audit "
            "ORDER BY audit_sequence DESC LIMIT 1"
        ).fetchone()
        sequence = (latest["audit_sequence"] if latest else 0) + 1
        previous = latest["audit_digest"] if latest else "0" * 64
        value = {
            "audit_sequence": sequence,
            "proposal_id": proposal_id,
            "action": action,
            "actor_id": actor_id,
            "evidence_digest": evidence_digest,
            "previous_digest": previous,
            "recorded_at": recorded_at.isoformat(),
        }
        self._connection.execute(
            """
            INSERT INTO synthetic_implementation_review_audit (
                audit_sequence, proposal_id, action, actor_id, evidence_digest,
                previous_digest, audit_digest, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sequence,
                proposal_id,
                action,
                actor_id,
                evidence_digest,
                previous,
                canonical_digest(value),
                recorded_at.isoformat(),
            ),
        )

    @staticmethod
    def _proposal_from_payload(payload: object) -> SyntheticImplementationProposalDraft:
        if not isinstance(payload, dict):
            raise GovernanceRejected("stored implementation proposal object required")
        proposal = SyntheticImplementationProposalDraft(
            int(payload["sequence"]),
            str(payload["proposal_id"]),
            str(payload["source_receipt_id"]),
            str(payload["source_receipt_digest"]),
            str(payload["source_assessment_id"]),
            str(payload["source_packet_id"]),
            str(payload["operator_id"]),
            SyntheticOperatorDecision(str(payload["decision"])),
            tuple(str(value) for value in payload["draft_scopes"]),
            tuple(str(value) for value in payload["required_checks"]),
            datetime.fromisoformat(str(payload["drafted_at"])),
            str(payload["previous_digest"]),
            str(payload["proposal_digest"]),
            str(payload["state"]),
            bool(payload["eternian_review_required"]),
            bool(payload["actual_operator_decision_recorded"]),
            bool(payload["code_change_allowed"]),
            bool(payload["automatic_application_allowed"]),
            bool(payload["execution_allowed"]),
            bool(payload["money_movement_allowed"]),
            bool(payload["production_activation_allowed"]),
        )
        return proposal

    @classmethod
    def _record_from_row(cls, row: sqlite3.Row) -> SyntheticImplementationReviewRecord:
        try:
            payload = json.loads(row["proposal_json"])
            proposal = cls._proposal_from_payload(payload)
            if (
                proposal.proposal_id != row["proposal_id"]
                or proposal.proposal_digest != row["proposal_digest"]
                or proposal.source_receipt_id != row["source_receipt_id"]
                or proposal.source_receipt_digest != row["source_receipt_digest"]
                or proposal.source_packet_id != row["source_packet_id"]
            ):
                raise GovernanceRejected("stored implementation proposal binding is invalid")
            decision = (
                ImplementationProposalReviewDecision(row["review_decision"])
                if row["review_decision"] is not None
                else None
            )
            return SyntheticImplementationReviewRecord(
                proposal,
                ImplementationProposalReviewState(row["state"]),
                datetime.fromisoformat(row["submitted_at"]),
                row["review_id"],
                row["reviewer_id"],
                decision,
                row["findings_digest"],
                datetime.fromisoformat(row["reviewed_at"])
                if row["reviewed_at"] is not None
                else None,
                row["review_digest"],
                bool(row["actual_operator_decision_recorded"]),
                bool(row["code_change_allowed"]),
                bool(row["automatic_application_allowed"]),
                bool(row["execution_allowed"]),
                bool(row["production_activation_allowed"]),
            )
        except (GovernanceRejected, KeyError, TypeError, ValueError) as exc:
            raise GovernanceRejected("stored implementation review is invalid") from exc

    def _get_record(self, proposal_id: str) -> SyntheticImplementationReviewRecord:
        row = self._connection.execute(
            "SELECT * FROM synthetic_implementation_review_records WHERE proposal_id = ?",
            (proposal_id,),
        ).fetchone()
        if row is None:
            raise GovernanceRejected("unknown implementation proposal")
        return self._record_from_row(row)

    def get(self, proposal_id: str) -> SyntheticImplementationReviewRecord:
        with self._lock:
            return self._get_record(proposal_id)

    def ready_source(self, proposal_id: str) -> SyntheticImplementationReviewRecord:
        with self._lock:
            if not self.verify_audit_chain() or not self.verify_record_bindings():
                raise GovernanceRejected("implementation review docket is invalid")
            record = self._get_record(proposal_id)
            if record.state is not ImplementationProposalReviewState.READY_FOR_SYNTHETIC_PATCH_SHADOW:
                raise GovernanceRejected("implementation proposal is not shadow-ready")
            return record

    def verify_audit_chain(self) -> bool:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM synthetic_implementation_review_audit "
                "ORDER BY audit_sequence"
            ).fetchall()
            previous = "0" * 64
            for sequence, row in enumerate(rows, start=1):
                value = {
                    "audit_sequence": sequence,
                    "proposal_id": row["proposal_id"],
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
                "SELECT * FROM synthetic_implementation_review_records "
                "ORDER BY proposal_id"
            ).fetchall()
            audits = self._connection.execute(
                "SELECT * FROM synthetic_implementation_review_audit "
                "ORDER BY audit_sequence"
            ).fetchall()
            audits_by_key = {(row["proposal_id"], row["action"]): row for row in audits}
            try:
                for row in rows:
                    record = self._record_from_row(row)
                    submitted = audits_by_key.get((row["proposal_id"], "SUBMITTED"))
                    if (
                        submitted is None
                        or submitted["actor_id"]
                        != "synthetic:system:implementation-review-docket"
                        or submitted["evidence_digest"] != row["proposal_digest"]
                        or submitted["recorded_at"] != row["submitted_at"]
                    ):
                        return False
                    reviewed = audits_by_key.get(
                        (row["proposal_id"], "ETERNIAN_REVIEWED")
                    )
                    if record.review_id is None:
                        if reviewed is not None:
                            return False
                    elif (
                        reviewed is None
                        or reviewed["actor_id"] != record.reviewer_id
                        or reviewed["evidence_digest"] != record.review_digest
                        or reviewed["recorded_at"] != row["reviewed_at"]
                    ):
                        return False
            except (GovernanceRejected, KeyError, TypeError, ValueError):
                return False
            expected_audits = sum(1 if row["review_id"] is None else 2 for row in rows)
            return len(audits) == expected_audits

    def evidence(self) -> dict[str, object]:
        with self._lock:
            counts = {state.value: 0 for state in ImplementationProposalReviewState}
            record_digests = []
            for row in self._connection.execute(
                "SELECT * FROM synthetic_implementation_review_records "
                "ORDER BY proposal_id"
            ):
                counts[row["state"]] += 1
                record = self._record_from_row(row)
                record_digests.append(
                    canonical_digest(
                        {
                            "proposal_digest": record.proposal.proposal_digest,
                            "state": record.state.value,
                            "submitted_at": record.submitted_at.isoformat(),
                            "review_digest": record.review_digest,
                        }
                    )
                )
            latest = self._connection.execute(
                "SELECT audit_digest FROM synthetic_implementation_review_audit "
                "ORDER BY audit_sequence DESC LIMIT 1"
            ).fetchone()
            value = {
                "schema": "nurion.pg.synthetic-implementation-review-evidence.v1",
                "database_engine": "SQLite",
                "schema_version": IMPLEMENTATION_REVIEW_SCHEMA_VERSION,
                "schema_digest": canonical_digest(IMPLEMENTATION_REVIEW_SCHEMA_SQL),
                "metadata_valid": self.verify_metadata(),
                "state_counts": counts,
                "record_digests": record_digests,
                "audit_head_digest": latest["audit_digest"] if latest else "0" * 64,
                "audit_chain_valid": self.verify_audit_chain(),
                "record_bindings_valid": self.verify_record_bindings(),
                "maximum_state": MAXIMUM_REVIEW_STATE,
                "actual_operator_decision_recording_method_present": False,
                "code_change_method_present": False,
                "application_method_present": False,
                "safety_baseline_relaxation_method_present": False,
                "execution_method_present": False,
                "money_movement_executed": False,
                "production_activation_allowed": False,
            }
            return {**value, "report_digest": canonical_digest(value)}
