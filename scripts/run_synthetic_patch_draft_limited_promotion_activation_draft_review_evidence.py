"""Generate evidence for independent review of metadata-only activation drafts."""

from __future__ import annotations

import json
from hashlib import sha256

from nurion_pg.synthetic_patch_draft_limited_promotion_activation_draft_review import (
    ACTIVATION_DRAFT_REVIEW_MAXIMUM_STATE,
    ActivationDraftReviewDecision,
    ActivationDraftReviewState,
    SyntheticActivationDraftReviewDocket,
)
from run_operator_decision_intake_evidence import NOW, ROOT, read_json
from run_synthetic_patch_draft_limited_promotion_activation_draft_evidence import main as build_draft


def main():
    policy = read_json("config/patch-draft-limited-promotion-activation-draft-review-policy.json")
    if (
        policy["mode"] != "UNREGISTERED_SYNTHETIC_ONLY"
        or policy["required_input_state"] != "SYNTHETIC_LIMITED_PROMOTION_ACTIVATION_DRAFTED"
        or tuple(policy["allowed_review_decisions"]) != ("PASS", "HOLD", "REJECT")
        or policy["maximum_state"] != ACTIVATION_DRAFT_REVIEW_MAXIMUM_STATE
        or policy["independent_eternian_review_required"] is not True
        or any(value is not False for key, value in policy.items() if key.endswith("_allowed"))
    ):
        raise SystemExit("activation draft review policy drift detected")
    book, draft = build_draft(); before = book.evidence()["report_digest"]
    docket = SyntheticActivationDraftReviewDocket()
    pending = docket.submit(book, draft.draft_id, submitted_at=NOW)
    reviewed = docket.record_eternian_review(
        draft.draft_id,
        review_id="synthetic:limited-promotion-activation-draft-review:evidence",
        reviewer_id="synthetic:eternian-reviewer:activation-draft:evidence",
        decision=ActivationDraftReviewDecision.PASS,
        findings_digest=sha256(b"activation draft review evidence").hexdigest(),
        reviewed_at=NOW,
    )
    report = docket.evidence()
    if (
        before != book.evidence()["report_digest"]
        or pending.state is not ActivationDraftReviewState.PENDING_ETERNIAN_REVIEW
        or reviewed.state is not ActivationDraftReviewState.READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_DESIGN
        or docket.ready_source(draft.draft_id) != reviewed
        or report["review_chain_valid"] is not True
        or report["maximum_state"] != ACTIVATION_DRAFT_REVIEW_MAXIMUM_STATE
        or any(report[key] is not False for key in report if key.endswith("_present") or key.endswith("_allowed") or key.endswith("_executed") or key.endswith("_recorded") or key.endswith("_used"))
    ):
        raise SystemExit("activation draft review boundary failed")
    output = ROOT / "build/synthetic-patch-draft-limited-promotion-activation-draft-review-evidence.json"
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode()).hexdigest()
    output.with_suffix(".json.sha256").write_text(digest + "\n", encoding="ascii")
    print(f"synthetic activation draft review: PASS {digest}")
    return docket, reviewed


if __name__ == "__main__":
    main()
