"""Durable Eternian review docket for synthetic limited promotion plans."""

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
from .patch_draft_promotion_decision_intake import (
    SyntheticPatchDraftPromotionDecision,
)
from .synthetic_patch_draft_limited_promotion_plans import (
    PATCH_DRAFT_LIMITED_PROMOTION_PLAN_STATE,
    SyntheticPatchDraftLimitedPromotionPlan,
    SyntheticPatchDraftLimitedPromotionPlanBook,
)


LIMITED_PROMOTION_REVIEW_SCHEMA_VERSION = 1
MAXIMUM_LIMITED_PROMOTION_REVIEW_STATE = (
    "READY_FOR_SYNTHETIC_PATCH_DRAFT_LIMITED_PROMOTION_SHADOW"
)
_REVIEW_ID_PREFIX = "synthetic:patch-draft-limited-promotion-review:"
_REVIEWER_PREFIX = (
    "synthetic:eternian-reviewer:patch-draft-limited-promotion:"
)
_SUBMITTER_ID = (
    "synthetic:system:patch-draft-limited-promotion-review-docket"
)


class LimitedPromotionPlanReviewState(StrEnum):
    PENDING_ETERNIAN_REVIEW = "PENDING_ETERNIAN_REVIEW"
    READY_FOR_SYNTHETIC_PATCH_DRAFT_LIMITED_PROMOTION_SHADOW = (
        "READY_FOR_SYNTHETIC_PATCH_DRAFT_LIMITED_PROMOTION_SHADOW"
    )
    HELD = "HELD"
    REJECTED = "REJECTED"


class LimitedPromotionPlanReviewDecision(StrEnum):
    PASS = "PASS"
    HOLD = "HOLD"
    REJECT = "REJECT"


_STATE_BY_DECISION = {
    LimitedPromotionPlanReviewDecision.PASS: (
        LimitedPromotionPlanReviewState
        .READY_FOR_SYNTHETIC_PATCH_DRAFT_LIMITED_PROMOTION_SHADOW
    ),
    LimitedPromotionPlanReviewDecision.HOLD: LimitedPromotionPlanReviewState.HELD,
    LimitedPromotionPlanReviewDecision.REJECT: (
        LimitedPromotionPlanReviewState.REJECTED
    ),
}


LIMITED_PROMOTION_REVIEW_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS synthetic_limited_promotion_review_metadata (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    schema_version INTEGER NOT NULL CHECK (schema_version = 1),
    synthetic_only INTEGER NOT NULL CHECK (synthetic_only = 1)
);
CREATE TABLE IF NOT EXISTS synthetic_limited_promotion_review_records (
    plan_id TEXT PRIMARY KEY,
    plan_digest TEXT NOT NULL UNIQUE,
    source_receipt_id TEXT NOT NULL UNIQUE,
    source_receipt_digest TEXT NOT NULL,
    source_packet_id TEXT NOT NULL,
    plan_json TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN (
        'PENDING_ETERNIAN_REVIEW',
        'READY_FOR_SYNTHETIC_PATCH_DRAFT_LIMITED_PROMOTION_SHADOW',
        'HELD', 'REJECTED'
    )),
    submitted_at TEXT NOT NULL,
    review_id TEXT UNIQUE,
    reviewer_id TEXT,
    review_decision TEXT CHECK (review_decision IN ('PASS', 'HOLD', 'REJECT')),
    findings_digest TEXT,
    reviewed_at TEXT,
    review_digest TEXT UNIQUE,
    automatic_review_allowed INTEGER NOT NULL DEFAULT 0
        CHECK (automatic_review_allowed = 0),
    operator_decision_recorded INTEGER NOT NULL DEFAULT 0
        CHECK (operator_decision_recorded = 0),
    candidate_content_present INTEGER NOT NULL DEFAULT 0
        CHECK (candidate_content_present = 0),
    patch_content_present INTEGER NOT NULL DEFAULT 0 CHECK (patch_content_present = 0),
    diff_content_present INTEGER NOT NULL DEFAULT 0 CHECK (diff_content_present = 0),
    source_code_changed INTEGER NOT NULL DEFAULT 0 CHECK (source_code_changed = 0),
    filesystem_written INTEGER NOT NULL DEFAULT 0 CHECK (filesystem_written = 0),
    automatic_application_allowed INTEGER NOT NULL DEFAULT 0
        CHECK (automatic_application_allowed = 0),
    safety_baseline_relaxation_allowed INTEGER NOT NULL DEFAULT 0
        CHECK (safety_baseline_relaxation_allowed = 0),
    execution_allowed INTEGER NOT NULL DEFAULT 0 CHECK (execution_allowed = 0),
    synthetic_activation_allowed INTEGER NOT NULL DEFAULT 0
        CHECK (synthetic_activation_allowed = 0),
    production_activation_allowed INTEGER NOT NULL DEFAULT 0
        CHECK (production_activation_allowed = 0),
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
CREATE TABLE IF NOT EXISTS synthetic_limited_promotion_review_audit (
    audit_sequence INTEGER PRIMARY KEY,
    plan_id TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('SUBMITTED', 'ETERNIAN_REVIEWED')),
    actor_id TEXT NOT NULL,
    evidence_digest TEXT NOT NULL,
    previous_digest TEXT NOT NULL,
    audit_digest TEXT NOT NULL UNIQUE,
    recorded_at TEXT NOT NULL,
    UNIQUE (plan_id, action)
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
class SyntheticPatchDraftLimitedPromotionReviewRecord:
    plan: SyntheticPatchDraftLimitedPromotionPlan
    state: LimitedPromotionPlanReviewState
    submitted_at: datetime
    review_id: str | None = None
    reviewer_id: str | None = None
    review_decision: LimitedPromotionPlanReviewDecision | None = None
    findings_digest: str | None = None
    reviewed_at: datetime | None = None
    review_digest: str | None = None
    automatic_review_allowed: bool = False
    operator_decision_recorded: bool = False
    candidate_content_present: bool = False
    patch_content_present: bool = False
    diff_content_present: bool = False
    source_code_changed: bool = False
    filesystem_written: bool = False
    automatic_application_allowed: bool = False
    safety_baseline_relaxation_allowed: bool = False
    execution_allowed: bool = False
    synthetic_activation_allowed: bool = False
    production_activation_allowed: bool = False

    def __post_init__(self) -> None:
        pending = self.state is LimitedPromotionPlanReviewState.PENDING_ETERNIAN_REVIEW
        review_fields = (
            self.review_id,
            self.reviewer_id,
            self.review_decision,
            self.findings_digest,
            self.reviewed_at,
            self.review_digest,
        )
        forbidden = (
            self.automatic_review_allowed,
            self.operator_decision_recorded,
            self.candidate_content_present,
            self.patch_content_present,
            self.diff_content_present,
            self.source_code_changed,
            self.filesystem_written,
            self.automatic_application_allowed,
            self.safety_baseline_relaxation_allowed,
            self.execution_allowed,
            self.synthetic_activation_allowed,
            self.production_activation_allowed,
        )
        if (
            not isinstance(self.plan, SyntheticPatchDraftLimitedPromotionPlan)
            or self.plan.state != PATCH_DRAFT_LIMITED_PROMOTION_PLAN_STATE
            or self.plan.plan_digest != canonical_digest(self.plan.digest_value())
            or self.submitted_at.tzinfo is None
            or self.submitted_at < self.plan.drafted_at
            or any(forbidden)
            or (pending and any(field is not None for field in review_fields))
            or (not pending and any(field is None for field in review_fields))
        ):
            raise GovernanceRejected(
                "valid synthetic limited promotion review record required"
            )
        if not pending and (
            not _valid_prefixed(self.review_id, _REVIEW_ID_PREFIX)
            or not _valid_prefixed(self.reviewer_id, _REVIEWER_PREFIX)
            or not isinstance(
                self.review_decision, LimitedPromotionPlanReviewDecision
            )
            or self.state != _STATE_BY_DECISION[self.review_decision]
            or not _valid_digest(self.findings_digest)
            or self.reviewed_at.tzinfo is None  # type: ignore[union-attr]
            or self.reviewed_at < self.submitted_at  # type: ignore[operator]
            or self.review_digest != canonical_digest(self.review_value())
        ):
            raise GovernanceRejected(
                "valid independent limited promotion plan review required"
            )

    def review_value(self) -> dict[str, object]:
        return {
            "plan_id": self.plan.plan_id,
            "plan_digest": self.plan.plan_digest,
            "review_id": self.review_id,
            "reviewer_id": self.reviewer_id,
            "decision": (
                self.review_decision.value if self.review_decision else None
            ),
            "findings_digest": self.findings_digest,
            "reviewed_at": (
                self.reviewed_at.isoformat() if self.reviewed_at else None
            ),
            "resulting_state": self.state.value,
            "automatic_review_allowed": False,
            "operator_decision_recorded": False,
            "candidate_content_present": False,
            "patch_content_present": False,
            "diff_content_present": False,
            "source_code_changed": False,
            "filesystem_written": False,
            "automatic_application_allowed": False,
            "safety_baseline_relaxation_allowed": False,
            "execution_allowed": False,
            "synthetic_activation_allowed": False,
            "production_activation_allowed": False,
        }


class SyntheticPatchDraftLimitedPromotionReviewDocket:
    """Persists an independent plan review without activating the plan."""

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
            ".db",
            ".sqlite",
            ".sqlite3",
        }:
            raise GovernanceRejected(
                "synthetic SQLite limited promotion review target required"
            )

    def _initialize_schema(self) -> None:
        with self._lock:
            self._connection.executescript(LIMITED_PROMOTION_REVIEW_SCHEMA_SQL)
            self._connection.execute(
                "INSERT OR IGNORE INTO synthetic_limited_promotion_review_metadata "
                "(singleton, schema_version, synthetic_only) VALUES (1, ?, 1)",
                (LIMITED_PROMOTION_REVIEW_SCHEMA_VERSION,),
            )
            if not self.verify_metadata():
                raise GovernanceRejected(
                    "unsupported limited promotion review schema"
                )

    def verify_metadata(self) -> bool:
        with self._lock:
            rows = self._connection.execute(
                "SELECT singleton, schema_version, synthetic_only "
                "FROM synthetic_limited_promotion_review_metadata"
            ).fetchall()
            return (
                len(rows) == 1
                and rows[0]["singleton"] == 1
                and rows[0]["schema_version"]
                == LIMITED_PROMOTION_REVIEW_SCHEMA_VERSION
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
        book: SyntheticPatchDraftLimitedPromotionPlanBook,
        source_receipt_id: str,
        *,
        submitted_at: datetime,
    ) -> SyntheticPatchDraftLimitedPromotionReviewRecord:
        if submitted_at.tzinfo is None:
            raise GovernanceRejected("timezone-aware plan submission required")
        if not isinstance(book, SyntheticPatchDraftLimitedPromotionPlanBook):
            raise GovernanceRejected("typed limited promotion plan book required")
        if not book.verify_plan_chain():
            raise GovernanceRejected("intact limited promotion plan chain required")
        matches = [
            item for item in book.plans
            if item.source_receipt_id == source_receipt_id
        ]
        if len(matches) != 1:
            raise GovernanceRejected("one synthetic limited promotion plan required")
        plan = matches[0]
        self._validate_plan(plan)
        if submitted_at < plan.drafted_at:
            raise GovernanceRejected("submission cannot predate plan")
        before = book.evidence()["report_digest"]
        payload = {**plan.digest_value(), "plan_digest": plan.plan_digest}

        with self._lock:
            try:
                with self._transaction():
                    if not self.verify_metadata():
                        raise GovernanceRejected(
                            "limited promotion review metadata is invalid"
                        )
                    existing = self._connection.execute(
                        "SELECT * FROM synthetic_limited_promotion_review_records "
                        "WHERE plan_id = ?",
                        (plan.plan_id,),
                    ).fetchone()
                    if existing is not None:
                        if (
                            existing["plan_digest"] != plan.plan_digest
                            or existing["source_receipt_id"] != source_receipt_id
                        ):
                            raise GovernanceRejected(
                                "limited promotion plan submission collision"
                            )
                        if not self.verify_record_bindings():
                            raise GovernanceRejected(
                                "existing limited promotion review is invalid"
                            )
                        record = self._record_from_row(existing)
                    else:
                        self._connection.execute(
                            """
                            INSERT INTO synthetic_limited_promotion_review_records (
                                plan_id, plan_digest, source_receipt_id,
                                source_receipt_digest, source_packet_id, plan_json,
                                state, submitted_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                plan.plan_id,
                                plan.plan_digest,
                                plan.source_receipt_id,
                                plan.source_receipt_digest,
                                plan.source_packet_id,
                                json.dumps(
                                    payload,
                                    ensure_ascii=False,
                                    sort_keys=True,
                                    separators=(",", ":"),
                                ),
                                LimitedPromotionPlanReviewState
                                .PENDING_ETERNIAN_REVIEW.value,
                                submitted_at.isoformat(),
                            ),
                        )
                        self._append_audit(
                            plan.plan_id,
                            "SUBMITTED",
                            _SUBMITTER_ID,
                            plan.plan_digest,
                            submitted_at,
                        )
                        record = self._get_record(plan.plan_id)
                    if before != book.evidence()["report_digest"]:
                        raise GovernanceRejected(
                            "limited promotion plan changed during submission"
                        )
                    return record
            except sqlite3.Error as exc:
                raise GovernanceRejected(
                    "limited promotion plan submission transaction failed"
                ) from exc

    @staticmethod
    def _validate_plan(plan: SyntheticPatchDraftLimitedPromotionPlan) -> None:
        if (
            not isinstance(plan, SyntheticPatchDraftLimitedPromotionPlan)
            or plan.state != PATCH_DRAFT_LIMITED_PROMOTION_PLAN_STATE
            or plan.plan_digest != canonical_digest(plan.digest_value())
            or not plan.synthetic_only
            or not plan.rollback_required
            or not plan.eternian_review_required
            or not plan.operator_reconfirmation_required
            or any(
                (
                    plan.candidate_content_present,
                    plan.patch_content_present,
                    plan.diff_content_present,
                    plan.source_code_changed,
                    plan.filesystem_written,
                    plan.automatic_application_allowed,
                    plan.safety_baseline_relaxation_allowed,
                    plan.execution_allowed,
                    plan.network_access_allowed,
                    plan.money_movement_allowed,
                    plan.production_activation_allowed,
                )
            )
        ):
            raise GovernanceRejected(
                "intact metadata-only limited promotion plan required"
            )

    def record_eternian_review(
        self,
        plan_id: str,
        *,
        review_id: str,
        reviewer_id: str,
        decision: LimitedPromotionPlanReviewDecision,
        findings_digest: str,
        reviewed_at: datetime,
    ) -> SyntheticPatchDraftLimitedPromotionReviewRecord:
        if (
            not _valid_prefixed(review_id, _REVIEW_ID_PREFIX)
            or not _valid_prefixed(reviewer_id, _REVIEWER_PREFIX)
            or not isinstance(decision, LimitedPromotionPlanReviewDecision)
            or not _valid_digest(findings_digest)
            or reviewed_at.tzinfo is None
        ):
            raise GovernanceRejected(
                "valid Eternian limited promotion review metadata required"
            )
        with self._lock:
            try:
                with self._transaction():
                    if not self.verify_metadata():
                        raise GovernanceRejected(
                            "limited promotion review metadata is invalid"
                        )
                    row = self._connection.execute(
                        "SELECT * FROM synthetic_limited_promotion_review_records "
                        "WHERE plan_id = ?",
                        (plan_id,),
                    ).fetchone()
                    if row is None:
                        raise GovernanceRejected(
                            "unknown synthetic limited promotion plan"
                        )
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
                            raise GovernanceRejected(
                                "limited promotion review already recorded"
                            )
                        if not self.verify_record_bindings():
                            raise GovernanceRejected(
                                "existing limited promotion review is invalid"
                            )
                        return current
                    if reviewed_at < current.submitted_at:
                        raise GovernanceRejected("review cannot predate submission")
                    state = _STATE_BY_DECISION[decision]
                    value = {
                        "plan_id": plan_id,
                        "plan_digest": current.plan.plan_digest,
                        "review_id": review_id,
                        "reviewer_id": reviewer_id,
                        "decision": decision.value,
                        "findings_digest": findings_digest,
                        "reviewed_at": reviewed_at.isoformat(),
                        "resulting_state": state.value,
                        "automatic_review_allowed": False,
                        "operator_decision_recorded": False,
                        "candidate_content_present": False,
                        "patch_content_present": False,
                        "diff_content_present": False,
                        "source_code_changed": False,
                        "filesystem_written": False,
                        "automatic_application_allowed": False,
                        "safety_baseline_relaxation_allowed": False,
                        "execution_allowed": False,
                        "synthetic_activation_allowed": False,
                        "production_activation_allowed": False,
                    }
                    review_digest = canonical_digest(value)
                    updated = self._connection.execute(
                        """
                        UPDATE synthetic_limited_promotion_review_records SET
                            state = ?, review_id = ?, reviewer_id = ?,
                            review_decision = ?, findings_digest = ?, reviewed_at = ?,
                            review_digest = ?
                        WHERE plan_id = ? AND state = 'PENDING_ETERNIAN_REVIEW'
                        """,
                        (
                            state.value,
                            review_id,
                            reviewer_id,
                            decision.value,
                            findings_digest,
                            reviewed_at.isoformat(),
                            review_digest,
                            plan_id,
                        ),
                    )
                    if updated.rowcount != 1:
                        raise GovernanceRejected(
                            "limited promotion review state transition failed"
                        )
                    self._append_audit(
                        plan_id,
                        "ETERNIAN_REVIEWED",
                        reviewer_id,
                        review_digest,
                        reviewed_at,
                    )
                    return self._get_record(plan_id)
            except sqlite3.Error as exc:
                raise GovernanceRejected(
                    "limited promotion review transaction failed"
                ) from exc

    def _append_audit(
        self,
        plan_id: str,
        action: str,
        actor_id: str,
        evidence_digest: str,
        recorded_at: datetime,
    ) -> None:
        latest = self._connection.execute(
            "SELECT audit_sequence, audit_digest "
            "FROM synthetic_limited_promotion_review_audit "
            "ORDER BY audit_sequence DESC LIMIT 1"
        ).fetchone()
        sequence = (latest["audit_sequence"] if latest else 0) + 1
        previous = latest["audit_digest"] if latest else "0" * 64
        value = {
            "audit_sequence": sequence,
            "plan_id": plan_id,
            "action": action,
            "actor_id": actor_id,
            "evidence_digest": evidence_digest,
            "previous_digest": previous,
            "recorded_at": recorded_at.isoformat(),
        }
        self._connection.execute(
            "INSERT INTO synthetic_limited_promotion_review_audit "
            "(audit_sequence, plan_id, action, actor_id, evidence_digest, "
            "previous_digest, audit_digest, recorded_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                sequence,
                plan_id,
                action,
                actor_id,
                evidence_digest,
                previous,
                canonical_digest(value),
                recorded_at.isoformat(),
            ),
        )

    @staticmethod
    def _plan_from_payload(
        payload: object,
    ) -> SyntheticPatchDraftLimitedPromotionPlan:
        if not isinstance(payload, dict):
            raise GovernanceRejected("stored limited promotion plan object required")
        return SyntheticPatchDraftLimitedPromotionPlan(
            int(payload["sequence"]),
            str(payload["plan_id"]),
            str(payload["source_receipt_id"]),
            str(payload["source_receipt_digest"]),
            str(payload["source_assessment_id"]),
            str(payload["source_packet_id"]),
            str(payload["operator_id"]),
            SyntheticPatchDraftPromotionDecision(str(payload["decision"])),
            str(payload["promotion_scope"]),
            str(payload["candidate_digest"]),
            str(payload["cohort_digest"]),
            int(payload["synthetic_sample_size"]),
            int(payload["observation_window_seconds"]),
            tuple(str(value) for value in payload["rollback_triggers"]),
            tuple(str(value) for value in payload["required_checks"]),
            datetime.fromisoformat(str(payload["drafted_at"])),
            str(payload["previous_digest"]),
            str(payload["plan_digest"]),
            str(payload["state"]),
            bool(payload["synthetic_only"]),
            bool(payload["rollback_required"]),
            bool(payload["eternian_review_required"]),
            bool(payload["operator_reconfirmation_required"]),
            bool(payload["candidate_content_present"]),
            bool(payload["patch_content_present"]),
            bool(payload["diff_content_present"]),
            bool(payload["source_code_changed"]),
            bool(payload["filesystem_written"]),
            bool(payload["automatic_application_allowed"]),
            bool(payload["safety_baseline_relaxation_allowed"]),
            bool(payload["execution_allowed"]),
            bool(payload["network_access_allowed"]),
            bool(payload["money_movement_allowed"]),
            bool(payload["production_activation_allowed"]),
        )

    @classmethod
    def _record_from_row(
        cls, row: sqlite3.Row
    ) -> SyntheticPatchDraftLimitedPromotionReviewRecord:
        try:
            plan = cls._plan_from_payload(json.loads(row["plan_json"]))
            if (
                plan.plan_id != row["plan_id"]
                or plan.plan_digest != row["plan_digest"]
                or plan.source_receipt_id != row["source_receipt_id"]
                or plan.source_receipt_digest != row["source_receipt_digest"]
                or plan.source_packet_id != row["source_packet_id"]
            ):
                raise GovernanceRejected(
                    "stored limited promotion plan binding is invalid"
                )
            decision = (
                LimitedPromotionPlanReviewDecision(row["review_decision"])
                if row["review_decision"] is not None
                else None
            )
            return SyntheticPatchDraftLimitedPromotionReviewRecord(
                plan,
                LimitedPromotionPlanReviewState(row["state"]),
                datetime.fromisoformat(row["submitted_at"]),
                row["review_id"],
                row["reviewer_id"],
                decision,
                row["findings_digest"],
                (
                    datetime.fromisoformat(row["reviewed_at"])
                    if row["reviewed_at"] is not None
                    else None
                ),
                row["review_digest"],
                bool(row["automatic_review_allowed"]),
                bool(row["operator_decision_recorded"]),
                bool(row["candidate_content_present"]),
                bool(row["patch_content_present"]),
                bool(row["diff_content_present"]),
                bool(row["source_code_changed"]),
                bool(row["filesystem_written"]),
                bool(row["automatic_application_allowed"]),
                bool(row["safety_baseline_relaxation_allowed"]),
                bool(row["execution_allowed"]),
                bool(row["synthetic_activation_allowed"]),
                bool(row["production_activation_allowed"]),
            )
        except (GovernanceRejected, KeyError, TypeError, ValueError) as exc:
            raise GovernanceRejected(
                "stored limited promotion review is invalid"
            ) from exc

    def _get_record(
        self, plan_id: str
    ) -> SyntheticPatchDraftLimitedPromotionReviewRecord:
        row = self._connection.execute(
            "SELECT * FROM synthetic_limited_promotion_review_records "
            "WHERE plan_id = ?",
            (plan_id,),
        ).fetchone()
        if row is None:
            raise GovernanceRejected("unknown synthetic limited promotion plan")
        return self._record_from_row(row)

    def get(
        self, plan_id: str
    ) -> SyntheticPatchDraftLimitedPromotionReviewRecord:
        with self._lock:
            return self._get_record(plan_id)

    def ready_source(
        self, plan_id: str
    ) -> SyntheticPatchDraftLimitedPromotionReviewRecord:
        with self._lock:
            if not self.verify_record_bindings():
                raise GovernanceRejected(
                    "limited promotion review docket is invalid"
                )
            record = self._get_record(plan_id)
            if record.state is not (
                LimitedPromotionPlanReviewState
                .READY_FOR_SYNTHETIC_PATCH_DRAFT_LIMITED_PROMOTION_SHADOW
            ):
                raise GovernanceRejected(
                    "limited promotion plan is not shadow-ready"
                )
            return record

    def verify_audit_chain(self) -> bool:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM synthetic_limited_promotion_review_audit "
                "ORDER BY audit_sequence"
            ).fetchall()
            previous = "0" * 64
            for sequence, row in enumerate(rows, start=1):
                value = {
                    "audit_sequence": sequence,
                    "plan_id": row["plan_id"],
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
                "SELECT * FROM synthetic_limited_promotion_review_records "
                "ORDER BY plan_id"
            ).fetchall()
            audits = self._connection.execute(
                "SELECT * FROM synthetic_limited_promotion_review_audit "
                "ORDER BY audit_sequence"
            ).fetchall()
            by_key = {(row["plan_id"], row["action"]): row for row in audits}
            try:
                for row in rows:
                    record = self._record_from_row(row)
                    submitted = by_key.get((row["plan_id"], "SUBMITTED"))
                    if (
                        submitted is None
                        or submitted["actor_id"] != _SUBMITTER_ID
                        or submitted["evidence_digest"] != row["plan_digest"]
                        or submitted["recorded_at"] != row["submitted_at"]
                    ):
                        return False
                    reviewed = by_key.get(
                        (row["plan_id"], "ETERNIAN_REVIEWED")
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
            expected = sum(
                1 if row["review_id"] is None else 2 for row in rows
            )
            return len(audits) == expected

    def evidence(self) -> dict[str, object]:
        with self._lock:
            counts = {
                state.value: 0 for state in LimitedPromotionPlanReviewState
            }
            record_digests = []
            for row in self._connection.execute(
                "SELECT * FROM synthetic_limited_promotion_review_records "
                "ORDER BY plan_id"
            ):
                counts[row["state"]] += 1
                record = self._record_from_row(row)
                record_digests.append(
                    canonical_digest(
                        {
                            "plan_digest": record.plan.plan_digest,
                            "state": record.state.value,
                            "submitted_at": record.submitted_at.isoformat(),
                            "review_digest": record.review_digest,
                        }
                    )
                )
            latest = self._connection.execute(
                "SELECT audit_digest "
                "FROM synthetic_limited_promotion_review_audit "
                "ORDER BY audit_sequence DESC LIMIT 1"
            ).fetchone()
            value = {
                "schema": (
                    "nurion.pg.synthetic-patch-draft-limited-promotion-review-"
                    "evidence.v1"
                ),
                "database_engine": "SQLite",
                "schema_version": LIMITED_PROMOTION_REVIEW_SCHEMA_VERSION,
                "schema_digest": canonical_digest(
                    LIMITED_PROMOTION_REVIEW_SCHEMA_SQL
                ),
                "metadata_valid": self.verify_metadata(),
                "state_counts": counts,
                "record_digests": record_digests,
                "audit_head_digest": (
                    latest["audit_digest"] if latest else "0" * 64
                ),
                "audit_chain_valid": self.verify_audit_chain(),
                "record_bindings_valid": self.verify_record_bindings(),
                "maximum_state": MAXIMUM_LIMITED_PROMOTION_REVIEW_STATE,
                "automatic_review_allowed": False,
                "operator_decision_recorded": False,
                "candidate_content_present": False,
                "patch_content_present": False,
                "diff_content_present": False,
                "source_code_changed": False,
                "filesystem_written": False,
                "application_method_present": False,
                "safety_baseline_relaxation_method_present": False,
                "execution_method_present": False,
                "synthetic_activation_allowed": False,
                "network_access_method_present": False,
                "personal_data_used": False,
                "credentials_used": False,
                "money_movement_executed": False,
                "production_activation_allowed": False,
            }
            return {**value, "report_digest": canonical_digest(value)}
