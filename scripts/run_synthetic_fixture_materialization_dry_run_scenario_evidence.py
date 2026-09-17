from __future__ import annotations
import json
from hashlib import sha256
from nurion_pg.synthetic_fixture_materialization_dry_run_scenarios import SCENARIO_SCOPE,SCENARIO_STATE,SyntheticFixtureMaterializationDryRunScenarioBook
from run_operator_decision_intake_evidence import NOW,ROOT,read_json
from run_synthetic_activation_dry_run_fixture_materialization_dry_run_plan_review_evidence import main as build_review
def main():
    policy=read_json("config/synthetic-fixture-materialization-dry-run-scenario-policy.json")
    if policy["scope"]!=SCENARIO_SCOPE or policy["maximum_state"]!=SCENARIO_STATE or any(v is not False for k,v in policy.items() if k.endswith("_allowed")):raise SystemExit("scenario policy drift")
    docket,review=build_review();book=SyntheticFixtureMaterializationDryRunScenarioBook();item=book.draft_from_review(docket,review.plan.plan_id,drafted_at=NOW);report=book.evidence()
    if not report["scenario_chain_valid"] or any(report[k] is not False for k in report if k.endswith("_present") or k.endswith("_allowed") or k.endswith("_executed") or k.endswith("_used")):raise SystemExit("scenario boundary failed")
    output=ROOT/"build/synthetic-fixture-materialization-dry-run-scenario-evidence.json";output.parent.mkdir(exist_ok=True);payload=json.dumps(report,sort_keys=True,indent=2)+"\n";output.write_text(payload)
    digest=sha256(payload.encode()).hexdigest();output.with_suffix(".json.sha256").write_text(digest+"\n");print(f"synthetic fixture materialization dry-run scenario: PASS {digest}");return book,item
if __name__=="__main__":main()
