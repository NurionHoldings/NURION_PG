from hashlib import sha256
import json
from pathlib import Path

from nurion_pg.arkaon.governance import canonical_digest
from nurion_pg.synthetic_review_challenge_reconsideration_lineage import (
    APPLIED_LESSONS,APPLIED_RULES,CONTROL_ASPECTS,FLOWS,FLOW_SOURCE_PARTY,GROUNDS,NEGATIVE,PARTIES,WORKSTREAMS,
    SyntheticReviewChallengeReconsiderationLineage,
)
from validate_arkaon_lesson_registry import MANIFEST,declared_remediations,discovered_negative_tests,validate

ROOT=Path(__file__).resolve().parents[1];REGISTRY=ROOT/"config/arkaon-lesson-registry-v1.json";GUIDANCE=ROOT/"config/arkaon-audit-recurrence-prevention.json"
def d(x):return sha256(x.encode()).hexdigest()
def main():
    rb=REGISTRY.read_bytes();mb=MANIFEST.read_bytes();gb=GUIDANCE.read_bytes();registry=json.loads(rb);manifest=json.loads(mb);guidance=json.loads(gb)
    lessons=validate(registry,declared_remediations(manifest),discovered_negative_tests());rules=tuple(x["id"] for x in guidance["rules"])
    if lessons!=APPLIED_LESSONS or rules!=APPLIED_RULES or guidance["completion_gate"]["fail_closed"] is not True:raise ValueError("exact stable learned protections required")
    s=SyntheticReviewChallengeReconsiderationLineage()
    for start,end,name in WORKSTREAMS:
        for cid in range(start,end+1):
            aspect=CONTROL_ASPECTS[(cid-5501)%25];s.add_control(cid,name,aspect,f"synthetic:challenge-requirement:{(cid-5501)//25:02}",d(f"fixture:{cid}"),"EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS")
    docs=tuple((p,d(f"document:{p}")) for p in PARTIES);packet=d("preflight-packet")
    routes=tuple((f,canonical_digest(("CHALLENGE_ROUTE",f,docs,packet))) for f in FLOWS)
    s.anchor_source("synthetic:challenge-anchor:evidence",packet,d("item-set"),sha256(rb).hexdigest(),sha256(mb).hexdigest(),lessons,rules,docs,routes,11,True,"synthetic:readiness-reviewer:maker","synthetic:preflight-reviewer:checker")
    source_docs=dict(docs);route_map=dict(routes)
    for flow in FLOWS:
        for ground in GROUNDS:
            party=FLOW_SOURCE_PARTY[flow];document=canonical_digest(("CHALLENGE_DOCUMENT",party,source_docs[party],flow,ground,route_map[flow]))
            s.add_challenge(f"synthetic:challenge:{flow}:{ground}",flow,ground,document,f"synthetic:challenger:{party}")
    s.finalize("synthetic:reconsideration-receipt:evidence","synthetic:reconsideration-reviewer:independent")
    evidence=s.evidence()
    if not evidence["complete_reconsideration_evidence"] or evidence["registered_control_count"]!=400:raise ValueError("incomplete evidence")
    evidence.update({"lesson_registry_read_and_applied":True,"lesson_registry_version":registry["version"],"lesson_registry_digest":sha256(rb).hexdigest(),"remediation_manifest_digest":sha256(mb).hexdigest(),"remediation_guidance_digest":sha256(gb).hexdigest(),"lesson_validation_mode":"STABLE_MANIFEST_NO_GIT_HISTORY_DEPENDENCY"})
    out=ROOT/"build/synthetic-review-challenge-reconsideration-lineage-evidence.json";out.parent.mkdir(exist_ok=True);content=json.dumps(evidence,ensure_ascii=False,indent=2,sort_keys=True)+"\n";out.write_text(content,encoding="utf-8");checksum=sha256(content.encode()).hexdigest();out.with_suffix(".json.sha256").write_text(checksum+"\n",encoding="utf-8");print("synthetic review challenge reconsideration lineage #5501-#5900: PASS",checksum)
if __name__=="__main__":main()
