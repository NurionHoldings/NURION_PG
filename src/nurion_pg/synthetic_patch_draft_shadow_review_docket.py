"""Durable Eternian review docket for metadata-only patch draft shadow results."""

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
from .synthetic_patch_draft_shadow import (
    PatchDraftShadowDecision,
    PatchDraftShadowItemDecision,
    SyntheticPatchDraftShadowAssessment,
    SyntheticPatchDraftShadowBook,
    SyntheticPatchDraftShadowItemResult,
)


PATCH_DRAFT_SHADOW_REVIEW_SCHEMA_VERSION = 1
MAXIMUM_PATCH_DRAFT_SHADOW_REVIEW_STATE = "READY_FOR_PATCH_DRAFT_OPERATOR_DECISION"
ARKAON_PATCH_DRAFT_SHADOW_SUBMITTER_ID = (
    "synthetic:arkaon:NURION_PG:patch-draft-shadow-evaluator"
)
_REVIEW_ID_PREFIX = "synthetic:patch-draft-shadow-review:"
_REVIEWER_PREFIX = "synthetic:eternian-reviewer:patch-draft-shadow:"


class PatchDraftShadowReviewState(StrEnum):
    PENDING_ETERNIAN_REVIEW = "PENDING_ETERNIAN_REVIEW"
    READY_FOR_PATCH_DRAFT_OPERATOR_DECISION = (
        "READY_FOR_PATCH_DRAFT_OPERATOR_DECISION"
    )
    HELD = "HELD"
    REJECTED = "REJECTED"


class PatchDraftShadowReviewDecision(StrEnum):
    PASS = "PASS"
    HOLD = "HOLD"
    REJECT = "REJECT"


_STATE_BY_DECISION = {
    PatchDraftShadowReviewDecision.PASS: (
        PatchDraftShadowReviewState.READY_FOR_PATCH_DRAFT_OPERATOR_DECISION
    ),
    PatchDraftShadowReviewDecision.HOLD: PatchDraftShadowReviewState.HELD,
    PatchDraftShadowReviewDecision.REJECT: PatchDraftShadowReviewState.REJECTED,
}


PATCH_DRAFT_SHADOW_REVIEW_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS synthetic_patch_draft_shadow_review_metadata (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    schema_version INTEGER NOT NULL CHECK (schema_version = 1),
    synthetic_only INTEGER NOT NULL CHECK (synthetic_only = 1)
);
CREATE TABLE IF NOT EXISTS synthetic_patch_draft_shadow_review_records (
    shadow_id TEXT PRIMARY KEY,
    manifest_id TEXT NOT NULL UNIQUE,
    manifest_digest TEXT NOT NULL,
    source_review_digest TEXT NOT NULL,
    shadow_assessment_digest TEXT NOT NULL UNIQUE,
    assessment_json TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN (
        'PENDING_ETERNIAN_REVIEW',
        'READY_FOR_PATCH_DRAFT_OPERATOR_DECISION',
        'HELD', 'REJECTED'
    )),
    submitted_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    submitter_id TEXT NOT NULL CHECK (
        submitter_id = 'synthetic:arkaon:NURION_PG:patch-draft-shadow-evaluator'
    ),
    review_id TEXT UNIQUE,
    reviewer_id TEXT,
    review_decision TEXT CHECK (review_decision IN ('PASS', 'HOLD', 'REJECT')),
    findings_digest TEXT,
    reviewed_at TEXT,
    review_digest TEXT UNIQUE,
    automatic_review_allowed INTEGER NOT NULL DEFAULT 0 CHECK (automatic_review_allowed = 0),
    operator_decision_recorded INTEGER NOT NULL DEFAULT 0 CHECK (operator_decision_recorded = 0),
    patch_content_present INTEGER NOT NULL DEFAULT 0 CHECK (patch_content_present = 0),
    diff_content_present INTEGER NOT NULL DEFAULT 0 CHECK (diff_content_present = 0),
    source_code_changed INTEGER NOT NULL DEFAULT 0 CHECK (source_code_changed = 0),
    filesystem_written INTEGER NOT NULL DEFAULT 0 CHECK (filesystem_written = 0),
    automatic_application_allowed INTEGER NOT NULL DEFAULT 0 CHECK (automatic_application_allowed = 0),
    safety_baseline_relaxation_allowed INTEGER NOT NULL DEFAULT 0 CHECK (safety_baseline_relaxation_allowed = 0),
    execution_allowed INTEGER NOT NULL DEFAULT 0 CHECK (execution_allowed = 0),
    production_activation_allowed INTEGER NOT NULL DEFAULT 0 CHECK (production_activation_allowed = 0),
    CHECK (
        (state = 'PENDING_ETERNIAN_REVIEW'
            AND review_id IS NULL AND reviewer_id IS NULL
            AND review_decision IS NULL AND findings_digest IS NULL
            AND reviewed_at IS NULL AND review_digest IS NULL)
        OR
        (state != 'PENDING_ETERNIAN_REVIEW'
            AND review_id IS NOT NULL AND reviewer_id IS NOT NULL
            AND review_decision IS NOT NULL AND findings_digest IS NOT NULL
            AND reviewed_at IS NOT NULL AND review_digest IS NOT NULL)
    )
);
CREATE TABLE IF NOT EXISTS synthetic_patch_draft_shadow_review_audit (
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


def _valid_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _valid_prefixed(value: object, prefix: str) -> bool:
    return isinstance(value, str) and value.startswith(prefix) and len(value) > len(prefix)


@dataclass(frozen=True)
class SyntheticPatchDraftShadowReviewRecord:
    shadow_id: str
    manifest_id: str
    manifest_digest: str
    source_review_digest: str
    shadow_assessment_digest: str
    state: PatchDraftShadowReviewState
    submitted_at: datetime
    updated_at: datetime
    review_id: str | None = None
    reviewer_id: str | None = None
    review_decision: PatchDraftShadowReviewDecision | None = None
    findings_digest: str | None = None
    reviewed_at: datetime | None = None
    review_digest: str | None = None
    submitter_id: str = ARKAON_PATCH_DRAFT_SHADOW_SUBMITTER_ID
    automatic_review_allowed: bool = False
    operator_decision_recorded: bool = False
    patch_content_present: bool = False
    diff_content_present: bool = False
    source_code_changed: bool = False
    filesystem_written: bool = False
    automatic_application_allowed: bool = False
    safety_baseline_relaxation_allowed: bool = False
    execution_allowed: bool = False
    production_activation_allowed: bool = False

    def __post_init__(self) -> None:
        pending = self.state is PatchDraftShadowReviewState.PENDING_ETERNIAN_REVIEW
        review_fields = (
            self.review_id, self.reviewer_id, self.review_decision,
            self.findings_digest, self.reviewed_at, self.review_digest,
        )
        forbidden = (
            self.automatic_review_allowed, self.operator_decision_recorded,
            self.patch_content_present, self.diff_content_present,
            self.source_code_changed, self.filesystem_written,
            self.automatic_application_allowed,
            self.safety_baseline_relaxation_allowed, self.execution_allowed,
            self.production_activation_allowed,
        )
        if (
            not _valid_prefixed(self.shadow_id, "synthetic:patch-draft-shadow:")
            or not _valid_prefixed(self.manifest_id, "synthetic:patch-draft-manifest:")
            or not _valid_digest(self.manifest_digest)
            or not _valid_digest(self.source_review_digest)
            or not _valid_digest(self.shadow_assessment_digest)
            or self.submitted_at.tzinfo is None
            or self.updated_at.tzinfo is None
            or self.updated_at < self.submitted_at
            or self.submitter_id != ARKAON_PATCH_DRAFT_SHADOW_SUBMITTER_ID
            or any(forbidden)
            or (pending and any(field is not None for field in review_fields))
            or (not pending and any(field is None for field in review_fields))
        ):
            raise GovernanceRejected("valid non-authorizing patch draft shadow review required")
        if not pending and (
            not _valid_prefixed(self.review_id, _REVIEW_ID_PREFIX)
            or not _valid_prefixed(self.reviewer_id, _REVIEWER_PREFIX)
            or not isinstance(self.review_decision, PatchDraftShadowReviewDecision)
            or self.state != _STATE_BY_DECISION[self.review_decision]
            or not _valid_digest(self.findings_digest)
            or self.reviewed_at.tzinfo is None  # type: ignore[union-attr]
            or self.reviewed_at < self.submitted_at  # type: ignore[operator]
            or self.review_digest != canonical_digest(self.review_value())
        ):
            raise GovernanceRejected("valid independent patch draft shadow review required")

    def review_value(self) -> dict[str, object]:
        return {
            "shadow_id": self.shadow_id,
            "shadow_assessment_digest": self.shadow_assessment_digest,
            "review_id": self.review_id,
            "reviewer_id": self.reviewer_id,
            "decision": self.review_decision.value if self.review_decision else None,
            "findings_digest": self.findings_digest,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "resulting_state": self.state.value,
        }


@dataclass(frozen=True)
class ReadyPatchDraftShadowReviewSource:
    shadow_id: str
    manifest_id: str
    manifest_digest: str
    source_review_digest: str
    shadow_assessment_digest: str
    review_digest: str
    assessment_json: str
    reviewed_at: datetime

    def __post_init__(self) -> None:
        if (
            not _valid_prefixed(self.shadow_id, "synthetic:patch-draft-shadow:")
            or not _valid_prefixed(self.manifest_id, "synthetic:patch-draft-manifest:")
            or not all(_valid_digest(item) for item in (
                self.manifest_digest, self.source_review_digest,
                self.shadow_assessment_digest, self.review_digest,
            ))
            or not self.assessment_json
            or self.reviewed_at.tzinfo is None
        ):
            raise GovernanceRejected("complete patch draft shadow review source required")


class SyntheticPatchDraftShadowReviewDocket:
    """Persists shadow evidence and independent review without approval or execution."""

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
            raise GovernanceRejected("synthetic SQLite patch draft shadow review target required")

    def _initialize_schema(self) -> None:
        with self._lock:
            self._connection.executescript(PATCH_DRAFT_SHADOW_REVIEW_SCHEMA_SQL)
            self._connection.execute(
                "INSERT OR IGNORE INTO synthetic_patch_draft_shadow_review_metadata "
                "(singleton, schema_version, synthetic_only) VALUES (1, ?, 1)",
                (PATCH_DRAFT_SHADOW_REVIEW_SCHEMA_VERSION,),
            )
            if not self.verify_metadata():
                raise GovernanceRejected("unsupported patch draft shadow review schema")

    def verify_metadata(self) -> bool:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM synthetic_patch_draft_shadow_review_metadata"
            ).fetchall()
            return (
                len(rows) == 1
                and rows[0]["singleton"] == 1
                and rows[0]["schema_version"] == PATCH_DRAFT_SHADOW_REVIEW_SCHEMA_VERSION
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
        book: SyntheticPatchDraftShadowBook,
        manifest_id: str,
        *,
        submitted_at: datetime,
    ) -> SyntheticPatchDraftShadowReviewRecord:
        if submitted_at.tzinfo is None:
            raise GovernanceRejected("timezone-aware shadow review submission required")
        if not isinstance(book, SyntheticPatchDraftShadowBook):
            raise GovernanceRejected("typed patch draft shadow book required")
        if not book.verify_assessment_chain():
            raise GovernanceRejected("patch draft shadow assessment chain is invalid")
        matches = [item for item in book.assessments if item.manifest_id == manifest_id]
        if len(matches) != 1:
            raise GovernanceRejected("one patch draft shadow assessment required")
        assessment = matches[0]
        self._validate_assessment(assessment)
        if submitted_at < assessment.evaluated_at:
            raise GovernanceRejected("shadow review submission cannot predate assessment")
        payload = self._assessment_payload(assessment)
        payload_json = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        with self._lock:
            try:
                with self._transaction():
                    row = self._connection.execute(
                        "SELECT * FROM synthetic_patch_draft_shadow_review_records "
                        "WHERE shadow_id = ?", (assessment.shadow_id,),
                    ).fetchone()
                    if row is not None:
                        if (
                            row["manifest_id"] != manifest_id
                            or row["shadow_assessment_digest"] != assessment.assessment_digest
                            or row["submitted_at"] != submitted_at.isoformat()
                        ):
                            raise GovernanceRejected("patch draft shadow docket identity collision")
                        if not self.verify_audit_chain() or not self.verify_record_bindings():
                            raise GovernanceRejected("existing shadow review evidence is invalid")
                        return self._record_from_row(row)
                    self._connection.execute(
                        """
                        INSERT INTO synthetic_patch_draft_shadow_review_records (
                            shadow_id, manifest_id, manifest_digest, source_review_digest,
                            shadow_assessment_digest, assessment_json, state,
                            submitted_at, updated_at, submitter_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            assessment.shadow_id, manifest_id, assessment.manifest_digest,
                            assessment.source_review_digest, assessment.assessment_digest,
                            payload_json,
                            PatchDraftShadowReviewState.PENDING_ETERNIAN_REVIEW.value,
                            submitted_at.isoformat(), submitted_at.isoformat(),
                            ARKAON_PATCH_DRAFT_SHADOW_SUBMITTER_ID,
                        ),
                    )
                    self._append_audit(
                        shadow_id=assessment.shadow_id,
                        action="ARKAON_PATCH_DRAFT_SHADOW_RESULT_SUBMITTED",
                        state_before=None,
                        state_after=PatchDraftShadowReviewState.PENDING_ETERNIAN_REVIEW,
                        actor_id=ARKAON_PATCH_DRAFT_SHADOW_SUBMITTER_ID,
                        evidence_digest=assessment.assessment_digest,
                        recorded_at=submitted_at,
                    )
                    return self._get_record(assessment.shadow_id)
            except sqlite3.Error as exc:
                raise GovernanceRejected("patch draft shadow review transaction failed") from exc

    @staticmethod
    def _validate_assessment(assessment: SyntheticPatchDraftShadowAssessment) -> None:
        if (
            assessment.decision is not PatchDraftShadowDecision.PROPOSED_FOR_ETERNIAN_REVIEW
            or assessment.reason != "patch_draft_shadow_ready_for_eternian_review"
            or assessment.assessment_digest != canonical_digest(assessment.digest_value())
            or not assessment.item_results
            or any((
                assessment.source_docket_state_changed,
                assessment.patch_content_present, assessment.diff_content_present,
                assessment.source_code_changed, assessment.filesystem_written,
                assessment.automatic_application_allowed,
                assessment.safety_baseline_relaxation_allowed,
                assessment.execution_allowed, assessment.production_activation_allowed,
            ))
        ):
            raise GovernanceRejected("reviewable non-executing shadow assessment required")
        if any(
            item.decision is not PatchDraftShadowItemDecision.PASS
            or item.reason != "all_patch_draft_shadow_controls_passed"
            or item.result_digest != canonical_digest(item.digest_value())
            for item in assessment.item_results
        ):
            raise GovernanceRejected("all patch draft shadow items must pass")

    @staticmethod
    def _assessment_payload(
        assessment: SyntheticPatchDraftShadowAssessment,
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
        decision: PatchDraftShadowReviewDecision,
        findings_digest: str,
        reviewed_at: datetime,
    ) -> SyntheticPatchDraftShadowReviewRecord:
        if (
            not _valid_prefixed(review_id, _REVIEW_ID_PREFIX)
            or not _valid_prefixed(reviewer_id, _REVIEWER_PREFIX)
            or not isinstance(decision, PatchDraftShadowReviewDecision)
            or not _valid_digest(findings_digest)
            or reviewed_at.tzinfo is None
        ):
            raise GovernanceRejected("complete independent shadow review required")
        target = _STATE_BY_DECISION[decision]
        review_value = {
            "shadow_id": shadow_id,
            "shadow_assessment_digest": None,
            "review_id": review_id,
            "reviewer_id": reviewer_id,
            "decision": decision.value,
            "findings_digest": findings_digest,
            "reviewed_at": reviewed_at.isoformat(),
            "resulting_state": target.value,
        }
        with self._lock:
            try:
                with self._transaction():
                    row = self._connection.execute(
                        "SELECT * FROM synthetic_patch_draft_shadow_review_records "
                        "WHERE shadow_id = ?", (shadow_id,),
                    ).fetchone()
                    if row is None:
                        raise GovernanceRejected("unknown patch draft shadow review docket")
                    review_value["shadow_assessment_digest"] = row["shadow_assessment_digest"]
                    review_digest = canonical_digest(review_value)
                    existing = self._connection.execute(
                        "SELECT * FROM synthetic_patch_draft_shadow_review_records "
                        "WHERE review_id = ?", (review_id,),
                    ).fetchone()
                    if existing is not None:
                        if existing["review_digest"] != review_digest:
                            raise GovernanceRejected("shadow review idempotency mismatch")
                        if not self.verify_audit_chain() or not self.verify_record_bindings():
                            raise GovernanceRejected("existing shadow review evidence is invalid")
                        return self._record_from_row(existing)
                    if not self.verify_audit_chain() or not self.verify_record_bindings():
                        raise GovernanceRejected("patch draft shadow review evidence is invalid")
                    if reviewed_at < datetime.fromisoformat(row["submitted_at"]):
                        raise GovernanceRejected("shadow review cannot predate submission")
                    if row["state"] != PatchDraftShadowReviewState.PENDING_ETERNIAN_REVIEW.value:
                        raise GovernanceRejected("patch draft shadow is not pending review")
                    self._connection.execute(
                        """
                        UPDATE synthetic_patch_draft_shadow_review_records
                        SET state = ?, updated_at = ?, review_id = ?, reviewer_id = ?,
                            review_decision = ?, findings_digest = ?, reviewed_at = ?,
                            review_digest = ?
                        WHERE shadow_id = ?
                        """,
                        (
                            target.value, reviewed_at.isoformat(), review_id, reviewer_id,
                            decision.value, findings_digest, reviewed_at.isoformat(),
                            review_digest, shadow_id,
                        ),
                    )
                    self._append_audit(
                        shadow_id=shadow_id,
                        action=f"ETERNIAN_PATCH_DRAFT_SHADOW_REVIEW_{decision.value}",
                        state_before=PatchDraftShadowReviewState.PENDING_ETERNIAN_REVIEW,
                        state_after=target,
                        actor_id=reviewer_id,
                        evidence_digest=review_digest,
                        recorded_at=reviewed_at,
                    )
                    return self._get_record(shadow_id)
            except sqlite3.Error as exc:
                raise GovernanceRejected("patch draft shadow review transaction failed") from exc

    def _append_audit(
        self, *, shadow_id: str, action: str,
        state_before: PatchDraftShadowReviewState | None,
        state_after: PatchDraftShadowReviewState, actor_id: str,
        evidence_digest: str, recorded_at: datetime,
    ) -> None:
        latest = self._connection.execute(
            "SELECT * FROM synthetic_patch_draft_shadow_review_audit "
            "ORDER BY audit_sequence DESC LIMIT 1"
        ).fetchone()
        sequence = (latest["audit_sequence"] if latest else 0) + 1
        previous = latest["audit_digest"] if latest else "0" * 64
        value = {
            "audit_sequence": sequence, "shadow_id": shadow_id, "action": action,
            "state_before": state_before.value if state_before else None,
            "state_after": state_after.value, "actor_id": actor_id,
            "evidence_digest": evidence_digest, "previous_digest": previous,
            "recorded_at": recorded_at.isoformat(),
        }
        self._connection.execute(
            "INSERT INTO synthetic_patch_draft_shadow_review_audit VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                sequence, shadow_id, action, value["state_before"], state_after.value,
                actor_id, evidence_digest, previous, canonical_digest(value),
                recorded_at.isoformat(),
            ),
        )

    def _get_record(self, shadow_id: str) -> SyntheticPatchDraftShadowReviewRecord:
        row = self._connection.execute(
            "SELECT * FROM synthetic_patch_draft_shadow_review_records WHERE shadow_id = ?",
            (shadow_id,),
        ).fetchone()
        if row is None:
            raise GovernanceRejected("unknown patch draft shadow review docket")
        return self._record_from_row(row)

    @classmethod
    def _record_from_row(cls, row: sqlite3.Row) -> SyntheticPatchDraftShadowReviewRecord:
        try:
            payload = json.loads(row["assessment_json"])
            cls._validate_stored_payload(payload)
        except (GovernanceRejected, KeyError, TypeError, ValueError) as exc:
            raise GovernanceRejected("stored patch draft shadow assessment is invalid") from exc
        if (
            payload["shadow_id"] != row["shadow_id"]
            or payload["manifest_id"] != row["manifest_id"]
            or payload["manifest_digest"] != row["manifest_digest"]
            or payload["source_review_digest"] != row["source_review_digest"]
            or payload["assessment_digest"] != row["shadow_assessment_digest"]
        ):
            raise GovernanceRejected("stored patch draft shadow binding is invalid")
        return SyntheticPatchDraftShadowReviewRecord(
            row["shadow_id"], row["manifest_id"], row["manifest_digest"],
            row["source_review_digest"], row["shadow_assessment_digest"],
            PatchDraftShadowReviewState(row["state"]),
            datetime.fromisoformat(row["submitted_at"]),
            datetime.fromisoformat(row["updated_at"]),
            row["review_id"], row["reviewer_id"],
            PatchDraftShadowReviewDecision(row["review_decision"])
            if row["review_decision"] else None,
            row["findings_digest"],
            datetime.fromisoformat(row["reviewed_at"]) if row["reviewed_at"] else None,
            row["review_digest"], row["submitter_id"],
            bool(row["automatic_review_allowed"]),
            bool(row["operator_decision_recorded"]),
            bool(row["patch_content_present"]), bool(row["diff_content_present"]),
            bool(row["source_code_changed"]), bool(row["filesystem_written"]),
            bool(row["automatic_application_allowed"]),
            bool(row["safety_baseline_relaxation_allowed"]),
            bool(row["execution_allowed"]), bool(row["production_activation_allowed"]),
        )

    @staticmethod
    def _validate_stored_payload(payload: object) -> None:
        if not isinstance(payload, dict) or not isinstance(payload.get("item_results"), list):
            raise GovernanceRejected("stored patch draft shadow object required")
        results = []
        for item in payload["item_results"]:
            if not isinstance(item, dict):
                raise GovernanceRejected("stored patch draft shadow item required")
            results.append(SyntheticPatchDraftShadowItemResult(
                int(item["ordinal"]), str(item["draft_scope"]),
                str(item["target_path_digest"]), str(item["fixture_digest"]),
                PatchDraftShadowItemDecision(str(item["decision"])),
                str(item["reason"]), str(item["result_digest"]),
            ))
        value = {
            key: payload[key] for key in (
                "sequence", "shadow_id", "manifest_id", "manifest_digest",
                "source_review_digest", "item_result_digests", "decision", "reason",
                "evaluated_at", "previous_digest", "source_docket_state_changed",
                "patch_content_present", "diff_content_present", "source_code_changed",
                "filesystem_written", "automatic_application_allowed",
                "safety_baseline_relaxation_allowed", "execution_allowed",
                "production_activation_allowed",
            )
        }
        if (
            not results
            or payload["item_result_digests"] != [item.result_digest for item in results]
            or any(item.decision is not PatchDraftShadowItemDecision.PASS for item in results)
            or payload["decision"] != PatchDraftShadowDecision.PROPOSED_FOR_ETERNIAN_REVIEW.value
            or payload["reason"] != "patch_draft_shadow_ready_for_eternian_review"
            or any(payload[field] is not False for field in (
                "source_docket_state_changed", "patch_content_present",
                "diff_content_present", "source_code_changed", "filesystem_written",
                "automatic_application_allowed", "safety_baseline_relaxation_allowed",
                "execution_allowed", "production_activation_allowed",
            ))
            or canonical_digest(value) != payload.get("assessment_digest")
        ):
            raise GovernanceRejected("stored patch draft shadow digest mismatch")
        SyntheticPatchDraftShadowAssessment(
            int(payload["sequence"]),
            str(payload["shadow_id"]),
            str(payload["manifest_id"]),
            str(payload["manifest_digest"]),
            str(payload["source_review_digest"]),
            tuple(results),
            PatchDraftShadowDecision(str(payload["decision"])),
            str(payload["reason"]),
            datetime.fromisoformat(str(payload["evaluated_at"])),
            str(payload["previous_digest"]),
            str(payload["assessment_digest"]),
        )

    def get(self, shadow_id: str) -> SyntheticPatchDraftShadowReviewRecord:
        with self._lock:
            return self._get_record(shadow_id)

    def ready_source(self, shadow_id: str) -> ReadyPatchDraftShadowReviewSource:
        with self._lock:
            if not self.verify_audit_chain() or not self.verify_record_bindings():
                raise GovernanceRejected("patch draft shadow review evidence is invalid")
            row = self._connection.execute(
                "SELECT * FROM synthetic_patch_draft_shadow_review_records "
                "WHERE shadow_id = ?", (shadow_id,),
            ).fetchone()
            if row is None:
                raise GovernanceRejected("unknown patch draft shadow review docket")
            record = self._record_from_row(row)
            if record.state is not PatchDraftShadowReviewState.READY_FOR_PATCH_DRAFT_OPERATOR_DECISION:
                raise GovernanceRejected("patch draft shadow is not ready for operator decision")
            return ReadyPatchDraftShadowReviewSource(
                row["shadow_id"], row["manifest_id"], row["manifest_digest"],
                row["source_review_digest"], row["shadow_assessment_digest"],
                row["review_digest"], row["assessment_json"],
                datetime.fromisoformat(row["reviewed_at"]),
            )

    def verify_audit_chain(self) -> bool:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM synthetic_patch_draft_shadow_review_audit "
                "ORDER BY audit_sequence"
            ).fetchall()
            previous = "0" * 64
            for sequence, row in enumerate(rows, start=1):
                value = {
                    "audit_sequence": sequence, "shadow_id": row["shadow_id"],
                    "action": row["action"], "state_before": row["state_before"],
                    "state_after": row["state_after"], "actor_id": row["actor_id"],
                    "evidence_digest": row["evidence_digest"],
                    "previous_digest": previous, "recorded_at": row["recorded_at"],
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
            rows = self._connection.execute(
                "SELECT * FROM synthetic_patch_draft_shadow_review_records"
            ).fetchall()
            try:
                records = [self._record_from_row(row) for row in rows]
            except (GovernanceRejected, ValueError):
                return False
            return all(
                (record.state is PatchDraftShadowReviewState.PENDING_ETERNIAN_REVIEW)
                == (record.review_id is None)
                for record in records
            )

    def evidence(self) -> dict[str, object]:
        with self._lock:
            records = self._connection.execute(
                "SELECT state, shadow_assessment_digest, review_digest "
                "FROM synthetic_patch_draft_shadow_review_records ORDER BY shadow_id"
            ).fetchall()
            audits = self._connection.execute(
                "SELECT audit_digest FROM synthetic_patch_draft_shadow_review_audit "
                "ORDER BY audit_sequence"
            ).fetchall()
            report = {
                "schema": "nurion.pg.synthetic-patch-draft-shadow-review-evidence.v1",
                "mode": "UNREGISTERED_SYNTHETIC_ONLY",
                "review_authority": "ETERNIAN_INDEPENDENT_REVIEW",
                "maximum_state": MAXIMUM_PATCH_DRAFT_SHADOW_REVIEW_STATE,
                "record_count": len(records),
                "assessment_digests": [row["shadow_assessment_digest"] for row in records],
                "review_digests": [row["review_digest"] for row in records if row["review_digest"]],
                "audit_digests": [row["audit_digest"] for row in audits],
                "audit_chain_valid": self.verify_audit_chain(),
                "record_bindings_valid": self.verify_record_bindings(),
                "automatic_review_allowed": False,
                "operator_decision_method_present": False,
                "operator_decision_recorded": False,
                "patch_content_present": False,
                "diff_content_present": False,
                "source_code_changed": False,
                "filesystem_written": False,
                "application_method_present": False,
                "safety_baseline_relaxation_method_present": False,
                "execution_method_present": False,
                "network_access_method_present": False,
                "personal_data_used": False,
                "credentials_used": False,
                "money_movement_executed": False,
                "production_activation_allowed": False,
            }
            return {**report, "report_digest": canonical_digest(report)}
