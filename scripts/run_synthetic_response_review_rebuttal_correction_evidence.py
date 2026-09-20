from hashlib import sha256
import json
from pathlib import Path
from nurion_pg.arkaon.governance import canonical_digest
from nurion_pg.synthetic_response_review_rebuttal_correction import *
from validate_arkaon_lesson_registry import MANIFEST,declared_remediations,discovered_negative_tests,validate
ROOT=Path(__file__).resolve().parents[1];REGISTRY=ROOT/"config/arkaon-lesson-registry-v1.json";GUIDANCE=ROOT/"config/arkaon-audit-recurrence-prevention.json"
def d(v):return sha256(v.encode()).hexdigest()
def main():
 rb=REGISTRY.read_bytes();mb=MANIFEST.read_bytes();gb=GUIDANCE.read_bytes();lessons=validate(json.loads(rb),declared_remediations(json.loads(mb)),discovered_negative_tests());rules=tuple(x["id"] for x in json.loads(gb)["rules"])
 if lessons!=APPLIED_LESSONS or rules!=APPLIED_RULES:raise ValueError("exact lessons required")
 s=SyntheticResponseReviewRebuttalCorrection()
 for start,end,name in WORKSTREAMS:
  for cid in range(start,end+1):
   a=CONTROL_ASPECTS[(cid-9901)%25];s.add_control(cid,name,a,f"synthetic:response-review-requirement:{(cid-9901)//25:02}",d(f"fixture:{cid}"),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
 rows=[]
 for f in FLOWS:
  for i,k in enumerate(ANSWER_KINDS):
   o=OUTCOMES[i];present=i>0;req=d(f"request:{f}:{k}");res=RESPONDER[f] if present else None;doc=d(f"response:{f}:{k}") if present else None;parent=None if not rows else rows[-1].intake_digest;dig=intake_digest(f,k,o,req,res,doc,parent,present);rows.append(SourceIntake(f,k,o,req,res,doc,parent,present,dig))
 rows=tuple(rows);iset=canonical_digest(tuple(x.intake_digest for x in rows));roles=tuple(f"synthetic:{kind}:{i}" for i,kind in enumerate(SOURCE_ROLE_KINDS));docket=canonical_digest(("CLARIFICATION_RESPONSE_INTAKE_DOCKET_SOURCE",iset,roles));s.anchor("synthetic:response-review-anchor:evidence",docket,iset,sha256(rb).hexdigest(),sha256(mb).hexdigest(),lessons,rules,rows,roles,21,True)
 for f in FLOWS:
  for i,k in enumerate(ANSWER_KINDS):
   args=(f"synthetic:response-review:{f}:{k}",f,k)
   if i==0:s.add_review(*args)
   elif i<3:s.add_review(*args,f"synthetic:response-independent-reviewer:r-{f}-{k}",f"synthetic:rebuttal-custodian:c-{f}-{k}")
   else:s.add_review(*args,f"synthetic:response-independent-reviewer:r-{f}-{k}",f"synthetic:correction-request-compiler:c-{f}-{k}")
 s.finalize("synthetic:response-review-docket:evidence","synthetic:review-docket-compiler:compiler","synthetic:review-docket-validator:validator");e=s.evidence()
 if not e["complete_review_docket_evidence"] or e["registered_control_count"]!=400:raise ValueError("incomplete")
 e.update({"lesson_registry_digest":sha256(rb).hexdigest(),"remediation_manifest_digest":sha256(mb).hexdigest(),"remediation_guidance_digest":sha256(gb).hexdigest()});out=ROOT/"build/synthetic-response-review-rebuttal-correction-evidence.json";out.parent.mkdir(exist_ok=True);content=json.dumps(e,ensure_ascii=False,indent=2,sort_keys=True)+"\n";out.write_text(content,encoding="utf-8");checksum=sha256(content.encode()).hexdigest();out.with_suffix(".json.sha256").write_text(checksum+"\n",encoding="utf-8");print("synthetic response review #9901-#10300: PASS",checksum)
if __name__=="__main__":main()
