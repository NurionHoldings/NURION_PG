from hashlib import sha256
import json
from pathlib import Path

from nurion_pg.arkaon.governance import canonical_digest
from nurion_pg.synthetic_answer_material_intake_validation import *
from validate_arkaon_lesson_registry import MANIFEST, declared_remediations, discovered_negative_tests, validate

ROOT=Path(__file__).resolve().parents[1]; REGISTRY=ROOT/"config/arkaon-lesson-registry-v1.json"; GUIDANCE=ROOT/"config/arkaon-audit-recurrence-prevention.json"
def d(x): return sha256(x.encode()).hexdigest()
def main():
    rb=REGISTRY.read_bytes(); mb=MANIFEST.read_bytes(); gb=GUIDANCE.read_bytes(); registry=json.loads(rb); manifest=json.loads(mb); guidance=json.loads(gb)
    lessons=validate(registry,declared_remediations(manifest),discovered_negative_tests()); rules=tuple(x["id"] for x in guidance["rules"])
    if lessons != APPLIED_LESSONS or rules != APPLIED_RULES or guidance["completion_gate"]["fail_closed"] is not True: raise ValueError("exact stable learned protections required")
    s=SyntheticAnswerMaterialIntakeValidation()
    for start,end,name in WORKSTREAMS:
        for cid in range(start,end+1):
            a=CONTROL_ASPECTS[(cid-7501)%25]; s.add_control(cid,name,a,f"synthetic:answer-intake-requirement:{(cid-7501)//25:02}",d(f"fixture:{cid}"),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    docs=tuple((p,d(f"document:{p}")) for p in PARTIES); docket=d("question-docket"); qset=d("question-set")
    routes=tuple((f,canonical_digest(("ANSWER_INTAKE_ROUTE",f,FLOW_PARTIES[f],docs,docket,qset))) for f in FLOWS)
    reviewers=("synthetic:readiness-reviewer:maker","synthetic:preflight-reviewer:checker","synthetic:reconsideration-reviewer:independent")
    compilers=("synthetic:packet-compiler:antecedent","synthetic:packet-compiler:conflict","synthetic:packet-compiler:simulation")
    anchor=s.anchor_source("synthetic:answer-intake-anchor:evidence",docket,qset,sha256(rb).hexdigest(),sha256(mb).hexdigest(),lessons,rules,docs,routes,15,True,reviewers,compilers,"synthetic:human-deliberation-chair:chair")
    for flow in FLOWS:
        source,counter=FLOW_PARTIES[flow]; route=dict(anchor.route_binding_digests)[flow]
        for kind in ANSWER_KINDS:
            question=canonical_digest(("SOURCE_QUESTION",anchor.question_set_digest,flow,kind,source,counter,route)); source_doc=dict(anchor.party_document_digests)[source]
            claim=canonical_digest(("SYNTHETIC_SEMANTIC_CLAIM",question,source,counter,source_doc,route)); manifest_digest=canonical_digest(("SYNTHETIC_MATERIAL_MANIFEST",question,source,counter,claim,route,1))
            answer=canonical_digest(("SYNTHETIC_ANSWER_DOCUMENT",question,source,counter,1,claim,manifest_digest)); receipt=canonical_digest(("SYNTHETIC_SOURCE_RECEIPT",source,flow,kind,answer,manifest_digest,1,None))
            s.add_answer_material(f"synthetic:answer-material:{flow}:{kind}",flow,kind,question,answer,manifest_digest,receipt,1,None,claim,f"synthetic:answer-submitter:{source}",f"synthetic:intake-reviewer:{counter}")
    s.finalize("synthetic:answer-intake-packet:evidence","synthetic:intake-validator:validator")
    evidence=s.evidence()
    if not evidence["complete_answer_material_validation_evidence"] or evidence["registered_control_count"] != 400: raise ValueError("incomplete evidence")
    evidence.update({"lesson_registry_read_and_applied":True,"lesson_registry_version":registry["version"],"lesson_registry_digest":sha256(rb).hexdigest(),"remediation_manifest_digest":sha256(mb).hexdigest(),"remediation_guidance_digest":sha256(gb).hexdigest(),"lesson_validation_mode":"STABLE_MANIFEST_NO_GIT_HISTORY_DEPENDENCY"})
    out=ROOT/"build/synthetic-answer-material-intake-validation-evidence.json"; out.parent.mkdir(exist_ok=True); content=json.dumps(evidence,ensure_ascii=False,indent=2,sort_keys=True)+"\n"; out.write_text(content,encoding="utf-8"); checksum=sha256(content.encode()).hexdigest(); out.with_suffix(".json.sha256").write_text(checksum+"\n",encoding="utf-8"); print("synthetic answer material intake validation #7501-#7900: PASS",checksum)
if __name__ == "__main__": main()
