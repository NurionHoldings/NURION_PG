from __future__ import annotations
import json
from hashlib import sha256
from nurion_pg.arkaon_release_evidence_manifest_draft import FOUNDRY_COMMIT,FOUNDRY_PACKAGE_HASH,FOUNDRY_PATTERN_STATUS,MANIFEST_DRAFT_STATE,draft_release_evidence_manifest,evidence
from run_operator_decision_intake_evidence import NOW,ROOT,read_json
def main():
    policy=read_json("config/arkaon-release-evidence-manifest-draft-policy.json")
    if (policy["maximum_state"]!=MANIFEST_DRAFT_STATE or policy["foundry_commit"]!=FOUNDRY_COMMIT
        or policy["foundry_package_hash"]!=FOUNDRY_PACKAGE_HASH or policy["foundry_pattern_status"]!=FOUNDRY_PATTERN_STATUS
        or any(v is not False for k,v in policy.items() if k.endswith("_allowed"))):raise SystemExit("ARKAON release evidence manifest policy drift")
    item=draft_release_evidence_manifest(artifact_digest=sha256(b"synthetic-pg-artifact").hexdigest(),test_digest=sha256(b"synthetic-pg-tests").hexdigest(),
        evidence_digest=sha256(b"synthetic-pg-evidence").hexdigest(),policy_digest=sha256(b"synthetic-pg-policy").hexdigest(),drafted_at=NOW);report=evidence(item)
    if any(report[k] is not False for k in report if k.endswith("_present") or k.endswith("_allowed") or k.endswith("_executed") or k.endswith("_used") or k=="deployable"):raise SystemExit("ARKAON release evidence manifest boundary failed")
    output=ROOT/"build/arkaon-release-evidence-manifest-draft-evidence.json";output.parent.mkdir(exist_ok=True);payload=json.dumps(report,sort_keys=True,indent=2)+"\n";output.write_text(payload)
    digest=sha256(payload.encode()).hexdigest();output.with_suffix(".json.sha256").write_text(digest+"\n");print(f"ARKAON release evidence manifest draft: PASS {digest}");return item
if __name__=="__main__":main()
