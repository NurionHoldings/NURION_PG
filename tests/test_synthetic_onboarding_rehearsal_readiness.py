from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from hashlib import sha256
import unittest

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.synthetic_onboarding_rehearsal_readiness import (
    APPLIED_LESSONS, COMMON_OPERATIONS, COMMON_TOKEN_CLASSES, CONTROL_ASPECTS,
    FLOWS, NEGATIVE, PARTIES, SCENARIOS, WORKSTREAMS,
    SyntheticOnboardingRehearsalReadiness,
)

def d(x): return sha256(x.encode()).hexdigest()

def populated(full=True):
    s=SyntheticOnboardingRehearsalReadiness(); streams=WORKSTREAMS if full else WORKSTREAMS[:1]
    for start,end,name in streams:
        ids=range(start,end+1) if full else (start,)
        for cid in ids:
            aspect=CONTROL_ASPECTS[(cid-4701)%25]
            s.add_control(cid,name,aspect,f"synthetic:onboarding-requirement:{(cid-4701)//25:02}",d(f"fixture:{cid}"),"EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS")
    return s

def anchored():
    s=populated(); a=s.anchor_source("synthetic:onboarding-anchor:one",d("manifest"),d("receipt"),d("registry"),APPLIED_LESSONS,tuple((p,d(p)) for p in PARTIES),tuple((p,COMMON_OPERATIONS) for p in PARTIES),tuple((p,COMMON_TOKEN_CLASSES) for p in PARTIES),COMMON_OPERATIONS,COMMON_TOKEN_CLASSES,7,True,"synthetic:package-assembler:maker"); return s,a

def planned():
    s,a=anchored()
    for flow in FLOWS:
        for scenario in SCENARIOS:
            s.add_plan(f"synthetic:rehearsal-plan:{flow}:{scenario}",flow,scenario,COMMON_OPERATIONS,COMMON_TOKEN_CLASSES)
    return s,a

def completed():
    s,a=planned(); s.run_rehearsal(); r=s.review("synthetic:readiness-receipt:one","synthetic:readiness-reviewer:checker"); return s,a,r

def rehash(row, **changes):
    p=row.__dict__|changes; p["digest"]=canonical_digest({k:v for k,v in p.items() if k!="digest"}); return replace(row,**changes,digest=p["digest"])

class Tests(unittest.TestCase):
    def test_exact_matrix_and_range(self):
        e=populated().evidence(); self.assertEqual((e["control_count"],e["workstream_count"],e["controls_per_workstream"]),(400,16,25)); self.assertEqual(set(populated()._controls),set(range(4701,5101)))
    def test_partial_registry_fails(self):
        s=populated(False)
        with self.assertRaises(GovernanceRejected): s.anchor_source("synthetic:onboarding-anchor:x",d("m"),d("r"),d("l"),APPLIED_LESSONS,tuple((p,d(p)) for p in PARTIES),tuple((p,COMMON_OPERATIONS) for p in PARTIES),tuple((p,COMMON_TOKEN_CLASSES) for p in PARTIES),COMMON_OPERATIONS,COMMON_TOKEN_CLASSES,1,True,"synthetic:package-assembler:x")
    def test_control_idempotency_and_conflict(self):
        s=populated(False); row=next(iter(s._controls.values())); args={k:v for k,v in row.__dict__.items() if k!="digest"}; self.assertIs(s.add_control(**args),s.add_control(**args))
        with self.assertRaises(GovernanceRejected): s.add_control(**(args|{"fixture_digest":d("other")}))
    def test_anchor_idempotent(self):
        s,a=anchored(); args={k:v for k,v in a.__dict__.items() if k not in {"digest","status"}}; self.assertIs(s.anchor_source(**args),a)
    def test_anchor_requires_latest(self):
        s=populated()
        with self.assertRaises(GovernanceRejected): s.anchor_source("synthetic:onboarding-anchor:x",d("m"),d("r"),d("l"),APPLIED_LESSONS,tuple((p,d(p)) for p in PARTIES),tuple((p,COMMON_OPERATIONS) for p in PARTIES),tuple((p,COMMON_TOKEN_CLASSES) for p in PARTIES),COMMON_OPERATIONS,COMMON_TOKEN_CLASSES,6,False,"synthetic:package-assembler:x")
    def test_anchor_requires_all_lessons(self):
        s=populated()
        with self.assertRaises(GovernanceRejected): s.anchor_source("synthetic:onboarding-anchor:x",d("m"),d("r"),d("l"),APPLIED_LESSONS[:-1],tuple((p,d(p)) for p in PARTIES),tuple((p,COMMON_OPERATIONS) for p in PARTIES),tuple((p,COMMON_TOKEN_CLASSES) for p in PARTIES),COMMON_OPERATIONS,COMMON_TOKEN_CLASSES,7,True,"synthetic:package-assembler:x")
    def test_anchor_requires_profile_order_and_digests(self):
        s=populated()
        with self.assertRaises(GovernanceRejected): s.anchor_source("synthetic:onboarding-anchor:x",d("m"),d("r"),d("l"),APPLIED_LESSONS,(("NURION_PG",d("n")),),tuple((p,COMMON_OPERATIONS) for p in PARTIES),tuple((p,COMMON_TOKEN_CLASSES) for p in PARTIES),COMMON_OPERATIONS,COMMON_TOKEN_CLASSES,7,True,"synthetic:package-assembler:x")
    def test_anchor_recalculates_common_capability_intersection(self):
        s=populated(); operations=((PARTIES[0],COMMON_OPERATIONS),(PARTIES[1],COMMON_OPERATIONS),(PARTIES[2],("MAP","VALIDATE")))
        with self.assertRaises(GovernanceRejected):
            s.anchor_source("synthetic:onboarding-anchor:x",d("m"),d("r"),d("l"),APPLIED_LESSONS,tuple((p,d(p)) for p in PARTIES),operations,tuple((p,COMMON_TOKEN_CLASSES) for p in PARTIES),COMMON_OPERATIONS,COMMON_TOKEN_CLASSES,7,True,"synthetic:package-assembler:x")
    def test_anchor_profile_capability_rehash_tamper(self):
        s,a=anchored(); specs=((PARTIES[0],COMMON_OPERATIONS),(PARTIES[1],COMMON_OPERATIONS),(PARTIES[2],("MAP",)))
        s._anchor=rehash(a,capability_profile_operations=specs)
        self.assertFalse(s.evidence()["integrity_valid"])
    def test_common_capability_only(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected): s.add_plan("synthetic:rehearsal-plan:x",FLOWS[0],SCENARIOS[0],("EXECUTE",),COMMON_TOKEN_CLASSES)
    def test_unknown_flow_or_scenario(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected): s.add_plan("synthetic:rehearsal-plan:x","external",SCENARIOS[0],COMMON_OPERATIONS,COMMON_TOKEN_CLASSES)
    def test_plan_idempotency_conflict(self):
        s,_=anchored(); p=s.add_plan("synthetic:rehearsal-plan:x",FLOWS[0],SCENARIOS[0],COMMON_OPERATIONS,COMMON_TOKEN_CLASSES); self.assertIs(s.add_plan(p.plan_id,FLOWS[0],SCENARIOS[0],COMMON_OPERATIONS,COMMON_TOKEN_CLASSES),p)
        with self.assertRaises(GovernanceRejected): s.add_plan("synthetic:rehearsal-plan:other",FLOWS[0],SCENARIOS[0],COMMON_OPERATIONS,COMMON_TOKEN_CLASSES)
    def test_partial_plan_set_holds(self):
        s,_=anchored(); s.add_plan("synthetic:rehearsal-plan:x",FLOWS[0],SCENARIOS[0],COMMON_OPERATIONS,COMMON_TOKEN_CLASSES)
        with self.assertRaises(GovernanceRejected): s.run_rehearsal()
        self.assertEqual(s.evidence()["hold_count"],1)
    def test_exact_24_plans_and_results(self):
        s,_=planned(); self.assertEqual(len(s.run_rehearsal()),24); self.assertEqual((s.evidence()["plan_count"],s.evidence()["result_count"]),(24,24))
    def test_partial_batch_fails_closed(self):
        s,_=planned(); rows=s.run_rehearsal(); self.assertTrue(all(x.observed=="FAIL_CLOSED" for x in rows if "PARTIAL_BATCH" in x.result_id))
    def test_rehearsal_single_run(self):
        s,_=planned(); s.run_rehearsal()
        with self.assertRaises(GovernanceRejected): s.run_rehearsal()
    def test_review_requires_results(self):
        s,_=planned()
        with self.assertRaises(GovernanceRejected): s.review("synthetic:readiness-receipt:x","synthetic:readiness-reviewer:checker")
    def test_review_role_separation(self):
        s,_=planned(); s.run_rehearsal()
        with self.assertRaises(GovernanceRejected): s.review("synthetic:readiness-receipt:x","synthetic:readiness-reviewer:maker")
    def test_receipt_safe_maximum_state(self):
        r=completed()[2]; self.assertTrue(r.ready_for_operator_review); self.assertFalse(r.activation_recorded); self.assertFalse(r.deployment_recorded); self.assertEqual(r.status,"READY_FOR_OPERATOR_REVIEW_NOT_ACTIVATED")
    def test_control_semantic_rehash_tamper(self):
        s=populated(); row=s._controls[4701]; s._controls[4701]=rehash(row,workstream="WRONG"); self.assertFalse(s.evidence()["integrity_valid"])
    def test_anchor_package_source_rehash_tamper(self):
        s,a=anchored(); s._anchor=rehash(a,package_manifest_digest=d("substitute")); self.assertFalse(s.evidence()["integrity_valid"])
    def test_anchor_latest_rehash_tamper(self):
        s,a=anchored(); s._anchor=rehash(a,is_latest=False); self.assertFalse(s.evidence()["integrity_valid"])
    def test_anchor_lessons_rehash_tamper(self):
        s,a=anchored(); s._anchor=rehash(a,applied_lesson_ids=APPLIED_LESSONS[:-1]); self.assertFalse(s.evidence()["integrity_valid"])
    def test_anchor_common_capability_rehash_tamper(self):
        s,a=anchored(); s._anchor=rehash(a,common_operations=("MAP",)); self.assertFalse(s.evidence()["integrity_valid"])
    def test_plan_route_rehash_substitution(self):
        s,_=planned(); key=next(iter(s._plans)); s._plans[key]=rehash(s._plans[key],route_digest=d("forged")); self.assertFalse(s.evidence()["integrity_valid"])
    def test_plan_capability_rehash_substitution(self):
        s,_=planned(); key=next(iter(s._plans)); s._plans[key]=rehash(s._plans[key],capability_digest=d("forged")); self.assertFalse(s.evidence()["integrity_valid"])
    def test_result_external_call_rehash_tamper(self):
        s,_=planned(); s.run_rehearsal(); key=next(iter(s._results)); s._results[key]=rehash(s._results[key],external_calls=1); self.assertFalse(s.evidence()["integrity_valid"])
    def test_result_observed_rehash_tamper(self):
        s,_=planned(); s.run_rehearsal(); key=next(iter(s._results)); s._results[key]=rehash(s._results[key],observed="EXECUTED"); self.assertFalse(s.evidence()["integrity_valid"])
    def test_result_id_rehash_namespace_tamper(self):
        s,_=planned(); s.run_rehearsal(); key=next(iter(s._results)); s._results[key]=rehash(s._results[key],result_id="real:result"); self.assertFalse(s.evidence()["integrity_valid"])
    def test_receipt_activation_rehash_tamper(self):
        s,_,r=completed(); s._receipt=rehash(r,activation_recorded=True); self.assertFalse(s.evidence()["integrity_valid"])
    def test_receipt_deployment_rehash_tamper(self):
        s,_,r=completed(); s._receipt=rehash(r,deployment_recorded=True); self.assertFalse(s.evidence()["integrity_valid"])
    def test_receipt_maker_rehash_tamper(self):
        s,_,r=completed(); s._receipt=rehash(r,package_assembler="synthetic:package-assembler:attacker"); self.assertFalse(s.evidence()["integrity_valid"])
    def test_event_action_rehash_tamper(self):
        s,_=anchored(); x=s._events[0]|{"action":"ACTIVATED"}; x["digest"]=canonical_digest({k:v for k,v in x.items() if k!="digest"}); s._events[0]=x; self.assertFalse(s.evidence()["integrity_valid"])
    def test_event_artifact_rehash_substitution(self):
        s,_=anchored(); x=s._events[0]|{"artifact_digest":d("substitute")}; x["digest"]=canonical_digest({k:v for k,v in x.items() if k!="digest"}); s._events[0]=x; self.assertFalse(s.evidence()["integrity_valid"])
    def test_concurrent_control_converges(self):
        s=SyntheticOnboardingRehearsalReadiness(); args=(4701,WORKSTREAMS[0][2],CONTROL_ASPECTS[0],"synthetic:onboarding-requirement:00",d("f"),"PASS")
        with ThreadPoolExecutor(max_workers=8) as pool: rows=list(pool.map(lambda _:s.add_control(*args),range(20)))
        self.assertEqual(len({x.digest for x in rows}),1)
    def test_complete_evidence(self):
        e=completed()[0].evidence(); self.assertTrue(e["capability_ready"]); self.assertTrue(e["complete_readiness_evidence"]); self.assertEqual((e["plan_count"],e["result_count"]),(24,24))
    def test_non_execution_boundary(self):
        e=completed()[0].evidence(); keys=("external_calls","document_transmissions","electronic_signatures","external_pg_calls","card_network_calls","payment_approvals","cancellations","refunds","settlements","transfers","ledger_writes","credential_reads","deployments","policy_prompt_weight_changes"); self.assertEqual(tuple(e[k] for k in keys),(0,)*len(keys)); self.assertFalse(e["activation_recorded"]); self.assertFalse(e["release_recorded"])

if __name__ == "__main__": unittest.main()
