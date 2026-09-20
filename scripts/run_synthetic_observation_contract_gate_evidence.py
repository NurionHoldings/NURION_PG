import json,sys
from hashlib import sha256
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"src"));sys.path.insert(0,str(ROOT/"scripts"));sys.path.insert(0,str(ROOT))
from nurion_pg.synthetic_observation_contract_gate import *
from tests.test_synthetic_recovery_preflight_audit import completed as prior_completed
from validate_arkaon_lesson_registry import MANIFEST,REGISTRY,declared_remediations,discovered_negative_tests,validate,validated_stage_chain,validated_stage_snapshot
POLICY=ROOT/"config/arkaon-audit-recurrence-prevention.json"
def d(v):return sha256(v.encode()).hexdigest()
def main():
    rb=REGISTRY.read_bytes();mb=MANIFEST.read_bytes();manifest_digest=sha256(mb).hexdigest();rules=tuple(x["id"] for x in json.loads(POLICY.read_bytes())["rules"]);live=validate(json.loads(rb),declared_remediations(json.loads(mb)),discovered_negative_tests());validated_stage_chain();lessons,registry_digest=validated_stage_snapshot(live,APPLIED_LESSONS,"ARKAON-LESSONS-13501",(13501,13900));source=prior_completed()[0]
    s=SyntheticObservationContractGate()
    for cid in range(13501,13901):
        w,a=s._expected(cid);s.add_control(cid,w,a,f"synthetic:observation-contract-requirement:{(cid-13501)//25:02}",d(f"fixture:{cid}"),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    s.anchor(source,mapping_digest(STAGE_MAPPING),registry_digest,manifest_digest,lessons,rules,source._snapshot.digest,30,True)
    for i,key in enumerate(CASE_KEYS):
        args=(f"synthetic:observation-contract:{key[0]}:{key[1]}",*key)
        if source._audits[key].pending_human_judgment:s.add_contract(*args,f"synthetic:observation-contract-author:oca-{i}",f"synthetic:observation-contract-verifier:ocv-{i}")
        else:s.add_contract(*args)
    s.finalize("synthetic:observation-docket:final","synthetic:observation-docket-compiler:occ-final","synthetic:observation-docket-validator:ocv-final");e=s.evidence()
    if not e["complete_observation_contract_gate_evidence"] or e["registered_control_count"]!=400 or e["content_free_fixture_count"]!=16 or e["recovery_path_count"]!=32 or e["not_run_count"]!=16 or e["probe_executions"]!=0 or e["judgment_authority"] is not False:raise ValueError("incomplete or over-authoritative observation contract evidence")
    e.update({"lesson_registry_digest":registry_digest,"remediation_manifest_digest":manifest_digest,"audit_remediation":"ETH-13501-AUDIT-001"});out=ROOT/"build/synthetic-observation-contract-gate-evidence.json";out.parent.mkdir(exist_ok=True);payload=json.dumps(e,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode();out.write_bytes(payload);digest=sha256(payload).hexdigest();out.with_suffix(out.suffix+".sha256").write_text(digest+"\n",encoding="utf-8");print(digest)
if __name__=="__main__":main()
