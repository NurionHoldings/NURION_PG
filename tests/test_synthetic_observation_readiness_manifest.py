from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from hashlib import sha256
import unittest

from nurion_pg.arkaon.governance import GovernanceRejected,canonical_digest
from nurion_pg.synthetic_observation_readiness_manifest import *
from tests.test_synthetic_observation_contract_gate import completed as prior_completed

def d(v):return sha256(v.encode()).hexdigest()
def populated():
    s=SyntheticObservationReadinessManifest()
    for cid in range(13901,14301):
        w,a=s._expected(cid);s.add_control(cid,w,a,f"synthetic:readiness-requirement:{(cid-13901)//25:02}",d(str(cid)),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    return s
def anchored():
    p=prior_completed()[0];s=populated();s.anchor(p,mapping_digest(STAGE_MAPPING),d("registry"),d("manifest"),APPLIED_LESSONS,APPLIED_RULES,p._snapshot.digest,31,True);return s,p
def planned():
    s,p=anchored()
    for i,key in enumerate(CASE_KEYS):
        args=(f"synthetic:readiness-plan:{key[0]}:{key[1]}",*key)
        if p._contracts[key].pending_human_judgment:s.add_plan(*args,f"synthetic:readiness-planner:rp-{i}",f"synthetic:readiness-challenger:rc-{i}")
        else:s.add_plan(*args)
    return s,p
def completed():
    s,p=planned();s.finalize("synthetic:readiness-docket:final","synthetic:readiness-docket-compiler:rdc-final","synthetic:readiness-docket-validator:rdv-final");return s,p
FIELDS=("plan_id","flow","kind","source_contract_digest","manifest_identity","resource_budget","privacy_classification","data_classification","determinism","isolation","timeout_policy","side_effect_policy","receipt_schema","approval_gate","recovery_paths","planner","challenger","parent_digest","position","status","held","pending_human_judgment","materialized","executed")
def full_rehash(s,start,changes):
    for i in range(start,len(CASE_KEYS)):
        key=CASE_KEYS[i];r=s._plans[key];v={**r.__dict__,**(changes if i==start else {})};v["parent_digest"]=None if i==0 else s._plans[CASE_KEYS[i-1]].digest;v["digest"]=canonical_digest(("READINESS_PLAN",tuple(v[k] for k in FIELDS)));s._plans[key]=replace(r,**{k:x for k,x in v.items() if k in r.__dict__})
    s._events=[];s._holds=[];s._event("READINESS_CHAIN_ANCHORED",s._snapshot.digest)
    for r in s._plans.values():
        s._event("READINESS_PLAN_RECORDED",r.digest)
        if r.pending_human_judgment:s._hold("MATERIALIZATION_AND_EXECUTION_APPROVAL_PENDING",r.digest)
    if s._docket:
        r=s._docket;p={**r.__dict__,"plan_set_digest":canonical_digest(tuple(s._plans[k].digest for k in CASE_KEYS))};p.pop("digest");s._docket=replace(r,plan_set_digest=p["plan_set_digest"],digest=canonical_digest(p));s._event("READINESS_DOCKET_HELD",s._docket.digest)

class Tests(unittest.TestCase):
    def test_matrix_exactly_400(self):self.assertEqual((len(WORKSTREAMS),len(populated()._controls),WORKSTREAMS[0][0],WORKSTREAMS[-1][1]),(16,400,13901,14300))
    def test_control_concurrency_idempotent(self):
        s=SyntheticObservationReadinessManifest();args=(13901,WORKSTREAM_NAMES[0],CONTROL_ASPECTS[0],"synthetic:readiness-requirement:00",d("x"),"PASS")
        with ThreadPoolExecutor(max_workers=8) as pool:rows=list(pool.map(lambda _:s.add_control(*args),range(20)))
        self.assertEqual(len({x.digest for x in rows}),1)
    def test_plan_concurrency_idempotent(self):
        s,_=anchored();args=("synthetic:readiness-plan:na-concurrent",*CASE_KEYS[0])
        with ThreadPoolExecutor(max_workers=8) as pool:rows=list(pool.map(lambda _:s.add_plan(*args),range(20)))
        self.assertEqual((len(s._plans),len({x.digest for x in rows})),(1,1))
    def test_duplicate_plan_id_other_key_rejected(self):
        s,p=anchored();pid="synthetic:readiness-plan:duplicate";s.add_plan(pid,*CASE_KEYS[0]);key=CASE_KEYS[1]
        with self.assertRaises(GovernanceRejected):s.add_plan(pid,*key,"synthetic:readiness-planner:dup-p","synthetic:readiness-challenger:dup-c")
    def test_latest_required(self):
        p=prior_completed()[0]
        with self.assertRaises(GovernanceRejected):populated().anchor(p,mapping_digest(STAGE_MAPPING),d("r"),d("m"),APPLIED_LESSONS,APPLIED_RULES,p._snapshot.digest,31,False)
    def test_partial_batch_fail_closed(self):
        with self.assertRaises(GovernanceRejected):anchored()[0].finalize("synthetic:readiness-docket:x","synthetic:readiness-docket-compiler:c","synthetic:readiness-docket-validator:v")
    def test_immediate_parent_required(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected):s.add_plan("synthetic:readiness-plan:x",*CASE_KEYS[1],"synthetic:readiness-planner:a","synthetic:readiness-challenger:b")
    def test_na_forbids_actors(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected):s.add_plan("synthetic:readiness-plan:x",*CASE_KEYS[0],"synthetic:readiness-planner:a","synthetic:readiness-challenger:b")
    def test_readiness_counts_and_semantics(self):
        s,_=completed();e=s.evidence();self.assertEqual((e["plan_count"],e["bound_manifest_count"],e["recovery_path_count"],e["human_judgment_hold_count"]),(20,16,32,16));r=s._plans[CASE_KEYS[1]];self.assertEqual((r.status,r.materialized,r.executed,r.approval_gate[-1]),("PLANNED_NOT_MATERIALIZED_NOT_EXECUTED",False,False,"PENDING"))
    def test_resource_budget_removed_full_rehash_rejected(self):
        s,_=completed();full_rehash(s,1,{"resource_budget":None});self.assertFalse(s.evidence()["integrity_valid"])
    def test_privacy_downgrade_full_rehash_rejected(self):
        s,_=completed();full_rehash(s,1,{"privacy_classification":("PUBLIC",)});self.assertFalse(s.evidence()["integrity_valid"])
    def test_determinism_removed_full_rehash_rejected(self):
        s,_=completed();full_rehash(s,1,{"determinism":None});self.assertFalse(s.evidence()["integrity_valid"])
    def test_isolation_relaxed_full_rehash_rejected(self):
        s,_=completed();full_rehash(s,1,{"isolation":("NETWORK_ALLOWED",)});self.assertFalse(s.evidence()["integrity_valid"])
    def test_timeout_removed_full_rehash_rejected(self):
        s,_=completed();full_rehash(s,1,{"timeout_policy":None});self.assertFalse(s.evidence()["integrity_valid"])
    def test_side_effect_permission_full_rehash_rejected(self):
        s,_=completed();full_rehash(s,1,{"side_effect_policy":("PG_ALLOWED",)});self.assertFalse(s.evidence()["integrity_valid"])
    def test_receipt_schema_observation_value_full_rehash_rejected(self):
        s,_=completed();full_rehash(s,1,{"receipt_schema":("PLAN_RECEIPT_V1",("observation_value",))});self.assertFalse(s.evidence()["integrity_valid"])
    def test_approval_gate_bypass_full_rehash_rejected(self):
        s,_=completed();full_rehash(s,1,{"approval_gate":("AUTO_APPROVED",)});self.assertFalse(s.evidence()["integrity_valid"])
    def test_materialization_forgery_full_rehash_rejected(self):
        s,_=completed();full_rehash(s,1,{"materialized":True,"status":"MATERIALIZED"});self.assertFalse(s.evidence()["integrity_valid"])
    def test_execution_forgery_full_rehash_rejected(self):
        s,_=completed();full_rehash(s,1,{"executed":True,"status":"EXECUTED"});self.assertFalse(s.evidence()["integrity_valid"])
    def test_duplicate_plan_id_full_downstream_rehash_rejected(self):
        s,_=completed();full_rehash(s,2,{"plan_id":s._plans[CASE_KEYS[1]].plan_id});e=s.evidence();self.assertFalse(e["integrity_valid"]);self.assertFalse(e["complete_observation_readiness_manifest_evidence"])
    def test_single_recovery_path_full_rehash_rejected(self):
        s,_=completed();r=s._plans[CASE_KEYS[1]];full_rehash(s,1,{"recovery_paths":r.recovery_paths[:1]});self.assertFalse(s.evidence()["integrity_valid"])
    def test_source_contract_full_downstream_rehash_rejected(self):
        s,p=completed();key=CASE_KEYS[1];old=p._contracts[key];p._contracts[key]=replace(old,observation_status="ATTACKER",digest=d("attacker"));terms=readiness_terms(p._contracts[key],*key,s._snapshot.digest);full_rehash(s,1,{"source_contract_digest":p._contracts[key].digest,**dict(zip(("manifest_identity","resource_budget","privacy_classification","data_classification","determinism","isolation","timeout_policy","side_effect_policy","receipt_schema","approval_gate","recovery_paths"),terms))});self.assertFalse(s.evidence()["integrity_valid"])
    def test_event_and_hold_tamper_rejected(self):
        s,_=completed();s._events[1]["artifact_digest"]=d("bad");self.assertFalse(s.evidence()["integrity_valid"]);s,_=completed();s._holds.pop();self.assertFalse(s.evidence()["integrity_valid"])
    def test_final_actor_reuse_rejected(self):
        s,_=planned()
        with self.assertRaises(GovernanceRejected):s.finalize("synthetic:readiness-docket:x","synthetic:readiness-docket-compiler:rp-1","synthetic:readiness-docket-validator:v")
    def test_non_execution_and_no_authority(self):
        e=completed()[0].evidence();self.assertTrue(e["complete_observation_readiness_manifest_evidence"]);self.assertFalse(any(e[k] for k in ("judgment_authority","materialized","executed","passed","failed","approved","activated")));self.assertEqual(tuple(e[k] for k in ("fixture_materializations","probe_executions","observation_values","external_calls","external_pg_calls","ledger_writes","credential_reads","deployments")),(0,)*8)

if __name__=="__main__":unittest.main()
