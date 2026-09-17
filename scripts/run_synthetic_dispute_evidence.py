from datetime import UTC,datetime,timedelta
from hashlib import sha256
import json
from pathlib import Path
from nurion_pg.synthetic_dispute_cases import *
ROOT=Path(__file__).resolve().parents[1];h=lambda x:sha256(x).hexdigest()
def main():
 now=datetime(2026,9,17,tzinfo=UTC);b=SyntheticDisputeBook();c=DisputeCase("synthetic:case:evidence","synthetic:intent:evidence","synthetic:merchant:evidence","FRAUD",5000,"KRW",now+timedelta(days=7),h(b"p"),h(b"s"));b.open(c,available_minor=10000,snapshot_valid=True,now=now,idempotency_key="synthetic:open");b.verify(c.case_id,expected_version=1,idempotency_key="synthetic:verify");b.freeze(c.case_id,tuple(sorted((h(b"a"),h(b"b")))),expected_version=2,idempotency_key="synthetic:freeze");r=b.evidence();o=ROOT/"build/synthetic-dispute-evidence.json";o.parent.mkdir(exist_ok=True);p=json.dumps(r,sort_keys=True,indent=2)+"\n";o.write_text(p);d=sha256(p.encode()).hexdigest();o.with_suffix(".json.sha256").write_text(d+"\n");print("synthetic dispute evidence: PASS",d)
if __name__=="__main__":main()
