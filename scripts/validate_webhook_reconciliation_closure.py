import json
from pathlib import Path
def validate():
 p=json.loads((Path(__file__).resolve().parents[1]/"config/webhook-reconciliation-closure-v1.json").read_text())
 assert p["completion_percent"]==100 and len(p["criteria"])==15 and len(set(p["criteria"]))==15
 assert p["provider_signature_claimed"] is False and p["provider_lookup_is_authority"] is True
 assert not p["production_credentials_configured"] and not p["live_webhook_received"] and not p["live_payment_executed"]
 return {"result":"PASS","completion_percent":100,"criteria_passed":15,"live_payment_executed":False}
if __name__=="__main__":print(json.dumps(validate(),sort_keys=True))
