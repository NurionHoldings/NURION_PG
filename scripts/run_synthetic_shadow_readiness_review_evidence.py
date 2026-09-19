from datetime import UTC,datetime,timedelta
from hashlib import sha256
import json
from pathlib import Path
from nurion_pg.synthetic_shadow_readiness_review import ShadowReadinessReview
ROOT=Path(__file__).resolve().parents[1];h=lambda x:sha256(x).hexdigest()
def main():
 n=datetime(2026,9,18,tzinfo=UTC);r=ShadowReadinessReview(h(b"validation"),h(b"policy"));r.admit("SYNTHETIC_RESPONSE_SHADOW_VALIDATION_COMPLETED","ELIGIBLE_DRAFT",True,False,("CEILING_BREACH","FAIRNESS_BREACH"),"synthetic:key:411");r.blockers(("NONE",),"synthetic:key:412",1);r.evidence_matrix(("CRITERIA","FAIRNESS","FINANCIAL","ROLLBACK","SENSITIVITY"),"synthetic:key:413",2);r.consistency("ELIGIBLE_DRAFT","synthetic:key:414",3);r.fairness(150,200,"synthetic:key:415",4);r.financial(900,1000,"synthetic:key:416",5);r.rollback(("CEILING_BREACH","FAIRNESS_BREACH"),("CEILING_BREACH","FAIRNESS_BREACH"),"synthetic:key:417",6);r.capacity(100,90,20,"synthetic:key:418",7);r.window(n,n+timedelta(days=7),"synthetic:key:419",8);r.roles("synthetic:actor:author","synthetic:actor:reviewer","synthetic:operator:1","synthetic:key:420",9);r.alternatives(("HOLD","REQUEST_REVISION","SUBMIT_FOR_OPERATOR_REVIEW"),"synthetic:key:421",10);r.packet("synthetic:operator:1","SUBMIT_FOR_OPERATOR_REVIEW","synthetic:key:422",11);r.verify("synthetic:verifier:1",("DIGESTS","ROLES","BLOCKERS","SAFETY"),"synthetic:key:423",12);r.seal(None,"synthetic:key:424",13);r.complete(("NO_ACTIVATION","NO_AUTHORIZATION","READ_ONLY","SYNTHETIC_ONLY"),"synthetic:key:425",14)
 e=r.evidence();o=ROOT/"build/synthetic-shadow-readiness-review-evidence.json";o.parent.mkdir(exist_ok=True);x=json.dumps(e,sort_keys=True,indent=2)+"\n";o.write_text(x);d=sha256(x.encode()).hexdigest();o.with_suffix(".json.sha256").write_text(d+"\n");print("synthetic shadow readiness review: PASS",d)
if __name__=="__main__":main()
