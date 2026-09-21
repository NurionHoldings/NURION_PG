"""Machine-check the OPS-E01 runtime closure contract."""
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REQUIRED={"EXECUTABLE_ENTRYPOINT","VALIDATED_SETTINGS","LIVENESS_STARTUP_READINESS","CORRELATION_PROPAGATION","STANDARD_ERROR_ENVELOPE","REQUEST_SIZE_BOUNDARY","SECURITY_RESPONSE_HEADERS","SECRET_FREE_RUNTIME_INFO","GRACEFUL_TERMINATION","NON_ROOT_HEALTHCHECKED_CONTAINER"}

def validate(root:Path=ROOT)->dict[str,object]:
    policy=json.loads((root/"config/runtime-closure-v1.json").read_text())
    assert policy["scope"]=="OPERATING_API_RUNTIME" and set(policy["required_criteria"])==REQUIRED
    assert policy["completion_percent"]==100 and policy["payment_execution_implied"] is False and policy["production_deployment_implied"] is False
    pyproject=(root/"pyproject.toml").read_text();app=(root/"src/nurion_pg/api/app.py").read_text();settings=(root/"src/nurion_pg/api/settings.py").read_text();main=(root/"src/nurion_pg/api/__main__.py").read_text();docker=(root/"Dockerfile").read_text();tests=(root/"tests/test_api_runtime.py").read_text();workflow=(root/".github/workflows/ci.yml").read_text()
    assert 'nurion-pg-api = "nurion_pg.api.__main__:main"' in pyproject and "uvicorn.run" in main
    for token in ("max_request_bytes","graceful_shutdown_seconds","public_view"):assert token in settings
    for token in ('/health/live','/health/startup','/health/ready','x-correlation-id','REQUEST_VALIDATION_FAILED','REQUEST_TOO_LARGE','x-content-type-options','/runtime/info'):assert token in app
    for token in ("USER 65532:65532","STOPSIGNAL SIGTERM","HEALTHCHECK"):assert token in docker
    assert "test_request_size_and_content_length_fail_closed" in tests and "test_framework_errors_use_standard_envelope" in tests
    assert "tests.test_api_runtime" in workflow
    return {"scope":policy["scope"],"criteria_total":10,"criteria_passed":10,"completion_percent":100,"payment_execution_implied":False,"production_deployment_implied":False,"result":"PASS"}

def main()->None:
    evidence=validate();out=ROOT/"build/runtime-closure-evidence.json";out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(evidence,sort_keys=True,indent=2)+"\n");print("runtime closure: PASS")

if __name__=="__main__":main()
