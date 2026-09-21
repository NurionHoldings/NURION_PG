from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from hashlib import sha256
import unittest

from nurion_pg.arkaon.governance import GovernanceRejected,canonical_digest
from nurion_pg.synthetic_preissuance_dual_signature_input_contract import *
from tests.test_synthetic_approval_receipt_schema_contract import completed as prior_completed

def d(v):return sha256(v.encode()).hexdigest()
def populated():
    s=SyntheticPreissuanceDualSignatureInputContract()
    for cid in range(15101,15501):
        w,a=s._expected(cid);s.add_control(cid,w,a,f"synthetic:preissuance-input-requirement:{(cid-15101)//25:02}",d(str(cid)),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    return s
def anchored():
    p=prior_completed()[0];s=populated();s.anchor(p,mapping_digest(STAGE_MAPPING),d("registry"),d("manifest"),APPLIED_LESSONS,APPLIED_RULES,p._snapshot.digest,34,True);return s,p
def packet_args(key,i):
    f,k,t=key;return (f"synthetic:preissuance-validation-packet:{f}:{k}:{t.lower()}",f"synthetic:preissuance-packet-idempotency-key:key-{i}",f,k,t,f"synthetic:preissuance-issuer:preissuer-{i}",f"synthetic:preissuance-verifier:preverifier-{i}",f"synthetic:issuer-challenge:i-{i}",f"synthetic:verifier-challenge:v-{i}",f"synthetic:issuer-audience:i-{i}",f"synthetic:verifier-audience:v-{i}",f"synthetic:issuer-purpose:i-{i}",f"synthetic:verifier-purpose:v-{i}","synthetic:signature-policy-version:v1")
def packeted():
    s,p=anchored()
    for i,key in enumerate(p._schemas):s.add_packet(*packet_args(key,i))
    return s,p
def completed():
    s,p=packeted();s.finalize("synthetic:preissuance-docket:final","synthetic:preissuance-docket-compiler:final-c","synthetic:preissuance-docket-validator:final-v");return s,p
FIELDS=tuple(ValidationPacket.__dataclass_fields__)[:-1]
def rehash(s,start,changes):
    keys=list(s._packets)
    for i in range(start,len(keys)):
        key=keys[i];r=s._packets[key];v={**r.__dict__};v["predecessor_packet_digest"]=None if i==0 else s._packets[keys[i-1]].digest;v.update(changes if i==start else {});v["digest"]=canonical_digest(("PREISSUANCE_DUAL_SIGNATURE_INPUT_CONTRACT",tuple(v[k] for k in FIELDS)));s._packets[key]=replace(r,**v)
    s._keys={x.idempotency_key_id:x for x in s._packets.values()};s._events=[];s._holds=[];s._event("PREISSUANCE_CHAIN_ANCHORED",s._snapshot.digest)
    for x in s._packets.values():
        s._event("PREISSUANCE_PACKET_RECORDED",x.digest)
        if s._source._schemas[(x.flow,x.kind,x.intent_kind)].source_actor:s._hold("DUAL_SIGNATURE_INPUT_PENDING_HUMAN_AUTHORITY",x.digest)
    if s._docket:
        r=s._docket;p={**r.__dict__,"packet_set_digest":canonical_digest(tuple(x.digest for x in s._packets.values()))};p.pop("digest");s._docket=replace(r,packet_set_digest=p["packet_set_digest"],digest=canonical_digest(p));s._event("PREISSUANCE_DOCKET_HELD",s._docket.digest)
def full_policy_rehash(s,policy):
    keys=list(s._packets)
    for i,key in enumerate(keys):
        r=s._packets[key];source=s._source._schemas[key];position=i+1;pred=None if i==0 else s._packets[keys[i-1]].digest;chosen=policy if i==0 else r.policy_version;issued=SYNTHETIC_EPOCH+position*100;expires=issued+300
        scope=canonical_digest(("PREISSUANCE_PACKET_SCOPE_V1",r.idempotency_key_id,source.digest,source.idempotency_scope_digest,source.composite_identity_digest,position,pred,chosen));nonce=canonical_digest(("PREISSUANCE_PACKET_NONCE_V1",source.nonce_scope_digest,scope,position,pred));ii=canonical_digest(("ISSUER_SIGNATURE_INPUT_V1",source.digest,scope,nonce,r.issuer_actor,r.issuer_domain,r.issuer_challenge,r.issuer_audience,r.issuer_purpose,chosen,issued,expires));vi=canonical_digest(("VERIFIER_SIGNATURE_INPUT_V1",source.digest,scope,nonce,r.verifier_actor,r.verifier_domain,r.verifier_challenge,r.verifier_audience,r.verifier_purpose,chosen,issued,expires,ii));v={**r.__dict__,"policy_version":chosen,"predecessor_packet_digest":pred,"packet_scope_digest":scope,"nonce_scope_digest":nonce,"issuer_signature_input_digest":ii,"verifier_signature_input_digest":vi};v["digest"]=canonical_digest(("PREISSUANCE_DUAL_SIGNATURE_INPUT_CONTRACT",tuple(v[k] for k in FIELDS)));s._packets[key]=replace(r,**v)
    s._keys={x.idempotency_key_id:x for x in s._packets.values()};s._events=[];s._holds=[];s._event("PREISSUANCE_CHAIN_ANCHORED",s._snapshot.digest)
    for x in s._packets.values():
        s._event("PREISSUANCE_PACKET_RECORDED",x.digest)
        if s._source._schemas[(x.flow,x.kind,x.intent_kind)].source_actor:s._hold("DUAL_SIGNATURE_INPUT_PENDING_HUMAN_AUTHORITY",x.digest)
    r=s._docket;p={**r.__dict__,"packet_set_digest":canonical_digest(tuple(x.digest for x in s._packets.values()))};p.pop("digest");s._docket=replace(r,packet_set_digest=p["packet_set_digest"],digest=canonical_digest(p));s._event("PREISSUANCE_DOCKET_HELD",s._docket.digest)

class Tests(unittest.TestCase):
    def test_matrix_exactly_400(self):self.assertEqual((len(WORKSTREAMS),len(populated()._controls),WORKSTREAMS[0][0],WORKSTREAMS[-1][1]),(16,400,15101,15500))
    def test_serial_and_parallel_idempotency(self):
        s,p=anchored();a=packet_args(next(iter(p._schemas)),0);self.assertIs(s.add_packet(*a),s.add_packet(*a))
        s,p=anchored();a=packet_args(next(iter(p._schemas)),0)
        with ThreadPoolExecutor(max_workers=8) as pool:rows=list(pool.map(lambda _:s.add_packet(*a),range(20)))
        self.assertEqual((len(s._packets),len({id(x) for x in rows})),(1,1))
    def test_routed_materialization_20_way_idempotency(self):
        s,p=anchored();keys=list(p._schemas);s.add_packet(*packet_args(keys[0],0));s.add_packet(*packet_args(keys[1],1));a=packet_args(keys[2],2)
        with ThreadPoolExecutor(max_workers=8) as pool:rows=list(pool.map(lambda _:s.add_packet(*a),range(20)))
        self.assertEqual((len(s._packets),len({id(x) for x in rows})),(3,1))
    def test_routed_execution_20_way_idempotency(self):
        s,p=anchored();keys=list(p._schemas)
        for i in range(3):s.add_packet(*packet_args(keys[i],i))
        a=packet_args(keys[3],3)
        with ThreadPoolExecutor(max_workers=8) as pool:rows=list(pool.map(lambda _:s.add_packet(*a),range(20)))
        self.assertEqual((len(s._packets),len({id(x) for x in rows})),(4,1))
    def test_changed_payload_and_cross_key_ids_rejected(self):
        s,p=anchored();keys=list(p._schemas);a=packet_args(keys[0],0);s.add_packet(*a);changed=list(a);changed[7]="synthetic:issuer-challenge:changed"
        with self.assertRaisesRegex(GovernanceRejected,"validation packet conflict"):s.add_packet(*changed)
        b=list(packet_args(keys[1],1));b[0]=a[0]
        with self.assertRaises(GovernanceRejected):s.add_packet(*b)
    def test_policy_downgrade_missing_unknown_future_api_rejected(self):
        for policy in ("synthetic:signature-policy-version:v0","","synthetic:signature-policy-version:unknown","synthetic:signature-policy-version:v2"):
            s,p=anchored();a=list(packet_args(next(iter(p._schemas)),0));a[-1]=policy
            with self.assertRaisesRegex(GovernanceRejected,"required signature policy version only"):s.add_packet(*a)
    def test_policy_downgrade_complete_downstream_rehash_rejected(self):
        s,_=completed();full_policy_rehash(s,"synthetic:signature-policy-version:v0");self.assertFalse(s.evidence()["integrity_valid"])
    def test_current_other_source_and_namespace_aliases_rejected(self):
        s,p=anchored();keys=list(p._schemas);s.add_packet(*packet_args(keys[0],0));a=list(packet_args(keys[1],1));a[5]="synthetic:preissuance-issuer:a-1-0"
        with self.assertRaisesRegex(GovernanceRejected,"global actor identity collision"):s.add_packet(*a)
        a=list(packet_args(keys[1],1));a[6]="synthetic:preissuance-verifier:preissuer-0"
        with self.assertRaisesRegex(GovernanceRejected,"global actor identity collision"):s.add_packet(*a)
    def test_challenge_and_signature_input_reuse_rejected(self):
        s,p=anchored();keys=list(p._schemas);x=s.add_packet(*packet_args(keys[0],0));a=list(packet_args(keys[1],1));a[7]=x.issuer_challenge
        with self.assertRaises(GovernanceRejected):s.add_packet(*a)
    def test_partial_batch_order_swap_rejected(self):
        s,p=anchored();keys=list(p._schemas)
        with self.assertRaises(GovernanceRejected):s.add_packet(*packet_args(keys[1],1))
        s.add_packet(*packet_args(keys[0],0))
        with self.assertRaises(GovernanceRejected):s.finalize("synthetic:preissuance-docket:x","synthetic:preissuance-docket-compiler:c","synthetic:preissuance-docket-validator:v")
    def test_counts_deterministic_epoch_and_non_issuance(self):
        s,_=completed();e=s.evidence();self.assertEqual((e["validation_packet_count"],e["dual_signature_input_count"],e["recovery_path_count"],e["human_judgment_hold_count"]),(40,80,64,32));self.assertTrue(all(x.expires_at_epoch-x.issued_at_epoch==300 and x.state=="INPUT_ONLY_NOT_SIGNED" and x.signature_value is None and x.receipt_id is None for x in s._packets.values()))
    def test_exchange_delete_relax_and_full_rehash_attacks_rejected(self):
        attacks=({"issuer_challenge":"synthetic:verifier-challenge:v-2"},{"verifier_audience":""},{"issuer_purpose":"synthetic:verifier-purpose:v-2"},{"expires_at_epoch":SYNTHETIC_EPOCH+2*100+999},{"policy_version":"synthetic:signature-policy-version:v0"},{"issuer_domain":"synthetic:signature-domain:verifier:3"},{"predecessor_packet_digest":None})
        for attack in attacks:
            s,_=completed();rehash(s,2,attack);self.assertFalse(s.evidence()["integrity_valid"],attack)
    def test_forged_signature_receipt_and_authority_rejected(self):
        for attack in ({"signature_value":"forged","verified":True},{"receipt_id":"synthetic:receipt:forged","receipt_digest":d("x"),"issued":True}):
            s,_=completed();rehash(s,2,attack);self.assertFalse(s.evidence()["integrity_valid"])
        s,_=completed();r=s._docket;p={**r.__dict__,"approved":True,"status":"APPROVED"};p.pop("digest");s._docket=replace(r,approved=True,status="APPROVED",digest=canonical_digest(p));s._events[-1]["artifact_digest"]=s._docket.digest;ep={k:s._events[-1][k] for k in ("sequence","action","artifact_digest","previous_digest")};s._events[-1]["digest"]=canonical_digest(ep);self.assertFalse(s.evidence()["integrity_valid"])
    def test_source_schema_full_downstream_rehash_rejected(self):
        s,p=completed();key=list(p._schemas)[2];p._schemas[key]=replace(p._schemas[key],digest=d("attacker"));rehash(s,2,{"source_schema_digest":d("attacker")});self.assertFalse(s.evidence()["integrity_valid"])
    def test_namespace_and_docket_full_rehash_rejected(self):
        s,_=completed();rehash(s,2,{"packet_id":"attacker:packet:3"});self.assertFalse(s.evidence()["integrity_valid"])
        s,_=completed();r=s._docket;p={**r.__dict__,"docket_id":"attacker:docket"};p.pop("digest");s._docket=replace(r,docket_id=p["docket_id"],digest=canonical_digest(p));s._events[-1]["artifact_digest"]=s._docket.digest;ep={k:s._events[-1][k] for k in ("sequence","action","artifact_digest","previous_digest")};s._events[-1]["digest"]=canonical_digest(ep);self.assertFalse(s.evidence()["integrity_valid"])
    def test_recovery_guidance_and_zero_side_effects(self):
        s,_=completed();r=next(x for x in s._packets.values() if x.recovery_paths);self.assertIn(("recommended",True),r.recovery_paths[0]);self.assertIn(("rollback","discard_packet_preserve_schema"),r.recovery_paths[0]);e=s.evidence();self.assertTrue(e["complete_preissuance_dual_signature_input_contract_evidence"]);self.assertFalse(any(e[k] for k in ("judgment_authority","recommendation_authority","selection_authority","acceptance_authority","resolution_authority","approved","materialized","executed","observed","passed","failed","activated")));self.assertEqual(tuple(e[k] for k in ("signature_values_created","signature_verifications","key_material_reads","credential_reads","approval_receipts_issued","ledger_writes","external_calls","deployments")),(0,)*8)

if __name__=="__main__":unittest.main()
