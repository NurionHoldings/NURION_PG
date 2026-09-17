"""Generate deterministic evidence for synthetic ledger invariants."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from nurion_pg.arkaon.governance import canonical_digest
from nurion_pg.synthetic_finance import EntrySide, Journal, LedgerEntry, SyntheticLedger


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ledger = SyntheticLedger()
    journal = Journal(
        journal_id="synthetic:journal:001",
        idempotency_key="synthetic:idempotency:001",
        created_at=datetime(2026, 9, 17, tzinfo=UTC),
        entries=(
            LedgerEntry("synthetic:receivable", EntrySide.DEBIT, 10000, "KRW"),
            LedgerEntry("synthetic:merchant-payable", EntrySide.CREDIT, 10000, "KRW"),
        ),
        evidence_digest=canonical_digest({"fixture": "balanced-journal-v1"}),
    )
    ledger.post(journal)
    ledger.post(journal)
    report = ledger.evidence()
    output = ROOT / "build/synthetic-ledger-evidence.json"
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode("utf-8")).hexdigest()
    output.with_suffix(".json.sha256").write_text(digest + "\n", encoding="ascii")
    if report["journal_count"] != 1 or report["money_movement_executed"] is not False:
        raise SystemExit("synthetic ledger invariant failed")
    print(f"synthetic ledger evidence: PASS {digest}")


if __name__ == "__main__":
    main()

