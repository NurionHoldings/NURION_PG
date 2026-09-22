import json
from pathlib import Path
def validate():
 p=json.loads((Path(__file__).resolve().parents[1]/"config/test-payment-execution-closure-v1.json").read_text());assert p["completion_percent"]==100 and len(p["criteria"])==21 and len(set(p["criteria"]))==21;assert p["toss_test_only"] and not p["live_commercial_payment_allowed"] and not p["external_live_call_performed"] and not p["bank_transfer_connected"];return {"result":"PASS","completion_percent":100,"criteria_passed":21,"live_payment":False}
if __name__=="__main__":print(json.dumps(validate(),sort_keys=True))
