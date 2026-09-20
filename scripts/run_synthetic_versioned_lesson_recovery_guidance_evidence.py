from hashlib import sha256
import json
from pathlib import Path

from nurion_pg.synthetic_versioned_lesson_recovery_guidance import *
from run_synthetic_option_methodology_independent_challenge_evidence import option_service
from validate_arkaon_lesson_registry import MANIFEST,declared_remediations,discovered_negative_tests,validate,validated_stage_snapshot

ROOT=Path(__file__).resolve().parents[1];REGISTRY=ROOT/"config/arkaon-lesson-registry-v1.json";POLICY=ROOT/"config/arkaon-audit-recurrence-prevention.json"
def d(v):return sha256(v.encode()).hexdigest()
def main():
    rb=REGISTRY.read_bytes();mb=MANIFEST.read_bytes();manifest_digest=sha256(mb).hexdigest();rules=tuple(x["id"] for x in json.loads(POLICY.read_bytes())["rules"]);live=validate(json.loads(rb),declared_remediations(json.loads(mb)),discovered_negative_tests());prior_lessons,prior_registry_digest=validated_stage_snapshot(live,PRIOR_LESSONS,"ARKAON-LESSONS-12301",(9901,12700));lessons,registry_digest=validated_stage_snapshot(live,APPLIED_LESSONS,"ARKAON-LESSONS-12701",(12701,13100))
    if lessons!=APPLIED_LESSONS or rules!=APPLIED_RULES:raise ValueError("continuous stage snapshot lessons and rules required")
    prior=option_service(prior_lessons,rules,prior_registry_digest,manifest_digest);s=SyntheticVersionedLessonRecoveryGuidance()
    for cid in range(12701,13101):
        w,a=s._expected(cid);s.add_control(cid,w,a,f"synthetic:recovery-guidance-requirement:{(cid-12701)//25:02}",d(f"fixture:{cid}"),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    previous_snapshot=source_stage_snapshot_digest("ARKAON-LESSONS-12301",(9901,12700),prior_lessons,rules,prior_registry_digest,manifest_digest,prior._docket.digest)
    s.anchor(prior,registry_digest,manifest_digest,lessons,rules,prior_registry_digest,previous_snapshot,28,True)
    for i,key in enumerate(CASE_KEYS):
        args=(f"synthetic:versioned-recovery-guidance:{key[0]}:{key[1]}",*key)
        if prior._challenges[key].methodology_cards:s.add_guidance(*args,f"synthetic:recovery-guidance-reviewer:guide-reviewer-{i}",f"synthetic:recovery-guidance-verifier:guide-verifier-{i}")
        else:s.add_guidance(*args)
    s.finalize("synthetic:recovery-guidance-docket:evidence","synthetic:recovery-docket-compiler:final-compiler","synthetic:recovery-docket-validator:final-validator");e=s.evidence()
    if not e["complete_versioned_recovery_guidance_evidence"] or e["registered_control_count"]!=400 or e["recovery_alternative_count"]!=32 or e["human_judgment_hold_count"]!=16 or e["judgment_authority"] is not False:raise ValueError("incomplete or over-authoritative evidence")
    e.update({"lesson_registry_digest":registry_digest,"remediation_manifest_digest":manifest_digest,"audit_remediation":"ETH-12701-AUDIT-001"});out=ROOT/"build/synthetic-versioned-lesson-recovery-guidance-evidence.json";out.parent.mkdir(exist_ok=True);payload=json.dumps(e,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode();out.write_bytes(payload);digest=sha256(payload).hexdigest();out.with_suffix(out.suffix+".sha256").write_text(digest+"\n",encoding="utf-8");print(digest)
if __name__=="__main__":main()
