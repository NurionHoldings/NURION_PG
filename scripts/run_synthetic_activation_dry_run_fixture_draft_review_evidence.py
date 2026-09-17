"""Generate evidence for independent review of non-materialized fixture drafts."""
from __future__ import annotations
import json
from hashlib import sha256
from nurion_pg.synthetic_activation_dry_run_fixture_draft_review import FIXTURE_DRAFT_REVIEW_MAXIMUM_STATE,FixtureDraftReviewDecision,SyntheticActivationDryRunFixtureDraftReviewDocket
from run_operator_decision_intake_evidence import NOW,ROOT,read_json
from run_synthetic_activation_dry_run_fixture_draft_evidence import main as build_draft

def main():
    policy=read_json("config/synthetic-activation-dry-run-fixture-draft-review-policy.json")
    if (policy["mode"]!="UNREGISTERED_SYNTHETIC_ONLY" or policy["maximum_state"]!=FIXTURE_DRAFT_REVIEW_MAXIMUM_STATE
        or policy["required_input_state"]!="SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_DRAFTED" or policy["independent_eternian_review_required"] is not True
        or any(v is not False for k,v in policy.items() if k.endswith("_allowed"))):raise SystemExit("fixture draft review policy drift detected")
    book,draft=build_draft();before=book.evidence()["report_digest"];docket=SyntheticActivationDryRunFixtureDraftReviewDocket();docket.submit(book,draft.draft_id,submitted_at=NOW)
    item=docket.record_eternian_review(draft.draft_id,review_id="synthetic:activation-dry-run-fixture-draft-review:evidence",reviewer_id="synthetic:eternian-reviewer:activation-dry-run-fixture-draft:evidence",
        decision=FixtureDraftReviewDecision.PASS,findings_digest=sha256(b"independent fixture draft evidence review").hexdigest(),reviewed_at=NOW);report=docket.evidence()
    if (before!=book.evidence()["report_digest"] or docket.ready_source(draft.draft_id) is not item or report["review_chain_valid"] is not True
        or report["maximum_state"]!=FIXTURE_DRAFT_REVIEW_MAXIMUM_STATE
        or any(report[k] is not False for k in report if k.endswith("_present") or k.endswith("_allowed") or k.endswith("_executed") or k.endswith("_used"))):raise SystemExit("fixture draft review boundary failed")
    output=ROOT/"build/synthetic-activation-dry-run-fixture-draft-review-evidence.json";output.parent.mkdir(exist_ok=True);payload=json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n";output.write_text(payload,encoding="utf-8")
    digest=sha256(payload.encode()).hexdigest();output.with_suffix(".json.sha256").write_text(digest+"\n",encoding="ascii");print(f"synthetic activation dry-run fixture draft review: PASS {digest}");return docket,item

if __name__=="__main__":main()
