from hashlib import sha256
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/"src")]
from nurion_pg.synthetic_postgres_recovery_supersession_proof import *
from scripts.validate_arkaon_lesson_registry import REGISTRY,MANIFEST,declared_remediations,discovered_negative_tests,validate,validated_stage_chain_through,validated_stage_snapshot
from tests.test_synthetic_postgres_recovery_disposition_proof import complete as prior_complete
def d(v):return sha256(v.encode()).hexdigest()
def main():
    rb=REGISTRY.read_bytes();mb=MANIFEST.read_bytes();rules=tuple(x["id"] for x in json.loads((ROOT/"config/arkaon-audit-recurrence-prevention.json").read_bytes())["rules"]);live=validate(json.loads(rb),declared_remediations(json.loads(mb)),discovered_negative_tests());chain=validated_stage_chain_through(19100);lessons,rd=validated_stage_snapshot(live,APPLIED_LESSONS,"ARKAON-LESSONS-18701",(18701,19100));source=prior_complete();proof=SyntheticPostgresRecoverySupersessionProof()
    for cid in range(18701,19101):
        w,a=proof._expected(cid);proof.add_control(cid,w,a,f"synthetic:postgres-recovery-supersession-proof-requirement:{(cid-18701)//20:02}",d(str(cid)),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    proof.anchor(source,mapping_digest(STAGE_MAPPING),rd,sha256(mb).hexdigest(),lessons,rules,source._snapshot.digest,23,True);proof.finalize("synthetic:postgres-recovery-supersession-proof-docket:final");e=proof.evidence()
    if not e["complete_postgres_recovery_supersession_contract_evidence"] or e["registered_control_count"]!=400 or e["postgresql_recovery_supersession_proof_status"]!="SKIP_NO_PRECONFIGURED_TEST_DATABASE" or e["production_database_writes"] or len(chain)!=17:raise ValueError("incomplete or over-authoritative recovery supersession evidence")
    e.update({"lesson_registry_digest":rd,"remediation_manifest_digest":sha256(mb).hexdigest(),"audit_remediation":"ETH-18701-AUDIT-001","continuous_evidence_stage_count":23});out=ROOT/"build/synthetic-postgres-recovery-supersession-proof-evidence.json";out.parent.mkdir(exist_ok=True);payload=json.dumps(e,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode();out.write_bytes(payload);digest=sha256(payload).hexdigest();out.with_suffix(out.suffix+".sha256").write_text(digest+"\n",encoding="utf-8");print(digest)
if __name__=="__main__":main()
