from hashlib import sha256
import json
from pathlib import Path

from nurion_pg.synthetic_option_methodology_independent_challenge import *
from nurion_pg.synthetic_judgment_preparation_stress_test import SyntheticJudgmentPreparationStressTest,NEGATIVE as STRESS_NEGATIVE
from run_synthetic_judgment_preparation_stress_test_evidence import prior_service
from validate_arkaon_lesson_registry import MANIFEST,declared_remediations,discovered_negative_tests,validate

ROOT=Path(__file__).resolve().parents[1];REGISTRY=ROOT/"config/arkaon-lesson-registry-v1.json";GUIDANCE=ROOT/"config/arkaon-audit-recurrence-prevention.json"
def d(v):return sha256(v.encode()).hexdigest()
def main():
    rb=REGISTRY.read_bytes();mb=MANIFEST.read_bytes();rules=tuple(x["id"] for x in json.loads(GUIDANCE.read_bytes())["rules"]);lessons=validate(json.loads(rb),declared_remediations(json.loads(mb)),discovered_negative_tests())
    if lessons!=APPLIED_LESSONS or rules!=APPLIED_RULES:raise ValueError("continuous lessons and rules required")
    old=tuple(x for x in lessons if x!="ARL-12301-001");prior=prior_service(old,rules,sha256(rb).hexdigest(),sha256(mb).hexdigest());stress=SyntheticJudgmentPreparationStressTest()
    for cid in range(11901,12301):
        w,a=stress._expected(cid);stress.add_control(cid,w,a,f"synthetic:judgment-stress-requirement:{(cid-11901)//25:02}",d(f"prior:{cid}"),"EXPECTED_REJECTION" if a in STRESS_NEGATIVE else "PASS")
    stress.anchor(prior,sha256(rb).hexdigest(),sha256(mb).hexdigest(),old,rules,26,True)
    for i,key in enumerate(CASE_KEYS):
        args=(f"synthetic:judgment-preparation-stress-test:{key[0]}:{key[1]}",*key)
        if prior._reviews[key].judgment_packet:stress.add_stress_test(*args,f"synthetic:judgment-stress-preparer:preparer-{i}",f"synthetic:judgment-stress-challenger:challenger-{i}")
        else:stress.add_stress_test(*args)
    stress.finalize("synthetic:judgment-stress-docket:methodology-source","synthetic:judgment-stress-docket-compiler:stress-final-compiler","synthetic:judgment-stress-docket-validator:stress-final-validator")
    s=SyntheticOptionMethodologyIndependentChallenge()
    for cid in range(12301,12701):
        w,a=s._expected(cid);s.add_control(cid,w,a,f"synthetic:methodology-challenge-requirement:{(cid-12301)//25:02}",d(f"fixture:{cid}"),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    s.anchor(stress,sha256(rb).hexdigest(),sha256(mb).hexdigest(),lessons,rules,27,True)
    for i,key in enumerate(CASE_KEYS):
        args=(f"synthetic:option-methodology-challenge:{key[0]}:{key[1]}",*key)
        if stress._tests[key].option_profiles:s.add_challenge(*args,f"synthetic:methodology-challenger:method-challenger-{i}",f"synthetic:methodology-custodian:method-custodian-{i}")
        else:s.add_challenge(*args)
    s.finalize("synthetic:option-methodology-docket:evidence","synthetic:methodology-docket-compiler:methodology-final-compiler","synthetic:methodology-docket-validator:methodology-final-validator");e=s.evidence()
    if not e["complete_option_methodology_challenge_evidence"] or e["registered_control_count"]!=400 or e["methodology_card_count"]!=32 or e["judgment_authority"] is not False:raise ValueError("incomplete or over-authoritative evidence")
    e.update({"lesson_registry_digest":sha256(rb).hexdigest(),"remediation_manifest_digest":sha256(mb).hexdigest(),"audit_remediation":"ETH-12301-AUDIT-001"});out=ROOT/"build/synthetic-option-methodology-independent-challenge-evidence.json";out.parent.mkdir(exist_ok=True);payload=json.dumps(e,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode();out.write_bytes(payload);digest=sha256(payload).hexdigest();out.with_suffix(out.suffix+".sha256").write_text(digest+"\n",encoding="utf-8");print(digest)
if __name__=="__main__":main()
