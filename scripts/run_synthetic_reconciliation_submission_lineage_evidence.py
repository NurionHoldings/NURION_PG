from hashlib import sha256
import json
from pathlib import Path

from nurion_pg.arkaon.governance import canonical_digest
from nurion_pg.synthetic_reconciliation_submission_lineage import *
from validate_arkaon_lesson_registry import MANIFEST, declared_remediations, discovered_negative_tests, validate

ROOT=Path(__file__).resolve().parents[1]; REGISTRY=ROOT/"config/arkaon-lesson-registry-v1.json"; GUIDANCE=ROOT/"config/arkaon-audit-recurrence-prevention.json"
def d(value): return sha256(value.encode()).hexdigest()
def main():
    rb=REGISTRY.read_bytes(); mb=MANIFEST.read_bytes(); gb=GUIDANCE.read_bytes(); registry=json.loads(rb); manifest=json.loads(mb); guidance=json.loads(gb)
    lessons=validate(registry,declared_remediations(manifest),discovered_negative_tests()); rules=tuple(x["id"] for x in guidance["rules"])
    if lessons!=APPLIED_LESSONS or rules!=APPLIED_RULES or guidance["completion_gate"]["fail_closed"] is not True: raise ValueError("exact stable learned protections required")
    service=SyntheticReconciliationSubmissionLineage()
    for start,end,name in WORKSTREAMS:
        for cid in range(start,end+1):
            aspect=CONTROL_ASPECTS[(cid-8301)%25]; service.add_control(cid,name,aspect,f"synthetic:submission-lineage-requirement:{(cid-8301)//25:02}",d(f"fixture:{cid}"),"EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS")
    cases=[]
    for flow in FLOWS:
        for index,kind in enumerate(ANSWER_KINDS):
            claim=d(f"claim:{flow}:{kind}"); manifest_digest=d(f"manifest:{flow}:{kind}"); receipt=d(f"receipt:{flow}:{kind}")
            counter_claim=claim if index!=1 else d(f"counter-claim:{flow}:{kind}"); counter_manifest=manifest_digest if index!=2 else d(f"counter-manifest:{flow}:{kind}"); counter_receipt=receipt if index!=3 else d(f"counter-receipt:{flow}:{kind}"); sv=1; cv=2 if index==4 else 1
            source_binding=d(f"source:{flow}:{kind}"); counter_binding=d(f"counter:{flow}:{kind}"); outcome=COMPARISON_OUTCOMES[index]; comparison=canonical_digest(("SOURCE_RECONCILIATION_COMPARISON",flow,kind,outcome,source_binding,counter_binding)); route=canonical_digest(("SOURCE_HUMAN_RECONCILIATION_QUEUE",flow,kind,outcome,comparison,*FLOW_PARTIES[flow])); vals=(source_binding,counter_binding,claim,counter_claim,manifest_digest,counter_manifest,receipt,counter_receipt,sv,cv,comparison,route)
            cases.append(SourceCase(flow,kind,outcome,*vals,canonical_digest(("SOURCE_RECONCILIATION_CASE",flow,kind,outcome,*vals))))
    reviewers=("synthetic:readiness-reviewer:maker","synthetic:preflight-reviewer:checker","synthetic:reconsideration-reviewer:independent"); compilers=tuple(f"synthetic:packet-compiler:source-{i}" for i in range(1,5))
    case_set=canonical_digest(tuple(x.case_digest for x in cases))
    service.anchor_queue("synthetic:submission-lineage-anchor:evidence",d("queue"),case_set,sha256(rb).hexdigest(),sha256(mb).hexdigest(),lessons,rules,cases,17,True,reviewers,compilers,"synthetic:human-deliberation-chair:chair","synthetic:cross-party-validator:cross")
    for flow in FLOWS:
        for kind in ANSWER_KINDS:
            for submission_kind in SUBMISSION_KINDS:
                party=expected_author(flow,submission_kind); service.add_submission(f"synthetic:reconciliation-submission:{flow}:{kind}:{submission_kind}",flow,kind,submission_kind,party,f"synthetic:submission-author:{party}","synthetic:submission-lineage-validator:lineage")
    for flow in FLOWS:
        for kind in ANSWER_KINDS:
            service.build_bundle(f"synthetic:submission-bundle:{flow}:{kind}",flow,kind,"synthetic:submission-bundle-compiler:bundle")
    service.finalize("synthetic:submission-hold-docket:evidence","synthetic:submission-docket-compiler:docket")
    evidence=service.evidence()
    if not evidence["complete_submission_hold_evidence"] or evidence["registered_control_count"]!=400: raise ValueError("incomplete evidence")
    evidence.update({"lesson_registry_read_and_applied":True,"lesson_registry_version":registry["version"],"lesson_registry_digest":sha256(rb).hexdigest(),"remediation_manifest_digest":sha256(mb).hexdigest(),"remediation_guidance_digest":sha256(gb).hexdigest(),"lesson_validation_mode":"STABLE_MANIFEST_NO_GIT_HISTORY_DEPENDENCY"})
    out=ROOT/"build/synthetic-reconciliation-submission-lineage-evidence.json"; out.parent.mkdir(exist_ok=True); content=json.dumps(evidence,ensure_ascii=False,indent=2,sort_keys=True)+"\n"; out.write_text(content,encoding="utf-8"); checksum=sha256(content.encode()).hexdigest(); out.with_suffix(".json.sha256").write_text(checksum+"\n",encoding="utf-8"); print("synthetic reconciliation submission lineage #8301-#8700: PASS",checksum)
if __name__=="__main__": main()
