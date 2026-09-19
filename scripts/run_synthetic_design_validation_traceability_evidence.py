from hashlib import sha256
import json
from pathlib import Path

from nurion_pg.synthetic_design_validation_traceability import (
    CONTROL_ASPECTS, WORKSTREAMS, SyntheticDesignValidationTraceability,
)

ROOT = Path(__file__).resolve().parents[1]
def d(value): return sha256(value.encode()).hexdigest()


def main():
    service = SyntheticDesignValidationTraceability()
    service.add_anchor("synthetic:p0-anchor:evidence", d("baseline-commit"), d("baseline-evidence"))
    negative = {"negative_path", "missing_input", "duplicate_input", "conflict", "stale_version", "partial_batch"}
    for start, end, workstream in WORKSTREAMS:
        for control_id in range(start, end + 1):
            aspect = CONTROL_ASPECTS[(control_id - 3501) % 25]
            service.add_claim(
                f"synthetic:validation-claim:{control_id}", control_id, workstream, aspect,
                "synthetic:p0-anchor:evidence", f"synthetic:p0-requirement:{(control_id - 3501) // 25:02}",
                f"synthetic threat {control_id}", d(f"fixture:{control_id}"),
                "EXPECTED_REJECTION" if aspect in negative else "PASS", d(f"evidence:{control_id}"),
                1, "SECURITY", True,
            )
    row = service.author("synthetic:validation-dossier:evidence", "synthetic:validation-author:author",
                         "synthetic:p0-anchor:evidence", tuple(service._claims))
    row = service.review("synthetic:validation-review:evidence", row.dossier_id, row.version,
                         "synthetic:validation-reviewer:reviewer", True, d("review-finding"))
    review = service.artifact("synthetic:validation-review:evidence")
    row = service.record("synthetic:validation-receipt:evidence", row.dossier_id, row.version,
                         "synthetic:validation-verifier:verifier", review.digest)
    service.generate_integration_drafts(
        row.dossier_id, "synthetic:tenant:agency-evidence", "synthetic:upstream-pg:evidence", 1,
        "synthetic:correlation:evidence", "synthetic:idempotency:evidence",
        (("tenant_order_id", "merchant_reference"), ("amount_token", "amount_token"),
         ("status_code", "status_code")),
    )
    evidence = service.evidence()
    assert (evidence["control_count"] == 400 and evidence["claim_count"] == 400
            and evidence["integrity_valid"] and evidence["capability_ready"]
            and evidence["electronic_document_draft_count"] == 4
            and evidence["adapter_draft_count"] == 3
            and evidence["integration_event_count"] == 7)
    output = ROOT / "build/synthetic-design-validation-traceability-evidence.json"
    output.parent.mkdir(exist_ok=True)
    content = json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    output.write_text(content, encoding="utf-8")
    checksum = sha256(content.encode()).hexdigest()
    output.with_suffix(".json.sha256").write_text(checksum + "\n", encoding="utf-8")
    print("synthetic design validation traceability #3501-#3900: PASS", checksum)


if __name__ == "__main__": main()
