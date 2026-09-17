"""Generate evidence for independent review of activation dry-run designs."""
from __future__ import annotations
import json
from hashlib import sha256
from nurion_pg.synthetic_activation_dry_run_design_review import (
    DESIGN_REVIEW_MAXIMUM_STATE,DryRunDesignReviewDecision,DryRunDesignReviewState,SyntheticActivationDryRunDesignReviewDocket,
)
from run_operator_decision_intake_evidence import NOW,ROOT,read_json
from run_synthetic_activation_dry_run_design_evidence import main as build_design

def main():
    policy=read_json("config/synthetic-activation-dry-run-design-review-policy.json")
    if (policy["mode"]!="UNREGISTERED_SYNTHETIC_ONLY" or policy["required_input_state"]!="SYNTHETIC_ACTIVATION_DRY_RUN_DESIGNED"
        or tuple(policy["allowed_review_decisions"])!=("PASS","HOLD","REJECT") or policy["maximum_state"]!=DESIGN_REVIEW_MAXIMUM_STATE
        or policy["independent_eternian_review_required"] is not True
        or any(value is not False for key,value in policy.items() if key.endswith("_allowed"))): raise SystemExit("activation dry-run design review policy drift detected")
    book,design=build_design(); before=book.evidence()["report_digest"]; docket=SyntheticActivationDryRunDesignReviewDocket()
    pending=docket.submit(book,design.design_id,submitted_at=NOW)
    reviewed=docket.record_eternian_review(design.design_id,review_id="synthetic:activation-dry-run-design-review:evidence",
        reviewer_id="synthetic:eternian-reviewer:activation-dry-run-design:evidence",decision=DryRunDesignReviewDecision.PASS,
        findings_digest=sha256(b"activation dry-run design review evidence").hexdigest(),reviewed_at=NOW)
    report=docket.evidence()
    if (before!=book.evidence()["report_digest"] or pending.state is not DryRunDesignReviewState.PENDING_ETERNIAN_REVIEW
        or reviewed.state is not DryRunDesignReviewState.READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_PROPOSAL
        or docket.ready_source(design.design_id)!=reviewed or report["review_chain_valid"] is not True
        or report["maximum_state"]!=DESIGN_REVIEW_MAXIMUM_STATE
        or any(report[key] is not False for key in report if key.endswith("_present") or key.endswith("_allowed") or key.endswith("_executed") or key.endswith("_used"))):
        raise SystemExit("activation dry-run design review boundary failed")
    output=ROOT/"build/synthetic-activation-dry-run-design-review-evidence.json"; output.parent.mkdir(exist_ok=True)
    payload=json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n"; output.write_text(payload,encoding="utf-8")
    digest=sha256(payload.encode()).hexdigest(); output.with_suffix(".json.sha256").write_text(digest+"\n",encoding="ascii")
    print(f"synthetic activation dry-run design review: PASS {digest}"); return docket,reviewed

if __name__=="__main__": main()
