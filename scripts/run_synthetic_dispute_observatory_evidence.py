from datetime import UTC,datetime
from hashlib import sha256
import json
from pathlib import Path
from nurion_pg.synthetic_dispute_observatory import DisputeObservatory
ROOT=Path(__file__).resolve().parents[1];h=lambda x:sha256(x).hexdigest()
def main():
 o=DisputeObservatory(h(b"manifest"),h(b"policy"));rows=({"case_id":"synthetic:case:e","currency":"KRW","state":"CLOSURE_RECONCILED","lineage_digest":h(b"lineage"),"reason":"SERVICE","merchant_ref":"synthetic:merchant:e","received_at":"2026-09-01T00:00:00+00:00","exposure_minor":1000},)
 o.projection(rows,"synthetic:key:366");o.cohorts(("age","currency","merchant","reason"),"synthetic:key:367",1);o.exposure((("KRW",1000),),"synthetic:key:368",2);o.aging(datetime(2026,9,18,tzinfo=UTC),(17,),"synthetic:key:369",3);o.deadline_risk(48,60,"synthetic:key:370",4);o.reason_concentration((("SERVICE",10000),),"synthetic:key:371",5);o.merchant_concentration((("synthetic:merchant:e","KRW",1000),),"synthetic:key:372",6);o.duplicate_clusters((("synthetic:case:e","synthetic:case:o"),),"synthetic:key:373",7);o.evidence_coverage(("AUTH","DELIVERY"),("AUTH","DELIVERY","COMMUNICATION"),"synthetic:key:374",8);o.independence("synthetic:actor:intake","synthetic:actor:reviewer","synthetic:actor:verifier","synthetic:key:375",9);o.impact_ceiling(900,1000,False,"synthetic:key:376",10);o.anomalies(("CONCENTRATION_HIGH","COVERAGE_LOW","DEADLINE_HIGH","IMPACT_NEAR_CEILING"),("COVERAGE_LOW",),"synthetic:key:377",11);o.alert_dockets(("synthetic:alert:coverage",),"synthetic:key:378",12);o.snapshot(None,"synthetic:key:379",13);o.report(("ALERTS_READ_ONLY","NO_AUTO_ACTION","NO_CURRENCY_COLLAPSE","ROLE_SEPARATION"),"synthetic:key:380",14)
 result=o.evidence();path=ROOT/"build/synthetic-dispute-observatory-evidence.json";path.parent.mkdir(exist_ok=True);data=json.dumps(result,sort_keys=True,indent=2)+"\n";path.write_text(data);digest=sha256(data.encode()).hexdigest();path.with_suffix(".json.sha256").write_text(digest+"\n");print("synthetic dispute observatory: PASS",digest)
if __name__=="__main__":main()
