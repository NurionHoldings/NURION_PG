from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/"src"))
from nurion_pg.synthetic_postgres_reservation_ledger_contract import *
from scripts.validate_arkaon_lesson_registry import REGISTRY,MANIFEST,declared_remediations,discovered_negative_tests,validate,validated_stage_chain_through,validated_stage_snapshot
from tests.test_synthetic_nonissuance_result_seal_reservation import completed as prior_completed
POLICY=ROOT/"config/arkaon-audit-recurrence-prevention.json"
def d(v):return sha256(v.encode()).hexdigest()
def main():
    rb=REGISTRY.read_bytes();mb=MANIFEST.read_bytes();rules=tuple(x["id"] for x in json.loads(POLICY.read_bytes())["rules"]);live=validate(json.loads(rb),declared_remediations(json.loads(mb)),discovered_negative_tests());chain=validated_stage_chain_through(16300);lessons,registry_digest=validated_stage_snapshot(live,APPLIED_LESSONS,"ARKAON-LESSONS-15901",(15901,16300));source=prior_completed()[0]
    s=SyntheticPostgresReservationLedgerContract()
    for cid in range(15901,16301):
        w,a=s._expected(cid);s.add_control(cid,w,a,f"synthetic:postgres-ledger-requirement:{(cid-15901)//25:02}",d(f"fixture:{cid}"),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    manifest_digest=sha256(mb).hexdigest();s.anchor(source,mapping_digest(STAGE_MAPPING),registry_digest,manifest_digest,lessons,rules,source._snapshot.digest,36,True);s.define_schema()
    for flow,kind,intent in source._reservations:s.plan_row(f"synthetic:postgres-ledger-row-plan:{flow}:{kind}:{intent.lower()}",flow,kind,intent)
    s.define_transaction();s.finalize("synthetic:postgres-ledger-plan-docket:final","synthetic:ledger-plan-compiler:final-c","synthetic:ledger-plan-validator:final-v");e=s.evidence();zero=("database_connections","database_url_reads","credential_reads","database_writes","ledger_writes","reservation_commits","approval_receipts_issued","external_calls","external_pg_calls","card_network_calls","payment_approvals","deployments")
    if not e["complete_postgres_reservation_ledger_contract_evidence"] or e["registered_control_count"]!=400 or e["row_plan_count"]!=40 or e["recovery_path_count"]!=64 or e["postgresql_proof_claimed"] or e["sqlite_used_as_postgresql_proof"] or any(e[k] for k in zero) or len(chain)!=10:raise ValueError("incomplete or over-authoritative PostgreSQL ledger-plan evidence")
    e.update({"lesson_registry_digest":registry_digest,"remediation_manifest_digest":manifest_digest,"audit_remediation":"ETH-15901-AUDIT-001","continuous_evidence_stage_count":16,"ddl_digest":canonical_digest(s._ddl)});out=ROOT/"build/synthetic-postgres-reservation-ledger-contract-evidence.json";out.parent.mkdir(exist_ok=True);payload=json.dumps(e,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode();out.write_bytes(payload);digest=sha256(payload).hexdigest();out.with_suffix(out.suffix+".sha256").write_text(digest+"\n",encoding="utf-8");print(digest)
if __name__=="__main__":main()
