from hashlib import sha256
import json
from pathlib import Path
from nurion_pg.arkaon.governance import canonical_digest
from nurion_pg.synthetic_clarification_response_intake import *
from validate_arkaon_lesson_registry import MANIFEST,declared_remediations,discovered_negative_tests,validate
ROOT=Path(__file__).resolve().parents[1];REGISTRY=ROOT/"config/arkaon-lesson-registry-v1.json";GUIDANCE=ROOT/"config/arkaon-audit-recurrence-prevention.json"
def d(v):return sha256(v.encode()).hexdigest()
def main():
 rb=REGISTRY.read_bytes();mb=MANIFEST.read_bytes();gb=GUIDANCE.read_bytes();registry=json.loads(rb);manifest=json.loads(mb);guidance=json.loads(gb);lessons=validate(registry,declared_remediations(manifest),discovered_negative_tests());rules=tuple(x["id"] for x in guidance["rules"])
 if lessons!=APPLIED_LESSONS or rules!=APPLIED_RULES:raise ValueError("exact learned protections required")
 s=SyntheticClarificationResponseIntake()
 for start,end,name in WORKSTREAMS:
  for cid in range(start,end+1):
   a=CONTROL_ASPECTS[(cid-9501)%25];s.add_control(cid,name,a,f"synthetic:response-intake-requirement:{(cid-9501)//25:02}",d(f"fixture:{cid}"),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
 requests=[]
 for f in FLOWS:
  for i,k in enumerate(ANSWER_KINDS):
   o=OUTCOMES[i];t=REQUEST_TYPES[o];issue=d(f"issue:{f}:{k}");parent=None if not requests else requests[-1].request_digest;required=o!="CONSISTENT";rd=request_digest(f,k,o,t,issue,parent,required);requests.append(SourceRequest(f,k,o,t,issue,parent,required,rd))
 requests=tuple(requests);rset=canonical_digest(tuple(x.request_digest for x in requests));roles=tuple(f"synthetic:{kind}:{i}" for i,kind in enumerate(SOURCE_ROLE_KINDS));docket=canonical_digest(("HUMAN_CLARIFICATION_DOCKET_SOURCE",rset,roles));s.anchor_docket("synthetic:response-intake-anchor:evidence",docket,rset,sha256(rb).hexdigest(),sha256(mb).hexdigest(),lessons,rules,requests,roles,20,True)
 for f in FLOWS:
  for i,k in enumerate(ANSWER_KINDS):
   args=(f"synthetic:clarification-response-intake:{f}:{k}",f,k);s.add_intake(*args,RESPONDER[f],d(f"response:{f}:{k}")) if i else s.add_intake(*args)
 s.finalize("synthetic:clarification-response-intake-docket:evidence","synthetic:response-intake-compiler:compiler","synthetic:response-intake-validator:validator");e=s.evidence()
 if not e["complete_response_intake_evidence"] or e["registered_control_count"]!=400:raise ValueError("incomplete evidence")
 e.update({"lesson_registry_read_and_applied":True,"lesson_registry_digest":sha256(rb).hexdigest(),"remediation_manifest_digest":sha256(mb).hexdigest(),"remediation_guidance_digest":sha256(gb).hexdigest()});out=ROOT/"build/synthetic-clarification-response-intake-evidence.json";out.parent.mkdir(exist_ok=True);content=json.dumps(e,ensure_ascii=False,indent=2,sort_keys=True)+"\n";out.write_text(content,encoding="utf-8");checksum=sha256(content.encode()).hexdigest();out.with_suffix(".json.sha256").write_text(checksum+"\n",encoding="utf-8");print("synthetic clarification response intake #9501-#9900: PASS",checksum)
if __name__=="__main__":main()
