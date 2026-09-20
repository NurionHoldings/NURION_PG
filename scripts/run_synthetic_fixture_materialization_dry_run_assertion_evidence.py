from __future__ import annotations
import json
from hashlib import sha256
from nurion_pg.synthetic_fixture_materialization_dry_run_assertions import ASSERTION_SCOPE,ASSERTION_STATE,SyntheticFixtureMaterializationDryRunAssertionBook
from run_operator_decision_intake_evidence import NOW,ROOT,read_json
from run_synthetic_fixture_materialization_dry_run_expectation_review_evidence import main as build_review
def main():
    policy=read_json("config/synthetic-fixture-materialization-dry-run-assertion-policy.json")
    if policy["scope"]!=ASSERTION_SCOPE or policy["maximum_state"]!=ASSERTION_STATE or any(v is not False for k,v in policy.items() if k.endswith("_allowed")):raise SystemExit("assertion policy drift")
    docket,review=build_review();book=SyntheticFixtureMaterializationDryRunAssertionBook()
    item=book.draft_from_review(docket,review.expectation.expectation_id,drafted_at=NOW);report=book.evidence()
    if not report["assertion_chain_valid"] or any(report[k] is not False for k in report if k.endswith("_present") or k.endswith("_allowed") or k.endswith("_executed") or k.endswith("_used")):raise SystemExit("assertion boundary failed")
    output=ROOT/"build/synthetic-fixture-materialization-dry-run-assertion-evidence.json";output.parent.mkdir(exist_ok=True);payload=json.dumps(report,sort_keys=True,indent=2)+"\n";output.write_text(payload)
    digest=sha256(payload.encode()).hexdigest();output.with_suffix(".json.sha256").write_text(digest+"\n");print(f"synthetic fixture materialization dry-run assertion: PASS {digest}");return book,item
if __name__=="__main__":main()
