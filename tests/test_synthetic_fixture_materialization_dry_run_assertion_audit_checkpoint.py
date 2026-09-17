from __future__ import annotations

import unittest
from datetime import timedelta

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.synthetic_fixture_materialization_dry_run_assertion_audit import audit_assertion
from nurion_pg.synthetic_fixture_materialization_dry_run_assertion_audit_checkpoint import (
    AUDIT_CHECKPOINT_STATE,
    checkpoint_audit_ledger,
    evidence,
)
from nurion_pg.synthetic_fixture_materialization_dry_run_assertion_audit_ledger import (
    SyntheticFixtureMaterializationDryRunAssertionAuditLedger,
)
from nurion_pg.synthetic_fixture_materialization_dry_run_assertions import (
    SyntheticFixtureMaterializationDryRunAssertionBook,
)
from tests.test_patch_draft_limited_promotion_reconfirmation_intake import NOW
from tests.test_synthetic_fixture_materialization_dry_run_assertions import reviewed_expectation
from tests.test_synthetic_patch_draft_limited_promotion_activation_drafts import close_sources


def source():
    resources, sd, source_ledger, docket, review = reviewed_expectation()
    book = SyntheticFixtureMaterializationDryRunAssertionBook()
    item = book.draft_from_review(docket, review.expectation.expectation_id, drafted_at=NOW)
    audit = audit_assertion(book, item, audited_at=NOW)
    ledger = SyntheticFixtureMaterializationDryRunAssertionAuditLedger()
    ledger.record(book, item, audit, recorded_at=NOW)
    return resources, sd, source_ledger, ledger


class AssertionAuditCheckpointTests(unittest.TestCase):
    def test_read_only_checkpoint_and_authority(self):
        resources, sd, source_ledger, ledger = source()
        checkpoint = checkpoint_audit_ledger(ledger, checkpointed_at=NOW)
        self.assertEqual(checkpoint.state, AUDIT_CHECKPOINT_STATE)
        report = evidence(checkpoint)
        self.assertEqual(report["record_count"], 1)
        self.assertEqual(report["tip_record_digest"], ledger.records[-1].record_digest)
        for key in report:
            if key.endswith("_present") or key.endswith("_allowed") or key.endswith("_executed") or key.endswith("_used"):
                self.assertFalse(report[key])
        close_sources(resources, sd, source_ledger)

    def test_empty_type_and_time_fail_closed(self):
        with self.assertRaises(GovernanceRejected):
            checkpoint_audit_ledger(object(), checkpointed_at=NOW)
        with self.assertRaises(GovernanceRejected):
            checkpoint_audit_ledger(
                SyntheticFixtureMaterializationDryRunAssertionAuditLedger(),
                checkpointed_at=NOW,
            )
        resources, sd, source_ledger, ledger = source()
        with self.assertRaises(GovernanceRejected):
            checkpoint_audit_ledger(ledger, checkpointed_at=NOW - timedelta(seconds=1))
        close_sources(resources, sd, source_ledger)

    def test_tampered_ledger_and_checkpoint_fail_closed(self):
        resources, sd, source_ledger, ledger = source()
        object.__setattr__(ledger.records[-1], "state", "TAMPERED")
        with self.assertRaises(GovernanceRejected):
            checkpoint_audit_ledger(ledger, checkpointed_at=NOW)
        close_sources(resources, sd, source_ledger)
        resources, sd, source_ledger, ledger = source()
        checkpoint = checkpoint_audit_ledger(ledger, checkpointed_at=NOW)
        object.__setattr__(checkpoint, "state", "TAMPERED")
        object.__setattr__(
            checkpoint, "checkpoint_digest", canonical_digest(checkpoint.digest_value())
        )
        with self.assertRaises(GovernanceRejected):
            evidence(checkpoint)
        close_sources(resources, sd, source_ledger)


if __name__ == "__main__":
    unittest.main()
