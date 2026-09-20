from hashlib import sha256
import json
from pathlib import Path
from nurion_pg.synthetic_p0_design_baseline_rfc import WORKSTREAMS, SyntheticP0DesignBaselineRFC

ROOT=Path(__file__).resolve().parents[1]
def d(x): return sha256(x.encode()).hexdigest()
def main():
    s=SyntheticP0DesignBaselineRFC(); sid="synthetic:official-source:baseline"
    s.add_source(sid,"https://www.w3.org/TR/WCAG22/","Official synthetic reference metadata","2026-09-01","STANDARD","2027-09-01",d("content"))
    for i,(start,end,name) in enumerate(WORKSTREAMS):
        s.add_requirement(f"synthetic:p0-requirement:{i:02}",name,range(start,end+1),f"P0 rationale {i}",f"P0 threat {i}",(d(f"acceptance:{i}"),),"SECURITY",True,(sid,))
    row=s.author("synthetic:p0-rfc:evidence","synthetic:rfc-author:author",tuple(s._requirements))
    row=s.review("synthetic:rfc-review:evidence",row.rfc_id,row.version,"synthetic:rfc-reviewer:reviewer",True,d("finding"))
    review=s.artifact("synthetic:rfc-review:evidence")
    row=s.record("synthetic:rfc-receipt:evidence",row.rfc_id,row.version,"synthetic:rfc-verifier:verifier",review.digest)
    e=s.evidence(); assert row.status==e["maximum_state"] and e["control_count"]==400 and e["workstream_count"]==16 and e["integrity_valid"] and e["capability_ready"]
    out=ROOT/"build/synthetic-p0-design-baseline-rfc-evidence.json"; out.parent.mkdir(exist_ok=True)
    content=json.dumps(e,ensure_ascii=False,indent=2,sort_keys=True)+"\n"; out.write_text(content,encoding="utf-8")
    checksum=sha256(content.encode()).hexdigest(); out.with_suffix(".json.sha256").write_text(checksum+"\n",encoding="utf-8")
    print("synthetic P0 design baseline RFC #3101-#3500: PASS",checksum)
if __name__=="__main__": main()
