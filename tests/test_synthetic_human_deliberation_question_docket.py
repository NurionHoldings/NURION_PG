import hashlib
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from nurion_pg.arkaon.governance import GovernanceRejected,canonical_digest
from nurion_pg.synthetic_human_deliberation_question_docket import *

def d(v):return hashlib.sha256(v.encode()).hexdigest()
def rehash(r,**c):
    x=replace(r,**c);p={k:v for k,v in x.__dict__.items() if k!="digest"};return replace(x,digest=canonical_digest(p))
def populated():
    s=SyntheticHumanDeliberationQuestionDocket()
    for cid in range(7101,7501):
        ws,a=s._expected(cid);s.add_control(cid,ws,a,f"synthetic:question-requirement:{(cid-7101)//25:02}",d(str(cid)),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    return s
def anchored():
    s=populated();docs=tuple((p,d(p)) for p in PARTIES);receipt=d("simulation-packet");routes=tuple((f,canonical_digest(("HUMAN_QUESTION_ROUTE",f,FLOW_PARTIES[f],docs,receipt))) for f in FLOWS)
    reviewers=("synthetic:readiness-reviewer:r1","synthetic:preflight-reviewer:r2","synthetic:reconsideration-reviewer:r3");compilers=("synthetic:packet-compiler:c1","synthetic:packet-compiler:c2","synthetic:packet-compiler:c3")
    a=s.anchor_source("synthetic:question-anchor:a",receipt,d("case-set"),d("registry"),d("manifest"),APPLIED_LESSONS,APPLIED_RULES,docs,routes,14,True,reviewers,compilers);return s,a
def questioned():
    s,a=anchored();docs=dict(a.party_document_digests);routes=dict(a.route_binding_digests)
    for f in FLOWS:
        source,counter=FLOW_PARTIES[f]
        for kind in QUESTION_KINDS:
            assumption=canonical_digest(("QUESTION_ASSUMPTION",source,docs[source],f,kind,routes[f],a.simulation_case_set_digest));risk=canonical_digest(("QUESTION_RESIDUAL_RISK",source,counter,f,kind,assumption,routes[f]));request=canonical_digest(("ADDITIONAL_EVIDENCE_REQUEST",counter,f,kind,assumption,risk,routes[f]));question=canonical_digest(("HUMAN_DELIBERATION_QUESTION",f,kind,assumption,risk,request,a.simulation_packet_digest))
            s.add_question(f"synthetic:deliberation-question:{f}:{kind}",f,kind,question,assumption,risk,request,f"synthetic:question-drafter:{source}",f"synthetic:human-reviewer:{counter}")
    return s,a
def completed():
    s,a=questioned();return s,a,s.finalize("synthetic:human-question-docket:a","synthetic:human-deliberation-chair:chair")

class TestHumanDeliberationQuestionDocket(unittest.TestCase):
    def test_matrix(self):self.assertEqual((WORKSTREAMS[0][0],WORKSTREAMS[-1][1],len(WORKSTREAMS)),(7101,7500,16));self.assertTrue(all(b-a+1==25 for a,b,_ in WORKSTREAMS))
    def test_exact_controls(self):self.assertEqual(set(populated()._controls),set(range(7101,7501)))
    def test_control_mapping_rejected(self):
        with self.assertRaises(GovernanceRejected):SyntheticHumanDeliberationQuestionDocket().add_control(7101,"WRONG",CONTROL_ASPECTS[0],"synthetic:question-requirement:00",d("x"),"PASS")
    def test_control_idempotency_conflict(self):
        s=SyntheticHumanDeliberationQuestionDocket();a=(7101,WORKSTREAM_NAMES[0],CONTROL_ASPECTS[0],"synthetic:question-requirement:00",d("x"),"PASS");x=s.add_control(*a);self.assertIs(x,s.add_control(*a))
        with self.assertRaises(GovernanceRejected):s.add_control(*a[:-2],d("y"),"PASS")
    def test_control_slot_swap(self):
        s=populated();s._controls[7101],s._controls[7102]=s._controls[7102],s._controls[7101];self.assertFalse(s.evidence()["integrity_valid"])
    def test_anchor_requires_controls(self):
        with self.assertRaises(GovernanceRejected):SyntheticHumanDeliberationQuestionDocket().anchor_source("synthetic:question-anchor:a",d("p"),d("c"),d("r"),d("m"),APPLIED_LESSONS,APPLIED_RULES,(),(),1,True,(),())
    def test_anchor_latest(self):
        s=populated();docs=tuple((p,d(p)) for p in PARTIES);receipt=d("p");routes=tuple((f,canonical_digest(("HUMAN_QUESTION_ROUTE",f,FLOW_PARTIES[f],docs,receipt))) for f in FLOWS)
        with self.assertRaises(GovernanceRejected):s.anchor_source("synthetic:question-anchor:a",receipt,d("c"),d("r"),d("m"),APPLIED_LESSONS,APPLIED_RULES,docs,routes,1,False,("synthetic:readiness-reviewer:a","synthetic:preflight-reviewer:b","synthetic:reconsideration-reviewer:c"),("synthetic:packet-compiler:d","synthetic:packet-compiler:e","synthetic:packet-compiler:f"))
    def test_lessons_exact(self):
        s=populated();docs=tuple((p,d(p)) for p in PARTIES);receipt=d("p");routes=tuple((f,canonical_digest(("HUMAN_QUESTION_ROUTE",f,FLOW_PARTIES[f],docs,receipt))) for f in FLOWS)
        with self.assertRaises(GovernanceRejected):s.anchor_source("synthetic:question-anchor:a",receipt,d("c"),d("r"),d("m"),APPLIED_LESSONS[:-1],APPLIED_RULES,docs,routes,1,True,("synthetic:readiness-reviewer:a","synthetic:preflight-reviewer:b","synthetic:reconsideration-reviewer:c"),("synthetic:packet-compiler:d","synthetic:packet-compiler:e","synthetic:packet-compiler:f"))
    def test_role_collision(self):
        s=populated();docs=tuple((p,d(p)) for p in PARTIES);receipt=d("p");routes=tuple((f,canonical_digest(("HUMAN_QUESTION_ROUTE",f,FLOW_PARTIES[f],docs,receipt))) for f in FLOWS)
        with self.assertRaises(GovernanceRejected):s.anchor_source("synthetic:question-anchor:a",receipt,d("c"),d("r"),d("m"),APPLIED_LESSONS,APPLIED_RULES,docs,routes,1,True,("synthetic:readiness-reviewer:same","synthetic:preflight-reviewer:same","synthetic:reconsideration-reviewer:c"),("synthetic:packet-compiler:d","synthetic:packet-compiler:e","synthetic:packet-compiler:f"))
    def test_route_binding(self):
        s=populated();docs=tuple((p,d(p)) for p in PARTIES)
        with self.assertRaises(GovernanceRejected):s.anchor_source("synthetic:question-anchor:a",d("p"),d("c"),d("r"),d("m"),APPLIED_LESSONS,APPLIED_RULES,docs,tuple((f,d(f)) for f in FLOWS),1,True,("synthetic:readiness-reviewer:a","synthetic:preflight-reviewer:b","synthetic:reconsideration-reviewer:c"),("synthetic:packet-compiler:d","synthetic:packet-compiler:e","synthetic:packet-compiler:f"))
    def test_anchor_idempotent(self):
        s,a=anchored();self.assertIs(a,s.anchor_source(a.anchor_id,a.simulation_packet_digest,a.simulation_case_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest,a.applied_lesson_ids,a.applied_rule_ids,a.party_document_digests,a.route_binding_digests,a.source_sequence,a.is_latest,a.source_reviewers,a.source_compilers))
    def test_question_requires_anchor(self):
        with self.assertRaises(GovernanceRejected):SyntheticHumanDeliberationQuestionDocket().add_question("synthetic:deliberation-question:x",FLOWS[0],QUESTION_KINDS[0],d("q"),d("a"),d("r"),d("e"),"synthetic:question-drafter:x","synthetic:human-reviewer:y")
    def test_question_namespace(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected):s.add_question("real:x",FLOWS[0],QUESTION_KINDS[0],d("q"),d("a"),d("r"),d("e"),"synthetic:question-drafter:x","synthetic:human-reviewer:y")
    def test_exact_twenty_questions_holds(self):
        s,_=questioned();self.assertEqual((len(s._questions),len(s._holds)),(20,20))
    def test_question_idempotent_conflict(self):
        s,a=anchored();f=FLOWS[0];kind=QUESTION_KINDS[0];source,counter=FLOW_PARTIES[f];route=dict(a.route_binding_digests)[f];doc=dict(a.party_document_digests)[source];assumption=canonical_digest(("QUESTION_ASSUMPTION",source,doc,f,kind,route,a.simulation_case_set_digest));risk=canonical_digest(("QUESTION_RESIDUAL_RISK",source,counter,f,kind,assumption,route));req=canonical_digest(("ADDITIONAL_EVIDENCE_REQUEST",counter,f,kind,assumption,risk,route));q=canonical_digest(("HUMAN_DELIBERATION_QUESTION",f,kind,assumption,risk,req,a.simulation_packet_digest));args=("synthetic:deliberation-question:x",f,kind,q,assumption,risk,req,f"synthetic:question-drafter:{source}",f"synthetic:human-reviewer:{counter}");x=s.add_question(*args);self.assertIs(x,s.add_question(*args))
        with self.assertRaises(GovernanceRejected):s.add_question(*args[:-3],d("bad"),*args[-2:])
    def _tamper(self,field,value):
        s,_=questioned();k=next(iter(s._questions));s._questions[k]=rehash(s._questions[k],**{field:value});self.assertFalse(s.evidence()["integrity_valid"])
    def test_question_digest_tamper(self):self._tamper("question_digest",d("bad"))
    def test_assumption_tamper(self):self._tamper("assumption_digest",d("bad"))
    def test_risk_tamper(self):self._tamper("residual_risk_digest",d("bad"))
    def test_request_tamper(self):self._tamper("evidence_request_digest",d("bad"))
    def test_document_tamper(self):self._tamper("source_document_digest",d("bad"))
    def test_reviewer_tamper(self):self._tamper("human_reviewer","synthetic:human-reviewer:wrong")
    def test_status_tamper(self):self._tamper("status","ANSWERED")
    def test_question_key_swap(self):
        s,_=questioned();ks=list(s._questions)[:2];s._questions[ks[0]],s._questions[ks[1]]=s._questions[ks[1]],s._questions[ks[0]];self.assertFalse(s.evidence()["integrity_valid"])
    def test_anchor_document_swap(self):
        s,a=anchored();docs=((PARTIES[0],a.party_document_digests[1][1]),(PARTIES[1],a.party_document_digests[0][1]),a.party_document_digests[2]);s._anchor=rehash(a,party_document_digests=docs);self.assertFalse(s.evidence()["integrity_valid"])
    def test_source_lineage_tamper(self):
        s,a=anchored();s._anchor=rehash(a,source_compilers=(a.source_compilers[0],a.source_compilers[1],"synthetic:packet-compiler:substitute"));self.assertFalse(s.evidence()["integrity_valid"])
    def test_finalize_requires_complete(self):
        with self.assertRaises(GovernanceRejected):anchored()[0].finalize("synthetic:human-question-docket:a","synthetic:human-deliberation-chair:chair")
    def test_chair_separation(self):
        s,_=questioned()
        with self.assertRaises(GovernanceRejected):s.finalize("synthetic:human-question-docket:a","synthetic:human-deliberation-chair:c1")
    def test_chair_separated_from_question_human_reviewer(self):
        s,_=questioned()
        with self.assertRaises(GovernanceRejected):s.finalize("synthetic:human-question-docket:a","synthetic:human-deliberation-chair:TENANT_AGENCY")
    def test_safe_docket(self):
        r=completed()[2];self.assertTrue(r.complete);self.assertFalse(any((r.published,r.recommended,r.consent_recorded,r.decision_recorded,r.approval_recorded,r.activation_recorded,r.deployment_recorded)))
    def test_docket_decision_tamper(self):
        s,_,r=completed();s._docket=rehash(r,decision_recorded=True);self.assertFalse(s.evidence()["integrity_valid"])
    def test_docket_lineage_tamper(self):
        s,_,r=completed();s._docket=rehash(r,source_lineage_digest=d("bad"));self.assertFalse(s.evidence()["integrity_valid"])
    def test_docket_reviewer_tamper(self):
        s,_,r=completed();s._docket=rehash(r,source_reviewers=(r.source_reviewers[0],r.source_reviewers[1],"synthetic:reconsideration-reviewer:x"));self.assertFalse(s.evidence()["integrity_valid"])
    def test_event_tamper(self):
        s,_=anchored();x=s._events[0]|{"artifact_digest":d("bad")};x["digest"]=canonical_digest({k:v for k,v in x.items() if k!="digest"});s._events[0]=x;self.assertFalse(s.evidence()["integrity_valid"])
    def test_missing_hold(self):
        s,_=questioned();s._holds.pop();self.assertFalse(s.evidence()["integrity_valid"])
    def test_missing_question(self):
        s,_=questioned();s._questions.pop(next(iter(s._questions)));self.assertFalse(s.evidence()["integrity_valid"])
    def test_concurrent_control(self):
        s=SyntheticHumanDeliberationQuestionDocket();a=(7101,WORKSTREAM_NAMES[0],CONTROL_ASPECTS[0],"synthetic:question-requirement:00",d("x"),"PASS")
        with ThreadPoolExecutor(max_workers=8) as p:rows=list(p.map(lambda _:s.add_control(*a),range(20)))
        self.assertEqual(len({x.digest for x in rows}),1)
    def test_complete_evidence(self):
        e=completed()[0].evidence();self.assertTrue(e["complete_human_deliberation_evidence"]);self.assertEqual((e["question_count"],e["hold_count"]),(20,20))
    def test_non_execution(self):
        e=completed()[0].evidence();keys=("external_calls","document_transmissions","electronic_signatures","external_pg_calls","card_network_calls","payment_approvals","cancellations","refunds","settlements","transfers","ledger_writes","credential_reads","deployments","policy_prompt_weight_changes");self.assertEqual(tuple(e[k] for k in keys),(0,)*len(keys));self.assertFalse(any(e[k] for k in ("published","recommended","consent_recorded","decision_recorded","approval_recorded","activation_recorded")))

if __name__=="__main__":unittest.main()
