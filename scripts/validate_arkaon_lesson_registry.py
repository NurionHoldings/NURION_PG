from __future__ import annotations
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/"config/arkaon-lesson-registry-v1.json"
FIELDS={"lesson_id","discovery_scope","defect_category","root_cause","exploit_scenario",
        "mandatory_prevention_rules","required_negative_tests","ethernian_remediation_reference",
        "arkaon_acknowledgement","revalidation_evidence"}

def discovered_fix_commits(base):
    output=subprocess.check_output(["git","log","--format=%H%x09%s",f"{base}..HEAD"],cwd=ROOT,text=True)
    return {line.split("\t",1)[0][:7] for line in output.splitlines() if "\tfix:" in line}

def validate(data, discovered):
    if data.get("version") != 1 or data.get("mode") != "DEVELOPMENT_LEARNING_ONLY" or data.get("automatic_prompt_policy_weight_change") is not False:
        raise ValueError("safe versioned lesson registry required")
    lessons=data.get("lessons",[]); ids=[x.get("lesson_id") for x in lessons]
    if len(ids)!=len(set(ids)) or not lessons: raise ValueError("unique lessons required")
    covered=set()
    for lesson in lessons:
        if not FIELDS <= set(lesson): raise ValueError("incomplete lesson")
        if not all(lesson.get(k) for k in ("discovery_scope","defect_category","root_cause","exploit_scenario")): raise ValueError("empty lesson narrative")
        if not lesson["mandatory_prevention_rules"] or not lesson["required_negative_tests"]: raise ValueError("prevention rules and negative tests required")
        ack=lesson["arkaon_acknowledgement"]; evidence=lesson["revalidation_evidence"]
        if ack.get("acknowledged") is not True or not ack.get("applied_in"): raise ValueError("ARKAON acknowledgement required")
        if evidence.get("result") != "PASS" or not evidence.get("suite"): raise ValueError("passing revalidation required")
        covered.add(lesson["ethernian_remediation_reference"].split("^",1)[0][:7])
    if set(discovered)-covered: raise ValueError(f"unregistered Ethernian fix: {sorted(set(discovered)-covered)}")
    gate=data.get("next_stage_gate",{})
    if not all(gate.get(k) is True for k in ("must_read_registry","must_record_registry_digest_in_evidence","must_record_applied_lesson_ids","fail_closed_on_unregistered_ethernian_fix")):
        raise ValueError("next-stage fail-closed gate required")
    return tuple(sorted(ids))

def main():
    data=json.loads(REGISTRY.read_text(encoding="utf-8")); ids=validate(data,discovered_fix_commits(data["scan_base_commit"]))
    print("ARKAON lesson registry: PASS",len(ids),"lessons")

if __name__=="__main__": main()
