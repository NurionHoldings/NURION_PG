from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from hashlib import sha256
import unittest

from nurion_pg.arkaon.governance import GovernanceRejected,canonical_digest
from nurion_pg.synthetic_observation_contract_gate import *
from tests.test_synthetic_recovery_preflight_audit import completed as prior_completed

def d(v):return sha256(v.encode()).hexdigest()
def populated():
    s=SyntheticObservationContractGate()
    for cid in range(13501,13901):
        w,a=s._expected(cid);s.add_control(cid,w,a,f"synthetic:observation-contract-requirement:{(cid-13501)//25:02}",d(str(cid)),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    return s
def anchored():
    p=prior_completed()[0];s=populated();s.anchor(p,mapping_digest(STAGE_MAPPING),d("registry"),d("manifest"),APPLIED_LESSONS,APPLIED_RULES,p._snapshot.digest,30,True);return s,p
def contracted():
    s,p=anchored()
    for i,key in enumerate(CASE_KEYS):
        args=(f"synthetic:observation-contract:{key[0]}:{key[1]}",*key)
        if p._audits[key].pending_human_judgment:s.add_contract(*args,f"synthetic:observation-contract-author:oca-{i}",f"synthetic:observation-contract-verifier:ocv-{i}")
        else:s.add_contract(*args)
    return s,p
def completed():
    s,p=contracted();s.finalize("synthetic:observation-docket:final","synthetic:observation-docket-compiler:occ-final","synthetic:observation-docket-validator:ocv-final");return s,p
def full_rehash(s,start,changes):
    fields=("contract_id","flow","kind","source_audit_digest","fixture_identity","input_identity","expected_outcome","observation_status","observed_outcome","evidence_completeness","verifier_gate","ambiguous_policy","contradictory_policy","recovery_paths","author","verifier","parent_digest","position","held","pending_human_judgment","passed","failed")
    for i in range(start,len(CASE_KEYS)):
        key=CASE_KEYS[i];r=s._contracts[key];v={**r.__dict__,**(changes if i==start else {})};v["parent_digest"]=None if i==0 else s._contracts[CASE_KEYS[i-1]].digest;v["digest"]=canonical_digest(("OBSERVATION_CONTRACT",tuple(v[k] for k in fields)));s._contracts[key]=replace(r,**{k:x for k,x in v.items() if k in r.__dict__})
    s._events=[];s._holds=[];s._event("OBSERVATION_CONTRACT_CHAIN_ANCHORED",s._snapshot.digest)
    for r in s._contracts.values():
        s._event("OBSERVATION_CONTRACT_RECORDED",r.digest)
        if r.pending_human_judgment:s._hold("OBSERVATION_NOT_RUN_HUMAN_GATE_REQUIRED",r.digest)
    if s._docket:
        r=s._docket;cset=canonical_digest(tuple(s._contracts[k].digest for k in CASE_KEYS));p={**r.__dict__,"contract_set_digest":cset};p.pop("digest");s._docket=replace(r,contract_set_digest=cset,digest=canonical_digest(p));s._event("OBSERVATION_CONTRACT_DOCKET_HELD",s._docket.digest)
def docket_full_rehash(s,**changes):
    r=s._docket;p={**r.__dict__,**changes};p.pop("digest");s._docket=replace(r,**changes,digest=canonical_digest(p));s._events[-1]={"sequence":len(s._events),"action":"OBSERVATION_CONTRACT_DOCKET_HELD","artifact_digest":s._docket.digest,"previous_digest":s._events[-2]["digest"]};e=s._events[-1];e["digest"]=canonical_digest({k:e[k] for k in ("sequence","action","artifact_digest","previous_digest")})

class Tests(unittest.TestCase):
    def test_matrix_exactly_400(self):self.assertEqual((len(WORKSTREAMS),len(populated()._controls),WORKSTREAMS[0][0],WORKSTREAMS[-1][1]),(16,400,13501,13900))
    def test_wrong_control_rejected(self):
        with self.assertRaises(GovernanceRejected):SyntheticObservationContractGate().add_control(13501,"BAD",CONTROL_ASPECTS[0],"synthetic:observation-contract-requirement:00",d("x"),"PASS")
    def test_control_concurrency_idempotent(self):
        s=SyntheticObservationContractGate();args=(13501,WORKSTREAM_NAMES[0],CONTROL_ASPECTS[0],"synthetic:observation-contract-requirement:00",d("x"),"PASS")
        with ThreadPoolExecutor(max_workers=8) as pool:rows=list(pool.map(lambda _:s.add_control(*args),range(20)))
        self.assertEqual(len({x.digest for x in rows}),1)
    def test_latest_required(self):
        p=prior_completed()[0]
        with self.assertRaises(GovernanceRejected):populated().anchor(p,mapping_digest(STAGE_MAPPING),d("r"),d("m"),APPLIED_LESSONS,APPLIED_RULES,p._snapshot.digest,30,False)
    def test_partial_batch_fail_closed(self):
        with self.assertRaises(GovernanceRejected):anchored()[0].finalize("synthetic:observation-docket:x","synthetic:observation-docket-compiler:c","synthetic:observation-docket-validator:v")
    def test_immediate_parent_required(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected):s.add_contract("synthetic:observation-contract:x",*CASE_KEYS[1],"synthetic:observation-contract-author:a","synthetic:observation-contract-verifier:v")
    def test_na_forbids_actors(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected):s.add_contract("synthetic:observation-contract:x",*CASE_KEYS[0],"synthetic:observation-contract-author:a","synthetic:observation-contract-verifier:v")
    def test_contract_counts_and_semantics(self):
        s,_=completed();e=s.evidence();self.assertEqual((e["contract_count"],e["content_free_fixture_count"],e["recovery_path_count"],e["not_run_count"],e["human_judgment_hold_count"]),(20,16,32,16,16));r=s._contracts[CASE_KEYS[1]];self.assertEqual((r.observation_status,r.observed_outcome,r.evidence_completeness,r.verifier_gate),("NOT_RUN",None,False,"PENDING_NOT_EXECUTED"));self.assertIn("PASS_REQUIRES",r.expected_outcome[2]);self.assertEqual(r.ambiguous_policy[1],"HOLD");self.assertEqual(r.contradictory_policy[1],"HOLD")
    def test_forged_pass_full_rehash_rejected(self):
        s,_=completed();full_rehash(s,1,{"observation_status":"COMPLETE","observed_outcome":"PASS","evidence_completeness":True,"verifier_gate":"PASS","passed":True});self.assertFalse(s.evidence()["integrity_valid"])
    def test_forged_fail_full_rehash_rejected(self):
        s,_=completed();full_rehash(s,1,{"observation_status":"COMPLETE","observed_outcome":"FAIL","evidence_completeness":True,"verifier_gate":"PASS","failed":True});self.assertFalse(s.evidence()["integrity_valid"])
    def test_fixture_identity_rebind_full_rehash_rejected(self):
        s,_=completed();r=s._contracts[CASE_KEYS[1]];f=list(r.fixture_identity);f[2]=d("attacker");full_rehash(s,1,{"fixture_identity":tuple(f)});self.assertFalse(s.evidence()["integrity_valid"])
    def test_expected_outcome_removed_full_rehash_rejected(self):
        s,_=completed();full_rehash(s,1,{"expected_outcome":None});self.assertFalse(s.evidence()["integrity_valid"])
    def test_ambiguous_policy_removed_full_rehash_rejected(self):
        s,_=completed();full_rehash(s,1,{"ambiguous_policy":None});self.assertFalse(s.evidence()["integrity_valid"])
    def test_contradictory_promoted_full_rehash_rejected(self):
        s,_=completed();full_rehash(s,1,{"contradictory_policy":("contradictory_result","PASS")});self.assertFalse(s.evidence()["integrity_valid"])
    def test_single_recovery_path_full_rehash_rejected(self):
        s,_=completed();r=s._contracts[CASE_KEYS[1]];full_rehash(s,1,{"recovery_paths":r.recovery_paths[:1]});self.assertFalse(s.evidence()["integrity_valid"])
    def test_source_full_downstream_rehash_rejected(self):
        s,p=completed();key=CASE_KEYS[1];old=p._audits[key];p._audits[key]=replace(old,marker="ATTACKER",digest=d("attacker"));fixture,inputs,expected,ambiguous,contradictory,paths=observation_terms(p._audits[key],*key,s._snapshot.digest);full_rehash(s,1,{"source_audit_digest":p._audits[key].digest,"fixture_identity":fixture,"input_identity":inputs,"expected_outcome":expected,"ambiguous_policy":ambiguous,"contradictory_policy":contradictory,"recovery_paths":paths});self.assertFalse(s.evidence()["integrity_valid"])
    def test_event_and_hold_tamper_rejected(self):
        s,_=completed();s._events[1]["artifact_digest"]=d("bad");self.assertFalse(s.evidence()["integrity_valid"]);s,_=completed();s._holds.pop();self.assertFalse(s.evidence()["integrity_valid"])
    def test_final_actor_reuse_rejected(self):
        s,_=contracted()
        with self.assertRaises(GovernanceRejected):s.finalize("synthetic:observation-docket:x","synthetic:observation-docket-compiler:oca-1","synthetic:observation-docket-validator:v")
    def test_docket_compiler_namespace_full_rehash_rejected(self):
        s,_=completed();docket_full_rehash(s,compiler="synthetic:attacker:occ-final");self.assertFalse(s.evidence()["integrity_valid"])
    def test_docket_validator_namespace_full_rehash_rejected(self):
        s,_=completed();docket_full_rehash(s,validator="synthetic:attacker:ocv-final");self.assertFalse(s.evidence()["integrity_valid"])
    def test_docket_id_namespace_full_rehash_rejected(self):
        s,_=completed();docket_full_rehash(s,docket_id="synthetic:attacker:final");self.assertFalse(s.evidence()["integrity_valid"])
    def test_docket_status_full_rehash_rejected(self):
        s,_=completed();docket_full_rehash(s,status="OBSERVATION_CONTRACT_DOCKET_COMPLETE");self.assertFalse(s.evidence()["integrity_valid"])
    def test_docket_held_full_rehash_rejected(self):
        s,_=completed();docket_full_rehash(s,held=False);self.assertFalse(s.evidence()["integrity_valid"])
    def test_docket_complete_full_rehash_rejected(self):
        s,_=completed();docket_full_rehash(s,complete=False);self.assertFalse(s.evidence()["integrity_valid"])
    def test_docket_pending_full_rehash_rejected(self):
        s,_=completed();docket_full_rehash(s,pending_human_judgment=False);self.assertFalse(s.evidence()["integrity_valid"])
    def test_docket_passed_full_rehash_rejected(self):
        s,_=completed();docket_full_rehash(s,passed=True);self.assertFalse(s.evidence()["integrity_valid"])
    def test_docket_failed_full_rehash_rejected(self):
        s,_=completed();docket_full_rehash(s,failed=True);self.assertFalse(s.evidence()["integrity_valid"])
    def test_non_execution_and_no_authority(self):
        e=completed()[0].evidence();self.assertTrue(e["complete_observation_contract_gate_evidence"]);self.assertFalse(any(e[k] for k in ("judgment_authority","passed","failed","ranked","selected","concluded","recommended","accepted","resolved","approved","activated")));keys=("probe_executions","observation_values","external_calls","external_pg_calls","card_network_calls","payment_approvals","ledger_writes","credential_reads","deployments");self.assertEqual(tuple(e[k] for k in keys),(0,)*len(keys))

if __name__=="__main__":unittest.main()
