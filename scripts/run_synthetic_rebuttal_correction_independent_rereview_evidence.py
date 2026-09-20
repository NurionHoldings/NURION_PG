from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path

from nurion_pg.arkaon.governance import canonical_digest
from nurion_pg.synthetic_rebuttal_correction_independent_rereview import *
from validate_arkaon_lesson_registry import MANIFEST, declared_remediations, discovered_negative_tests, validate

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config/arkaon-lesson-registry-v1.json"
GUIDANCE = ROOT / "config/arkaon-audit-recurrence-prevention.json"

def d(value): return sha256(value.encode()).hexdigest()

def main():
    registry_bytes = REGISTRY.read_bytes(); manifest_bytes = MANIFEST.read_bytes(); guidance_bytes = GUIDANCE.read_bytes()
    lessons = validate(json.loads(registry_bytes), declared_remediations(json.loads(manifest_bytes)), discovered_negative_tests())
    rules = tuple(x["id"] for x in json.loads(guidance_bytes)["rules"])
    if lessons != APPLIED_LESSONS or rules != APPLIED_RULES: raise ValueError("exact lessons and rules required")
    service = SyntheticRebuttalCorrectionIndependentReReview()
    for start, end, workstream in WORKSTREAMS:
        for control_id in range(start, end + 1):
            aspect = CONTROL_ASPECTS[(control_id - 10701) % 25]
            service.add_control(control_id, workstream, aspect, f"synthetic:independent-rereview-requirement:{(control_id-10701)//25:02}", d(f"fixture:{control_id}"), "EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS")
    submissions = []
    for position, (flow, kind) in enumerate(CASE_KEYS):
        route = ROUTES[position % 5]; parent = None if not submissions else submissions[-1].digest
        source_review = d(f"source-review:{flow}:{kind}")
        if route == "NOT_APPLICABLE_PRESERVED":
            submitter = document = receipt = None; marker = "NO_SUBMISSION_REQUIRED"
        else:
            submitter = RESPONDER[flow]; document = d(f"document:{flow}:{kind}")
            receipt = derived_receipt_digest(flow, kind, source_review, route, submitter, document)
            marker = "SUBMISSION_RECEIVED_FOR_HUMAN_REVIEW"
        digest = submission_digest(flow, kind, source_review, route, submitter, document, receipt, marker, parent, position + 1)
        submissions.append(SourceSubmission(f"synthetic:rebuttal-correction-submission:{flow}:{kind}", flow, kind, source_review, route, submitter, document, receipt, marker, parent, position + 1, True, True, False, False, digest))
    submissions = tuple(submissions); submission_set = canonical_digest(tuple(x.digest for x in submissions))
    source_compiler = "synthetic:submission-docket-compiler:source-compiler"; source_validator = "synthetic:submission-docket-validator:source-validator"
    source_actor_roles = tuple(f"synthetic:{kind}:source-actor-{position}" for position, kind in enumerate(SOURCE_ACTOR_KINDS))
    source_docket = canonical_digest(("REBUTTAL_CORRECTION_SUBMISSION_DOCKET_SOURCE", submission_set, source_compiler, source_validator))
    service.anchor("synthetic:independent-rereview-anchor:evidence", source_docket, submission_set,
                   sha256(registry_bytes).hexdigest(), sha256(manifest_bytes).hexdigest(), lessons, rules,
                   submissions, source_actor_roles, source_compiler, source_validator, 23, True)
    for position, (flow, kind) in enumerate(CASE_KEYS):
        args = (f"synthetic:independent-rereview:{flow}:{kind}", flow, kind)
        if ROUTES[position % 5] == "NOT_APPLICABLE_PRESERVED": service.add_rereview(*args)
        else: service.add_rereview(*args, f"synthetic:independent-human-rereviewer:reviewer-{position}")
    service.finalize("synthetic:independent-rereview-docket:evidence", "synthetic:rereview-docket-compiler:compiler", "synthetic:rereview-docket-validator:validator")
    evidence = service.evidence()
    if not evidence["complete_pending_rereview_docket_evidence"] or evidence["registered_control_count"] != 400: raise ValueError("incomplete evidence")
    evidence.update({"lesson_registry_digest": sha256(registry_bytes).hexdigest(), "remediation_manifest_digest": sha256(manifest_bytes).hexdigest(), "remediation_guidance_digest": sha256(guidance_bytes).hexdigest(), "applied_lesson_ids": lessons})
    output = ROOT / "build/synthetic-rebuttal-correction-independent-rereview-evidence.json"; output.parent.mkdir(exist_ok=True)
    content = json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n"; output.write_text(content, encoding="utf-8")
    checksum = sha256(content.encode()).hexdigest(); output.with_suffix(".json.sha256").write_text(checksum + "\n", encoding="utf-8")
    print("synthetic independent rereview #10701-#11100: PASS", checksum)

if __name__ == "__main__": main()
