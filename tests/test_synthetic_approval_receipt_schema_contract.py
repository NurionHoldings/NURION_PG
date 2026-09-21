from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from hashlib import sha256
import unittest

from nurion_pg.arkaon.governance import GovernanceRejected,canonical_digest
from nurion_pg.synthetic_approval_receipt_schema_contract import *
from tests.test_synthetic_approval_intent_envelope_gate import completed as prior_completed

def d(v):return sha256(v.encode()).hexdigest()
def populated():
    s=SyntheticApprovalReceiptSchemaContract()
    for cid in range(14701,15101):
        w,a=s._expected(cid);s.add_control(cid,w,a,f"synthetic:receipt-schema-requirement:{(cid-14701)//25:02}",d(str(cid)),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    return s
def anchored():
    p=prior_completed()[0];s=populated();s.anchor(p,mapping_digest(STAGE_MAPPING),d("registry"),d("manifest"),APPLIED_LESSONS,APPLIED_RULES,p._snapshot.digest,33,True);return s,p
def schema_args(key,i):
    f,k,t=key;return (f"synthetic:approval-receipt-schema:{f}:{k}:{t.lower()}",f"synthetic:approval-receipt-idempotency-key:key-{i}",f,k,t,f"synthetic:approval-receipt-issuer-role:issuer-{i}",f"synthetic:approval-receipt-verifier-role:verifier-{i}")
def schemed():
    s,p=anchored()
    for i,key in enumerate(p._envelopes):s.add_schema(*schema_args(key,i))
    return s,p
def completed():
    s,p=schemed();s.finalize("synthetic:receipt-schema-docket:final","synthetic:receipt-schema-docket-compiler:final-c","synthetic:receipt-schema-docket-validator:final-v");return s,p
FIELDS=tuple(ReceiptSchema.__dataclass_fields__)[:-1]
def rehash(s,start,changes):
    keys=list(s._schemas)
    for i in range(start,len(keys)):
        key=keys[i];r=s._schemas[key];v={**r.__dict__};v["predecessor_schema_digest"]=None if i==0 else s._schemas[keys[i-1]].digest;v.update(changes if i==start else {})
        v["digest"]=canonical_digest(("APPROVAL_RECEIPT_SCHEMA_CONTRACT",tuple(v[k] for k in FIELDS)));s._schemas[key]=replace(r,**v)
    s._keys={x.idempotency_key_id:x for x in s._schemas.values()};s._events=[];s._holds=[];s._event("RECEIPT_SCHEMA_CHAIN_ANCHORED",s._snapshot.digest)
    for x in s._schemas.values():
        s._event("RECEIPT_SCHEMA_RECORDED",x.digest)
        if x.source_actor:s._hold("APPROVAL_RECEIPT_SCHEMA_PENDING_HUMAN_ISSUANCE",x.digest)
    if s._docket:
        r=s._docket;p={**r.__dict__,"schema_set_digest":canonical_digest(tuple(x.digest for x in s._schemas.values()))};p.pop("digest");s._docket=replace(r,schema_set_digest=p["schema_set_digest"],digest=canonical_digest(p));s._event("RECEIPT_SCHEMA_DOCKET_HELD",s._docket.digest)

class Tests(unittest.TestCase):
    def test_matrix_exactly_400(self):self.assertEqual((len(WORKSTREAMS),len(populated()._controls),WORKSTREAMS[0][0],WORKSTREAMS[-1][1]),(16,400,14701,15100))
    def test_control_serial_idempotency_and_conflict(self):
        s=SyntheticApprovalReceiptSchemaContract();args=(14701,WORKSTREAM_NAMES[0],CONTROL_ASPECTS[0],"synthetic:receipt-schema-requirement:00",d("x"),"PASS");self.assertIs(s.add_control(*args),s.add_control(*args))
        with self.assertRaises(GovernanceRejected):s.add_control(*args[:-2],d("changed"),args[-1])
    def test_same_key_same_payload_serial_idempotency(self):
        s,p=anchored();args=schema_args(next(iter(p._envelopes)),0);self.assertIs(s.add_schema(*args),s.add_schema(*args))
    def test_same_key_same_payload_parallel_idempotency(self):
        s,p=anchored();args=schema_args(next(iter(p._envelopes)),0)
        with ThreadPoolExecutor(max_workers=8) as pool:rows=list(pool.map(lambda _:s.add_schema(*args),range(20)))
        self.assertEqual((len(s._schemas),len({id(x) for x in rows})),(1,1))
    def test_routed_materialization_same_payload_parallel_idempotency(self):
        s,p=anchored();keys=list(p._envelopes);s.add_schema(*schema_args(keys[0],0));s.add_schema(*schema_args(keys[1],1));args=schema_args(keys[2],2)
        with ThreadPoolExecutor(max_workers=8) as pool:rows=list(pool.map(lambda _:s.add_schema(*args),range(20)))
        self.assertEqual((len(s._schemas),len({id(x) for x in rows})),(3,1))
    def test_routed_execution_same_payload_parallel_idempotency(self):
        s,p=anchored();keys=list(p._envelopes)
        for i in range(3):s.add_schema(*schema_args(keys[i],i))
        args=schema_args(keys[3],3)
        with ThreadPoolExecutor(max_workers=8) as pool:rows=list(pool.map(lambda _:s.add_schema(*args),range(20)))
        self.assertEqual((len(s._schemas),len({id(x) for x in rows})),(4,1))
    def test_current_source_actor_alias_issuer_rejected(self):
        s,p=anchored();keys=list(p._envelopes);s.add_schema(*schema_args(keys[0],0));s.add_schema(*schema_args(keys[1],1));args=list(schema_args(keys[2],2));args[5]="synthetic:approval-receipt-issuer-role:a-1-0"
        with self.assertRaisesRegex(GovernanceRejected,"role identity collision"):s.add_schema(*args)
    def test_current_source_counter_alias_verifier_rejected(self):
        s,p=anchored();keys=list(p._envelopes);s.add_schema(*schema_args(keys[0],0));s.add_schema(*schema_args(keys[1],1));args=list(schema_args(keys[2],2));args[6]="synthetic:approval-receipt-verifier-role:c-1-0"
        with self.assertRaisesRegex(GovernanceRejected,"role identity collision"):s.add_schema(*args)
    def test_other_key_source_actor_alias_rejected(self):
        s,p=anchored();keys=list(p._envelopes);s.add_schema(*schema_args(keys[0],0));s.add_schema(*schema_args(keys[1],1));args=list(schema_args(keys[2],2));args[5]="synthetic:approval-receipt-issuer-role:a-2-0"
        with self.assertRaisesRegex(GovernanceRejected,"role identity collision"):s.add_schema(*args)
    def test_same_key_different_payload_conflict(self):
        s,p=anchored();args=schema_args(next(iter(p._envelopes)),0);s.add_schema(*args)
        with self.assertRaisesRegex(GovernanceRejected,"receipt schema conflict"):s.add_schema(args[0],args[1],*args[2:5],args[5],"synthetic:approval-receipt-verifier-role:changed")
    def test_different_key_schema_id_reuse_fail_closed(self):
        s,p=anchored();keys=list(p._envelopes);a=schema_args(keys[0],0);s.add_schema(*a);b=list(schema_args(keys[1],1));b[0]=a[0]
        with self.assertRaises(GovernanceRejected):s.add_schema(*b)
    def test_same_idempotency_key_other_logical_schema_conflict(self):
        s,p=anchored();keys=list(p._envelopes);a=schema_args(keys[0],0);s.add_schema(*a);b=list(schema_args(keys[1],1));b[1]=a[1]
        with self.assertRaisesRegex(GovernanceRejected,"idempotency key conflict"):s.add_schema(*b)
    def test_partial_batch_and_order_swap_fail_closed(self):
        s,p=anchored();keys=list(p._envelopes)
        with self.assertRaises(GovernanceRejected):s.add_schema(*schema_args(keys[1],1))
        s.add_schema(*schema_args(keys[0],0))
        with self.assertRaises(GovernanceRejected):s.finalize("synthetic:receipt-schema-docket:x","synthetic:receipt-schema-docket-compiler:c","synthetic:receipt-schema-docket-validator:v")
    def test_counts_and_non_issuance_state(self):
        s,_=completed();e=s.evidence();self.assertEqual((e["receipt_schema_count"],e["idempotency_key_contract_count"],e["recovery_path_count"],e["human_judgment_hold_count"]),(40,40,64,32));self.assertTrue(all(x.state=="SCHEMA_ONLY_NOT_ISSUED" and not x.issued and x.receipt_id is None and x.receipt_digest is None for x in s._schemas.values()))
    def test_composite_identity_full_rehash_rejected(self):
        s,_=completed();rehash(s,2,{"composite_identity_digest":d("attacker")});self.assertFalse(s.evidence()["integrity_valid"])
    def test_source_intent_full_downstream_rehash_rejected(self):
        s,p=completed();key=list(p._envelopes)[2];p._envelopes[key]=replace(p._envelopes[key],digest=d("attacker"));rehash(s,2,{"source_intent_digest":d("attacker")});self.assertFalse(s.evidence()["integrity_valid"])
    def test_idempotency_scope_full_rehash_rejected(self):
        s,_=completed();rehash(s,2,{"idempotency_scope_digest":d("attacker")});self.assertFalse(s.evidence()["integrity_valid"])
    def test_nonce_replay_full_rehash_rejected(self):
        s,_=completed();rows=list(s._schemas.values());rehash(s,2,{"nonce_scope_digest":rows[1].nonce_scope_digest});self.assertFalse(s.evidence()["integrity_valid"])
    def test_predecessor_removed_full_rehash_rejected(self):
        s,_=completed();rehash(s,2,{"predecessor_schema_digest":None});self.assertFalse(s.evidence()["integrity_valid"])
    def test_receipt_forgery_full_rehash_rejected(self):
        s,_=completed();rehash(s,2,{"receipt_id":"synthetic:approval-receipt:forged","receipt_digest":d("forged"),"issued":True,"state":"ISSUED"});self.assertFalse(s.evidence()["integrity_valid"])
    def test_authority_forgery_full_rehash_rejected(self):
        s,_=completed();r=s._docket;p={**r.__dict__,"approved":True,"status":"APPROVED"};p.pop("digest");s._docket=replace(r,approved=True,status="APPROVED",digest=canonical_digest(p));s._events[-1]["artifact_digest"]=s._docket.digest;ep={k:s._events[-1][k] for k in ("sequence","action","artifact_digest","previous_digest")};s._events[-1]["digest"]=canonical_digest(ep);self.assertFalse(s.evidence()["integrity_valid"])
    def test_role_exchange_full_rehash_rejected(self):
        s,_=completed();r=list(s._schemas.values())[2];rehash(s,2,{"issuer_role":r.verifier_role,"verifier_role":r.issuer_role});self.assertFalse(s.evidence()["integrity_valid"])
    def test_source_actor_alias_full_downstream_rehash_rejected(self):
        s,_=completed();rehash(s,2,{"issuer_role":"synthetic:approval-receipt-issuer-role:a-1-0"});self.assertFalse(s.evidence()["integrity_valid"])
    def test_single_recovery_path_full_rehash_rejected(self):
        s,_=completed();r=list(s._schemas.values())[2];rehash(s,2,{"recovery_paths":r.recovery_paths[:1]});self.assertFalse(s.evidence()["integrity_valid"])
    def test_event_hold_tamper_rejected(self):
        s,_=completed();s._events[1]["artifact_digest"]=d("bad");self.assertFalse(s.evidence()["integrity_valid"]);s,_=completed();s._holds.pop();self.assertFalse(s.evidence()["integrity_valid"])
    def test_no_receipt_execution_observation_or_authority(self):
        e=completed()[0].evidence();self.assertTrue(e["complete_approval_receipt_schema_contract_evidence"]);self.assertFalse(any(e[k] for k in ("judgment_authority","recommendation_authority","selection_authority","acceptance_authority","resolution_authority","approved","materialized","executed","observed","passed","failed","activated")));self.assertEqual(tuple(e[k] for k in ("approval_receipts_issued","fixture_materializations","probe_executions","observation_values","external_calls","ledger_writes","credential_reads","deployments")),(0,)*8)

if __name__=="__main__":unittest.main()
