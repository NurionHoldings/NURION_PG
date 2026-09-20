from hashlib import sha256
import json
from pathlib import Path

from nurion_pg.arkaon.governance import canonical_digest
from nurion_pg.synthetic_human_review_clarification_docket import *
from validate_arkaon_lesson_registry import MANIFEST, declared_remediations, discovered_negative_tests, validate

ROOT=Path(__file__).resolve().parents[1]; REGISTRY=ROOT/"config/arkaon-lesson-registry-v1.json"; GUIDANCE=ROOT/"config/arkaon-audit-recurrence-prevention.json"
def d(v):return sha256(v.encode()).hexdigest()
def main():
    rb=REGISTRY.read_bytes(); mb=MANIFEST.read_bytes(); gb=GUIDANCE.read_bytes(); registry=json.loads(rb); manifest=json.loads(mb); guidance=json.loads(gb)
    lessons=validate(registry,declared_remediations(manifest),discovered_negative_tests()); rules=tuple(x["id"] for x in guidance["rules"])
    if lessons!=APPLIED_LESSONS or rules!=APPLIED_RULES or guidance["completion_gate"]["fail_closed"] is not True:raise ValueError("exact learned protections required")
    service=SyntheticHumanReviewClarificationDocket()
    for start,end,name in WORKSTREAMS:
        for cid in range(start,end+1):
            aspect=CONTROL_ASPECTS[(cid-9101)%25]; service.add_control(cid,name,aspect,f"synthetic:clarification-docket-requirement:{(cid-9101)//25:02}",d(f"fixture:{cid}"),"EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS")
    issues=[]
    for flow in FLOWS:
        for i,kind in enumerate(ANSWER_KINDS):
            claim=(d(f"claim:{flow}:{kind}"),)*2; material=(d(f"manifest:{flow}:{kind}"),)*2; receipt=(d(f"receipt:{flow}:{kind}"),)*2; version=(1,1)
            if i==1:claim=(claim[0],d(f"counter-claim:{flow}:{kind}"))
            if i==2:material=(material[0],d(f"counter-manifest:{flow}:{kind}"))
            if i==3:receipt=(receipt[0],d(f"counter-receipt:{flow}:{kind}"))
            if i==4:version=(1,2)
            outcome=actual_outcome(claim,material,receipt,version); bundle=bundle_projection_digest(flow,kind,claim,material,receipt,version); parent=None if not issues else issues[-1].projection_digest; projection=issue_projection_digest(flow,kind,outcome,bundle,claim,material,receipt,version,parent)
            issues.append(SourceIssue(flow,kind,outcome,bundle,claim,material,receipt,version,parent,projection))
    issues=tuple(issues); issue_set=canonical_digest(tuple(x.projection_digest for x in issues)); reviewers=("synthetic:readiness-reviewer:maker","synthetic:preflight-reviewer:checker","synthetic:reconsideration-reviewer:independent"); compilers=tuple(f"synthetic:packet-compiler:source-{i}" for i in range(1,5)); mc="synthetic:issue-matrix-compiler:matrix"; mv="synthetic:issue-matrix-validator:validation"; matrix=canonical_digest(("HUMAN_REVIEW_ISSUE_MATRIX_SOURCE",issue_set,mc,mv))
    service.anchor_matrix("synthetic:clarification-docket-anchor:evidence",matrix,issue_set,sha256(rb).hexdigest(),sha256(mb).hexdigest(),lessons,rules,issues,reviewers,compilers,"synthetic:human-deliberation-chair:chair","synthetic:cross-party-validator:cross",mc,mv,19,True)
    for flow in FLOWS:
        for kind in ANSWER_KINDS:service.add_request(f"synthetic:clarification-request:{flow}:{kind}",flow,kind)
    service.finalize("synthetic:human-clarification-docket:evidence","synthetic:clarification-drafter:drafter","synthetic:clarification-reviewer:reviewer")
    evidence=service.evidence()
    if not evidence["complete_clarification_docket_evidence"] or evidence["registered_control_count"]!=400:raise ValueError("incomplete evidence")
    evidence.update({"lesson_registry_read_and_applied":True,"lesson_registry_version":registry["version"],"lesson_registry_digest":sha256(rb).hexdigest(),"remediation_manifest_digest":sha256(mb).hexdigest(),"remediation_guidance_digest":sha256(gb).hexdigest(),"lesson_validation_mode":"STABLE_MANIFEST_NO_GIT_HISTORY_DEPENDENCY"})
    out=ROOT/"build/synthetic-human-review-clarification-docket-evidence.json"; out.parent.mkdir(exist_ok=True); content=json.dumps(evidence,ensure_ascii=False,indent=2,sort_keys=True)+"\n"; out.write_text(content,encoding="utf-8"); checksum=sha256(content.encode()).hexdigest(); out.with_suffix(".json.sha256").write_text(checksum+"\n",encoding="utf-8"); print("synthetic human review clarification docket #9101-#9500: PASS",checksum)
if __name__=="__main__":main()
