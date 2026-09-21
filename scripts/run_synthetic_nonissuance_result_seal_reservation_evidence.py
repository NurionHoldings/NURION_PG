from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/"src"))
from nurion_pg.synthetic_nonissuance_result_seal_reservation import *
from scripts.validate_arkaon_lesson_registry import REGISTRY,MANIFEST,declared_remediations,discovered_negative_tests,validate,validated_stage_chain_through,validated_stage_snapshot
from tests.test_synthetic_preissuance_dual_signature_input_contract import completed as prior_completed
POLICY=ROOT/"config/arkaon-audit-recurrence-prevention.json"
def d(v):return sha256(v.encode()).hexdigest()
def main():
    rb=REGISTRY.read_bytes();mb=MANIFEST.read_bytes();rules=tuple(x["id"] for x in json.loads(POLICY.read_bytes())["rules"]);live=validate(json.loads(rb),declared_remediations(json.loads(mb)),discovered_negative_tests());chain=validated_stage_chain_through(15900);lessons,registry_digest=validated_stage_snapshot(live,APPLIED_LESSONS,"ARKAON-LESSONS-15501",(15501,15900));source=prior_completed()[0]
    s=SyntheticNonissuanceResultSealReservation()
    for cid in range(15501,15901):
        w,a=s._expected(cid);s.add_control(cid,w,a,f"synthetic:reservation-requirement:{(cid-15501)//25:02}",d(f"fixture:{cid}"),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    manifest_digest=sha256(mb).hexdigest();s.anchor(source,mapping_digest(STAGE_MAPPING),registry_digest,manifest_digest,lessons,rules,source._snapshot.digest,35,True)
    for i,(flow,kind,intent) in enumerate(source._packets):s.reserve(f"synthetic:nonissuance-reservation:{flow}:{kind}:{intent.lower()}",f"synthetic:reservation-idempotency-key:key-{i}",f"synthetic:reservation-token:token-{i}",flow,kind,intent,f"synthetic:reservation-owner:owner-{i}",f"synthetic:reservation-validator:validator-{i}")
    s.finalize("synthetic:reservation-docket:final","synthetic:reservation-docket-compiler:final-c","synthetic:reservation-final-validator:final-v");e=s.evidence();zero=("cryptographic_verifications","signature_values_created","key_material_reads","credential_reads","reservation_commits","approval_receipts_issued","ledger_writes","database_writes","fixture_materializations","probe_executions","observation_values","external_calls","external_pg_calls","card_network_calls","payment_approvals","deployments")
    if not e["complete_nonissuance_result_seal_reservation_evidence"] or e["registered_control_count"]!=400 or e["reservation_count"]!=40 or e["seal_input_count"]!=40 or e["recovery_path_count"]!=64 or any(e[k] for k in zero) or len(chain)!=9:raise ValueError("incomplete or over-authoritative reservation evidence")
    e.update({"lesson_registry_digest":registry_digest,"remediation_manifest_digest":manifest_digest,"audit_remediation":"ETH-15501-AUDIT-001","continuous_evidence_stage_count":15});out=ROOT/"build/synthetic-nonissuance-result-seal-reservation-evidence.json";out.parent.mkdir(exist_ok=True);payload=json.dumps(e,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode();out.write_bytes(payload);digest=sha256(payload).hexdigest();out.with_suffix(out.suffix+".sha256").write_text(digest+"\n",encoding="utf-8");print(digest)
if __name__=="__main__":main()
