"""Durable Eternian final review for synthetic activation manifests."""

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
from .synthetic_patch_draft_limited_promotion_activation_manifests import (
    SyntheticPatchDraftLimitedPromotionActivationManifest,
    SyntheticPatchDraftLimitedPromotionActivationManifestBook,
)


ACTIVATION_MANIFEST_REVIEW_SCHEMA_VERSION = 1
MAXIMUM_ACTIVATION_MANIFEST_REVIEW_STATE = (
    "READY_FOR_SYNTHETIC_LIMITED_PROMOTION_OPERATOR_DECISION"
)
_SUBMITTER_ID = (
    "synthetic:arkaon:NURION_PG:limited-promotion-activation-manifest"
)
_REVIEW_ID_PREFIX = "synthetic:limited-promotion-activation-final-review:"
_REVIEWER_PREFIX = (
    "synthetic:eternian-reviewer:limited-promotion-activation:"
)


class ActivationManifestReviewState(StrEnum):
    PENDING_ETERNIAN_FINAL_REVIEW = "PENDING_ETERNIAN_FINAL_REVIEW"
    READY_FOR_SYNTHETIC_LIMITED_PROMOTION_OPERATOR_DECISION = (
        "READY_FOR_SYNTHETIC_LIMITED_PROMOTION_OPERATOR_DECISION"
    )
    HELD = "HELD"
    REJECTED = "REJECTED"


class ActivationManifestReviewDecision(StrEnum):
    PASS = "PASS"
    HOLD = "HOLD"
    REJECT = "REJECT"


def _target_state(
    decision: ActivationManifestReviewDecision,
) -> ActivationManifestReviewState:
    if decision is ActivationManifestReviewDecision.PASS:
        return (
            ActivationManifestReviewState
            .READY_FOR_SYNTHETIC_LIMITED_PROMOTION_OPERATOR_DECISION
        )
    if decision is ActivationManifestReviewDecision.HOLD:
        return ActivationManifestReviewState.HELD
    return ActivationManifestReviewState.REJECTED


ACTIVATION_MANIFEST_REVIEW_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS synthetic_activation_manifest_review_metadata (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    schema_version INTEGER NOT NULL CHECK (schema_version = 1),
    synthetic_only INTEGER NOT NULL CHECK (synthetic_only = 1)
);
CREATE TABLE IF NOT EXISTS synthetic_activation_manifest_review_records (
    manifest_id TEXT PRIMARY KEY,
    source_receipt_id TEXT NOT NULL UNIQUE,
    source_receipt_digest TEXT NOT NULL,
    source_packet_digest TEXT NOT NULL,
    shadow_id TEXT NOT NULL UNIQUE,
    plan_digest TEXT NOT NULL,
    manifest_digest TEXT NOT NULL UNIQUE,
    manifest_json TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN (
        'PENDING_ETERNIAN_FINAL_REVIEW',
        'READY_FOR_SYNTHETIC_LIMITED_PROMOTION_OPERATOR_DECISION',
        'HELD', 'REJECTED'
    )),
    submitted_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    submitter_id TEXT NOT NULL CHECK (
        submitter_id =
        'synthetic:arkaon:NURION_PG:limited-promotion-activation-manifest'
    ),
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
    patch_content_present INTEGER NOT NULL DEFAULT 0
        CHECK (patch_content_present = 0),
    diff_content_present INTEGER NOT NULL DEFAULT 0
        CHECK (diff_content_present = 0),
    source_code_changed INTEGER NOT NULL DEFAULT 0
        CHECK (source_code_changed = 0),
    filesystem_written INTEGER NOT NULL DEFAULT 0
        CHECK (filesystem_written = 0),
    activation_allowed INTEGER NOT NULL DEFAULT 0
        CHECK (activation_allowed = 0),
    rollback_execution_allowed INTEGER NOT NULL DEFAULT 0
        CHECK (rollback_execution_allowed = 0),
    safety_baseline_relaxation_allowed INTEGER NOT NULL DEFAULT 0
        CHECK (safety_baseline_relaxation_allowed = 0),
    execution_allowed INTEGER NOT NULL DEFAULT 0 CHECK (execution_allowed = 0),
    production_activation_allowed INTEGER NOT NULL DEFAULT 0
        CHECK (production_activation_allowed = 0),
    CHECK (
        (state = 'PENDING_ETERNIAN_FINAL_REVIEW'
            AND review_id IS NULL AND reviewer_id IS NULL
            AND review_decision IS NULL AND findings_digest IS NULL
            AND reviewed_at IS NULL AND review_digest IS NULL)
        OR
        (state != 'PENDING_ETERNIAN_FINAL_REVIEW'
            AND review_id IS NOT NULL AND reviewer_id IS NOT NULL
            AND review_decision IS NOT NULL AND findings_digest IS NOT NULL
            AND reviewed_at IS NOT NULL AND review_digest IS NOT NULL)
    )
);
CREATE TABLE IF NOT EXISTS synthetic_activation_manifest_review_audit (
    audit_sequence INTEGER PRIMARY KEY,
    manifest_id TEXT NOT NULL,
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
class SyntheticPatchDraftLimitedPromotionActivationReviewRecord:
    manifest: SyntheticPatchDraftLimitedPromotionActivationManifest
    state: ActivationManifestReviewState
    submitted_at: datetime
    updated_at: datetime
    review_id: str | None = None
    reviewer_id: str | None = None
    review_decision: ActivationManifestReviewDecision | None = None
    findings_digest: str | None = None
    reviewed_at: datetime | None = None
    review_digest: str | None = None
    submitter_id: str = _SUBMITTER_ID
    automatic_review_allowed: bool = False
    operator_decision_recorded: bool = False
    candidate_content_present: bool = False
    patch_content_present: bool = False
    diff_content_present: bool = False
    source_code_changed: bool = False
    filesystem_written: bool = False
    activation_allowed: bool = False
    rollback_execution_allowed: bool = False
    safety_baseline_relaxation_allowed: bool = False
    execution_allowed: bool = False
    production_activation_allowed: bool = False

    def __post_init__(self) -> None:
        pending = (
            self.state
            is ActivationManifestReviewState.PENDING_ETERNIAN_FINAL_REVIEW
        )
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
            self.activation_allowed,
            self.rollback_execution_allowed,
            self.safety_baseline_relaxation_allowed,
            self.execution_allowed,
            self.production_activation_allowed,
        )
        if (
            not isinstance(
                self.manifest,
                SyntheticPatchDraftLimitedPromotionActivationManifest,
            )
            or self.manifest.manifest_digest
            != canonical_digest(self.manifest.digest_value())
            or self.submitted_at.tzinfo is None
            or self.submitted_at < self.manifest.drafted_at
            or self.updated_at.tzinfo is None
            or self.updated_at < self.submitted_at
            or self.submitter_id != _SUBMITTER_ID
            or any(forbidden)
            or (pending and any(field is not None for field in review_fields))
            or (not pending and any(field is None for field in review_fields))
        ):
            raise GovernanceRejected(
                "valid activation manifest review record required"
            )
        if not pending and (
            not _valid_prefixed(self.review_id, _REVIEW_ID_PREFIX)
            or not _valid_prefixed(self.reviewer_id, _REVIEWER_PREFIX)
            or not isinstance(
                self.review_decision, ActivationManifestReviewDecision
            )
            or self.state != _target_state(self.review_decision)
            or not _valid_digest(self.findings_digest)
            or self.reviewed_at.tzinfo is None  # type: ignore[union-attr]
            or self.reviewed_at < self.submitted_at  # type: ignore[operator]
            or self.updated_at != self.reviewed_at
            or self.review_digest != canonical_digest(self.review_value())
        ):
            raise GovernanceRejected(
                "valid independent activation manifest final review required"
            )

    def review_value(self) -> dict[str, object]:
        return {
            "manifest_id": self.manifest.manifest_id,
            "manifest_digest": self.manifest.manifest_digest,
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


class SyntheticPatchDraftLimitedPromotionActivationReviewDocket:
    """Persists final review without recording an operator decision."""

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
                "synthetic SQLite activation review target required"
            )

    def _initialize_schema(self) -> None:
        with self._lock:
            self._connection.executescript(ACTIVATION_MANIFEST_REVIEW_SCHEMA_SQL)
            self._connection.execute(
                "INSERT OR IGNORE INTO synthetic_activation_manifest_review_metadata "
                "(singleton, schema_version, synthetic_only) VALUES (1, ?, 1)",
                (ACTIVATION_MANIFEST_REVIEW_SCHEMA_VERSION,),
            )
            if not self.verify_metadata():
                raise GovernanceRejected("unsupported activation review schema")

    def verify_metadata(self) -> bool:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM synthetic_activation_manifest_review_metadata"
            ).fetchall()
            return (
                len(rows) == 1
                and rows[0]["singleton"] == 1
                and rows[0]["schema_version"]
                == ACTIVATION_MANIFEST_REVIEW_SCHEMA_VERSION
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

    @staticmethod
    def _manifest_payload(
        manifest: SyntheticPatchDraftLimitedPromotionActivationManifest,
    ) -> dict[str, object]:
        return {**manifest.digest_value(), "manifest_digest": manifest.manifest_digest}

    @staticmethod
    def _manifest_from_payload(
        payload: object,
    ) -> SyntheticPatchDraftLimitedPromotionActivationManifest:
        if not isinstance(payload, dict):
            raise GovernanceRejected("stored activation manifest object required")
        return SyntheticPatchDraftLimitedPromotionActivationManifest(
            int(payload["sequence"]), str(payload["manifest_id"]),
            str(payload["source_receipt_id"]), str(payload["source_receipt_digest"]),
            str(payload["source_assessment_id"]), str(payload["source_packet_id"]),
            str(payload["source_packet_digest"]), str(payload["shadow_id"]),
            str(payload["plan_id"]), str(payload["plan_digest"]),
            str(payload["source_plan_review_digest"]),
            str(payload["candidate_digest"]), str(payload["cohort_digest"]),
            str(payload["shadow_assessment_digest"]),
            str(payload["shadow_review_digest"]), str(payload["governance_digest"]),
            int(payload["synthetic_sample_size"]),
            int(payload["observation_window_seconds"]),
            tuple(str(item) for item in payload["observation_result_digests"]),
            str(payload["activation_scope"]),
            tuple(str(item) for item in payload["rollback_triggers"]),
            tuple(str(item) for item in payload["required_checks"]),
            datetime.fromisoformat(str(payload["drafted_at"])),
            str(payload["previous_digest"]), str(payload["manifest_digest"]),
            str(payload["state"]), bool(payload["synthetic_only"]),
            bool(payload["eternian_final_review_required"]),
            bool(payload["validated_reconfirmation_receipt_only"]),
            bool(payload["actual_operator_reconfirmation_recorded"]),
            bool(payload["candidate_content_present"]),
            bool(payload["patch_content_present"]), bool(payload["diff_content_present"]),
            bool(payload["source_code_changed"]), bool(payload["filesystem_written"]),
            bool(payload["activation_allowed"]),
            bool(payload["rollback_execution_allowed"]),
            bool(payload["safety_baseline_relaxation_allowed"]),
            bool(payload["execution_allowed"]), bool(payload["network_access_allowed"]),
            bool(payload["money_movement_allowed"]),
            bool(payload["production_activation_allowed"]),
        )

    def submit_from_book(
        self,
        book: SyntheticPatchDraftLimitedPromotionActivationManifestBook,
        manifest_id: str,
        *,
        submitted_at: datetime,
    ) -> SyntheticPatchDraftLimitedPromotionActivationReviewRecord:
        if submitted_at.tzinfo is None:
            raise GovernanceRejected("timezone-aware manifest submission required")
        if not isinstance(
            book, SyntheticPatchDraftLimitedPromotionActivationManifestBook
        ):
            raise GovernanceRejected("typed activation manifest book required")
        if not book.verify_manifest_chain():
            raise GovernanceRejected("activation manifest chain is invalid")
        matches = [item for item in book.manifests if item.manifest_id == manifest_id]
        if len(matches) != 1:
            raise GovernanceRejected("one activation manifest required")
        manifest = matches[0]
        if submitted_at < manifest.drafted_at:
            raise GovernanceRejected("submission cannot predate manifest")
        before = book.evidence()["report_digest"]
        payload_json = json.dumps(
            self._manifest_payload(manifest), ensure_ascii=False,
            sort_keys=True, separators=(",", ":"),
        )
        with self._lock:
            try:
                with self._transaction():
                    if not self.verify_metadata():
                        raise GovernanceRejected("activation review metadata is invalid")
                    row = self._connection.execute(
                        "SELECT * FROM synthetic_activation_manifest_review_records "
                        "WHERE manifest_id = ?", (manifest_id,),
                    ).fetchone()
                    if row is not None:
                        if (
                            row["manifest_digest"] != manifest.manifest_digest
                            or row["submitted_at"] != submitted_at.isoformat()
                        ):
                            raise GovernanceRejected("manifest submission collision")
                        if not self.verify_record_bindings():
                            raise GovernanceRejected("existing activation review is invalid")
                        record = self._record_from_row(row)
                    else:
                        self._connection.execute(
                            """
                            INSERT INTO synthetic_activation_manifest_review_records (
                                manifest_id, source_receipt_id, source_receipt_digest,
                                source_packet_digest, shadow_id, plan_digest,
                                manifest_digest, manifest_json, state, submitted_at,
                                updated_at, submitter_id
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                manifest.manifest_id, manifest.source_receipt_id,
                                manifest.source_receipt_digest,
                                manifest.source_packet_digest, manifest.shadow_id,
                                manifest.plan_digest, manifest.manifest_digest,
                                payload_json,
                                ActivationManifestReviewState
                                .PENDING_ETERNIAN_FINAL_REVIEW.value,
                                submitted_at.isoformat(), submitted_at.isoformat(),
                                _SUBMITTER_ID,
                            ),
                        )
                        self._append_audit(
                            manifest_id=manifest_id,
                            action="ARKAON_ACTIVATION_MANIFEST_SUBMITTED",
                            state_before=None,
                            state_after=(
                                ActivationManifestReviewState
                                .PENDING_ETERNIAN_FINAL_REVIEW
                            ),
                            actor_id=_SUBMITTER_ID,
                            evidence_digest=manifest.manifest_digest,
                            recorded_at=submitted_at,
                        )
                        record = self._get_record(manifest_id)
                    if before != book.evidence()["report_digest"]:
                        raise GovernanceRejected("manifest changed during submission")
                    return record
            except sqlite3.Error as exc:
                raise GovernanceRejected("manifest submission transaction failed") from exc

    def record_eternian_review(
        self,
        manifest_id: str,
        *,
        review_id: str,
        reviewer_id: str,
        decision: ActivationManifestReviewDecision,
        findings_digest: str,
        reviewed_at: datetime,
    ) -> SyntheticPatchDraftLimitedPromotionActivationReviewRecord:
        if (
            not _valid_prefixed(review_id, _REVIEW_ID_PREFIX)
            or not _valid_prefixed(reviewer_id, _REVIEWER_PREFIX)
            or not isinstance(decision, ActivationManifestReviewDecision)
            or not _valid_digest(findings_digest)
            or reviewed_at.tzinfo is None
        ):
            raise GovernanceRejected("valid Eternian final review metadata required")
        with self._lock:
            try:
                with self._transaction():
                    if not self.verify_metadata():
                        raise GovernanceRejected("activation review metadata is invalid")
                    row = self._connection.execute(
                        "SELECT * FROM synthetic_activation_manifest_review_records "
                        "WHERE manifest_id = ?", (manifest_id,),
                    ).fetchone()
                    if row is None:
                        raise GovernanceRejected("unknown activation manifest")
                    target = _target_state(decision)
                    value = {
                        "manifest_id": manifest_id,
                        "manifest_digest": row["manifest_digest"],
                        "review_id": review_id, "reviewer_id": reviewer_id,
                        "decision": decision.value,
                        "findings_digest": findings_digest,
                        "reviewed_at": reviewed_at.isoformat(),
                        "resulting_state": target.value,
                    }
                    review_digest = canonical_digest(value)
                    existing = self._connection.execute(
                        "SELECT * FROM synthetic_activation_manifest_review_records "
                        "WHERE review_id = ?", (review_id,),
                    ).fetchone()
                    if existing is not None:
                        if existing["review_digest"] != review_digest:
                            raise GovernanceRejected("final review idempotency mismatch")
                        if not self.verify_record_bindings():
                            raise GovernanceRejected("existing final review is invalid")
                        return self._record_from_row(existing)
                    if not self.verify_record_bindings():
                        raise GovernanceRejected("activation review evidence is invalid")
                    if reviewed_at < datetime.fromisoformat(row["submitted_at"]):
                        raise GovernanceRejected("review cannot predate submission")
                    if row["state"] != (
                        ActivationManifestReviewState
                        .PENDING_ETERNIAN_FINAL_REVIEW.value
                    ):
                        raise GovernanceRejected("manifest is not pending final review")
                    updated = self._connection.execute(
                        """
                        UPDATE synthetic_activation_manifest_review_records
                        SET state = ?, updated_at = ?, review_id = ?, reviewer_id = ?,
                            review_decision = ?, findings_digest = ?, reviewed_at = ?,
                            review_digest = ?
                        WHERE manifest_id = ? AND state = 'PENDING_ETERNIAN_FINAL_REVIEW'
                        """,
                        (
                            target.value, reviewed_at.isoformat(), review_id,
                            reviewer_id, decision.value, findings_digest,
                            reviewed_at.isoformat(), review_digest, manifest_id,
                        ),
                    )
                    if updated.rowcount != 1:
                        raise GovernanceRejected("final review transition failed")
                    self._append_audit(
                        manifest_id=manifest_id,
                        action=f"ETERNIAN_ACTIVATION_FINAL_REVIEW_{decision.value}",
                        state_before=(
                            ActivationManifestReviewState
                            .PENDING_ETERNIAN_FINAL_REVIEW
                        ),
                        state_after=target, actor_id=reviewer_id,
                        evidence_digest=review_digest, recorded_at=reviewed_at,
                    )
                    return self._get_record(manifest_id)
            except sqlite3.Error as exc:
                raise GovernanceRejected("final review transaction failed") from exc

    def _append_audit(
        self, *, manifest_id: str, action: str,
        state_before: ActivationManifestReviewState | None,
        state_after: ActivationManifestReviewState, actor_id: str,
        evidence_digest: str, recorded_at: datetime,
    ) -> None:
        latest = self._connection.execute(
            "SELECT * FROM synthetic_activation_manifest_review_audit "
            "ORDER BY audit_sequence DESC LIMIT 1"
        ).fetchone()
        sequence = (latest["audit_sequence"] if latest else 0) + 1
        previous = latest["audit_digest"] if latest else "0" * 64
        value = {
            "audit_sequence": sequence, "manifest_id": manifest_id,
            "action": action,
            "state_before": state_before.value if state_before else None,
            "state_after": state_after.value, "actor_id": actor_id,
            "evidence_digest": evidence_digest, "previous_digest": previous,
            "recorded_at": recorded_at.isoformat(),
        }
        self._connection.execute(
            "INSERT INTO synthetic_activation_manifest_review_audit "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                sequence, manifest_id, action, value["state_before"],
                state_after.value, actor_id, evidence_digest, previous,
                canonical_digest(value), recorded_at.isoformat(),
            ),
        )

    @classmethod
    def _record_from_row(
        cls, row: sqlite3.Row
    ) -> SyntheticPatchDraftLimitedPromotionActivationReviewRecord:
        try:
            manifest = cls._manifest_from_payload(json.loads(row["manifest_json"]))
            if (
                manifest.manifest_id != row["manifest_id"]
                or manifest.source_receipt_id != row["source_receipt_id"]
                or manifest.source_receipt_digest != row["source_receipt_digest"]
                or manifest.source_packet_digest != row["source_packet_digest"]
                or manifest.shadow_id != row["shadow_id"]
                or manifest.plan_digest != row["plan_digest"]
                or manifest.manifest_digest != row["manifest_digest"]
            ):
                raise GovernanceRejected("stored activation binding is invalid")
            return SyntheticPatchDraftLimitedPromotionActivationReviewRecord(
                manifest, ActivationManifestReviewState(row["state"]),
                datetime.fromisoformat(row["submitted_at"]),
                datetime.fromisoformat(row["updated_at"]), row["review_id"],
                row["reviewer_id"],
                (
                    ActivationManifestReviewDecision(row["review_decision"])
                    if row["review_decision"] is not None else None
                ),
                row["findings_digest"],
                (
                    datetime.fromisoformat(row["reviewed_at"])
                    if row["reviewed_at"] is not None else None
                ),
                row["review_digest"], row["submitter_id"],
                bool(row["automatic_review_allowed"]),
                bool(row["operator_decision_recorded"]),
                bool(row["candidate_content_present"]),
                bool(row["patch_content_present"]), bool(row["diff_content_present"]),
                bool(row["source_code_changed"]), bool(row["filesystem_written"]),
                bool(row["activation_allowed"]),
                bool(row["rollback_execution_allowed"]),
                bool(row["safety_baseline_relaxation_allowed"]),
                bool(row["execution_allowed"]),
                bool(row["production_activation_allowed"]),
            )
        except (GovernanceRejected, KeyError, TypeError, ValueError) as exc:
            raise GovernanceRejected("stored activation review is invalid") from exc

    def _get_record(
        self, manifest_id: str
    ) -> SyntheticPatchDraftLimitedPromotionActivationReviewRecord:
        row = self._connection.execute(
            "SELECT * FROM synthetic_activation_manifest_review_records "
            "WHERE manifest_id = ?", (manifest_id,),
        ).fetchone()
        if row is None:
            raise GovernanceRejected("unknown activation review record")
        return self._record_from_row(row)

    def get(
        self, manifest_id: str
    ) -> SyntheticPatchDraftLimitedPromotionActivationReviewRecord:
        with self._lock:
            return self._get_record(manifest_id)

    def ready_source(
        self, manifest_id: str
    ) -> SyntheticPatchDraftLimitedPromotionActivationReviewRecord:
        with self._lock:
            if not self.verify_record_bindings():
                raise GovernanceRejected("activation review docket is invalid")
            record = self._get_record(manifest_id)
            if record.state is not (
                ActivationManifestReviewState
                .READY_FOR_SYNTHETIC_LIMITED_PROMOTION_OPERATOR_DECISION
            ):
                raise GovernanceRejected("manifest is not operator-decision ready")
            return record

    def verify_audit_chain(self) -> bool:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM synthetic_activation_manifest_review_audit "
                "ORDER BY audit_sequence"
            ).fetchall()
            previous = "0" * 64
            for sequence, row in enumerate(rows, start=1):
                value = {
                    "audit_sequence": sequence, "manifest_id": row["manifest_id"],
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
            if not self.verify_metadata() or not self.verify_audit_chain():
                return False
            rows = self._connection.execute(
                "SELECT * FROM synthetic_activation_manifest_review_records"
            ).fetchall()
            audits = self._connection.execute(
                "SELECT * FROM synthetic_activation_manifest_review_audit "
                "ORDER BY audit_sequence"
            ).fetchall()
            by_manifest: dict[str, list[sqlite3.Row]] = {}
            for audit in audits:
                by_manifest.setdefault(audit["manifest_id"], []).append(audit)
            try:
                for row in rows:
                    record = self._record_from_row(row)
                    entries = by_manifest.get(row["manifest_id"], [])
                    if len(entries) not in {1, 2}:
                        return False
                    submitted = entries[0]
                    if (
                        submitted["action"] != "ARKAON_ACTIVATION_MANIFEST_SUBMITTED"
                        or submitted["state_before"] is not None
                        or submitted["state_after"] != (
                            ActivationManifestReviewState
                            .PENDING_ETERNIAN_FINAL_REVIEW.value
                        )
                        or submitted["actor_id"] != _SUBMITTER_ID
                        or submitted["evidence_digest"] != row["manifest_digest"]
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
                            reviewed["state_before"] != (
                                ActivationManifestReviewState
                                .PENDING_ETERNIAN_FINAL_REVIEW.value
                            )
                            or reviewed["state_after"] != record.state.value
                            or reviewed["actor_id"] != record.reviewer_id
                            or reviewed["evidence_digest"] != record.review_digest
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
            rows = self._connection.execute(
                "SELECT state, manifest_digest, review_digest FROM "
                "synthetic_activation_manifest_review_records "
                "ORDER BY manifest_id"
            ).fetchall()
            audits = self._connection.execute(
                "SELECT audit_digest FROM synthetic_activation_manifest_review_audit "
                "ORDER BY audit_sequence"
            ).fetchall()
            counts = {state.value: 0 for state in ActivationManifestReviewState}
            for row in rows:
                counts[row["state"]] += 1
            value = {
                "schema": (
                    "nurion.pg.synthetic-limited-promotion-activation-"
                    "final-review-evidence.v1"
                ),
                "mode": "UNREGISTERED_SYNTHETIC_ONLY",
                "database_engine": "SQLite",
                "schema_version": ACTIVATION_MANIFEST_REVIEW_SCHEMA_VERSION,
                "schema_digest": canonical_digest(ACTIVATION_MANIFEST_REVIEW_SCHEMA_SQL),
                "review_authority": "ETERNIAN_FINAL_REVIEW",
                "maximum_state": MAXIMUM_ACTIVATION_MANIFEST_REVIEW_STATE,
                "record_count": len(rows), "state_counts": counts,
                "manifest_digests": [row["manifest_digest"] for row in rows],
                "review_digests": [row["review_digest"] for row in rows if row["review_digest"]],
                "audit_digests": [row["audit_digest"] for row in audits],
                "metadata_valid": self.verify_metadata(),
                "audit_chain_valid": self.verify_audit_chain(),
                "record_bindings_valid": self.verify_record_bindings(),
                "automatic_review_allowed": False,
                "operator_decision_recording_method_present": False,
                "candidate_content_present": False,
                "patch_content_present": False,
                "diff_content_present": False,
                "source_code_changed": False,
                "filesystem_written": False,
                "activation_method_present": False,
                "rollback_execution_method_present": False,
                "safety_baseline_relaxation_method_present": False,
                "execution_method_present": False,
                "network_access_method_present": False,
                "external_blocker_close_method_present": False,
                "automatic_merge_method_present": False,
                "automatic_deploy_method_present": False,
                "personal_data_used": False,
                "credentials_used": False,
                "money_movement_executed": False,
                "production_activation_allowed": False,
            }
            return {**value, "report_digest": canonical_digest(value)}
