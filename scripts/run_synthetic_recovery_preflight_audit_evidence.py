from hashlib import sha256
import json
from pathlib import Path

from nurion_pg.synthetic_recovery_preflight_audit import *
from run_synthetic_versioned_lesson_recovery_guidance_evidence import recovery_service
from validate_arkaon_lesson_registry import MANIFEST,REGISTRY,STAGE_LESSON_SNAPSHOTS,declared_remediations,discovered_negative_tests,validate,validated_stage_chain,validated_stage_snapshot

ROOT=Path(__file__).resolve().parents[1];POLICY=ROOT/"config/arkaon-audit-recurrence-prevention.json"
def d(v):return sha256(v.encode()).hexdigest()
def main():
    rb=REGISTRY.read_bytes();mb=MANIFEST.read_bytes();manifest_digest=sha256(mb).hexdigest();rules=tuple(x["id"] for x in json.loads(POLICY.read_bytes())["rules"]);live=validate(json.loads(rb),declared_remediations(json.loads(mb)),discovered_negative_tests());chain=validated_stage_chain();lessons,registry_digest=validated_stage_snapshot(live,APPLIED_LESSONS,"ARKAON-LESSONS-13101",(13101,13500));source,_=recovery_service(live,rules,manifest_digest)
    if lessons!=APPLIED_LESSONS or rules!=APPLIED_RULES:raise ValueError("continuous automated stage lessons and rules required")
    s=SyntheticRecoveryPreflightAudit()
    for cid in range(13101,13501):
        w,a=s._expected(cid);s.add_control(cid,w,a,f"synthetic:recovery-preflight-requirement:{(cid-13101)//25:02}",d(f"fixture:{cid}"),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    mapping=tuple((sid,bounds) for sid,bounds,_ in chain if bounds[1]<=13500);s.anchor(source,mapping_digest(mapping),registry_digest,manifest_digest,lessons,rules,source._snapshot.digest,29,True)
    for i,key in enumerate(CASE_KEYS):
        args=(f"synthetic:recovery-preflight-audit:{key[0]}:{key[1]}",*key)
        if source._guidance[key].alternatives:s.add_audit(*args,f"synthetic:recovery-preflight-auditor:a-{i}",f"synthetic:recovery-preflight-verifier:v-{i}")
        else:s.add_audit(*args)
    s.finalize("synthetic:preflight-docket:evidence","synthetic:preflight-docket-compiler:compiler-final","synthetic:preflight-docket-validator:validator-final");e=s.evidence()
    if not e["complete_recovery_preflight_audit_evidence"] or e["registered_control_count"]!=400 or e["diagnostic_option_count"]!=32 or e["undetermined_cause_count"]!=16 or e["human_judgment_hold_count"]!=16 or e["judgment_authority"] is not False:raise ValueError("incomplete or over-authoritative preflight evidence")
    e.update({"lesson_registry_digest":registry_digest,"remediation_manifest_digest":manifest_digest,"audit_remediation":"ETH-13101-AUDIT-001"});out=ROOT/"build/synthetic-recovery-preflight-audit-evidence.json";out.parent.mkdir(exist_ok=True);payload=json.dumps(e,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode();out.write_bytes(payload);digest=sha256(payload).hexdigest();out.with_suffix(out.suffix+".sha256").write_text(digest+"\n",encoding="utf-8");print(digest)
if __name__=="__main__":main()
