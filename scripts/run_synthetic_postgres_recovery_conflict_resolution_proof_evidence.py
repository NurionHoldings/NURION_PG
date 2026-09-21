from hashlib import sha256
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/"src")]
from nurion_pg.synthetic_postgres_recovery_conflict_resolution_proof import *
from scripts.validate_arkaon_lesson_registry import REGISTRY,MANIFEST,declared_remediations,discovered_negative_tests,validate,validated_stage_chain_through,validated_stage_snapshot
def d(value):return sha256(value.encode()).hexdigest()
def main():
    rb=REGISTRY.read_bytes();mb=MANIFEST.read_bytes();live=validate(json.loads(rb),declared_remediations(json.loads(mb)),discovered_negative_tests());chain=validated_stage_chain_through(20300);lessons,rd=validated_stage_snapshot(live,APPLIED_LESSONS,"ARKAON-LESSONS-19901",(19901,20300));ledger=ConflictResolutionLedger();conflicts=(("c1",d("c1"),"reviewer:one"),("c2",d("c2"),"reviewer:two"));docket=ledger.add_docket("recommendation",d("recommendation"),conflicts,"resolution-key","author:resolution",d("resolution"));ledger.add_round(docket.docket_id,None,None,1,"reviewer:three","REVIEWED_HOLD",d("rationale"));evidence=ledger.evidence()
    if len(chain)!=20 or lessons!=APPLIED_LESSONS or evidence["docket_count"]!=1 or evidence["round_count"]!=1 or not evidence["held"] or evidence["production_database_writes"]:raise ValueError("incomplete conflict resolution evidence")
    evidence.update({"range":[19901,20300],"lesson_registry_digest":rd,"remediation_manifest_digest":sha256(mb).hexdigest(),"audit_remediation":"ETH-19901-AUDIT-001","continuous_evidence_stage_count":26,"postgresql_status":"SKIP_NO_PRECONFIGURED_TEST_DATABASE"});out=ROOT/"build/synthetic-postgres-recovery-conflict-resolution-proof-evidence.json";out.parent.mkdir(exist_ok=True);payload=json.dumps(evidence,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode();out.write_bytes(payload);digest=sha256(payload).hexdigest();out.with_suffix(out.suffix+".sha256").write_text(digest+"\n",encoding="utf-8");print(digest)
if __name__=="__main__":main()
