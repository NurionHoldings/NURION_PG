from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/"src"))
from nurion_pg.synthetic_approval_intent_envelope_gate import *
from scripts.validate_arkaon_lesson_registry import REGISTRY,MANIFEST,declared_remediations,discovered_negative_tests,validate,validated_stage_chain_through,validated_stage_snapshot
from tests.test_synthetic_observation_readiness_manifest import completed as prior_completed
POLICY=ROOT/"config/arkaon-audit-recurrence-prevention.json"
def d(v):return sha256(v.encode()).hexdigest()
def main():
    rb=REGISTRY.read_bytes();mb=MANIFEST.read_bytes();rules=tuple(x["id"] for x in json.loads(POLICY.read_bytes())["rules"]);live=validate(json.loads(rb),declared_remediations(json.loads(mb)),discovered_negative_tests());validated_stage_chain_through(14700);lessons,registry_digest=validated_stage_snapshot(live,APPLIED_LESSONS,"ARKAON-LESSONS-14301",(14301,14700));source=prior_completed()[0]
    s=SyntheticApprovalIntentEnvelopeGate()
    for cid in range(14301,14701):
        w,a=s._expected(cid);s.add_control(cid,w,a,f"synthetic:intent-requirement:{(cid-14301)//25:02}",d(f"fixture:{cid}"),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    manifest_digest=sha256(mb).hexdigest();s.anchor(source,mapping_digest(STAGE_MAPPING),registry_digest,manifest_digest,lessons,rules,source._snapshot.digest,32,True)
    for i,key in enumerate(CASE_KEYS):
        routed=source._plans[key].pending_human_judgment
        for j,intent in enumerate(("MATERIALIZATION","EXECUTION")):
            args=(f"synthetic:approval-intent-envelope:{key[0]}:{key[1]}:{intent.lower()}",*key,intent)
            if routed:s.add_envelope(*args,f"synthetic:approval-intent-actor:a-{i}-{j}",f"synthetic:approval-intent-counter-actor:c-{i}-{j}")
            else:s.add_envelope(*args)
    s.finalize("synthetic:intent-docket:final","synthetic:intent-docket-compiler:final-c","synthetic:intent-docket-validator:final-v");e=s.evidence()
    if not e["complete_approval_intent_envelope_gate_evidence"] or e["registered_control_count"]!=400 or e["envelope_count"]!=40 or e["recovery_path_count"]!=64 or e["approval_receipts_issued"] or e["fixture_materializations"] or e["probe_executions"] or e["judgment_authority"] is not False:raise ValueError("incomplete or over-authoritative intent evidence")
    e.update({"lesson_registry_digest":registry_digest,"remediation_manifest_digest":manifest_digest,"audit_remediation":"ETH-14301-AUDIT-001","continuous_evidence_stage_count":12});out=ROOT/"build/synthetic-approval-intent-envelope-gate-evidence.json";out.parent.mkdir(exist_ok=True);payload=json.dumps(e,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode();out.write_bytes(payload);digest=sha256(payload).hexdigest();out.with_suffix(out.suffix+".sha256").write_text(digest+"\n",encoding="utf-8");print(digest)
if __name__=="__main__":main()
