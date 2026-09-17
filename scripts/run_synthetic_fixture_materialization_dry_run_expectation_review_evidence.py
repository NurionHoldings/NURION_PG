from __future__ import annotations
import json
from hashlib import sha256
from nurion_pg.synthetic_fixture_materialization_dry_run_expectation_review import EXPECTATION_REVIEW_MAXIMUM_STATE,ExpectationReviewDecision,SyntheticFixtureMaterializationDryRunExpectationReviewDocket
from run_operator_decision_intake_evidence import NOW,ROOT,read_json
from run_synthetic_fixture_materialization_dry_run_expectation_evidence import main as build_expectation
def main():
    policy=read_json("config/synthetic-fixture-materialization-dry-run-expectation-review-policy.json")
    if policy["maximum_state"]!=EXPECTATION_REVIEW_MAXIMUM_STATE or any(v is not False for k,v in policy.items() if k.endswith("_allowed")):raise SystemExit("expectation review policy drift")
    book,item=build_expectation();docket=SyntheticFixtureMaterializationDryRunExpectationReviewDocket();docket.submit(book,item.expectation_id,submitted_at=NOW)
    final=docket.record_eternian_review(item.expectation_id,review_id="synthetic:fixture-materialization-dry-run-expectation-review:evidence",
        reviewer_id="synthetic:eternian-reviewer:fixture-materialization-dry-run-expectation:evidence",decision=ExpectationReviewDecision.PASS,
        findings_digest=sha256(b"expectation evidence review").hexdigest(),reviewed_at=NOW);report=docket.evidence()
    if docket.ready_source(item.expectation_id) is not final or not report["review_chain_valid"] or any(report[k] is not False for k in report if k.endswith("_present") or k.endswith("_allowed") or k.endswith("_executed") or k.endswith("_used")):raise SystemExit("expectation review boundary failed")
    output=ROOT/"build/synthetic-fixture-materialization-dry-run-expectation-review-evidence.json";output.parent.mkdir(exist_ok=True);payload=json.dumps(report,sort_keys=True,indent=2)+"\n";output.write_text(payload)
    digest=sha256(payload.encode()).hexdigest();output.with_suffix(".json.sha256").write_text(digest+"\n");print(f"synthetic fixture materialization dry-run expectation review: PASS {digest}");return docket,final
if __name__=="__main__":main()
