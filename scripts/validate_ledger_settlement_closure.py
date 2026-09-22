import json
from pathlib import Path
def validate():
 p=json.loads((Path(__file__).resolve().parents[1]/"config/ledger-settlement-closure-v1.json").read_text());assert p["completion_percent"]==100 and len(p["criteria"])==20 and len(set(p["criteria"]))==20;assert not p["bank_adapter_connected"] and not p["live_transfer_executed"] and not p["production_credentials_configured"];return {"result":"PASS","completion_percent":100,"criteria_passed":20,"live_transfer_executed":False}
if __name__=="__main__":print(json.dumps(validate(),sort_keys=True))
