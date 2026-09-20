import hashlib
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from nurion_pg.arkaon.governance import GovernanceRejected,canonical_digest
from nurion_pg.synthetic_versioned_lesson_recovery_guidance import *
from tests.test_synthetic_option_methodology_independent_challenge import completed as prior_completed,full_rehash as prior_full_rehash

def d(v):return hashlib.sha256(v.encode()).hexdigest()
def populated():
    s=SyntheticVersionedLessonRecoveryGuidance()
    for cid in range(12701,13101):
        w,a=s._expected(cid);s.add_control(cid,w,a,f"synthetic:recovery-guidance-requirement:{(cid-12701)//25:02}",d(str(cid)),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    return s
def anchored():
    p=prior_completed()[0];s=populated();prior_registry=d("prior-registry");previous=source_stage_snapshot_digest("ARKAON-LESSONS-12301",(9901,12700),PRIOR_LESSONS,APPLIED_RULES,prior_registry,d("manifest"),p._docket.digest);s.anchor(p,d("registry"),d("manifest"),APPLIED_LESSONS,APPLIED_RULES,prior_registry,previous,28,True);return s,p
def guided():
    s,p=anchored()
    for i,key in enumerate(CASE_KEYS):
        args=(f"synthetic:versioned-recovery-guidance:{key[0]}:{key[1]}",*key)
        if p._challenges[key].methodology_cards:s.add_guidance(*args,f"synthetic:recovery-guidance-reviewer:guide-reviewer-{i}",f"synthetic:recovery-guidance-verifier:guide-verifier-{i}")
        else:s.add_guidance(*args)
    return s,p
def completed():
    s,p=guided();r=s.finalize("synthetic:recovery-guidance-docket:d","synthetic:recovery-docket-compiler:final-compiler","synthetic:recovery-docket-validator:final-validator");return s,p,r
def full_rehash(s,start,changes):
    for i,key in enumerate(CASE_KEYS):
        if i<start:continue
        r=s._guidance[key];v={**r.__dict__,**(changes if i==start else {})};v["parent_digest"]=None if i==0 else s._guidance[CASE_KEYS[i-1]].digest;v["projection_digest"]=projection(v["source_challenge_digest"],v["reviewer"],v["verifier"],v["marker"],v["rejection_reason"],v["safe_candidate"],v["alternatives"]);ordered=tuple(v[k] for k in ("guidance_id","flow","answer_kind","source_challenge_digest","reviewer","verifier","marker","parent_digest","position","rejection_reason","safe_candidate","alternatives","projection_digest","held","pending_human_judgment","ranked","selected","concluded","recommended","accepted","resolved"));v["digest"]=canonical_digest(("VERSIONED_LESSON_RECOVERY_GUIDANCE",ordered));s._guidance[key]=replace(r,**{k:x for k,x in v.items() if k in r.__dict__})
    s._events=[];s._holds=[];s._event("VERSIONED_LESSON_SNAPSHOT_ANCHORED",s._snapshot.digest)
    for r in s._guidance.values():
        s._event("RECOVERY_GUIDANCE_RECORDED",r.digest)
        if r.pending_human_judgment:s._hold("HUMAN_RECOVERY_PATH_JUDGMENT_REQUIRED",r.digest)
    if s._docket:
        r=s._docket;gset=canonical_digest(tuple(s._guidance[k].digest for k in CASE_KEYS));p={**r.__dict__,"guidance_set_digest":gset};p.pop("digest");s._docket=replace(r,guidance_set_digest=gset,digest=canonical_digest(p));s._event("RECOVERY_GUIDANCE_DOCKET_HELD",s._docket.digest)
def snapshot_full_rehash(s,changes):
    r=s._snapshot;v={**r.__dict__,**changes};p={k:x for k,x in v.items() if k!="digest"};s._snapshot=replace(r,**{**changes,"digest":canonical_digest(p)});full_rehash(s,0,{})
    if s._docket:
        r=s._docket;p={**r.__dict__,"snapshot_digest":s._snapshot.digest};p.pop("digest");s._docket=replace(r,snapshot_digest=s._snapshot.digest,digest=canonical_digest(p));s._events[-1]["artifact_digest"]=s._docket.digest;ep={k:s._events[-1][k] for k in ("sequence","action","artifact_digest","previous_digest")};s._events[-1]["digest"]=canonical_digest(ep)

class Tests(unittest.TestCase):
    def test_matrix_exactly_400(self):self.assertEqual((WORKSTREAMS[0][0],WORKSTREAMS[-1][1],len(WORKSTREAMS),len(populated()._controls)),(12701,13100,16,400))
    def test_wrong_control_rejected(self):
        with self.assertRaises(GovernanceRejected):SyntheticVersionedLessonRecoveryGuidance().add_control(12701,"BAD",CONTROL_ASPECTS[0],"synthetic:recovery-guidance-requirement:00",d("x"),"PASS")
    def test_control_concurrency_idempotent(self):
        s=SyntheticVersionedLessonRecoveryGuidance();args=(12701,WORKSTREAM_NAMES[0],CONTROL_ASPECTS[0],"synthetic:recovery-guidance-requirement:00",d("x"),"PASS")
        with ThreadPoolExecutor(max_workers=8) as p:rows=list(p.map(lambda _:s.add_control(*args),range(20)))
        self.assertEqual(len({x.digest for x in rows}),1)
    def test_latest_snapshot_required(self):
        p=prior_completed()[0]
        prior_registry=d("prior-registry");previous=source_stage_snapshot_digest("ARKAON-LESSONS-12301",(9901,12700),PRIOR_LESSONS,APPLIED_RULES,prior_registry,d("m"),p._docket.digest)
        with self.assertRaises(GovernanceRejected):populated().anchor(p,d("r"),d("m"),APPLIED_LESSONS,APPLIED_RULES,prior_registry,previous,28,False)
    def test_partial_batch_fail_closed(self):
        with self.assertRaises(GovernanceRejected):anchored()[0].finalize("synthetic:recovery-guidance-docket:d","synthetic:recovery-docket-compiler:c","synthetic:recovery-docket-validator:v")
    def test_immediate_parent_required(self):
        s,p=anchored()
        with self.assertRaises(GovernanceRejected):s.add_guidance("synthetic:versioned-recovery-guidance:x",*CASE_KEYS[1],"synthetic:recovery-guidance-reviewer:x","synthetic:recovery-guidance-verifier:y")
    def test_na_forbids_actors(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected):s.add_guidance("synthetic:versioned-recovery-guidance:x",*CASE_KEYS[0],"synthetic:recovery-guidance-reviewer:x","synthetic:recovery-guidance-verifier:y")
    def test_routed_requires_independent_actors(self):
        s,_=anchored();s.add_guidance("synthetic:versioned-recovery-guidance:a",*CASE_KEYS[0])
        with self.assertRaises(GovernanceRejected):s.add_guidance("synthetic:versioned-recovery-guidance:b",*CASE_KEYS[1])
    def test_counts_and_guided_alternatives(self):
        s,_,_=completed();e=s.evidence();self.assertEqual((e["guidance_count"],e["recovery_alternative_count"],e["no_guidance_marker_count"],e["human_judgment_hold_count"]),(20,32,4,16));g=s._guidance[CASE_KEYS[1]];self.assertEqual(len(g.alternatives),2);self.assertEqual(g.safe_candidate[2],"NONBINDING")
    def test_stage_snapshot_lesson_omission_full_rehash_rejected(self):
        s,_,_=completed();snapshot_full_rehash(s,{"lesson_ids":APPLIED_LESSONS[:-1]});self.assertFalse(s.evidence()["integrity_valid"])
    def test_stage_snapshot_predecessor_tamper_full_rehash_rejected(self):
        s,_,_=completed();snapshot_full_rehash(s,{"previous_snapshot_digest":"not-hex"});self.assertFalse(s.evidence()["integrity_valid"])
    def test_unreconstructable_predecessor_snapshot_rejected(self):
        p=prior_completed()[0]
        with self.assertRaises(GovernanceRejected):populated().anchor(p,d("registry"),d("manifest"),APPLIED_LESSONS,APPLIED_RULES,d("prior-registry"),d("arbitrary"),28,True)
    def test_stage_snapshot_range_rebind_full_rehash_rejected(self):
        s,_,_=completed();snapshot_full_rehash(s,{"stage_range":(1,2)});self.assertFalse(s.evidence()["integrity_valid"])
    def test_single_recovery_path_full_rehash_rejected(self):
        s,_,_=completed();r=s._guidance[CASE_KEYS[1]];full_rehash(s,1,{"alternatives":r.alternatives[:1]});self.assertFalse(s.evidence()["integrity_valid"])
    def test_recovery_assumption_hidden_full_rehash_rejected(self):
        s,_,_=completed();r=s._guidance[CASE_KEYS[1]];alts=list(r.alternatives);a=list(alts[0]);a[3]=("assumption","VERIFIED",r.source_challenge_digest);body=tuple(a[:-1]);a[-1]=canonical_digest(("RECOVERY_ALTERNATIVE",body));alts[0]=tuple(a);full_rehash(s,1,{"alternatives":tuple(alts)});self.assertFalse(s.evidence()["integrity_valid"])
    def test_recovery_validation_removed_full_rehash_rejected(self):
        s,_,_=completed();r=s._guidance[CASE_KEYS[1]];alts=list(r.alternatives);a=list(alts[0]);a[6]=("validation_criteria","COMMON_ONLY");body=tuple(a[:-1]);a[-1]=canonical_digest(("RECOVERY_ALTERNATIVE",body));alts[0]=tuple(a);full_rehash(s,1,{"alternatives":tuple(alts)});self.assertFalse(s.evidence()["integrity_valid"])
    def test_recovery_rollback_removed_full_rehash_rejected(self):
        s,_,_=completed();r=s._guidance[CASE_KEYS[1]];alts=list(r.alternatives);a=list(alts[0]);a[12]=("rollback","REMOVED");body=tuple(a[:-1]);a[-1]=canonical_digest(("RECOVERY_ALTERNATIVE",body));alts[0]=tuple(a);full_rehash(s,1,{"alternatives":tuple(alts)});self.assertFalse(s.evidence()["integrity_valid"])
    def test_prior_source_full_downstream_rehash_rejected(self):
        s,p,_=completed();key=CASE_KEYS[1];prior_full_rehash(p,1,{"methodology_cards":p._challenges[key].methodology_cards[:1]});r=s._snapshot;p0={**r.__dict__,"source_docket_digest":p._docket.digest};p0.pop("digest");s._snapshot=replace(r,source_docket_digest=p._docket.digest,digest=canonical_digest(p0));full_rehash(s,1,{"source_challenge_digest":p._challenges[key].digest,"alternatives":recovery_alternatives(p._challenges[key])});self.assertFalse(s.evidence()["integrity_valid"])
    def test_event_and_hold_tamper_rejected(self):
        s,_,_=completed();s._events[1]["artifact_digest"]=d("bad");self.assertFalse(s.evidence()["integrity_valid"]);s,_,_=completed();s._holds.pop();self.assertFalse(s.evidence()["integrity_valid"])
    def test_final_actor_reuse_rejected(self):
        s,_=guided()
        with self.assertRaises(GovernanceRejected):s.finalize("synthetic:recovery-guidance-docket:d","synthetic:recovery-docket-compiler:guide-reviewer-1","synthetic:recovery-docket-validator:v")
    def test_no_authority_and_non_execution(self):
        e=completed()[0].evidence();self.assertTrue(e["complete_versioned_recovery_guidance_evidence"]);self.assertFalse(any(e[k] for k in ("judgment_authority","ranked","selected","concluded","recommended","accepted","resolved","approved","activated")));keys=("external_calls","document_transmissions","external_pg_calls","card_network_calls","payment_approvals","cancellations","refunds","settlements","transfers","ledger_writes","credential_reads","deployments");self.assertEqual(tuple(e[k] for k in keys),(0,)*len(keys))

if __name__=="__main__":unittest.main()
