"""Generate deterministic evidence for non-executing activation dry-run designs."""

from __future__ import annotations

import json
from hashlib import sha256

from nurion_pg.synthetic_activation_dry_run_designs import (
    DRY_RUN_DESIGN_SCOPE, DRY_RUN_DESIGN_STATE, SyntheticActivationDryRunDesignBook,
)
from run_operator_decision_intake_evidence import NOW, ROOT, read_json
from run_synthetic_patch_draft_limited_promotion_activation_draft_review_evidence import main as build_review


def main():
    policy = read_json("config/synthetic-activation-dry-run-design-policy.json")
    if (
        policy["mode"] != "UNREGISTERED_SYNTHETIC_ONLY"
        or policy["required_input_state"] != "READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_DESIGN"
        or policy["scope"] != DRY_RUN_DESIGN_SCOPE or policy["maximum_state"] != DRY_RUN_DESIGN_STATE
        or policy["separate_review_required"] is not True
        or any(value is not False for key, value in policy.items() if key.endswith("_allowed"))
    ): raise SystemExit("activation dry-run design policy drift detected")
    docket, review = build_review(); before = docket.evidence()["report_digest"]
    book = SyntheticActivationDryRunDesignBook()
    design = book.design_from_review(docket, review.draft.draft_id, designed_at=NOW)
    report = book.evidence()
    if (
        before != docket.evidence()["report_digest"] or design.source_review_digest != review.review_digest
        or report["design_chain_valid"] is not True or report["maximum_state"] != DRY_RUN_DESIGN_STATE
        or report["scope"] != DRY_RUN_DESIGN_SCOPE
        or any(report[key] is not False for key in report if key.endswith("_present") or key.endswith("_allowed") or key.endswith("_executed") or key.endswith("_used"))
    ): raise SystemExit("activation dry-run design boundary failed")
    output = ROOT / "build/synthetic-activation-dry-run-design-evidence.json"; output.parent.mkdir(exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"; output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode()).hexdigest(); output.with_suffix(".json.sha256").write_text(digest + "\n", encoding="ascii")
    print(f"synthetic activation dry-run design: PASS {digest}"); return book, design


if __name__ == "__main__": main()
