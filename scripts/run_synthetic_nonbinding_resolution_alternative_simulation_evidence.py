from hashlib import sha256
import json
from pathlib import Path

from nurion_pg.arkaon.governance import canonical_digest
from nurion_pg.synthetic_nonbinding_resolution_alternative_simulation import (
    APPLIED_LESSONS,APPLIED_RULES,CONTROL_ASPECTS,DIMENSIONS,FLOWS,FLOW_PARTIES,NEGATIVE,PARTIES,WORKSTREAMS,
    SyntheticNonbindingResolutionAlternativeSimulation,
)
from validate_arkaon_lesson_registry import MANIFEST,declared_remediations,discovered_negative_tests,validate

ROOT=Path(__file__).resolve().parents[1];REGISTRY=ROOT/"config/arkaon-lesson-registry-v1.json";GUIDANCE=ROOT/"config/arkaon-audit-recurrence-prevention.json"
def d(x):return sha256(x.encode()).hexdigest()
def main():
    rb=REGISTRY.read_bytes();mb=MANIFEST.read_bytes();gb=GUIDANCE.read_bytes();registry=json.loads(rb);manifest=json.loads(mb);guidance=json.loads(gb)
    lessons=validate(registry,declared_remediations(manifest),discovered_negative_tests());rules=tuple(x["id"] for x in guidance["rules"])
    if lessons!=APPLIED_LESSONS or rules!=APPLIED_RULES or guidance["completion_gate"]["fail_closed"] is not True:raise ValueError("exact stable learned protections required")
    s=SyntheticNonbindingResolutionAlternativeSimulation()
    for start,end,name in WORKSTREAMS:
        for cid in range(start,end+1):
            aspect=CONTROL_ASPECTS[(cid-6701)%25];s.add_control(cid,name,aspect,f"synthetic:alternative-requirement:{(cid-6701)//25:02}",d(f"fixture:{cid}"),"EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS")
    docs=tuple((p,d(f"document:{p}")) for p in PARTIES);receipt=d("conflict-review-packet")
    routes=tuple((f,canonical_digest(("NONBINDING_ALTERNATIVE_ROUTE",f,FLOW_PARTIES[f],docs,receipt))) for f in FLOWS)
    reviewers=("synthetic:readiness-reviewer:maker","synthetic:preflight-reviewer:checker","synthetic:reconsideration-reviewer:independent")
    compilers=("synthetic:packet-compiler:antecedent","synthetic:packet-compiler:conflict")
    a=s.anchor_source("synthetic:alternative-anchor:evidence",receipt,d("conflict-case-set"),sha256(rb).hexdigest(),sha256(mb).hexdigest(),lessons,rules,docs,routes,13,True,reviewers,compilers)
    source_docs=dict(docs);route_map=dict(routes)
    for flow in FLOWS:
        source,counter=FLOW_PARTIES[flow]
        for dimension in DIMENSIONS:
            condition=canonical_digest(("ALTERNATIVE_CONDITION",source,source_docs[source],flow,dimension,route_map[flow],a.conflict_case_set_digest))
            impact=canonical_digest(("ALTERNATIVE_IMPACT",counter,flow,dimension,condition,route_map[flow]))
            risk=canonical_digest(("ALTERNATIVE_RESIDUAL_RISK",source,counter,flow,dimension,condition,impact,route_map[flow]))
            comparison=canonical_digest(("NONBINDING_COMPARISON",flow,dimension,condition,impact,risk,a.conflict_review_packet_digest))
            s.add_case(f"synthetic:alternative-case:{flow}:{dimension}",flow,dimension,condition,impact,risk,comparison,f"synthetic:alternative-simulator:{source}",f"synthetic:risk-evaluator:{counter}")
    s.finalize("synthetic:nonbinding-simulation-packet:evidence","synthetic:simulation-compiler:new")
    evidence=s.evidence()
    if not evidence["complete_nonbinding_simulation_evidence"] or evidence["registered_control_count"]!=400:raise ValueError("incomplete evidence")
    evidence.update({"lesson_registry_read_and_applied":True,"lesson_registry_version":registry["version"],"lesson_registry_digest":sha256(rb).hexdigest(),"remediation_manifest_digest":sha256(mb).hexdigest(),"remediation_guidance_digest":sha256(gb).hexdigest(),"lesson_validation_mode":"STABLE_MANIFEST_NO_GIT_HISTORY_DEPENDENCY"})
    out=ROOT/"build/synthetic-nonbinding-resolution-alternative-simulation-evidence.json";out.parent.mkdir(exist_ok=True);content=json.dumps(evidence,ensure_ascii=False,indent=2,sort_keys=True)+"\n";out.write_text(content,encoding="utf-8");checksum=sha256(content.encode()).hexdigest();out.with_suffix(".json.sha256").write_text(checksum+"\n",encoding="utf-8");print("synthetic nonbinding resolution alternative simulation #6701-#7100: PASS",checksum)
if __name__=="__main__":main()
