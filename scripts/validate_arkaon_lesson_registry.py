from __future__ import annotations
import json
from pathlib import Path
import re
from hashlib import sha256

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/"config/arkaon-lesson-registry-v1.json"
MANIFEST=ROOT/"config/ethernian-remediation-manifest-v1.json"
FIELDS={"lesson_id","discovery_scope","defect_category","root_cause","exploit_scenario",
        "mandatory_prevention_rules","required_negative_tests","ethernian_remediation_reference",
        "arkaon_acknowledgement","revalidation_evidence"}
LESSONS_12301=("ARL-10301-001","ARL-10701-001","ARL-11101-001","ARL-11501-001","ARL-12301-001","ARL-3901-001","ARL-4301-001","ARL-4301-002","ARL-4301-003","ARL-4701-001","ARL-5101-001","ARL-5501-001","ARL-5901-001","ARL-6301-001","ARL-6701-001","ARL-7101-001","ARL-7501-001","ARL-7901-001","ARL-8301-001","ARL-8701-001","ARL-9101-001","ARL-9501-001","ARL-9901-001")
HISTORICAL_LESSON_SNAPSHOTS={
    "ARKAON-LESSONS-7501":((7501,7900),("ARL-3901-001","ARL-4301-001","ARL-4301-002","ARL-4301-003","ARL-4701-001","ARL-5101-001","ARL-5501-001","ARL-5901-001","ARL-6301-001","ARL-6701-001","ARL-7101-001","ARL-7501-001")),
}
STAGE_LESSON_SNAPSHOTS={
    "ARKAON-LESSONS-12301":((9901,12700),LESSONS_12301),
    "ARKAON-LESSONS-12701":((12701,13100),tuple(sorted(LESSONS_12301+("ARL-12701-001",)))),
    "ARKAON-LESSONS-13101":((13101,13500),tuple(sorted(LESSONS_12301+("ARL-12701-001","ARL-13101-001")))),
    "ARKAON-LESSONS-13501":((13501,13900),tuple(sorted(LESSONS_12301+("ARL-12701-001","ARL-13101-001","ARL-13501-001")))),
    "ARKAON-LESSONS-13901":((13901,14300),tuple(sorted(LESSONS_12301+("ARL-12701-001","ARL-13101-001","ARL-13501-001","ARL-13901-001")))),
    "ARKAON-LESSONS-14301":((14301,14700),tuple(sorted(LESSONS_12301+("ARL-12701-001","ARL-13101-001","ARL-13501-001","ARL-13901-001","ARL-14301-001")))),
    "ARKAON-LESSONS-14701":((14701,15100),tuple(sorted(LESSONS_12301+("ARL-12701-001","ARL-13101-001","ARL-13501-001","ARL-13901-001","ARL-14301-001","ARL-14701-001")))),
    "ARKAON-LESSONS-15101":((15101,15500),tuple(sorted(LESSONS_12301+("ARL-12701-001","ARL-13101-001","ARL-13501-001","ARL-13901-001","ARL-14301-001","ARL-14701-001","ARL-15101-001")))),
    "ARKAON-LESSONS-15501":((15501,15900),tuple(sorted(LESSONS_12301+("ARL-12701-001","ARL-13101-001","ARL-13501-001","ARL-13901-001","ARL-14301-001","ARL-14701-001","ARL-15101-001","ARL-15501-001")))),
    "ARKAON-LESSONS-15901":((15901,16300),tuple(sorted(LESSONS_12301+("ARL-12701-001","ARL-13101-001","ARL-13501-001","ARL-13901-001","ARL-14301-001","ARL-14701-001","ARL-15101-001","ARL-15501-001","ARL-15901-001")))),
    "ARKAON-LESSONS-16301":((16301,16700),tuple(sorted(LESSONS_12301+("ARL-12701-001","ARL-13101-001","ARL-13501-001","ARL-13901-001","ARL-14301-001","ARL-14701-001","ARL-15101-001","ARL-15501-001","ARL-15901-001","ARL-16301-001")))),
    "ARKAON-LESSONS-16701":((16701,17100),tuple(sorted(LESSONS_12301+("ARL-12701-001","ARL-13101-001","ARL-13501-001","ARL-13901-001","ARL-14301-001","ARL-14701-001","ARL-15101-001","ARL-15501-001","ARL-15901-001","ARL-16301-001","ARL-16701-001")))),
}

def validated_stage_chain(snapshots=STAGE_LESSON_SNAPSHOTS):
    """Reject duplicate/gapped/overlapping stages and lesson-chain regressions."""
    rows=sorted((bounds[0],bounds[1],sid,tuple(lessons)) for sid,(bounds,lessons) in snapshots.items())
    if not rows: raise ValueError("at least one stage snapshot required")
    seen=set();previous=None
    for start,end,sid,lessons in rows:
        if not sid or start>end or (start,end) in seen: raise ValueError("unique valid stage range required")
        if previous and start!=previous[1]+1: raise ValueError("contiguous stage snapshot chain required")
        if len(lessons)!=len(set(lessons)) or tuple(sorted(lessons))!=lessons: raise ValueError("canonical unique lessons required")
        if previous and not set(previous[3])<=set(lessons): raise ValueError("stage lesson chain cannot regress")
        seen.add((start,end));previous=(start,end,sid,lessons)
    return tuple((sid,(start,end),lessons) for start,end,sid,lessons in rows)

def validated_stage_chain_through(max_end, snapshots=STAGE_LESSON_SNAPSHOTS):
    """Validate the immutable chain visible at a stage boundary, ignoring future stages."""
    if not isinstance(max_end,int) or isinstance(max_end,bool):
        raise ValueError("integer stage boundary required")
    bounded={sid:(bounds,lessons) for sid,(bounds,lessons) in snapshots.items() if bounds[1]<=max_end}
    rows=validated_stage_chain(bounded)
    if not rows or rows[-1][1][1]!=max_end:
        raise ValueError("declared stage boundary required")
    return rows

def declared_remediations(data):
    if data.get("version") != 1: raise ValueError("versioned remediation manifest required")
    rows=data.get("remediations",[]); ids=[x.get("remediation_id") for x in rows]
    if not rows or len(ids)!=len(set(ids)) or any(not x.get("scope") or not x.get("required_lesson_ids") for x in rows):
        raise ValueError("complete unique remediation declarations required")
    return {x["remediation_id"]: set(x["required_lesson_ids"]) for x in rows}

def discovered_negative_tests():
    names=set()
    for path in (ROOT/"tests").glob("test_*.py"):
        names.update(re.findall(r"^\s*def\s+(test_[A-Za-z0-9_]+)\s*\(",path.read_text(encoding="utf-8"),re.M))
    return names

def validate(data, declared, test_names):
    if data.get("version") != 1 or data.get("mode") != "DEVELOPMENT_LEARNING_ONLY" or data.get("automatic_prompt_policy_weight_change") is not False:
        raise ValueError("safe versioned lesson registry required")
    lessons=data.get("lessons",[]); ids=[x.get("lesson_id") for x in lessons]
    if len(ids)!=len(set(ids)) or not lessons: raise ValueError("unique lessons required")
    covered={}
    for lesson in lessons:
        if not FIELDS <= set(lesson): raise ValueError("incomplete lesson")
        if not all(lesson.get(k) for k in ("discovery_scope","defect_category","root_cause","exploit_scenario")): raise ValueError("empty lesson narrative")
        if not lesson["mandatory_prevention_rules"] or not lesson["required_negative_tests"]: raise ValueError("prevention rules and negative tests required")
        if not set(lesson["required_negative_tests"]) <= set(test_names): raise ValueError("named negative test missing")
        ack=lesson["arkaon_acknowledgement"]; evidence=lesson["revalidation_evidence"]
        if ack.get("acknowledged") is not True or not ack.get("applied_in"): raise ValueError("ARKAON acknowledgement required")
        if evidence.get("result") != "PASS" or not evidence.get("suite"): raise ValueError("passing revalidation required")
        ref=lesson["ethernian_remediation_reference"]
        covered.setdefault(ref,set()).add(lesson["lesson_id"])
    if set(declared)!=set(covered): raise ValueError("remediation/lesson coverage mismatch")
    for ref, required in declared.items():
        if covered[ref] != required: raise ValueError(f"lesson mismatch for remediation: {ref}")
    gate=data.get("next_stage_gate",{})
    if not all(gate.get(k) is True for k in ("must_read_registry","must_record_registry_digest_in_evidence","must_record_applied_lesson_ids","fail_closed_on_unregistered_ethernian_fix")):
        raise ValueError("next-stage fail-closed gate required")
    return tuple(sorted(ids))

def validated_stage_snapshot(validated_lessons, required_lessons, snapshot_id, stage_range):
    """Validate an immutable stage subset without equating it to the live registry."""
    validated_lessons=tuple(validated_lessons);required_lessons=tuple(required_lessons)
    validated_stage_chain();declared=(STAGE_LESSON_SNAPSHOTS|HISTORICAL_LESSON_SNAPSHOTS).get(snapshot_id)
    if not snapshot_id or not isinstance(stage_range,tuple) or len(stage_range)!=2 or stage_range[0]>stage_range[1] or declared!=(stage_range,required_lessons):
        raise ValueError("valid stage snapshot identity and range required")
    if not required_lessons or len(required_lessons)!=len(set(required_lessons)) or not set(required_lessons)<=set(validated_lessons):
        raise ValueError("stage lessons must be a unique validated registry subset")
    payload=json.dumps({"snapshot_id":snapshot_id,"stage_range":stage_range,"lesson_ids":required_lessons},sort_keys=True,separators=(",",":")).encode()
    return required_lessons,sha256(payload).hexdigest()

def main():
    data=json.loads(REGISTRY.read_text(encoding="utf-8"))
    manifest=json.loads(MANIFEST.read_text(encoding="utf-8"))
    ids=validate(data,declared_remediations(manifest),discovered_negative_tests())
    print("ARKAON lesson registry: PASS",len(ids),"lessons")

if __name__=="__main__": main()
