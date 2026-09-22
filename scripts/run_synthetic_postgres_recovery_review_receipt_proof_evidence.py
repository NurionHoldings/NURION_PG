from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/"src")]
from nurion_pg.synthetic_postgres_recovery_review_receipt_proof import *
from scripts.validate_arkaon_lesson_registry import REGISTRY,MANIFEST,declared_remediations,discovered_negative_tests,validate,validated_stage_chain_through,validated_stage_snapshot
from tests.test_synthetic_postgres_recovery_supersession_proof import complete as prior_complete

def d(value): return sha256(value.encode()).hexdigest()

def main():
    registry_bytes=REGISTRY.read_bytes();manifest_bytes=MANIFEST.read_bytes()
    rules=tuple(row["id"] for row in json.loads((ROOT/"config/arkaon-audit-recurrence-prevention.json").read_bytes())["rules"])
    live=validate(json.loads(registry_bytes),declared_remediations(json.loads(manifest_bytes)),discovered_negative_tests())
    chain=validated_stage_chain_through(19500)
    lessons,registry_digest=validated_stage_snapshot(live,APPLIED_LESSONS,"ARKAON-LESSONS-19101",(19101,19500))
    source=prior_complete();proof=SyntheticPostgresRecoveryReviewReceiptProof()
    for control_id in range(19101,19501):
        workstream,aspect=proof._expected(control_id)
        proof.add_control(control_id,workstream,aspect,f"synthetic:postgres-recovery-review-receipt-proof-requirement:{(control_id-19101)//20:02}",d(str(control_id)),"EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS")
    proof.anchor(source,mapping_digest(STAGE_MAPPING),registry_digest,sha256(manifest_bytes).hexdigest(),lessons,rules,source._snapshot.digest,24,True)
    proof.finalize("synthetic:postgres-recovery-review-receipt-proof-docket:final");evidence=proof.evidence()
    if not evidence["complete_postgres_recovery_review_receipt_contract_evidence"] or evidence["registered_control_count"]!=400 or evidence["postgresql_recovery_review_receipt_proof_status"]!="SKIP_NO_PRECONFIGURED_TEST_DATABASE" or evidence["production_database_writes"] or len(chain)!=18:
        raise ValueError("incomplete or over-authoritative recovery review receipt evidence")
    evidence.update({"lesson_registry_digest":registry_digest,"remediation_manifest_digest":sha256(manifest_bytes).hexdigest(),"audit_remediation":"ETH-19101-AUDIT-001","continuous_evidence_stage_count":24})
    out=ROOT/"build/synthetic-postgres-recovery-review-receipt-proof-evidence.json";out.parent.mkdir(exist_ok=True)
    payload=json.dumps(evidence,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode();out.write_bytes(payload)
    digest=sha256(payload).hexdigest();out.with_suffix(out.suffix+".sha256").write_text(digest+"\n",encoding="utf-8");print(digest)

if __name__=="__main__":main()
