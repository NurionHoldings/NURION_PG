import hashlib
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.synthetic_finding_independent_review import *
from nurion_pg.synthetic_rebuttal_correction_submission_validation import RESPONDER, derived_receipt_digest, submission_digest

def d(v): return hashlib.sha256(v.encode()).hexdigest()

def populated():
    s=SyntheticFindingIndependentReview()
    for cid in range(11501,11901):
        w,a=s._expected(cid);s.add_control(cid,w,a,f"synthetic:finding-review-requirement:{(cid-11501)//25:02}",d(str(cid)),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    return s

def source_material():
    submissions=[];rereviews=[];findings=[]
    for i,(flow,kind) in enumerate(CASE_KEYS):
        route=ROUTES[i%5];sp=None if not submissions else submissions[-1].digest;review=d(f"review:{flow}:{kind}")
        if route=="NOT_APPLICABLE_PRESERVED":submitter=document=receipt=None;sm="NO_SUBMISSION_REQUIRED"
        else:submitter=RESPONDER[flow];document=d(f"document:{flow}:{kind}");receipt=derived_receipt_digest(flow,kind,review,route,submitter,document);sm="SUBMISSION_RECEIVED_FOR_HUMAN_REVIEW"
        sd=submission_digest(flow,kind,review,route,submitter,document,receipt,sm,sp,i+1);submissions.append(SourceSubmission(f"synthetic:rebuttal-correction-submission:{flow}:{kind}",flow,kind,review,route,submitter,document,receipt,sm,sp,i+1,True,True,False,False,sd))
        rp=None if not rereviews else rereviews[-1].digest;rr=None if route=="NOT_APPLICABLE_PRESERVED" else f"synthetic:independent-human-rereviewer:rereviewer-{i}";rm="NO_SUBMISSION_MARKER_PRESERVED" if rr is None else "HUMAN_REEXAMINATION_PENDING";rid=f"synthetic:independent-rereview:{flow}:{kind}";rd=rereview_digest(rid,flow,kind,sd,route,rr,rm,rp,i+1);rereviews.append(SourceReReview(rid,flow,kind,sd,route,rr,rm,rp,i+1,True,rr is not None,False,False,False,rd))
        fp=None if not findings else findings[-1].digest;drafter=None if rr is None else f"synthetic:finding-drafter:drafter-{i}";reviewer=None if rr is None else f"synthetic:finding-reviewer:finding-reviewer-{i}";fm="NO_FINDING_MARKER_PRESERVED" if rr is None else "HUMAN_FINDING_REVIEW_PENDING";projection=observation_projection_digest(rd,route,drafter,reviewer,fm);fid=f"synthetic:finding-observation:{flow}:{kind}";fd=finding_digest(fid,flow,kind,rd,route,drafter,reviewer,fm,fp,i+1,projection);findings.append(Finding(fid,flow,kind,rd,route,drafter,reviewer,fm,fp,i+1,projection,True,rr is not None,False,False,False,False,fd))
    return tuple(submissions),tuple(rereviews),tuple(findings)

def anchored():
    s=populated();subs,rrs,findings=source_material();fset=canonical_digest(tuple(x.digest for x in findings));sc="synthetic:submission-docket-compiler:source-compiler";sv="synthetic:submission-docket-validator:source-validator";rc="synthetic:rereview-docket-compiler:rereview-compiler";rv="synthetic:rereview-docket-validator:rereview-validator";fc="synthetic:finding-docket-compiler:finding-compiler";fv="synthetic:finding-docket-validator:finding-validator";roles=tuple(f"synthetic:{kind}:source-actor-{i}" for i,kind in enumerate(SOURCE_ACTOR_KINDS));docket=canonical_digest(("FINDING_OBSERVATION_DOCKET_SOURCE",fset,fc,fv));a=s.anchor("synthetic:finding-independent-review-anchor:a",docket,fset,d("registry"),d("manifest"),APPLIED_LESSONS,APPLIED_RULES,subs,rrs,findings,roles,sc,sv,rc,rv,fc,fv,25,True);return s,a

def reviewed():
    s,a=anchored()
    for i,(flow,kind) in enumerate(CASE_KEYS):
        args=(f"synthetic:independent-finding-review:{flow}:{kind}",flow,kind)
        if ROUTES[i%5]=="NOT_APPLICABLE_PRESERVED":s.add_review(*args)
        else:s.add_review(*args,f"synthetic:independent-finding-reviewer:reviewer-{i}",f"synthetic:finding-review-custodian:custodian-{i}")
    return s,a

def completed():
    s,a=reviewed();row=s.finalize("synthetic:finding-independent-review-docket:d","synthetic:finding-review-docket-compiler:compiler","synthetic:finding-review-docket-validator:validator");return s,a,row

class Tests(unittest.TestCase):
    def test_matrix(self):self.assertEqual((WORKSTREAMS[0][0],WORKSTREAMS[-1][1],len(WORKSTREAMS)),(11501,11900,16))
    def test_controls(self):self.assertEqual(len(populated()._controls),400)
    def test_wrong_control(self):
        with self.assertRaises(GovernanceRejected):SyntheticFindingIndependentReview().add_control(11501,"BAD",CONTROL_ASPECTS[0],"synthetic:finding-review-requirement:00",d("x"),"PASS")
    def test_control_concurrency(self):
        s=SyntheticFindingIndependentReview();args=(11501,WORKSTREAM_NAMES[0],CONTROL_ASPECTS[0],"synthetic:finding-review-requirement:00",d("x"),"PASS")
        with ThreadPoolExecutor(max_workers=8) as p: rows=list(p.map(lambda _:s.add_control(*args),range(20)))
        self.assertEqual(len({x.digest for x in rows}),1)
    def test_latest_required(self):
        s,a=anchored();s._anchor=None
        with self.assertRaises(GovernanceRejected):s.anchor(a.anchor_id,a.source_docket_digest,a.source_finding_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest,a.applied_lesson_ids,a.applied_rule_ids,a.source_submissions,a.source_rereviews,a.source_findings,a.source_actor_roles,a.source_submission_compiler,a.source_submission_validator,a.source_rereview_compiler,a.source_rereview_validator,a.source_finding_compiler,a.source_finding_validator,a.source_sequence,False)
    def test_source_docket_incomplete_role_lineage_rejected(self):
        s,a=anchored();legacy=canonical_digest(("REREVIEW_FULL_ROLE_LINEAGE",a.source_docket_digest,a.source_finding_set_digest));s._anchor=replace(a,full_source_lineage_digest=legacy);self.assertFalse(s.evidence()["integrity_valid"])
    def test_source_finding_actor_namespace_rejected(self):
        s,a=anchored();rows=list(a.source_findings);rows[1]=replace(rows[1],drafter="synthetic:wrong:drafter-1");s._anchor=replace(a,source_findings=tuple(rows));self.assertFalse(s.evidence()["integrity_valid"])
    def test_source_finding_order_rejected(self):
        s,a=anchored();rows=list(a.source_findings);rows[1],rows[2]=rows[2],rows[1];s._anchor=replace(a,source_findings=tuple(rows));self.assertFalse(s.evidence()["integrity_valid"])
    def test_na_forbids_actors(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected):s.add_review("synthetic:independent-finding-review:x",*CASE_KEYS[0],"synthetic:independent-finding-reviewer:x","synthetic:finding-review-custodian:y")
    def test_routed_requires_actors(self):
        s,_=anchored();s.add_review("synthetic:independent-finding-review:first",*CASE_KEYS[0])
        with self.assertRaises(GovernanceRejected):s.add_review("synthetic:independent-finding-review:second",*CASE_KEYS[1])
    def test_partial_batch_fail_closed(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected):s.finalize("synthetic:finding-independent-review-docket:d","synthetic:finding-review-docket-compiler:c","synthetic:finding-review-docket-validator:v")
    def test_immediate_parent_required(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected):s.add_review("synthetic:independent-finding-review:second",*CASE_KEYS[1],"synthetic:independent-finding-reviewer:x","synthetic:finding-review-custodian:y")
    def test_prior_actor_reuse_rejected(self):
        s,a=anchored();s.add_review("synthetic:independent-finding-review:first",*CASE_KEYS[0]);identity=a.source_findings[1].reviewer.rsplit(":",1)[-1]
        with self.assertRaises(GovernanceRejected):s.add_review("synthetic:independent-finding-review:second",*CASE_KEYS[1],f"synthetic:independent-finding-reviewer:{identity}","synthetic:finding-review-custodian:y")
    def test_self_approval_rejected(self):
        s,_=anchored();s.add_review("synthetic:independent-finding-review:first",*CASE_KEYS[0])
        with self.assertRaises(GovernanceRejected):s.add_review("synthetic:independent-finding-review:second",*CASE_KEYS[1],"synthetic:independent-finding-reviewer:same","synthetic:finding-review-custodian:same")
    def test_counts(self):
        e=reviewed()[0].evidence();self.assertEqual((e["review_count"],e["no_finding_marker_count"],e["rebuttal_finding_pending_count"],e["correction_finding_pending_count"],e["hold_count"]),(20,4,8,8,16));self.assertEqual(e["judgment_preparation_packet_count"],16)
    def test_judgment_method_complete(self):
        row=reviewed()[0]._reviews[CASE_KEYS[1]];packet=dict(row.judgment_packet);self.assertEqual(set(packet),{"conclusion_method","recommendation_method","acceptance_method","resolution_method","correction_direction","overcoming_options","validation_criteria","residual_risk","escalation_condition"});self.assertFalse(completed()[0].evidence()["judgment_authority"])
    def test_single_alternative_tamper_rejected(self):
        s,_=reviewed();key=CASE_KEYS[1];row=s._reviews[key];p=list(row.judgment_packet);method=dict(p[1][1]);method["alternatives"]=method["alternatives"][:1];p[1]=(p[1][0],tuple(method.items()));s._reviews[key]=replace(row,judgment_packet=tuple(p),judgment_packet_digest=canonical_digest(tuple(p)));self.assertFalse(s.evidence()["integrity_valid"])
    def test_missing_human_gate_rejected(self):
        s,_=reviewed();key=CASE_KEYS[1];row=s._reviews[key];p=list(row.judgment_packet);method=dict(p[2][1]);method["explicit_human_approval_gate"]=False;p[2]=(p[2][0],tuple(method.items()));s._reviews[key]=replace(row,judgment_packet=tuple(p),judgment_packet_digest=canonical_digest(tuple(p)));self.assertFalse(s.evidence()["integrity_valid"])
    def test_unvalidated_resolution_rejected(self):
        s,_=reviewed();key=CASE_KEYS[1];row=s._reviews[key];p=list(row.judgment_packet);method=dict(p[3][1]);method["negative_test"]="OMITTED";p[3]=(p[3][0],tuple(method.items()));s._reviews[key]=replace(row,judgment_packet=tuple(p),judgment_packet_digest=canonical_digest(tuple(p)));self.assertFalse(s.evidence()["integrity_valid"])
    def test_hidden_residual_risk_rejected(self):
        s,_=reviewed();key=CASE_KEYS[1];row=s._reviews[key];p=list(row.judgment_packet);p[7]=(p[7][0],("NONE",row.source_finding_digest));s._reviews[key]=replace(row,judgment_packet=tuple(p),judgment_packet_digest=canonical_digest(tuple(p)));self.assertFalse(s.evidence()["integrity_valid"])
    def test_parent_tamper(self):
        s,_=reviewed();key=CASE_KEYS[1];s._reviews[key]=replace(s._reviews[key],parent_review_digest=d("bad"));self.assertFalse(s.evidence()["integrity_valid"])
    def test_packet_projection_tamper(self):
        s,_=reviewed();key=CASE_KEYS[1];s._reviews[key]=replace(s._reviews[key],review_projection_digest=d("bad"));self.assertFalse(s.evidence()["integrity_valid"])
    def test_missing_hold(self):s,_=reviewed();s._holds.pop();self.assertFalse(s.evidence()["integrity_valid"])
    def test_event_tamper(self):s,_=reviewed();s._events[1]["artifact_digest"]=d("bad");self.assertFalse(s.evidence()["integrity_valid"])
    def test_final_actor_reuse_rejected(self):
        s,_=reviewed()
        with self.assertRaises(GovernanceRejected):s.finalize("synthetic:finding-independent-review-docket:d","synthetic:finding-review-docket-compiler:reviewer-1","synthetic:finding-review-docket-validator:v")
    def test_safe_docket(self):row=completed()[2];self.assertFalse(any((row.concluded,row.recommended,row.accepted,row.resolved,row.approved,row.activated,row.deployed)))
    def test_content_addressed_evidence(self):
        s,_,row=completed();e=s.evidence();self.assertEqual(e["final_docket_digest"],row.digest);self.assertTrue(all(isinstance(e[k],str) and len(e[k])==64 for k in ("review_projection_set_digest","review_set_digest","final_docket_digest","complete_role_lineage_digest")))
    def test_incomplete_hides_results(self):e=anchored()[0].evidence();self.assertEqual(tuple(e[k] for k in ("review_projection_set_digest","review_set_digest","final_docket_digest","complete_role_lineage_digest")),(None,)*4)
    def test_non_execution(self):
        e=completed()[0].evidence();keys=("external_calls","document_transmissions","external_pg_calls","card_network_calls","payment_approvals","cancellations","refunds","settlements","transfers","ledger_writes","credential_reads","deployments");self.assertEqual(tuple(e[k] for k in keys),(0,)*len(keys))

if __name__=="__main__":unittest.main()
