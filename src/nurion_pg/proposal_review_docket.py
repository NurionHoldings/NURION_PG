"""Durable synthetic ARKAON proposal docket capped at operator decision readiness."""

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
from .webhook_command_proposals import (
    ProposalDecision,
    SyntheticWebhookProposalBook,
    WebhookCommandProposal,
)


DOCKET_SCHEMA_VERSION = 1
ARKAON_PROPOSER_ID = "synthetic:arkaon:NURION_PG"
DOCKET_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS synthetic_docket_metadata (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    schema_version INTEGER NOT NULL CHECK (schema_version = 1),
    synthetic_only INTEGER NOT NULL CHECK (synthetic_only = 1)
);
CREATE TABLE IF NOT EXISTS synthetic_proposal_dockets (
    proposal_id TEXT PRIMARY KEY,
    source_event_id TEXT NOT NULL UNIQUE,
    proposal_digest TEXT NOT NULL UNIQUE,
    source_assessment_digest TEXT NOT NULL UNIQUE,
    proposal_json TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN (
        'PENDING_ETERNIAN_REVIEW',
        'READY_FOR_OPERATOR_DECISION',
        'HELD',
        'REJECTED'
    )),
    submitted_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    proposer_id TEXT NOT NULL CHECK (proposer_id = 'synthetic:arkaon:NURION_PG'),
    automatic_review_allowed INTEGER NOT NULL DEFAULT 0 CHECK (automatic_review_allowed = 0),
    operator_approval_recorded INTEGER NOT NULL DEFAULT 0 CHECK (operator_approval_recorded = 0),
    execution_allowed INTEGER NOT NULL DEFAULT 0 CHECK (execution_allowed = 0)
);
CREATE TABLE IF NOT EXISTS synthetic_eternian_reviews (
    review_id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL UNIQUE REFERENCES synthetic_proposal_dockets(proposal_id),
    reviewer_id TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('PASS', 'HOLD', 'REJECT')),
    findings_digest TEXT NOT NULL,
    reviewed_at TEXT NOT NULL,
    review_digest TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS synthetic_docket_audit (
    audit_sequence INTEGER PRIMARY KEY,
    proposal_id TEXT NOT NULL,
    action TEXT NOT NULL,
    state_before TEXT,
    state_after TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    evidence_digest TEXT NOT NULL,
    previous_digest TEXT NOT NULL,
    audit_digest TEXT NOT NULL UNIQUE,
    recorded_at TEXT NOT NULL
);
""".strip()


class DocketState(StrEnum):
    PENDING_ETERNIAN_REVIEW = "PENDING_ETERNIAN_REVIEW"
    READY_FOR_OPERATOR_DECISION = "READY_FOR_OPERATOR_DECISION"
    HELD = "HELD"
    REJECTED = "REJECTED"


class EternianReviewDecision(StrEnum):
    PASS = "PASS"
    HOLD = "HOLD"
    REJECT = "REJECT"


@dataclass(frozen=True)
class ProposalDocketRecord:
    proposal_id: str
    source_event_id: str
    proposal_digest: str
    source_assessment_digest: str
    state: DocketState
    submitted_at: datetime
    updated_at: datetime
    proposer_id: str = ARKAON_PROPOSER_ID
    automatic_review_allowed: bool = False
    operator_approval_recorded: bool = False
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if (
            not self.proposal_id.startswith("synthetic:proposal:")
            or not self.source_event_id.startswith("synthetic:")
            or self.proposer_id != ARKAON_PROPOSER_ID
            or self.submitted_at.tzinfo is None
            or self.updated_at.tzinfo is None
            or self.updated_at < self.submitted_at
            or self.automatic_review_allowed
            or self.operator_approval_recorded
            or self.execution_allowed
        ):
            raise GovernanceRejected("valid non-executable synthetic docket record required")
        for digest in (self.proposal_digest, self.source_assessment_digest):
            if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                raise GovernanceRejected("valid docket evidence digests required")


class SyntheticProposalReviewDocket:
    """Persists ARKAON proposals and Eternian review, never operator approval."""

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
        self._connection.execute("PRAGMA foreign_keys = ON")
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
            raise GovernanceRejected("synthetic SQLite docket target required")

    def _initialize_schema(self) -> None:
        with self._lock:
            self._connection.executescript(DOCKET_SCHEMA_SQL)
            self._connection.execute(
                """
                INSERT OR IGNORE INTO synthetic_docket_metadata
                    (singleton, schema_version, synthetic_only)
                VALUES (1, ?, 1)
                """,
                (DOCKET_SCHEMA_VERSION,),
            )
            row = self._connection.execute(
                "SELECT schema_version, synthetic_only FROM synthetic_docket_metadata WHERE singleton = 1"
            ).fetchone()
            if (
                row is None
                or row["schema_version"] != DOCKET_SCHEMA_VERSION
                or row["synthetic_only"] != 1
            ):
                raise GovernanceRejected("unsupported or non-synthetic docket schema")

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
        book: SyntheticWebhookProposalBook,
        source_event_id: str,
        *,
        submitted_at: datetime,
    ) -> ProposalDocketRecord:
        if submitted_at.tzinfo is None:
            raise GovernanceRejected("timezone-aware docket submission required")
        if not book.verify_assessment_chain():
            raise GovernanceRejected("proposal assessment chain is invalid")
        matches = [
            assessment
            for assessment in book.assessments
            if assessment.source_event_id == source_event_id
        ]
        if len(matches) != 1:
            raise GovernanceRejected("one proposal assessment source required")
        assessment = matches[0]
        if (
            assessment.decision is not ProposalDecision.PROPOSED_FOR_HUMAN_REVIEW
            or assessment.proposal is None
        ):
            raise GovernanceRejected("reviewable proposal assessment required")
        proposal = assessment.proposal
        self._validate_proposal(proposal)
        if submitted_at < proposal.created_at:
            raise GovernanceRejected("docket submission cannot predate proposal")

        with self._lock:
            try:
                with self._transaction():
                    existing = self._connection.execute(
                        "SELECT * FROM synthetic_proposal_dockets WHERE proposal_id = ?",
                        (proposal.proposal_id,),
                    ).fetchone()
                    if existing is not None:
                        if (
                            existing["proposal_digest"] != proposal.proposal_digest
                            or existing["source_assessment_digest"]
                            != assessment.assessment_digest
                        ):
                            raise GovernanceRejected("proposal docket identity collision")
                        return self._record_from_row(existing)
                    payload = {
                        **proposal.digest_value(),
                        "proposal_digest": proposal.proposal_digest,
                    }
                    self._connection.execute(
                        """
                        INSERT INTO synthetic_proposal_dockets (
                            proposal_id, source_event_id, proposal_digest,
                            source_assessment_digest, proposal_json, state,
                            submitted_at, updated_at, proposer_id,
                            automatic_review_allowed, operator_approval_recorded,
                            execution_allowed
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0)
                        """,
                        (
                            proposal.proposal_id,
                            proposal.source_event_id,
                            proposal.proposal_digest,
                            assessment.assessment_digest,
                            json.dumps(
                                payload,
                                ensure_ascii=False,
                                sort_keys=True,
                                separators=(",", ":"),
                            ),
                            DocketState.PENDING_ETERNIAN_REVIEW.value,
                            submitted_at.isoformat(),
                            submitted_at.isoformat(),
                            ARKAON_PROPOSER_ID,
                        ),
                    )
                    self._append_audit(
                        proposal_id=proposal.proposal_id,
                        action="ARKAON_PROPOSAL_SUBMITTED",
                        state_before=None,
                        state_after=DocketState.PENDING_ETERNIAN_REVIEW,
                        actor_id=ARKAON_PROPOSER_ID,
                        evidence_digest=assessment.assessment_digest,
                        recorded_at=submitted_at,
                    )
                    return self._get_record(proposal.proposal_id)
            except sqlite3.Error as exc:
                raise GovernanceRejected("synthetic docket transaction failed") from exc

    @staticmethod
    def _validate_proposal(proposal: WebhookCommandProposal) -> None:
        if (
            proposal.proposal_digest != canonical_digest(proposal.digest_value())
            or not proposal.review_required
            or proposal.automatic_application_allowed
            or proposal.execution_allowed
            or proposal.operator_approval_recorded
        ):
            raise GovernanceRejected("intact non-executable proposal required")

    def record_eternian_review(
        self,
        proposal_id: str,
        *,
        review_id: str,
        reviewer_id: str,
        decision: EternianReviewDecision,
        findings_digest: str,
        reviewed_at: datetime,
    ) -> ProposalDocketRecord:
        if (
            not review_id.startswith("synthetic:review:")
            or not reviewer_id.startswith("synthetic:eternian-reviewer:")
            or len(review_id) <= len("synthetic:review:")
            or len(reviewer_id) <= len("synthetic:eternian-reviewer:")
            or reviewer_id == ARKAON_PROPOSER_ID
            or not isinstance(decision, EternianReviewDecision)
            or reviewed_at.tzinfo is None
            or len(findings_digest) != 64
            or any(char not in "0123456789abcdef" for char in findings_digest)
        ):
            raise GovernanceRejected("complete independent synthetic Eternian review required")
        review_value = {
            "review_id": review_id,
            "proposal_id": proposal_id,
            "reviewer_id": reviewer_id,
            "decision": decision.value,
            "findings_digest": findings_digest,
            "reviewed_at": reviewed_at.isoformat(),
        }
        review_digest = canonical_digest(review_value)
        target = {
            EternianReviewDecision.PASS: DocketState.READY_FOR_OPERATOR_DECISION,
            EternianReviewDecision.HOLD: DocketState.HELD,
            EternianReviewDecision.REJECT: DocketState.REJECTED,
        }[decision]
        with self._lock:
            try:
                with self._transaction():
                    existing_review = self._connection.execute(
                        "SELECT * FROM synthetic_eternian_reviews WHERE review_id = ?",
                        (review_id,),
                    ).fetchone()
                    if existing_review is not None:
                        if existing_review["review_digest"] != review_digest:
                            raise GovernanceRejected("review idempotency payload mismatch")
                        return self._get_record(proposal_id)
                    docket = self._connection.execute(
                        "SELECT * FROM synthetic_proposal_dockets WHERE proposal_id = ?",
                        (proposal_id,),
                    ).fetchone()
                    if docket is None:
                        raise GovernanceRejected("unknown proposal docket")
                    if reviewed_at < datetime.fromisoformat(docket["submitted_at"]):
                        raise GovernanceRejected("review cannot predate docket submission")
                    if docket["state"] != DocketState.PENDING_ETERNIAN_REVIEW.value:
                        raise GovernanceRejected("proposal is not pending Eternian review")
                    other = self._connection.execute(
                        "SELECT review_id FROM synthetic_eternian_reviews WHERE proposal_id = ?",
                        (proposal_id,),
                    ).fetchone()
                    if other is not None:
                        raise GovernanceRejected("proposal already has an Eternian review")
                    self._connection.execute(
                        """
                        INSERT INTO synthetic_eternian_reviews (
                            review_id, proposal_id, reviewer_id, decision,
                            findings_digest, reviewed_at, review_digest
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            review_id,
                            proposal_id,
                            reviewer_id,
                            decision.value,
                            findings_digest,
                            reviewed_at.isoformat(),
                            review_digest,
                        ),
                    )
                    self._connection.execute(
                        """
                        UPDATE synthetic_proposal_dockets
                        SET state = ?, updated_at = ?
                        WHERE proposal_id = ?
                        """,
                        (target.value, reviewed_at.isoformat(), proposal_id),
                    )
                    self._append_audit(
                        proposal_id=proposal_id,
                        action=f"ETERNIAN_REVIEW_{decision.value}",
                        state_before=DocketState.PENDING_ETERNIAN_REVIEW,
                        state_after=target,
                        actor_id=reviewer_id,
                        evidence_digest=review_digest,
                        recorded_at=reviewed_at,
                    )
                    return self._get_record(proposal_id)
            except sqlite3.Error as exc:
                raise GovernanceRejected("synthetic docket transaction failed") from exc

    def _append_audit(
        self,
        *,
        proposal_id: str,
        action: str,
        state_before: DocketState | None,
        state_after: DocketState,
        actor_id: str,
        evidence_digest: str,
        recorded_at: datetime,
    ) -> None:
        latest = self._connection.execute(
            """
            SELECT audit_sequence, audit_digest
            FROM synthetic_docket_audit
            ORDER BY audit_sequence DESC LIMIT 1
            """
        ).fetchone()
        sequence = (latest["audit_sequence"] if latest is not None else 0) + 1
        previous = latest["audit_digest"] if latest is not None else "0" * 64
        value = {
            "audit_sequence": sequence,
            "proposal_id": proposal_id,
            "action": action,
            "state_before": state_before.value if state_before is not None else None,
            "state_after": state_after.value,
            "actor_id": actor_id,
            "evidence_digest": evidence_digest,
            "previous_digest": previous,
            "recorded_at": recorded_at.isoformat(),
        }
        self._connection.execute(
            """
            INSERT INTO synthetic_docket_audit (
                audit_sequence, proposal_id, action, state_before, state_after,
                actor_id, evidence_digest, previous_digest, audit_digest,
                recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sequence,
                proposal_id,
                action,
                state_before.value if state_before is not None else None,
                state_after.value,
                actor_id,
                evidence_digest,
                previous,
                canonical_digest(value),
                recorded_at.isoformat(),
            ),
        )

    def _get_record(self, proposal_id: str) -> ProposalDocketRecord:
        row = self._connection.execute(
            "SELECT * FROM synthetic_proposal_dockets WHERE proposal_id = ?",
            (proposal_id,),
        ).fetchone()
        if row is None:
            raise GovernanceRejected("unknown proposal docket")
        return self._record_from_row(row)

    @staticmethod
    def _record_from_row(row: sqlite3.Row) -> ProposalDocketRecord:
        try:
            payload = json.loads(row["proposal_json"])
        except (TypeError, ValueError) as exc:
            raise GovernanceRejected("stored proposal JSON is corrupt") from exc
        if not isinstance(payload, dict):
            raise GovernanceRejected("stored proposal object required")
        stored_digest = payload.pop("proposal_digest", None)
        if (
            stored_digest != row["proposal_digest"]
            or canonical_digest(payload) != row["proposal_digest"]
            or payload.get("proposal_id") != row["proposal_id"]
            or payload.get("source_event_id") != row["source_event_id"]
        ):
            raise GovernanceRejected("stored proposal binding is invalid")
        return ProposalDocketRecord(
            row["proposal_id"],
            row["source_event_id"],
            row["proposal_digest"],
            row["source_assessment_digest"],
            DocketState(row["state"]),
            datetime.fromisoformat(row["submitted_at"]),
            datetime.fromisoformat(row["updated_at"]),
            row["proposer_id"],
            bool(row["automatic_review_allowed"]),
            bool(row["operator_approval_recorded"]),
            bool(row["execution_allowed"]),
        )

    def get(self, proposal_id: str) -> ProposalDocketRecord:
        with self._lock:
            return self._get_record(proposal_id)

    def verify_audit_chain(self) -> bool:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM synthetic_docket_audit ORDER BY audit_sequence"
            ).fetchall()
            previous = "0" * 64
            for sequence, row in enumerate(rows, start=1):
                value = {
                    "audit_sequence": sequence,
                    "proposal_id": row["proposal_id"],
                    "action": row["action"],
                    "state_before": row["state_before"],
                    "state_after": row["state_after"],
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
            dockets = self._connection.execute(
                "SELECT * FROM synthetic_proposal_dockets ORDER BY proposal_id"
            ).fetchall()
            reviews = self._connection.execute(
                "SELECT * FROM synthetic_eternian_reviews ORDER BY review_id"
            ).fetchall()
            audits = self._connection.execute(
                "SELECT * FROM synthetic_docket_audit ORDER BY audit_sequence"
            ).fetchall()
            try:
                for docket in dockets:
                    self._record_from_row(docket)
            except (GovernanceRejected, TypeError, ValueError):
                return False
            if len(audits) != len(dockets) + len(reviews):
                return False
            audit_by_action = {
                (row["proposal_id"], row["action"]): row for row in audits
            }
            review_by_proposal = {row["proposal_id"]: row for row in reviews}
            for docket in dockets:
                submitted = audit_by_action.get(
                    (docket["proposal_id"], "ARKAON_PROPOSAL_SUBMITTED")
                )
                if (
                    submitted is None
                    or submitted["state_before"] is not None
                    or submitted["state_after"]
                    != DocketState.PENDING_ETERNIAN_REVIEW.value
                    or submitted["actor_id"] != ARKAON_PROPOSER_ID
                    or submitted["evidence_digest"]
                    != docket["source_assessment_digest"]
                    or submitted["recorded_at"] != docket["submitted_at"]
                ):
                    return False
                review = review_by_proposal.get(docket["proposal_id"])
                if review is None:
                    if docket["state"] != DocketState.PENDING_ETERNIAN_REVIEW.value:
                        return False
                    continue
                review_value = {
                    "review_id": review["review_id"],
                    "proposal_id": review["proposal_id"],
                    "reviewer_id": review["reviewer_id"],
                    "decision": review["decision"],
                    "findings_digest": review["findings_digest"],
                    "reviewed_at": review["reviewed_at"],
                }
                if canonical_digest(review_value) != review["review_digest"]:
                    return False
                target = {
                    EternianReviewDecision.PASS.value: DocketState.READY_FOR_OPERATOR_DECISION,
                    EternianReviewDecision.HOLD.value: DocketState.HELD,
                    EternianReviewDecision.REJECT.value: DocketState.REJECTED,
                }.get(review["decision"])
                if target is None or docket["state"] != target.value:
                    return False
                audit = audit_by_action.get(
                    (docket["proposal_id"], f"ETERNIAN_REVIEW_{review['decision']}")
                )
                if (
                    audit is None
                    or audit["state_before"]
                    != DocketState.PENDING_ETERNIAN_REVIEW.value
                    or audit["state_after"] != target.value
                    or audit["actor_id"] != review["reviewer_id"]
                    or audit["evidence_digest"] != review["review_digest"]
                    or audit["recorded_at"] != review["reviewed_at"]
                    or docket["updated_at"] != review["reviewed_at"]
                ):
                    return False
            return True

    def evidence(self) -> dict[str, object]:
        with self._lock:
            counts = {state.value: 0 for state in DocketState}
            for row in self._connection.execute(
                "SELECT state, COUNT(*) AS count FROM synthetic_proposal_dockets GROUP BY state"
            ):
                counts[row["state"]] = row["count"]
            value = {
                "schema": "nurion.pg.synthetic-proposal-review-docket-evidence.v1",
                "database_engine": "SQLite",
                "schema_version": DOCKET_SCHEMA_VERSION,
                "schema_digest": canonical_digest(DOCKET_SCHEMA_SQL),
                "state_counts": counts,
                "audit_chain_valid": self.verify_audit_chain(),
                "record_bindings_valid": self.verify_record_bindings(),
                "maximum_automatic_state": DocketState.READY_FOR_OPERATOR_DECISION.value,
                "proposer_reviewer_separation_required": True,
                "operator_decision_method_present": False,
                "execution_method_present": False,
                "operator_approval_automatically_recorded": False,
                "money_movement_executed": False,
                "production_activation_allowed": False,
            }
            return {**value, "report_digest": canonical_digest(value)}
