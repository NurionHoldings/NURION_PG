import hashlib
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.synthetic_nonbinding_resolution_alternative_simulation import *

def d(v):return hashlib.sha256(v.encode()).hexdigest()
def rehash(row,**changes):
    x=replace(row,**changes);p={k:v for k,v in x.__dict__.items() if k!="digest"};return replace(x,digest=canonical_digest(p))
def populated():
    s=SyntheticNonbindingResolutionAlternativeSimulation()
    for cid in range(6701,7101):
        ws,aspect=s._expected(cid);s.add_control(cid,ws,aspect,f"synthetic:alternative-requirement:{(cid-6701)//25:02}",d(str(cid)),"EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS")
    return s
def anchored():
    s=populated();docs=tuple((p,d(p)) for p in PARTIES);receipt=d("conflict-review-packet")
    routes=tuple((f,canonical_digest(("NONBINDING_ALTERNATIVE_ROUTE",f,FLOW_PARTIES[f],docs,receipt))) for f in FLOWS)
    reviewers=("synthetic:readiness-reviewer:maker","synthetic:preflight-reviewer:checker","synthetic:reconsideration-reviewer:independent")
    compilers=("synthetic:packet-compiler:antecedent","synthetic:packet-compiler:conflict")
    a=s.anchor_source("synthetic:alternative-anchor:a",receipt,d("cases"),d("registry"),d("manifest"),APPLIED_LESSONS,APPLIED_RULES,docs,routes,13,True,reviewers,compilers)
    return s,a
def cased():
    s,a=anchored();docs=dict(a.party_document_digests);routes=dict(a.route_binding_digests)
    for f in FLOWS:
        source,counter=FLOW_PARTIES[f]
        for dimension in DIMENSIONS:
            condition=canonical_digest(("ALTERNATIVE_CONDITION",source,docs[source],f,dimension,routes[f],a.conflict_case_set_digest))
            impact=canonical_digest(("ALTERNATIVE_IMPACT",counter,f,dimension,condition,routes[f]))
            risk=canonical_digest(("ALTERNATIVE_RESIDUAL_RISK",source,counter,f,dimension,condition,impact,routes[f]))
            comparison=canonical_digest(("NONBINDING_COMPARISON",f,dimension,condition,impact,risk,a.conflict_review_packet_digest))
            s.add_case(f"synthetic:alternative-case:{f}:{dimension}",f,dimension,condition,impact,risk,comparison,f"synthetic:alternative-simulator:{source}",f"synthetic:risk-evaluator:{counter}")
    return s,a
def completed():
    s,a=cased();return s,a,s.finalize("synthetic:nonbinding-simulation-packet:a","synthetic:simulation-compiler:new")

class TestNonbindingResolutionAlternativeSimulation(unittest.TestCase):
    def test_matrix(self):self.assertEqual((WORKSTREAMS[0][0],WORKSTREAMS[-1][1],len(WORKSTREAMS)),(6701,7100,16));self.assertTrue(all(b-a+1==25 for a,b,_ in WORKSTREAMS))
    def test_exact_controls(self):self.assertEqual(set(populated()._controls),set(range(6701,7101)))
    def test_control_mapping_rejected(self):
        with self.assertRaises(GovernanceRejected):SyntheticNonbindingResolutionAlternativeSimulation().add_control(6701,"WRONG",CONTROL_ASPECTS[0],"synthetic:alternative-requirement:00",d("x"),"PASS")
    def test_control_idempotency_conflict(self):
        s=SyntheticNonbindingResolutionAlternativeSimulation();a=(6701,WORKSTREAM_NAMES[0],CONTROL_ASPECTS[0],"synthetic:alternative-requirement:00",d("x"),"PASS");x=s.add_control(*a);self.assertIs(x,s.add_control(*a))
        with self.assertRaises(GovernanceRejected):s.add_control(*a[:-2],d("y"),"PASS")
    def test_control_slot_swap_rehash_tamper(self):
        s=populated();s._controls[6701],s._controls[6702]=s._controls[6702],s._controls[6701];self.assertFalse(s.evidence()["integrity_valid"])
    def test_anchor_requires_controls(self):
        with self.assertRaises(GovernanceRejected):SyntheticNonbindingResolutionAlternativeSimulation().anchor_source("synthetic:alternative-anchor:a",d("r"),d("c"),d("l"),d("m"),APPLIED_LESSONS,APPLIED_RULES,(),(),1,True,(),())
    def test_anchor_latest(self):
        s=populated();docs=tuple((p,d(p)) for p in PARTIES);receipt=d("r");routes=tuple((f,canonical_digest(("NONBINDING_ALTERNATIVE_ROUTE",f,FLOW_PARTIES[f],docs,receipt))) for f in FLOWS)
        with self.assertRaises(GovernanceRejected):s.anchor_source("synthetic:alternative-anchor:a",receipt,d("c"),d("l"),d("m"),APPLIED_LESSONS,APPLIED_RULES,docs,routes,1,False,("synthetic:readiness-reviewer:a","synthetic:preflight-reviewer:b","synthetic:reconsideration-reviewer:c"),("synthetic:packet-compiler:d","synthetic:packet-compiler:e"))
    def test_anchor_lessons_exact(self):
        s=populated();docs=tuple((p,d(p)) for p in PARTIES);receipt=d("r");routes=tuple((f,canonical_digest(("NONBINDING_ALTERNATIVE_ROUTE",f,FLOW_PARTIES[f],docs,receipt))) for f in FLOWS)
        with self.assertRaises(GovernanceRejected):s.anchor_source("synthetic:alternative-anchor:a",receipt,d("c"),d("l"),d("m"),APPLIED_LESSONS[:-1],APPLIED_RULES,docs,routes,1,True,("synthetic:readiness-reviewer:a","synthetic:preflight-reviewer:b","synthetic:reconsideration-reviewer:c"),("synthetic:packet-compiler:d","synthetic:packet-compiler:e"))
    def test_source_role_separation(self):
        s=populated();docs=tuple((p,d(p)) for p in PARTIES);receipt=d("r");routes=tuple((f,canonical_digest(("NONBINDING_ALTERNATIVE_ROUTE",f,FLOW_PARTIES[f],docs,receipt))) for f in FLOWS)
        with self.assertRaises(GovernanceRejected):s.anchor_source("synthetic:alternative-anchor:a",receipt,d("c"),d("l"),d("m"),APPLIED_LESSONS,APPLIED_RULES,docs,routes,1,True,("synthetic:readiness-reviewer:same","synthetic:preflight-reviewer:same","synthetic:reconsideration-reviewer:c"),("synthetic:packet-compiler:d","synthetic:packet-compiler:e"))
    def test_source_compiler_separation(self):
        s=populated();docs=tuple((p,d(p)) for p in PARTIES);receipt=d("r");routes=tuple((f,canonical_digest(("NONBINDING_ALTERNATIVE_ROUTE",f,FLOW_PARTIES[f],docs,receipt))) for f in FLOWS)
        with self.assertRaises(GovernanceRejected):s.anchor_source("synthetic:alternative-anchor:a",receipt,d("c"),d("l"),d("m"),APPLIED_LESSONS,APPLIED_RULES,docs,routes,1,True,("synthetic:readiness-reviewer:a","synthetic:preflight-reviewer:b","synthetic:reconsideration-reviewer:c"),("synthetic:packet-compiler:d","synthetic:packet-compiler:d"))
    def test_route_semantic_binding(self):
        s=populated();docs=tuple((p,d(p)) for p in PARTIES)
        with self.assertRaises(GovernanceRejected):s.anchor_source("synthetic:alternative-anchor:a",d("r"),d("c"),d("l"),d("m"),APPLIED_LESSONS,APPLIED_RULES,docs,tuple((f,d(f)) for f in FLOWS),1,True,("synthetic:readiness-reviewer:a","synthetic:preflight-reviewer:b","synthetic:reconsideration-reviewer:c"),("synthetic:packet-compiler:d","synthetic:packet-compiler:e"))
    def test_anchor_idempotent(self):
        s,a=anchored();self.assertIs(a,s.anchor_source(a.anchor_id,a.conflict_review_packet_digest,a.conflict_case_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest,a.applied_lesson_ids,a.applied_rule_ids,a.party_document_digests,a.route_binding_digests,a.source_sequence,a.is_latest,a.source_reviewers,a.source_compilers))
    def test_case_requires_anchor(self):
        with self.assertRaises(GovernanceRejected):SyntheticNonbindingResolutionAlternativeSimulation().add_case("synthetic:alternative-case:x",FLOWS[0],DIMENSIONS[0],d("c"),d("i"),d("r"),d("x"),"synthetic:alternative-simulator:x","synthetic:risk-evaluator:y")
    def test_case_namespace(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected):s.add_case("real:x",FLOWS[0],DIMENSIONS[0],d("c"),d("i"),d("r"),d("x"),"synthetic:alternative-simulator:x","synthetic:risk-evaluator:y")
    def test_exact_twenty_cases_and_holds(self):
        s,_=cased();self.assertEqual((len(s._cases),s.evidence()["hold_count"]),(20,20))
    def test_case_idempotent_conflict(self):
        s,a=anchored();f=FLOWS[0];dim=DIMENSIONS[0];source,counter=FLOW_PARTIES[f];route=dict(a.route_binding_digests)[f];doc=dict(a.party_document_digests)[source];condition=canonical_digest(("ALTERNATIVE_CONDITION",source,doc,f,dim,route,a.conflict_case_set_digest));impact=canonical_digest(("ALTERNATIVE_IMPACT",counter,f,dim,condition,route));risk=canonical_digest(("ALTERNATIVE_RESIDUAL_RISK",source,counter,f,dim,condition,impact,route));comparison=canonical_digest(("NONBINDING_COMPARISON",f,dim,condition,impact,risk,a.conflict_review_packet_digest));args=("synthetic:alternative-case:x",f,dim,condition,impact,risk,comparison,f"synthetic:alternative-simulator:{source}",f"synthetic:risk-evaluator:{counter}");x=s.add_case(*args);self.assertIs(x,s.add_case(*args))
        with self.assertRaises(GovernanceRejected):s.add_case(*args[:-4],d("bad"),*args[-3:])
    def test_condition_rehash_substitution(self):
        s,_=cased();k=next(iter(s._cases));s._cases[k]=rehash(s._cases[k],condition_digest=d("fake"));self.assertFalse(s.evidence()["integrity_valid"])
    def test_impact_rehash_substitution(self):
        s,_=cased();k=next(iter(s._cases));s._cases[k]=rehash(s._cases[k],impact_digest=d("fake"));self.assertFalse(s.evidence()["integrity_valid"])
    def test_residual_risk_rehash_substitution(self):
        s,_=cased();k=next(iter(s._cases));s._cases[k]=rehash(s._cases[k],residual_risk_digest=d("fake"));self.assertFalse(s.evidence()["integrity_valid"])
    def test_comparison_rehash_substitution(self):
        s,_=cased();k=next(iter(s._cases));s._cases[k]=rehash(s._cases[k],comparison_digest=d("fake"));self.assertFalse(s.evidence()["integrity_valid"])
    def test_party_rehash_substitution(self):
        s,_=cased();k=next(iter(s._cases));s._cases[k]=rehash(s._cases[k],evaluator="synthetic:risk-evaluator:UPSTREAM_PG");self.assertFalse(s.evidence()["integrity_valid"])
    def test_anchor_document_rehash_tamper(self):
        s,a=anchored();docs=((PARTIES[0],a.party_document_digests[1][1]),(PARTIES[1],a.party_document_digests[0][1]),a.party_document_digests[2]);s._anchor=rehash(a,party_document_digests=docs);self.assertFalse(s.evidence()["integrity_valid"])
    def test_source_lineage_rehash_tamper(self):
        s,a=anchored();s._anchor=rehash(a,source_compilers=(a.source_compilers[0],"synthetic:packet-compiler:substitute"));self.assertFalse(s.evidence()["integrity_valid"])
    def test_case_key_swap_rehash_tamper(self):
        s,_=cased();ks=list(s._cases)[:2];s._cases[ks[0]],s._cases[ks[1]]=s._cases[ks[1]],s._cases[ks[0]];self.assertFalse(s.evidence()["integrity_valid"])
    def test_case_status_rehash_tamper(self):
        s,_=cased();k=next(iter(s._cases));s._cases[k]=rehash(s._cases[k],status="RECOMMENDED");self.assertFalse(s.evidence()["integrity_valid"])
    def test_finalize_requires_complete(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected):s.finalize("synthetic:nonbinding-simulation-packet:x","synthetic:simulation-compiler:new")
    def test_compiler_role_separation(self):
        s,a=cased()
        with self.assertRaises(GovernanceRejected):s.finalize("synthetic:nonbinding-simulation-packet:x","synthetic:simulation-compiler:antecedent")
    def test_safe_packet(self):
        r=completed()[2];self.assertTrue(r.complete);self.assertFalse(r.published);self.assertFalse(r.recommended);self.assertFalse(r.consent_recorded);self.assertFalse(r.decision_recorded);self.assertFalse(r.approval_recorded);self.assertFalse(r.activation_recorded);self.assertFalse(r.deployment_recorded)
    def test_packet_recommendation_rehash_tamper(self):
        s,_,r=completed();s._packet=rehash(r,recommended=True);self.assertFalse(s.evidence()["integrity_valid"])
    def test_packet_source_reviewer_rehash_tamper(self):
        s,_,r=completed();reviewers=(r.source_reviewers[0],r.source_reviewers[1],"synthetic:reconsideration-reviewer:substitute")
        s._packet=rehash(r,source_reviewers=reviewers);self.assertFalse(s.evidence()["integrity_valid"])
    def test_packet_source_lineage_rehash_tamper(self):
        s,_,r=completed();s._packet=rehash(r,source_lineage_digest=d("substitute"));self.assertFalse(s.evidence()["integrity_valid"])
    def test_packet_status_rehash_tamper(self):
        s,_,r=completed();s._packet=rehash(r,status="APPROVED");self.assertFalse(s.evidence()["integrity_valid"])
    def test_event_artifact_rehash_tamper(self):
        s,_=anchored();x=s._events[0]|{"artifact_digest":d("fake")};x["digest"]=canonical_digest({k:v for k,v in x.items() if k!="digest"});s._events[0]=x;self.assertFalse(s.evidence()["integrity_valid"])
    def test_missing_hold_fails_closed(self):
        s,_=cased();s._holds.pop();self.assertFalse(s.evidence()["integrity_valid"])
    def test_missing_case_fails_closed(self):
        s,_=cased();s._cases.pop(next(iter(s._cases)));self.assertFalse(s.evidence()["integrity_valid"])
    def test_concurrent_control_converges(self):
        s=SyntheticNonbindingResolutionAlternativeSimulation();a=(6701,WORKSTREAM_NAMES[0],CONTROL_ASPECTS[0],"synthetic:alternative-requirement:00",d("x"),"PASS")
        with ThreadPoolExecutor(max_workers=8) as p:rows=list(p.map(lambda _:s.add_control(*a),range(20)))
        self.assertEqual(len({x.digest for x in rows}),1)
    def test_complete_evidence(self):
        e=completed()[0].evidence();self.assertTrue(e["complete_nonbinding_simulation_evidence"]);self.assertEqual(e["case_count"],20);self.assertEqual(e["applied_lesson_ids"],list(APPLIED_LESSONS))
    def test_non_execution(self):
        e=completed()[0].evidence();keys=("external_calls","document_transmissions","electronic_signatures","external_pg_calls","card_network_calls","payment_approvals","cancellations","refunds","settlements","transfers","ledger_writes","credential_reads","deployments","policy_prompt_weight_changes");self.assertEqual(tuple(e[k] for k in keys),(0,)*len(keys));self.assertFalse(e["published"]);self.assertFalse(e["recommended"]);self.assertFalse(e["consent_recorded"]);self.assertFalse(e["decision_recorded"]);self.assertFalse(e["approval_recorded"]);self.assertFalse(e["activation_recorded"])

if __name__=="__main__":unittest.main()
