"""Generate evidence for independent review of dry-run fixture proposals."""
from __future__ import annotations
import json
from hashlib import sha256
from nurion_pg.synthetic_activation_dry_run_fixture_proposal_review import FIXTURE_REVIEW_MAXIMUM_STATE,FixtureProposalReviewDecision,FixtureProposalReviewState,SyntheticActivationDryRunFixtureProposalReviewDocket
from run_operator_decision_intake_evidence import NOW,ROOT,read_json
from run_synthetic_activation_dry_run_fixture_proposal_evidence import main as build_proposal
def main():
    policy=read_json("config/synthetic-activation-dry-run-fixture-proposal-review-policy.json")
    if (policy["mode"]!="UNREGISTERED_SYNTHETIC_ONLY" or policy["required_input_state"]!="SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_PROPOSED"
        or tuple(policy["allowed_review_decisions"])!=("PASS","HOLD","REJECT") or policy["maximum_state"]!=FIXTURE_REVIEW_MAXIMUM_STATE
        or policy["independent_eternian_review_required"] is not True or any(v is not False for k,v in policy.items() if k.endswith("_allowed"))):raise SystemExit("fixture proposal review policy drift detected")
    book,p=build_proposal();before=book.evidence()["report_digest"];d=SyntheticActivationDryRunFixtureProposalReviewDocket();pending=d.submit(book,p.proposal_id,submitted_at=NOW)
    reviewed=d.record_eternian_review(p.proposal_id,review_id="synthetic:activation-dry-run-fixture-proposal-review:evidence",reviewer_id="synthetic:eternian-reviewer:activation-dry-run-fixture-proposal:evidence",
        decision=FixtureProposalReviewDecision.PASS,findings_digest=sha256(b"fixture proposal review evidence").hexdigest(),reviewed_at=NOW);report=d.evidence()
    if (before!=book.evidence()["report_digest"] or pending.state is not FixtureProposalReviewState.PENDING_ETERNIAN_REVIEW
        or reviewed.state is not FixtureProposalReviewState.READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_DRAFT or d.ready_source(p.proposal_id)!=reviewed
        or report["review_chain_valid"] is not True or report["maximum_state"]!=FIXTURE_REVIEW_MAXIMUM_STATE
        or any(report[k] is not False for k in report if k.endswith("_present") or k.endswith("_allowed") or k.endswith("_executed") or k.endswith("_used"))):raise SystemExit("fixture proposal review boundary failed")
    output=ROOT/"build/synthetic-activation-dry-run-fixture-proposal-review-evidence.json";output.parent.mkdir(exist_ok=True)
    payload=json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n";output.write_text(payload,encoding="utf-8");digest=sha256(payload.encode()).hexdigest();output.with_suffix(".json.sha256").write_text(digest+"\n",encoding="ascii")
    print(f"synthetic activation dry-run fixture proposal review: PASS {digest}");return d,reviewed
if __name__=="__main__":main()
