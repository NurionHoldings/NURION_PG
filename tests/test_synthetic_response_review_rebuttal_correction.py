import hashlib,unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from nurion_pg.arkaon.governance import GovernanceRejected,canonical_digest
from nurion_pg.synthetic_response_review_rebuttal_correction import *
def d(v):return hashlib.sha256(v.encode()).hexdigest()
def rehash(r,**c):
 v=replace(r,**c);p={k:x for k,x in v.__dict__.items() if k!="digest"}
 if "source_intakes" in p:p["source_intakes"]=tuple(tuple(x.__dict__.values()) for x in p["source_intakes"])
 return replace(v,digest=canonical_digest(p))
def sources():
 rows=[]
 for f in FLOWS:
  for i,k in enumerate(ANSWER_KINDS):
   o=OUTCOMES[i];present=i>0;req=d(f"request:{f}:{k}");res=RESPONDER[f] if present else None;doc=d(f"response:{f}:{k}") if present else None;parent=None if not rows else rows[-1].intake_digest;dig=intake_digest(f,k,o,req,res,doc,parent,present);rows.append(SourceIntake(f,k,o,req,res,doc,parent,present,dig))
 return tuple(rows)
def populated():
 s=SyntheticResponseReviewRebuttalCorrection()
 for cid in range(9901,10301):
  w,a=s._expected(cid);s.add_control(cid,w,a,f"synthetic:response-review-requirement:{(cid-9901)//25:02}",d(str(cid)),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
 return s
def anchored():
 s=populated();rows=sources();iset=canonical_digest(tuple(x.intake_digest for x in rows));roles=tuple(f"synthetic:{kind}:{i}" for i,kind in enumerate(SOURCE_ROLE_KINDS));docket=canonical_digest(("CLARIFICATION_RESPONSE_INTAKE_DOCKET_SOURCE",iset,roles));a=s.anchor("synthetic:response-review-anchor:a",docket,iset,d("registry"),d("manifest"),APPLIED_LESSONS,APPLIED_RULES,rows,roles,21,True);return s,a
def reviewed():
 s,a=anchored()
 for f in FLOWS:
  for i,k in enumerate(ANSWER_KINDS):
   args=(f"synthetic:response-review:{f}:{k}",f,k)
   if i==0:s.add_review(*args)
   elif i<3:s.add_review(*args,f"synthetic:response-independent-reviewer:r-{f}-{k}",f"synthetic:rebuttal-custodian:c-{f}-{k}")
   else:s.add_review(*args,f"synthetic:response-independent-reviewer:r-{f}-{k}",f"synthetic:correction-request-compiler:c-{f}-{k}")
 return s,a
def completed():
 s,a=reviewed();return s,a,s.finalize("synthetic:response-review-docket:d","synthetic:review-docket-compiler:dc","synthetic:review-docket-validator:dv")
class Tests(unittest.TestCase):
 def test_matrix(self):self.assertEqual((WORKSTREAMS[0][0],WORKSTREAMS[-1][1],len(WORKSTREAMS)),(9901,10300,16))
 def test_controls(self):self.assertEqual(set(populated()._controls),set(range(9901,10301)))
 def test_wrong_control(self):
  with self.assertRaises(GovernanceRejected):SyntheticResponseReviewRebuttalCorrection().add_control(9901,"BAD",CONTROL_ASPECTS[0],"synthetic:response-review-requirement:00",d("x"),"PASS")
 def test_control_concurrency(self):
  s=SyntheticResponseReviewRebuttalCorrection();a=(9901,WORKSTREAM_NAMES[0],CONTROL_ASPECTS[0],"synthetic:response-review-requirement:00",d("x"),"PASS")
  with ThreadPoolExecutor(max_workers=8) as p:rows=list(p.map(lambda _:s.add_control(*a),range(20)))
  self.assertEqual(len({x.digest for x in rows}),1)
 def test_anchor_requires_controls(self):
  with self.assertRaises(GovernanceRejected):SyntheticResponseReviewRebuttalCorrection().anchor("x",d("d"),d("s"),d("r"),d("m"),(),(),(),(),1,True)
 def test_lessons_exact(self):
  s,a=anchored();s._anchor=None
  with self.assertRaises(GovernanceRejected):s.anchor(a.anchor_id,a.source_docket_digest,a.intake_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest,a.applied_lesson_ids[:-1],a.applied_rule_ids,a.source_intakes,a.source_roles,a.source_sequence,True)
 def test_latest(self):
  s,a=anchored();s._anchor=None
  with self.assertRaises(GovernanceRejected):s.anchor(a.anchor_id,a.source_docket_digest,a.intake_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest,a.applied_lesson_ids,a.applied_rule_ids,a.source_intakes,a.source_roles,a.source_sequence,False)
 def test_source_outcome_full_rehash(self):
  s,a=anchored();rows=list(a.source_intakes);r=rows[0];rows[0]=replace(r,outcome="CLAIM_CONFLICT",response_present=True,responder_party=RESPONDER[r.flow],response_document_digest=d("x"),intake_digest=intake_digest(r.flow,r.answer_kind,"CLAIM_CONFLICT",r.request_digest,RESPONDER[r.flow],d("x"),None,True));rows=tuple(rows);iset=canonical_digest(tuple(x.intake_digest for x in rows));docket=canonical_digest(("CLARIFICATION_RESPONSE_INTAKE_DOCKET_SOURCE",iset,a.source_roles));lineage=canonical_digest(("RESPONSE_INTAKE_FULL_LINEAGE",docket,iset,tuple(x.intake_digest for x in rows),a.source_roles));s._anchor=rehash(a,source_intakes=rows,intake_set_digest=iset,source_docket_digest=docket,source_lineage_digest=lineage);self.assertFalse(s.evidence()["integrity_valid"])
 def test_role_namespace_tamper(self):
  s,a=anchored();roles=list(a.source_roles);roles[0]="synthetic:wrong:0";roles=tuple(roles);docket=canonical_digest(("CLARIFICATION_RESPONSE_INTAKE_DOCKET_SOURCE",a.intake_set_digest,roles));lineage=canonical_digest(("RESPONSE_INTAKE_FULL_LINEAGE",docket,a.intake_set_digest,tuple(x.intake_digest for x in a.source_intakes),roles));s._anchor=rehash(a,source_roles=roles,source_docket_digest=docket,source_lineage_digest=lineage);self.assertFalse(s.evidence()["integrity_valid"])
 def test_review_requires_anchor(self):
  with self.assertRaises(GovernanceRejected):SyntheticResponseReviewRebuttalCorrection().add_review("synthetic:response-review:x",FLOWS[0],ANSWER_KINDS[0])
 def test_na_forbids_actors(self):
  s,_=anchored()
  with self.assertRaises(GovernanceRejected):s.add_review("synthetic:response-review:x",FLOWS[0],ANSWER_KINDS[0],"synthetic:response-independent-reviewer:r","synthetic:rebuttal-custodian:c")
 def test_route_actor_type(self):
  s,_=anchored();s.add_review("synthetic:response-review:x",FLOWS[0],ANSWER_KINDS[0])
  with self.assertRaises(GovernanceRejected):s.add_review("synthetic:response-review:y",FLOWS[0],ANSWER_KINDS[1],"synthetic:response-independent-reviewer:r","synthetic:correction-request-compiler:c")
 def test_immediate_parent(self):
  s,_=anchored()
  with self.assertRaises(GovernanceRejected):s.add_review("synthetic:response-review:y",FLOWS[0],ANSWER_KINDS[1],"synthetic:response-independent-reviewer:r","synthetic:rebuttal-custodian:c")
 def test_counts(self):
  s,_=reviewed();self.assertEqual((len(s._reviews),len(s._holds)),(20,16));self.assertEqual((sum(x.route=="REBUTTAL_OPPORTUNITY_REQUIRED" for x in s._reviews.values()),sum(x.route=="CORRECTION_REQUEST_REQUIRED" for x in s._reviews.values())),(8,8))
 def test_route_rehash_tamper(self):
  s,_=reviewed();k=(FLOWS[0],ANSWER_KINDS[1]);s._reviews[k]=rehash(s._reviews[k],route="CORRECTION_REQUEST_REQUIRED");self.assertFalse(s.evidence()["integrity_valid"])
 def test_parent_rehash_tamper(self):
  s,_=reviewed();k=(FLOWS[0],ANSWER_KINDS[1]);s._reviews[k]=rehash(s._reviews[k],parent_review_digest=d("bad"));self.assertFalse(s.evidence()["integrity_valid"])
 def test_finalize_incomplete(self):
  with self.assertRaises(GovernanceRejected):anchored()[0].finalize("synthetic:response-review-docket:d","synthetic:review-docket-compiler:c","synthetic:review-docket-validator:v")
 def test_safe_docket(self):
  r=completed()[2];self.assertTrue(r.held);self.assertFalse(any((r.resolved,r.recommended,r.accepted,r.approved,r.activated,r.deployed)))
 def test_docket_tamper(self):
  s,_,r=completed();s._docket=rehash(r,resolved=True);self.assertFalse(s.evidence()["integrity_valid"])
 def test_missing_hold(self):
  s,_=reviewed();s._holds.pop();self.assertFalse(s.evidence()["integrity_valid"])
 def test_complete(self):
  e=completed()[0].evidence();self.assertTrue(e["complete_review_docket_evidence"]);self.assertEqual((e["review_count"],e["rebuttal_route_count"],e["correction_route_count"],e["hold_count"]),(20,8,8,16))
 def test_non_execution(self):
  e=completed()[0].evidence();keys=("external_calls","document_transmissions","electronic_signatures","external_pg_calls","card_network_calls","payment_approvals","cancellations","refunds","settlements","transfers","ledger_writes","credential_reads","deployments","policy_prompt_weight_changes");self.assertEqual(tuple(e[k] for k in keys),(0,)*len(keys))
if __name__=="__main__":unittest.main()
