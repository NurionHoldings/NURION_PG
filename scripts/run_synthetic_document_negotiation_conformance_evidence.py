from hashlib import sha256
import json
from pathlib import Path

from nurion_pg.synthetic_document_negotiation_conformance import (
    CONTROL_ASPECTS, NEGATIVE, WORKSTREAMS, SyntheticDocumentNegotiationConformance,
)

ROOT=Path(__file__).resolve().parents[1]
def d(x): return sha256(x.encode()).hexdigest()

def main():
    s=SyntheticDocumentNegotiationConformance()
    for start,end,name in WORKSTREAMS:
        for cid in range(start,end+1):
            aspect=CONTROL_ASPECTS[(cid-3901)%25]
            s.add_control(cid,name,aspect,f"synthetic:negotiation-requirement:{(cid-3901)//25:02}",d(f"fixture:{cid}"),"EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS")
    s.anchor_bundle("synthetic:negotiation-bundle:evidence",d("source-dossier"),d("source-receipt"),tuple(d(f"document:{x}") for x in range(4)),tuple(d(f"adapter:{x}") for x in range(3)))
    for party in ("TENANT_AGENCY","NURION_PG","UPSTREAM_PG"):
        s.add_profile(f"synthetic:capability-profile:{party.lower()}",party,1,2,("TOKEN_AMOUNT","TOKEN_ID","TOKEN_STATUS"),("COPY_TOKEN","RENAME","ENUM_LOOKUP"))
    s.add_rule("synthetic:mapping-rule:id","order_token","merchant_token","COPY_TOKEN","TOKEN_ID")
    s.add_rule("synthetic:mapping-rule:amount","amount_token","amount_token","COPY_TOKEN","TOKEN_AMOUNT")
    s.add_rule("synthetic:mapping-rule:status","status_token","status_token","ENUM_LOOKUP","TOKEN_STATUS")
    row=s.propose_round("synthetic:negotiation-round:evidence","TENANT_AGENCY",1,"synthetic:correlation:evidence","synthetic:idempotency:evidence")
    s.run_cases(row.round_id)
    s.review("synthetic:conformance-receipt:evidence",row.round_id,"synthetic:conformance-reviewer:reviewer",row.proposer)
    evidence=s.evidence(); assert evidence["capability_ready"] and evidence["conformance_case_count"]==400
    out=ROOT/"build/synthetic-document-negotiation-conformance-evidence.json"; out.parent.mkdir(exist_ok=True)
    content=json.dumps(evidence,ensure_ascii=False,indent=2,sort_keys=True)+"\n"; out.write_text(content,encoding="utf-8")
    checksum=sha256(content.encode()).hexdigest(); out.with_suffix(".json.sha256").write_text(checksum+"\n",encoding="utf-8")
    print("synthetic document negotiation conformance #3901-#4300: PASS",checksum)

if __name__=="__main__": main()
