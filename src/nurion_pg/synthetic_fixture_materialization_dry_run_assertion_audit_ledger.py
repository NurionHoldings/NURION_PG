"""Append-only evidence ledger for read-only assertion boundary audits."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest
from .synthetic_fixture_materialization_dry_run_assertion_audit import (
    AUDIT_STATE,
    SyntheticFixtureMaterializationDryRunAssertionAudit,
    audit_assertion,
)
from .synthetic_fixture_materialization_dry_run_assertions import (
    SyntheticFixtureMaterializationDryRunAssertion,
    SyntheticFixtureMaterializationDryRunAssertionBook,
)

AUDIT_LEDGER_STATE = "SYNTHETIC_FIXTURE_MATERIALIZATION_DRY_RUN_ASSERTION_AUDIT_RECORDED"


def _valid_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


@dataclass(frozen=True)
class SyntheticFixtureMaterializationDryRunAssertionAuditRecord:
    sequence: int
    assertion_id: str
    assertion_digest: str
    audit_digest: str
    audited_at: datetime
    recorded_at: datetime
    previous_digest: str
    state: str
    record_digest: str

    def __post_init__(self) -> None:
        if (
            self.sequence <= 0
            or not _valid_digest(self.assertion_digest)
            or not _valid_digest(self.audit_digest)
            or self.audited_at.tzinfo is None
            or self.recorded_at.tzinfo is None
            or self.recorded_at < self.audited_at
            or not _valid_digest(self.previous_digest)
            or self.state != AUDIT_LEDGER_STATE
            or self.record_digest != canonical_digest(self.digest_value())
        ):
            raise GovernanceRejected("valid assertion audit record required")

    def digest_value(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "assertion_id": self.assertion_id,
            "assertion_digest": self.assertion_digest,
            "audit_digest": self.audit_digest,
            "audited_at": self.audited_at.isoformat(),
            "recorded_at": self.recorded_at.isoformat(),
            "previous_digest": self.previous_digest,
            "state": self.state,
            "evaluation_allowed": False,
            "dry_run_execution_allowed": False,
            "fixture_materialization_allowed": False,
            "activation_allowed": False,
        }


class SyntheticFixtureMaterializationDryRunAssertionAuditLedger:
    def __init__(self) -> None:
        self._records: list[SyntheticFixtureMaterializationDryRunAssertionAuditRecord] = []
        self._by_audit: dict[str, SyntheticFixtureMaterializationDryRunAssertionAuditRecord] = {}
        self._lock = RLock()

    @property
    def records(self) -> tuple[SyntheticFixtureMaterializationDryRunAssertionAuditRecord, ...]:
        with self._lock:
            return tuple(self._records)

    def record(
        self,
        book: SyntheticFixtureMaterializationDryRunAssertionBook,
        item: SyntheticFixtureMaterializationDryRunAssertion,
        audit: SyntheticFixtureMaterializationDryRunAssertionAudit,
        *,
        recorded_at: datetime,
    ) -> SyntheticFixtureMaterializationDryRunAssertionAuditRecord:
        if (
            not isinstance(book, SyntheticFixtureMaterializationDryRunAssertionBook)
            or not book.verify_chain()
            or item not in book.assertions
            or not isinstance(audit, SyntheticFixtureMaterializationDryRunAssertionAudit)
            or audit.state != AUDIT_STATE
            or recorded_at.tzinfo is None
            or recorded_at < audit.audited_at
        ):
            raise GovernanceRejected("intact typed assertion audit required")
        expected = audit_assertion(book, item, audited_at=audit.audited_at)
        if expected != audit:
            raise GovernanceRejected("audit does not match assertion source")
        with self._lock:
            if not self.verify_chain():
                raise GovernanceRejected("existing assertion audit ledger invalid")
            old = self._by_audit.get(audit.audit_digest)
            if old is not None:
                return old
            previous = self._records[-1].record_digest if self._records else "0" * 64
            values = {
                "sequence": len(self._records) + 1,
                "assertion_id": item.assertion_id,
                "assertion_digest": item.assertion_digest,
                "audit_digest": audit.audit_digest,
                "audited_at": audit.audited_at.isoformat(),
                "recorded_at": recorded_at.isoformat(),
                "previous_digest": previous,
                "state": AUDIT_LEDGER_STATE,
                "evaluation_allowed": False,
                "dry_run_execution_allowed": False,
                "fixture_materialization_allowed": False,
                "activation_allowed": False,
            }
            record = SyntheticFixtureMaterializationDryRunAssertionAuditRecord(
                len(self._records) + 1,
                item.assertion_id,
                item.assertion_digest,
                audit.audit_digest,
                audit.audited_at,
                recorded_at,
                previous,
                AUDIT_LEDGER_STATE,
                canonical_digest(values),
            )
            self._records.append(record)
            self._by_audit[audit.audit_digest] = record
            return record

    def verify_chain(self) -> bool:
        with self._lock:
            previous = "0" * 64
            for sequence, record in enumerate(self._records, 1):
                if (
                    record.sequence != sequence
                    or record.previous_digest != previous
                    or not _valid_digest(record.assertion_digest)
                    or not _valid_digest(record.audit_digest)
                    or record.audited_at.tzinfo is None
                    or record.recorded_at.tzinfo is None
                    or record.recorded_at < record.audited_at
                    or record.state != AUDIT_LEDGER_STATE
                    or record.record_digest != canonical_digest(record.digest_value())
                ):
                    return False
                previous = record.record_digest
            return len(self._records) == len(self._by_audit) and all(
                self._by_audit.get(record.audit_digest) is record for record in self._records
            )

    def evidence(self) -> dict[str, object]:
        with self._lock:
            values = {
                "schema": "nurion.pg.synthetic-fixture-materialization-dry-run-assertion-audit-ledger-evidence.v1",
                "mode": "UNREGISTERED_SYNTHETIC_ONLY",
                "record_count": len(self._records),
                "record_digests": [record.record_digest for record in self._records],
                "audit_chain_valid": self.verify_chain(),
                "maximum_state": AUDIT_LEDGER_STATE,
                "evaluation_method_present": False,
                "dry_run_execution_method_present": False,
                "fixture_materialization_method_present": False,
                "activation_method_present": False,
                "network_access_method_present": False,
                "automatic_merge_method_present": False,
                "automatic_deploy_method_present": False,
                "credentials_used": False,
                "personal_data_used": False,
                "money_movement_executed": False,
            }
            return {**values, "report_digest": canonical_digest(values)}
