"""Generate evidence for non-materialized activation dry-run fixture drafts."""
from __future__ import annotations
import json
from hashlib import sha256
from nurion_pg.synthetic_activation_dry_run_fixture_drafts import FIXTURE_DRAFT_SCOPE,FIXTURE_DRAFT_STATE,SyntheticActivationDryRunFixtureDraftBook
from run_operator_decision_intake_evidence import NOW,ROOT,read_json
from run_synthetic_activation_dry_run_fixture_proposal_review_evidence import main as build_review
def main():
    policy=read_json("config/synthetic-activation-dry-run-fixture-draft-policy.json")
    if (policy["mode"]!="UNREGISTERED_SYNTHETIC_ONLY" or policy["required_input_state"]!="READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_DRAFT"
        or policy["scope"]!=FIXTURE_DRAFT_SCOPE or policy["maximum_state"]!=FIXTURE_DRAFT_STATE or policy["separate_review_required"] is not True
        or any(v is not False for k,v in policy.items() if k.endswith("_allowed"))):raise SystemExit("fixture draft policy drift detected")
    docket,review=build_review();before=docket.evidence()["report_digest"];book=SyntheticActivationDryRunFixtureDraftBook();item=book.draft_from_review(docket,review.proposal.proposal_id,drafted_at=NOW);report=book.evidence()
    if (before!=docket.evidence()["report_digest"] or item.source_review_digest!=review.review_digest or report["draft_chain_valid"] is not True
        or report["maximum_state"]!=FIXTURE_DRAFT_STATE or report["scope"]!=FIXTURE_DRAFT_SCOPE
        or any(report[k] is not False for k in report if k.endswith("_present") or k.endswith("_allowed") or k.endswith("_executed") or k.endswith("_used"))):raise SystemExit("fixture draft boundary failed")
    output=ROOT/"build/synthetic-activation-dry-run-fixture-draft-evidence.json";output.parent.mkdir(exist_ok=True);payload=json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n";output.write_text(payload,encoding="utf-8")
    digest=sha256(payload.encode()).hexdigest();output.with_suffix(".json.sha256").write_text(digest+"\n",encoding="ascii");print(f"synthetic activation dry-run fixture draft: PASS {digest}");return book,item
if __name__=="__main__":main()
