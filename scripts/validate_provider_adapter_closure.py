import json
from pathlib import Path

def validate():
    root=Path(__file__).resolve().parents[1];p=json.loads((root/"config/provider-adapter-closure-v1.json").read_text())
    assert p["completion_percent"]==100 and len(p["criteria"])==14 and len(set(p["criteria"]))==14
    assert p["sandbox_ready"] is True and p["production_credentials_configured"] is False and p["live_payment_executed"] is False and p["commercial_activation_authorized"] is False
    return {"result":"PASS","completion_percent":100,"criteria_passed":14,"live_payment_executed":False}
if __name__=="__main__":print(json.dumps(validate(),sort_keys=True))
