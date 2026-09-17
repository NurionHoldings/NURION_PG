from __future__ import annotations

import json
from hashlib import sha256

from nurion_pg.synthetic_fixture_materialization_dry_run_assertion_audit import audit_assertion
from nurion_pg.synthetic_fixture_materialization_dry_run_assertion_audit_ledger import (
    AUDIT_LEDGER_STATE,
    SyntheticFixtureMaterializationDryRunAssertionAuditLedger,
)
from run_operator_decision_intake_evidence import NOW, ROOT, read_json
from run_synthetic_fixture_materialization_dry_run_assertion_evidence import main as build_assertion


def main():
    policy = read_json("config/synthetic-fixture-materialization-dry-run-assertion-audit-ledger-policy.json")
    if policy["maximum_state"] != AUDIT_LEDGER_STATE or any(
        value is not False for key, value in policy.items() if key.endswith("_allowed")
    ):
        raise SystemExit("assertion audit ledger policy drift")
    book, item = build_assertion()
    audit = audit_assertion(book, item, audited_at=NOW)
    ledger = SyntheticFixtureMaterializationDryRunAssertionAuditLedger()
    record = ledger.record(book, item, audit, recorded_at=NOW)
    report = ledger.evidence()
    if (
        record.state != AUDIT_LEDGER_STATE
        or not report["audit_chain_valid"]
        or any(
            report[key] is not False
            for key in report
            if key.endswith("_present") or key.endswith("_allowed") or key.endswith("_executed") or key.endswith("_used")
        )
    ):
        raise SystemExit("assertion audit ledger boundary failed")
    output = ROOT / "build/synthetic-fixture-materialization-dry-run-assertion-audit-ledger-evidence.json"
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(report, sort_keys=True, indent=2) + "\n"
    output.write_text(payload)
    digest = sha256(payload.encode()).hexdigest()
    output.with_suffix(".json.sha256").write_text(digest + "\n")
    print(f"synthetic fixture materialization dry-run assertion audit ledger: PASS {digest}")
    return ledger, record


if __name__ == "__main__":
    main()
