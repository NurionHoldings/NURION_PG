import hashlib
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.synthetic_rebuttal_correction_submission_validation import RESPONDER, derived_receipt_digest, submission_digest
from nurion_pg.synthetic_rereview_finding_observation import *

def d(value): return hashlib.sha256(value.encode()).hexdigest()

def populated():
    service=SyntheticReReviewFindingObservation()
    for control_id in range(11101,11501):
        workstream,aspect=service._expected(control_id)
        service.add_control(control_id,workstream,aspect,f"synthetic:finding-observation-requirement:{(control_id-11101)//25:02}",d(str(control_id)),"EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS")
    return service

def source_material():
    submissions=[];rereviews=[]
    for position,(flow,kind) in enumerate(CASE_KEYS):
        route=ROUTES[position%5];parent=None if not submissions else submissions[-1].digest;review=d(f"review:{flow}:{kind}")
        if route=="NOT_APPLICABLE_PRESERVED":submitter=document=receipt=None;marker="NO_SUBMISSION_REQUIRED"
        else:
            submitter=RESPONDER[flow];document=d(f"document:{flow}:{kind}");receipt=derived_receipt_digest(flow,kind,review,route,submitter,document);marker="SUBMISSION_RECEIVED_FOR_HUMAN_REVIEW"
        digest=submission_digest(flow,kind,review,route,submitter,document,receipt,marker,parent,position+1)
        submissions.append(SourceSubmission(f"synthetic:rebuttal-correction-submission:{flow}:{kind}",flow,kind,review,route,submitter,document,receipt,marker,parent,position+1,True,True,False,False,digest))
        source=submissions[-1];rparent=None if not rereviews else rereviews[-1].digest
        reviewer=None if route=="NOT_APPLICABLE_PRESERVED" else f"synthetic:independent-human-rereviewer:rereviewer-{position}"
        rmarker="NO_SUBMISSION_MARKER_PRESERVED" if reviewer is None else "HUMAN_REEXAMINATION_PENDING"
        rid=f"synthetic:independent-rereview:{flow}:{kind}";rdigest=rereview_digest(rid,flow,kind,source.digest,route,reviewer,rmarker,rparent,position+1)
        rereviews.append(SourceReReview(rid,flow,kind,source.digest,route,reviewer,rmarker,rparent,position+1,True,reviewer is not None,False,False,False,rdigest))
    return tuple(submissions),tuple(rereviews)

def anchored():
    service=populated();submissions,rereviews=source_material();rset=canonical_digest(tuple(x.digest for x in rereviews))
    sc="synthetic:submission-docket-compiler:source-compiler";sv="synthetic:submission-docket-validator:source-validator";rc="synthetic:rereview-docket-compiler:rereview-compiler";rv="synthetic:rereview-docket-validator:rereview-validator"
    actors=tuple(f"synthetic:{kind}:source-actor-{i}" for i,kind in enumerate(SOURCE_ACTOR_KINDS));docket=canonical_digest(("INDEPENDENT_REREVIEW_DOCKET_SOURCE",rset,rc,rv))
    anchor=service.anchor("synthetic:finding-observation-anchor:a",docket,rset,d("registry"),d("manifest"),APPLIED_LESSONS,APPLIED_RULES,submissions,rereviews,actors,sc,sv,rc,rv,24,True)
    return service,anchor

def observed():
    service,anchor=anchored()
    for position,(flow,kind) in enumerate(CASE_KEYS):
        args=(f"synthetic:finding-observation:{flow}:{kind}",flow,kind)
        if ROUTES[position%5]=="NOT_APPLICABLE_PRESERVED":service.add_finding(*args)
        else:service.add_finding(*args,f"synthetic:finding-drafter:drafter-{position}",f"synthetic:finding-reviewer:finding-reviewer-{position}")
    return service,anchor

def completed():
    service,anchor=observed();docket=service.finalize("synthetic:finding-observation-docket:d","synthetic:finding-docket-compiler:compiler","synthetic:finding-docket-validator:validator");return service,anchor,docket

def full_rehash_source(service, anchor, mutate):
    submissions=[]
    for position,row in enumerate(anchor.source_submissions):
        row=mutate(position,row);row=replace(row,parent_submission_digest=None if not submissions else submissions[-1].digest)
        row=replace(row,digest=source_submission_digest(row));submissions.append(row)
    rereviews=[]
    for position,row in enumerate(anchor.source_rereviews):
        row=replace(row,source_submission_digest=submissions[position].digest,parent_rereview_digest=None if not rereviews else rereviews[-1].digest)
        row=replace(row,digest=rereview_digest(row.rereview_id,row.flow,row.answer_kind,row.source_submission_digest,row.route,row.reviewer,row.marker,row.parent_rereview_digest,row.position));rereviews.append(row)
    submissions=tuple(submissions);rereviews=tuple(rereviews);rset=canonical_digest(tuple(x.digest for x in rereviews));docket=canonical_digest(("INDEPENDENT_REREVIEW_DOCKET_SOURCE",rset,anchor.source_rereview_compiler,anchor.source_rereview_validator));lineage=canonical_digest(("REREVIEW_FULL_ROLE_LINEAGE",docket,rset,tuple(x.digest for x in submissions),tuple(x.digest for x in rereviews),anchor.source_actor_roles,anchor.source_submission_compiler,anchor.source_submission_validator,anchor.source_rereview_compiler,anchor.source_rereview_validator))
    row=replace(anchor,source_docket_digest=docket,source_rereview_set_digest=rset,source_submissions=submissions,source_rereviews=rereviews,full_lineage_digest=lineage)
    payload={k:v for k,v in row.__dict__.items() if k!="digest"};payload["source_submissions"]=tuple(tuple(x.__dict__.values()) for x in submissions);payload["source_rereviews"]=tuple(tuple(x.__dict__.values()) for x in rereviews);service._anchor=replace(row,digest=canonical_digest(payload))

class Tests(unittest.TestCase):
    def test_matrix(self):self.assertEqual((WORKSTREAMS[0][0],WORKSTREAMS[-1][1],len(WORKSTREAMS)),(11101,11500,16))
    def test_controls(self):self.assertEqual(len(populated()._controls),400)
    def test_wrong_control(self):
        with self.assertRaises(GovernanceRejected):SyntheticReReviewFindingObservation().add_control(11101,"BAD",CONTROL_ASPECTS[0],"synthetic:finding-observation-requirement:00",d("x"),"PASS")
    def test_control_concurrency(self):
        s=SyntheticReReviewFindingObservation();args=(11101,WORKSTREAM_NAMES[0],CONTROL_ASPECTS[0],"synthetic:finding-observation-requirement:00",d("x"),"PASS")
        with ThreadPoolExecutor(max_workers=8) as pool:rows=list(pool.map(lambda _:s.add_control(*args),range(20)))
        self.assertEqual(len({x.digest for x in rows}),1)
    def test_latest_required(self):
        s,a=anchored();s._anchor=None
        with self.assertRaises(GovernanceRejected):s.anchor(a.anchor_id,a.source_docket_digest,a.source_rereview_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest,a.applied_lesson_ids,a.applied_rule_ids,a.source_submissions,a.source_rereviews,a.source_actor_roles,a.source_submission_compiler,a.source_submission_validator,a.source_rereview_compiler,a.source_rereview_validator,a.source_sequence,False)
    def test_source_actor_namespace_rejected(self):
        s,a=anchored();s._anchor=replace(a,source_actor_roles=("synthetic:wrong:x",)+a.source_actor_roles[1:]);self.assertFalse(s.evidence()["integrity_valid"])
    def test_duplicate_source_rereview_id_full_rehash_rejected(self):
        s,a=anchored();rows=list(a.source_rereviews);row=rows[1];rows[1]=replace(row,rereview_id=rows[0].rereview_id,digest=rereview_digest(rows[0].rereview_id,row.flow,row.answer_kind,row.source_submission_digest,row.route,row.reviewer,row.marker,row.parent_rereview_digest,row.position));s._anchor=replace(a,source_rereviews=tuple(rows));self.assertFalse(s.evidence()["integrity_valid"])
    def test_source_rereviewer_namespace_rejected(self):
        s,a=anchored();rows=list(a.source_rereviews);row=rows[1];rows[1]=replace(row,reviewer="synthetic:wrong-reviewer:rereviewer-1");s._anchor=replace(a,source_rereviews=tuple(rows));self.assertFalse(s.evidence()["integrity_valid"])
    def test_na_material_attachment_full_rehash_rejected(self):
        s,a=anchored();full_rehash_source(s,a,lambda i,row: replace(row,document_digest=d("forbidden"),receipt_digest=d("forbidden")) if i==0 else row);self.assertFalse(s.evidence()["integrity_valid"])
    def test_routed_unrelated_document_receipt_full_chain_rehash_rejected(self):
        s,a=anchored();full_rehash_source(s,a,lambda i,row: replace(row,document_digest=d("unrelated-document"),receipt_digest=d("unrelated-receipt")) if i==1 else row);self.assertFalse(s.evidence()["integrity_valid"])
    def test_source_submission_id_namespace_full_rehash_rejected(self):
        s,a=anchored();full_rehash_source(s,a,lambda i,row: replace(row,submission_id="synthetic:wrong-submission:x") if i==0 else row);self.assertFalse(s.evidence()["integrity_valid"])
    def test_duplicate_source_submission_id_full_rehash_rejected(self):
        s,a=anchored();duplicate=a.source_submissions[0].submission_id;full_rehash_source(s,a,lambda i,row: replace(row,submission_id=duplicate) if i==1 else row);self.assertFalse(s.evidence()["integrity_valid"])
    def test_na_forbids_actors(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected):s.add_finding("synthetic:finding-observation:x",*CASE_KEYS[0],"synthetic:finding-drafter:x","synthetic:finding-reviewer:y")
    def test_routed_requires_actors(self):
        s,_=anchored();s.add_finding("synthetic:finding-observation:first",*CASE_KEYS[0])
        with self.assertRaises(GovernanceRejected):s.add_finding("synthetic:finding-observation:second",*CASE_KEYS[1])
    def test_partial_batch_fail_closed(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected):s.finalize("synthetic:finding-observation-docket:d","synthetic:finding-docket-compiler:c","synthetic:finding-docket-validator:v")
    def test_immediate_parent_required(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected):s.add_finding("synthetic:finding-observation:second",*CASE_KEYS[1],"synthetic:finding-drafter:x","synthetic:finding-reviewer:y")
    def test_source_actor_reuse_rejected(self):
        s,a=anchored();s.add_finding("synthetic:finding-observation:first",*CASE_KEYS[0]);identity=a.source_actor_roles[0].rsplit(":",1)[-1]
        with self.assertRaises(GovernanceRejected):s.add_finding("synthetic:finding-observation:second",*CASE_KEYS[1],f"synthetic:finding-drafter:{identity}","synthetic:finding-reviewer:y")
    def test_prior_rereviewer_reuse_rejected(self):
        s,a=anchored();s.add_finding("synthetic:finding-observation:first",*CASE_KEYS[0]);identity=a.source_rereviews[1].reviewer.rsplit(":",1)[-1]
        with self.assertRaises(GovernanceRejected):s.add_finding("synthetic:finding-observation:second",*CASE_KEYS[1],f"synthetic:finding-drafter:{identity}","synthetic:finding-reviewer:y")
    def test_drafter_reviewer_same_rejected(self):
        s,_=anchored();s.add_finding("synthetic:finding-observation:first",*CASE_KEYS[0])
        with self.assertRaises(GovernanceRejected):s.add_finding("synthetic:finding-observation:second",*CASE_KEYS[1],"synthetic:finding-drafter:same","synthetic:finding-reviewer:same")
    def test_counts(self):
        e=observed()[0].evidence();self.assertEqual((e["finding_count"],e["no_finding_marker_count"],e["rebuttal_finding_pending_count"],e["correction_finding_pending_count"],e["hold_count"]),(20,4,8,8,16));self.assertEqual((e["source_actor_count"],e["source_rereviewer_count"]),(32,16))
    def test_parent_tamper(self):
        s,_=observed();key=CASE_KEYS[1];s._findings[key]=replace(s._findings[key],parent_finding_digest=d("bad"));self.assertFalse(s.evidence()["integrity_valid"])
    def test_observation_projection_tamper_rejected(self):
        s,_=observed();key=CASE_KEYS[1];row=s._findings[key];s._findings[key]=replace(row,observation_projection_digest=d("unrelated"));self.assertFalse(s.evidence()["integrity_valid"])
    def test_missing_hold(self):
        s,_=observed();s._holds.pop();self.assertFalse(s.evidence()["integrity_valid"])
    def test_event_tamper(self):
        s,_=observed();s._events[1]["artifact_digest"]=d("bad");self.assertFalse(s.evidence()["integrity_valid"])
    def test_final_actor_reuse_rejected(self):
        s,_=observed()
        with self.assertRaises(GovernanceRejected):s.finalize("synthetic:finding-observation-docket:d","synthetic:finding-docket-compiler:drafter-1","synthetic:finding-docket-validator:v")
    def test_safe_docket(self):
        row=completed()[2];self.assertTrue(row.pending_human_finding_review);self.assertFalse(any((row.concluded,row.recommended,row.accepted,row.resolved,row.approved,row.activated,row.deployed)))
    def test_complete(self):self.assertTrue(completed()[0].evidence()["complete_pending_finding_docket_evidence"])
    def test_content_addressed_evidence_digests(self):
        s,_,docket=completed();e=s.evidence()
        projection_set=canonical_digest(tuple(s._findings[k].observation_projection_digest for k in CASE_KEYS));finding_set=canonical_digest(tuple(s._findings[k].digest for k in CASE_KEYS))
        self.assertEqual((e["observation_projection_set_digest"],e["finding_set_digest"],e["final_docket_digest"]),(projection_set,finding_set,docket.digest));self.assertTrue(all(len(e[k])==64 and all(c in "0123456789abcdef" for c in e[k]) for k in ("observation_projection_set_digest","finding_set_digest","final_docket_digest")))
    def test_incomplete_evidence_hides_result_digests(self):
        e=anchored()[0].evidence();self.assertEqual(tuple(e[k] for k in ("observation_projection_set_digest","finding_set_digest","final_docket_digest")),(None,None,None))
    def test_non_execution(self):
        e=completed()[0].evidence();keys=("external_calls","document_transmissions","external_pg_calls","payment_approvals","ledger_writes","credential_reads","deployments");self.assertEqual(tuple(e[k] for k in keys),(0,)*len(keys))

if __name__=="__main__":unittest.main()
