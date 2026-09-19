"""Durable Eternian review docket for metadata-only synthetic patch drafts."""

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
from .patch_operator_decision_intake import SyntheticPatchOperatorDecision
from .synthetic_patch_draft_manifests import (
    PATCH_DRAFT_MANIFEST_STATE,
    SyntheticPatchDraftManifest,
    SyntheticPatchDraftManifestBook,
)


PATCH_DRAFT_REVIEW_SCHEMA_VERSION = 1
MAXIMUM_PATCH_DRAFT_REVIEW_STATE = "READY_FOR_SYNTHETIC_PATCH_DRAFT_SHADOW"
_REVIEW_ID_PREFIX = "synthetic:patch-draft-review:"
_REVIEWER_PREFIX = "synthetic:eternian-reviewer:patch-draft:"


class PatchDraftReviewState(StrEnum):
    PENDING_ETERNIAN_REVIEW = "PENDING_ETERNIAN_REVIEW"
    READY_FOR_SYNTHETIC_PATCH_DRAFT_SHADOW = (
        "READY_FOR_SYNTHETIC_PATCH_DRAFT_SHADOW"
    )
    HELD = "HELD"
    REJECTED = "REJECTED"


class PatchDraftReviewDecision(StrEnum):
    PASS = "PASS"
    HOLD = "HOLD"
    REJECT = "REJECT"


_STATE_BY_DECISION = {
    PatchDraftReviewDecision.PASS: (
        PatchDraftReviewState.READY_FOR_SYNTHETIC_PATCH_DRAFT_SHADOW
    ),
    PatchDraftReviewDecision.HOLD: PatchDraftReviewState.HELD,
    PatchDraftReviewDecision.REJECT: PatchDraftReviewState.REJECTED,
}


PATCH_DRAFT_REVIEW_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS synthetic_patch_draft_review_metadata (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    schema_version INTEGER NOT NULL CHECK (schema_version = 1),
    synthetic_only INTEGER NOT NULL CHECK (synthetic_only = 1)
);
CREATE TABLE IF NOT EXISTS synthetic_patch_draft_review_records (
    manifest_id TEXT PRIMARY KEY,
    manifest_digest TEXT NOT NULL UNIQUE,
    source_receipt_id TEXT NOT NULL UNIQUE,
    source_receipt_digest TEXT NOT NULL,
    source_packet_id TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN (
        'PENDING_ETERNIAN_REVIEW',
        'READY_FOR_SYNTHETIC_PATCH_DRAFT_SHADOW',
        'HELD', 'REJECTED'
    )),
    submitted_at TEXT NOT NULL,
    review_id TEXT UNIQUE,
    reviewer_id TEXT,
    review_decision TEXT CHECK (review_decision IN ('PASS', 'HOLD', 'REJECT')),
    findings_digest TEXT,
    reviewed_at TEXT,
    review_digest TEXT UNIQUE,
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
CREATE TABLE IF NOT EXISTS synthetic_patch_draft_review_audit (
    audit_sequence INTEGER PRIMARY KEY,
    manifest_id TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('SUBMITTED', 'ETERNIAN_REVIEWED')),
    actor_id TEXT NOT NULL,
    evidence_digest TEXT NOT NULL,
    previous_digest TEXT NOT NULL,
    audit_digest TEXT NOT NULL UNIQUE,
    recorded_at TEXT NOT NULL,
    UNIQUE (manifest_id, action)
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
class SyntheticPatchDraftReviewRecord:
    manifest: SyntheticPatchDraftManifest
    state: PatchDraftReviewState
    submitted_at: datetime
    review_id: str | None = None
    reviewer_id: str | None = None
    review_decision: PatchDraftReviewDecision | None = None
    findings_digest: str | None = None
    reviewed_at: datetime | None = None
    review_digest: str | None = None
    patch_content_present: bool = False
    diff_content_present: bool = False
    source_code_changed: bool = False
    filesystem_written: bool = False
    automatic_application_allowed: bool = False
    safety_baseline_relaxation_allowed: bool = False
    execution_allowed: bool = False
    production_activation_allowed: bool = False

    def __post_init__(self) -> None:
        pending = self.state is PatchDraftReviewState.PENDING_ETERNIAN_REVIEW
        review_fields = (
            self.review_id,
            self.reviewer_id,
            self.review_decision,
            self.findings_digest,
            self.reviewed_at,
            self.review_digest,
        )
        if (
            not isinstance(self.manifest, SyntheticPatchDraftManifest)
            or self.manifest.state != PATCH_DRAFT_MANIFEST_STATE
            or self.manifest.manifest_digest
            != canonical_digest(self.manifest.digest_value())
            or self.submitted_at.tzinfo is None
            or self.submitted_at < self.manifest.drafted_at
            or self.patch_content_present
            or self.diff_content_present
            or self.source_code_changed
            or self.filesystem_written
            or self.automatic_application_allowed
            or self.safety_baseline_relaxation_allowed
            or self.execution_allowed
            or self.production_activation_allowed
            or (pending and any(field is not None for field in review_fields))
            or (not pending and any(field is None for field in review_fields))
        ):
            raise GovernanceRejected("valid synthetic patch draft review record required")
        if not pending and (
            not _valid_prefixed_id(self.review_id, _REVIEW_ID_PREFIX)
            or not _valid_prefixed_id(self.reviewer_id, _REVIEWER_PREFIX)
            or not isinstance(self.review_decision, PatchDraftReviewDecision)
            or self.state != _STATE_BY_DECISION[self.review_decision]
            or not _valid_digest(self.findings_digest)
            or self.reviewed_at.tzinfo is None  # type: ignore[union-attr]
            or self.reviewed_at < self.submitted_at  # type: ignore[operator]
            or self.review_digest != canonical_digest(self.review_value())
        ):
            raise GovernanceRejected("valid Eternian patch draft review required")

    def review_value(self) -> dict[str, object]:
        return {
            "manifest_id": self.manifest.manifest_id,
            "manifest_digest": self.manifest.manifest_digest,
            "review_id": self.review_id,
            "reviewer_id": self.reviewer_id,
            "decision": self.review_decision.value if self.review_decision else None,
            "findings_digest": self.findings_digest,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "resulting_state": self.state.value,
            "patch_content_present": False,
            "diff_content_present": False,
            "source_code_changed": False,
            "filesystem_written": False,
            "automatic_application_allowed": False,
            "safety_baseline_relaxation_allowed": False,
            "execution_allowed": False,
            "production_activation_allowed": False,
        }


class SyntheticPatchDraftReviewDocket:
    """Persists independent review without creating or applying patch content."""

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
        name = Path(database).name
        if not name.startswith("synthetic-") or Path(name).suffix not in {
            ".db", ".sqlite", ".sqlite3"
        }:
            raise GovernanceRejected("synthetic SQLite patch review target required")

    def _initialize_schema(self) -> None:
        with self._lock:
            self._connection.executescript(PATCH_DRAFT_REVIEW_SCHEMA_SQL)
            self._connection.execute(
                "INSERT OR IGNORE INTO synthetic_patch_draft_review_metadata "
                "(singleton, schema_version, synthetic_only) VALUES (1, ?, 1)",
                (PATCH_DRAFT_REVIEW_SCHEMA_VERSION,),
            )
            if not self.verify_metadata():
                raise GovernanceRejected("unsupported patch draft review schema")

    def verify_metadata(self) -> bool:
        with self._lock:
            rows = self._connection.execute(
                "SELECT singleton, schema_version, synthetic_only "
                "FROM synthetic_patch_draft_review_metadata"
            ).fetchall()
            return (
                len(rows) == 1
                and rows[0]["singleton"] == 1
                and rows[0]["schema_version"] == PATCH_DRAFT_REVIEW_SCHEMA_VERSION
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
        book: SyntheticPatchDraftManifestBook,
        source_receipt_id: str,
        *,
        submitted_at: datetime,
    ) -> SyntheticPatchDraftReviewRecord:
        if submitted_at.tzinfo is None:
            raise GovernanceRejected("timezone-aware patch draft submission required")
        if not isinstance(book, SyntheticPatchDraftManifestBook):
            raise GovernanceRejected("typed synthetic patch draft book required")
        if not book.verify_manifest_chain():
            raise GovernanceRejected("intact synthetic patch draft chain required")
        matches = [
            item for item in book.manifests if item.source_receipt_id == source_receipt_id
        ]
        if len(matches) != 1:
            raise GovernanceRejected("one synthetic patch draft manifest required")
        manifest = matches[0]
        self._validate_manifest(manifest)
        if submitted_at < manifest.drafted_at:
            raise GovernanceRejected("submission cannot predate patch draft")
        before = book.evidence()["report_digest"]
        payload = {**manifest.digest_value(), "manifest_digest": manifest.manifest_digest}
        with self._lock:
            try:
                with self._transaction():
                    if not self.verify_metadata():
                        raise GovernanceRejected("patch draft review metadata is invalid")
                    existing = self._connection.execute(
                        "SELECT * FROM synthetic_patch_draft_review_records "
                        "WHERE manifest_id = ?", (manifest.manifest_id,)
                    ).fetchone()
                    if existing is not None:
                        if (
                            existing["manifest_digest"] != manifest.manifest_digest
                            or existing["source_receipt_id"] != source_receipt_id
                        ):
                            raise GovernanceRejected("patch draft submission collision")
                        if not self.verify_record_bindings():
                            raise GovernanceRejected("existing patch draft review is invalid")
                        record = self._record_from_row(existing)
                    else:
                        self._connection.execute(
                            """
                            INSERT INTO synthetic_patch_draft_review_records (
                                manifest_id, manifest_digest, source_receipt_id,
                                source_receipt_digest, source_packet_id, manifest_json,
                                state, submitted_at, patch_content_present,
                                diff_content_present, source_code_changed, filesystem_written,
                                automatic_application_allowed,
                                safety_baseline_relaxation_allowed, execution_allowed,
                                production_activation_allowed
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0)
                            """,
                            (
                                manifest.manifest_id, manifest.manifest_digest,
                                manifest.source_receipt_id,
                                manifest.source_receipt_digest,
                                manifest.source_packet_id,
                                json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                           separators=(",", ":")),
                                PatchDraftReviewState.PENDING_ETERNIAN_REVIEW.value,
                                submitted_at.isoformat(),
                            ),
                        )
                        self._append_audit(
                            manifest.manifest_id, "SUBMITTED",
                            "synthetic:system:patch-draft-review-docket",
                            manifest.manifest_digest, submitted_at,
                        )
                        record = self._get_record(manifest.manifest_id)
                    if before != book.evidence()["report_digest"]:
                        raise GovernanceRejected("patch draft changed during submission")
                    return record
            except sqlite3.Error as exc:
                raise GovernanceRejected("patch draft submission transaction failed") from exc

    @staticmethod
    def _validate_manifest(manifest: SyntheticPatchDraftManifest) -> None:
        if (
            not isinstance(manifest, SyntheticPatchDraftManifest)
            or manifest.manifest_digest != canonical_digest(manifest.digest_value())
            or manifest.state != PATCH_DRAFT_MANIFEST_STATE
            or not manifest.eternian_review_required
            or manifest.patch_content_present
            or manifest.diff_content_present
            or manifest.source_code_changed
            or manifest.filesystem_written
            or manifest.automatic_application_allowed
            or manifest.safety_baseline_relaxation_allowed
            or manifest.execution_allowed
            or manifest.network_access_allowed
            or manifest.money_movement_allowed
            or manifest.production_activation_allowed
        ):
            raise GovernanceRejected("intact metadata-only patch draft required")

    def record_eternian_review(
        self,
        manifest_id: str,
        *,
        review_id: str,
        reviewer_id: str,
        decision: PatchDraftReviewDecision,
        findings_digest: str,
        reviewed_at: datetime,
    ) -> SyntheticPatchDraftReviewRecord:
        if (
            not _valid_prefixed_id(review_id, _REVIEW_ID_PREFIX)
            or not _valid_prefixed_id(reviewer_id, _REVIEWER_PREFIX)
            or not isinstance(decision, PatchDraftReviewDecision)
            or not _valid_digest(findings_digest)
            or reviewed_at.tzinfo is None
        ):
            raise GovernanceRejected("valid Eternian patch draft review metadata required")
        with self._lock:
            try:
                with self._transaction():
                    if not self.verify_metadata():
                        raise GovernanceRejected("patch draft review metadata is invalid")
                    row = self._connection.execute(
                        "SELECT * FROM synthetic_patch_draft_review_records "
                        "WHERE manifest_id = ?", (manifest_id,)
                    ).fetchone()
                    if row is None:
                        raise GovernanceRejected("unknown patch draft manifest")
                    current = self._record_from_row(row)
                    if current.review_id is not None:
                        expected = (review_id, reviewer_id, decision, findings_digest, reviewed_at)
                        actual = (
                            current.review_id, current.reviewer_id,
                            current.review_decision, current.findings_digest,
                            current.reviewed_at,
                        )
                        if expected != actual:
                            raise GovernanceRejected("patch draft review already recorded")
                        if not self.verify_record_bindings():
                            raise GovernanceRejected("existing patch draft review is invalid")
                        return current
                    if reviewed_at < current.submitted_at:
                        raise GovernanceRejected("review cannot predate submission")
                    state = _STATE_BY_DECISION[decision]
                    value = {
                        "manifest_id": manifest_id,
                        "manifest_digest": current.manifest.manifest_digest,
                        "review_id": review_id,
                        "reviewer_id": reviewer_id,
                        "decision": decision.value,
                        "findings_digest": findings_digest,
                        "reviewed_at": reviewed_at.isoformat(),
                        "resulting_state": state.value,
                        "patch_content_present": False,
                        "diff_content_present": False,
                        "source_code_changed": False,
                        "filesystem_written": False,
                        "automatic_application_allowed": False,
                        "safety_baseline_relaxation_allowed": False,
                        "execution_allowed": False,
                        "production_activation_allowed": False,
                    }
                    review_digest = canonical_digest(value)
                    self._connection.execute(
                        """
                        UPDATE synthetic_patch_draft_review_records SET
                            state = ?, review_id = ?, reviewer_id = ?,
                            review_decision = ?, findings_digest = ?, reviewed_at = ?,
                            review_digest = ?
                        WHERE manifest_id = ? AND state = 'PENDING_ETERNIAN_REVIEW'
                        """,
                        (state.value, review_id, reviewer_id, decision.value,
                         findings_digest, reviewed_at.isoformat(), review_digest,
                         manifest_id),
                    )
                    self._append_audit(
                        manifest_id, "ETERNIAN_REVIEWED", reviewer_id,
                        review_digest, reviewed_at,
                    )
                    return self._get_record(manifest_id)
            except sqlite3.Error as exc:
                raise GovernanceRejected("patch draft review transaction failed") from exc

    def _append_audit(
        self,
        manifest_id: str,
        action: str,
        actor_id: str,
        evidence_digest: str,
        recorded_at: datetime,
    ) -> None:
        latest = self._connection.execute(
            "SELECT audit_sequence, audit_digest FROM synthetic_patch_draft_review_audit "
            "ORDER BY audit_sequence DESC LIMIT 1"
        ).fetchone()
        sequence = (latest["audit_sequence"] if latest else 0) + 1
        previous = latest["audit_digest"] if latest else "0" * 64
        value = {
            "audit_sequence": sequence, "manifest_id": manifest_id,
            "action": action, "actor_id": actor_id,
            "evidence_digest": evidence_digest, "previous_digest": previous,
            "recorded_at": recorded_at.isoformat(),
        }
        self._connection.execute(
            "INSERT INTO synthetic_patch_draft_review_audit "
            "(audit_sequence, manifest_id, action, actor_id, evidence_digest, "
            "previous_digest, audit_digest, recorded_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (sequence, manifest_id, action, actor_id, evidence_digest, previous,
             canonical_digest(value), recorded_at.isoformat()),
        )

    @staticmethod
    def _manifest_from_payload(payload: object) -> SyntheticPatchDraftManifest:
        if not isinstance(payload, dict):
            raise GovernanceRejected("stored patch draft object required")
        return SyntheticPatchDraftManifest(
            int(payload["sequence"]), str(payload["manifest_id"]),
            str(payload["source_receipt_id"]), str(payload["source_receipt_digest"]),
            str(payload["source_assessment_id"]), str(payload["source_packet_id"]),
            str(payload["operator_id"]),
            SyntheticPatchOperatorDecision(str(payload["decision"])),
            tuple(str(value) for value in payload["draft_scopes"]),
            tuple(str(value) for value in payload["target_path_digests"]),
            tuple(str(value) for value in payload["required_checks"]),
            datetime.fromisoformat(str(payload["drafted_at"])),
            str(payload["previous_digest"]), str(payload["manifest_digest"]),
            str(payload["state"]), bool(payload["eternian_review_required"]),
            bool(payload["patch_content_present"]), bool(payload["diff_content_present"]),
            bool(payload["source_code_changed"]), bool(payload["filesystem_written"]),
            bool(payload["automatic_application_allowed"]),
            bool(payload["safety_baseline_relaxation_allowed"]),
            bool(payload["execution_allowed"]), bool(payload["network_access_allowed"]),
            bool(payload["money_movement_allowed"]),
            bool(payload["production_activation_allowed"]),
        )

    @classmethod
    def _record_from_row(cls, row: sqlite3.Row) -> SyntheticPatchDraftReviewRecord:
        try:
            manifest = cls._manifest_from_payload(json.loads(row["manifest_json"]))
            if (
                manifest.manifest_id != row["manifest_id"]
                or manifest.manifest_digest != row["manifest_digest"]
                or manifest.source_receipt_id != row["source_receipt_id"]
                or manifest.source_receipt_digest != row["source_receipt_digest"]
                or manifest.source_packet_id != row["source_packet_id"]
            ):
                raise GovernanceRejected("stored patch draft binding is invalid")
            decision = (
                PatchDraftReviewDecision(row["review_decision"])
                if row["review_decision"] is not None else None
            )
            return SyntheticPatchDraftReviewRecord(
                manifest, PatchDraftReviewState(row["state"]),
                datetime.fromisoformat(row["submitted_at"]),
                row["review_id"], row["reviewer_id"], decision,
                row["findings_digest"],
                datetime.fromisoformat(row["reviewed_at"])
                if row["reviewed_at"] is not None else None,
                row["review_digest"], bool(row["patch_content_present"]),
                bool(row["diff_content_present"]), bool(row["source_code_changed"]),
                bool(row["filesystem_written"]),
                bool(row["automatic_application_allowed"]),
                bool(row["safety_baseline_relaxation_allowed"]),
                bool(row["execution_allowed"]),
                bool(row["production_activation_allowed"]),
            )
        except (GovernanceRejected, KeyError, TypeError, ValueError) as exc:
            raise GovernanceRejected("stored patch draft review is invalid") from exc

    def _get_record(self, manifest_id: str) -> SyntheticPatchDraftReviewRecord:
        row = self._connection.execute(
            "SELECT * FROM synthetic_patch_draft_review_records WHERE manifest_id = ?",
            (manifest_id,),
        ).fetchone()
        if row is None:
            raise GovernanceRejected("unknown patch draft manifest")
        return self._record_from_row(row)

    def get(self, manifest_id: str) -> SyntheticPatchDraftReviewRecord:
        with self._lock:
            return self._get_record(manifest_id)

    def ready_source(self, manifest_id: str) -> SyntheticPatchDraftReviewRecord:
        with self._lock:
            if not self.verify_record_bindings():
                raise GovernanceRejected("patch draft review docket is invalid")
            record = self._get_record(manifest_id)
            if record.state is not PatchDraftReviewState.READY_FOR_SYNTHETIC_PATCH_DRAFT_SHADOW:
                raise GovernanceRejected("patch draft is not shadow-ready")
            return record

    def verify_audit_chain(self) -> bool:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM synthetic_patch_draft_review_audit ORDER BY audit_sequence"
            ).fetchall()
            previous = "0" * 64
            for sequence, row in enumerate(rows, start=1):
                value = {
                    "audit_sequence": sequence, "manifest_id": row["manifest_id"],
                    "action": row["action"], "actor_id": row["actor_id"],
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
                "SELECT * FROM synthetic_patch_draft_review_records ORDER BY manifest_id"
            ).fetchall()
            audits = self._connection.execute(
                "SELECT * FROM synthetic_patch_draft_review_audit ORDER BY audit_sequence"
            ).fetchall()
            by_key = {(row["manifest_id"], row["action"]): row for row in audits}
            try:
                for row in rows:
                    record = self._record_from_row(row)
                    submitted = by_key.get((row["manifest_id"], "SUBMITTED"))
                    if (
                        submitted is None
                        or submitted["actor_id"]
                        != "synthetic:system:patch-draft-review-docket"
                        or submitted["evidence_digest"] != row["manifest_digest"]
                        or submitted["recorded_at"] != row["submitted_at"]
                    ):
                        return False
                    reviewed = by_key.get((row["manifest_id"], "ETERNIAN_REVIEWED"))
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
            expected = sum(1 if row["review_id"] is None else 2 for row in rows)
            return len(audits) == expected

    def evidence(self) -> dict[str, object]:
        with self._lock:
            counts = {state.value: 0 for state in PatchDraftReviewState}
            record_digests = []
            for row in self._connection.execute(
                "SELECT * FROM synthetic_patch_draft_review_records ORDER BY manifest_id"
            ):
                counts[row["state"]] += 1
                record = self._record_from_row(row)
                record_digests.append(canonical_digest({
                    "manifest_digest": record.manifest.manifest_digest,
                    "state": record.state.value,
                    "submitted_at": record.submitted_at.isoformat(),
                    "review_digest": record.review_digest,
                }))
            latest = self._connection.execute(
                "SELECT audit_digest FROM synthetic_patch_draft_review_audit "
                "ORDER BY audit_sequence DESC LIMIT 1"
            ).fetchone()
            value = {
                "schema": "nurion.pg.synthetic-patch-draft-review-evidence.v1",
                "database_engine": "SQLite",
                "schema_version": PATCH_DRAFT_REVIEW_SCHEMA_VERSION,
                "schema_digest": canonical_digest(PATCH_DRAFT_REVIEW_SCHEMA_SQL),
                "metadata_valid": self.verify_metadata(),
                "state_counts": counts,
                "record_digests": record_digests,
                "audit_head_digest": latest["audit_digest"] if latest else "0" * 64,
                "audit_chain_valid": self.verify_audit_chain(),
                "record_bindings_valid": self.verify_record_bindings(),
                "maximum_state": MAXIMUM_PATCH_DRAFT_REVIEW_STATE,
                "patch_content_present": False,
                "diff_content_present": False,
                "source_code_changed": False,
                "filesystem_written": False,
                "application_method_present": False,
                "safety_baseline_relaxation_method_present": False,
                "execution_method_present": False,
                "network_access_method_present": False,
                "money_movement_executed": False,
                "production_activation_allowed": False,
            }
            return {**value, "report_digest": canonical_digest(value)}
