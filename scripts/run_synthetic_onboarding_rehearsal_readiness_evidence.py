from hashlib import sha256
import json
from pathlib import Path

from nurion_pg.synthetic_onboarding_rehearsal_readiness import (
    APPLIED_LESSONS, COMMON_OPERATIONS, COMMON_TOKEN_CLASSES, CONTROL_ASPECTS,
    FLOWS, NEGATIVE, PARTIES, SCENARIOS, WORKSTREAMS,
    SyntheticOnboardingRehearsalReadiness,
)
from validate_arkaon_lesson_registry import (MANIFEST, declared_remediations,
                                             discovered_negative_tests, validate)

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/"config/arkaon-lesson-registry-v1.json"
GUIDANCE=ROOT/"config/arkaon-audit-recurrence-prevention.json"
def d(x): return sha256(x.encode()).hexdigest()

def validate_stable_lessons(registry, guidance, manifest):
    ids=validate(registry,declared_remediations(manifest),discovered_negative_tests())
    if ids != APPLIED_LESSONS: raise ValueError("exact stable lesson set required")
    rule_ids=tuple(x.get("id") for x in guidance.get("rules",[]))
    if rule_ids != tuple(f"ARP-{i:02}" for i in range(1,9)): raise ValueError("ARP-01..08 required")
    if guidance.get("completion_gate",{}).get("fail_closed") is not True: raise ValueError("fail closed guidance required")
    return ids

def main():
    registry_content=REGISTRY.read_bytes(); guidance_content=GUIDANCE.read_bytes(); manifest_content=MANIFEST.read_bytes()
    registry=json.loads(registry_content); guidance=json.loads(guidance_content); manifest=json.loads(manifest_content)
    lessons=validate_stable_lessons(registry,guidance,manifest)
    s=SyntheticOnboardingRehearsalReadiness()
    for start,end,name in WORKSTREAMS:
        for cid in range(start,end+1):
            aspect=CONTROL_ASPECTS[(cid-4701)%25]
            s.add_control(cid,name,aspect,f"synthetic:onboarding-requirement:{(cid-4701)//25:02}",d(f"fixture:{cid}"),"EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS")
    s.anchor_source("synthetic:onboarding-anchor:evidence",d("package-manifest"),d("acceptance-receipt"),sha256(registry_content).hexdigest(),lessons,tuple((p,d(f"profile:{p}")) for p in PARTIES),tuple((p,COMMON_OPERATIONS) for p in PARTIES),tuple((p,COMMON_TOKEN_CLASSES) for p in PARTIES),COMMON_OPERATIONS,COMMON_TOKEN_CLASSES,8,True,"synthetic:package-assembler:maker")
    for flow in FLOWS:
        for scenario in SCENARIOS:
            s.add_plan(f"synthetic:rehearsal-plan:{flow}:{scenario}",flow,scenario,COMMON_OPERATIONS,COMMON_TOKEN_CLASSES)
    s.run_rehearsal(); s.review("synthetic:readiness-receipt:evidence","synthetic:readiness-reviewer:checker")
    evidence=s.evidence(); assert evidence["capability_ready"] and evidence["registered_control_count"]==400
    evidence.update({"lesson_registry_read_and_applied":True,"lesson_registry_version":registry["version"],
                     "lesson_registry_digest":sha256(registry_content).hexdigest(),
                     "remediation_manifest_digest":sha256(manifest_content).hexdigest(),
                     "remediation_guidance_digest":sha256(guidance_content).hexdigest(),
                     "applied_lesson_ids":list(lessons),"applied_prevention_rule_ids":[f"ARP-{i:02}" for i in range(1,9)],
                     "lesson_validation_mode":"STABLE_MANIFEST_NO_GIT_HISTORY_DEPENDENCY"})
    out=ROOT/"build/synthetic-onboarding-rehearsal-readiness-evidence.json"; out.parent.mkdir(exist_ok=True)
    content=json.dumps(evidence,ensure_ascii=False,indent=2,sort_keys=True)+"\n"; out.write_text(content,encoding="utf-8")
    checksum=sha256(content.encode()).hexdigest(); out.with_suffix(".json.sha256").write_text(checksum+"\n",encoding="utf-8")
    print("synthetic onboarding rehearsal readiness #4701-#5100: PASS",checksum)

if __name__=="__main__": main()
