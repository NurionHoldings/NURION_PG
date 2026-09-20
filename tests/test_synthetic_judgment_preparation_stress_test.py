import hashlib
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.synthetic_judgment_preparation_stress_test import *
from nurion_pg.synthetic_finding_independent_review import finding_review_digest, review_projection_digest
from tests.test_synthetic_finding_independent_review import completed as prior_completed

def d(v):return hashlib.sha256(v.encode()).hexdigest()
def populated():
    s=SyntheticJudgmentPreparationStressTest()
    for cid in range(11901,12301):
        w,a=s._expected(cid);s.add_control(cid,w,a,f"synthetic:judgment-stress-requirement:{(cid-11901)//25:02}",d(str(cid)),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    return s
def anchored():
    prior=prior_completed()[0];s=populated();s.anchor(prior,d("registry"),d("manifest"),APPLIED_LESSONS,APPLIED_RULES,26,True);return s,prior
def stressed():
    s,prior=anchored()
    for i,(flow,kind) in enumerate(CASE_KEYS):
        args=(f"synthetic:judgment-preparation-stress-test:{flow}:{kind}",flow,kind)
        if prior._reviews[(flow,kind)].judgment_packet:s.add_stress_test(*args,f"synthetic:judgment-stress-preparer:preparer-{i}",f"synthetic:judgment-stress-challenger:challenger-{i}")
        else:s.add_stress_test(*args)
    return s,prior
def completed():
    s,p=stressed();row=s.finalize("synthetic:judgment-stress-docket:d","synthetic:judgment-stress-docket-compiler:stress-final-compiler","synthetic:judgment-stress-docket-validator:stress-final-validator");return s,p,row

def rehash_attack(s,start,changes):
    """Rehash changed row, every parent, events, holds and final docket."""
    for i,key in enumerate(CASE_KEYS):
        if i<start:continue
        r=s._tests[key];values={**r.__dict__,**(changes if i==start else {})};parent=None if i==0 else s._tests[CASE_KEYS[i-1]].digest
        values["parent_stress_digest"]=parent
        projection=stress_projection(values["source_review_digest"],values["source_packet_digest"],values["preparer"],values["challenger"],values["marker"],values["option_profiles"],values["assumption_register"],values["validation_criteria"],values["residual_risks"],values["escalation_conditions"],values["rollback_conditions"]);values["stress_projection_digest"]=projection
        ordered=tuple(values[k] for k in ("stress_id","flow","answer_kind","source_review_digest","source_packet_digest","preparer","challenger","marker","parent_stress_digest","position","option_profiles","assumption_register","validation_criteria","residual_risks","escalation_conditions","rollback_conditions","stress_projection_digest","held","pending_human_judgment","ranked","selected","concluded","recommended","accepted","resolved"));values["digest"]=canonical_digest(("JUDGMENT_PREPARATION_STRESS_TEST",ordered));s._tests[key]=replace(r,**{k:v for k,v in values.items() if k in r.__dict__})
    s._events=[];s._holds=[];s._event("PRIOR_JUDGMENT_DOCKET_ANCHORED",s._source.digest)
    for r in s._tests.values():
        s._event("JUDGMENT_PREPARATION_STRESS_TEST_RECORDED",r.digest)
        if r.pending_human_judgment:s._hold("HUMAN_JUDGMENT_REQUIRED",r.digest)
    if s._docket:
        r=s._docket;stress_set=canonical_digest(tuple(s._tests[k].digest for k in CASE_KEYS));p={**r.__dict__,"stress_set_digest":stress_set};p.pop("digest");s._docket=replace(r,stress_set_digest=stress_set,digest=canonical_digest(p));s._event("COUNTERFACTUAL_STRESS_DOCKET_HELD",s._docket.digest)

class Tests(unittest.TestCase):
    def test_matrix_and_controls(self):self.assertEqual((WORKSTREAMS[0][0],WORKSTREAMS[-1][1],len(WORKSTREAMS),len(populated()._controls)),(11901,12300,16,400))
    def test_wrong_control(self):
        with self.assertRaises(GovernanceRejected):SyntheticJudgmentPreparationStressTest().add_control(11901,"BAD",CONTROL_ASPECTS[0],"synthetic:judgment-stress-requirement:00",d("x"),"PASS")
    def test_control_concurrency(self):
        s=SyntheticJudgmentPreparationStressTest();args=(11901,WORKSTREAM_NAMES[0],CONTROL_ASPECTS[0],"synthetic:judgment-stress-requirement:00",d("x"),"PASS")
        with ThreadPoolExecutor(max_workers=8) as p:rows=list(p.map(lambda _:s.add_control(*args),range(20)))
        self.assertEqual(len({x.digest for x in rows}),1)
    def test_latest_required(self):
        prior=prior_completed()[0]
        with self.assertRaises(GovernanceRejected):populated().anchor(prior,d("r"),d("m"),APPLIED_LESSONS,APPLIED_RULES,26,False)
    def test_partial_batch_fail_closed(self):
        with self.assertRaises(GovernanceRejected):anchored()[0].finalize("synthetic:judgment-stress-docket:d","synthetic:judgment-stress-docket-compiler:c","synthetic:judgment-stress-docket-validator:v")
    def test_immediate_parent_required(self):
        s,p=anchored()
        with self.assertRaises(GovernanceRejected):s.add_stress_test("synthetic:judgment-preparation-stress-test:x",*CASE_KEYS[1],"synthetic:judgment-stress-preparer:x","synthetic:judgment-stress-challenger:y")
    def test_na_forbids_actors(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected):s.add_stress_test("synthetic:judgment-preparation-stress-test:x",*CASE_KEYS[0],"synthetic:judgment-stress-preparer:x","synthetic:judgment-stress-challenger:y")
    def test_routed_requires_actors(self):
        s,_=anchored();s.add_stress_test("synthetic:judgment-preparation-stress-test:a",*CASE_KEYS[0])
        with self.assertRaises(GovernanceRejected):s.add_stress_test("synthetic:judgment-preparation-stress-test:b",*CASE_KEYS[1])
    def test_prior_actor_reuse_rejected(self):
        s,p=anchored();s.add_stress_test("synthetic:judgment-preparation-stress-test:a",*CASE_KEYS[0]);identity=p._reviews[CASE_KEYS[1]].reviewer.rsplit(":",1)[-1]
        with self.assertRaises(GovernanceRejected):s.add_stress_test("synthetic:judgment-preparation-stress-test:b",*CASE_KEYS[1],f"synthetic:judgment-stress-preparer:{identity}","synthetic:judgment-stress-challenger:y")
    def test_counts(self):
        e=completed()[0].evidence();self.assertEqual((e["stress_test_count"],e["option_profile_count"],e["no_judgment_marker_count"],e["human_judgment_hold_count"]),(20,32,4,16))
    def test_source_bound_distinct_options(self):
        row=stressed()[0]._tests[CASE_KEYS[1]];self.assertEqual(len(row.option_profiles),2);self.assertEqual(len({p[-1] for p in row.option_profiles}),2);self.assertTrue(all(p[1]==row.source_review_digest and p[2]==row.source_packet_digest for p in row.option_profiles))
    def test_single_alternative_full_rehash_rejected(self):
        """ETH-11501-AUDIT-001: count-only alternatives cannot survive rehash."""
        s,_,_=completed();r=s._tests[CASE_KEYS[1]];profiles=r.option_profiles[:1];rehash_attack(s,1,{"option_profiles":profiles,"assumption_register":r.assumption_register[:1]});self.assertFalse(s.evidence()["integrity_valid"])
    def test_hidden_assumption_full_rehash_rejected(self):
        s,_,_=completed();r=s._tests[CASE_KEYS[1]];rehash_attack(s,1,{"assumption_register":r.assumption_register[:1]});self.assertFalse(s.evidence()["integrity_valid"])
    def test_source_option_rebind_rejected(self):
        s,_,_=completed();r=s._tests[CASE_KEYS[1]];foreign=d("other-source");profiles=option_profiles(foreign,r.source_packet_digest);assumptions=tuple((p[0],p[8],p[-1]) for p in profiles);rehash_attack(s,1,{"source_review_digest":foreign,"option_profiles":profiles,"assumption_register":assumptions});self.assertFalse(s.evidence()["integrity_valid"])
    def test_source_bundle_digest_full_rehash_tamper_rejected(self):
        s,_,_=completed();b=s._source;reviews=list(b.reviews);reviews[1],reviews[2]=reviews[2],reviews[1];reviews=tuple(reviews);bundle=source_bundle_digest(b.anchor,reviews,b.docket);s._source=replace(b,reviews=reviews,source_bundle_digest=bundle,digest=source_record_digest(b.anchor,reviews,b.docket,bundle,b.lesson_registry_digest,b.remediation_manifest_digest,b.applied_lesson_ids,b.applied_rule_ids,b.source_sequence,b.is_latest));self.assertFalse(s._source_valid());self.assertFalse(s.evidence()["integrity_valid"])
    def test_prior_judgment_packet_full_downstream_rehash_rejected(self):
        s,_,_=completed();b=s._source;reviews=list(b.reviews);i=1;r=reviews[i];packet=list(r.judgment_packet);packet[0]=(packet[0][0],tuple(list(packet[0][1])[:-1]));packet=tuple(packet);packet_digest=canonical_digest(packet)
        for j in range(i,len(reviews)):
            old=reviews[j];parent=None if j==0 else reviews[j-1].digest
            if j==i:projection=review_projection_digest(old.source_finding_digest,old.route,old.reviewer,old.custodian,old.marker,packet_digest);digest=finding_review_digest(old.review_id,old.flow,old.answer_kind,old.source_finding_digest,old.route,old.reviewer,old.custodian,old.marker,parent,j+1,packet,packet_digest,projection);reviews[j]=replace(old,parent_review_digest=parent,judgment_packet=packet,judgment_packet_digest=packet_digest,review_projection_digest=projection,digest=digest)
            else:digest=finding_review_digest(old.review_id,old.flow,old.answer_kind,old.source_finding_digest,old.route,old.reviewer,old.custodian,old.marker,parent,j+1,old.judgment_packet,old.judgment_packet_digest,old.review_projection_digest);reviews[j]=replace(old,parent_review_digest=parent,digest=digest)
        reviews=tuple(reviews);docket=b.docket;p={**docket.__dict__,"review_set_digest":canonical_digest(tuple(x.digest for x in reviews))};p.pop("digest");docket=replace(docket,review_set_digest=p["review_set_digest"],digest=canonical_digest(p));bundle=source_bundle_digest(b.anchor,reviews,docket);source=replace(b,reviews=reviews,docket=docket,source_bundle_digest=bundle,digest=source_record_digest(b.anchor,reviews,docket,bundle,b.lesson_registry_digest,b.remediation_manifest_digest,b.applied_lesson_ids,b.applied_rule_ids,b.source_sequence,b.is_latest));s._source=source
        rr=reviews[i];profiles=option_profiles(rr.digest,rr.judgment_packet_digest);rehash_attack(s,i,{"source_review_digest":rr.digest,"source_packet_digest":rr.judgment_packet_digest,"option_profiles":profiles,"assumption_register":tuple((p[0],p[8],p[-1]) for p in profiles)});self.assertFalse(s.evidence()["integrity_valid"])
    def test_selection_authority_tamper_rejected(self):
        s,_=stressed();key=CASE_KEYS[1];s._tests[key]=replace(s._tests[key],selected=True,digest=d("rehash"));self.assertFalse(s.evidence()["integrity_valid"])
    def test_missing_hold_rejected(self):s,_=stressed();s._holds.pop();self.assertFalse(s.evidence()["integrity_valid"])
    def test_event_tamper_rejected(self):s,_=stressed();s._events[1]["artifact_digest"]=d("bad");self.assertFalse(s.evidence()["integrity_valid"])
    def test_final_actor_reuse_rejected(self):
        s,_=stressed()
        with self.assertRaises(GovernanceRejected):s.finalize("synthetic:judgment-stress-docket:d","synthetic:judgment-stress-docket-compiler:preparer-1","synthetic:judgment-stress-docket-validator:v")
    def test_safe_docket(self):r=completed()[2];self.assertFalse(any((r.ranked,r.selected,r.concluded,r.recommended,r.accepted,r.resolved,r.approved,r.activated,r.deployed)))
    def test_content_addressed_results(self):
        e=completed()[0].evidence();self.assertTrue(all(isinstance(e[k],str) and len(e[k])==64 for k in ("source_bundle_digest","stress_projection_set_digest","stress_set_digest","final_docket_digest","complete_role_lineage_digest")))
    def test_non_execution(self):
        e=completed()[0].evidence();keys=("external_calls","document_transmissions","external_pg_calls","card_network_calls","payment_approvals","cancellations","refunds","settlements","transfers","ledger_writes","credential_reads","deployments");self.assertEqual(tuple(e[k] for k in keys),(0,)*len(keys))

if __name__=="__main__":unittest.main()
