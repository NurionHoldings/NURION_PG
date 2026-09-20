from __future__ import annotations
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/"config/arkaon-lesson-registry-v1.json"
MANIFEST=ROOT/"config/ethernian-remediation-manifest-v1.json"
FIELDS={"lesson_id","discovery_scope","defect_category","root_cause","exploit_scenario",
        "mandatory_prevention_rules","required_negative_tests","ethernian_remediation_reference",
        "arkaon_acknowledgement","revalidation_evidence"}

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

def main():
    data=json.loads(REGISTRY.read_text(encoding="utf-8"))
    manifest=json.loads(MANIFEST.read_text(encoding="utf-8"))
    ids=validate(data,declared_remediations(manifest),discovered_negative_tests())
    print("ARKAON lesson registry: PASS",len(ids),"lessons")

if __name__=="__main__": main()
