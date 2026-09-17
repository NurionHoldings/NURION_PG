from __future__ import annotations
import json
from hashlib import sha256
from nurion_pg.synthetic_fixture_materialization_dry_run_expectations import EXPECTATION_SCOPE,EXPECTATION_STATE,SyntheticFixtureMaterializationDryRunExpectationBook
from run_operator_decision_intake_evidence import NOW,ROOT,read_json
from run_synthetic_fixture_materialization_dry_run_scenario_review_evidence import main as build_review
def main():
    policy=read_json("config/synthetic-fixture-materialization-dry-run-expectation-policy.json")
    if policy["scope"]!=EXPECTATION_SCOPE or policy["maximum_state"]!=EXPECTATION_STATE or any(v is not False for k,v in policy.items() if k.endswith("_allowed")):raise SystemExit("expectation policy drift")
    docket,review=build_review();book=SyntheticFixtureMaterializationDryRunExpectationBook()
    item=book.draft_from_review(docket,review.scenario.scenario_id,drafted_at=NOW);report=book.evidence()
    if not report["expectation_chain_valid"] or any(report[k] is not False for k in report if k.endswith("_present") or k.endswith("_allowed") or k.endswith("_executed") or k.endswith("_used")):raise SystemExit("expectation boundary failed")
    output=ROOT/"build/synthetic-fixture-materialization-dry-run-expectation-evidence.json";output.parent.mkdir(exist_ok=True);payload=json.dumps(report,sort_keys=True,indent=2)+"\n";output.write_text(payload)
    digest=sha256(payload.encode()).hexdigest();output.with_suffix(".json.sha256").write_text(digest+"\n");print(f"synthetic fixture materialization dry-run expectation: PASS {digest}");return book,item
if __name__=="__main__":main()
