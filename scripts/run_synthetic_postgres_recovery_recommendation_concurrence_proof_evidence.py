from hashlib import sha256
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/"src")]
from nurion_pg.synthetic_postgres_recovery_recommendation_concurrence_proof import *
from scripts.validate_arkaon_lesson_registry import REGISTRY,MANIFEST,declared_remediations,discovered_negative_tests,validate,validated_stage_chain_through,validated_stage_snapshot
from tests.test_synthetic_postgres_recovery_review_receipt_proof import complete as prior_complete
def d(value):return sha256(value.encode()).hexdigest()
def main():
    rb=REGISTRY.read_bytes();mb=MANIFEST.read_bytes();rules=tuple(row["id"] for row in json.loads((ROOT/"config/arkaon-audit-recurrence-prevention.json").read_bytes())["rules"]);live=validate(json.loads(rb),declared_remediations(json.loads(mb)),discovered_negative_tests());chain=validated_stage_chain_through(19900);lessons,rd=validated_stage_snapshot(live,APPLIED_LESSONS,"ARKAON-LESSONS-19501",(19501,19900));source=prior_complete();proof=SyntheticPostgresRecoveryRecommendationConcurrenceProof()
    for cid in range(19501,19901):
        workstream,aspect=proof._expected(cid);proof.add_control(cid,workstream,aspect,f"synthetic:postgres-recovery-recommendation-concurrence-proof-requirement:{(cid-19501)//20:02}",d(str(cid)),"EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS")
    proof.anchor(source,mapping_digest(STAGE_MAPPING),rd,sha256(mb).hexdigest(),lessons,rules,source._snapshot.digest,25,True);proof.finalize("synthetic:postgres-recovery-recommendation-concurrence-proof-docket:final");evidence=proof.evidence()
    if not evidence["complete_postgres_recovery_recommendation_concurrence_contract_evidence"] or evidence["registered_control_count"]!=400 or evidence["postgresql_recovery_recommendation_concurrence_proof_status"]!="SKIP_NO_PRECONFIGURED_TEST_DATABASE" or evidence["production_database_writes"] or len(chain)!=19:raise ValueError("incomplete or over-authoritative recommendation concurrence evidence")
    evidence.update({"lesson_registry_digest":rd,"remediation_manifest_digest":sha256(mb).hexdigest(),"audit_remediation":"ETH-19501-AUDIT-001","continuous_evidence_stage_count":25});out=ROOT/"build/synthetic-postgres-recovery-recommendation-concurrence-proof-evidence.json";out.parent.mkdir(exist_ok=True);payload=json.dumps(evidence,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode();out.write_bytes(payload);digest=sha256(payload).hexdigest();out.with_suffix(out.suffix+".sha256").write_text(digest+"\n",encoding="utf-8");print(digest)
if __name__=="__main__":main()
