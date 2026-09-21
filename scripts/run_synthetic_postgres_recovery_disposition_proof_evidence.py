from hashlib import sha256
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/"src")]
from nurion_pg.synthetic_postgres_recovery_disposition_proof import *
from scripts.validate_arkaon_lesson_registry import REGISTRY,MANIFEST,declared_remediations,discovered_negative_tests,validate,validated_stage_chain_through,validated_stage_snapshot
from tests.test_synthetic_postgres_recovery_quarantine_proof import complete as prior_complete
def d(v):return sha256(v.encode()).hexdigest()
def main():
    rb=REGISTRY.read_bytes();mb=MANIFEST.read_bytes();rules=tuple(x["id"] for x in json.loads((ROOT/"config/arkaon-audit-recurrence-prevention.json").read_bytes())["rules"]);live=validate(json.loads(rb),declared_remediations(json.loads(mb)),discovered_negative_tests());chain=validated_stage_chain_through(18700);lessons,rd=validated_stage_snapshot(live,APPLIED_LESSONS,"ARKAON-LESSONS-18301",(18301,18700));source=prior_complete();proof=SyntheticPostgresRecoveryDispositionProof()
    for cid in range(18301,18701):
        w,a=proof._expected(cid);proof.add_control(cid,w,a,f"synthetic:postgres-recovery-disposition-proof-requirement:{(cid-18301)//20:02}",d(str(cid)),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    proof.anchor(source,mapping_digest(STAGE_MAPPING),rd,sha256(mb).hexdigest(),lessons,rules,source._snapshot.digest,22,True);proof.finalize("synthetic:postgres-recovery-disposition-proof-docket:final");e=proof.evidence()
    if not e["complete_postgres_recovery_disposition_contract_evidence"] or e["registered_control_count"]!=400 or e["postgresql_recovery_disposition_proof_status"]!="SKIP_NO_PRECONFIGURED_TEST_DATABASE" or e["production_database_writes"] or len(chain)!=16:raise ValueError("incomplete or over-authoritative recovery disposition evidence")
    e.update({"lesson_registry_digest":rd,"remediation_manifest_digest":sha256(mb).hexdigest(),"audit_remediation":"ETH-18301-AUDIT-001","continuous_evidence_stage_count":22});out=ROOT/"build/synthetic-postgres-recovery-disposition-proof-evidence.json";out.parent.mkdir(exist_ok=True);payload=json.dumps(e,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode();out.write_bytes(payload);digest=sha256(payload).hexdigest();out.with_suffix(out.suffix+".sha256").write_text(digest+"\n",encoding="utf-8");print(digest)
if __name__=="__main__":main()
