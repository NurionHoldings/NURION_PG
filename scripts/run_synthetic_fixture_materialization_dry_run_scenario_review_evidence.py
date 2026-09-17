from __future__ import annotations
import json
from hashlib import sha256
from nurion_pg.synthetic_fixture_materialization_dry_run_scenario_review import SCENARIO_REVIEW_MAXIMUM_STATE,ScenarioReviewDecision,SyntheticFixtureMaterializationDryRunScenarioReviewDocket
from run_operator_decision_intake_evidence import NOW,ROOT,read_json
from run_synthetic_fixture_materialization_dry_run_scenario_evidence import main as build_scenario
def main():
    policy=read_json("config/synthetic-fixture-materialization-dry-run-scenario-review-policy.json")
    if policy["maximum_state"]!=SCENARIO_REVIEW_MAXIMUM_STATE or any(v is not False for k,v in policy.items() if k.endswith("_allowed")):raise SystemExit("scenario review policy drift")
    book,scenario=build_scenario();docket=SyntheticFixtureMaterializationDryRunScenarioReviewDocket();docket.submit(book,scenario.scenario_id,submitted_at=NOW)
    item=docket.record_eternian_review(scenario.scenario_id,review_id="synthetic:fixture-materialization-dry-run-scenario-review:evidence",
        reviewer_id="synthetic:eternian-reviewer:fixture-materialization-dry-run-scenario:evidence",decision=ScenarioReviewDecision.PASS,
        findings_digest=sha256(b"scenario evidence review").hexdigest(),reviewed_at=NOW);report=docket.evidence()
    if docket.ready_source(scenario.scenario_id) is not item or not report["review_chain_valid"] or any(report[k] is not False for k in report if k.endswith("_present") or k.endswith("_allowed") or k.endswith("_executed") or k.endswith("_used")):raise SystemExit("scenario review boundary failed")
    output=ROOT/"build/synthetic-fixture-materialization-dry-run-scenario-review-evidence.json";output.parent.mkdir(exist_ok=True);payload=json.dumps(report,sort_keys=True,indent=2)+"\n";output.write_text(payload)
    digest=sha256(payload.encode()).hexdigest();output.with_suffix(".json.sha256").write_text(digest+"\n");print(f"synthetic fixture materialization dry-run scenario review: PASS {digest}");return docket,item
if __name__=="__main__":main()
