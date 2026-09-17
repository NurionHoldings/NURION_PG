"""Generate evidence for metadata-only activation drafts."""

from __future__ import annotations

import json
from hashlib import sha256

from nurion_pg.synthetic_patch_draft_limited_promotion_activation_drafts import (
    ACTIVATION_DRAFT_SCOPE,
    ACTIVATION_DRAFT_STATE,
    SyntheticPatchDraftLimitedPromotionActivationDraftBook,
)
from nurion_pg.synthetic_patch_draft_limited_promotion_activation_receipt_ledger import (
    SyntheticPatchDraftLimitedPromotionActivationReceiptLedger,
)
from run_operator_decision_intake_evidence import NOW, ROOT, read_json
from run_synthetic_patch_draft_limited_promotion_activation_intake_evidence import (
    main as build_intake,
)
from run_synthetic_patch_draft_limited_promotion_activation_operator_packet_evidence import (
    main as build_packet_book,
)


def main():
    policy = read_json(
        "config/patch-draft-limited-promotion-activation-draft-policy.json"
    )
    forbidden = tuple(
        key for key, value in policy.items()
        if key.endswith("_allowed") and value is False
    )
    if (
        policy["mode"] != "UNREGISTERED_SYNTHETIC_ONLY"
        or policy["activation_scope"] != ACTIVATION_DRAFT_SCOPE
        or policy["maximum_state"] != ACTIVATION_DRAFT_STATE
        or policy["eternian_review_required"] is not True
        or len(forbidden) != 19
    ):
        raise SystemExit("activation draft policy drift detected")

    packet_book = build_packet_book()
    intake, envelope = build_intake()
    ledger = SyntheticPatchDraftLimitedPromotionActivationReceiptLedger(":memory:")
    receipt = ledger.record_from_intake(
        intake, envelope.envelope_id, recorded_at=NOW
    )
    before_ledger = ledger.evidence()["report_digest"]
    before_packet = packet_book.evidence()["report_digest"]
    book = SyntheticPatchDraftLimitedPromotionActivationDraftBook()
    draft = book.draft_from_receipt(
        ledger, receipt.receipt_id, packet_book, drafted_at=NOW
    )
    report = book.evidence()
    if (
        before_ledger != ledger.evidence()["report_digest"]
        or before_packet != packet_book.evidence()["report_digest"]
        or draft.source_receipt_digest != receipt.receipt_digest()
        or report["draft_chain_valid"] is not True
        or report["maximum_state"] != ACTIVATION_DRAFT_STATE
        or report["activation_scope"] != ACTIVATION_DRAFT_SCOPE
        or report["eternian_review_required"] is not True
        or any(
            report[key] is not False
            for key in report
            if key.endswith("_present") or key.endswith("_allowed")
        )
    ):
        raise SystemExit("activation draft boundary failed")
    ledger.close()

    output = ROOT / "build/synthetic-patch-draft-limited-promotion-activation-draft-evidence.json"
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode("utf-8")).hexdigest()
    output.with_suffix(".json.sha256").write_text(digest + "\n", encoding="ascii")
    print(f"synthetic activation draft: PASS {digest}")
    return book, draft


if __name__ == "__main__":
    main()
