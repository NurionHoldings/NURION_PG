"""Synthetic-only balanced ledger and settlement calculations.

No provider adapter, network I/O, real customer identifier, or money movement
exists in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .arkaon.governance import GovernanceRejected, canonical_digest


class EntrySide(StrEnum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


@dataclass(frozen=True)
class LedgerEntry:
    account_ref: str
    side: EntrySide
    amount_minor: int
    currency: str

    def __post_init__(self) -> None:
        if (
            not self.account_ref.startswith("synthetic:")
            or self.amount_minor <= 0
            or len(self.currency) != 3
            or not self.currency.isascii()
            or not self.currency.isalpha()
            or self.currency != self.currency.upper()
        ):
            raise GovernanceRejected("synthetic account, positive amount and currency required")


@dataclass(frozen=True)
class Journal:
    journal_id: str
    idempotency_key: str
    created_at: datetime
    entries: tuple[LedgerEntry, ...]
    evidence_digest: str
    synthetic_only: bool = True
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if (
            not self.journal_id.startswith("synthetic:")
            or not self.idempotency_key.startswith("synthetic:")
            or self.created_at.tzinfo is None
            or len(self.entries) < 2
            or len(self.evidence_digest) != 64
            or any(char not in "0123456789abcdef" for char in self.evidence_digest)
            or not self.synthetic_only
            or self.execution_allowed
        ):
            raise GovernanceRejected("complete non-executable synthetic journal required")
        currencies = {entry.currency for entry in self.entries}
        debit = sum(entry.amount_minor for entry in self.entries if entry.side is EntrySide.DEBIT)
        credit = sum(entry.amount_minor for entry in self.entries if entry.side is EntrySide.CREDIT)
        if len(currencies) != 1 or debit != credit:
            raise GovernanceRejected("journal must balance in exactly one currency")

    @property
    def digest(self) -> str:
        return canonical_digest(
            {
                "journal_id": self.journal_id,
                "idempotency_key": self.idempotency_key,
                "created_at": self.created_at.isoformat(),
                "entries": [
                    {
                        "account_ref": entry.account_ref,
                        "side": entry.side.value,
                        "amount_minor": entry.amount_minor,
                        "currency": entry.currency,
                    }
                    for entry in self.entries
                ],
                "evidence_digest": self.evidence_digest,
                "synthetic_only": self.synthetic_only,
                "execution_allowed": self.execution_allowed,
            }
        )


class SyntheticLedger:
    def __init__(self) -> None:
        self._journals: list[Journal] = []
        self._by_idempotency: dict[str, Journal] = {}

    @property
    def journals(self) -> tuple[Journal, ...]:
        return tuple(self._journals)

    def post(self, journal: Journal) -> Journal:
        existing = self._by_idempotency.get(journal.idempotency_key)
        if existing is not None:
            if existing.digest != journal.digest:
                raise GovernanceRejected("idempotency key payload mismatch")
            return existing
        if any(item.journal_id == journal.journal_id for item in self._journals):
            raise GovernanceRejected("duplicate journal identity")
        self._journals.append(journal)
        self._by_idempotency[journal.idempotency_key] = journal
        return journal

    def evidence(self) -> dict[str, object]:
        value = {
            "schema": "nurion.pg.synthetic-ledger-evidence.v1",
            "journal_digests": [journal.digest for journal in self._journals],
            "journal_count": len(self._journals),
            "synthetic_only": True,
            "money_movement_executed": False,
            "production_activation_allowed": False,
        }
        return {**value, "report_digest": canonical_digest(value)}


@dataclass(frozen=True)
class SettlementSimulation:
    settlement_id: str
    merchant_ref: str
    gross_minor: int
    fee_minor: int
    refund_minor: int
    currency: str
    policy_digest: str
    synthetic_only: bool = True
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if (
            not self.settlement_id.startswith("synthetic:")
            or not self.merchant_ref.startswith("synthetic:")
            or any(value < 0 for value in (self.gross_minor, self.fee_minor, self.refund_minor))
            or self.fee_minor + self.refund_minor > self.gross_minor
            or len(self.currency) != 3
            or not self.currency.isascii()
            or not self.currency.isalpha()
            or self.currency != self.currency.upper()
            or len(self.policy_digest) != 64
            or any(char not in "0123456789abcdef" for char in self.policy_digest)
            or not self.synthetic_only
            or self.execution_allowed
        ):
            raise GovernanceRejected("valid non-executable synthetic settlement required")

    @property
    def net_minor(self) -> int:
        return self.gross_minor - self.fee_minor - self.refund_minor
