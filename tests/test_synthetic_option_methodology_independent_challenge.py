import hashlib
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from nurion_pg.arkaon.governance import GovernanceRejected,canonical_digest
from nurion_pg.synthetic_option_methodology_independent_challenge import *
from tests.test_synthetic_judgment_preparation_stress_test import completed as prior_completed,rehash_attack as prior_full_rehash

def d(v):return hashlib.sha256(v.encode()).hexdigest()
def populated():
    s=SyntheticOptionMethodologyIndependentChallenge()
    for cid in range(12301,12701):
        w,a=s._expected(cid);s.add_control(cid,w,a,f"synthetic:methodology-challenge-requirement:{(cid-12301)//25:02}",d(str(cid)),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    return s
def anchored():
    prior=prior_completed()[0];s=populated();s.anchor(prior,d("registry"),d("manifest"),APPLIED_LESSONS,APPLIED_RULES,27,True);return s,prior
def challenged():
    s,p=anchored()
    for i,key in enumerate(CASE_KEYS):
        args=(f"synthetic:option-methodology-challenge:{key[0]}:{key[1]}",*key)
        if p._tests[key].option_profiles:s.add_challenge(*args,f"synthetic:methodology-challenger:method-challenger-{i}",f"synthetic:methodology-custodian:method-custodian-{i}")
        else:s.add_challenge(*args)
    return s,p
def completed():
    s,p=challenged();r=s.finalize("synthetic:option-methodology-docket:d","synthetic:methodology-docket-compiler:methodology-final-compiler","synthetic:methodology-docket-validator:methodology-final-validator");return s,p,r
def full_rehash(s,start,changes):
    for i,key in enumerate(CASE_KEYS):
        if i<start:continue
        r=s._challenges[key];v={**r.__dict__,**(changes if i==start else {})};v["parent_digest"]=None if i==0 else s._challenges[CASE_KEYS[i-1]].digest;v["projection_digest"]=projection(v["source_stress_digest"],v["challenger"],v["custodian"],v["marker"],v["methodology_cards"]);ordered=tuple(v[k] for k in ("challenge_id","flow","answer_kind","source_stress_digest","challenger","custodian","marker","parent_digest","position","methodology_cards","projection_digest","held","pending_human_judgment","ranked","selected","concluded","recommended","accepted","resolved"));v["digest"]=canonical_digest(("OPTION_METHODOLOGY_CHALLENGE",ordered));s._challenges[key]=replace(r,**{k:x for k,x in v.items() if k in r.__dict__})
    s._events=[];s._holds=[];s._event("PRIOR_STRESS_DOCKET_ANCHORED",s._source.digest)
    for r in s._challenges.values():
        s._event("OPTION_METHODOLOGY_CHALLENGE_RECORDED",r.digest)
        if r.pending_human_judgment:s._hold("HUMAN_METHODOLOGY_JUDGMENT_REQUIRED",r.digest)
    if s._docket:
        r=s._docket;cset=canonical_digest(tuple(s._challenges[k].digest for k in CASE_KEYS));p={**r.__dict__,"challenge_set_digest":cset};p.pop("digest");s._docket=replace(r,challenge_set_digest=cset,digest=canonical_digest(p));s._event("OPTION_METHODOLOGY_DOCKET_HELD",s._docket.digest)
def source_metadata_full_rehash(s,changes):
    a=s._source;v={**a.__dict__,**changes};e=a.service.evidence();ordered=tuple(v[k] for k in ("docket_digest","stress_set_digest","registry_digest","manifest_digest","lessons","rules","sequence","latest"))+(e.get("complete_role_lineage_digest"),);v["digest"]=canonical_digest(ordered);s._source=replace(a,**{k:x for k,x in v.items() if k in a.__dict__});full_rehash(s,0,{})
    r=s._docket;p={**r.__dict__,"source_anchor_digest":s._source.digest};p.pop("digest");s._docket=replace(r,source_anchor_digest=s._source.digest,digest=canonical_digest(p));s._events[-1]["artifact_digest"]=s._docket.digest;ep={k:s._events[-1][k] for k in ("sequence","action","artifact_digest","previous_digest")};s._events[-1]["digest"]=canonical_digest(ep)
def docket_full_rehash(s,changes):
    r=s._docket;v={**r.__dict__,**changes};actors=s._prior_actors()+tuple(y for x in s._challenges.values() for y in (x.challenger,x.custodian) if y)+(v["compiler"],v["validator"]);v["role_lineage_digest"]=canonical_digest(("COMPLETE_OPTION_METHODOLOGY_ROLE_LINEAGE",s._source.service._docket.full_role_lineage_digest,actors));p={k:x for k,x in v.items() if k!="digest"};v["digest"]=canonical_digest(p);s._docket=replace(r,**{k:x for k,x in v.items() if k in r.__dict__});s._events[-1]["artifact_digest"]=s._docket.digest;ep={k:s._events[-1][k] for k in ("sequence","action","artifact_digest","previous_digest")};s._events[-1]["digest"]=canonical_digest(ep)

class Tests(unittest.TestCase):
    def test_matrix_exactly_400(self):self.assertEqual((WORKSTREAMS[0][0],WORKSTREAMS[-1][1],len(WORKSTREAMS),len(populated()._controls)),(12301,12700,16,400))
    def test_wrong_control_rejected(self):
        with self.assertRaises(GovernanceRejected):SyntheticOptionMethodologyIndependentChallenge().add_control(12301,"BAD",CONTROL_ASPECTS[0],"synthetic:methodology-challenge-requirement:00",d("x"),"PASS")
    def test_control_concurrency_idempotent(self):
        s=SyntheticOptionMethodologyIndependentChallenge();args=(12301,WORKSTREAM_NAMES[0],CONTROL_ASPECTS[0],"synthetic:methodology-challenge-requirement:00",d("x"),"PASS")
        with ThreadPoolExecutor(max_workers=8) as p:rows=list(p.map(lambda _:s.add_control(*args),range(20)))
        self.assertEqual(len({x.digest for x in rows}),1)
    def test_latest_required(self):
        with self.assertRaises(GovernanceRejected):populated().anchor(prior_completed()[0],d("r"),d("m"),APPLIED_LESSONS,APPLIED_RULES,27,False)
    def test_partial_batch_fail_closed(self):
        with self.assertRaises(GovernanceRejected):anchored()[0].finalize("synthetic:option-methodology-docket:d","synthetic:methodology-docket-compiler:c","synthetic:methodology-docket-validator:v")
    def test_immediate_parent_required(self):
        s,p=anchored()
        with self.assertRaises(GovernanceRejected):s.add_challenge("synthetic:option-methodology-challenge:x",*CASE_KEYS[1],"synthetic:methodology-challenger:x","synthetic:methodology-custodian:y")
    def test_na_forbids_actors(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected):s.add_challenge("synthetic:option-methodology-challenge:x",*CASE_KEYS[0],"synthetic:methodology-challenger:x","synthetic:methodology-custodian:y")
    def test_routed_requires_actors(self):
        s,_=anchored();s.add_challenge("synthetic:option-methodology-challenge:a",*CASE_KEYS[0])
        with self.assertRaises(GovernanceRejected):s.add_challenge("synthetic:option-methodology-challenge:b",*CASE_KEYS[1])
    def test_counts_and_per_option_methodology(self):
        s,_,_=completed();e=s.evidence();self.assertEqual((e["challenge_count"],e["methodology_card_count"],e["no_judgment_marker_count"],e["human_judgment_hold_count"]),(20,32,4,16));cards=s._challenges[CASE_KEYS[1]].methodology_cards;self.assertEqual(len(cards),2);self.assertTrue(all(len(c)==16 for c in cards))
    def test_common_criteria_substitution_full_rehash_rejected(self):
        s,_,_=completed();r=s._challenges[CASE_KEYS[1]];cards=list(r.methodology_cards);c=list(cards[0]);c[10]=("validation_criteria","COMMON_ONLY");body=tuple(c[:-1]);c[-1]=canonical_digest(("SOURCE_BOUND_METHODOLOGY_CARD",body));cards[0]=tuple(c);full_rehash(s,1,{"methodology_cards":tuple(cards)});self.assertFalse(s.evidence()["integrity_valid"])
    def test_card_exchange_full_rehash_rejected(self):
        s,_,_=completed();r=s._challenges[CASE_KEYS[1]];full_rehash(s,1,{"methodology_cards":tuple(reversed(r.methodology_cards))});self.assertFalse(s.evidence()["integrity_valid"])
    def test_method_card_source_rebind_full_rehash_rejected(self):
        s,_,_=completed();r=s._challenges[CASE_KEYS[1]];cards=list(r.methodology_cards);c=list(cards[0]);c[1]=d("foreign-stress");body=tuple(c[:-1]);c[-1]=canonical_digest(("SOURCE_BOUND_METHODOLOGY_CARD",body));cards[0]=tuple(c);full_rehash(s,1,{"methodology_cards":tuple(cards)});self.assertFalse(s.evidence()["integrity_valid"])
    def test_hidden_rollback_full_rehash_rejected(self):
        s,_,_=completed();r=s._challenges[CASE_KEYS[1]];cards=list(r.methodology_cards);c=list(cards[0]);c[13]=("rollback","REMOVED");body=tuple(c[:-1]);c[-1]=canonical_digest(("SOURCE_BOUND_METHODOLOGY_CARD",body));cards[0]=tuple(c);full_rehash(s,1,{"methodology_cards":tuple(cards)});self.assertFalse(s.evidence()["integrity_valid"])
    def test_single_method_full_rehash_rejected(self):
        s,_,_=completed();r=s._challenges[CASE_KEYS[1]];full_rehash(s,1,{"methodology_cards":r.methodology_cards[:1]});self.assertFalse(s.evidence()["integrity_valid"])
    def test_prior_source_full_downstream_rehash_rejected(self):
        """Rehash the altered prior source, this layer, both chains, and docket."""
        s,prior,_=completed();key=CASE_KEYS[1];prior_full_rehash(prior,1,{"validation_criteria":(("common",True),)})
        a=s._source;pe=prior.evidence();ad=prior._docket;vals=(ad.digest,ad.stress_set_digest,a.registry_digest,a.manifest_digest,a.lessons,a.rules,a.sequence,a.latest,pe.get("complete_role_lineage_digest"));s._source=replace(a,docket_digest=ad.digest,stress_set_digest=ad.stress_set_digest,digest=canonical_digest(vals))
        r=s._challenges[key];full_rehash(s,1,{"source_stress_digest":prior._tests[key].digest,"methodology_cards":methodology_cards(prior._tests[key])})
        dr=s._docket;p={**dr.__dict__,"source_anchor_digest":s._source.digest};p.pop("digest");s._docket=replace(dr,source_anchor_digest=s._source.digest,digest=canonical_digest(p));s._events=[];s._holds=[];s._event("PRIOR_STRESS_DOCKET_ANCHORED",s._source.digest)
        for row in s._challenges.values():
            s._event("OPTION_METHODOLOGY_CHALLENGE_RECORDED",row.digest)
            if row.pending_human_judgment:s._hold("HUMAN_METHODOLOGY_JUDGMENT_REQUIRED",row.digest)
        s._event("OPTION_METHODOLOGY_DOCKET_HELD",s._docket.digest);self.assertFalse(s.evidence()["integrity_valid"])
    def test_source_metadata_full_downstream_rehash_rejected(self):
        attacks=({"registry_digest":"not-hex"},{"manifest_digest":"not-hex"},{"sequence":True},{"sequence":0},{"latest":1},{"lessons":APPLIED_LESSONS[:-1]},{"rules":APPLIED_RULES[:-1]})
        for change in attacks:
            with self.subTest(change=change):s,_,_=completed();source_metadata_full_rehash(s,change);e=s.evidence();self.assertFalse(e["integrity_valid"]);self.assertFalse(e["complete_option_methodology_challenge_evidence"])
    def test_final_docket_semantic_full_rehash_rejected(self):
        attacks=({"status":"APPROVED"},{"held":False},{"complete":False},{"pending_human_judgment":False},{"docket_id":"synthetic:wrong:d"},{"compiler":"synthetic:wrong:c"},{"validator":"synthetic:wrong:v"})
        for change in attacks:
            with self.subTest(change=change):s,_,_=completed();docket_full_rehash(s,change);e=s.evidence();self.assertFalse(e["integrity_valid"]);self.assertFalse(e["complete_option_methodology_challenge_evidence"])
    def test_event_and_hold_tamper_rejected(self):
        s,_,_=completed();s._events[1]["artifact_digest"]=d("bad");self.assertFalse(s.evidence()["integrity_valid"]);s,_,_=completed();s._holds.pop();self.assertFalse(s.evidence()["integrity_valid"])
    def test_final_actor_reuse_rejected(self):
        s,_=challenged()
        with self.assertRaises(GovernanceRejected):s.finalize("synthetic:option-methodology-docket:d","synthetic:methodology-docket-compiler:method-challenger-1","synthetic:methodology-docket-validator:v")
    def test_no_authority_and_non_execution(self):
        e=completed()[0].evidence();self.assertTrue(e["complete_option_methodology_challenge_evidence"]);self.assertFalse(any(e[k] for k in ("judgment_authority","ranked","selected","concluded","recommended","accepted","resolved","approved","activated")));keys=("external_calls","document_transmissions","external_pg_calls","card_network_calls","payment_approvals","cancellations","refunds","settlements","transfers","ledger_writes","credential_reads","deployments");self.assertEqual(tuple(e[k] for k in keys),(0,)*len(keys))

if __name__=="__main__":unittest.main()
