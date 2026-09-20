from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from hashlib import sha256
import unittest

from nurion_pg.arkaon.governance import GovernanceRejected,canonical_digest
from nurion_pg.synthetic_recovery_preflight_audit import *
from tests.test_synthetic_versioned_lesson_recovery_guidance import completed as prior_completed

def d(v):return sha256(v.encode()).hexdigest()
def populated():
    s=SyntheticRecoveryPreflightAudit()
    for cid in range(13101,13501):
        w,a=s._expected(cid);s.add_control(cid,w,a,f"synthetic:recovery-preflight-requirement:{(cid-13101)//25:02}",d(str(cid)),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    return s
def anchored():
    p=prior_completed()[0];s=populated();s.anchor(p,mapping_digest(STAGE_MAPPING),d("registry"),d("manifest"),APPLIED_LESSONS,APPLIED_RULES,p._snapshot.digest,29,True);return s,p
def audited():
    s,p=anchored()
    for i,key in enumerate(CASE_KEYS):
        args=(f"synthetic:recovery-preflight-audit:{key[0]}:{key[1]}",*key)
        if p._guidance[key].alternatives:s.add_audit(*args,f"synthetic:recovery-preflight-auditor:a-{i}",f"synthetic:recovery-preflight-verifier:v-{i}")
        else:s.add_audit(*args)
    return s,p
def completed():
    s,p=audited();s.finalize("synthetic:preflight-docket:final","synthetic:preflight-docket-compiler:c","synthetic:preflight-docket-validator:v");return s,p
def full_rehash(s,start,changes):
    for i in range(start,len(CASE_KEYS)):
        key=CASE_KEYS[i];r=s._audits[key];v={**r.__dict__,**(changes if i==start else {})};v["parent_digest"]=None if i==0 else s._audits[CASE_KEYS[i-1]].digest;values=tuple(v[k] for k in ("audit_id","flow","kind","source_guidance_digest","cause_evidence","cause","auditor","verifier","marker","parent_digest","position","options","held","pending_human_judgment","ranked","selected","concluded","recommended","accepted","resolved"));v["digest"]=canonical_digest(("RECOVERY_PREFLIGHT_AUDIT",values));s._audits[key]=replace(r,**{k:x for k,x in v.items() if k in r.__dict__})
    s._events=[];s._holds=[];s._event("AUTOMATED_STAGE_CHAIN_ANCHORED",s._snapshot.digest)
    for r in s._audits.values():
        s._event("RECOVERY_PREFLIGHT_AUDITED",r.digest)
        if r.pending_human_judgment:s._hold("HUMAN_RECOVERY_SELECTION_REQUIRED",r.digest)
    if s._docket:
        r=s._docket;aset=canonical_digest(tuple(s._audits[k].digest for k in CASE_KEYS));p={**r.__dict__,"audit_set_digest":aset};p.pop("digest");s._docket=replace(r,audit_set_digest=aset,digest=canonical_digest(p));s._event("RECOVERY_PREFLIGHT_DOCKET_HELD",s._docket.digest)

class Tests(unittest.TestCase):
    def test_matrix_exactly_400(self):self.assertEqual((len(WORKSTREAMS),len(populated()._controls),WORKSTREAMS[0][0],WORKSTREAMS[-1][1]),(16,400,13101,13500))
    def test_wrong_control_rejected(self):
        with self.assertRaises(GovernanceRejected):SyntheticRecoveryPreflightAudit().add_control(13101,"BAD",CONTROL_ASPECTS[0],"synthetic:recovery-preflight-requirement:00",d("x"),"PASS")
    def test_control_concurrency_idempotent(self):
        s=SyntheticRecoveryPreflightAudit();args=(13101,WORKSTREAM_NAMES[0],CONTROL_ASPECTS[0],"synthetic:recovery-preflight-requirement:00",d("x"),"PASS")
        with ThreadPoolExecutor(max_workers=8) as pool:rows=list(pool.map(lambda _:s.add_control(*args),range(20)))
        self.assertEqual(len({x.digest for x in rows}),1)
    def test_latest_required(self):
        p=prior_completed()[0]
        with self.assertRaises(GovernanceRejected):populated().anchor(p,mapping_digest(STAGE_MAPPING),d("r"),d("m"),APPLIED_LESSONS,APPLIED_RULES,p._snapshot.digest,29,False)
    def test_partial_batch_fail_closed(self):
        with self.assertRaises(GovernanceRejected):anchored()[0].finalize("synthetic:preflight-docket:x","synthetic:preflight-docket-compiler:c","synthetic:preflight-docket-validator:v")
    def test_immediate_parent_required(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected):s.add_audit("synthetic:recovery-preflight-audit:x",*CASE_KEYS[1],"synthetic:recovery-preflight-auditor:a","synthetic:recovery-preflight-verifier:v")
    def test_na_forbids_actors(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected):s.add_audit("synthetic:recovery-preflight-audit:x",*CASE_KEYS[0],"synthetic:recovery-preflight-auditor:a","synthetic:recovery-preflight-verifier:v")
    def test_counts_and_distinct_preflights(self):
        s,_=completed();e=s.evidence();self.assertEqual((e["audit_count"],e["diagnostic_option_count"],e["undetermined_cause_count"],e["no_preflight_marker_count"],e["human_judgment_hold_count"]),(20,32,16,4,16));r=s._audits[CASE_KEYS[1]];self.assertEqual(r.cause,"CAUSE_UNDETERMINED");self.assertTrue(all(x[1]=="NOT_RUN" for x in r.cause_evidence[5]));self.assertNotEqual(r.options[0][0],r.options[1][0]);self.assertNotEqual(r.options[0][6],r.options[1][6])
    def test_wrong_cause_full_rehash_rejected(self):
        s,_=completed();full_rehash(s,1,{"cause":"SOURCE_SEMANTIC_MISMATCH","options":recovery_options(s._source._guidance[CASE_KEYS[1]],"SOURCE_SEMANTIC_MISMATCH")});self.assertFalse(s.evidence()["integrity_valid"])
    def test_cause_evidence_removed_full_rehash_rejected(self):
        s,_=completed();full_rehash(s,1,{"cause_evidence":None});self.assertFalse(s.evidence()["integrity_valid"])
    def test_ambiguous_promoted_to_certain_full_rehash_rejected(self):
        s,_=completed();r=s._audits[CASE_KEYS[1]];full_rehash(s,1,{"cause":"LINEAGE_DISCONTINUITY","options":recovery_options(s._source._guidance[CASE_KEYS[1]],"LINEAGE_DISCONTINUITY")});self.assertFalse(s.evidence()["integrity_valid"])
    def test_probe_pass_forgery_full_rehash_rejected(self):
        s,_=completed();r=s._audits[CASE_KEYS[1]];ev=list(r.cause_evidence);probes=list(ev[5]);probes[0]=(probes[0][0],"PASS");ev[5]=tuple(probes);ev[-1]=canonical_digest(tuple(ev[:-1]));forged=tuple(ev);full_rehash(s,1,{"cause_evidence":forged,"cause":"SOURCE_SEMANTIC_MISMATCH","options":recovery_options(s._source._guidance[CASE_KEYS[1]],"SOURCE_SEMANTIC_MISMATCH")});self.assertFalse(s.evidence()["integrity_valid"])
    def test_duplicate_strategy_full_rehash_rejected(self):
        s,_=completed();r=s._audits[CASE_KEYS[1]];full_rehash(s,1,{"options":(r.options[0],r.options[0])});self.assertFalse(s.evidence()["integrity_valid"])
    def test_preflight_removed_full_rehash_rejected(self):
        s,_=completed();r=s._audits[CASE_KEYS[1]];opts=list(r.options);a=list(opts[0]);a[6]=("preflight","REMOVED");a[-1]=canonical_digest(("CAUSE_FIT_RECOVERY_OPTION",tuple(a[:-1])));opts[0]=tuple(a);full_rehash(s,1,{"options":tuple(opts)});self.assertFalse(s.evidence()["integrity_valid"])
    def test_prior_guidance_full_downstream_rehash_rejected(self):
        s,p=completed();key=CASE_KEYS[1];old=p._guidance[key];p._guidance[key]=replace(old,rejection_reason="REBOUND",digest=d("rebound"));challenge=p._source._challenges[key];ev=cause_evidence(p._guidance[key],challenge,s._snapshot.digest);full_rehash(s,1,{"source_guidance_digest":p._guidance[key].digest,"cause_evidence":ev,"cause":classified_cause(ev),"options":recovery_options(p._guidance[key],classified_cause(ev))});self.assertFalse(s.evidence()["integrity_valid"])
    def test_same_row_idempotent_and_conflict_rejected(self):
        s,p=anchored();key=CASE_KEYS[0];args=("synthetic:recovery-preflight-audit:idempotent",*key);a=s.add_audit(*args);self.assertIs(a,s.add_audit(*args))
        with self.assertRaises(GovernanceRejected):s.add_audit("synthetic:recovery-preflight-audit:conflict",*key)
    def test_same_row_concurrent_idempotent(self):
        s,p=anchored();key=CASE_KEYS[0];args=("synthetic:recovery-preflight-audit:concurrent",*key)
        with ThreadPoolExecutor(max_workers=8) as pool:rows=list(pool.map(lambda _:s.add_audit(*args),range(20)))
        self.assertEqual(len({x.digest for x in rows}),1)
    def test_mapping_tamper_full_rehash_rejected(self):
        s,_=completed();r=s._snapshot;p={**r.__dict__,"mapping_digest":d("attacker")};p.pop("digest");s._snapshot=replace(r,mapping_digest=d("attacker"),digest=canonical_digest(p));self.assertFalse(s.evidence()["integrity_valid"])
    def test_event_and_hold_tamper_rejected(self):
        s,_=completed();s._events[1]["artifact_digest"]=d("bad");self.assertFalse(s.evidence()["integrity_valid"]);s,_=completed();s._holds.pop();self.assertFalse(s.evidence()["integrity_valid"])
    def test_final_actor_reuse_rejected(self):
        s,_=audited()
        with self.assertRaises(GovernanceRejected):s.finalize("synthetic:preflight-docket:x","synthetic:preflight-docket-compiler:a-1","synthetic:preflight-docket-validator:v")
    def test_no_authority_and_non_execution(self):
        e=completed()[0].evidence();self.assertTrue(e["complete_recovery_preflight_audit_evidence"]);self.assertFalse(any(e[k] for k in ("judgment_authority","ranked","selected","concluded","recommended","accepted","resolved","approved","activated")));keys=("external_calls","document_transmissions","external_pg_calls","card_network_calls","payment_approvals","cancellations","refunds","settlements","transfers","ledger_writes","credential_reads","deployments");self.assertEqual(tuple(e[k] for k in keys),(0,)*len(keys))

if __name__=="__main__":unittest.main()
