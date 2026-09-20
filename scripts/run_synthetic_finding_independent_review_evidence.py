from hashlib import sha256
import json
from pathlib import Path

from nurion_pg.arkaon.governance import canonical_digest
from nurion_pg.synthetic_finding_independent_review import *
from nurion_pg.synthetic_rebuttal_correction_submission_validation import RESPONDER, derived_receipt_digest, submission_digest
from validate_arkaon_lesson_registry import MANIFEST, declared_remediations, discovered_negative_tests, validate

ROOT=Path(__file__).resolve().parents[1];REGISTRY=ROOT/"config/arkaon-lesson-registry-v1.json";GUIDANCE=ROOT/"config/arkaon-audit-recurrence-prevention.json"
def d(v):return sha256(v.encode()).hexdigest()

def main():
    registry_bytes=REGISTRY.read_bytes();manifest_bytes=MANIFEST.read_bytes();guidance_bytes=GUIDANCE.read_bytes();lessons=validate(json.loads(registry_bytes),declared_remediations(json.loads(manifest_bytes)),discovered_negative_tests());rules=tuple(x["id"] for x in json.loads(guidance_bytes)["rules"])
    if lessons!=APPLIED_LESSONS or rules!=APPLIED_RULES:raise ValueError("exact ordered lessons and rules required")
    s=SyntheticFindingIndependentReview()
    for cid in range(11501,11901):
        w,a=s._expected(cid);s.add_control(cid,w,a,f"synthetic:finding-review-requirement:{(cid-11501)//25:02}",d(f"fixture:{cid}"),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    submissions=[];rereviews=[];findings=[]
    for i,(flow,kind) in enumerate(CASE_KEYS):
        route=ROUTES[i%5];sp=None if not submissions else submissions[-1].digest;review=d(f"review:{flow}:{kind}")
        if route=="NOT_APPLICABLE_PRESERVED":submitter=document=receipt=None;sm="NO_SUBMISSION_REQUIRED"
        else:submitter=RESPONDER[flow];document=d(f"document:{flow}:{kind}");receipt=derived_receipt_digest(flow,kind,review,route,submitter,document);sm="SUBMISSION_RECEIVED_FOR_HUMAN_REVIEW"
        sd=submission_digest(flow,kind,review,route,submitter,document,receipt,sm,sp,i+1);submissions.append(SourceSubmission(f"synthetic:rebuttal-correction-submission:{flow}:{kind}",flow,kind,review,route,submitter,document,receipt,sm,sp,i+1,True,True,False,False,sd))
        rp=None if not rereviews else rereviews[-1].digest;rr=None if route=="NOT_APPLICABLE_PRESERVED" else f"synthetic:independent-human-rereviewer:rereviewer-{i}";rm="NO_SUBMISSION_MARKER_PRESERVED" if rr is None else "HUMAN_REEXAMINATION_PENDING";rid=f"synthetic:independent-rereview:{flow}:{kind}";rd=rereview_digest(rid,flow,kind,sd,route,rr,rm,rp,i+1);rereviews.append(SourceReReview(rid,flow,kind,sd,route,rr,rm,rp,i+1,True,rr is not None,False,False,False,rd))
        fp=None if not findings else findings[-1].digest;drafter=None if rr is None else f"synthetic:finding-drafter:drafter-{i}";reviewer=None if rr is None else f"synthetic:finding-reviewer:finding-reviewer-{i}";fm="NO_FINDING_MARKER_PRESERVED" if rr is None else "HUMAN_FINDING_REVIEW_PENDING";projection=observation_projection_digest(rd,route,drafter,reviewer,fm);fid=f"synthetic:finding-observation:{flow}:{kind}";fd=finding_digest(fid,flow,kind,rd,route,drafter,reviewer,fm,fp,i+1,projection);findings.append(Finding(fid,flow,kind,rd,route,drafter,reviewer,fm,fp,i+1,projection,True,rr is not None,False,False,False,False,fd))
    submissions,rereviews,findings=tuple(submissions),tuple(rereviews),tuple(findings);fset=canonical_digest(tuple(x.digest for x in findings));sc="synthetic:submission-docket-compiler:source-compiler";sv="synthetic:submission-docket-validator:source-validator";rc="synthetic:rereview-docket-compiler:rereview-compiler";rv="synthetic:rereview-docket-validator:rereview-validator";fc="synthetic:finding-docket-compiler:finding-compiler";fv="synthetic:finding-docket-validator:finding-validator";roles=tuple(f"synthetic:{kind}:source-actor-{i}" for i,kind in enumerate(SOURCE_ACTOR_KINDS));docket=canonical_digest(("FINDING_OBSERVATION_DOCKET_SOURCE",fset,fc,fv))
    s.anchor("synthetic:finding-independent-review-anchor:evidence",docket,fset,sha256(registry_bytes).hexdigest(),sha256(manifest_bytes).hexdigest(),lessons,rules,submissions,rereviews,findings,roles,sc,sv,rc,rv,fc,fv,25,True)
    for i,(flow,kind) in enumerate(CASE_KEYS):
        args=(f"synthetic:independent-finding-review:{flow}:{kind}",flow,kind)
        if ROUTES[i%5]=="NOT_APPLICABLE_PRESERVED":s.add_review(*args)
        else:s.add_review(*args,f"synthetic:independent-finding-reviewer:reviewer-{i}",f"synthetic:finding-review-custodian:custodian-{i}")
    s.finalize("synthetic:finding-independent-review-docket:evidence","synthetic:finding-review-docket-compiler:compiler","synthetic:finding-review-docket-validator:validator");e=s.evidence()
    if not e["complete_pending_finding_review_evidence"] or e["registered_control_count"]!=400 or e["judgment_preparation_packet_count"]!=16 or e["judgment_authority"] is not False:raise ValueError("incomplete or over-authoritative evidence")
    result_keys=("review_projection_set_digest","review_set_digest","final_docket_digest","complete_role_lineage_digest")
    if not all(isinstance(e[k],str) and len(e[k])==64 for k in result_keys):raise ValueError("content-addressed results required")
    e.update({"lesson_registry_digest":sha256(registry_bytes).hexdigest(),"remediation_manifest_digest":sha256(manifest_bytes).hexdigest(),"audit_remediation":"ETH-11101-AUDIT-001"})
    out=ROOT/"build/synthetic-finding-independent-review-evidence.json";out.parent.mkdir(exist_ok=True);payload=json.dumps(e,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode();out.write_bytes(payload);digest=sha256(payload).hexdigest();out.with_suffix(out.suffix+".sha256").write_text(digest+"\n",encoding="utf-8");print(digest)

if __name__=="__main__":main()
