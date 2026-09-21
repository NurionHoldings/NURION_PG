from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/"src"))
from nurion_pg.synthetic_postgres_ephemeral_repository_proof import *
from scripts.validate_arkaon_lesson_registry import REGISTRY,MANIFEST,declared_remediations,discovered_negative_tests,validate,validated_stage_chain_through,validated_stage_snapshot
from tests.test_synthetic_postgres_reservation_ledger_contract import completed as prior_completed

def d(v):return sha256(v.encode()).hexdigest()
def main():
    rb=REGISTRY.read_bytes();mb=MANIFEST.read_bytes();rules=tuple(x["id"] for x in json.loads((ROOT/"config/arkaon-audit-recurrence-prevention.json").read_bytes())["rules"]);live=validate(json.loads(rb),declared_remediations(json.loads(mb)),discovered_negative_tests());chain=validated_stage_chain_through(16700);lessons,registry_digest=validated_stage_snapshot(live,APPLIED_LESSONS,"ARKAON-LESSONS-16301",(16301,16700));source=prior_completed()[0];s=SyntheticPostgresEphemeralRepositoryProof()
    for cid in range(16301,16701):
        w,a=s._expected(cid);s.add_control(cid,w,a,f"synthetic:postgres-ephemeral-proof-requirement:{(cid-16301)//25:02}",d(str(cid)),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    s.anchor(source,mapping_digest(STAGE_MAPPING),registry_digest,sha256(mb).hexdigest(),lessons,rules,source._snapshot.digest,17,True);s.plan_fixture();s.finalize("synthetic:postgres-ephemeral-proof-docket:final");e=s.evidence()
    if not e["complete_postgres_ephemeral_repository_proof_contract_evidence"] or e["registered_control_count"]!=400 or e["postgresql_proof_status"]!="SKIP_NO_PRECONFIGURED_TEST_DATABASE" or e["postgresql_integration_skip_count"]!=1 or e["production_database_writes"] or len(chain)!=11:raise ValueError("incomplete or over-authoritative ephemeral PostgreSQL contract evidence")
    e.update({"lesson_registry_digest":registry_digest,"remediation_manifest_digest":sha256(mb).hexdigest(),"audit_remediation":"ETH-16301-AUDIT-001","continuous_evidence_stage_count":17,"fixture_digest":s._fixture.digest});out=ROOT/"build/synthetic-postgres-ephemeral-repository-proof-evidence.json";out.parent.mkdir(exist_ok=True);payload=json.dumps(e,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode();out.write_bytes(payload);digest=sha256(payload).hexdigest();out.with_suffix(out.suffix+".sha256").write_text(digest+"\n",encoding="utf-8");print(digest)
if __name__=="__main__":main()
