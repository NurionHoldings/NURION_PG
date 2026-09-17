from __future__ import annotations

import unittest
from datetime import timedelta

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_fixture_materialization_dry_run_assertion_audit import audit_assertion
from nurion_pg.synthetic_fixture_materialization_dry_run_assertion_audit_ledger import (
    AUDIT_LEDGER_STATE,
    SyntheticFixtureMaterializationDryRunAssertionAuditLedger,
)
from nurion_pg.synthetic_fixture_materialization_dry_run_assertions import (
    SyntheticFixtureMaterializationDryRunAssertionBook,
)
from tests.test_patch_draft_limited_promotion_reconfirmation_intake import NOW
from tests.test_synthetic_fixture_materialization_dry_run_assertions import reviewed_expectation
from tests.test_synthetic_patch_draft_limited_promotion_activation_drafts import close_sources


def source():
    resources, sd, ledger, docket, review = reviewed_expectation()
    book = SyntheticFixtureMaterializationDryRunAssertionBook()
    item = book.draft_from_review(docket, review.expectation.expectation_id, drafted_at=NOW)
    audit = audit_assertion(book, item, audited_at=NOW)
    return resources, sd, ledger, book, item, audit


class AssertionAuditLedgerTests(unittest.TestCase):
    def test_append_only_idempotent_record_and_authority(self):
        resources, sd, source_ledger, book, item, audit = source()
        ledger = SyntheticFixtureMaterializationDryRunAssertionAuditLedger()
        first = ledger.record(book, item, audit, recorded_at=NOW)
        self.assertIs(ledger.record(book, item, audit, recorded_at=NOW), first)
        self.assertEqual(first.state, AUDIT_LEDGER_STATE)
        report = ledger.evidence()
        self.assertTrue(report["audit_chain_valid"])
        self.assertEqual(report["record_count"], 1)
        for key in report:
            if key.endswith("_present") or key.endswith("_allowed") or key.endswith("_executed") or key.endswith("_used"):
                self.assertFalse(report[key])
        close_sources(resources, sd, source_ledger)

    def test_type_time_and_source_mismatch_fail_closed(self):
        resources, sd, source_ledger, book, item, audit = source()
        ledger = SyntheticFixtureMaterializationDryRunAssertionAuditLedger()
        with self.assertRaises(GovernanceRejected):
            ledger.record(object(), item, audit, recorded_at=NOW)
        with self.assertRaises(GovernanceRejected):
            ledger.record(book, item, audit, recorded_at=NOW - timedelta(seconds=1))
        object.__setattr__(audit, "assertion_digest", "f" * 64)
        with self.assertRaises(GovernanceRejected):
            ledger.record(book, item, audit, recorded_at=NOW)
        close_sources(resources, sd, source_ledger)

    def test_record_chain_tamper_fails_closed(self):
        resources, sd, source_ledger, book, item, audit = source()
        ledger = SyntheticFixtureMaterializationDryRunAssertionAuditLedger()
        record = ledger.record(book, item, audit, recorded_at=NOW)
        object.__setattr__(record, "previous_digest", "f" * 64)
        self.assertFalse(ledger.verify_chain())
        with self.assertRaises(GovernanceRejected):
            ledger.record(book, item, audit, recorded_at=NOW)
        close_sources(resources, sd, source_ledger)


if __name__ == "__main__":
    unittest.main()
