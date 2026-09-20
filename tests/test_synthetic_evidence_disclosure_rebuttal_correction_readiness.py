import hashlib
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.synthetic_evidence_disclosure_rebuttal_correction_readiness import *

def d(v): return hashlib.sha256(v.encode()).hexdigest()
def rehash(row,**changes):
    x=replace(row,**changes);p={k:v for k,v in x.__dict__.items() if k!="digest"};return replace(x,digest=canonical_digest(p))
def populated():
    s=SyntheticEvidenceDisclosureRebuttalCorrectionReadiness()
    for cid in range(5901,6301):
        ws,aspect=s._expected(cid);s.add_control(cid,ws,aspect,f"synthetic:correction-requirement:{(cid-5901)//25:02}",d(str(cid)),"EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS")
    return s
def anchored():
    s=populated();docs=tuple((p,d(p)) for p in PARTIES);receipt=d("receipt")
    routes=tuple((f,canonical_digest(("DISCLOSURE_ROUTE",f,FLOW_PARTIES[f],docs,receipt))) for f in FLOWS)
    reviewers=("synthetic:readiness-reviewer:maker","synthetic:preflight-reviewer:checker","synthetic:reconsideration-reviewer:independent")
    a=s.anchor_source("synthetic:disclosure-anchor:a",receipt,d("challenges"),d("registry"),d("manifest"),APPLIED_LESSONS,APPLIED_RULES,docs,routes,12,True,reviewers)
    return s,a
def cased():
    s,a=anchored();docs=dict(a.party_document_digests);routes=dict(a.route_binding_digests)
    for f in FLOWS:
        source,counterparty=FLOW_PARTIES[f]
        for topic in TOPICS:
            disclosure=canonical_digest(("DISCLOSURE_DOCUMENT",source,docs[source],f,topic,routes[f],a.challenge_set_digest))
            rebuttal=canonical_digest(("REBUTTAL_DOCUMENT",counterparty,f,topic,disclosure,routes[f]))
            correction=canonical_digest(("CORRECTION_DRAFT",source,counterparty,f,topic,disclosure,rebuttal,routes[f]))
            s.add_case(f"synthetic:correction-case:{f}:{topic}",f,topic,disclosure,rebuttal,correction,f"synthetic:discloser:{source}",f"synthetic:rebutter:{counterparty}")
    return s,a
def completed():
    s,a=cased();return s,a,s.finalize("synthetic:correction-readiness-packet:a","synthetic:packet-compiler:new")

class TestCorrectionReadiness(unittest.TestCase):
    def test_matrix(self):self.assertEqual((WORKSTREAMS[0][0],WORKSTREAMS[-1][1],len(WORKSTREAMS)),(5901,6300,16));self.assertTrue(all(b-a+1==25 for a,b,_ in WORKSTREAMS))
    def test_exact_controls(self):self.assertEqual(set(populated()._controls),set(range(5901,6301)))
    def test_control_mapping_rejected(self):
        with self.assertRaises(GovernanceRejected):SyntheticEvidenceDisclosureRebuttalCorrectionReadiness().add_control(5901,"WRONG",CONTROL_ASPECTS[0],"synthetic:correction-requirement:00",d("x"),"PASS")
    def test_control_idempotency_conflict(self):
        s=SyntheticEvidenceDisclosureRebuttalCorrectionReadiness();a=(5901,WORKSTREAM_NAMES[0],CONTROL_ASPECTS[0],"synthetic:correction-requirement:00",d("x"),"PASS");x=s.add_control(*a);self.assertIs(x,s.add_control(*a))
        with self.assertRaises(GovernanceRejected):s.add_control(*a[:-2],d("y"),"PASS")
    def test_control_slot_swap_rejected(self):
        s=populated();s._controls[5901],s._controls[5902]=s._controls[5902],s._controls[5901];self.assertFalse(s.evidence()["integrity_valid"])
    def test_anchor_requires_controls(self):
        with self.assertRaises(GovernanceRejected):SyntheticEvidenceDisclosureRebuttalCorrectionReadiness().anchor_source("synthetic:disclosure-anchor:a",d("r"),d("c"),d("l"),d("m"),APPLIED_LESSONS,APPLIED_RULES,(),(),1,True,())
    def test_anchor_latest(self):
        s=populated();docs=tuple((p,d(p)) for p in PARTIES);receipt=d("r");routes=tuple((f,canonical_digest(("DISCLOSURE_ROUTE",f,FLOW_PARTIES[f],docs,receipt))) for f in FLOWS)
        with self.assertRaises(GovernanceRejected):s.anchor_source("synthetic:disclosure-anchor:a",receipt,d("c"),d("l"),d("m"),APPLIED_LESSONS,APPLIED_RULES,docs,routes,1,False,("synthetic:readiness-reviewer:a","synthetic:preflight-reviewer:b","synthetic:reconsideration-reviewer:c"))
    def test_anchor_lessons_rules_exact(self):
        s=populated();docs=tuple((p,d(p)) for p in PARTIES);receipt=d("r");routes=tuple((f,canonical_digest(("DISCLOSURE_ROUTE",f,FLOW_PARTIES[f],docs,receipt))) for f in FLOWS)
        with self.assertRaises(GovernanceRejected):s.anchor_source("synthetic:disclosure-anchor:a",receipt,d("c"),d("l"),d("m"),APPLIED_LESSONS[:-1],APPLIED_RULES,docs,routes,1,True,("synthetic:readiness-reviewer:a","synthetic:preflight-reviewer:b","synthetic:reconsideration-reviewer:c"))
    def test_source_role_separation(self):
        s=populated();docs=tuple((p,d(p)) for p in PARTIES);receipt=d("r");routes=tuple((f,canonical_digest(("DISCLOSURE_ROUTE",f,FLOW_PARTIES[f],docs,receipt))) for f in FLOWS)
        with self.assertRaises(GovernanceRejected):s.anchor_source("synthetic:disclosure-anchor:a",receipt,d("c"),d("l"),d("m"),APPLIED_LESSONS,APPLIED_RULES,docs,routes,1,True,("synthetic:readiness-reviewer:same","synthetic:preflight-reviewer:same","synthetic:reconsideration-reviewer:c"))
    def test_malformed_source_reviewer_fails_closed(self):
        s=populated();docs=tuple((p,d(p)) for p in PARTIES);receipt=d("r");routes=tuple((f,canonical_digest(("DISCLOSURE_ROUTE",f,FLOW_PARTIES[f],docs,receipt))) for f in FLOWS)
        with self.assertRaises(GovernanceRejected):s.anchor_source("synthetic:disclosure-anchor:a",receipt,d("c"),d("l"),d("m"),APPLIED_LESSONS,APPLIED_RULES,docs,routes,1,True,("malformed","synthetic:preflight-reviewer:b","synthetic:reconsideration-reviewer:c"))
    def test_route_semantic_binding(self):
        s=populated();docs=tuple((p,d(p)) for p in PARTIES)
        with self.assertRaises(GovernanceRejected):s.anchor_source("synthetic:disclosure-anchor:a",d("r"),d("c"),d("l"),d("m"),APPLIED_LESSONS,APPLIED_RULES,docs,tuple((f,d(f)) for f in FLOWS),1,True,("synthetic:readiness-reviewer:a","synthetic:preflight-reviewer:b","synthetic:reconsideration-reviewer:c"))
    def test_anchor_idempotent(self):
        s,a=anchored();self.assertIs(a,s.anchor_source(a.anchor_id,a.reconsideration_receipt_digest,a.challenge_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest,a.applied_lesson_ids,a.applied_rule_ids,a.party_document_digests,a.route_binding_digests,a.source_sequence,a.is_latest,a.source_reviewers))
    def test_case_requires_anchor(self):
        with self.assertRaises(GovernanceRejected):SyntheticEvidenceDisclosureRebuttalCorrectionReadiness().add_case("synthetic:correction-case:x",FLOWS[0],TOPICS[0],d("d"),d("r"),d("c"),"synthetic:discloser:x","synthetic:rebutter:y")
    def test_case_namespace(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected):s.add_case("real:x",FLOWS[0],TOPICS[0],d("d"),d("r"),d("c"),"synthetic:discloser:x","synthetic:rebutter:y")
    def test_exact_twenty_cases_and_holds(self):
        s,_=cased();self.assertEqual((len(s._cases),s.evidence()["hold_count"]),(20,20))
    def test_case_idempotent_conflict(self):
        s,a=anchored();f=FLOWS[0];topic=TOPICS[0];source,counter=FLOW_PARTIES[f];route=dict(a.route_binding_digests)[f];doc=dict(a.party_document_digests)[source]
        disclosure=canonical_digest(("DISCLOSURE_DOCUMENT",source,doc,f,topic,route,a.challenge_set_digest));rebuttal=canonical_digest(("REBUTTAL_DOCUMENT",counter,f,topic,disclosure,route));correction=canonical_digest(("CORRECTION_DRAFT",source,counter,f,topic,disclosure,rebuttal,route));args=("synthetic:correction-case:x",f,topic,disclosure,rebuttal,correction,f"synthetic:discloser:{source}",f"synthetic:rebutter:{counter}");x=s.add_case(*args);self.assertIs(x,s.add_case(*args))
        with self.assertRaises(GovernanceRejected):s.add_case(*args[:-3],d("bad"),*args[-2:])
    def test_disclosure_rehash_substitution(self):
        s,_=cased();k=next(iter(s._cases));s._cases[k]=rehash(s._cases[k],disclosure_digest=d("fake"));self.assertFalse(s.evidence()["integrity_valid"])
    def test_rebuttal_rehash_substitution(self):
        s,_=cased();k=next(iter(s._cases));s._cases[k]=rehash(s._cases[k],rebuttal_digest=d("fake"));self.assertFalse(s.evidence()["integrity_valid"])
    def test_correction_rehash_substitution(self):
        s,_=cased();k=next(iter(s._cases));s._cases[k]=rehash(s._cases[k],correction_draft_digest=d("fake"));self.assertFalse(s.evidence()["integrity_valid"])
    def test_party_rehash_substitution(self):
        s,_=cased();k=next(iter(s._cases));s._cases[k]=rehash(s._cases[k],rebutter="synthetic:rebutter:UPSTREAM_PG");self.assertFalse(s.evidence()["integrity_valid"])
    def test_anchor_document_rehash_tamper(self):
        s,a=anchored();docs=((PARTIES[0],a.party_document_digests[1][1]),(PARTIES[1],a.party_document_digests[0][1]),a.party_document_digests[2]);s._anchor=rehash(a,party_document_digests=docs);self.assertFalse(s.evidence()["integrity_valid"])
    def test_source_reviewer_lineage_rehash_tamper(self):
        s,a=anchored();reviewers=(a.source_reviewers[0],a.source_reviewers[1],"synthetic:reconsideration-reviewer:substitute")
        s._anchor=rehash(a,source_reviewers=reviewers);self.assertFalse(s.evidence()["integrity_valid"])
    def test_case_key_swap_rehash_tamper(self):
        s,_=cased();ks=list(s._cases)[:2];s._cases[ks[0]],s._cases[ks[1]]=s._cases[ks[1]],s._cases[ks[0]];self.assertFalse(s.evidence()["integrity_valid"])
    def test_case_status_rehash_tamper(self):
        s,_=cased();k=next(iter(s._cases));s._cases[k]=rehash(s._cases[k],status="PUBLISHED");self.assertFalse(s.evidence()["integrity_valid"])
    def test_finalize_requires_complete(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected):s.finalize("synthetic:correction-readiness-packet:x","synthetic:packet-compiler:new")
    def test_compiler_role_separation(self):
        s,_=cased()
        with self.assertRaises(GovernanceRejected):s.finalize("synthetic:correction-readiness-packet:x","synthetic:packet-compiler:checker")
    def test_safe_packet(self):
        r=completed()[2];self.assertTrue(r.complete);self.assertFalse(r.published);self.assertFalse(r.decision_recorded);self.assertFalse(r.approval_recorded);self.assertFalse(r.activation_recorded);self.assertFalse(r.deployment_recorded)
    def test_packet_publication_rehash_tamper(self):
        s,_,r=completed();s._packet=rehash(r,published=True);self.assertFalse(s.evidence()["integrity_valid"])
    def test_packet_status_rehash_tamper(self):
        s,_,r=completed();s._packet=rehash(r,status="APPROVED");self.assertFalse(s.evidence()["integrity_valid"])
    def test_event_artifact_rehash_tamper(self):
        s,_=anchored();x=s._events[0]|{"artifact_digest":d("fake")};x["digest"]=canonical_digest({k:v for k,v in x.items() if k!="digest"});s._events[0]=x;self.assertFalse(s.evidence()["integrity_valid"])
    def test_missing_hold_fails_closed(self):
        s,_=cased();s._holds.pop();self.assertFalse(s.evidence()["integrity_valid"])
    def test_missing_case_fails_closed(self):
        s,_=cased();s._cases.pop(next(iter(s._cases)));self.assertFalse(s.evidence()["integrity_valid"])
    def test_concurrent_control_converges(self):
        s=SyntheticEvidenceDisclosureRebuttalCorrectionReadiness();a=(5901,WORKSTREAM_NAMES[0],CONTROL_ASPECTS[0],"synthetic:correction-requirement:00",d("x"),"PASS")
        with ThreadPoolExecutor(max_workers=8) as p:rows=list(p.map(lambda _:s.add_control(*a),range(20)))
        self.assertEqual(len({x.digest for x in rows}),1)
    def test_complete_evidence(self):
        e=completed()[0].evidence();self.assertTrue(e["complete_correction_readiness_evidence"]);self.assertEqual(e["case_count"],20);self.assertEqual(e["applied_lesson_ids"],list(APPLIED_LESSONS))
    def test_non_execution(self):
        e=completed()[0].evidence();keys=("external_calls","document_transmissions","electronic_signatures","external_pg_calls","card_network_calls","payment_approvals","cancellations","refunds","settlements","transfers","ledger_writes","credential_reads","deployments","policy_prompt_weight_changes");self.assertEqual(tuple(e[k] for k in keys),(0,)*len(keys));self.assertFalse(e["published"]);self.assertFalse(e["decision_recorded"]);self.assertFalse(e["approval_recorded"]);self.assertFalse(e["activation_recorded"])

if __name__=="__main__":unittest.main()
