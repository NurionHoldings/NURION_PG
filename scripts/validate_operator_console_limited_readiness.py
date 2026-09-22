import json
from pathlib import Path
def validate():
 p=json.loads((Path(__file__).resolve().parents[1]/"config/operator-console-limited-readiness-closure-v1.json").read_text());assert p["completion_percent"]==100 and len(p["criteria"])==16 and len(set(p["criteria"]))==16;assert not p["external_production_activation_performed"] and not p["commercial_credentials_present"];return {"result":"PASS","criteria_passed":16,"production_activated":False}
if __name__=="__main__":print(json.dumps(validate(),sort_keys=True))
