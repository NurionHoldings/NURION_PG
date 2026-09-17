from __future__ import annotations
import json
from hashlib import sha256
from nurion_pg.arkaon_benchmark_receipt_repository_parity import FOUNDRY_PACKAGE_HASH,FOUNDRY_PATTERN_STATUS,PARITY_STATE,verify_repository_contract
from nurion_pg.arkaon_release_evidence_manifest_draft import draft_release_evidence_manifest
from nurion_pg.arkaon_role_separated_release_benchmark import BenchmarkRole,RoleResult,record_role_separated_benchmark
from run_operator_decision_intake_evidence import NOW,ROOT,read_json
def h(v:bytes)->str:return sha256(v).hexdigest()
def main():
    policy=read_json("config/arkaon-benchmark-receipt-repository-parity-policy.json")
    if (policy["maximum_state"]!=PARITY_STATE or policy["foundry_package_hash"]!=FOUNDRY_PACKAGE_HASH
        or policy["foundry_pattern_status"]!=FOUNDRY_PATTERN_STATUS or any(v is not False for k,v in policy.items() if k.endswith("_allowed"))):
        raise SystemExit("repository parity policy drift")
    manifest=draft_release_evidence_manifest(artifact_digest=h(b"a"),test_digest=h(b"t"),evidence_digest=h(b"e"),policy_digest=h(b"p"),drafted_at=NOW)
    results=tuple(RoleResult(role,f"synthetic:{role.value.lower()}:parity",h(role.value.encode()),True) for role in BenchmarkRole);findings=h(b"findings")
    benchmark=record_role_separated_benchmark(manifest,results,attack_findings_digest=findings,judge_observed_attack_findings_digest=findings,recorded_at=NOW)
    report=verify_repository_contract(benchmark,idempotency_key="synthetic:repository-parity:evidence")
    if not report["adapter_outcomes_equal"] or not report["idempotent_retry_equal"]:raise SystemExit("repository parity failed")
    output=ROOT/"build/arkaon-benchmark-receipt-repository-parity-evidence.json";output.parent.mkdir(exist_ok=True);payload=json.dumps(report,sort_keys=True,indent=2)+"\n";output.write_text(payload)
    digest=sha256(payload.encode()).hexdigest();output.with_suffix(".json.sha256").write_text(digest+"\n");print(f"ARKAON benchmark receipt repository parity: PASS {digest}");return report
if __name__=="__main__":main()
