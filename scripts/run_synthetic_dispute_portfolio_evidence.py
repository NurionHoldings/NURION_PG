from datetime import UTC,datetime,timedelta
from hashlib import sha256
import json
from pathlib import Path
from nurion_pg.synthetic_dispute_portfolio import *
ROOT=Path(__file__).resolve().parents[1];h=lambda x:sha256(x).hexdigest()
def main():
 n=datetime(2026,9,18,tzinfo=UTC);p=DisputePortfolio("synthetic:case:e","synthetic:merchant:e","KRW",10000,h(b"f"),h(b"r"));p.supplement((h(b"a"),),(h(b"b"),),h(b"q"));p.merchant_response(("SERVICE_PROVIDED",),True);p.sla(n,n+timedelta(days=2),n);p.relationship("synthetic:case:o","synthetic:merchant:e","KRW",True);p.liability(20,70,10,h(b"m"));p.financial_impact(100,500,h(b"p"));p.resolution_packet("synthetic:issuer:e","synthetic:reviewer:e");p.verify_packet("synthetic:verifier:e","synthetic:issuer:e",("DIGESTS","ROLES","AMOUNTS","SAFETY"));p.ledger_preview(7000,7000);p.envelope_lint(h(b"s"),("case_digest","currency","evidence_set_digest","recommended_minor"));p.reversal("NEW_EVIDENCE");p.reconcile_closure();p.complete();r=p.evidence();o=ROOT/"build/synthetic-dispute-portfolio-evidence.json";o.parent.mkdir(exist_ok=True);x=json.dumps(r,sort_keys=True,indent=2)+"\n";o.write_text(x);d=sha256(x.encode()).hexdigest();o.with_suffix(".json.sha256").write_text(d+"\n");print("synthetic dispute portfolio: PASS",d)
if __name__=="__main__":main()
