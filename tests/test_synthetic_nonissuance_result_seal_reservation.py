from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from hashlib import sha256
import unittest

from nurion_pg.arkaon.governance import GovernanceRejected,canonical_digest
from nurion_pg.synthetic_nonissuance_result_seal_reservation import *
from tests.test_synthetic_preissuance_dual_signature_input_contract import completed as prior_completed

def d(v):return sha256(v.encode()).hexdigest()
def populated():
    s=SyntheticNonissuanceResultSealReservation()
    for cid in range(15501,15901):
        w,a=s._expected(cid);s.add_control(cid,w,a,f"synthetic:reservation-requirement:{(cid-15501)//25:02}",d(str(cid)),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    return s
def anchored():
    p=prior_completed()[0];s=populated();s.anchor(p,mapping_digest(STAGE_MAPPING),d("registry"),d("manifest"),APPLIED_LESSONS,APPLIED_RULES,p._snapshot.digest,35,True);return s,p
def args(key,i,epoch=None):
    f,k,t=key;return (f"synthetic:nonissuance-reservation:{f}:{k}:{t.lower()}",f"synthetic:reservation-idempotency-key:key-{i}",f"synthetic:reservation-token:token-{i}",f,k,t,f"synthetic:reservation-owner:owner-{i}",f"synthetic:reservation-validator:validator-{i}",epoch)
def reserved():
    s,p=anchored()
    for i,key in enumerate(p._packets):s.reserve(*args(key,i))
    return s,p
def completed():
    s,p=reserved();s.finalize("synthetic:reservation-docket:final","synthetic:reservation-docket-compiler:final-c","synthetic:reservation-final-validator:final-v");return s,p
def rehash_from(s,start,changes):
    keys=list(s._reservations)
    for i in range(start,len(keys)):
        key=keys[i];old=s._reservations[key];source=s._source._packets[key];pred=None if i==0 else s._reservations[keys[i-1]].digest;observed=changes.get("observed_epoch",old.observed_epoch) if i==start else old.observed_epoch
        scope=canonical_digest(("ATOMIC_RESERVATION_SCOPE_V1",old.idempotency_key_id,old.reservation_token_id,source.digest,source.packet_scope_digest,source.source_idempotency_scope_digest,source.composite_identity_digest,source.issuer_signature_input_digest,source.verifier_signature_input_digest,source.policy_version,i+1,pred,old.owner_actor,old.validator_actor));nonce=canonical_digest(("RESERVATION_NONCE_V1",source.nonce_scope_digest,scope,i+1,pred));candidate=canonical_digest(("NONISSUING_VALIDATION_RESULT_CANDIDATE_V1",source.digest,source.issuer_signature_input_digest,source.verifier_signature_input_digest,source.policy_version,"NOT_CRYPTOGRAPHICALLY_VERIFIED"));seal=canonical_digest(("NONISSUANCE_RESULT_SEAL_INPUT_V1",candidate,scope,nonce,old.owner_actor,old.validator_actor,observed,source.expires_at_epoch));v={**old.__dict__,"observed_epoch":observed,"predecessor_reservation_digest":pred,"reservation_scope_digest":scope,"nonce_scope_digest":nonce,"result_candidate_digest":candidate,"seal_input_digest":seal};vals=tuple(v[k] for k in Reservation.__dataclass_fields__ if k!="digest");v["digest"]=canonical_digest(("NONISSUANCE_RESULT_SEAL_RESERVATION_V1",vals));s._reservations[key]=replace(old,**v)
    s._keys={x.idempotency_key_id:x for x in s._reservations.values()};s._tokens={x.reservation_token_id:x for x in s._reservations.values()};s._events=[];s._holds=[];s._event("RESERVATION_CHAIN_ANCHORED",s._snapshot.digest)
    for x in s._reservations.values():
        s._event("ATOMIC_RESERVATION_RECORDED",x.digest)
        if x.recovery_paths:s._hold("RESERVATION_PENDING_HUMAN_AUTHORITY",x.digest)
    r=s._docket;p={**r.__dict__,"reservation_set_digest":canonical_digest(tuple(x.digest for x in s._reservations.values()))};p.pop("digest");s._docket=replace(r,reservation_set_digest=p["reservation_set_digest"],digest=canonical_digest(p));s._event("RESERVATION_DOCKET_HELD",s._docket.digest)
def rehash_snapshot(s,sequence):
    snap=s._snapshot;p={**snap.__dict__,"sequence":sequence};p.pop("digest");s._snapshot=replace(snap,sequence=sequence,digest=canonical_digest(p));s._events[0]["artifact_digest"]=s._snapshot.digest;ep={k:s._events[0][k] for k in ("sequence","action","artifact_digest","previous_digest")};s._events[0]["digest"]=canonical_digest(ep)
    for i in range(1,len(s._events)):s._events[i]["previous_digest"]=s._events[i-1]["digest"];ep={k:s._events[i][k] for k in ("sequence","action","artifact_digest","previous_digest")};s._events[i]["digest"]=canonical_digest(ep)
    r=s._docket;p={**r.__dict__,"snapshot_digest":s._snapshot.digest};p.pop("digest");s._docket=replace(r,snapshot_digest=s._snapshot.digest,digest=canonical_digest(p));s._events[-1]["artifact_digest"]=s._docket.digest;ep={k:s._events[-1][k] for k in ("sequence","action","artifact_digest","previous_digest")};s._events[-1]["digest"]=canonical_digest(ep)

class Tests(unittest.TestCase):
    def test_matrix_exactly_400(self):self.assertEqual((len(WORKSTREAMS),len(populated()._controls),WORKSTREAMS[0][0],WORKSTREAMS[-1][1]),(16,400,15501,15900))
    def test_same_key_same_payload_serial_parallel_converges(self):
        s,p=anchored();a=args(next(iter(p._packets)),0);self.assertIs(s.reserve(*a),s.reserve(*a))
        s,p=anchored();a=args(next(iter(p._packets)),0)
        with ThreadPoolExecutor(max_workers=8) as pool:rows=list(pool.map(lambda _:s.reserve(*a),range(20)))
        self.assertEqual((len(s._reservations),len({id(x) for x in rows})),(1,1))
    def test_routed_materialization_20_way_idempotency(self):
        s,p=anchored();keys=list(p._packets);s.reserve(*args(keys[0],0));s.reserve(*args(keys[1],1));a=args(keys[2],2)
        with ThreadPoolExecutor(max_workers=8) as pool:rows=list(pool.map(lambda _:s.reserve(*a),range(20)))
        self.assertEqual((len(s._reservations),len({id(x) for x in rows})),(3,1))
    def test_routed_execution_20_way_idempotency(self):
        s,p=anchored();keys=list(p._packets)
        for i in range(3):s.reserve(*args(keys[i],i))
        a=args(keys[3],3)
        with ThreadPoolExecutor(max_workers=8) as pool:rows=list(pool.map(lambda _:s.reserve(*a),range(20)))
        self.assertEqual((len(s._reservations),len({id(x) for x in rows})),(4,1))
    def test_same_key_changed_payload_and_cross_key_identity_reuse_rejected(self):
        s,p=anchored();keys=list(p._packets);a=args(keys[0],0);s.reserve(*a);changed=list(a);changed[6]="synthetic:reservation-owner:changed"
        with self.assertRaisesRegex(GovernanceRejected,"reservation conflict"):s.reserve(*changed)
        b=list(args(keys[1],1));b[0]=a[0]
        with self.assertRaises(GovernanceRejected):s.reserve(*b)
    def test_token_scope_nonce_reuse_rejected(self):
        s,p=anchored();keys=list(p._packets);x=s.reserve(*args(keys[0],0));b=list(args(keys[1],1));b[2]=x.reservation_token_id
        with self.assertRaises(GovernanceRejected):s.reserve(*b)
        s,_=completed();key=list(s._reservations)[2];r=s._reservations[key];s._reservations[key]=replace(r,nonce_scope_digest=next(iter(s._reservations.values())).nonce_scope_digest);self.assertFalse(s.evidence()["integrity_valid"])
    def test_owner_validator_exchange_alias_and_global_actor_collision_rejected(self):
        s,p=anchored();key=next(iter(p._packets));a=list(args(key,0));a[6]="synthetic:reservation-owner:shared";a[7]="synthetic:reservation-validator:shared"
        with self.assertRaisesRegex(GovernanceRejected,"independent reservation actors"):s.reserve(*a)
        source=p._packets[key];a=list(args(key,0));a[6]=f"synthetic:reservation-owner:{source.issuer_actor.rsplit(':',1)[-1]}"
        with self.assertRaisesRegex(GovernanceRejected,"global actor identity collision"):s.reserve(*a)
    def test_policy_v0_missing_unknown_future_and_downstream_rehash_rejected(self):
        for policy in ("synthetic:signature-policy-version:v0","","synthetic:signature-policy-version:unknown","synthetic:signature-policy-version:v2"):
            s,p=anchored();key=next(iter(p._packets));p._packets[key]=replace(p._packets[key],policy_version=policy)
            with self.assertRaisesRegex(GovernanceRejected,"required signature policy version only"):s.reserve(*args(key,0))
        s,p=completed();key=list(p._packets)[2];p._packets[key]=replace(p._packets[key],policy_version="synthetic:signature-policy-version:v0");self.assertFalse(s.evidence()["integrity_valid"])
    def test_deterministic_expiry_boundary_and_expired_resume_rejected(self):
        s,p=anchored();key=next(iter(p._packets));issued=p._packets[key].issued_at_epoch;expiry=p._packets[key].expires_at_epoch;self.assertEqual(s.reserve(*args(key,0,issued)).observed_epoch,issued)
        s,p=anchored();key=next(iter(p._packets));expiry=p._packets[key].expires_at_epoch;self.assertEqual(s.reserve(*args(key,0,expiry)).observed_epoch,expiry)
        for epoch in (p._packets[key].issued_at_epoch-1,expiry+1):
            s,p=anchored();key=next(iter(p._packets))
            with self.assertRaisesRegex(GovernanceRejected,"in-window deterministic"):s.reserve(*args(key,0,epoch))
        s,p=completed();issued=next(iter(p._packets.values())).issued_at_epoch;rehash_from(s,0,{"observed_epoch":issued-1});self.assertFalse(s.evidence()["integrity_valid"])
    def test_snapshot_sequence_api_and_full_downstream_rehash_rejected(self):
        for sequence in (0,True,-1):
            p=prior_completed()[0];s=populated()
            with self.assertRaisesRegex(GovernanceRejected,"complete latest reservation snapshot required"):s.anchor(p,mapping_digest(STAGE_MAPPING),d("registry"),d("manifest"),APPLIED_LESSONS,APPLIED_RULES,p._snapshot.digest,sequence,True)
            s,_=completed();rehash_snapshot(s,sequence);self.assertFalse(s.evidence()["integrity_valid"])
    def test_partial_batch_and_order_swap_fail_closed(self):
        s,p=anchored();keys=list(p._packets)
        with self.assertRaises(GovernanceRejected):s.reserve(*args(keys[1],1))
        s.reserve(*args(keys[0],0))
        with self.assertRaises(GovernanceRejected):s.finalize("synthetic:reservation-docket:x","synthetic:reservation-docket-compiler:c","synthetic:reservation-final-validator:v")
    def test_source_input_exchange_full_rehash_rejected(self):
        s,p=completed();keys=list(p._packets);key=keys[2];source=p._packets[key];p._packets[key]=replace(source,issuer_signature_input_digest=p._packets[keys[1]].issuer_signature_input_digest);self.assertFalse(s.evidence()["integrity_valid"])
    def test_owner_validator_exchange_full_rehash_rejected(self):
        s,_=completed();key=list(s._reservations)[2];r=s._reservations[key];s._reservations[key]=replace(r,owner_actor=r.validator_actor,validator_actor=r.owner_actor);self.assertFalse(s.evidence()["integrity_valid"])
    def test_commit_receipt_and_authority_forgery_rejected(self):
        for changes in ({"committed":True},{"receipt_id":"synthetic:receipt:forged","receipt_digest":d("x")},{"signature_value":"forged","signature_verified":True},{"passed":True}):
            s,_=completed();key=list(s._reservations)[2];s._reservations[key]=replace(s._reservations[key],**changes);self.assertFalse(s.evidence()["integrity_valid"])
        s,_=completed();r=s._docket;s._docket=replace(r,approved=True,status="APPROVED");self.assertFalse(s.evidence()["integrity_valid"])
    def test_reservation_id_namespace_and_docket_roles_rejected(self):
        s,_=completed();key=list(s._reservations)[2];r=s._reservations[key];s._reservations[key]=replace(r,reservation_id="attacker:id");self.assertFalse(s.evidence()["integrity_valid"])
        s,p=reserved();prior=next(iter(s._reservations.values())).owner_actor
        with self.assertRaisesRegex(GovernanceRejected,"independent reservation docket roles"):s.finalize("synthetic:reservation-docket:x",f"synthetic:reservation-docket-compiler:{prior.rsplit(':',1)[-1]}","synthetic:reservation-final-validator:v")
    def test_counts_guidance_and_zero_side_effects(self):
        s,_=completed();e=s.evidence();self.assertEqual((e["reservation_count"],e["result_candidate_count"],e["seal_input_count"],e["recovery_path_count"],e["human_judgment_hold_count"]),(40,40,40,64,32));r=next(x for x in s._reservations.values() if x.recovery_paths);self.assertIn(("recommended",True),r.recovery_paths[0]);self.assertIn(("rollback","discard_uncommitted_reservation_preserve_packet"),r.recovery_paths[0]);self.assertTrue(e["complete_nonissuance_result_seal_reservation_evidence"]);self.assertEqual(tuple(e[k] for k in ("cryptographic_verifications","reservation_commits","approval_receipts_issued","ledger_writes","database_writes","external_calls","deployments")),(0,)*7)
    def test_result_candidate_not_cryptographic_verdict(self):
        s,_=completed();self.assertTrue(all(x.state=="RESERVED_NOT_COMMITTED_NOT_ISSUED" and not x.signature_verified and not x.passed and not x.failed for x in s._reservations.values()))

if __name__=="__main__":unittest.main()
