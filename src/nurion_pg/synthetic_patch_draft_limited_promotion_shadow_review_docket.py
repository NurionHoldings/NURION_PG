"""Durable independent review of synthetic limited promotion shadow results."""

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
from .synthetic_patch_draft_limited_promotion_shadow import (
    LimitedPromotionShadowDecision,
    LimitedPromotionShadowItemDecision,
    SyntheticPatchDraftLimitedPromotionObservationResult,
    SyntheticPatchDraftLimitedPromotionShadowAssessment,
    SyntheticPatchDraftLimitedPromotionShadowBook,
)


LIMITED_PROMOTION_SHADOW_REVIEW_SCHEMA_VERSION = 1
MAXIMUM_LIMITED_PROMOTION_SHADOW_REVIEW_STATE = (
    "READY_FOR_PATCH_DRAFT_LIMITED_PROMOTION_OPERATOR_RECONFIRMATION"
)
ARKAON_LIMITED_PROMOTION_SHADOW_SUBMITTER_ID = (
    "synthetic:arkaon:NURION_PG:limited-promotion-shadow-evaluator"
)
_REVIEW_ID_PREFIX = (
    "synthetic:patch-draft-limited-promotion-shadow-review:"
)
_REVIEWER_PREFIX = (
    "synthetic:eternian-reviewer:patch-draft-limited-promotion-shadow:"
)


class LimitedPromotionShadowReviewState(StrEnum):
    PENDING_ETERNIAN_REVIEW = "PENDING_ETERNIAN_REVIEW"
    READY_FOR_PATCH_DRAFT_LIMITED_PROMOTION_OPERATOR_RECONFIRMATION = (
        "READY_FOR_PATCH_DRAFT_LIMITED_PROMOTION_OPERATOR_RECONFIRMATION"
    )
    ROLLBACK_REQUIRED_CONFIRMED = "ROLLBACK_REQUIRED_CONFIRMED"
    HELD = "HELD"
    REJECTED = "REJECTED"


class LimitedPromotionShadowReviewDecision(StrEnum):
    PASS = "PASS"
    HOLD = "HOLD"
    REJECT = "REJECT"


def _target_state(
    shadow_decision: LimitedPromotionShadowDecision,
    review_decision: LimitedPromotionShadowReviewDecision,
) -> LimitedPromotionShadowReviewState:
    if review_decision is LimitedPromotionShadowReviewDecision.HOLD:
        return LimitedPromotionShadowReviewState.HELD
    if review_decision is LimitedPromotionShadowReviewDecision.REJECT:
        return LimitedPromotionShadowReviewState.REJECTED
    if (
        shadow_decision
        is LimitedPromotionShadowDecision.PROPOSED_FOR_ETERNIAN_REVIEW
    ):
        return (
            LimitedPromotionShadowReviewState
            .READY_FOR_PATCH_DRAFT_LIMITED_PROMOTION_OPERATOR_RECONFIRMATION
        )
    return LimitedPromotionShadowReviewState.ROLLBACK_REQUIRED_CONFIRMED


LIMITED_PROMOTION_SHADOW_REVIEW_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS synthetic_limited_promotion_shadow_review_metadata (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    schema_version INTEGER NOT NULL CHECK (schema_version = 1),
    synthetic_only INTEGER NOT NULL CHECK (synthetic_only = 1)
);
CREATE TABLE IF NOT EXISTS synthetic_limited_promotion_shadow_review_records (
    shadow_id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL UNIQUE,
    plan_digest TEXT NOT NULL,
    source_review_digest TEXT NOT NULL,
    shadow_assessment_digest TEXT NOT NULL UNIQUE,
    shadow_decision TEXT NOT NULL CHECK (
        shadow_decision IN ('PROPOSED_FOR_ETERNIAN_REVIEW', 'ROLLBACK_REQUIRED')
    ),
    assessment_json TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN (
        'PENDING_ETERNIAN_REVIEW',
        'READY_FOR_PATCH_DRAFT_LIMITED_PROMOTION_OPERATOR_RECONFIRMATION',
        'ROLLBACK_REQUIRED_CONFIRMED', 'HELD', 'REJECTED'
    )),
    submitted_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    submitter_id TEXT NOT NULL CHECK (
        submitter_id =
        'synthetic:arkaon:NURION_PG:limited-promotion-shadow-evaluator'
    ),
    review_id TEXT UNIQUE,
    reviewer_id TEXT,
    review_decision TEXT CHECK (review_decision IN ('PASS', 'HOLD', 'REJECT')),
    findings_digest TEXT,
    reviewed_at TEXT,
    review_digest TEXT UNIQUE,
    automatic_review_allowed INTEGER NOT NULL DEFAULT 0
        CHECK (automatic_review_allowed = 0),
    operator_reconfirmation_recorded INTEGER NOT NULL DEFAULT 0
        CHECK (operator_reconfirmation_recorded = 0),
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
CREATE TABLE IF NOT EXISTS synthetic_limited_promotion_shadow_review_audit (
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
class SyntheticPatchDraftLimitedPromotionShadowReviewRecord:
    assessment: SyntheticPatchDraftLimitedPromotionShadowAssessment
    state: LimitedPromotionShadowReviewState
    submitted_at: datetime
    updated_at: datetime
    review_id: str | None = None
    reviewer_id: str | None = None
    review_decision: LimitedPromotionShadowReviewDecision | None = None
    findings_digest: str | None = None
    reviewed_at: datetime | None = None
    review_digest: str | None = None
    submitter_id: str = ARKAON_LIMITED_PROMOTION_SHADOW_SUBMITTER_ID
    automatic_review_allowed: bool = False
    operator_reconfirmation_recorded: bool = False
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
        pending = self.state is LimitedPromotionShadowReviewState.PENDING_ETERNIAN_REVIEW
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
            self.operator_reconfirmation_recorded,
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
            not isinstance(
                self.assessment,
                SyntheticPatchDraftLimitedPromotionShadowAssessment,
            )
            or self.assessment.assessment_digest
            != canonical_digest(self.assessment.digest_value())
            or self.submitted_at.tzinfo is None
            or self.submitted_at < self.assessment.evaluated_at
            or self.updated_at.tzinfo is None
            or self.updated_at < self.submitted_at
            or self.submitter_id
            != ARKAON_LIMITED_PROMOTION_SHADOW_SUBMITTER_ID
            or any(forbidden)
            or (pending and any(field is not None for field in review_fields))
            or (not pending and any(field is None for field in review_fields))
        ):
            raise GovernanceRejected(
                "valid synthetic limited promotion shadow review record required"
            )
        if not pending and (
            not _valid_prefixed(self.review_id, _REVIEW_ID_PREFIX)
            or not _valid_prefixed(self.reviewer_id, _REVIEWER_PREFIX)
            or not isinstance(
                self.review_decision, LimitedPromotionShadowReviewDecision
            )
            or self.state
            != _target_state(
                self.assessment.decision, self.review_decision
            )
            or not _valid_digest(self.findings_digest)
            or self.reviewed_at.tzinfo is None  # type: ignore[union-attr]
            or self.reviewed_at < self.submitted_at  # type: ignore[operator]
            or self.updated_at != self.reviewed_at
            or self.review_digest != canonical_digest(self.review_value())
        ):
            raise GovernanceRejected(
                "valid independent limited promotion shadow review required"
            )

    def review_value(self) -> dict[str, object]:
        return {
            "shadow_id": self.assessment.shadow_id,
            "shadow_assessment_digest": self.assessment.assessment_digest,
            "shadow_decision": self.assessment.decision.value,
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
        }


class SyntheticPatchDraftLimitedPromotionShadowReviewDocket:
    """Persists shadow evidence and review without activation or approval."""

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
                "synthetic SQLite limited promotion shadow review target required"
            )

    def _initialize_schema(self) -> None:
        with self._lock:
            self._connection.executescript(
                LIMITED_PROMOTION_SHADOW_REVIEW_SCHEMA_SQL
            )
            self._connection.execute(
                "INSERT OR IGNORE INTO "
                "synthetic_limited_promotion_shadow_review_metadata "
                "(singleton, schema_version, synthetic_only) VALUES (1, ?, 1)",
                (LIMITED_PROMOTION_SHADOW_REVIEW_SCHEMA_VERSION,),
            )
            if not self.verify_metadata():
                raise GovernanceRejected(
                    "unsupported limited promotion shadow review schema"
                )

    def verify_metadata(self) -> bool:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM "
                "synthetic_limited_promotion_shadow_review_metadata"
            ).fetchall()
            return (
                len(rows) == 1
                and rows[0]["singleton"] == 1
                and rows[0]["schema_version"]
                == LIMITED_PROMOTION_SHADOW_REVIEW_SCHEMA_VERSION
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
        book: SyntheticPatchDraftLimitedPromotionShadowBook,
        plan_id: str,
        *,
        submitted_at: datetime,
    ) -> SyntheticPatchDraftLimitedPromotionShadowReviewRecord:
        if submitted_at.tzinfo is None:
            raise GovernanceRejected("timezone-aware shadow submission required")
        if not isinstance(
            book, SyntheticPatchDraftLimitedPromotionShadowBook
        ):
            raise GovernanceRejected(
                "typed limited promotion shadow book required"
            )
        if not book.verify_assessment_chain():
            raise GovernanceRejected(
                "limited promotion shadow assessment chain is invalid"
            )
        matches = [
            item for item in book.assessments if item.plan_id == plan_id
        ]
        if len(matches) != 1:
            raise GovernanceRejected(
                "one limited promotion shadow assessment required"
            )
        assessment = matches[0]
        self._validate_assessment(assessment)
        if submitted_at < assessment.evaluated_at:
            raise GovernanceRejected("submission cannot predate shadow assessment")
        before = book.evidence()["report_digest"]
        payload_json = json.dumps(
            self._assessment_payload(assessment),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

        with self._lock:
            try:
                with self._transaction():
                    if not self.verify_metadata():
                        raise GovernanceRejected(
                            "limited promotion shadow review metadata is invalid"
                        )
                    row = self._connection.execute(
                        "SELECT * FROM "
                        "synthetic_limited_promotion_shadow_review_records "
                        "WHERE shadow_id = ?",
                        (assessment.shadow_id,),
                    ).fetchone()
                    if row is not None:
                        if (
                            row["plan_id"] != plan_id
                            or row["shadow_assessment_digest"]
                            != assessment.assessment_digest
                            or row["submitted_at"] != submitted_at.isoformat()
                        ):
                            raise GovernanceRejected(
                                "limited promotion shadow submission collision"
                            )
                        if not self.verify_record_bindings():
                            raise GovernanceRejected(
                                "existing shadow review evidence is invalid"
                            )
                        record = self._record_from_row(row)
                    else:
                        self._connection.execute(
                            """
                            INSERT INTO synthetic_limited_promotion_shadow_review_records (
                                shadow_id, plan_id, plan_digest, source_review_digest,
                                shadow_assessment_digest, shadow_decision,
                                assessment_json, state, submitted_at, updated_at,
                                submitter_id
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                assessment.shadow_id,
                                assessment.plan_id,
                                assessment.plan_digest,
                                assessment.source_review_digest,
                                assessment.assessment_digest,
                                assessment.decision.value,
                                payload_json,
                                LimitedPromotionShadowReviewState
                                .PENDING_ETERNIAN_REVIEW.value,
                                submitted_at.isoformat(),
                                submitted_at.isoformat(),
                                ARKAON_LIMITED_PROMOTION_SHADOW_SUBMITTER_ID,
                            ),
                        )
                        self._append_audit(
                            shadow_id=assessment.shadow_id,
                            action="ARKAON_LIMITED_PROMOTION_SHADOW_SUBMITTED",
                            state_before=None,
                            state_after=(
                                LimitedPromotionShadowReviewState
                                .PENDING_ETERNIAN_REVIEW
                            ),
                            actor_id=(
                                ARKAON_LIMITED_PROMOTION_SHADOW_SUBMITTER_ID
                            ),
                            evidence_digest=assessment.assessment_digest,
                            recorded_at=submitted_at,
                        )
                        record = self._get_record(assessment.shadow_id)
                    if before != book.evidence()["report_digest"]:
                        raise GovernanceRejected(
                            "shadow assessment changed during submission"
                        )
                    return record
            except sqlite3.Error as exc:
                raise GovernanceRejected(
                    "limited promotion shadow submission transaction failed"
                ) from exc

    @staticmethod
    def _validate_assessment(
        assessment: SyntheticPatchDraftLimitedPromotionShadowAssessment,
    ) -> None:
        if (
            not isinstance(
                assessment,
                SyntheticPatchDraftLimitedPromotionShadowAssessment,
            )
            or assessment.assessment_digest
            != canonical_digest(assessment.digest_value())
            or not assessment.item_results
            or any(
                item.result_digest != canonical_digest(item.digest_value())
                for item in assessment.item_results
            )
            or any(
                (
                    assessment.source_docket_state_changed,
                    assessment.candidate_content_present,
                    assessment.patch_content_present,
                    assessment.diff_content_present,
                    assessment.source_code_changed,
                    assessment.filesystem_written,
                    assessment.automatic_application_allowed,
                    assessment.safety_baseline_relaxation_allowed,
                    assessment.execution_allowed,
                    assessment.synthetic_activation_allowed,
                    assessment.network_access_allowed,
                    assessment.money_movement_allowed,
                    assessment.production_activation_allowed,
                )
            )
        ):
            raise GovernanceRejected(
                "reviewable non-activating shadow assessment required"
            )
        if (
            assessment.decision
            is LimitedPromotionShadowDecision.PROPOSED_FOR_ETERNIAN_REVIEW
            and any(
                item.decision is not LimitedPromotionShadowItemDecision.PASS
                for item in assessment.item_results
            )
        ):
            raise GovernanceRejected(
                "review candidate requires all passing observations"
            )
        if (
            assessment.decision
            is LimitedPromotionShadowDecision.ROLLBACK_REQUIRED
            and all(
                item.decision is LimitedPromotionShadowItemDecision.PASS
                for item in assessment.item_results
            )
        ):
            raise GovernanceRejected(
                "rollback assessment requires a triggered observation"
            )

    @staticmethod
    def _assessment_payload(
        assessment: SyntheticPatchDraftLimitedPromotionShadowAssessment,
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
        decision: LimitedPromotionShadowReviewDecision,
        findings_digest: str,
        reviewed_at: datetime,
    ) -> SyntheticPatchDraftLimitedPromotionShadowReviewRecord:
        if (
            not _valid_prefixed(review_id, _REVIEW_ID_PREFIX)
            or not _valid_prefixed(reviewer_id, _REVIEWER_PREFIX)
            or not isinstance(
                decision, LimitedPromotionShadowReviewDecision
            )
            or not _valid_digest(findings_digest)
            or reviewed_at.tzinfo is None
        ):
            raise GovernanceRejected(
                "complete independent shadow review required"
            )
        with self._lock:
            try:
                with self._transaction():
                    if not self.verify_metadata():
                        raise GovernanceRejected(
                            "limited promotion shadow review metadata is invalid"
                        )
                    row = self._connection.execute(
                        "SELECT * FROM "
                        "synthetic_limited_promotion_shadow_review_records "
                        "WHERE shadow_id = ?",
                        (shadow_id,),
                    ).fetchone()
                    if row is None:
                        raise GovernanceRejected("unknown shadow assessment")
                    shadow_decision = LimitedPromotionShadowDecision(
                        row["shadow_decision"]
                    )
                    target = _target_state(shadow_decision, decision)
                    value = {
                        "shadow_id": shadow_id,
                        "shadow_assessment_digest": (
                            row["shadow_assessment_digest"]
                        ),
                        "shadow_decision": shadow_decision.value,
                        "review_id": review_id,
                        "reviewer_id": reviewer_id,
                        "decision": decision.value,
                        "findings_digest": findings_digest,
                        "reviewed_at": reviewed_at.isoformat(),
                        "resulting_state": target.value,
                    }
                    review_digest = canonical_digest(value)
                    existing = self._connection.execute(
                        "SELECT * FROM "
                        "synthetic_limited_promotion_shadow_review_records "
                        "WHERE review_id = ?",
                        (review_id,),
                    ).fetchone()
                    if existing is not None:
                        if existing["review_digest"] != review_digest:
                            raise GovernanceRejected(
                                "shadow review idempotency mismatch"
                            )
                        if not self.verify_record_bindings():
                            raise GovernanceRejected(
                                "existing shadow review evidence is invalid"
                            )
                        return self._record_from_row(existing)
                    if not self.verify_record_bindings():
                        raise GovernanceRejected(
                            "limited promotion shadow review evidence is invalid"
                        )
                    if reviewed_at < datetime.fromisoformat(row["submitted_at"]):
                        raise GovernanceRejected(
                            "shadow review cannot predate submission"
                        )
                    if row["state"] != (
                        LimitedPromotionShadowReviewState
                        .PENDING_ETERNIAN_REVIEW.value
                    ):
                        raise GovernanceRejected("shadow is not pending review")
                    updated = self._connection.execute(
                        """
                        UPDATE synthetic_limited_promotion_shadow_review_records
                        SET state = ?, updated_at = ?, review_id = ?, reviewer_id = ?,
                            review_decision = ?, findings_digest = ?, reviewed_at = ?,
                            review_digest = ?
                        WHERE shadow_id = ? AND state = 'PENDING_ETERNIAN_REVIEW'
                        """,
                        (
                            target.value,
                            reviewed_at.isoformat(),
                            review_id,
                            reviewer_id,
                            decision.value,
                            findings_digest,
                            reviewed_at.isoformat(),
                            review_digest,
                            shadow_id,
                        ),
                    )
                    if updated.rowcount != 1:
                        raise GovernanceRejected(
                            "shadow review state transition failed"
                        )
                    self._append_audit(
                        shadow_id=shadow_id,
                        action=(
                            "ETERNIAN_LIMITED_PROMOTION_SHADOW_REVIEW_"
                            f"{decision.value}"
                        ),
                        state_before=(
                            LimitedPromotionShadowReviewState
                            .PENDING_ETERNIAN_REVIEW
                        ),
                        state_after=target,
                        actor_id=reviewer_id,
                        evidence_digest=review_digest,
                        recorded_at=reviewed_at,
                    )
                    return self._get_record(shadow_id)
            except sqlite3.Error as exc:
                raise GovernanceRejected(
                    "limited promotion shadow review transaction failed"
                ) from exc

    def _append_audit(
        self,
        *,
        shadow_id: str,
        action: str,
        state_before: LimitedPromotionShadowReviewState | None,
        state_after: LimitedPromotionShadowReviewState,
        actor_id: str,
        evidence_digest: str,
        recorded_at: datetime,
    ) -> None:
        latest = self._connection.execute(
            "SELECT * FROM synthetic_limited_promotion_shadow_review_audit "
            "ORDER BY audit_sequence DESC LIMIT 1"
        ).fetchone()
        sequence = (latest["audit_sequence"] if latest else 0) + 1
        previous = latest["audit_digest"] if latest else "0" * 64
        value = {
            "audit_sequence": sequence,
            "shadow_id": shadow_id,
            "action": action,
            "state_before": state_before.value if state_before else None,
            "state_after": state_after.value,
            "actor_id": actor_id,
            "evidence_digest": evidence_digest,
            "previous_digest": previous,
            "recorded_at": recorded_at.isoformat(),
        }
        self._connection.execute(
            "INSERT INTO synthetic_limited_promotion_shadow_review_audit "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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

    @staticmethod
    def _assessment_from_payload(
        payload: object,
    ) -> SyntheticPatchDraftLimitedPromotionShadowAssessment:
        if not isinstance(payload, dict) or not isinstance(
            payload.get("item_results"), list
        ):
            raise GovernanceRejected("stored shadow assessment object required")
        results = []
        for item in payload["item_results"]:
            if not isinstance(item, dict):
                raise GovernanceRejected("stored shadow item object required")
            results.append(
                SyntheticPatchDraftLimitedPromotionObservationResult(
                    int(item["ordinal"]),
                    str(item["observation_id"]),
                    str(item["observation_digest"]),
                    LimitedPromotionShadowItemDecision(str(item["decision"])),
                    tuple(
                        str(value)
                        for value in item["triggered_rollback_conditions"]
                    ),
                    str(item["reason"]),
                    str(item["result_digest"]),
                )
            )
        if payload["item_result_digests"] != [
            item.result_digest for item in results
        ]:
            raise GovernanceRejected("stored shadow item digest mismatch")
        return SyntheticPatchDraftLimitedPromotionShadowAssessment(
            int(payload["sequence"]),
            str(payload["shadow_id"]),
            str(payload["plan_id"]),
            str(payload["plan_digest"]),
            str(payload["source_review_digest"]),
            str(payload["candidate_digest"]),
            str(payload["cohort_digest"]),
            int(payload["synthetic_sample_size"]),
            int(payload["observation_window_seconds"]),
            tuple(results),
            LimitedPromotionShadowDecision(str(payload["decision"])),
            str(payload["reason"]),
            datetime.fromisoformat(str(payload["evaluated_at"])),
            str(payload["previous_digest"]),
            str(payload["assessment_digest"]),
            bool(payload["source_docket_state_changed"]),
            bool(payload["candidate_content_present"]),
            bool(payload["patch_content_present"]),
            bool(payload["diff_content_present"]),
            bool(payload["source_code_changed"]),
            bool(payload["filesystem_written"]),
            bool(payload["automatic_application_allowed"]),
            bool(payload["safety_baseline_relaxation_allowed"]),
            bool(payload["execution_allowed"]),
            bool(payload["synthetic_activation_allowed"]),
            bool(payload["network_access_allowed"]),
            bool(payload["money_movement_allowed"]),
            bool(payload["production_activation_allowed"]),
        )

    @classmethod
    def _record_from_row(
        cls, row: sqlite3.Row
    ) -> SyntheticPatchDraftLimitedPromotionShadowReviewRecord:
        try:
            assessment = cls._assessment_from_payload(
                json.loads(row["assessment_json"])
            )
            if (
                assessment.shadow_id != row["shadow_id"]
                or assessment.plan_id != row["plan_id"]
                or assessment.plan_digest != row["plan_digest"]
                or assessment.source_review_digest
                != row["source_review_digest"]
                or assessment.assessment_digest
                != row["shadow_assessment_digest"]
                or assessment.decision.value != row["shadow_decision"]
            ):
                raise GovernanceRejected("stored shadow binding is invalid")
            review_decision = (
                LimitedPromotionShadowReviewDecision(row["review_decision"])
                if row["review_decision"] is not None
                else None
            )
            return SyntheticPatchDraftLimitedPromotionShadowReviewRecord(
                assessment,
                LimitedPromotionShadowReviewState(row["state"]),
                datetime.fromisoformat(row["submitted_at"]),
                datetime.fromisoformat(row["updated_at"]),
                row["review_id"],
                row["reviewer_id"],
                review_decision,
                row["findings_digest"],
                (
                    datetime.fromisoformat(row["reviewed_at"])
                    if row["reviewed_at"] is not None
                    else None
                ),
                row["review_digest"],
                row["submitter_id"],
                bool(row["automatic_review_allowed"]),
                bool(row["operator_reconfirmation_recorded"]),
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
            raise GovernanceRejected("stored shadow review is invalid") from exc

    def _get_record(
        self, shadow_id: str
    ) -> SyntheticPatchDraftLimitedPromotionShadowReviewRecord:
        row = self._connection.execute(
            "SELECT * FROM synthetic_limited_promotion_shadow_review_records "
            "WHERE shadow_id = ?",
            (shadow_id,),
        ).fetchone()
        if row is None:
            raise GovernanceRejected("unknown shadow review record")
        return self._record_from_row(row)

    def get(
        self, shadow_id: str
    ) -> SyntheticPatchDraftLimitedPromotionShadowReviewRecord:
        with self._lock:
            return self._get_record(shadow_id)

    def ready_source(
        self, shadow_id: str
    ) -> SyntheticPatchDraftLimitedPromotionShadowReviewRecord:
        with self._lock:
            if not self.verify_record_bindings():
                raise GovernanceRejected("shadow review docket is invalid")
            record = self._get_record(shadow_id)
            if record.state is not (
                LimitedPromotionShadowReviewState
                .READY_FOR_PATCH_DRAFT_LIMITED_PROMOTION_OPERATOR_RECONFIRMATION
            ):
                raise GovernanceRejected(
                    "shadow is not ready for operator reconfirmation"
                )
            return record

    def rollback_source(
        self, shadow_id: str
    ) -> SyntheticPatchDraftLimitedPromotionShadowReviewRecord:
        with self._lock:
            if not self.verify_record_bindings():
                raise GovernanceRejected("shadow review docket is invalid")
            record = self._get_record(shadow_id)
            if record.state is not (
                LimitedPromotionShadowReviewState.ROLLBACK_REQUIRED_CONFIRMED
            ):
                raise GovernanceRejected("rollback requirement is not confirmed")
            return record

    def verify_audit_chain(self) -> bool:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM "
                "synthetic_limited_promotion_shadow_review_audit "
                "ORDER BY audit_sequence"
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
            if not self.verify_metadata() or not self.verify_audit_chain():
                return False
            rows = self._connection.execute(
                "SELECT * FROM "
                "synthetic_limited_promotion_shadow_review_records "
                "ORDER BY shadow_id"
            ).fetchall()
            audits = self._connection.execute(
                "SELECT * FROM "
                "synthetic_limited_promotion_shadow_review_audit "
                "ORDER BY audit_sequence"
            ).fetchall()
            by_shadow: dict[str, list[sqlite3.Row]] = {}
            for audit in audits:
                by_shadow.setdefault(audit["shadow_id"], []).append(audit)
            try:
                for row in rows:
                    record = self._record_from_row(row)
                    entries = by_shadow.get(row["shadow_id"], [])
                    if len(entries) not in {1, 2}:
                        return False
                    submitted = entries[0]
                    if (
                        submitted["action"]
                        != "ARKAON_LIMITED_PROMOTION_SHADOW_SUBMITTED"
                        or submitted["state_before"] is not None
                        or submitted["state_after"]
                        != LimitedPromotionShadowReviewState
                        .PENDING_ETERNIAN_REVIEW.value
                        or submitted["actor_id"]
                        != ARKAON_LIMITED_PROMOTION_SHADOW_SUBMITTER_ID
                        or submitted["evidence_digest"]
                        != row["shadow_assessment_digest"]
                        or submitted["recorded_at"] != row["submitted_at"]
                    ):
                        return False
                    if record.review_id is None:
                        if len(entries) != 1:
                            return False
                    else:
                        if len(entries) != 2:
                            return False
                        reviewed = entries[1]
                        if (
                            reviewed["state_before"]
                            != LimitedPromotionShadowReviewState
                            .PENDING_ETERNIAN_REVIEW.value
                            or reviewed["state_after"] != record.state.value
                            or reviewed["actor_id"] != record.reviewer_id
                            or reviewed["evidence_digest"]
                            != record.review_digest
                            or reviewed["recorded_at"] != row["reviewed_at"]
                        ):
                            return False
            except (GovernanceRejected, KeyError, TypeError, ValueError):
                return False
            return len(audits) == sum(
                1 if row["review_id"] is None else 2 for row in rows
            )

    def evidence(self) -> dict[str, object]:
        with self._lock:
            records = self._connection.execute(
                "SELECT state, shadow_decision, shadow_assessment_digest, "
                "review_digest FROM "
                "synthetic_limited_promotion_shadow_review_records "
                "ORDER BY shadow_id"
            ).fetchall()
            audits = self._connection.execute(
                "SELECT audit_digest FROM "
                "synthetic_limited_promotion_shadow_review_audit "
                "ORDER BY audit_sequence"
            ).fetchall()
            state_counts = {
                state.value: 0 for state in LimitedPromotionShadowReviewState
            }
            shadow_decision_counts = {
                decision.value: 0 for decision in LimitedPromotionShadowDecision
            }
            for row in records:
                state_counts[row["state"]] += 1
                shadow_decision_counts[row["shadow_decision"]] += 1
            value = {
                "schema": (
                    "nurion.pg.synthetic-patch-draft-limited-promotion-shadow-"
                    "review-evidence.v1"
                ),
                "mode": "UNREGISTERED_SYNTHETIC_ONLY",
                "database_engine": "SQLite",
                "schema_version": (
                    LIMITED_PROMOTION_SHADOW_REVIEW_SCHEMA_VERSION
                ),
                "schema_digest": canonical_digest(
                    LIMITED_PROMOTION_SHADOW_REVIEW_SCHEMA_SQL
                ),
                "review_authority": "ETERNIAN_INDEPENDENT_REVIEW",
                "maximum_state": MAXIMUM_LIMITED_PROMOTION_SHADOW_REVIEW_STATE,
                "record_count": len(records),
                "state_counts": state_counts,
                "shadow_decision_counts": shadow_decision_counts,
                "assessment_digests": [
                    row["shadow_assessment_digest"] for row in records
                ],
                "review_digests": [
                    row["review_digest"]
                    for row in records
                    if row["review_digest"]
                ],
                "audit_digests": [row["audit_digest"] for row in audits],
                "metadata_valid": self.verify_metadata(),
                "audit_chain_valid": self.verify_audit_chain(),
                "record_bindings_valid": self.verify_record_bindings(),
                "automatic_review_allowed": False,
                "operator_reconfirmation_method_present": False,
                "operator_reconfirmation_recorded": False,
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
