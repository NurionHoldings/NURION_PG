from datetime import UTC,datetime,timedelta
from hashlib import sha256
import json
from pathlib import Path
from nurion_pg.synthetic_delivery_backpressure import SyntheticDeliveryQueue
ROOT=Path(__file__).resolve().parents[1];h=lambda x:sha256(x).hexdigest()
def main():
 n=datetime(2026,9,18,tzinfo=UTC);q=SyntheticDeliveryQueue(10);a=q.enqueue("synthetic:packet:1",h(b"one"),n,n+timedelta(hours=1));a=q.warn(a.packet_id,a.version,"STALE_PACKET",n);a=q.hold(a.packet_id,a.version,n);a=q.clear_warning(a.packet_id,a.version,n);a=q.verify_resume(a.packet_id,a.version,"synthetic:verifier:1",h(b"resume-receipt"),n);q.transition(a.packet_id,a.version,"READY",n);b=q.enqueue("synthetic:packet:2",h(b"two"),n,n+timedelta(hours=1));q.transition(b.packet_id,b.version,"EXPIRED",n+timedelta(hours=2))
 e=q.evidence();assert e["event_chain_valid"] and e["history_chain_valid"];assert e["event_count"]==8 and e["history_count"]==8;assert not any(e[k] for k in ("automatic_approval_allowed","external_delivery_used","external_io_used","production_credentials_accessed","money_movement_allowed","merge_allowed","deployment_allowed"));o=ROOT/"build/synthetic-delivery-backpressure-evidence.json";o.parent.mkdir(exist_ok=True);x=json.dumps(e,sort_keys=True,indent=2)+"\n";o.write_text(x);d=sha256(x.encode()).hexdigest();o.with_suffix(".json.sha256").write_text(d+"\n");print("synthetic delivery backpressure #701-#900: PASS",d)
if __name__=="__main__":main()
