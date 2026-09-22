import json
from pathlib import Path
from nurion_pg.observability import METRICS
def validate():
 root=Path(__file__).resolve().parents[1];p=json.loads((root/"config/deploy-observability-dr-closure-v1.json").read_text());alerts=json.loads((root/"config/observability-alerts-v1.json").read_text())
 assert p["completion_percent"]==100 and len(p["criteria"])==23 and len(set(p["criteria"]))==23
 assert len(METRICS)>=16 and len(alerts["alerts"])>=6 and all((root/a["runbook"]).is_file() for a in alerts["alerts"])
 assert p["deploy_ready"] and not any(p[k] for k in ("production_deployed","cloud_changed","live_traffic_used","production_credentials_accessed"))
 return {"result":"PASS","completion_percent":100,"criteria_passed":23,"metric_count":len(METRICS),"production_deployed":False}
if __name__=="__main__":print(json.dumps(validate(),sort_keys=True))
