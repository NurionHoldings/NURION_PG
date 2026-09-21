from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/"src"))
from nurion_pg.synthetic_approval_receipt_schema_contract import *
from scripts.validate_arkaon_lesson_registry import REGISTRY,MANIFEST,declared_remediations,discovered_negative_tests,validate,validated_stage_chain_through,validated_stage_snapshot
from tests.test_synthetic_approval_intent_envelope_gate import completed as prior_completed
POLICY=ROOT/"config/arkaon-audit-recurrence-prevention.json"
def d(v):return sha256(v.encode()).hexdigest()
def main():
    rb=REGISTRY.read_bytes();mb=MANIFEST.read_bytes();rules=tuple(x["id"] for x in json.loads(POLICY.read_bytes())["rules"]);live=validate(json.loads(rb),declared_remediations(json.loads(mb)),discovered_negative_tests());validated_stage_chain_through(15100);lessons,registry_digest=validated_stage_snapshot(live,APPLIED_LESSONS,"ARKAON-LESSONS-14701",(14701,15100));source=prior_completed()[0]
    s=SyntheticApprovalReceiptSchemaContract()
    for cid in range(14701,15101):
        w,a=s._expected(cid);s.add_control(cid,w,a,f"synthetic:receipt-schema-requirement:{(cid-14701)//25:02}",d(f"fixture:{cid}"),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    manifest_digest=sha256(mb).hexdigest();s.anchor(source,mapping_digest(STAGE_MAPPING),registry_digest,manifest_digest,lessons,rules,source._snapshot.digest,33,True)
    for i,(flow,kind,intent) in enumerate(source._envelopes):s.add_schema(f"synthetic:approval-receipt-schema:{flow}:{kind}:{intent.lower()}",f"synthetic:approval-receipt-idempotency-key:key-{i}",flow,kind,intent,f"synthetic:approval-receipt-issuer-role:issuer-{i}",f"synthetic:approval-receipt-verifier-role:verifier-{i}")
    s.finalize("synthetic:receipt-schema-docket:final","synthetic:receipt-schema-docket-compiler:final-c","synthetic:receipt-schema-docket-validator:final-v");e=s.evidence()
    if not e["complete_approval_receipt_schema_contract_evidence"] or e["registered_control_count"]!=400 or e["receipt_schema_count"]!=40 or e["idempotency_key_contract_count"]!=40 or e["recovery_path_count"]!=64 or e["approval_receipts_issued"] or e["fixture_materializations"] or e["probe_executions"] or e["observation_values"] or e["judgment_authority"] is not False:raise ValueError("incomplete or over-authoritative receipt schema evidence")
    e.update({"lesson_registry_digest":registry_digest,"remediation_manifest_digest":manifest_digest,"audit_remediation":"ETH-14701-AUDIT-001","continuous_evidence_stage_count":13});out=ROOT/"build/synthetic-approval-receipt-schema-contract-evidence.json";out.parent.mkdir(exist_ok=True);payload=json.dumps(e,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode();out.write_bytes(payload);digest=sha256(payload).hexdigest();out.with_suffix(out.suffix+".sha256").write_text(digest+"\n",encoding="utf-8");print(digest)
if __name__=="__main__":main()
