from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from hashlib import sha256
import unittest

from nurion_pg.arkaon.governance import GovernanceRejected,canonical_digest
from nurion_pg.synthetic_approval_intent_envelope_gate import *
from tests.test_synthetic_observation_readiness_manifest import completed as prior_completed

def d(v):return sha256(v.encode()).hexdigest()
def populated():
    s=SyntheticApprovalIntentEnvelopeGate()
    for cid in range(14301,14701):
        w,a=s._expected(cid);s.add_control(cid,w,a,f"synthetic:intent-requirement:{(cid-14301)//25:02}",d(str(cid)),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    return s
def anchored():
    p=prior_completed()[0];s=populated();s.anchor(p,mapping_digest(STAGE_MAPPING),d("registry"),d("manifest"),APPLIED_LESSONS,APPLIED_RULES,p._snapshot.digest,32,True);return s,p
def enveloped():
    s,p=anchored()
    for i,key in enumerate(CASE_KEYS):
        routed=p._plans[key].pending_human_judgment
        for j,intent in enumerate(("MATERIALIZATION","EXECUTION")):
            args=(f"synthetic:approval-intent-envelope:{key[0]}:{key[1]}:{intent.lower()}",*key,intent)
            if routed:s.add_envelope(*args,f"synthetic:approval-intent-actor:a-{i}-{j}",f"synthetic:approval-intent-counter-actor:c-{i}-{j}")
            else:s.add_envelope(*args)
    return s,p
def completed():
    s,p=enveloped();s.finalize("synthetic:intent-docket:final","synthetic:intent-docket-compiler:final-c","synthetic:intent-docket-validator:final-v");return s,p
FIELDS=tuple(Envelope.__dataclass_fields__)[:-1]
def full_rehash(s,start,changes):
    keys=list(s._envelopes)
    for i in range(start,len(keys)):
        key=keys[i];r=s._envelopes[key];v={**r.__dict__,**(changes if i==start else {})};v["parent_digest"]=None if i==0 else s._envelopes[keys[i-1]].digest
        if i!=start and r.intent_kind=="EXECUTION":v["prior_intent_digest"]=s._envelopes[(r.flow,r.kind,"MATERIALIZATION")].digest
        v["digest"]=canonical_digest(("APPROVAL_INTENT_ENVELOPE",tuple(v[k] for k in FIELDS)));s._envelopes[key]=replace(r,**v)
    s._events=[];s._holds=[];s._event("INTENT_CHAIN_ANCHORED",s._snapshot.digest)
    for r in s._envelopes.values():
        s._event("PENDING_INTENT_RECORDED",r.digest)
        if r.actor:s._hold(f"{r.intent_kind}_APPROVAL_PENDING",r.digest)
    if s._docket:
        r=s._docket;p={**r.__dict__,"envelope_set_digest":canonical_digest(tuple(x.digest for x in s._envelopes.values()))};p.pop("digest");s._docket=replace(r,envelope_set_digest=p["envelope_set_digest"],digest=canonical_digest(p));s._event("APPROVAL_INTENT_DOCKET_HELD",s._docket.digest)

class Tests(unittest.TestCase):
    def test_matrix_exactly_400(self):self.assertEqual((len(WORKSTREAMS),len(populated()._controls),WORKSTREAMS[0][0],WORKSTREAMS[-1][1]),(16,400,14301,14700))
    def test_control_concurrency_idempotent(self):
        s=SyntheticApprovalIntentEnvelopeGate();args=(14301,WORKSTREAM_NAMES[0],CONTROL_ASPECTS[0],"synthetic:intent-requirement:00",d("x"),"PASS")
        with ThreadPoolExecutor(max_workers=8) as pool:rows=list(pool.map(lambda _:s.add_control(*args),range(20)))
        self.assertEqual(len({x.digest for x in rows}),1)
    def test_envelope_concurrency_idempotent(self):
        s,_=anchored();args=("synthetic:approval-intent-envelope:na",*CASE_KEYS[0],"MATERIALIZATION")
        with ThreadPoolExecutor(max_workers=8) as pool:rows=list(pool.map(lambda _:s.add_envelope(*args),range(20)))
        self.assertEqual((len(s._envelopes),len({x.digest for x in rows})),(1,1))
    def test_routed_materialization_concurrency_idempotent(self):
        s,_=anchored();s.add_envelope("synthetic:approval-intent-envelope:na-m",*CASE_KEYS[0],"MATERIALIZATION");s.add_envelope("synthetic:approval-intent-envelope:na-e",*CASE_KEYS[0],"EXECUTION");args=("synthetic:approval-intent-envelope:routed-m",*CASE_KEYS[1],"MATERIALIZATION","synthetic:approval-intent-actor:concurrent-routed-m-a","synthetic:approval-intent-counter-actor:concurrent-routed-m-c")
        with ThreadPoolExecutor(max_workers=8) as pool:rows=list(pool.map(lambda _:s.add_envelope(*args),range(20)))
        self.assertEqual((len(s._envelopes),len({id(x) for x in rows})),(3,1))
    def test_routed_execution_concurrency_idempotent(self):
        s,_=anchored();s.add_envelope("synthetic:approval-intent-envelope:na-m",*CASE_KEYS[0],"MATERIALIZATION");s.add_envelope("synthetic:approval-intent-envelope:na-e",*CASE_KEYS[0],"EXECUTION");key=CASE_KEYS[1];s.add_envelope("synthetic:approval-intent-envelope:routed-m",*key,"MATERIALIZATION","synthetic:approval-intent-actor:concurrent-routed-m-a","synthetic:approval-intent-counter-actor:concurrent-routed-m-c");args=("synthetic:approval-intent-envelope:routed-e",*key,"EXECUTION","synthetic:approval-intent-actor:concurrent-routed-e-a","synthetic:approval-intent-counter-actor:concurrent-routed-e-c")
        with ThreadPoolExecutor(max_workers=8) as pool:rows=list(pool.map(lambda _:s.add_envelope(*args),range(20)))
        self.assertEqual((len(s._envelopes),len({id(x) for x in rows})),(4,1))
    def test_same_key_envelope_id_or_actor_conflict_rejected(self):
        s,_=anchored();s.add_envelope("synthetic:approval-intent-envelope:na-m",*CASE_KEYS[0],"MATERIALIZATION");s.add_envelope("synthetic:approval-intent-envelope:na-e",*CASE_KEYS[0],"EXECUTION");key=CASE_KEYS[1];args=("synthetic:approval-intent-envelope:routed-m",*key,"MATERIALIZATION","synthetic:approval-intent-actor:conflict-a","synthetic:approval-intent-counter-actor:conflict-c");s.add_envelope(*args)
        with self.assertRaisesRegex(GovernanceRejected,"envelope conflict"):s.add_envelope("synthetic:approval-intent-envelope:changed",*key,"MATERIALIZATION",args[-2],args[-1])
        with self.assertRaisesRegex(GovernanceRejected,"envelope conflict"):s.add_envelope(args[0],*key,"MATERIALIZATION","synthetic:approval-intent-actor:changed-a",args[-1])
    def test_other_key_envelope_id_reuse_api_rejected(self):
        s,_=anchored();shared="synthetic:approval-intent-envelope:shared";s.add_envelope(shared,*CASE_KEYS[0],"MATERIALIZATION");s.add_envelope("synthetic:approval-intent-envelope:na-e",*CASE_KEYS[0],"EXECUTION")
        with self.assertRaises(GovernanceRejected):s.add_envelope(shared,*CASE_KEYS[1],"MATERIALIZATION","synthetic:approval-intent-actor:other-key-a","synthetic:approval-intent-counter-actor:other-key-c")
    def test_latest_required(self):
        p=prior_completed()[0]
        with self.assertRaises(GovernanceRejected):populated().anchor(p,mapping_digest(STAGE_MAPPING),d("r"),d("m"),APPLIED_LESSONS,APPLIED_RULES,p._snapshot.digest,32,False)
    def test_order_and_partial_batch_fail_closed(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected):s.add_envelope("synthetic:approval-intent-envelope:x",*CASE_KEYS[0],"EXECUTION")
        with self.assertRaises(GovernanceRejected):s.finalize("synthetic:intent-docket:x","synthetic:intent-docket-compiler:c","synthetic:intent-docket-validator:v")
    def test_counts_identity_and_pending_state(self):
        s,_=completed();e=s.evidence();self.assertEqual((e["envelope_count"],e["materialization_intent_count"],e["execution_intent_count"],e["recovery_path_count"],e["human_judgment_hold_count"]),(40,20,20,64,32));r=s._envelopes[(*CASE_KEYS[1],"EXECUTION")];self.assertEqual((r.state,r.receipt_issued,r.materialized,r.executed),("PENDING_NOT_ISSUED",False,False,False))
    def test_plan_identity_substitution_full_rehash_rejected(self):
        s,_=completed();full_rehash(s,2,{"plan_id":"synthetic:readiness-plan:substitute"});self.assertFalse(s.evidence()["integrity_valid"])
    def test_flow_kind_substitution_full_rehash_rejected(self):
        s,_=completed();full_rehash(s,2,{"flow":"ATTACKER","kind":"ATTACKER"});self.assertFalse(s.evidence()["integrity_valid"])
    def test_manifest_digest_substitution_full_rehash_rejected(self):
        s,_=completed();full_rehash(s,2,{"readiness_manifest_digest":d("substitute")});self.assertFalse(s.evidence()["integrity_valid"])
    def test_composite_identity_substitution_full_rehash_rejected(self):
        s,_=completed();full_rehash(s,2,{"composite_identity_digest":d("substitute")});self.assertFalse(s.evidence()["integrity_valid"])
    def test_cross_kind_actor_reuse_rejected(self):
        s,p=anchored();s.add_envelope("synthetic:approval-intent-envelope:na-m",*CASE_KEYS[0],"MATERIALIZATION");s.add_envelope("synthetic:approval-intent-envelope:na-e",*CASE_KEYS[0],"EXECUTION");key=CASE_KEYS[1];s.add_envelope("synthetic:approval-intent-envelope:m",*key,"MATERIALIZATION","synthetic:approval-intent-actor:reuse-unique-actor","synthetic:approval-intent-counter-actor:reuse-unique-counter")
        with self.assertRaises(GovernanceRejected):s.add_envelope("synthetic:approval-intent-envelope:e",*key,"EXECUTION","synthetic:approval-intent-actor:reuse-unique-actor","synthetic:approval-intent-counter-actor:reuse-second-counter")
    def test_materialization_execution_sequence_swap_full_rehash_rejected(self):
        s,_=completed();full_rehash(s,2,{"sequence_precondition":4});self.assertFalse(s.evidence()["integrity_valid"])
    def test_prior_intent_removed_full_rehash_rejected(self):
        s,_=completed();full_rehash(s,3,{"prior_intent_digest":None});self.assertFalse(s.evidence()["integrity_valid"])
    def test_nonce_replay_full_rehash_rejected(self):
        s,_=completed();full_rehash(s,3,{"nonce_scope_digest":s._envelopes[list(s._envelopes)[2]].nonce_scope_digest});self.assertFalse(s.evidence()["integrity_valid"])
    def test_receipt_issue_forgery_full_rehash_rejected(self):
        s,_=completed();full_rehash(s,2,{"receipt_issued":True,"state":"ISSUED"});self.assertFalse(s.evidence()["integrity_valid"])
    def test_single_recovery_path_full_rehash_rejected(self):
        s,_=completed();r=s._envelopes[list(s._envelopes)[2]];full_rehash(s,2,{"recovery_paths":r.recovery_paths[:1]});self.assertFalse(s.evidence()["integrity_valid"])
    def test_source_plan_full_downstream_rehash_rejected(self):
        s,p=completed();key=CASE_KEYS[1];r=p._plans[key];p._plans[key]=replace(r,plan_id="synthetic:readiness-plan:attacker",digest=d("attacker"));full_rehash(s,2,{"plan_id":p._plans[key].plan_id,"readiness_manifest_digest":p._plans[key].digest,"composite_identity_digest":composite_identity(p._plans[key])});self.assertFalse(s.evidence()["integrity_valid"])
    def test_docket_invariant_interface_full_rehash_rejected(self):
        s,_=completed();r=s._docket;p={**r.__dict__,"approved":True,"status":"APPROVED"};p.pop("digest");s._docket=replace(r,approved=True,status="APPROVED",digest=canonical_digest(p));s._events[-1]["artifact_digest"]=s._docket.digest;ep={k:s._events[-1][k] for k in ("sequence","action","artifact_digest","previous_digest")};s._events[-1]["digest"]=canonical_digest(ep);self.assertFalse(s.evidence()["integrity_valid"])
    def test_event_hold_and_actor_tamper_rejected(self):
        s,_=completed();s._events[1]["artifact_digest"]=d("bad");self.assertFalse(s.evidence()["integrity_valid"]);s,_=completed();s._holds.pop();self.assertFalse(s.evidence()["integrity_valid"])
    def test_no_execution_receipt_or_authority(self):
        e=completed()[0].evidence();self.assertTrue(e["complete_approval_intent_envelope_gate_evidence"]);self.assertFalse(any(e[k] for k in ("judgment_authority","recommendation_authority","selection_authority","acceptance_authority","resolution_authority","approved","materialized","executed","passed","failed","activated")));self.assertEqual(tuple(e[k] for k in ("approval_receipts_issued","fixture_materializations","probe_executions","observation_values","external_calls","external_pg_calls","ledger_writes","credential_reads","deployments")),(0,)*9)

if __name__=="__main__":unittest.main()
