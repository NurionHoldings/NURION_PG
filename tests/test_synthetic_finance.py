from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_finance import (
    EntrySide,
    Journal,
    LedgerEntry,
    SettlementSimulation,
    SyntheticLedger,
)


def digest(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def journal(**changes) -> Journal:
    value = Journal(
        "synthetic:j-1",
        "synthetic:key-1",
        datetime(2026, 9, 17, tzinfo=UTC),
        (
            LedgerEntry("synthetic:cash", EntrySide.DEBIT, 1000, "KRW"),
            LedgerEntry("synthetic:payable", EntrySide.CREDIT, 1000, "KRW"),
        ),
        digest("fixture"),
    )
    return replace(value, **changes)


class SyntheticFinanceTests(unittest.TestCase):
    def test_balanced_journal_is_append_only_and_idempotent(self):
        ledger = SyntheticLedger()
        value = journal()
        self.assertIs(ledger.post(value), value)
        self.assertIs(ledger.post(value), value)
        self.assertEqual(len(ledger.journals), 1)
        self.assertFalse(ledger.evidence()["money_movement_executed"])

    def test_unbalanced_mixed_currency_and_nonpositive_entries_are_rejected(self):
        with self.assertRaises(GovernanceRejected):
            journal(entries=(
                LedgerEntry("synthetic:a", EntrySide.DEBIT, 1000, "KRW"),
                LedgerEntry("synthetic:b", EntrySide.CREDIT, 999, "KRW"),
            ))
        with self.assertRaises(GovernanceRejected):
            journal(entries=(
                LedgerEntry("synthetic:a", EntrySide.DEBIT, 1000, "KRW"),
                LedgerEntry("synthetic:b", EntrySide.CREDIT, 1000, "USD"),
            ))
        with self.assertRaises(GovernanceRejected):
            LedgerEntry("synthetic:a", EntrySide.DEBIT, 0, "KRW")

    def test_real_looking_references_and_execution_are_rejected(self):
        with self.assertRaises(GovernanceRejected):
            LedgerEntry("merchant-123", EntrySide.DEBIT, 1000, "KRW")
        with self.assertRaises(GovernanceRejected):
            journal(execution_allowed=True)

    def test_idempotency_payload_mismatch_and_duplicate_identity_are_rejected(self):
        ledger = SyntheticLedger()
        ledger.post(journal())
        with self.assertRaises(GovernanceRejected):
            ledger.post(journal(entries=(
                LedgerEntry("synthetic:cash", EntrySide.DEBIT, 2000, "KRW"),
                LedgerEntry("synthetic:payable", EntrySide.CREDIT, 2000, "KRW"),
            )))
        with self.assertRaises(GovernanceRejected):
            ledger.post(journal(idempotency_key="synthetic:key-2"))

    def test_settlement_is_calculation_only_and_never_executes(self):
        value = SettlementSimulation(
            "synthetic:s-1", "synthetic:m-1", 10000, 500, 1000, "KRW", digest("policy")
        )
        self.assertEqual(value.net_minor, 8500)
        self.assertFalse(value.execution_allowed)
        with self.assertRaises(GovernanceRejected):
            replace(value, execution_allowed=True)
        with self.assertRaises(GovernanceRejected):
            replace(value, fee_minor=10001)
        with self.assertRaises(GovernanceRejected):
            replace(value, currency="123")
        with self.assertRaises(GovernanceRejected):
            replace(value, policy_digest="z" * 64)


if __name__ == "__main__":
    unittest.main()
