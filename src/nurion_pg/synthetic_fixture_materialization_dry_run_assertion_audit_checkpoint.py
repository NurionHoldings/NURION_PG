"""Read-only checkpoint of an assertion audit evidence-ledger tip."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .arkaon.governance import GovernanceRejected, canonical_digest
from .synthetic_fixture_materialization_dry_run_assertion_audit_ledger import (
    SyntheticFixtureMaterializationDryRunAssertionAuditLedger,
)

AUDIT_CHECKPOINT_STATE = (
    "SYNTHETIC_FIXTURE_MATERIALIZATION_DRY_RUN_ASSERTION_AUDIT_LEDGER_CHECKPOINTED"
)


def _valid_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


@dataclass(frozen=True)
class SyntheticFixtureMaterializationDryRunAssertionAuditCheckpoint:
    record_count: int
    tip_record_digest: str
    ledger_report_digest: str
    checkpointed_at: datetime
    state: str
    checkpoint_digest: str

    def __post_init__(self) -> None:
        if (
            self.record_count <= 0
            or not _valid_digest(self.tip_record_digest)
            or not _valid_digest(self.ledger_report_digest)
            or self.checkpointed_at.tzinfo is None
            or self.state != AUDIT_CHECKPOINT_STATE
            or self.checkpoint_digest != canonical_digest(self.digest_value())
        ):
            raise GovernanceRejected("valid assertion audit ledger checkpoint required")

    def digest_value(self) -> dict[str, object]:
        return {
            "record_count": self.record_count,
            "tip_record_digest": self.tip_record_digest,
            "ledger_report_digest": self.ledger_report_digest,
            "checkpointed_at": self.checkpointed_at.isoformat(),
            "state": self.state,
            "evaluation_allowed": False,
            "dry_run_execution_allowed": False,
            "fixture_materialization_allowed": False,
            "activation_allowed": False,
        }


def checkpoint_audit_ledger(
    ledger: SyntheticFixtureMaterializationDryRunAssertionAuditLedger,
    *,
    checkpointed_at: datetime,
) -> SyntheticFixtureMaterializationDryRunAssertionAuditCheckpoint:
    if (
        not isinstance(ledger, SyntheticFixtureMaterializationDryRunAssertionAuditLedger)
        or not ledger.verify_chain()
        or checkpointed_at.tzinfo is None
    ):
        raise GovernanceRejected("intact typed assertion audit ledger required")
    records = ledger.records
    if not records or checkpointed_at < records[-1].recorded_at:
        raise GovernanceRejected("non-empty chronological assertion audit ledger required")
    before = ledger.evidence()
    values = {
        "record_count": len(records),
        "tip_record_digest": records[-1].record_digest,
        "ledger_report_digest": before["report_digest"],
        "checkpointed_at": checkpointed_at.isoformat(),
        "state": AUDIT_CHECKPOINT_STATE,
        "evaluation_allowed": False,
        "dry_run_execution_allowed": False,
        "fixture_materialization_allowed": False,
        "activation_allowed": False,
    }
    checkpoint = SyntheticFixtureMaterializationDryRunAssertionAuditCheckpoint(
        len(records),
        records[-1].record_digest,
        before["report_digest"],
        checkpointed_at,
        AUDIT_CHECKPOINT_STATE,
        canonical_digest(values),
    )
    if before != ledger.evidence():
        raise GovernanceRejected("assertion audit ledger changed during checkpoint")
    return checkpoint


def evidence(
    checkpoint: SyntheticFixtureMaterializationDryRunAssertionAuditCheckpoint,
) -> dict[str, object]:
    if not isinstance(
        checkpoint, SyntheticFixtureMaterializationDryRunAssertionAuditCheckpoint
    ):
        raise GovernanceRejected("intact assertion audit ledger checkpoint required")
    checkpoint.__post_init__()
    values = {
        "schema": "nurion.pg.synthetic-fixture-materialization-dry-run-assertion-audit-checkpoint-evidence.v1",
        "mode": "UNREGISTERED_SYNTHETIC_ONLY",
        "checkpoint_digest": checkpoint.checkpoint_digest,
        "record_count": checkpoint.record_count,
        "tip_record_digest": checkpoint.tip_record_digest,
        "ledger_report_digest": checkpoint.ledger_report_digest,
        "maximum_state": AUDIT_CHECKPOINT_STATE,
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
