"""Durable Eternian review docket for metadata-only patch shadow results."""

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
from .synthetic_patch_shadow import (
    PatchShadowDecision,
    PatchShadowItemDecision,
    SyntheticPatchShadowAssessment,
    SyntheticPatchShadowBook,
    SyntheticPatchShadowItemResult,
)


PATCH_SHADOW_REVIEW_SCHEMA_VERSION = 1
ARKAON_PATCH_SHADOW_SUBMITTER_ID = "synthetic:arkaon:NURION_PG:patch-shadow-evaluator"
PATCH_SHADOW_REVIEW_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS synthetic_patch_shadow_review_metadata (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    schema_version INTEGER NOT NULL CHECK (schema_version = 1),
    synthetic_only INTEGER NOT NULL CHECK (synthetic_only = 1)
);
CREATE TABLE IF NOT EXISTS synthetic_patch_shadow_review_dockets (
    shadow_id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL UNIQUE,
    proposal_digest TEXT NOT NULL UNIQUE,
    source_review_digest TEXT NOT NULL UNIQUE,
    shadow_assessment_digest TEXT NOT NULL UNIQUE,
    assessment_json TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN (
        'PENDING_ETERNIAN_REVIEW',
        'READY_FOR_OPERATOR_DECISION',
        'HELD',
        'REJECTED'
    )),
    submitted_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    submitter_id TEXT NOT NULL
        CHECK (submitter_id = 'synthetic:arkaon:NURION_PG:patch-shadow-evaluator'),
    automatic_review_allowed INTEGER NOT NULL DEFAULT 0
        CHECK (automatic_review_allowed = 0),
    patch_content_present INTEGER NOT NULL DEFAULT 0
        CHECK (patch_content_present = 0),
    code_change_allowed INTEGER NOT NULL DEFAULT 0 CHECK (code_change_allowed = 0),
    automatic_application_allowed INTEGER NOT NULL DEFAULT 0
        CHECK (automatic_application_allowed = 0),
    safety_baseline_relaxation_allowed INTEGER NOT NULL DEFAULT 0
        CHECK (safety_baseline_relaxation_allowed = 0),
    operator_decision_recorded INTEGER NOT NULL DEFAULT 0
        CHECK (operator_decision_recorded = 0),
    execution_allowed INTEGER NOT NULL DEFAULT 0 CHECK (execution_allowed = 0),
    production_activation_allowed INTEGER NOT NULL DEFAULT 0
        CHECK (production_activation_allowed = 0)
);
CREATE TABLE IF NOT EXISTS synthetic_patch_shadow_reviews (
    review_id TEXT PRIMARY KEY,
    shadow_id TEXT NOT NULL UNIQUE REFERENCES synthetic_patch_shadow_review_dockets(shadow_id),
    reviewer_id TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('PASS', 'HOLD', 'REJECT')),
    findings_digest TEXT NOT NULL,
    reviewed_at TEXT NOT NULL,
    review_digest TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS synthetic_patch_shadow_review_audit (
    audit_sequence INTEGER PRIMARY KEY,
    shadow_id TEXT NOT NULL,
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


class PatchShadowReviewState(StrEnum):
    PENDING_ETERNIAN_REVIEW = "PENDING_ETERNIAN_REVIEW"
    READY_FOR_OPERATOR_DECISION = "READY_FOR_OPERATOR_DECISION"
    HELD = "HELD"
    REJECTED = "REJECTED"


class PatchShadowReviewDecision(StrEnum):
    PASS = "PASS"
    HOLD = "HOLD"
    REJECT = "REJECT"


@dataclass(frozen=True)
class PatchShadowReviewRecord:
    shadow_id: str
    proposal_id: str
    proposal_digest: str
    source_review_digest: str
    shadow_assessment_digest: str
    state: PatchShadowReviewState
    submitted_at: datetime
    updated_at: datetime
    submitter_id: str = ARKAON_PATCH_SHADOW_SUBMITTER_ID
    automatic_review_allowed: bool = False
    patch_content_present: bool = False
    code_change_allowed: bool = False
    automatic_application_allowed: bool = False
    safety_baseline_relaxation_allowed: bool = False
    operator_decision_recorded: bool = False
    execution_allowed: bool = False
    production_activation_allowed: bool = False

    def __post_init__(self) -> None:
        if (
            not self.shadow_id.startswith("synthetic:patch-shadow:")
            or not self.proposal_id.startswith("synthetic:implementation-proposal-draft:")
            or not _valid_digest(self.proposal_digest)
            or not _valid_digest(self.source_review_digest)
            or not _valid_digest(self.shadow_assessment_digest)
            or self.submitted_at.tzinfo is None
            or self.updated_at.tzinfo is None
            or self.updated_at < self.submitted_at
            or self.submitter_id != ARKAON_PATCH_SHADOW_SUBMITTER_ID
            or self.automatic_review_allowed
            or self.patch_content_present
            or self.code_change_allowed
            or self.automatic_application_allowed
            or self.safety_baseline_relaxation_allowed
            or self.operator_decision_recorded
            or self.execution_allowed
            or self.production_activation_allowed
        ):
            raise GovernanceRejected("valid non-executing patch shadow review record required")


@dataclass(frozen=True)
class ReadyPatchShadowReviewSource:
    shadow_id: str
    proposal_id: str
    proposal_digest: str
    source_review_digest: str
    shadow_assessment_digest: str
    review_digest: str
    assessment_json: str
    reviewed_at: datetime

    def __post_init__(self) -> None:
        if (
            not self.shadow_id.startswith("synthetic:patch-shadow:")
            or not self.proposal_id.startswith("synthetic:implementation-proposal-draft:")
            or not _valid_digest(self.proposal_digest)
            or not _valid_digest(self.source_review_digest)
            or not _valid_digest(self.shadow_assessment_digest)
            or not _valid_digest(self.review_digest)
            or not self.assessment_json
            or self.reviewed_at.tzinfo is None
        ):
            raise GovernanceRejected("complete ready patch shadow review source required")


def _valid_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


class SyntheticPatchShadowReviewDocket:
    """Persists patch shadow results and review without operator action or execution."""

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
            raise GovernanceRejected("synthetic SQLite patch shadow review target required")

    def _initialize_schema(self) -> None:
        with self._lock:
            self._connection.executescript(PATCH_SHADOW_REVIEW_SCHEMA_SQL)
            self._connection.execute(
                """
                INSERT OR IGNORE INTO synthetic_patch_shadow_review_metadata
                    (singleton, schema_version, synthetic_only) VALUES (1, ?, 1)
                """,
                (PATCH_SHADOW_REVIEW_SCHEMA_VERSION,),
            )
            row = self._connection.execute(
                """
                SELECT schema_version, synthetic_only
                FROM synthetic_patch_shadow_review_metadata WHERE singleton = 1
                """
            ).fetchone()
            if (
                row is None
                or row["schema_version"] != PATCH_SHADOW_REVIEW_SCHEMA_VERSION
                or row["synthetic_only"] != 1
            ):
                raise GovernanceRejected("unsupported or non-synthetic patch shadow review schema")

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
        book: SyntheticPatchShadowBook,
        proposal_id: str,
        *,
        submitted_at: datetime,
    ) -> PatchShadowReviewRecord:
        if submitted_at.tzinfo is None:
            raise GovernanceRejected("timezone-aware patch shadow review submission required")
        if not isinstance(book, SyntheticPatchShadowBook):
            raise GovernanceRejected("typed synthetic patch shadow book required")
        if not book.verify_assessment_chain():
            raise GovernanceRejected("synthetic patch shadow assessment chain is invalid")
        matches = [
            assessment
            for assessment in book.assessments
            if assessment.proposal_id == proposal_id
        ]
        if len(matches) != 1:
            raise GovernanceRejected("one synthetic patch shadow assessment source required")
        assessment = matches[0]
        self._validate_assessment(assessment)
        if submitted_at < assessment.evaluated_at:
            raise GovernanceRejected("patch shadow review submission cannot predate assessment")
        shadow_id = assessment.shadow_id
        payload = self._assessment_payload(assessment)
        with self._lock:
            try:
                with self._transaction():
                    existing = self._connection.execute(
                        "SELECT * FROM synthetic_patch_shadow_review_dockets WHERE shadow_id = ?",
                        (shadow_id,),
                    ).fetchone()
                    if existing is not None:
                        if (
                            existing["proposal_id"] != proposal_id
                            or existing["shadow_assessment_digest"]
                            != assessment.assessment_digest
                            or existing["submitted_at"] != submitted_at.isoformat()
                        ):
                            raise GovernanceRejected("patch shadow review docket identity collision")
                        if (
                            not self.verify_audit_chain()
                            or not self.verify_record_bindings()
                        ):
                            raise GovernanceRejected("existing patch shadow review evidence is invalid")
                        return self._record_from_row(existing)
                    self._connection.execute(
                        """
                        INSERT INTO synthetic_patch_shadow_review_dockets (
                            shadow_id, proposal_id, proposal_digest,
                            source_review_digest, shadow_assessment_digest,
                            assessment_json, state, submitted_at, updated_at,
                            submitter_id, automatic_review_allowed,
                            patch_content_present, code_change_allowed,
                            automatic_application_allowed,
                            safety_baseline_relaxation_allowed,
                            operator_decision_recorded, execution_allowed,
                            production_activation_allowed
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0)
                        """,
                        (
                            shadow_id,
                            proposal_id,
                            assessment.proposal_digest,
                            assessment.source_review_digest,
                            assessment.assessment_digest,
                            json.dumps(
                                payload,
                                ensure_ascii=False,
                                sort_keys=True,
                                separators=(",", ":"),
                            ),
                            PatchShadowReviewState.PENDING_ETERNIAN_REVIEW.value,
                            submitted_at.isoformat(),
                            submitted_at.isoformat(),
                            ARKAON_PATCH_SHADOW_SUBMITTER_ID,
                        ),
                    )
                    self._append_audit(
                        shadow_id=shadow_id,
                        action="ARKAON_PATCH_SHADOW_RESULT_SUBMITTED",
                        state_before=None,
                        state_after=PatchShadowReviewState.PENDING_ETERNIAN_REVIEW,
                        actor_id=ARKAON_PATCH_SHADOW_SUBMITTER_ID,
                        evidence_digest=assessment.assessment_digest,
                        recorded_at=submitted_at,
                    )
                    return self._get_record(shadow_id)
            except sqlite3.Error as exc:
                raise GovernanceRejected("synthetic patch shadow review transaction failed") from exc

    @staticmethod
    def _validate_assessment(assessment: SyntheticPatchShadowAssessment) -> None:
        if (
            assessment.decision
            is not PatchShadowDecision.PROPOSED_FOR_ETERNIAN_REVIEW
            or assessment.reason != "patch_shadow_ready_for_eternian_review"
            or assessment.assessment_digest != canonical_digest(assessment.digest_value())
            or not assessment.item_results
            or assessment.source_docket_state_changed
            or assessment.patch_content_present
            or assessment.code_change_allowed
            or assessment.automatic_application_allowed
            or assessment.safety_baseline_relaxation_allowed
            or assessment.execution_allowed
            or assessment.production_activation_allowed
        ):
            raise GovernanceRejected("reviewable non-executing patch shadow assessment required")
        for result in assessment.item_results:
            if (
                result.decision is not PatchShadowItemDecision.PASS
                or result.reason != "all_patch_shadow_controls_passed"
                or result.result_digest != canonical_digest(result.digest_value())
            ):
                raise GovernanceRejected("all shadow items must pass before docket review")

    @staticmethod
    def _assessment_payload(
        assessment: SyntheticPatchShadowAssessment,
    ) -> dict[str, object]:
        return {
            **assessment.digest_value(),
            "item_results": [
                {**item.digest_value(), "result_digest": item.result_digest}
                for item in assessment.item_results
            ],
            "assessment_digest": assessment.assessment_digest,
        }

    def record_eternian_review(
        self,
        shadow_id: str,
        *,
        review_id: str,
        reviewer_id: str,
        decision: PatchShadowReviewDecision,
        findings_digest: str,
        reviewed_at: datetime,
    ) -> PatchShadowReviewRecord:
        if (
            not review_id.startswith("synthetic:patch-shadow-review:")
            or len(review_id) <= len("synthetic:patch-shadow-review:")
            or not reviewer_id.startswith("synthetic:eternian-reviewer:")
            or len(reviewer_id) <= len("synthetic:eternian-reviewer:")
            or not isinstance(decision, PatchShadowReviewDecision)
            or not _valid_digest(findings_digest)
            or reviewed_at.tzinfo is None
        ):
            raise GovernanceRejected("complete independent patch shadow review required")
        value = {
            "review_id": review_id,
            "shadow_id": shadow_id,
            "reviewer_id": reviewer_id,
            "decision": decision.value,
            "findings_digest": findings_digest,
            "reviewed_at": reviewed_at.isoformat(),
        }
        review_digest = canonical_digest(value)
        target = {
            PatchShadowReviewDecision.PASS: PatchShadowReviewState.READY_FOR_OPERATOR_DECISION,
            PatchShadowReviewDecision.HOLD: PatchShadowReviewState.HELD,
            PatchShadowReviewDecision.REJECT: PatchShadowReviewState.REJECTED,
        }[decision]
        with self._lock:
            try:
                with self._transaction():
                    existing = self._connection.execute(
                        "SELECT * FROM synthetic_patch_shadow_reviews WHERE review_id = ?",
                        (review_id,),
                    ).fetchone()
                    if existing is not None:
                        if existing["review_digest"] != review_digest:
                            raise GovernanceRejected("patch shadow review idempotency mismatch")
                        if (
                            not self.verify_audit_chain()
                            or not self.verify_record_bindings()
                        ):
                            raise GovernanceRejected(
                                "existing patch shadow review evidence is invalid"
                            )
                        return self._get_record(shadow_id)
                    docket = self._connection.execute(
                        "SELECT * FROM synthetic_patch_shadow_review_dockets WHERE shadow_id = ?",
                        (shadow_id,),
                    ).fetchone()
                    if docket is None:
                        raise GovernanceRejected("unknown patch shadow review docket")
                    if (
                        not self.verify_audit_chain()
                        or not self.verify_record_bindings()
                    ):
                        raise GovernanceRejected("patch shadow review evidence is invalid")
                    if reviewed_at < datetime.fromisoformat(docket["submitted_at"]):
                        raise GovernanceRejected("patch shadow review cannot predate submission")
                    if docket["state"] != PatchShadowReviewState.PENDING_ETERNIAN_REVIEW.value:
                        raise GovernanceRejected("patch shadow result is not pending review")
                    self._connection.execute(
                        """
                        INSERT INTO synthetic_patch_shadow_reviews (
                            review_id, shadow_id, reviewer_id, decision,
                            findings_digest, reviewed_at, review_digest
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            review_id,
                            shadow_id,
                            reviewer_id,
                            decision.value,
                            findings_digest,
                            reviewed_at.isoformat(),
                            review_digest,
                        ),
                    )
                    self._connection.execute(
                        """
                        UPDATE synthetic_patch_shadow_review_dockets SET state = ?, updated_at = ?
                        WHERE shadow_id = ?
                        """,
                        (target.value, reviewed_at.isoformat(), shadow_id),
                    )
                    self._append_audit(
                        shadow_id=shadow_id,
                        action=f"ETERNIAN_PATCH_SHADOW_REVIEW_{decision.value}",
                        state_before=PatchShadowReviewState.PENDING_ETERNIAN_REVIEW,
                        state_after=target,
                        actor_id=reviewer_id,
                        evidence_digest=review_digest,
                        recorded_at=reviewed_at,
                    )
                    return self._get_record(shadow_id)
            except sqlite3.Error as exc:
                raise GovernanceRejected("synthetic patch shadow review transaction failed") from exc

    def _append_audit(
        self,
        *,
        shadow_id: str,
        action: str,
        state_before: PatchShadowReviewState | None,
        state_after: PatchShadowReviewState,
        actor_id: str,
        evidence_digest: str,
        recorded_at: datetime,
    ) -> None:
        latest = self._connection.execute(
            """
            SELECT audit_sequence, audit_digest FROM synthetic_patch_shadow_review_audit
            ORDER BY audit_sequence DESC LIMIT 1
            """
        ).fetchone()
        sequence = (latest["audit_sequence"] if latest is not None else 0) + 1
        previous = latest["audit_digest"] if latest is not None else "0" * 64
        value = {
            "audit_sequence": sequence,
            "shadow_id": shadow_id,
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
            INSERT INTO synthetic_patch_shadow_review_audit (
                audit_sequence, shadow_id, action, state_before, state_after,
                actor_id, evidence_digest, previous_digest, audit_digest, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sequence,
                shadow_id,
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

    def _get_record(self, shadow_id: str) -> PatchShadowReviewRecord:
        row = self._connection.execute(
            "SELECT * FROM synthetic_patch_shadow_review_dockets WHERE shadow_id = ?",
            (shadow_id,),
        ).fetchone()
        if row is None:
            raise GovernanceRejected("unknown patch shadow review docket")
        return self._record_from_row(row)

    @classmethod
    def _record_from_row(cls, row: sqlite3.Row) -> PatchShadowReviewRecord:
        try:
            payload = json.loads(row["assessment_json"])
            cls._validate_stored_payload(payload)
        except (GovernanceRejected, KeyError, TypeError, ValueError) as exc:
            raise GovernanceRejected("stored patch shadow assessment is invalid") from exc
        shadow_id = payload["shadow_id"]
        if (
            row["shadow_id"] != shadow_id
            or payload["proposal_id"] != row["proposal_id"]
            or payload["proposal_digest"] != row["proposal_digest"]
            or payload["source_review_digest"] != row["source_review_digest"]
            or payload["assessment_digest"] != row["shadow_assessment_digest"]
        ):
            raise GovernanceRejected("stored shadow docket binding is invalid")
        return PatchShadowReviewRecord(
            row["shadow_id"],
            row["proposal_id"],
            row["proposal_digest"],
            row["source_review_digest"],
            row["shadow_assessment_digest"],
            PatchShadowReviewState(row["state"]),
            datetime.fromisoformat(row["submitted_at"]),
            datetime.fromisoformat(row["updated_at"]),
            row["submitter_id"],
            bool(row["automatic_review_allowed"]),
            bool(row["patch_content_present"]),
            bool(row["code_change_allowed"]),
            bool(row["automatic_application_allowed"]),
            bool(row["safety_baseline_relaxation_allowed"]),
            bool(row["operator_decision_recorded"]),
            bool(row["execution_allowed"]),
            bool(row["production_activation_allowed"]),
        )

    @staticmethod
    def _validate_stored_payload(payload: object) -> None:
        if not isinstance(payload, dict) or not isinstance(payload.get("item_results"), list):
            raise GovernanceRejected("stored patch shadow assessment object required")
        results = []
        for item in payload["item_results"]:
            if not isinstance(item, dict):
                raise GovernanceRejected("stored shadow item result required")
            results.append(
                SyntheticPatchShadowItemResult(
                    int(item["ordinal"]),
                    str(item["draft_scope"]),
                    str(item["fixture_digest"]),
                    PatchShadowItemDecision(str(item["decision"])),
                    str(item["reason"]),
                    str(item["result_digest"]),
                )
            )
        value = {
            "sequence": payload["sequence"],
            "shadow_id": payload["shadow_id"],
            "proposal_id": payload["proposal_id"],
            "proposal_digest": payload["proposal_digest"],
            "source_review_digest": payload["source_review_digest"],
            "item_result_digests": payload["item_result_digests"],
            "decision": payload["decision"],
            "reason": payload["reason"],
            "evaluated_at": payload["evaluated_at"],
            "previous_digest": payload["previous_digest"],
            "source_docket_state_changed": payload["source_docket_state_changed"],
            "patch_content_present": payload["patch_content_present"],
            "code_change_allowed": payload["code_change_allowed"],
            "automatic_application_allowed": payload["automatic_application_allowed"],
            "safety_baseline_relaxation_allowed": payload[
                "safety_baseline_relaxation_allowed"
            ],
            "execution_allowed": payload["execution_allowed"],
            "production_activation_allowed": payload[
                "production_activation_allowed"
            ],
        }
        if (
            not results
            or payload["item_result_digests"] != [item.result_digest for item in results]
            or any(item.decision is not PatchShadowItemDecision.PASS for item in results)
            or payload.get("decision")
            != PatchShadowDecision.PROPOSED_FOR_ETERNIAN_REVIEW.value
            or payload.get("reason") != "patch_shadow_ready_for_eternian_review"
            or payload.get("source_docket_state_changed") is not False
            or payload.get("patch_content_present") is not False
            or payload.get("code_change_allowed") is not False
            or payload.get("automatic_application_allowed") is not False
            or payload.get("safety_baseline_relaxation_allowed") is not False
            or payload.get("execution_allowed") is not False
            or payload.get("production_activation_allowed") is not False
            or canonical_digest(value) != payload.get("assessment_digest")
        ):
            raise GovernanceRejected("stored patch shadow assessment digest mismatch")

    def get(self, shadow_id: str) -> PatchShadowReviewRecord:
        with self._lock:
            return self._get_record(shadow_id)

    def ready_source(self, shadow_id: str) -> ReadyPatchShadowReviewSource:
        with self._lock:
            if not self.verify_audit_chain() or not self.verify_record_bindings():
                raise GovernanceRejected("patch shadow review evidence is invalid")
            row = self._connection.execute(
                "SELECT * FROM synthetic_patch_shadow_review_dockets WHERE shadow_id = ?",
                (shadow_id,),
            ).fetchone()
            if row is None:
                raise GovernanceRejected("unknown patch shadow review docket")
            self._record_from_row(row)
            if row["state"] != PatchShadowReviewState.READY_FOR_OPERATOR_DECISION.value:
                raise GovernanceRejected("patch shadow result is not ready for operator decision")
            review = self._connection.execute(
                "SELECT * FROM synthetic_patch_shadow_reviews WHERE shadow_id = ?",
                (shadow_id,),
            ).fetchone()
            if review is None or review["decision"] != PatchShadowReviewDecision.PASS.value:
                raise GovernanceRejected("passing patch shadow review source required")
            return ReadyPatchShadowReviewSource(
                row["shadow_id"],
                row["proposal_id"],
                row["proposal_digest"],
                row["source_review_digest"],
                row["shadow_assessment_digest"],
                review["review_digest"],
                row["assessment_json"],
                datetime.fromisoformat(review["reviewed_at"]),
            )

    def verify_audit_chain(self) -> bool:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM synthetic_patch_shadow_review_audit ORDER BY audit_sequence"
            ).fetchall()
            previous = "0" * 64
            for sequence, row in enumerate(rows, start=1):
                value = {
                    "audit_sequence": sequence,
                    "shadow_id": row["shadow_id"],
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
                "SELECT * FROM synthetic_patch_shadow_review_dockets ORDER BY shadow_id"
            ).fetchall()
            reviews = self._connection.execute(
                "SELECT * FROM synthetic_patch_shadow_reviews ORDER BY review_id"
            ).fetchall()
            audits = self._connection.execute(
                "SELECT * FROM synthetic_patch_shadow_review_audit ORDER BY audit_sequence"
            ).fetchall()
            try:
                for docket in dockets:
                    self._record_from_row(docket)
            except (GovernanceRejected, KeyError, TypeError, ValueError):
                return False
            if len(audits) != len(dockets) + len(reviews):
                return False
            audit_by_action = {(row["shadow_id"], row["action"]): row for row in audits}
            review_by_shadow = {row["shadow_id"]: row for row in reviews}
            for docket in dockets:
                submitted = audit_by_action.get(
                    (docket["shadow_id"], "ARKAON_PATCH_SHADOW_RESULT_SUBMITTED")
                )
                if (
                    submitted is None
                    or submitted["state_before"] is not None
                    or submitted["state_after"]
                    != PatchShadowReviewState.PENDING_ETERNIAN_REVIEW.value
                    or submitted["actor_id"] != ARKAON_PATCH_SHADOW_SUBMITTER_ID
                    or submitted["evidence_digest"]
                    != docket["shadow_assessment_digest"]
                    or submitted["recorded_at"] != docket["submitted_at"]
                ):
                    return False
                review = review_by_shadow.get(docket["shadow_id"])
                if review is None:
                    if docket["state"] != PatchShadowReviewState.PENDING_ETERNIAN_REVIEW.value:
                        return False
                    continue
                review_value = {
                    "review_id": review["review_id"],
                    "shadow_id": review["shadow_id"],
                    "reviewer_id": review["reviewer_id"],
                    "decision": review["decision"],
                    "findings_digest": review["findings_digest"],
                    "reviewed_at": review["reviewed_at"],
                }
                target = {
                    "PASS": PatchShadowReviewState.READY_FOR_OPERATOR_DECISION,
                    "HOLD": PatchShadowReviewState.HELD,
                    "REJECT": PatchShadowReviewState.REJECTED,
                }.get(review["decision"])
                audit = audit_by_action.get(
                    (docket["shadow_id"], f"ETERNIAN_PATCH_SHADOW_REVIEW_{review['decision']}")
                )
                if (
                    not review["review_id"].startswith("synthetic:patch-shadow-review:")
                    or len(review["review_id"]) <= len("synthetic:patch-shadow-review:")
                    or not review["reviewer_id"].startswith("synthetic:eternian-reviewer:")
                    or len(review["reviewer_id"])
                    <= len("synthetic:eternian-reviewer:")
                    or not _valid_digest(review["findings_digest"])
                    or canonical_digest(review_value) != review["review_digest"]
                    or target is None
                    or docket["state"] != target.value
                    or docket["updated_at"] != review["reviewed_at"]
                    or audit is None
                    or audit["state_before"]
                    != PatchShadowReviewState.PENDING_ETERNIAN_REVIEW.value
                    or audit["state_after"] != target.value
                    or audit["actor_id"] != review["reviewer_id"]
                    or audit["evidence_digest"] != review["review_digest"]
                    or audit["recorded_at"] != review["reviewed_at"]
                ):
                    return False
            return True

    def evidence(self) -> dict[str, object]:
        with self._lock:
            counts = {state.value: 0 for state in PatchShadowReviewState}
            for row in self._connection.execute(
                "SELECT state, COUNT(*) AS count FROM synthetic_patch_shadow_review_dockets GROUP BY state"
            ):
                counts[row["state"]] = row["count"]
            value = {
                "schema": "nurion.pg.synthetic-patch-shadow-review-docket-evidence.v1",
                "database_engine": "SQLite",
                "schema_version": PATCH_SHADOW_REVIEW_SCHEMA_VERSION,
                "schema_digest": canonical_digest(PATCH_SHADOW_REVIEW_SCHEMA_SQL),
                "state_counts": counts,
                "audit_chain_valid": self.verify_audit_chain(),
                "record_bindings_valid": self.verify_record_bindings(),
                "maximum_state": PatchShadowReviewState.READY_FOR_OPERATOR_DECISION.value,
                "automatic_review_allowed": False,
                "patch_content_present": False,
                "operator_decision_method_present": False,
                "code_change_method_present": False,
                "application_method_present": False,
                "safety_baseline_relaxation_allowed": False,
                "execution_method_present": False,
                "network_access_method_present": False,
                "personal_data_used": False,
                "credentials_used": False,
                "money_movement_executed": False,
                "production_activation_allowed": False,
            }
            return {**value, "report_digest": canonical_digest(value)}
