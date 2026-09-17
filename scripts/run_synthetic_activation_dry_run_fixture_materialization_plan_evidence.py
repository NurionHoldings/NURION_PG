"""Generate evidence for metadata-only fixture materialization plans."""
from __future__ import annotations
import json
from hashlib import sha256
from nurion_pg.synthetic_activation_dry_run_fixture_materialization_plans import FIXTURE_MATERIALIZATION_PLAN_SCOPE,FIXTURE_MATERIALIZATION_PLAN_STATE,SyntheticActivationDryRunFixtureMaterializationPlanBook
from run_operator_decision_intake_evidence import NOW,ROOT,read_json
from run_synthetic_activation_dry_run_fixture_draft_review_evidence import main as build_review

def main():
    policy=read_json("config/synthetic-activation-dry-run-fixture-materialization-plan-policy.json")
    if (policy["mode"]!="UNREGISTERED_SYNTHETIC_ONLY" or policy["required_input_state"]!="READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_MATERIALIZATION_PLAN"
        or policy["scope"]!=FIXTURE_MATERIALIZATION_PLAN_SCOPE or policy["maximum_state"]!=FIXTURE_MATERIALIZATION_PLAN_STATE
        or policy["separate_review_required"] is not True or any(v is not False for k,v in policy.items() if k.endswith("_allowed"))):raise SystemExit("fixture materialization plan policy drift detected")
    docket,review=build_review();before=docket.evidence()["report_digest"];book=SyntheticActivationDryRunFixtureMaterializationPlanBook()
    item=book.plan_from_review(docket,review.draft.draft_id,planned_at=NOW);report=book.evidence()
    if (before!=docket.evidence()["report_digest"] or item.source_review_digest!=review.review_digest or report["plan_chain_valid"] is not True
        or report["maximum_state"]!=FIXTURE_MATERIALIZATION_PLAN_STATE or report["scope"]!=FIXTURE_MATERIALIZATION_PLAN_SCOPE
        or any(report[k] is not False for k in report if k.endswith("_present") or k.endswith("_allowed") or k.endswith("_executed") or k.endswith("_used"))):raise SystemExit("fixture materialization plan boundary failed")
    output=ROOT/"build/synthetic-activation-dry-run-fixture-materialization-plan-evidence.json";output.parent.mkdir(exist_ok=True)
    payload=json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n";output.write_text(payload,encoding="utf-8")
    digest=sha256(payload.encode()).hexdigest();output.with_suffix(".json.sha256").write_text(digest+"\n",encoding="ascii")
    print(f"synthetic activation dry-run fixture materialization plan: PASS {digest}");return book,item

if __name__=="__main__":main()
