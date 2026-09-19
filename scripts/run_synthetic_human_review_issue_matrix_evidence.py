from hashlib import sha256
import json
from pathlib import Path

from nurion_pg.arkaon.governance import canonical_digest
from nurion_pg.synthetic_human_review_issue_matrix import *
from validate_arkaon_lesson_registry import MANIFEST, declared_remediations, discovered_negative_tests, validate

ROOT=Path(__file__).resolve().parents[1]; REGISTRY=ROOT/"config/arkaon-lesson-registry-v1.json"; GUIDANCE=ROOT/"config/arkaon-audit-recurrence-prevention.json"
def d(v):return sha256(v.encode()).hexdigest()
def main():
    rb=REGISTRY.read_bytes(); mb=MANIFEST.read_bytes(); gb=GUIDANCE.read_bytes(); registry=json.loads(rb); manifest=json.loads(mb); guidance=json.loads(gb)
    lessons=validate(registry,declared_remediations(manifest),discovered_negative_tests()); rules=tuple(x["id"] for x in guidance["rules"])
    if lessons!=APPLIED_LESSONS or rules!=APPLIED_RULES or guidance["completion_gate"]["fail_closed"] is not True:raise ValueError("exact learned protections required")
    service=SyntheticHumanReviewIssueMatrix()
    for start,end,name in WORKSTREAMS:
        for cid in range(start,end+1):
            aspect=CONTROL_ASPECTS[(cid-8701)%25]; service.add_control(cid,name,aspect,f"synthetic:issue-matrix-requirement:{(cid-8701)//25:02}",d(f"fixture:{cid}"),"EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS")
    bundles=[]; claims=[]; manifests=[]; receipts=[]; versions=[]
    for flow in FLOWS:
        for index,kind in enumerate(ANSWER_KINDS):
            claim=(d(f"claim:{flow}:{kind}"),)*2; manifest_digest=(d(f"manifest:{flow}:{kind}"),)*2; receipt=(d(f"receipt:{flow}:{kind}"),)*2; version=(1,1)
            if index==1:claim=(claim[0],d(f"counter-claim:{flow}:{kind}"))
            if index==2:manifest_digest=(manifest_digest[0],d(f"counter-manifest:{flow}:{kind}"))
            if index==3:receipt=(receipt[0],d(f"counter-receipt:{flow}:{kind}"))
            if index==4:version=(1,2)
            bundles.append(bundle_projection_digest(flow,kind,claim,manifest_digest,receipt,version)); claims.append(claim); manifests.append(manifest_digest); receipts.append(receipt); versions.append(version)
    reviewers=("synthetic:readiness-reviewer:maker","synthetic:preflight-reviewer:checker","synthetic:reconsideration-reviewer:independent"); compilers=tuple(f"synthetic:packet-compiler:source-{i}" for i in range(1,5))
    bset=canonical_digest(tuple(bundles)); source=canonical_digest(("SUBMISSION_HOLD_DOCKET_SOURCE",bset,reviewers,compilers,"synthetic:human-deliberation-chair:chair","synthetic:cross-party-validator:cross"))
    service.anchor_docket("synthetic:issue-matrix-anchor:evidence",source,bset,sha256(rb).hexdigest(),sha256(mb).hexdigest(),lessons,rules,bundles,claims,manifests,receipts,versions,reviewers,compilers,"synthetic:human-deliberation-chair:chair","synthetic:cross-party-validator:cross",18,True)
    for flow in FLOWS:
        for kind in ANSWER_KINDS:service.add_issue(f"synthetic:human-review-issue:{flow}:{kind}",flow,kind)
    service.finalize("synthetic:human-review-issue-matrix:evidence","synthetic:issue-matrix-compiler:compiler","synthetic:issue-matrix-validator:validator")
    evidence=service.evidence()
    if not evidence["complete_issue_matrix_evidence"] or evidence["registered_control_count"]!=400:raise ValueError("incomplete evidence")
    evidence.update({"lesson_registry_read_and_applied":True,"lesson_registry_version":registry["version"],"lesson_registry_digest":sha256(rb).hexdigest(),"remediation_manifest_digest":sha256(mb).hexdigest(),"remediation_guidance_digest":sha256(gb).hexdigest(),"lesson_validation_mode":"STABLE_MANIFEST_NO_GIT_HISTORY_DEPENDENCY"})
    out=ROOT/"build/synthetic-human-review-issue-matrix-evidence.json"; out.parent.mkdir(exist_ok=True); content=json.dumps(evidence,ensure_ascii=False,indent=2,sort_keys=True)+"\n"; out.write_text(content,encoding="utf-8"); checksum=sha256(content.encode()).hexdigest(); out.with_suffix(".json.sha256").write_text(checksum+"\n",encoding="utf-8"); print("synthetic human review issue matrix #8701-#9100: PASS",checksum)
if __name__=="__main__":main()
