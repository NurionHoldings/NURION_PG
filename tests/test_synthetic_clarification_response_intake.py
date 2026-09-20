import hashlib, unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.synthetic_clarification_response_intake import *
def d(v):return hashlib.sha256(v.encode()).hexdigest()
def rehash(r,**changes):
    v=replace(r,**changes);p={k:x for k,x in v.__dict__.items() if k!="digest"}
    if "source_requests" in p:p["source_requests"]=tuple(tuple(x.__dict__.values()) for x in p["source_requests"])
    return replace(v,digest=canonical_digest(p))
def sources():
    rows=[]
    for f in FLOWS:
        for i,k in enumerate(ANSWER_KINDS):
            o=OUTCOMES[i];t=REQUEST_TYPES[o];issue=d(f"issue:{f}:{k}");parent=None if not rows else rows[-1].request_digest;required=o!="CONSISTENT";rd=request_digest(f,k,o,t,issue,parent,required);rows.append(SourceRequest(f,k,o,t,issue,parent,required,rd))
    return tuple(rows)
def populated():
    s=SyntheticClarificationResponseIntake()
    for cid in range(9501,9901):
        w,a=s._expected(cid);s.add_control(cid,w,a,f"synthetic:response-intake-requirement:{(cid-9501)//25:02}",d(str(cid)),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    return s
def anchored():
    s=populated();rs=sources();rset=canonical_digest(tuple(x.request_digest for x in rs));roles=tuple(f"synthetic:{kind}:{i}" for i,kind in enumerate(SOURCE_ROLE_KINDS));docket=canonical_digest(("HUMAN_CLARIFICATION_DOCKET_SOURCE",rset,roles));a=s.anchor_docket("synthetic:response-intake-anchor:a",docket,rset,d("registry"),d("manifest"),APPLIED_LESSONS,APPLIED_RULES,rs,roles,20,True);return s,a
def filled():
    s,a=anchored()
    for f in FLOWS:
        for i,k in enumerate(ANSWER_KINDS):
            args=(f"synthetic:clarification-response-intake:{f}:{k}",f,k)
            s.add_intake(*args,RESPONDER[f],d(f"response:{f}:{k}")) if i else s.add_intake(*args)
    return s,a
def completed():
    s,a=filled();return s,a,s.finalize("synthetic:clarification-response-intake-docket:d","synthetic:response-intake-compiler:c","synthetic:response-intake-validator:v")
class Tests(unittest.TestCase):
    def test_matrix(self):self.assertEqual((WORKSTREAMS[0][0],WORKSTREAMS[-1][1],len(WORKSTREAMS)),(9501,9900,16));self.assertTrue(all(e-s+1==25 for s,e,_ in WORKSTREAMS))
    def test_exact_controls(self):self.assertEqual(set(populated()._controls),set(range(9501,9901)))
    def test_wrong_control(self):
        with self.assertRaises(GovernanceRejected):SyntheticClarificationResponseIntake().add_control(9501,"BAD",CONTROL_ASPECTS[0],"synthetic:response-intake-requirement:00",d("x"),"PASS")
    def test_control_conflict(self):
        s=SyntheticClarificationResponseIntake();a=(9501,WORKSTREAM_NAMES[0],CONTROL_ASPECTS[0],"synthetic:response-intake-requirement:00",d("x"),"PASS");r=s.add_control(*a);self.assertIs(r,s.add_control(*a))
        with self.assertRaises(GovernanceRejected):s.add_control(*a[:-2],d("y"),"PASS")
    def test_slot_swap(self):
        s=populated();s._controls[9501],s._controls[9502]=s._controls[9502],s._controls[9501];self.assertFalse(s.evidence()["integrity_valid"])
    def test_anchor_requires_controls(self):
        with self.assertRaises(GovernanceRejected):SyntheticClarificationResponseIntake().anchor_docket("x",d("d"),d("s"),d("r"),d("m"),(),(),(),(),1,True)
    def test_anchor_latest(self):
        s,a=anchored();s._anchor=None
        with self.assertRaises(GovernanceRejected):s.anchor_docket(a.anchor_id,a.source_docket_digest,a.request_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest,a.applied_lesson_ids,a.applied_rule_ids,a.source_requests,a.source_roles,a.source_sequence,False)
    def test_lessons_exact(self):
        s,a=anchored();s._anchor=None
        with self.assertRaises(GovernanceRejected):s.anchor_docket(a.anchor_id,a.source_docket_digest,a.request_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest,a.applied_lesson_ids[:-1],a.applied_rule_ids,a.source_requests,a.source_roles,a.source_sequence,True)
    def test_source_request_outcome_rehash_tamper(self):
        s,a=anchored();rs=list(a.source_requests);r=rs[0];rs[0]=replace(r,outcome="CLAIM_CONFLICT",request_type="CLARIFY_CLAIM_MEANING",response_required=True,request_digest=request_digest(r.flow,r.answer_kind,"CLAIM_CONFLICT","CLARIFY_CLAIM_MEANING",r.source_issue_digest,None,True));rs=tuple(rs);rset=canonical_digest(tuple(x.request_digest for x in rs));docket=canonical_digest(("HUMAN_CLARIFICATION_DOCKET_SOURCE",rset,a.source_roles));lineage=canonical_digest(("CLARIFICATION_DOCKET_FULL_LINEAGE",docket,rset,tuple(x.request_digest for x in rs),a.source_roles));s._anchor=rehash(a,source_requests=rs,request_set_digest=rset,source_docket_digest=docket,source_lineage_digest=lineage);self.assertFalse(s.evidence()["integrity_valid"])
    def test_source_parent_rehash_tamper(self):
        s,a=anchored();rs=list(a.source_requests);r=rs[1];bad=d("bad");rs[1]=replace(r,parent_request_digest=bad,request_digest=request_digest(r.flow,r.answer_kind,r.outcome,r.request_type,r.source_issue_digest,bad,r.response_required));rs=tuple(rs);rset=canonical_digest(tuple(x.request_digest for x in rs));docket=canonical_digest(("HUMAN_CLARIFICATION_DOCKET_SOURCE",rset,a.source_roles));lineage=canonical_digest(("CLARIFICATION_DOCKET_FULL_LINEAGE",docket,rset,tuple(x.request_digest for x in rs),a.source_roles));s._anchor=rehash(a,source_requests=rs,request_set_digest=rset,source_docket_digest=docket,source_lineage_digest=lineage);self.assertFalse(s.evidence()["integrity_valid"])
    def test_partial_source_rejected(self):
        s,a=anchored();s._anchor=None;rs=a.source_requests[:-1];rset=canonical_digest(tuple(x.request_digest for x in rs));docket=canonical_digest(("HUMAN_CLARIFICATION_DOCKET_SOURCE",rset,a.source_roles))
        with self.assertRaises(GovernanceRejected):s.anchor_docket(a.anchor_id,docket,rset,a.lesson_registry_digest,a.remediation_manifest_digest,a.applied_lesson_ids,a.applied_rule_ids,rs,a.source_roles,a.source_sequence,True)
    def test_source_role_namespace_rehash_tamper(self):
        s,a=anchored();roles=list(a.source_roles);roles[0]="synthetic:arbitrary-role:0";roles=tuple(roles);docket=canonical_digest(("HUMAN_CLARIFICATION_DOCKET_SOURCE",a.request_set_digest,roles));lineage=canonical_digest(("CLARIFICATION_DOCKET_FULL_LINEAGE",docket,a.request_set_digest,tuple(x.request_digest for x in a.source_requests),roles));s._anchor=rehash(a,source_roles=roles,source_docket_digest=docket,source_lineage_digest=lineage);self.assertFalse(s.evidence()["integrity_valid"])
    def test_response_requires_anchor(self):
        with self.assertRaises(GovernanceRejected):SyntheticClarificationResponseIntake().add_intake("synthetic:clarification-response-intake:x",FLOWS[0],ANSWER_KINDS[0])
    def test_consistent_forbids_response(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected):s.add_intake("synthetic:clarification-response-intake:x",FLOWS[0],ANSWER_KINDS[0],RESPONDER[FLOWS[0]],d("x"))
    def test_conflict_requires_response(self):
        s,_=anchored();s.add_intake("synthetic:clarification-response-intake:x",FLOWS[0],ANSWER_KINDS[0])
        with self.assertRaises(GovernanceRejected):s.add_intake("synthetic:clarification-response-intake:y",FLOWS[0],ANSWER_KINDS[1])
    def test_wrong_responder(self):
        s,_=anchored();s.add_intake("synthetic:clarification-response-intake:x",FLOWS[0],ANSWER_KINDS[0])
        with self.assertRaises(GovernanceRejected):s.add_intake("synthetic:clarification-response-intake:y",FLOWS[0],ANSWER_KINDS[1],"UPSTREAM_PG",d("x"))
    def test_immediate_parent(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected):s.add_intake("synthetic:clarification-response-intake:y",FLOWS[0],ANSWER_KINDS[1],RESPONDER[FLOWS[0]],d("x"))
    def test_counts(self):self.assertEqual((len(filled()[0]._intakes),len(filled()[0]._holds)),(20,16))
    def test_intake_rehash_tamper(self):
        s,_=filled();k=(FLOWS[0],ANSWER_KINDS[1]);s._intakes[k]=rehash(s._intakes[k],response_document_digest=d("bad"));self.assertFalse(s.evidence()["integrity_valid"])
    def test_parent_rehash_tamper(self):
        s,_=filled();k=(FLOWS[0],ANSWER_KINDS[1]);s._intakes[k]=rehash(s._intakes[k],parent_intake_digest=d("bad"));self.assertFalse(s.evidence()["integrity_valid"])
    def test_finalize_incomplete(self):
        with self.assertRaises(GovernanceRejected):anchored()[0].finalize("synthetic:clarification-response-intake-docket:d","synthetic:response-intake-compiler:c","synthetic:response-intake-validator:v")
    def test_role_collision(self):
        s,a=filled()
        with self.assertRaises(GovernanceRejected):s.finalize("synthetic:clarification-response-intake-docket:d","synthetic:response-intake-compiler:0","synthetic:response-intake-validator:v")
    def test_safe_docket(self):
        r=completed()[2];self.assertTrue(r.held);self.assertFalse(any((r.answered,r.concluded,r.recommended,r.accepted,r.approved,r.activated,r.deployed)))
    def test_docket_tamper(self):
        s,_,r=completed();s._docket=rehash(r,answered=True);self.assertFalse(s.evidence()["integrity_valid"])
    def test_missing_intake(self):
        s,_=filled();s._intakes.pop(next(iter(s._intakes)));self.assertFalse(s.evidence()["integrity_valid"])
    def test_missing_hold(self):
        s,_=filled();s._holds.pop();self.assertFalse(s.evidence()["integrity_valid"])
    def test_concurrency(self):
        s=SyntheticClarificationResponseIntake();a=(9501,WORKSTREAM_NAMES[0],CONTROL_ASPECTS[0],"synthetic:response-intake-requirement:00",d("x"),"PASS")
        with ThreadPoolExecutor(max_workers=8) as p:rows=list(p.map(lambda _:s.add_control(*a),range(20)))
        self.assertEqual(len({x.digest for x in rows}),1)
    def test_complete(self):
        e=completed()[0].evidence();self.assertTrue(e["complete_response_intake_evidence"]);self.assertEqual((e["intake_count"],e["response_count"],e["hold_count"]),(20,16,16))
    def test_non_execution(self):
        e=completed()[0].evidence();keys=("external_calls","document_transmissions","electronic_signatures","external_pg_calls","card_network_calls","payment_approvals","cancellations","refunds","settlements","transfers","ledger_writes","credential_reads","deployments","policy_prompt_weight_changes");self.assertEqual(tuple(e[k] for k in keys),(0,)*len(keys))
if __name__=="__main__":unittest.main()
