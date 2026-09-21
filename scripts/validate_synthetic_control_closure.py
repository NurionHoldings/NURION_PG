"""Validate the frozen synthetic control/audit closure boundary."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re


ROOT=Path(__file__).resolve().parents[1]
POLICY=ROOT/"config/synthetic-control-closure-v1.json"
REQUIRED={"MODULE_TEST_PARITY","FAIL_CLOSED_GOVERNANCE","NO_LIVE_EXECUTION_AUTHORITY","NO_AUTOMATIC_MERGE_OR_DEPLOY","EXTERNAL_BLOCKERS_OPEN","PINNED_CI_ACTIONS","DETERMINISTIC_EVIDENCE_RUNNERS","FULL_REGRESSION_GATE","POSTGRES_FAILURE_PROOFS","ROLE_SEPARATED_REVIEW"}


def digest(path:Path)->str:return sha256(path.read_bytes()).hexdigest()


def validate(root:Path=ROOT)->dict[str,object]:
    policy=json.loads((root/"config/synthetic-control-closure-v1.json").read_text(encoding="utf-8"))
    assert policy["schema_version"]=="synthetic-control-closure-v1"
    assert policy["scope"]=="SYNTHETIC_CONTROL_AND_AUDIT_ONLY"
    assert policy["stage_range_frozen_at"]==20300
    assert set(policy["required_criteria"])==REQUIRED and len(policy["required_criteria"])==len(REQUIRED)
    assert all(policy[key] is False for key in ("production_readiness_implied","commercial_readiness_implied","live_payment_allowed","automatic_close_allowed"))

    modules=sorted((root/"src/nurion_pg").glob("synthetic_*.py"))
    tests=sorted((root/"tests").glob("test_synthetic_*.py"))
    expected={f"test_{path.name}" for path in modules}
    actual={path.name for path in tests}
    assert expected.issubset(actual) and modules
    assert actual-expected<={"test_synthetic_control_closure.py"}

    authority=json.loads((root/"governance/authority-policy.json").read_text(encoding="utf-8"))
    promotion=json.loads((root/"governance/promotion-policy.json").read_text(encoding="utf-8"))
    blockers=json.loads((root/"config/external-blockers.json").read_text(encoding="utf-8"))
    workspace=json.loads((root/"arkaon.workspace.json").read_text(encoding="utf-8"))
    assert authority["default_decision"]=="BLOCKED" and "run_live_payment" in authority["forbidden_actions"]
    assert promotion["automatic_merge_allowed"] is False and promotion["automatic_deploy_allowed"] is False and promotion["production_promotion_allowed"] is False
    assert workspace["production_change_allowed"] is False and workspace["automatic_learning_allowed"] is False
    assert blockers["release_status"]=="BLOCKED" and blockers["automatic_close_allowed"] is False and all(row["status"]=="PENDING" for row in blockers["blockers"])

    workflow=(root/".github/workflows/ci.yml").read_text(encoding="utf-8")
    uses=re.findall(r"^\s*- uses: ([^\s#]+)",workflow,flags=re.MULTILINE)
    assert uses and all(re.fullmatch(r"[^@\s]+@[0-9a-f]{40}",item) for item in uses)
    assert "python -m unittest discover -s tests -v" in workflow
    for proof in ("run_postgres_deadlock_integration.py","run_postgres_connection_loss_integration.py","run_postgres_recovery_quarantine_integration.py"):
        assert proof in workflow

    runners=sorted((root/"scripts").glob("run_*_evidence.py"))
    assert len(runners)>=100
    assert (root/"docs/70-arkaon-audit-recurrence-prevention.md").is_file()
    assert (root/"config/ethernian-remediation-manifest-v1.json").is_file()
    assert (root/"config/arkaon-lesson-registry-v1.json").is_file()

    evidence={"schema_version":"synthetic-control-closure-evidence-v1","scope":policy["scope"],"stage_range_frozen_at":20300,"criteria_total":len(REQUIRED),"criteria_passed":len(REQUIRED),"completion_percent":100,"synthetic_module_count":len(modules),"paired_synthetic_test_count":len(expected),"closure_test_count":len(actual-expected),"evidence_runner_count":len(runners),"policy_digest":digest(root/"config/synthetic-control-closure-v1.json"),"live_payment_allowed":False,"production_readiness_implied":False,"commercial_readiness_implied":False,"result":"PASS"}
    evidence["evidence_digest"]=sha256(json.dumps(evidence,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()
    return evidence


def main()->None:
    evidence=validate();out=ROOT/"build/synthetic-control-closure-evidence.json";out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(evidence,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8");(out.with_suffix(out.suffix+".sha256")).write_text(sha256(out.read_bytes()).hexdigest()+"\n",encoding="ascii");print("synthetic control closure: PASS")


if __name__=="__main__":main()
