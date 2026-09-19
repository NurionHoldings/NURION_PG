from hashlib import sha256
import json
from pathlib import Path
from nurion_pg.synthetic_dispute_review_docket import *
ROOT=Path(__file__).resolve().parents[1];h=lambda x:sha256(x).hexdigest()
def main():
 b=ReviewBook();d=Docket("synthetic:docket:e","synthetic:case:e",h(b"c"),h(b"e"),"synthetic:intake:e",5000,h(b"p"));b.open(d,source_frozen=True,key="synthetic:o");b.assign(d.docket_id,"synthetic:reviewer:e",expected_version=1,key="synthetic:a");b.start(d.docket_id,"synthetic:reviewer:e",expected_version=2,key="synthetic:s");b.draft(d.docket_id,"synthetic:reviewer:e",Recommendation.ACCEPT_DRAFT,5000,"VALID_EVIDENCE",expected_version=3,key="synthetic:d");r=b.evidence();o=ROOT/"build/synthetic-dispute-review-evidence.json";o.parent.mkdir(exist_ok=True);p=json.dumps(r,sort_keys=True,indent=2)+"\n";o.write_text(p);dg=sha256(p.encode()).hexdigest();o.with_suffix(".json.sha256").write_text(dg+"\n");print("synthetic dispute review: PASS",dg)
if __name__=="__main__":main()
