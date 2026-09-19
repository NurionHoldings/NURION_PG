from datetime import UTC,datetime,timedelta
from hashlib import sha256
import json
from pathlib import Path
from nurion_pg.synthetic_operator_intent_receipts import OperatorIntentReceipts
ROOT=Path(__file__).resolve().parents[1];h=lambda x:sha256(x).hexdigest()
def main():
 n=datetime(2026,9,18,tzinfo=UTC);r=OperatorIntentReceipts(h(b"packet"),h(b"policy"));r.admit("SYNTHETIC_SHADOW_READINESS_REVIEW_COMPLETED","SUBMIT_FOR_OPERATOR_REVIEW",("NONE",),"synthetic:operator:1","synthetic:key:426");r.bind_scope("NURION_PG",(381,425),"READ_ONLY_CONSIDERATION","synthetic:key:427",1);r.validity(n,n+timedelta(days=7),n+timedelta(hours=1),"synthetic:key:428",2);r.actor("synthetic:operator:1","synthetic:operator:1","synthetic:key:429",3);r.intent("ACKNOWLEDGE_ONLY","synthetic:key:430",4);r.prerequisites(("DIGESTS","NON_AUTHORITY","SAFETY","SCOPE"),"synthetic:key:431",5);r.reviewer("synthetic:operator:1","synthetic:reviewer:1","synthetic:key:432",6);r.nonce("synthetic:nonce:abcdefghijklmnop","synthetic:key:433",7);r.canonicalize(("code","operator","packet_digest","scope_digest"),"synthetic:key:434",8);r.review("synthetic:reviewer:1",("IDENTITY","NONCE","SCOPE","SAFETY"),"synthetic:key:435",9);r.receipt("synthetic:receipt:1","synthetic:key:436",10);r.ledger(1,None,"synthetic:key:437",11);r.supersession(None,"INITIAL","synthetic:key:438",12);r.seal(None,"synthetic:key:439",13);r.complete(("INTENT_NOT_APPROVAL","NO_ACTIVATION","READ_ONLY","SYNTHETIC_ONLY"),"synthetic:key:440",14)
 e=r.evidence();o=ROOT/"build/synthetic-operator-intent-receipts-evidence.json";o.parent.mkdir(exist_ok=True);x=json.dumps(e,sort_keys=True,indent=2)+"\n";o.write_text(x);d=sha256(x.encode()).hexdigest();o.with_suffix(".json.sha256").write_text(d+"\n");print("synthetic operator intent receipts: PASS",d)
if __name__=="__main__":main()
