from hashlib import sha256
import json
from pathlib import Path

from nurion_pg.arkaon.governance import canonical_digest
from nurion_pg.synthetic_cross_party_answer_reconciliation import *
from validate_arkaon_lesson_registry import MANIFEST, declared_remediations, discovered_negative_tests, validate

ROOT=Path(__file__).resolve().parents[1]; REGISTRY=ROOT/"config/arkaon-lesson-registry-v1.json"; GUIDANCE=ROOT/"config/arkaon-audit-recurrence-prevention.json"
def d(x): return sha256(x.encode()).hexdigest()
def main():
    rb=REGISTRY.read_bytes(); mb=MANIFEST.read_bytes(); gb=GUIDANCE.read_bytes(); registry=json.loads(rb); manifest=json.loads(mb); guidance=json.loads(gb)
    lessons=validate(registry,declared_remediations(manifest),discovered_negative_tests()); rules=tuple(x["id"] for x in guidance["rules"])
    if lessons!=APPLIED_LESSONS or rules!=APPLIED_RULES or guidance["completion_gate"]["fail_closed"] is not True: raise ValueError("exact stable learned protections required")
    s=SyntheticCrossPartyAnswerReconciliation()
    for start,end,name in WORKSTREAMS:
        for cid in range(start,end+1):
            a=CONTROL_ASPECTS[(cid-7901)%25]; s.add_control(cid,name,a,f"synthetic:reconciliation-requirement:{(cid-7901)//25:02}",d(f"fixture:{cid}"),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    rows=[]
    for flow in FLOWS:
        source,counter=FLOW_PARTIES[flow]
        for kind in ANSWER_KINDS:
            pair="tenant-nurion" if "tenant" in flow else "nurion-upstream"; side="a" if flow in ("tenant_to_nurion","nurion_to_upstream") else "b"
            claim=d(f"claim:{pair}:{kind}:{side}" if kind=="RESIDUAL_RISK_RESPONSE" else f"claim:{pair}:{kind}")
            manifest=d(f"manifest:{pair}:{kind}:{side}" if kind=="ADDITIONAL_EVIDENCE" else f"manifest:{pair}:{kind}")
            receipt=d(f"receipt:{pair}:{kind}:{side}" if kind=="MEANING_CLARIFICATION" else f"receipt:{pair}:{kind}")
            version=2 if kind=="SAFE_BOUNDARY_ACKNOWLEDGEMENT" and side=="b" else 1; vals=(d(f"answer:{flow}:{kind}"),claim,manifest,receipt)
            binding=canonical_digest(("ANSWER_PROVENANCE",flow,kind,source,counter,*vals,version)); rows.append(AnswerProvenance(flow,kind,source,counter,*vals,version,binding))
    reviewers=("synthetic:readiness-reviewer:maker","synthetic:preflight-reviewer:checker","synthetic:reconsideration-reviewer:independent")
    compilers=("synthetic:packet-compiler:antecedent","synthetic:packet-compiler:conflict","synthetic:packet-compiler:simulation")
    s.anchor_source("synthetic:reconciliation-anchor:evidence",d("intake-packet"),d("answer-set"),sha256(rb).hexdigest(),sha256(mb).hexdigest(),lessons,rules,rows,16,True,reviewers,compilers,"synthetic:human-deliberation-chair:chair","synthetic:intake-validator:intake")
    for flow in FLOWS:
        for kind in ANSWER_KINDS:s.add_case(f"synthetic:reconciliation-case:{flow}:{kind}",flow,kind,f"synthetic:reconciliation-submitter:{FLOW_PARTIES[flow][0]}","synthetic:cross-party-validator:cross")
    s.finalize("synthetic:reconciliation-queue-packet:evidence","synthetic:reconciliation-queue-compiler:queue")
    evidence=s.evidence()
    if not evidence["complete_reconciliation_queue_evidence"] or evidence["registered_control_count"]!=400: raise ValueError("incomplete evidence")
    evidence.update({"lesson_registry_read_and_applied":True,"lesson_registry_version":registry["version"],"lesson_registry_digest":sha256(rb).hexdigest(),"remediation_manifest_digest":sha256(mb).hexdigest(),"remediation_guidance_digest":sha256(gb).hexdigest(),"lesson_validation_mode":"STABLE_MANIFEST_NO_GIT_HISTORY_DEPENDENCY"})
    out=ROOT/"build/synthetic-cross-party-answer-reconciliation-evidence.json"; out.parent.mkdir(exist_ok=True); content=json.dumps(evidence,ensure_ascii=False,indent=2,sort_keys=True)+"\n"; out.write_text(content,encoding="utf-8"); checksum=sha256(content.encode()).hexdigest(); out.with_suffix(".json.sha256").write_text(checksum+"\n",encoding="utf-8"); print("synthetic cross-party answer reconciliation #7901-#8300: PASS",checksum)
if __name__=="__main__": main()
