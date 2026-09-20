from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/"src"))
from nurion_pg.synthetic_observation_readiness_manifest import *
from scripts.validate_arkaon_lesson_registry import REGISTRY,MANIFEST,declared_remediations,discovered_negative_tests,validate,validated_stage_chain,validated_stage_snapshot
from tests.test_synthetic_observation_contract_gate import completed as prior_completed
POLICY=ROOT/"config/arkaon-audit-recurrence-prevention.json"
def d(v):return sha256(v.encode()).hexdigest()
def main():
    rb=REGISTRY.read_bytes();mb=MANIFEST.read_bytes();rules=tuple(x["id"] for x in json.loads(POLICY.read_bytes())["rules"]);live=validate(json.loads(rb),declared_remediations(json.loads(mb)),discovered_negative_tests());chain=validated_stage_chain();lessons,registry_digest=validated_stage_snapshot(live,APPLIED_LESSONS,"ARKAON-LESSONS-13901",(13901,14300));source=prior_completed()[0]
    if len(chain)!=5 or chain[-1][0]!="ARKAON-LESSONS-13901":raise ValueError("five-stage snapshot chain required")
    s=SyntheticObservationReadinessManifest()
    for cid in range(13901,14301):
        w,a=s._expected(cid);s.add_control(cid,w,a,f"synthetic:readiness-requirement:{(cid-13901)//25:02}",d(f"fixture:{cid}"),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    manifest_digest=sha256(mb).hexdigest();s.anchor(source,mapping_digest(STAGE_MAPPING),registry_digest,manifest_digest,lessons,rules,source._snapshot.digest,31,True)
    for i,key in enumerate(CASE_KEYS):
        args=(f"synthetic:readiness-plan:{key[0]}:{key[1]}",*key)
        if source._contracts[key].pending_human_judgment:s.add_plan(*args,f"synthetic:readiness-planner:rp-{i}",f"synthetic:readiness-challenger:rc-{i}")
        else:s.add_plan(*args)
    s.finalize("synthetic:readiness-docket:final","synthetic:readiness-docket-compiler:rdc-final","synthetic:readiness-docket-validator:rdv-final");e=s.evidence()
    if not e["complete_observation_readiness_manifest_evidence"] or e["registered_control_count"]!=400 or e["bound_manifest_count"]!=16 or e["recovery_path_count"]!=32 or e["fixture_materializations"] or e["probe_executions"] or e["judgment_authority"] is not False:raise ValueError("incomplete or over-authoritative readiness evidence")
    e.update({"lesson_registry_digest":registry_digest,"remediation_manifest_digest":manifest_digest,"audit_remediation":"ETH-13901-AUDIT-001","continuous_evidence_stage_count":11});out=ROOT/"build/synthetic-observation-readiness-manifest-evidence.json";out.parent.mkdir(exist_ok=True);payload=json.dumps(e,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode();out.write_bytes(payload);digest=sha256(payload).hexdigest();out.with_suffix(out.suffix+".sha256").write_text(digest+"\n",encoding="utf-8");print(digest)
if __name__=="__main__":main()
