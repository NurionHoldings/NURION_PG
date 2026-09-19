from hashlib import sha256
import json
from pathlib import Path

from nurion_pg.arkaon.governance import canonical_digest
from nurion_pg.synthetic_operator_review_preflight_docket import (
    APPLIED_LESSONS, APPLIED_RULES, COMMON_OPERATIONS, COMMON_TOKEN_CLASSES,
    CONTROL_ASPECTS, FLOWS, NEGATIVE, PARTIES, SCENARIOS, WORKSTREAMS,
    SyntheticOperatorReviewPreflightDocket,
)
from validate_arkaon_lesson_registry import MANIFEST, declared_remediations, discovered_negative_tests, validate

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/"config/arkaon-lesson-registry-v1.json"
GUIDANCE=ROOT/"config/arkaon-audit-recurrence-prevention.json"
def d(x):return sha256(x.encode()).hexdigest()

def main():
    rb=REGISTRY.read_bytes();mb=MANIFEST.read_bytes();gb=GUIDANCE.read_bytes()
    registry=json.loads(rb);manifest=json.loads(mb);guidance=json.loads(gb)
    lessons=validate(registry,declared_remediations(manifest),discovered_negative_tests())
    rules=tuple(x["id"] for x in guidance["rules"])
    if lessons!=APPLIED_LESSONS or rules!=APPLIED_RULES or guidance["completion_gate"]["fail_closed"] is not True:
        raise ValueError("exact stable learned protections required")
    s=SyntheticOperatorReviewPreflightDocket()
    for start,end,name in WORKSTREAMS:
        for cid in range(start,end+1):
            aspect=CONTROL_ASPECTS[(cid-5101)%25]
            s.add_control(cid,name,aspect,f"synthetic:preflight-requirement:{(cid-5101)//25:02}",d(f"fixture:{cid}"),"EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS")
    profiles=tuple((p,d(f"profile:{p}")) for p in PARTIES);ops=tuple((p,COMMON_OPERATIONS) for p in PARTIES);tokens=tuple((p,COMMON_TOKEN_CLASSES) for p in PARTIES)
    bindings=tuple((p,canonical_digest(("PARTY_CAPABILITY",p,dict(profiles)[p],dict(ops)[p],dict(tokens)[p]))) for p in PARTIES)
    s.anchor_readiness("synthetic:preflight-anchor:evidence",d("readiness-receipt"),d("plan-set"),d("result-set"),sha256(rb).hexdigest(),sha256(mb).hexdigest(),lessons,rules,profiles,bindings,ops,tokens,COMMON_OPERATIONS,COMMON_TOKEN_CLASSES,9,True,"synthetic:readiness-reviewer:maker")
    for flow in FLOWS:
        for scenario in SCENARIOS:s.add_review_item(f"synthetic:preflight-item:{flow}:{scenario}",flow,scenario,COMMON_OPERATIONS,COMMON_TOKEN_CLASSES)
    s.finalize("synthetic:preflight-packet:evidence","synthetic:preflight-reviewer:checker")
    evidence=s.evidence()
    if not evidence["complete_preflight_evidence"] or evidence["registered_control_count"]!=400:raise ValueError("incomplete preflight evidence")
    evidence.update({"lesson_registry_read_and_applied":True,"lesson_registry_version":registry["version"],
        "lesson_registry_digest":sha256(rb).hexdigest(),"remediation_manifest_digest":sha256(mb).hexdigest(),
        "remediation_guidance_digest":sha256(gb).hexdigest(),"lesson_validation_mode":"STABLE_MANIFEST_NO_GIT_HISTORY_DEPENDENCY"})
    out=ROOT/"build/synthetic-operator-review-preflight-docket-evidence.json";out.parent.mkdir(exist_ok=True)
    content=json.dumps(evidence,ensure_ascii=False,indent=2,sort_keys=True)+"\n";out.write_text(content,encoding="utf-8")
    checksum=sha256(content.encode()).hexdigest();out.with_suffix(".json.sha256").write_text(checksum+"\n",encoding="utf-8")
    print("synthetic operator review preflight docket #5101-#5500: PASS",checksum)
if __name__=="__main__":main()
