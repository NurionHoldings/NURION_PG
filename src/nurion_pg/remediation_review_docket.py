"""Durable Eternian review docket for non-executable remediation proposals."""

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
from .reconciliation_remediation_proposals import (
    RemediationActionType,
    RemediationPlanItem,
    RemediationProposalDecision,
    ReconciliationRemediationProposal,
    SyntheticRemediationProposalBook,
)


REMEDIATION_DOCKET_SCHEMA_VERSION = 1
ARKAON_REMEDIATION_PROPOSER_ID = "synthetic:arkaon:NURION_PG:remediation-proposer"
REMEDIATION_DOCKET_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS synthetic_remediation_docket_metadata (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    schema_version INTEGER NOT NULL CHECK (schema_version = 1),
    synthetic_only INTEGER NOT NULL CHECK (synthetic_only = 1)
);
CREATE TABLE IF NOT EXISTS synthetic_remediation_dockets (
    proposal_id TEXT PRIMARY KEY,
    source_case_id TEXT NOT NULL UNIQUE,
    proposal_digest TEXT NOT NULL UNIQUE,
    source_assessment_digest TEXT NOT NULL UNIQUE,
    proposal_json TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN (
        'PENDING_ETERNIAN_REVIEW',
        'READY_FOR_SYNTHETIC_SHADOW',
        'HELD',
        'REJECTED'
    )),
    submitted_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    proposer_id TEXT NOT NULL
        CHECK (proposer_id = 'synthetic:arkaon:NURION_PG:remediation-proposer'),
    automatic_review_allowed INTEGER NOT NULL DEFAULT 0
        CHECK (automatic_review_allowed = 0),
    code_change_allowed INTEGER NOT NULL DEFAULT 0 CHECK (code_change_allowed = 0),
    operator_approval_recorded INTEGER NOT NULL DEFAULT 0
        CHECK (operator_approval_recorded = 0),
    execution_allowed INTEGER NOT NULL DEFAULT 0 CHECK (execution_allowed = 0)
);
CREATE TABLE IF NOT EXISTS synthetic_remediation_reviews (
    review_id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL UNIQUE REFERENCES synthetic_remediation_dockets(proposal_id),
    reviewer_id TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('PASS', 'HOLD', 'REJECT')),
    findings_digest TEXT NOT NULL,
    reviewed_at TEXT NOT NULL,
    review_digest TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS synthetic_remediation_docket_audit (
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


class RemediationDocketState(StrEnum):
    PENDING_ETERNIAN_REVIEW = "PENDING_ETERNIAN_REVIEW"
    READY_FOR_SYNTHETIC_SHADOW = "READY_FOR_SYNTHETIC_SHADOW"
    HELD = "HELD"
    REJECTED = "REJECTED"


class RemediationReviewDecision(StrEnum):
    PASS = "PASS"
    HOLD = "HOLD"
    REJECT = "REJECT"


@dataclass(frozen=True)
class RemediationDocketRecord:
    proposal_id: str
    source_case_id: str
    proposal_digest: str
    source_assessment_digest: str
    state: RemediationDocketState
    submitted_at: datetime
    updated_at: datetime
    proposer_id: str = ARKAON_REMEDIATION_PROPOSER_ID
    automatic_review_allowed: bool = False
    code_change_allowed: bool = False
    operator_approval_recorded: bool = False
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if (
            not self.proposal_id.startswith("synthetic:remediation-proposal:")
            or not self.source_case_id.startswith("synthetic:reconciliation-case:")
            or not _valid_digest(self.proposal_digest)
            or not _valid_digest(self.source_assessment_digest)
            or self.submitted_at.tzinfo is None
            or self.updated_at.tzinfo is None
            or self.updated_at < self.submitted_at
            or self.proposer_id != ARKAON_REMEDIATION_PROPOSER_ID
            or self.automatic_review_allowed
            or self.code_change_allowed
            or self.operator_approval_recorded
            or self.execution_allowed
        ):
            raise GovernanceRejected("valid non-executable remediation docket record required")


@dataclass(frozen=True)
class ReadyRemediationProposalSource:
    proposal_id: str
    source_case_id: str
    proposal_digest: str
    review_digest: str
    proposal_json: str
    reviewed_at: datetime

    def __post_init__(self) -> None:
        if (
            not self.proposal_id.startswith("synthetic:remediation-proposal:")
            or not self.source_case_id.startswith("synthetic:reconciliation-case:")
            or not _valid_digest(self.proposal_digest)
            or not _valid_digest(self.review_digest)
            or not self.proposal_json
            or self.reviewed_at.tzinfo is None
        ):
            raise GovernanceRejected("complete ready remediation proposal source required")


def _valid_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


class SyntheticRemediationReviewDocket:
    """Persists remediation proposals and review, never code changes or execution."""

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
            raise GovernanceRejected("synthetic SQLite remediation docket target required")

    def _initialize_schema(self) -> None:
        with self._lock:
            self._connection.executescript(REMEDIATION_DOCKET_SCHEMA_SQL)
            self._connection.execute(
                """
                INSERT OR IGNORE INTO synthetic_remediation_docket_metadata
                    (singleton, schema_version, synthetic_only) VALUES (1, ?, 1)
                """,
                (REMEDIATION_DOCKET_SCHEMA_VERSION,),
            )
            row = self._connection.execute(
                """
                SELECT schema_version, synthetic_only
                FROM synthetic_remediation_docket_metadata WHERE singleton = 1
                """
            ).fetchone()
            if (
                row is None
                or row["schema_version"] != REMEDIATION_DOCKET_SCHEMA_VERSION
                or row["synthetic_only"] != 1
            ):
                raise GovernanceRejected("unsupported or non-synthetic remediation docket")

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
        book: SyntheticRemediationProposalBook,
        source_case_id: str,
        *,
        submitted_at: datetime,
    ) -> RemediationDocketRecord:
        if submitted_at.tzinfo is None:
            raise GovernanceRejected("timezone-aware remediation docket submission required")
        if not book.verify_assessment_chain():
            raise GovernanceRejected("remediation proposal assessment chain is invalid")
        matches = [
            assessment
            for assessment in book.assessments
            if assessment.source_case_id == source_case_id
        ]
        if len(matches) != 1:
            raise GovernanceRejected("one remediation proposal assessment source required")
        assessment = matches[0]
        if (
            assessment.decision
            is not RemediationProposalDecision.PROPOSED_FOR_ETERNIAN_REVIEW
            or assessment.proposal is None
        ):
            raise GovernanceRejected("reviewable remediation proposal assessment required")
        proposal = assessment.proposal
        self._validate_proposal(proposal)
        if submitted_at < proposal.created_at:
            raise GovernanceRejected("remediation docket cannot predate proposal")
        payload = self._proposal_payload(proposal)
        with self._lock:
            try:
                with self._transaction():
                    existing = self._connection.execute(
                        "SELECT * FROM synthetic_remediation_dockets WHERE proposal_id = ?",
                        (proposal.proposal_id,),
                    ).fetchone()
                    if existing is not None:
                        if (
                            existing["proposal_digest"] != proposal.proposal_digest
                            or existing["source_assessment_digest"]
                            != assessment.assessment_digest
                        ):
                            raise GovernanceRejected("remediation docket identity collision")
                        if (
                            not self.verify_audit_chain()
                            or not self.verify_record_bindings()
                        ):
                            raise GovernanceRejected(
                                "existing remediation docket evidence is invalid"
                            )
                        return self._record_from_row(existing)
                    self._connection.execute(
                        """
                        INSERT INTO synthetic_remediation_dockets (
                            proposal_id, source_case_id, proposal_digest,
                            source_assessment_digest, proposal_json, state,
                            submitted_at, updated_at, proposer_id,
                            automatic_review_allowed, code_change_allowed,
                            operator_approval_recorded, execution_allowed
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0)
                        """,
                        (
                            proposal.proposal_id,
                            proposal.source_case_id,
                            proposal.proposal_digest,
                            assessment.assessment_digest,
                            json.dumps(
                                payload,
                                ensure_ascii=False,
                                sort_keys=True,
                                separators=(",", ":"),
                            ),
                            RemediationDocketState.PENDING_ETERNIAN_REVIEW.value,
                            submitted_at.isoformat(),
                            submitted_at.isoformat(),
                            ARKAON_REMEDIATION_PROPOSER_ID,
                        ),
                    )
                    self._append_audit(
                        proposal_id=proposal.proposal_id,
                        action="ARKAON_REMEDIATION_PROPOSAL_SUBMITTED",
                        state_before=None,
                        state_after=RemediationDocketState.PENDING_ETERNIAN_REVIEW,
                        actor_id=ARKAON_REMEDIATION_PROPOSER_ID,
                        evidence_digest=assessment.assessment_digest,
                        recorded_at=submitted_at,
                    )
                    return self._get_record(proposal.proposal_id)
            except sqlite3.Error as exc:
                raise GovernanceRejected("synthetic remediation docket transaction failed") from exc

    @staticmethod
    def _validate_proposal(proposal: ReconciliationRemediationProposal) -> None:
        if (
            proposal.proposal_digest != canonical_digest(proposal.digest_value())
            or not proposal.review_required
            or proposal.code_change_allowed
            or proposal.automatic_application_allowed
            or proposal.safety_baseline_relaxation_allowed
            or proposal.operator_approval_recorded
            or proposal.execution_allowed
            or not proposal.plan_items
        ):
            raise GovernanceRejected("intact non-executable remediation proposal required")
        for item in proposal.plan_items:
            try:
                RemediationPlanItem(
                    item.ordinal,
                    item.finding_code,
                    item.subject_id,
                    item.action_type,
                    item.allowed_scopes,
                    item.required_checks,
                    item.item_digest,
                    item.code_change_allowed,
                    item.production_access_allowed,
                )
            except GovernanceRejected as exc:
                raise GovernanceRejected("invalid remediation plan item") from exc

    @staticmethod
    def _proposal_payload(proposal: ReconciliationRemediationProposal) -> dict[str, object]:
        return {
            **proposal.digest_value(),
            "plan_items": [
                {**item.digest_value(), "item_digest": item.item_digest}
                for item in proposal.plan_items
            ],
            "proposal_digest": proposal.proposal_digest,
        }

    def record_eternian_review(
        self,
        proposal_id: str,
        *,
        review_id: str,
        reviewer_id: str,
        decision: RemediationReviewDecision,
        findings_digest: str,
        reviewed_at: datetime,
    ) -> RemediationDocketRecord:
        if (
            not review_id.startswith("synthetic:remediation-review:")
            or len(review_id) <= len("synthetic:remediation-review:")
            or not reviewer_id.startswith("synthetic:eternian-reviewer:")
            or len(reviewer_id) <= len("synthetic:eternian-reviewer:")
            or reviewer_id == ARKAON_REMEDIATION_PROPOSER_ID
            or not isinstance(decision, RemediationReviewDecision)
            or not _valid_digest(findings_digest)
            or reviewed_at.tzinfo is None
        ):
            raise GovernanceRejected("complete independent remediation review required")
        value = {
            "review_id": review_id,
            "proposal_id": proposal_id,
            "reviewer_id": reviewer_id,
            "decision": decision.value,
            "findings_digest": findings_digest,
            "reviewed_at": reviewed_at.isoformat(),
        }
        review_digest = canonical_digest(value)
        target = {
            RemediationReviewDecision.PASS: RemediationDocketState.READY_FOR_SYNTHETIC_SHADOW,
            RemediationReviewDecision.HOLD: RemediationDocketState.HELD,
            RemediationReviewDecision.REJECT: RemediationDocketState.REJECTED,
        }[decision]
        with self._lock:
            try:
                with self._transaction():
                    existing = self._connection.execute(
                        "SELECT * FROM synthetic_remediation_reviews WHERE review_id = ?",
                        (review_id,),
                    ).fetchone()
                    if existing is not None:
                        if existing["review_digest"] != review_digest:
                            raise GovernanceRejected("remediation review idempotency mismatch")
                        return self._get_record(proposal_id)
                    docket = self._connection.execute(
                        "SELECT * FROM synthetic_remediation_dockets WHERE proposal_id = ?",
                        (proposal_id,),
                    ).fetchone()
                    if docket is None:
                        raise GovernanceRejected("unknown remediation proposal docket")
                    if (
                        not self.verify_audit_chain()
                        or not self.verify_record_bindings()
                    ):
                        raise GovernanceRejected(
                            "remediation docket evidence is invalid before review"
                        )
                    if reviewed_at < datetime.fromisoformat(docket["submitted_at"]):
                        raise GovernanceRejected("remediation review cannot predate submission")
                    if docket["state"] != RemediationDocketState.PENDING_ETERNIAN_REVIEW.value:
                        raise GovernanceRejected("remediation proposal is not pending review")
                    self._connection.execute(
                        """
                        INSERT INTO synthetic_remediation_reviews (
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
                        UPDATE synthetic_remediation_dockets SET state = ?, updated_at = ?
                        WHERE proposal_id = ?
                        """,
                        (target.value, reviewed_at.isoformat(), proposal_id),
                    )
                    self._append_audit(
                        proposal_id=proposal_id,
                        action=f"ETERNIAN_REMEDIATION_REVIEW_{decision.value}",
                        state_before=RemediationDocketState.PENDING_ETERNIAN_REVIEW,
                        state_after=target,
                        actor_id=reviewer_id,
                        evidence_digest=review_digest,
                        recorded_at=reviewed_at,
                    )
                    return self._get_record(proposal_id)
            except sqlite3.Error as exc:
                raise GovernanceRejected("synthetic remediation review transaction failed") from exc

    def _append_audit(
        self,
        *,
        proposal_id: str,
        action: str,
        state_before: RemediationDocketState | None,
        state_after: RemediationDocketState,
        actor_id: str,
        evidence_digest: str,
        recorded_at: datetime,
    ) -> None:
        latest = self._connection.execute(
            """
            SELECT audit_sequence, audit_digest FROM synthetic_remediation_docket_audit
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
            INSERT INTO synthetic_remediation_docket_audit (
                audit_sequence, proposal_id, action, state_before, state_after,
                actor_id, evidence_digest, previous_digest, audit_digest, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sequence,
                proposal_id,
                action,
                value["state_before"],
                state_after.value,
                actor_id,
                evidence_digest,
                previous,
                canonical_digest(value),
                recorded_at.isoformat(),
            ),
        )

    def _get_record(self, proposal_id: str) -> RemediationDocketRecord:
        row = self._connection.execute(
            "SELECT * FROM synthetic_remediation_dockets WHERE proposal_id = ?",
            (proposal_id,),
        ).fetchone()
        if row is None:
            raise GovernanceRejected("unknown remediation proposal docket")
        return self._record_from_row(row)

    @classmethod
    def _record_from_row(cls, row: sqlite3.Row) -> RemediationDocketRecord:
        try:
            payload = json.loads(row["proposal_json"])
            cls._validate_stored_payload(payload)
        except (GovernanceRejected, KeyError, TypeError, ValueError) as exc:
            raise GovernanceRejected("stored remediation proposal is invalid") from exc
        if (
            payload["proposal_id"] != row["proposal_id"]
            or payload["source_case_id"] != row["source_case_id"]
            or payload["proposal_digest"] != row["proposal_digest"]
        ):
            raise GovernanceRejected("stored remediation docket binding is invalid")
        return RemediationDocketRecord(
            row["proposal_id"],
            row["source_case_id"],
            row["proposal_digest"],
            row["source_assessment_digest"],
            RemediationDocketState(row["state"]),
            datetime.fromisoformat(row["submitted_at"]),
            datetime.fromisoformat(row["updated_at"]),
            row["proposer_id"],
            bool(row["automatic_review_allowed"]),
            bool(row["code_change_allowed"]),
            bool(row["operator_approval_recorded"]),
            bool(row["execution_allowed"]),
        )

    @staticmethod
    def _validate_stored_payload(payload: object) -> None:
        if not isinstance(payload, dict) or not isinstance(payload.get("plan_items"), list):
            raise GovernanceRejected("stored remediation proposal object required")
        items = []
        for item in payload["plan_items"]:
            if not isinstance(item, dict):
                raise GovernanceRejected("stored remediation plan item required")
            items.append(
                RemediationPlanItem(
                    int(item["ordinal"]),
                    str(item["finding_code"]),
                    str(item["subject_id"]),
                    RemediationActionType(str(item["action_type"])),
                    tuple(item["allowed_scopes"]),
                    tuple(item["required_checks"]),
                    str(item["item_digest"]),
                    bool(item["code_change_allowed"]),
                    bool(item["production_access_allowed"]),
                )
            )
        value = {
            "proposal_id": payload["proposal_id"],
            "source_case_id": payload["source_case_id"],
            "source_report_digest": payload["source_report_digest"],
            "source_case_review_digest": payload["source_case_review_digest"],
            "source_status": payload["source_status"],
            "plan_item_digests": payload["plan_item_digests"],
            "created_at": payload["created_at"],
            "review_required": payload["review_required"],
            "code_change_allowed": payload["code_change_allowed"],
            "automatic_application_allowed": payload["automatic_application_allowed"],
            "safety_baseline_relaxation_allowed": payload[
                "safety_baseline_relaxation_allowed"
            ],
            "operator_approval_recorded": payload["operator_approval_recorded"],
            "execution_allowed": payload["execution_allowed"],
        }
        if (
            not items
            or payload["plan_item_digests"] != [item.item_digest for item in items]
            or canonical_digest(value) != payload.get("proposal_digest")
            or payload.get("review_required") is not True
            or payload.get("code_change_allowed") is not False
            or payload.get("automatic_application_allowed") is not False
            or payload.get("safety_baseline_relaxation_allowed") is not False
            or payload.get("operator_approval_recorded") is not False
            or payload.get("execution_allowed") is not False
        ):
            raise GovernanceRejected("stored remediation proposal digest mismatch")

    def get(self, proposal_id: str) -> RemediationDocketRecord:
        with self._lock:
            return self._get_record(proposal_id)

    def ready_source(self, proposal_id: str) -> ReadyRemediationProposalSource:
        """Return an integrity-bound passed proposal without changing docket state."""
        with self._lock:
            if not self.verify_audit_chain() or not self.verify_record_bindings():
                raise GovernanceRejected("remediation docket evidence is invalid")
            row = self._connection.execute(
                "SELECT * FROM synthetic_remediation_dockets WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
            if row is None:
                raise GovernanceRejected("unknown remediation proposal docket")
            self._record_from_row(row)
            if row["state"] != RemediationDocketState.READY_FOR_SYNTHETIC_SHADOW.value:
                raise GovernanceRejected("remediation proposal is not ready for synthetic shadow")
            review = self._connection.execute(
                "SELECT * FROM synthetic_remediation_reviews WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
            if review is None or review["decision"] != RemediationReviewDecision.PASS.value:
                raise GovernanceRejected("passing remediation review source required")
            return ReadyRemediationProposalSource(
                row["proposal_id"],
                row["source_case_id"],
                row["proposal_digest"],
                review["review_digest"],
                row["proposal_json"],
                datetime.fromisoformat(review["reviewed_at"]),
            )

    def verify_audit_chain(self) -> bool:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM synthetic_remediation_docket_audit ORDER BY audit_sequence"
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
                "SELECT * FROM synthetic_remediation_dockets ORDER BY proposal_id"
            ).fetchall()
            reviews = self._connection.execute(
                "SELECT * FROM synthetic_remediation_reviews ORDER BY review_id"
            ).fetchall()
            audits = self._connection.execute(
                "SELECT * FROM synthetic_remediation_docket_audit ORDER BY audit_sequence"
            ).fetchall()
            try:
                for docket in dockets:
                    self._record_from_row(docket)
            except (GovernanceRejected, KeyError, TypeError, ValueError):
                return False
            if len(audits) != len(dockets) + len(reviews):
                return False
            audit_by_action = {(row["proposal_id"], row["action"]): row for row in audits}
            review_by_proposal = {row["proposal_id"]: row for row in reviews}
            for docket in dockets:
                submitted = audit_by_action.get(
                    (docket["proposal_id"], "ARKAON_REMEDIATION_PROPOSAL_SUBMITTED")
                )
                if (
                    submitted is None
                    or submitted["state_before"] is not None
                    or submitted["state_after"]
                    != RemediationDocketState.PENDING_ETERNIAN_REVIEW.value
                    or submitted["actor_id"] != ARKAON_REMEDIATION_PROPOSER_ID
                    or submitted["evidence_digest"] != docket["source_assessment_digest"]
                    or submitted["recorded_at"] != docket["submitted_at"]
                ):
                    return False
                review = review_by_proposal.get(docket["proposal_id"])
                if review is None:
                    if docket["state"] != RemediationDocketState.PENDING_ETERNIAN_REVIEW.value:
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
                target = {
                    "PASS": RemediationDocketState.READY_FOR_SYNTHETIC_SHADOW,
                    "HOLD": RemediationDocketState.HELD,
                    "REJECT": RemediationDocketState.REJECTED,
                }.get(review["decision"])
                audit = audit_by_action.get(
                    (docket["proposal_id"], f"ETERNIAN_REMEDIATION_REVIEW_{review['decision']}")
                )
                if (
                    not review["review_id"].startswith("synthetic:remediation-review:")
                    or len(review["review_id"])
                    <= len("synthetic:remediation-review:")
                    or not review["reviewer_id"].startswith("synthetic:eternian-reviewer:")
                    or len(review["reviewer_id"])
                    <= len("synthetic:eternian-reviewer:")
                    or review["reviewer_id"] == ARKAON_REMEDIATION_PROPOSER_ID
                    or not _valid_digest(review["findings_digest"])
                    or canonical_digest(review_value) != review["review_digest"]
                    or target is None
                    or docket["state"] != target.value
                    or docket["updated_at"] != review["reviewed_at"]
                    or audit is None
                    or audit["state_before"]
                    != RemediationDocketState.PENDING_ETERNIAN_REVIEW.value
                    or audit["state_after"] != target.value
                    or audit["actor_id"] != review["reviewer_id"]
                    or audit["evidence_digest"] != review["review_digest"]
                    or audit["recorded_at"] != review["reviewed_at"]
                ):
                    return False
            return True

    def evidence(self) -> dict[str, object]:
        with self._lock:
            counts = {state.value: 0 for state in RemediationDocketState}
            for row in self._connection.execute(
                "SELECT state, COUNT(*) AS count FROM synthetic_remediation_dockets GROUP BY state"
            ):
                counts[row["state"]] = row["count"]
            value = {
                "schema": "nurion.pg.synthetic-remediation-review-docket-evidence.v1",
                "database_engine": "SQLite",
                "schema_version": REMEDIATION_DOCKET_SCHEMA_VERSION,
                "schema_digest": canonical_digest(REMEDIATION_DOCKET_SCHEMA_SQL),
                "state_counts": counts,
                "audit_chain_valid": self.verify_audit_chain(),
                "record_bindings_valid": self.verify_record_bindings(),
                "maximum_state": RemediationDocketState.READY_FOR_SYNTHETIC_SHADOW.value,
                "synthetic_shadow_method_present": False,
                "code_change_method_present": False,
                "application_method_present": False,
                "operator_decision_method_present": False,
                "execution_method_present": False,
                "money_movement_executed": False,
                "production_activation_allowed": False,
            }
            return {**value, "report_digest": canonical_digest(value)}
