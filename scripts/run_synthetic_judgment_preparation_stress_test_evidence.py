from hashlib import sha256
import json
from pathlib import Path

from nurion_pg.arkaon.governance import canonical_digest
from nurion_pg.synthetic_judgment_preparation_stress_test import *
from nurion_pg.synthetic_finding_independent_review import SyntheticFindingIndependentReview
from nurion_pg.synthetic_rereview_finding_observation import Finding, SourceReReview, SourceSubmission, SOURCE_ACTOR_KINDS, finding_digest, observation_projection_digest, rereview_digest
from nurion_pg.synthetic_rebuttal_correction_submission_validation import RESPONDER, ROUTES, derived_receipt_digest, submission_digest
from validate_arkaon_lesson_registry import MANIFEST, declared_remediations, discovered_negative_tests, validate

ROOT=Path(__file__).resolve().parents[1];REGISTRY=ROOT/"config/arkaon-lesson-registry-v1.json";GUIDANCE=ROOT/"config/arkaon-audit-recurrence-prevention.json"
def d(v):return sha256(v.encode()).hexdigest()

def prior_service(old_lessons,rules,registry_digest,manifest_digest):
    s=SyntheticFindingIndependentReview()
    for cid in range(11501,11901):
        w,a=s._expected(cid);s.add_control(cid,w,a,f"synthetic:finding-review-requirement:{(cid-11501)//25:02}",d(f"prior:{cid}"),"EXPECTED_REJECTION" if a in __import__("nurion_pg.synthetic_finding_independent_review",fromlist=["NEGATIVE"]).NEGATIVE else "PASS")
    submissions=[];rereviews=[];findings=[]
    for i,(flow,kind) in enumerate(CASE_KEYS):
        route=ROUTES[i%5];sp=None if not submissions else submissions[-1].digest;review=d(f"review:{flow}:{kind}")
        if route=="NOT_APPLICABLE_PRESERVED":submitter=document=receipt=None;sm="NO_SUBMISSION_REQUIRED"
        else:submitter=RESPONDER[flow];document=d(f"document:{flow}:{kind}");receipt=derived_receipt_digest(flow,kind,review,route,submitter,document);sm="SUBMISSION_RECEIVED_FOR_HUMAN_REVIEW"
        sd=submission_digest(flow,kind,review,route,submitter,document,receipt,sm,sp,i+1);submissions.append(SourceSubmission(f"synthetic:rebuttal-correction-submission:{flow}:{kind}",flow,kind,review,route,submitter,document,receipt,sm,sp,i+1,True,True,False,False,sd))
        rp=None if not rereviews else rereviews[-1].digest;rr=None if route=="NOT_APPLICABLE_PRESERVED" else f"synthetic:independent-human-rereviewer:rereviewer-{i}";rm="NO_SUBMISSION_MARKER_PRESERVED" if rr is None else "HUMAN_REEXAMINATION_PENDING";rid=f"synthetic:independent-rereview:{flow}:{kind}";rd=rereview_digest(rid,flow,kind,sd,route,rr,rm,rp,i+1);rereviews.append(SourceReReview(rid,flow,kind,sd,route,rr,rm,rp,i+1,True,rr is not None,False,False,False,rd))
        fp=None if not findings else findings[-1].digest;drafter=None if rr is None else f"synthetic:finding-drafter:drafter-{i}";reviewer=None if rr is None else f"synthetic:finding-reviewer:finding-reviewer-{i}";fm="NO_FINDING_MARKER_PRESERVED" if rr is None else "HUMAN_FINDING_REVIEW_PENDING";projection=observation_projection_digest(rd,route,drafter,reviewer,fm);fid=f"synthetic:finding-observation:{flow}:{kind}";fd=finding_digest(fid,flow,kind,rd,route,drafter,reviewer,fm,fp,i+1,projection);findings.append(Finding(fid,flow,kind,rd,route,drafter,reviewer,fm,fp,i+1,projection,True,rr is not None,False,False,False,False,fd))
    submissions,rereviews,findings=tuple(submissions),tuple(rereviews),tuple(findings);fset=canonical_digest(tuple(x.digest for x in findings));sc="synthetic:submission-docket-compiler:source-compiler";sv="synthetic:submission-docket-validator:source-validator";rc="synthetic:rereview-docket-compiler:rereview-compiler";rv="synthetic:rereview-docket-validator:rereview-validator";fc="synthetic:finding-docket-compiler:finding-compiler";fv="synthetic:finding-docket-validator:finding-validator";roles=tuple(f"synthetic:{k}:source-actor-{i}" for i,k in enumerate(SOURCE_ACTOR_KINDS));source_docket=canonical_digest(("FINDING_OBSERVATION_DOCKET_SOURCE",fset,fc,fv))
    s.anchor("synthetic:finding-independent-review-anchor:stress-source",source_docket,fset,registry_digest,manifest_digest,old_lessons,rules,submissions,rereviews,findings,roles,sc,sv,rc,rv,fc,fv,25,True)
    for i,(flow,kind) in enumerate(CASE_KEYS):
        args=(f"synthetic:independent-finding-review:{flow}:{kind}",flow,kind)
        if ROUTES[i%5]=="NOT_APPLICABLE_PRESERVED":s.add_review(*args)
        else:s.add_review(*args,f"synthetic:independent-finding-reviewer:reviewer-{i}",f"synthetic:finding-review-custodian:custodian-{i}")
    s.finalize("synthetic:finding-independent-review-docket:stress-source","synthetic:finding-review-docket-compiler:compiler","synthetic:finding-review-docket-validator:validator");return s

def main():
    registry_bytes=REGISTRY.read_bytes();manifest_bytes=MANIFEST.read_bytes();rules=tuple(x["id"] for x in json.loads(GUIDANCE.read_bytes())["rules"]);lessons=validate(json.loads(registry_bytes),declared_remediations(json.loads(manifest_bytes)),discovered_negative_tests())
    if lessons!=APPLIED_LESSONS or rules!=APPLIED_RULES:raise ValueError("continuous lessons and rules required")
    prior=prior_service(lessons,rules,sha256(registry_bytes).hexdigest(),sha256(manifest_bytes).hexdigest())
    s=SyntheticJudgmentPreparationStressTest()
    for cid in range(11901,12301):
        w,a=s._expected(cid);s.add_control(cid,w,a,f"synthetic:judgment-stress-requirement:{(cid-11901)//25:02}",d(f"fixture:{cid}"),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    s.anchor(prior,sha256(registry_bytes).hexdigest(),sha256(manifest_bytes).hexdigest(),lessons,rules,26,True)
    for i,(flow,kind) in enumerate(CASE_KEYS):
        args=(f"synthetic:judgment-preparation-stress-test:{flow}:{kind}",flow,kind)
        if prior._reviews[(flow,kind)].judgment_packet:s.add_stress_test(*args,f"synthetic:judgment-stress-preparer:preparer-{i}",f"synthetic:judgment-stress-challenger:challenger-{i}")
        else:s.add_stress_test(*args)
    s.finalize("synthetic:judgment-stress-docket:evidence","synthetic:judgment-stress-docket-compiler:stress-final-compiler","synthetic:judgment-stress-docket-validator:stress-final-validator");e=s.evidence()
    if not e["complete_counterfactual_stress_evidence"] or e["registered_control_count"]!=400 or e["option_profile_count"]!=32 or e["judgment_authority"] is not False:raise ValueError("incomplete or over-authoritative evidence")
    e.update({"lesson_registry_digest":sha256(registry_bytes).hexdigest(),"remediation_manifest_digest":sha256(manifest_bytes).hexdigest(),"audit_remediation":"ETH-11501-AUDIT-001"})
    out=ROOT/"build/synthetic-judgment-preparation-stress-test-evidence.json";out.parent.mkdir(exist_ok=True);payload=json.dumps(e,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode();out.write_bytes(payload);digest=sha256(payload).hexdigest();out.with_suffix(out.suffix+".sha256").write_text(digest+"\n",encoding="utf-8");print(digest)
if __name__=="__main__":main()
