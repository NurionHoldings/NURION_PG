from __future__ import annotations
import json
from hashlib import sha256
from nurion_pg.synthetic_fixture_materialization_dry_run_assertion_audit import AUDIT_STATE,audit_assertion,evidence
from run_operator_decision_intake_evidence import NOW,ROOT,read_json
from run_synthetic_fixture_materialization_dry_run_assertion_evidence import main as build_assertion
def main():
    policy=read_json("config/synthetic-fixture-materialization-dry-run-assertion-audit-policy.json");book,item=build_assertion()
    report=evidence(audit_assertion(book,item,audited_at=NOW))
    if policy["maximum_state"]!=AUDIT_STATE or any(report[k] is not False for k in report if k.endswith("_present") or k.endswith("_allowed") or k.endswith("_executed") or k.endswith("_used")):raise SystemExit("assertion audit boundary failed")
    output=ROOT/"build/synthetic-fixture-materialization-dry-run-assertion-audit-evidence.json";output.parent.mkdir(exist_ok=True);payload=json.dumps(report,sort_keys=True,indent=2)+"\n";output.write_text(payload)
    digest=sha256(payload.encode()).hexdigest();output.with_suffix(".json.sha256").write_text(digest+"\n");print(f"synthetic fixture materialization dry-run assertion audit: PASS {digest}");return report
if __name__=="__main__":main()
