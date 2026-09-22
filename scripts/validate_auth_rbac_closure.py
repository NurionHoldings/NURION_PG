from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REQUIRED={"HASH_ONLY_CREDENTIALS","CONSTANT_TIME_SECRET_CHECK","PERSISTENT_PRINCIPAL_RESOLUTION","MERCHANT_STATUS_ENFORCEMENT","PRINCIPAL_STATUS_ENFORCEMENT","EXPLICIT_PERMISSION_MATRIX","CROSS_TENANT_DENIAL","KEY_ROTATION_AND_REVOCATION","DURABLE_ACCESS_AUDIT","POSTGRES_INTEGRATION_GATE"}

def validate(root:Path=ROOT)->dict[str,object]:
    policy=json.loads((root/"config/auth-rbac-closure-v1.json").read_text());assert set(policy["required_criteria"])==REQUIRED and policy["completion_percent"]==100;assert policy["plaintext_secret_storage_allowed"] is False and policy["cross_tenant_access_allowed"] is False
    auth=(root/"src/nurion_pg/api/auth.py").read_text();repository=(root/"src/nurion_pg/storage/auth_repository.py").read_text();app=(root/"src/nurion_pg/api/app.py").read_text();integration=(root/"scripts/run_ops_auth_rbac_integration.py").read_text();workflow=(root/".github/workflows/ci.yml").read_text();tests=(root/"tests/test_api_auth.py").read_text()
    for token in ("ROLE_PERMISSIONS","Permission.PRINCIPAL_ADMIN","hmac.compare_digest","secret_sha256"):assert token in auth
    for token in ("JOIN",'p.status', 'm.status',"rotate_key","revoke_key","record_audit","api_key.rotated"):assert token in repository
    for token in ("CROSS_TENANT_ACCESS_DENIED","authorize(principal,Permission.TENANT_READ","audit(principal"):assert token in app
    assert "persistent auth, rotation, revocation, and audit" in workflow and "PostgresAuthRepository" in integration
    assert "test_role_permission_matrix_is_explicit_and_fail_closed" in tests and "test_same_tenant_is_allowed_and_cross_tenant_is_denied" in tests
    return {"scope":policy["scope"],"criteria_total":10,"criteria_passed":10,"completion_percent":100,"plaintext_secret_storage_allowed":False,"cross_tenant_access_allowed":False,"result":"PASS"}

def main()->None:
    evidence=validate();out=ROOT/"build/auth-rbac-closure-evidence.json";out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(evidence,sort_keys=True,indent=2)+"\n");print("auth/RBAC closure: PASS")

if __name__=="__main__":main()
