import hashlib
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.synthetic_human_review_clarification_docket import *

def d(v): return hashlib.sha256(v.encode()).hexdigest()
def rehash(row,**changes):
    value=replace(row,**changes); p={k:v for k,v in value.__dict__.items() if k!="digest"}
    if "source_issues" in p:p["source_issues"]=tuple(tuple(x.__dict__.values()) for x in p["source_issues"])
    return replace(value,digest=canonical_digest(p))
def source_issues():
    rows=[]
    for flow in FLOWS:
        for i,kind in enumerate(ANSWER_KINDS):
            claim=(d(f"claim:{flow}:{kind}"),)*2; manifest=(d(f"manifest:{flow}:{kind}"),)*2; receipt=(d(f"receipt:{flow}:{kind}"),)*2; version=(1,1)
            if i==1:claim=(claim[0],d(f"counter-claim:{flow}:{kind}"))
            if i==2:manifest=(manifest[0],d(f"counter-manifest:{flow}:{kind}"))
            if i==3:receipt=(receipt[0],d(f"counter-receipt:{flow}:{kind}"))
            if i==4:version=(1,2)
            bundle=bundle_projection_digest(flow,kind,claim,manifest,receipt,version); parent=None if not rows else rows[-1].projection_digest; outcome=OUTCOMES[i]
            projection=issue_projection_digest(flow,kind,outcome,bundle,claim,manifest,receipt,version,parent)
            rows.append(SourceIssue(flow,kind,outcome,bundle,claim,manifest,receipt,version,parent,projection))
    return tuple(rows)
def populated():
    s=SyntheticHumanReviewClarificationDocket()
    for cid in range(9101,9501):
        ws,a=s._expected(cid); s.add_control(cid,ws,a,f"synthetic:clarification-docket-requirement:{(cid-9101)//25:02}",d(str(cid)),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    return s
def anchored():
    s=populated(); issues=source_issues(); issue_set=canonical_digest(tuple(x.projection_digest for x in issues)); reviewers=("synthetic:readiness-reviewer:r1","synthetic:preflight-reviewer:r2","synthetic:reconsideration-reviewer:r3"); compilers=tuple(f"synthetic:packet-compiler:c{i}" for i in range(4)); mc="synthetic:issue-matrix-compiler:mc"; mv="synthetic:issue-matrix-validator:mv"; matrix=canonical_digest(("HUMAN_REVIEW_ISSUE_MATRIX_SOURCE",issue_set,mc,mv))
    a=s.anchor_matrix("synthetic:clarification-docket-anchor:a",matrix,issue_set,d("registry"),d("manifest"),APPLIED_LESSONS,APPLIED_RULES,issues,reviewers,compilers,"synthetic:human-deliberation-chair:chair","synthetic:cross-party-validator:cross",mc,mv,19,True); return s,a
def requested():
    s,a=anchored()
    for f in FLOWS:
        for k in ANSWER_KINDS:s.add_request(f"synthetic:clarification-request:{f}:{k}",f,k)
    return s,a
def completed():
    s,a=requested(); return s,a,s.finalize("synthetic:human-clarification-docket:d","synthetic:clarification-drafter:cd","synthetic:clarification-reviewer:cr")

class TestSyntheticHumanReviewClarificationDocket(unittest.TestCase):
    def test_matrix(self): self.assertEqual((WORKSTREAMS[0][0],WORKSTREAMS[-1][1],len(WORKSTREAMS)),(9101,9500,16)); self.assertTrue(all(e-s+1==25 for s,e,_ in WORKSTREAMS))
    def test_exact_controls(self): self.assertEqual(set(populated()._controls),set(range(9101,9501)))
    def test_wrong_control(self):
        with self.assertRaises(GovernanceRejected):SyntheticHumanReviewClarificationDocket().add_control(9101,"WRONG",CONTROL_ASPECTS[0],"synthetic:clarification-docket-requirement:00",d("x"),"PASS")
    def test_control_idempotency_conflict(self):
        s=SyntheticHumanReviewClarificationDocket(); args=(9101,WORKSTREAM_NAMES[0],CONTROL_ASPECTS[0],"synthetic:clarification-docket-requirement:00",d("x"),"PASS"); r=s.add_control(*args); self.assertIs(r,s.add_control(*args))
        with self.assertRaises(GovernanceRejected):s.add_control(*args[:-2],d("y"),"PASS")
    def test_control_slot_swap(self):
        s=populated(); s._controls[9101],s._controls[9102]=s._controls[9102],s._controls[9101]; self.assertFalse(s.evidence()["integrity_valid"])
    def test_anchor_requires_controls(self):
        with self.assertRaises(GovernanceRejected):SyntheticHumanReviewClarificationDocket().anchor_matrix("x",d("m"),d("i"),d("r"),d("e"),(),(),(),(),(),"x","y","z","q",1,True)
    def test_lessons_exact(self):
        s,a=anchored(); s._anchor=None
        with self.assertRaises(GovernanceRejected):s.anchor_matrix(a.anchor_id,a.source_matrix_digest,a.issue_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest,a.applied_lesson_ids[:-1],a.applied_rule_ids,a.source_issues,a.source_reviewers,a.source_compilers,a.source_chair,a.source_validator,a.matrix_compiler,a.matrix_validator,a.source_sequence,True)
    def test_anchor_latest(self):
        s,a=anchored(); s._anchor=None
        with self.assertRaises(GovernanceRejected):s.anchor_matrix(a.anchor_id,a.source_matrix_digest,a.issue_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest,a.applied_lesson_ids,a.applied_rule_ids,a.source_issues,a.source_reviewers,a.source_compilers,a.source_chair,a.source_validator,a.matrix_compiler,a.matrix_validator,a.source_sequence,False)
    def test_anchor_idempotency(self):
        s,a=anchored(); self.assertIs(a,s.anchor_matrix(a.anchor_id,a.source_matrix_digest,a.issue_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest,a.applied_lesson_ids,a.applied_rule_ids,a.source_issues,a.source_reviewers,a.source_compilers,a.source_chair,a.source_validator,a.matrix_compiler,a.matrix_validator,a.source_sequence,True))
    def test_issue_set_full_rehash_tamper(self):
        s,a=anchored(); issues=list(a.source_issues); row=issues[0]; fake=d("fake-bundle"); issues[0]=replace(row,source_bundle_digest=fake,projection_digest=issue_projection_digest(row.flow,row.answer_kind,row.outcome,fake,row.claim_pair,row.manifest_pair,row.receipt_pair,row.version_pair,row.parent_issue_digest)); issues=tuple(issues); issue_set=canonical_digest(tuple(x.projection_digest for x in issues)); matrix=canonical_digest(("HUMAN_REVIEW_ISSUE_MATRIX_SOURCE",issue_set,a.matrix_compiler,a.matrix_validator)); lineage=canonical_digest(("HUMAN_REVIEW_ISSUE_MATRIX_FULL_LINEAGE",matrix,issue_set,tuple(x.projection_digest for x in issues),a.source_reviewers,a.source_compilers,a.source_chair,a.source_validator,a.matrix_compiler,a.matrix_validator)); s._anchor=rehash(a,source_issues=issues,issue_set_digest=issue_set,source_matrix_digest=matrix,source_lineage_digest=lineage); self.assertFalse(s.evidence()["integrity_valid"])
    def test_issue_semantic_rehash_tamper(self):
        s,a=anchored(); issues=list(a.source_issues); row=issues[0]; issues[0]=replace(row,outcome="CLAIM_CONFLICT",projection_digest=issue_projection_digest(row.flow,row.answer_kind,"CLAIM_CONFLICT",row.source_bundle_digest,row.claim_pair,row.manifest_pair,row.receipt_pair,row.version_pair,row.parent_issue_digest)); issues=tuple(issues); issue_set=canonical_digest(tuple(x.projection_digest for x in issues)); matrix=canonical_digest(("HUMAN_REVIEW_ISSUE_MATRIX_SOURCE",issue_set,a.matrix_compiler,a.matrix_validator)); lineage=canonical_digest(("HUMAN_REVIEW_ISSUE_MATRIX_FULL_LINEAGE",matrix,issue_set,tuple(x.projection_digest for x in issues),a.source_reviewers,a.source_compilers,a.source_chair,a.source_validator,a.matrix_compiler,a.matrix_validator)); s._anchor=rehash(a,source_issues=issues,issue_set_digest=issue_set,source_matrix_digest=matrix,source_lineage_digest=lineage); self.assertFalse(s.evidence()["integrity_valid"])
    def test_partial_issue_batch_rejected(self):
        s,a=anchored(); s._anchor=None; issues=a.source_issues[:-1]; issue_set=canonical_digest(tuple(x.projection_digest for x in issues)); matrix=canonical_digest(("HUMAN_REVIEW_ISSUE_MATRIX_SOURCE",issue_set,a.matrix_compiler,a.matrix_validator))
        with self.assertRaises(GovernanceRejected):s.anchor_matrix(a.anchor_id,matrix,issue_set,a.lesson_registry_digest,a.remediation_manifest_digest,a.applied_lesson_ids,a.applied_rule_ids,issues,a.source_reviewers,a.source_compilers,a.source_chair,a.source_validator,a.matrix_compiler,a.matrix_validator,a.source_sequence,True)
    def test_source_parent_tamper(self):
        s,a=anchored(); issues=list(a.source_issues); row=issues[1]; issues[1]=replace(row,parent_issue_digest=d("bad"),projection_digest=issue_projection_digest(row.flow,row.answer_kind,row.outcome,row.source_bundle_digest,row.claim_pair,row.manifest_pair,row.receipt_pair,row.version_pair,d("bad"))); issues=tuple(issues); issue_set=canonical_digest(tuple(x.projection_digest for x in issues)); matrix=canonical_digest(("HUMAN_REVIEW_ISSUE_MATRIX_SOURCE",issue_set,a.matrix_compiler,a.matrix_validator)); lineage=canonical_digest(("HUMAN_REVIEW_ISSUE_MATRIX_FULL_LINEAGE",matrix,issue_set,tuple(x.projection_digest for x in issues),a.source_reviewers,a.source_compilers,a.source_chair,a.source_validator,a.matrix_compiler,a.matrix_validator)); s._anchor=rehash(a,source_issues=issues,issue_set_digest=issue_set,source_matrix_digest=matrix,source_lineage_digest=lineage); self.assertFalse(s.evidence()["integrity_valid"])
    def test_role_collision(self):
        s,a=anchored(); s._anchor=None
        with self.assertRaises(GovernanceRejected):s.anchor_matrix(a.anchor_id,a.source_matrix_digest,a.issue_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest,a.applied_lesson_ids,a.applied_rule_ids,a.source_issues,a.source_reviewers,a.source_compilers,a.source_chair,a.source_validator,"synthetic:issue-matrix-compiler:chair",a.matrix_validator,a.source_sequence,True)
    def test_request_types_derived(self): self.assertEqual([x.request_type for x in requested()[0]._requests.values()],list(REQUEST_TYPES.values())*4)
    def test_consistent_does_not_require_response(self): self.assertEqual(sum(x.response_required for x in requested()[0]._requests.values()),16)
    def test_request_requires_anchor(self):
        with self.assertRaises(GovernanceRejected):SyntheticHumanReviewClarificationDocket().add_request("synthetic:clarification-request:x",FLOWS[0],ANSWER_KINDS[0])
    def test_immediate_parent_required(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected):s.add_request("synthetic:clarification-request:x",FLOWS[0],ANSWER_KINDS[1])
    def test_exact_twenty_requests_sixteen_holds(self): self.assertEqual((len(requested()[0]._requests),len(requested()[0]._holds)),(20,16))
    def test_request_idempotency_conflict(self):
        s,_=anchored(); r=s.add_request("synthetic:clarification-request:a",FLOWS[0],ANSWER_KINDS[0]); self.assertIs(r,s.add_request("synthetic:clarification-request:a",FLOWS[0],ANSWER_KINDS[0]))
        with self.assertRaises(GovernanceRejected):s.add_request("synthetic:clarification-request:b",FLOWS[0],ANSWER_KINDS[0])
    def test_request_type_rehash_tamper(self):
        s,_=requested(); key=next(iter(s._requests)); s._requests[key]=rehash(s._requests[key],request_type="CLARIFY_CLAIM_MEANING",response_required=True); self.assertFalse(s.evidence()["integrity_valid"])
    def test_parent_rehash_tamper(self):
        s,_=requested(); key=(FLOWS[0],ANSWER_KINDS[1]); s._requests[key]=rehash(s._requests[key],parent_request_digest=d("bad")); self.assertFalse(s.evidence()["integrity_valid"])
    def test_conclusion_tamper(self):
        s,_=requested(); key=next(iter(s._requests)); s._requests[key]=rehash(s._requests[key],concluded=True); self.assertFalse(s.evidence()["integrity_valid"])
    def test_finalize_requires_complete(self):
        with self.assertRaises(GovernanceRejected):anchored()[0].finalize("synthetic:human-clarification-docket:d","synthetic:clarification-drafter:x","synthetic:clarification-reviewer:y")
    def test_drafter_role_collision(self):
        s,_=requested()
        with self.assertRaises(GovernanceRejected):s.finalize("synthetic:human-clarification-docket:d","synthetic:clarification-drafter:chair","synthetic:clarification-reviewer:y")
    def test_drafter_reviewer_collision(self):
        s,_=requested()
        with self.assertRaises(GovernanceRejected):s.finalize("synthetic:human-clarification-docket:d","synthetic:clarification-drafter:same","synthetic:clarification-reviewer:same")
    def test_safe_docket(self):
        r=completed()[2]; self.assertTrue(r.held); self.assertFalse(any((r.concluded,r.recommended,r.accepted,r.approved,r.activated,r.deployed)))
    def test_docket_tamper(self):
        s,_,r=completed(); s._docket=rehash(r,concluded=True); self.assertFalse(s.evidence()["integrity_valid"])
    def test_missing_request_fails_closed(self):
        s,_=requested(); s._requests.pop(next(iter(s._requests))); self.assertFalse(s.evidence()["integrity_valid"])
    def test_missing_hold_fails_closed(self):
        s,_=requested(); s._holds.pop(); self.assertFalse(s.evidence()["integrity_valid"])
    def test_event_rehash_tamper(self):
        s,_=anchored(); row=s._events[0]|{"artifact_digest":d("bad")}; row["digest"]=canonical_digest({k:v for k,v in row.items() if k!="digest"}); s._events[0]=row; self.assertFalse(s.evidence()["integrity_valid"])
    def test_concurrent_control_idempotency(self):
        s=SyntheticHumanReviewClarificationDocket(); args=(9101,WORKSTREAM_NAMES[0],CONTROL_ASPECTS[0],"synthetic:clarification-docket-requirement:00",d("x"),"PASS")
        with ThreadPoolExecutor(max_workers=8) as pool:rows=list(pool.map(lambda _:s.add_control(*args),range(20)))
        self.assertEqual(len({x.digest for x in rows}),1)
    def test_complete_evidence(self):
        e=completed()[0].evidence(); self.assertTrue(e["complete_clarification_docket_evidence"]); self.assertEqual((e["request_count"],e["response_required_count"],e["hold_count"]),(20,16,16))
    def test_non_execution(self):
        e=completed()[0].evidence(); keys=("external_calls","document_transmissions","electronic_signatures","external_pg_calls","card_network_calls","payment_approvals","cancellations","refunds","settlements","transfers","ledger_writes","credential_reads","deployments","policy_prompt_weight_changes"); self.assertEqual(tuple(e[k] for k in keys),(0,)*len(keys)); self.assertFalse(any(e[k] for k in ("accepted","recommended","concluded","approved","activated")))

if __name__=="__main__":unittest.main()
