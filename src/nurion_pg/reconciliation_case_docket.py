"""Durable synthetic reconciliation cases capped at remediation proposal readiness."""

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


CASE_SCHEMA_VERSION = 1
ARKAON_MONITOR_ID = "synthetic:arkaon:NURION_PG:reconciliation-monitor"
CASE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS synthetic_reconciliation_case_metadata (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    schema_version INTEGER NOT NULL CHECK (schema_version = 1),
    synthetic_only INTEGER NOT NULL CHECK (synthetic_only = 1)
);
CREATE TABLE IF NOT EXISTS synthetic_reconciliation_cases (
    case_id TEXT PRIMARY KEY,
    report_digest TEXT NOT NULL UNIQUE,
    report_status TEXT NOT NULL CHECK (report_status IN ('HUMAN_REVIEW', 'BLOCKED')),
    finding_count INTEGER NOT NULL CHECK (finding_count > 0),
    report_json TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN (
        'PENDING_ETERNIAN_REVIEW',
        'READY_FOR_REMEDIATION_PROPOSAL',
        'HELD',
        'REJECTED'
    )),
    submitted_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    submitter_id TEXT NOT NULL
        CHECK (submitter_id = 'synthetic:arkaon:NURION_PG:reconciliation-monitor'),
    automatic_repair_allowed INTEGER NOT NULL DEFAULT 0
        CHECK (automatic_repair_allowed = 0),
    operator_approval_recorded INTEGER NOT NULL DEFAULT 0
        CHECK (operator_approval_recorded = 0),
    execution_allowed INTEGER NOT NULL DEFAULT 0 CHECK (execution_allowed = 0)
);
CREATE TABLE IF NOT EXISTS synthetic_reconciliation_case_reviews (
    review_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL UNIQUE REFERENCES synthetic_reconciliation_cases(case_id),
    reviewer_id TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('CONFIRM', 'HOLD', 'REJECT')),
    findings_digest TEXT NOT NULL,
    reviewed_at TEXT NOT NULL,
    review_digest TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS synthetic_reconciliation_case_audit (
    audit_sequence INTEGER PRIMARY KEY,
    case_id TEXT NOT NULL,
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


class ReconciliationCaseState(StrEnum):
    PENDING_ETERNIAN_REVIEW = "PENDING_ETERNIAN_REVIEW"
    READY_FOR_REMEDIATION_PROPOSAL = "READY_FOR_REMEDIATION_PROPOSAL"
    HELD = "HELD"
    REJECTED = "REJECTED"


class ReconciliationCaseReviewDecision(StrEnum):
    CONFIRM = "CONFIRM"
    HOLD = "HOLD"
    REJECT = "REJECT"


@dataclass(frozen=True)
class ReconciliationCaseRecord:
    case_id: str
    report_digest: str
    report_status: str
    finding_count: int
    state: ReconciliationCaseState
    submitted_at: datetime
    updated_at: datetime
    submitter_id: str = ARKAON_MONITOR_ID
    automatic_repair_allowed: bool = False
    operator_approval_recorded: bool = False
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if (
            not self.case_id.startswith("synthetic:reconciliation-case:")
            or not _valid_digest(self.report_digest)
            or self.report_status not in {"HUMAN_REVIEW", "BLOCKED"}
            or self.finding_count <= 0
            or self.submitted_at.tzinfo is None
            or self.updated_at.tzinfo is None
            or self.updated_at < self.submitted_at
            or self.submitter_id != ARKAON_MONITOR_ID
            or self.automatic_repair_allowed
            or self.operator_approval_recorded
            or self.execution_allowed
        ):
            raise GovernanceRejected("valid non-repairing synthetic reconciliation case required")


@dataclass(frozen=True)
class ReadyReconciliationCaseSource:
    case_id: str
    report_digest: str
    review_digest: str
    report_json: str

    def __post_init__(self) -> None:
        if (
            not self.case_id.startswith("synthetic:reconciliation-case:")
            or not _valid_digest(self.report_digest)
            or not _valid_digest(self.review_digest)
            or not self.report_json
        ):
            raise GovernanceRejected("complete ready reconciliation case source required")


def _valid_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


class SyntheticReconciliationCaseDocket:
    """Persists monitor findings and Eternian review without repairing anything."""

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
            raise GovernanceRejected("synthetic SQLite reconciliation case target required")

    def _initialize_schema(self) -> None:
        with self._lock:
            self._connection.executescript(CASE_SCHEMA_SQL)
            self._connection.execute(
                """
                INSERT OR IGNORE INTO synthetic_reconciliation_case_metadata
                    (singleton, schema_version, synthetic_only) VALUES (1, ?, 1)
                """,
                (CASE_SCHEMA_VERSION,),
            )
            row = self._connection.execute(
                """
                SELECT schema_version, synthetic_only
                FROM synthetic_reconciliation_case_metadata WHERE singleton = 1
                """
            ).fetchone()
            if (
                row is None
                or row["schema_version"] != CASE_SCHEMA_VERSION
                or row["synthetic_only"] != 1
            ):
                raise GovernanceRejected("unsupported or non-synthetic case schema")

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

    def submit_report(
        self, report: dict[str, object], *, submitted_at: datetime
    ) -> ReconciliationCaseRecord:
        if submitted_at.tzinfo is None:
            raise GovernanceRejected("timezone-aware case submission required")
        self._validate_report(report)
        observed_at = datetime.fromisoformat(str(report["observed_at"]))
        if submitted_at < observed_at:
            raise GovernanceRejected("case submission cannot predate reconciliation report")
        report_digest = str(report["report_digest"])
        case_id = f"synthetic:reconciliation-case:{report_digest[:32]}"
        with self._lock:
            try:
                with self._transaction():
                    existing = self._connection.execute(
                        "SELECT * FROM synthetic_reconciliation_cases WHERE case_id = ?",
                        (case_id,),
                    ).fetchone()
                    if existing is not None:
                        if existing["report_digest"] != report_digest:
                            raise GovernanceRejected("reconciliation case identity collision")
                        return self._record_from_row(existing)
                    self._connection.execute(
                        """
                        INSERT INTO synthetic_reconciliation_cases (
                            case_id, report_digest, report_status, finding_count,
                            report_json, state, submitted_at, updated_at, submitter_id,
                            automatic_repair_allowed, operator_approval_recorded,
                            execution_allowed
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0)
                        """,
                        (
                            case_id,
                            report_digest,
                            report["status"],
                            len(report["findings"]),  # type: ignore[arg-type]
                            json.dumps(
                                report,
                                ensure_ascii=False,
                                sort_keys=True,
                                separators=(",", ":"),
                            ),
                            ReconciliationCaseState.PENDING_ETERNIAN_REVIEW.value,
                            submitted_at.isoformat(),
                            submitted_at.isoformat(),
                            ARKAON_MONITOR_ID,
                        ),
                    )
                    self._append_audit(
                        case_id=case_id,
                        action="ARKAON_RECONCILIATION_CASE_SUBMITTED",
                        state_before=None,
                        state_after=ReconciliationCaseState.PENDING_ETERNIAN_REVIEW,
                        actor_id=ARKAON_MONITOR_ID,
                        evidence_digest=report_digest,
                        recorded_at=submitted_at,
                    )
                    return self._get_record(case_id)
            except sqlite3.Error as exc:
                raise GovernanceRejected("synthetic reconciliation case transaction failed") from exc

    @staticmethod
    def _validate_report(report: dict[str, object]) -> None:
        if not isinstance(report, dict):
            raise GovernanceRejected("synthetic reconciliation report object required")
        report_digest = report.get("report_digest")
        body = {key: value for key, value in report.items() if key != "report_digest"}
        if (
            report.get("schema") != "nurion.pg.synthetic-reconciliation-report.v1"
            or not _valid_digest(report_digest)
            or canonical_digest(body) != report_digest
            or report.get("status") not in {"HUMAN_REVIEW", "BLOCKED"}
            or report.get("read_only_verified") is not True
            or report.get("synthetic_only") is not True
            or report.get("automatic_repair_allowed") is not False
            or report.get("operator_decision_recorded") is not False
            or report.get("payment_state_changed") is not False
            or report.get("money_movement_executed") is not False
            or report.get("production_activation_allowed") is not False
        ):
            raise GovernanceRejected("intact non-repairing reconciliation report required")
        try:
            observed_at = datetime.fromisoformat(str(report["observed_at"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise GovernanceRejected("valid report observation time required") from exc
        if observed_at.tzinfo is None:
            raise GovernanceRejected("timezone-aware report observation required")
        component_digests = report.get("component_snapshot_digests")
        if (
            not isinstance(component_digests, dict)
            or set(component_digests) != {"payment", "inbox", "proposals", "docket"}
            or not all(_valid_digest(value) for value in component_digests.values())
        ):
            raise GovernanceRejected("complete component snapshot digests required")
        findings = report.get("findings")
        if not isinstance(findings, list) or not findings:
            raise GovernanceRejected("one or more reconciliation findings required")
        counts = {"WARNING": 0, "BLOCKED": 0}
        for finding in findings:
            if (
                not isinstance(finding, dict)
                or finding.get("severity") not in counts
                or not isinstance(finding.get("code"), str)
                or not finding.get("code")
                or not isinstance(finding.get("subject_id"), str)
                or not str(finding.get("subject_id")).startswith("synthetic:")
                or not isinstance(finding.get("detail"), str)
                or not finding.get("detail")
                or not isinstance(finding.get("suggested_action"), str)
                or not finding.get("suggested_action")
                or finding.get("automatic_repair_allowed") is not False
            ):
                raise GovernanceRejected("valid non-repairing finding required")
            counts[str(finding["severity"])] += 1
        expected_status = "BLOCKED" if counts["BLOCKED"] else "HUMAN_REVIEW"
        if report.get("finding_counts") != counts or report.get("status") != expected_status:
            raise GovernanceRejected("finding counts and report status must agree")

    def record_eternian_review(
        self,
        case_id: str,
        *,
        review_id: str,
        reviewer_id: str,
        decision: ReconciliationCaseReviewDecision,
        findings_digest: str,
        reviewed_at: datetime,
    ) -> ReconciliationCaseRecord:
        if (
            not review_id.startswith("synthetic:reconciliation-review:")
            or len(review_id) <= len("synthetic:reconciliation-review:")
            or not reviewer_id.startswith("synthetic:eternian-reviewer:")
            or len(reviewer_id) <= len("synthetic:eternian-reviewer:")
            or reviewer_id == ARKAON_MONITOR_ID
            or not isinstance(decision, ReconciliationCaseReviewDecision)
            or not _valid_digest(findings_digest)
            or reviewed_at.tzinfo is None
        ):
            raise GovernanceRejected("complete independent synthetic case review required")
        value = {
            "review_id": review_id,
            "case_id": case_id,
            "reviewer_id": reviewer_id,
            "decision": decision.value,
            "findings_digest": findings_digest,
            "reviewed_at": reviewed_at.isoformat(),
        }
        review_digest = canonical_digest(value)
        target = {
            ReconciliationCaseReviewDecision.CONFIRM:
                ReconciliationCaseState.READY_FOR_REMEDIATION_PROPOSAL,
            ReconciliationCaseReviewDecision.HOLD: ReconciliationCaseState.HELD,
            ReconciliationCaseReviewDecision.REJECT: ReconciliationCaseState.REJECTED,
        }[decision]
        with self._lock:
            try:
                with self._transaction():
                    existing = self._connection.execute(
                        "SELECT * FROM synthetic_reconciliation_case_reviews WHERE review_id = ?",
                        (review_id,),
                    ).fetchone()
                    if existing is not None:
                        if existing["review_digest"] != review_digest:
                            raise GovernanceRejected("case review idempotency payload mismatch")
                        return self._get_record(case_id)
                    case = self._connection.execute(
                        "SELECT * FROM synthetic_reconciliation_cases WHERE case_id = ?",
                        (case_id,),
                    ).fetchone()
                    if case is None:
                        raise GovernanceRejected("unknown reconciliation case")
                    if reviewed_at < datetime.fromisoformat(case["submitted_at"]):
                        raise GovernanceRejected("case review cannot predate submission")
                    if case["state"] != ReconciliationCaseState.PENDING_ETERNIAN_REVIEW.value:
                        raise GovernanceRejected("case is not pending Eternian review")
                    self._connection.execute(
                        """
                        INSERT INTO synthetic_reconciliation_case_reviews (
                            review_id, case_id, reviewer_id, decision, findings_digest,
                            reviewed_at, review_digest
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            review_id,
                            case_id,
                            reviewer_id,
                            decision.value,
                            findings_digest,
                            reviewed_at.isoformat(),
                            review_digest,
                        ),
                    )
                    self._connection.execute(
                        """
                        UPDATE synthetic_reconciliation_cases SET state = ?, updated_at = ?
                        WHERE case_id = ?
                        """,
                        (target.value, reviewed_at.isoformat(), case_id),
                    )
                    self._append_audit(
                        case_id=case_id,
                        action=f"ETERNIAN_RECONCILIATION_REVIEW_{decision.value}",
                        state_before=ReconciliationCaseState.PENDING_ETERNIAN_REVIEW,
                        state_after=target,
                        actor_id=reviewer_id,
                        evidence_digest=review_digest,
                        recorded_at=reviewed_at,
                    )
                    return self._get_record(case_id)
            except sqlite3.Error as exc:
                raise GovernanceRejected("synthetic reconciliation review transaction failed") from exc

    def _append_audit(
        self,
        *,
        case_id: str,
        action: str,
        state_before: ReconciliationCaseState | None,
        state_after: ReconciliationCaseState,
        actor_id: str,
        evidence_digest: str,
        recorded_at: datetime,
    ) -> None:
        latest = self._connection.execute(
            """
            SELECT audit_sequence, audit_digest FROM synthetic_reconciliation_case_audit
            ORDER BY audit_sequence DESC LIMIT 1
            """
        ).fetchone()
        sequence = (latest["audit_sequence"] if latest is not None else 0) + 1
        previous = latest["audit_digest"] if latest is not None else "0" * 64
        value = {
            "audit_sequence": sequence,
            "case_id": case_id,
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
            INSERT INTO synthetic_reconciliation_case_audit (
                audit_sequence, case_id, action, state_before, state_after, actor_id,
                evidence_digest, previous_digest, audit_digest, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sequence,
                case_id,
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

    def _get_record(self, case_id: str) -> ReconciliationCaseRecord:
        row = self._connection.execute(
            "SELECT * FROM synthetic_reconciliation_cases WHERE case_id = ?", (case_id,)
        ).fetchone()
        if row is None:
            raise GovernanceRejected("unknown reconciliation case")
        return self._record_from_row(row)

    @classmethod
    def _record_from_row(cls, row: sqlite3.Row) -> ReconciliationCaseRecord:
        try:
            report = json.loads(row["report_json"])
            cls._validate_report(report)
        except (GovernanceRejected, TypeError, ValueError) as exc:
            raise GovernanceRejected("stored reconciliation report binding is invalid") from exc
        if (
            report["report_digest"] != row["report_digest"]
            or row["case_id"]
            != f"synthetic:reconciliation-case:{row['report_digest'][:32]}"
            or report["status"] != row["report_status"]
            or len(report["findings"]) != row["finding_count"]
        ):
            raise GovernanceRejected("stored reconciliation case binding is invalid")
        return ReconciliationCaseRecord(
            row["case_id"],
            row["report_digest"],
            row["report_status"],
            row["finding_count"],
            ReconciliationCaseState(row["state"]),
            datetime.fromisoformat(row["submitted_at"]),
            datetime.fromisoformat(row["updated_at"]),
            row["submitter_id"],
            bool(row["automatic_repair_allowed"]),
            bool(row["operator_approval_recorded"]),
            bool(row["execution_allowed"]),
        )

    def get(self, case_id: str) -> ReconciliationCaseRecord:
        with self._lock:
            return self._get_record(case_id)

    def ready_source(self, case_id: str) -> ReadyReconciliationCaseSource:
        """Return an integrity-bound confirmed case without changing its state."""
        with self._lock:
            if not self.verify_audit_chain() or not self.verify_record_bindings():
                raise GovernanceRejected("reconciliation case evidence is invalid")
            row = self._connection.execute(
                "SELECT * FROM synthetic_reconciliation_cases WHERE case_id = ?", (case_id,)
            ).fetchone()
            if (
                row is None
                or row["state"]
                != ReconciliationCaseState.READY_FOR_REMEDIATION_PROPOSAL.value
            ):
                raise GovernanceRejected("confirmed reconciliation case source required")
            record = self._record_from_row(row)
            review = self._connection.execute(
                """
                SELECT * FROM synthetic_reconciliation_case_reviews WHERE case_id = ?
                """,
                (case_id,),
            ).fetchone()
            if review is None or review["decision"] != "CONFIRM":
                raise GovernanceRejected("confirmed Eternian case review required")
            review_value = {
                "review_id": review["review_id"],
                "case_id": review["case_id"],
                "reviewer_id": review["reviewer_id"],
                "decision": review["decision"],
                "findings_digest": review["findings_digest"],
                "reviewed_at": review["reviewed_at"],
            }
            if canonical_digest(review_value) != review["review_digest"]:
                raise GovernanceRejected("confirmed case review digest mismatch")
            return ReadyReconciliationCaseSource(
                record.case_id,
                record.report_digest,
                review["review_digest"],
                row["report_json"],
            )

    def verify_audit_chain(self) -> bool:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM synthetic_reconciliation_case_audit ORDER BY audit_sequence"
            ).fetchall()
            previous = "0" * 64
            for sequence, row in enumerate(rows, start=1):
                value = {
                    "audit_sequence": sequence,
                    "case_id": row["case_id"],
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
            cases = self._connection.execute(
                "SELECT * FROM synthetic_reconciliation_cases ORDER BY case_id"
            ).fetchall()
            reviews = self._connection.execute(
                "SELECT * FROM synthetic_reconciliation_case_reviews ORDER BY review_id"
            ).fetchall()
            audits = self._connection.execute(
                "SELECT * FROM synthetic_reconciliation_case_audit ORDER BY audit_sequence"
            ).fetchall()
            try:
                for case in cases:
                    self._record_from_row(case)
            except (GovernanceRejected, TypeError, ValueError):
                return False
            if len(audits) != len(cases) + len(reviews):
                return False
            audits_by_action = {(row["case_id"], row["action"]): row for row in audits}
            reviews_by_case = {row["case_id"]: row for row in reviews}
            for case in cases:
                submitted = audits_by_action.get(
                    (case["case_id"], "ARKAON_RECONCILIATION_CASE_SUBMITTED")
                )
                if (
                    submitted is None
                    or submitted["state_before"] is not None
                    or submitted["state_after"]
                    != ReconciliationCaseState.PENDING_ETERNIAN_REVIEW.value
                    or submitted["actor_id"] != ARKAON_MONITOR_ID
                    or submitted["evidence_digest"] != case["report_digest"]
                    or submitted["recorded_at"] != case["submitted_at"]
                ):
                    return False
                review = reviews_by_case.get(case["case_id"])
                if review is None:
                    if case["state"] != ReconciliationCaseState.PENDING_ETERNIAN_REVIEW.value:
                        return False
                    continue
                review_value = {
                    "review_id": review["review_id"],
                    "case_id": review["case_id"],
                    "reviewer_id": review["reviewer_id"],
                    "decision": review["decision"],
                    "findings_digest": review["findings_digest"],
                    "reviewed_at": review["reviewed_at"],
                }
                if (
                    not review["review_id"].startswith("synthetic:reconciliation-review:")
                    or len(review["review_id"])
                    <= len("synthetic:reconciliation-review:")
                    or not review["reviewer_id"].startswith(
                        "synthetic:eternian-reviewer:"
                    )
                    or len(review["reviewer_id"])
                    <= len("synthetic:eternian-reviewer:")
                    or review["reviewer_id"] == ARKAON_MONITOR_ID
                    or not _valid_digest(review["findings_digest"])
                    or canonical_digest(review_value) != review["review_digest"]
                ):
                    return False
                target = {
                    "CONFIRM": ReconciliationCaseState.READY_FOR_REMEDIATION_PROPOSAL,
                    "HOLD": ReconciliationCaseState.HELD,
                    "REJECT": ReconciliationCaseState.REJECTED,
                }.get(review["decision"])
                audit = audits_by_action.get(
                    (case["case_id"], f"ETERNIAN_RECONCILIATION_REVIEW_{review['decision']}")
                )
                if (
                    target is None
                    or case["state"] != target.value
                    or case["updated_at"] != review["reviewed_at"]
                    or audit is None
                    or audit["state_before"]
                    != ReconciliationCaseState.PENDING_ETERNIAN_REVIEW.value
                    or audit["state_after"] != target.value
                    or audit["actor_id"] != review["reviewer_id"]
                    or audit["evidence_digest"] != review["review_digest"]
                    or audit["recorded_at"] != review["reviewed_at"]
                ):
                    return False
            return True

    def evidence(self) -> dict[str, object]:
        with self._lock:
            counts = {state.value: 0 for state in ReconciliationCaseState}
            for row in self._connection.execute(
                "SELECT state, COUNT(*) AS count FROM synthetic_reconciliation_cases GROUP BY state"
            ):
                counts[row["state"]] = row["count"]
            value = {
                "schema": "nurion.pg.synthetic-reconciliation-case-docket-evidence.v1",
                "database_engine": "SQLite",
                "schema_version": CASE_SCHEMA_VERSION,
                "schema_digest": canonical_digest(CASE_SCHEMA_SQL),
                "state_counts": counts,
                "audit_chain_valid": self.verify_audit_chain(),
                "record_bindings_valid": self.verify_record_bindings(),
                "maximum_state": ReconciliationCaseState.READY_FOR_REMEDIATION_PROPOSAL.value,
                "remediation_proposal_method_present": False,
                "automatic_repair_method_present": False,
                "operator_decision_method_present": False,
                "execution_method_present": False,
                "money_movement_executed": False,
                "production_activation_allowed": False,
            }
            return {**value, "report_digest": canonical_digest(value)}
