from datetime import UTC,datetime,timedelta
from hashlib import sha256
import json
from pathlib import Path
from nurion_pg.synthetic_risk_response_plan import RiskResponsePlan
ROOT=Path(__file__).resolve().parents[1];h=lambda x:sha256(x).hexdigest()
def main():
 n=datetime(2026,9,18,tzinfo=UTC);p=RiskResponsePlan(h(b"risk"),h(b"policy"));p.intake("SYNTHETIC_PORTFOLIO_RISK_REPORT_COMPLETED",(),"synthetic:key:381");p.classify_gaps(("COVERAGE","DEADLINE"),"synthetic:key:382",1);p.candidates(("EXTEND_OBSERVATION","QUEUE_REVIEW"),"synthetic:key:383",2);p.impact("synthetic:merchant:e","KRW",500,1000,"synthetic:key:384",3);p.fairness(("A","B"),{"A":5000,"B":5200},"synthetic:key:385",4);p.priority(((1,"QUEUE_REVIEW"),(2,"EXTEND_OBSERVATION")),"synthetic:key:386",5);p.cooling(n,n+timedelta(days=7),"synthetic:key:387",6);p.exceptions(("FAIRNESS_REVIEW",),"synthetic:key:388",7);p.roles("synthetic:actor:author","synthetic:actor:reviewer","synthetic:actor:operator","synthetic:key:389",8);p.rollback(("FAIRNESS_BREACH","METRIC_REGRESSION"),"synthetic:key:390",9);p.shadow_schedule(n,n+timedelta(days=14),1000,"synthetic:key:391",10);p.success_criteria((("COVERAGE_BP","GTE",9000),("DEADLINE_BP","LTE",500)),"synthetic:key:392",11);p.operator_packet("synthetic:operator:1",("EVIDENCE","FAIRNESS","ROLLBACK","SAFETY"),"synthetic:key:393",12);p.seal(None,"synthetic:key:394",13);p.complete(("NON_EXECUTABLE","OPERATOR_SEPARATE","READ_ONLY","SYNTHETIC_ONLY"),"synthetic:key:395",14)
 r=p.evidence();o=ROOT/"build/synthetic-risk-response-plan-evidence.json";o.parent.mkdir(exist_ok=True);x=json.dumps(r,sort_keys=True,indent=2)+"\n";o.write_text(x);d=sha256(x.encode()).hexdigest();o.with_suffix(".json.sha256").write_text(d+"\n");print("synthetic risk response plan: PASS",d)
if __name__=="__main__":main()
