from hashlib import sha256
import json
from pathlib import Path
from dataclasses import replace

from nurion_pg.arkaon.governance import canonical_digest
from nurion_pg.synthetic_rebuttal_correction_submission_validation import *
from validate_arkaon_lesson_registry import MANIFEST, declared_remediations, discovered_negative_tests, validate, validated_stage_snapshot

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config/arkaon-lesson-registry-v1.json"
GUIDANCE = ROOT / "config/arkaon-audit-recurrence-prevention.json"

def d(value): return sha256(value.encode()).hexdigest()

def main():
    registry_bytes = REGISTRY.read_bytes(); manifest_bytes = MANIFEST.read_bytes(); guidance_bytes = GUIDANCE.read_bytes()
    live = validate(json.loads(registry_bytes), declared_remediations(json.loads(manifest_bytes)), discovered_negative_tests()); lessons, stage_digest = validated_stage_snapshot(live, APPLIED_LESSONS, "ARKAON-LESSONS-12301", (9901,12700))
    rules = tuple(x["id"] for x in json.loads(guidance_bytes)["rules"])
    if lessons != APPLIED_LESSONS or rules != APPLIED_RULES: raise ValueError("exact lessons and rules required")
    service = SyntheticRebuttalCorrectionSubmissionValidation()
    for start, end, workstream in WORKSTREAMS:
        for control_id in range(start, end+1):
            aspect = CONTROL_ASPECTS[(control_id-10301) % 25]
            service.add_control(control_id, workstream, aspect, f"synthetic:submission-validation-requirement:{(control_id-10301)//25:02}", d(f"fixture:{control_id}"), "EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS")
    reviews = []
    for pos, (flow, kind) in enumerate(CASE_KEYS):
        route = ROUTES[pos % 5]; previous = None if not reviews else reviews[-1].digest
        reviewer = None if route == "NOT_APPLICABLE_PRESERVED" else f"synthetic:response-independent-reviewer:r-{flow}-{kind}"
        custodian = None if route == "NOT_APPLICABLE_PRESERVED" else f"synthetic:{'rebuttal-custodian' if route == 'REBUTTAL_OPPORTUNITY_REQUIRED' else 'correction-request-compiler'}:c-{flow}-{kind}"
        row = SourceReview(f"synthetic:response-review:{flow}:{kind}", flow, kind, d(f"intake:{flow}:{kind}"), route, reviewer, custodian, previous, pos+1, True, False, False, False, "")
        reviews.append(replace(row, digest=review_digest(row)))
    reviews = tuple(reviews); review_set = canonical_digest(tuple(x.digest for x in reviews))
    source_compiler = "synthetic:review-docket-compiler:source-compiler"; source_validator = "synthetic:review-docket-validator:source-validator"
    source_docket = canonical_digest(("RESPONSE_REVIEW_REBUTTAL_CORRECTION_DOCKET_SOURCE", review_set, source_compiler, source_validator))
    anchor = service.anchor("synthetic:submission-validation-anchor:evidence", source_docket, review_set, stage_digest, sha256(manifest_bytes).hexdigest(), lessons, rules, reviews, source_compiler, source_validator, 22, True)
    for pos, (flow, kind) in enumerate(CASE_KEYS):
        submission_id = f"synthetic:rebuttal-correction-submission:{flow}:{kind}"
        if ROUTES[pos % 5] == "NOT_APPLICABLE_PRESERVED": service.add_submission(submission_id, flow, kind)
        else:
            document = d(f"document:{flow}:{kind}")
            receipt = derived_receipt_digest(flow, kind, anchor.source_reviews[pos].digest, ROUTES[pos % 5], RESPONDER[flow], document)
            service.add_submission(submission_id, flow, kind, document, receipt)
    service.finalize("synthetic:submission-validation-docket:evidence", "synthetic:submission-docket-compiler:compiler", "synthetic:submission-docket-validator:validator")
    evidence = service.evidence()
    if not evidence["complete_submission_docket_evidence"] or evidence["registered_control_count"] != 400: raise ValueError("incomplete evidence")
    evidence.update({"lesson_registry_digest": stage_digest, "remediation_manifest_digest": sha256(manifest_bytes).hexdigest(), "remediation_guidance_digest": sha256(guidance_bytes).hexdigest(), "applied_lesson_ids": lessons})
    output = ROOT / "build/synthetic-rebuttal-correction-submission-validation-evidence.json"; output.parent.mkdir(exist_ok=True)
    content = json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n"; output.write_text(content, encoding="utf-8")
    checksum = sha256(content.encode()).hexdigest(); output.with_suffix(".json.sha256").write_text(checksum + "\n", encoding="utf-8")
    print("synthetic submission validation #10301-#10700: PASS", checksum)

if __name__ == "__main__": main()
