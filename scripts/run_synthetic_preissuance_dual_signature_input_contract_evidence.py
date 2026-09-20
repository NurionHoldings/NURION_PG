from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/"src"))
from nurion_pg.synthetic_preissuance_dual_signature_input_contract import *
from scripts.validate_arkaon_lesson_registry import REGISTRY,MANIFEST,declared_remediations,discovered_negative_tests,validate,validated_stage_chain_through,validated_stage_snapshot
from tests.test_synthetic_approval_receipt_schema_contract import completed as prior_completed
POLICY=ROOT/"config/arkaon-audit-recurrence-prevention.json"
def d(v):return sha256(v.encode()).hexdigest()
def main():
    rb=REGISTRY.read_bytes();mb=MANIFEST.read_bytes();rules=tuple(x["id"] for x in json.loads(POLICY.read_bytes())["rules"]);live=validate(json.loads(rb),declared_remediations(json.loads(mb)),discovered_negative_tests());chain=validated_stage_chain_through(15500);lessons,registry_digest=validated_stage_snapshot(live,APPLIED_LESSONS,"ARKAON-LESSONS-15101",(15101,15500));source=prior_completed()[0]
    s=SyntheticPreissuanceDualSignatureInputContract()
    for cid in range(15101,15501):
        w,a=s._expected(cid);s.add_control(cid,w,a,f"synthetic:preissuance-input-requirement:{(cid-15101)//25:02}",d(f"fixture:{cid}"),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    manifest_digest=sha256(mb).hexdigest();s.anchor(source,mapping_digest(STAGE_MAPPING),registry_digest,manifest_digest,lessons,rules,source._snapshot.digest,34,True)
    for i,(flow,kind,intent) in enumerate(source._schemas):s.add_packet(f"synthetic:preissuance-validation-packet:{flow}:{kind}:{intent.lower()}",f"synthetic:preissuance-packet-idempotency-key:key-{i}",flow,kind,intent,f"synthetic:preissuance-issuer:preissuer-{i}",f"synthetic:preissuance-verifier:preverifier-{i}",f"synthetic:issuer-challenge:i-{i}",f"synthetic:verifier-challenge:v-{i}",f"synthetic:issuer-audience:i-{i}",f"synthetic:verifier-audience:v-{i}",f"synthetic:issuer-purpose:i-{i}",f"synthetic:verifier-purpose:v-{i}","synthetic:signature-policy-version:v1")
    s.finalize("synthetic:preissuance-docket:final","synthetic:preissuance-docket-compiler:final-c","synthetic:preissuance-docket-validator:final-v");e=s.evidence()
    zero=("signature_values_created","signature_verifications","key_material_reads","credential_reads","approval_receipts_issued","ledger_writes","fixture_materializations","probe_executions","observation_values","external_calls","external_pg_calls","card_network_calls","payment_approvals","deployments")
    if not e["complete_preissuance_dual_signature_input_contract_evidence"] or e["registered_control_count"]!=400 or e["validation_packet_count"]!=40 or e["dual_signature_input_count"]!=80 or e["recovery_path_count"]!=64 or any(e[k] for k in zero) or len(chain)!=8:raise ValueError("incomplete or over-authoritative preissuance evidence")
    e.update({"lesson_registry_digest":registry_digest,"remediation_manifest_digest":manifest_digest,"audit_remediation":"ETH-15101-AUDIT-001","continuous_evidence_stage_count":14});out=ROOT/"build/synthetic-preissuance-dual-signature-input-contract-evidence.json";out.parent.mkdir(exist_ok=True);payload=json.dumps(e,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode();out.write_bytes(payload);digest=sha256(payload).hexdigest();out.with_suffix(out.suffix+".sha256").write_text(digest+"\n",encoding="utf-8");print(digest)
if __name__=="__main__":main()
