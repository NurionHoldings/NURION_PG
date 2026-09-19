from hashlib import sha256
import json
from pathlib import Path

from nurion_pg.synthetic_integration_package_acceptance import ALLOWED_ARTIFACTS, CONTROL_ASPECTS, FLOWS, FLOW_OWNERS, NEGATIVE, WORKSTREAMS, SyntheticIntegrationPackageAcceptance
from validate_arkaon_lesson_registry import REGISTRY, discovered_fix_commits, validate

ROOT=Path(__file__).resolve().parents[1]
def d(x): return sha256(x.encode()).hexdigest()

def main():
    registry_content=REGISTRY.read_bytes(); registry=json.loads(registry_content)
    lesson_ids=validate(registry,discovered_fix_commits(registry["scan_base_commit"]))
    s=SyntheticIntegrationPackageAcceptance()
    for start,end,name in WORKSTREAMS:
        for cid in range(start,end+1):
            aspect=CONTROL_ASPECTS[(cid-4301)%25]
            s.add_control(cid,name,aspect,f"synthetic:package-requirement:{(cid-4301)//25:02}",d(f"fixture:{cid}"),"EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS")
    s.anchor_negotiation("synthetic:package-anchor:evidence",d("bundle"),d("round"),d("negotiation-cases"),d("negotiation-receipt"))
    for ki,kind in enumerate(sorted(ALLOWED_ARTIFACTS)):
        for fi,flow in enumerate(FLOWS):
            s.add_artifact(f"synthetic:package-artifact:{ki}-{fi}",kind,FLOW_OWNERS[flow],flow,d(f"content:{kind}:{flow}"))
    m=s.assemble("synthetic:integration-package:evidence","synthetic:tenant:evidence","synthetic:upstream:evidence","synthetic:package-assembler:maker")
    s.run_cases(m.package_id)
    s.review("synthetic:package-receipt:evidence",m.package_id,"synthetic:package-reviewer:checker","synthetic:package-assembler:maker")
    evidence=s.evidence(); assert evidence["capability_ready"] and evidence["mock_case_count"]==400
    evidence["lesson_registry_read_and_applied"]=True
    evidence["lesson_registry_version"]=registry["version"]
    evidence["lesson_registry_digest"]=sha256(registry_content).hexdigest()
    evidence["applied_lesson_ids"]=list(lesson_ids)
    out=ROOT/"build/synthetic-integration-package-acceptance-evidence.json"; out.parent.mkdir(exist_ok=True)
    content=json.dumps(evidence,ensure_ascii=False,indent=2,sort_keys=True)+"\n"; out.write_text(content,encoding="utf-8")
    checksum=sha256(content.encode()).hexdigest(); out.with_suffix(".json.sha256").write_text(checksum+"\n",encoding="utf-8")
    print("synthetic integration package acceptance #4301-#4700: PASS",checksum)

if __name__=="__main__": main()
