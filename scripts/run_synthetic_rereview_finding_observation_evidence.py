from hashlib import sha256
import json
from pathlib import Path

from nurion_pg.arkaon.governance import canonical_digest
from nurion_pg.synthetic_rebuttal_correction_submission_validation import RESPONDER, derived_receipt_digest, submission_digest
from nurion_pg.synthetic_rereview_finding_observation import *
from validate_arkaon_lesson_registry import MANIFEST, declared_remediations, discovered_negative_tests, validate

ROOT=Path(__file__).resolve().parents[1];REGISTRY=ROOT/"config/arkaon-lesson-registry-v1.json";GUIDANCE=ROOT/"config/arkaon-audit-recurrence-prevention.json"
def d(value):return sha256(value.encode()).hexdigest()

def main():
    registry_bytes=REGISTRY.read_bytes();manifest_bytes=MANIFEST.read_bytes();guidance_bytes=GUIDANCE.read_bytes()
    lessons=validate(json.loads(registry_bytes),declared_remediations(json.loads(manifest_bytes)),discovered_negative_tests());rules=tuple(x["id"] for x in json.loads(guidance_bytes)["rules"])
    if lessons!=APPLIED_LESSONS or rules!=APPLIED_RULES:raise ValueError("exact lessons and rules required")
    service=SyntheticReReviewFindingObservation()
    for control_id in range(11101,11501):
        workstream,aspect=service._expected(control_id);service.add_control(control_id,workstream,aspect,f"synthetic:finding-observation-requirement:{(control_id-11101)//25:02}",d(f"fixture:{control_id}"),"EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS")
    submissions=[];rereviews=[]
    for position,(flow,kind) in enumerate(CASE_KEYS):
        route=ROUTES[position%5];parent=None if not submissions else submissions[-1].digest;review=d(f"review:{flow}:{kind}")
        if route=="NOT_APPLICABLE_PRESERVED":submitter=document=receipt=None;marker="NO_SUBMISSION_REQUIRED"
        else:submitter=RESPONDER[flow];document=d(f"document:{flow}:{kind}");receipt=derived_receipt_digest(flow,kind,review,route,submitter,document);marker="SUBMISSION_RECEIVED_FOR_HUMAN_REVIEW"
        sd=submission_digest(flow,kind,review,route,submitter,document,receipt,marker,parent,position+1);submissions.append(SourceSubmission(f"synthetic:rebuttal-correction-submission:{flow}:{kind}",flow,kind,review,route,submitter,document,receipt,marker,parent,position+1,True,True,False,False,sd))
        rp=None if not rereviews else rereviews[-1].digest;rr=None if route=="NOT_APPLICABLE_PRESERVED" else f"synthetic:independent-human-rereviewer:rereviewer-{position}";rm="NO_SUBMISSION_MARKER_PRESERVED" if rr is None else "HUMAN_REEXAMINATION_PENDING";rid=f"synthetic:independent-rereview:{flow}:{kind}";rd=rereview_digest(rid,flow,kind,sd,route,rr,rm,rp,position+1);rereviews.append(SourceReReview(rid,flow,kind,sd,route,rr,rm,rp,position+1,True,rr is not None,False,False,False,rd))
    submissions=tuple(submissions);rereviews=tuple(rereviews);rset=canonical_digest(tuple(x.digest for x in rereviews));sc="synthetic:submission-docket-compiler:source-compiler";sv="synthetic:submission-docket-validator:source-validator";rc="synthetic:rereview-docket-compiler:rereview-compiler";rv="synthetic:rereview-docket-validator:rereview-validator";actors=tuple(f"synthetic:{kind}:source-actor-{i}" for i,kind in enumerate(SOURCE_ACTOR_KINDS));docket=canonical_digest(("INDEPENDENT_REREVIEW_DOCKET_SOURCE",rset,rc,rv))
    service.anchor("synthetic:finding-observation-anchor:evidence",docket,rset,sha256(registry_bytes).hexdigest(),sha256(manifest_bytes).hexdigest(),lessons,rules,submissions,rereviews,actors,sc,sv,rc,rv,24,True)
    for position,(flow,kind) in enumerate(CASE_KEYS):
        args=(f"synthetic:finding-observation:{flow}:{kind}",flow,kind)
        if ROUTES[position%5]=="NOT_APPLICABLE_PRESERVED":service.add_finding(*args)
        else:service.add_finding(*args,f"synthetic:finding-drafter:drafter-{position}",f"synthetic:finding-reviewer:finding-reviewer-{position}")
    service.finalize("synthetic:finding-observation-docket:evidence","synthetic:finding-docket-compiler:compiler","synthetic:finding-docket-validator:validator")
    evidence=service.evidence()
    if not evidence["complete_pending_finding_docket_evidence"] or evidence["registered_control_count"]!=400:raise ValueError("incomplete evidence")
    projection_set=canonical_digest(tuple(service._findings[k].observation_projection_digest for k in CASE_KEYS));finding_set=canonical_digest(tuple(service._findings[k].digest for k in CASE_KEYS));expected=(projection_set,finding_set,service._docket.digest);actual=tuple(evidence[k] for k in ("observation_projection_set_digest","finding_set_digest","final_docket_digest"))
    if actual!=expected or not all(isinstance(x,str) and len(x)==64 and all(c in "0123456789abcdef" for c in x) for x in actual):raise ValueError("content-addressed result digests required")
    evidence.update({"lesson_registry_digest":sha256(registry_bytes).hexdigest(),"remediation_manifest_digest":sha256(manifest_bytes).hexdigest(),"applied_lesson_ids":lessons,"applied_rule_ids":rules,"audit_remediation":"ETH-10701-AUDIT-001"})
    out=ROOT/"build/synthetic-rereview-finding-observation-evidence.json";out.parent.mkdir(exist_ok=True);payload=json.dumps(evidence,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode();out.write_bytes(payload);digest=sha256(payload).hexdigest();out.with_suffix(out.suffix+".sha256").write_text(digest+"\n",encoding="utf-8");print(digest)

if __name__=="__main__":main()
