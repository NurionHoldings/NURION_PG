from hashlib import sha256
import json
from pathlib import Path

from nurion_pg.arkaon.governance import canonical_digest
from nurion_pg.synthetic_evidence_disclosure_rebuttal_correction_readiness import (
    APPLIED_LESSONS,APPLIED_RULES,CONTROL_ASPECTS,FLOWS,FLOW_PARTIES,NEGATIVE,PARTIES,TOPICS,WORKSTREAMS,
    SyntheticEvidenceDisclosureRebuttalCorrectionReadiness,
)
from validate_arkaon_lesson_registry import MANIFEST,declared_remediations,discovered_negative_tests,validate

ROOT=Path(__file__).resolve().parents[1];REGISTRY=ROOT/"config/arkaon-lesson-registry-v1.json";GUIDANCE=ROOT/"config/arkaon-audit-recurrence-prevention.json"
def d(x):return sha256(x.encode()).hexdigest()
def main():
    rb=REGISTRY.read_bytes();mb=MANIFEST.read_bytes();gb=GUIDANCE.read_bytes();registry=json.loads(rb);manifest=json.loads(mb);guidance=json.loads(gb)
    lessons=validate(registry,declared_remediations(manifest),discovered_negative_tests());rules=tuple(x["id"] for x in guidance["rules"])
    if lessons!=APPLIED_LESSONS or rules!=APPLIED_RULES or guidance["completion_gate"]["fail_closed"] is not True:raise ValueError("exact stable learned protections required")
    s=SyntheticEvidenceDisclosureRebuttalCorrectionReadiness()
    for start,end,name in WORKSTREAMS:
        for cid in range(start,end+1):
            aspect=CONTROL_ASPECTS[(cid-5901)%25];s.add_control(cid,name,aspect,f"synthetic:correction-requirement:{(cid-5901)//25:02}",d(f"fixture:{cid}"),"EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS")
    docs=tuple((p,d(f"document:{p}")) for p in PARTIES);receipt=d("reconsideration-receipt")
    routes=tuple((f,canonical_digest(("DISCLOSURE_ROUTE",f,FLOW_PARTIES[f],docs,receipt))) for f in FLOWS)
    reviewers=("synthetic:readiness-reviewer:maker","synthetic:preflight-reviewer:checker","synthetic:reconsideration-reviewer:independent")
    a=s.anchor_source("synthetic:disclosure-anchor:evidence",receipt,d("challenge-set"),sha256(rb).hexdigest(),sha256(mb).hexdigest(),lessons,rules,docs,routes,12,True,reviewers)
    source_docs=dict(docs);route_map=dict(routes)
    for flow in FLOWS:
        source,counterparty=FLOW_PARTIES[flow]
        for topic in TOPICS:
            disclosure=canonical_digest(("DISCLOSURE_DOCUMENT",source,source_docs[source],flow,topic,route_map[flow],a.challenge_set_digest))
            rebuttal=canonical_digest(("REBUTTAL_DOCUMENT",counterparty,flow,topic,disclosure,route_map[flow]))
            correction=canonical_digest(("CORRECTION_DRAFT",source,counterparty,flow,topic,disclosure,rebuttal,route_map[flow]))
            s.add_case(f"synthetic:correction-case:{flow}:{topic}",flow,topic,disclosure,rebuttal,correction,f"synthetic:discloser:{source}",f"synthetic:rebutter:{counterparty}")
    s.finalize("synthetic:correction-readiness-packet:evidence","synthetic:packet-compiler:new")
    evidence=s.evidence()
    if not evidence["complete_correction_readiness_evidence"] or evidence["registered_control_count"]!=400:raise ValueError("incomplete evidence")
    evidence.update({"lesson_registry_read_and_applied":True,"lesson_registry_version":registry["version"],"lesson_registry_digest":sha256(rb).hexdigest(),"remediation_manifest_digest":sha256(mb).hexdigest(),"remediation_guidance_digest":sha256(gb).hexdigest(),"lesson_validation_mode":"STABLE_MANIFEST_NO_GIT_HISTORY_DEPENDENCY"})
    out=ROOT/"build/synthetic-evidence-disclosure-rebuttal-correction-readiness-evidence.json";out.parent.mkdir(exist_ok=True);content=json.dumps(evidence,ensure_ascii=False,indent=2,sort_keys=True)+"\n";out.write_text(content,encoding="utf-8");checksum=sha256(content.encode()).hexdigest();out.with_suffix(".json.sha256").write_text(checksum+"\n",encoding="utf-8");print("synthetic evidence disclosure rebuttal correction readiness #5901-#6300: PASS",checksum)
if __name__=="__main__":main()
