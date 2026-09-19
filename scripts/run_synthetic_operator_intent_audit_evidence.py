from datetime import UTC,datetime,timedelta
from hashlib import sha256
import json
from pathlib import Path
from nurion_pg.synthetic_operator_intent_audit import OperatorIntentAuditCheckpoint
ROOT=Path(__file__).resolve().parents[1]
h=lambda x:sha256(x).hexdigest()
def main():
 n=datetime(2026,9,18,tzinfo=UTC);r=OperatorIntentAuditCheckpoint(h(b"receipt-report"))
 r.admit("SYNTHETIC_OPERATOR_INTENT_RECEIPTS_COMPLETED",(426,440),False,"synthetic:key:441");r.bind_scope("NURION_PG","READ_ONLY_INDEPENDENT_AUDIT","synthetic:key:442",1);r.freshness(n,n+timedelta(days=7),n+timedelta(hours=1),"synthetic:key:443",2);r.roles("synthetic:operator:1","synthetic:auditor:1","synthetic:key:444",3);r.vocabulary(("ACKNOWLEDGE_ONLY","CLOSE_CONSIDERATION","DEFER_CONSIDERATION","REQUEST_REVISION"),"synthetic:key:445",4);r.authority(("ACTIVATION_FALSE","AUTHORITY_FALSE","EXECUTION_FALSE","POLICY_CHANGE_FALSE"),"synthetic:key:446",5);r.integrity(h(b"receipt"),True,"synthetic:key:447",6);r.replay(True,True,"synthetic:key:448",7);r.supersession(True,False,"synthetic:key:449",8);r.privacy(False,False,"synthetic:key:450",9);r.effects((),"synthetic:key:451",10);r.findings((),"synthetic:key:452",11);r.attest("synthetic:auditor:1",("AUTHORITY","INTEGRITY","PRIVACY","REPLAY","SCOPE"),"synthetic:key:453",12);r.seal(None,"synthetic:key:454",13);r.complete(("NO_AUTHORIZATION","NO_DEPLOYMENT","NO_MONEY_MOVEMENT","READ_ONLY","SYNTHETIC_ONLY"),"synthetic:key:455",14)
 e=r.evidence();o=ROOT/"build/synthetic-operator-intent-audit-evidence.json";o.parent.mkdir(exist_ok=True);x=json.dumps(e,sort_keys=True,indent=2)+"\n";o.write_text(x);d=sha256(x.encode()).hexdigest();o.with_suffix(".json.sha256").write_text(d+"\n");print("synthetic operator intent audit: PASS",d)
if __name__=="__main__":main()
