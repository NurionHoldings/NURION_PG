from __future__ import annotations
import json
from hashlib import sha256
from nurion_pg.arkaon_release_evidence_manifest_draft import draft_release_evidence_manifest
from nurion_pg.arkaon_role_separated_release_benchmark import BENCHMARK_STATE,FOUNDRY_PACKAGE_HASH,FOUNDRY_PATTERN_STATUS,BenchmarkOutcome,BenchmarkRole,RoleResult,evidence,record_role_separated_benchmark
from run_operator_decision_intake_evidence import NOW,ROOT,read_json
def h(v:bytes)->str:return sha256(v).hexdigest()
def main():
    policy=read_json("config/arkaon-role-separated-release-benchmark-policy.json")
    if (policy["maximum_state"]!=BENCHMARK_STATE or policy["foundry_package_hash"]!=FOUNDRY_PACKAGE_HASH
        or policy["foundry_pattern_status"]!=FOUNDRY_PATTERN_STATUS or any(v is not False for k,v in policy.items() if k.endswith("_allowed"))):
        raise SystemExit("role-separated benchmark policy drift")
    manifest=draft_release_evidence_manifest(artifact_digest=h(b"a"),test_digest=h(b"t"),evidence_digest=h(b"e"),policy_digest=h(b"p"),drafted_at=NOW)
    results=tuple(RoleResult(role,f"synthetic:{role.value.lower()}:evidence",h(role.value.encode()),True) for role in BenchmarkRole);findings=h(b"attack findings")
    item=record_role_separated_benchmark(manifest,results,attack_findings_digest=findings,judge_observed_attack_findings_digest=findings,recorded_at=NOW);report=evidence(item)
    if item.outcome is not BenchmarkOutcome.PASS or report["unique_actor_count"]!=4 or not report["attack_findings_visible_to_judge"]:raise SystemExit("role separation failed")
    output=ROOT/"build/arkaon-role-separated-release-benchmark-evidence.json";output.parent.mkdir(exist_ok=True);payload=json.dumps(report,sort_keys=True,indent=2)+"\n";output.write_text(payload)
    digest=sha256(payload.encode()).hexdigest();output.with_suffix(".json.sha256").write_text(digest+"\n");print(f"ARKAON role-separated release benchmark: PASS {digest}");return item
if __name__=="__main__":main()
