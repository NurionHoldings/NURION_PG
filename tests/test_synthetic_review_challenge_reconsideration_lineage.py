import hashlib
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.synthetic_review_challenge_reconsideration_lineage import *

def d(v): return hashlib.sha256(v.encode()).hexdigest()
def rehash(row,**changes):
    x=replace(row,**changes);p={k:v for k,v in x.__dict__.items() if k!="digest"};return replace(x,digest=canonical_digest(p))
def populated():
    s=SyntheticReviewChallengeReconsiderationLineage()
    for cid in range(5501,5901):
        ws,aspect=s._expected(cid);s.add_control(cid,ws,aspect,f"synthetic:challenge-requirement:{(cid-5501)//25:02}",d(str(cid)),"EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS")
    return s
def anchored():
    s=populated();docs=tuple((p,d(p)) for p in PARTIES)
    routes=tuple((f,canonical_digest(("CHALLENGE_ROUTE",f,docs,d("packet")))) for f in FLOWS)
    a=s.anchor_source("synthetic:challenge-anchor:a",d("packet"),d("items"),d("registry"),d("manifest"),APPLIED_LESSONS,APPLIED_RULES,docs,routes,10,True,"synthetic:readiness-reviewer:maker","synthetic:preflight-reviewer:checker")
    return s,a
def challenged():
    s,a=anchored()
    docs=dict(a.party_document_digests);routes=dict(a.route_binding_digests)
    for f in FLOWS:
        for g in GROUNDS:
            party=FLOW_SOURCE_PARTY[f];document=canonical_digest(("CHALLENGE_DOCUMENT",party,docs[party],f,g,routes[f]))
            s.add_challenge(f"synthetic:challenge:{f}:{g}",f,g,document,f"synthetic:challenger:{party}")
    return s,a
def completed():
    s,a=challenged();return s,a,s.finalize("synthetic:reconsideration-receipt:a","synthetic:reconsideration-reviewer:independent")

class TestChallengeReconsideration(unittest.TestCase):
    def test_matrix(self):self.assertEqual((WORKSTREAMS[0][0],WORKSTREAMS[-1][1],len(WORKSTREAMS)),(5501,5900,16));self.assertTrue(all(b-a+1==25 for a,b,_ in WORKSTREAMS))
    def test_exact_controls(self):self.assertEqual(set(populated()._controls),set(range(5501,5901)))
    def test_control_mapping_rejected(self):
        with self.assertRaises(GovernanceRejected):SyntheticReviewChallengeReconsiderationLineage().add_control(5501,"WRONG",CONTROL_ASPECTS[0],"synthetic:challenge-requirement:00",d("x"),"PASS")
    def test_control_idempotency_conflict(self):
        s=SyntheticReviewChallengeReconsiderationLineage();a=(5501,WORKSTREAM_NAMES[0],CONTROL_ASPECTS[0],"synthetic:challenge-requirement:00",d("x"),"PASS");x=s.add_control(*a);self.assertIs(x,s.add_control(*a))
        with self.assertRaises(GovernanceRejected):s.add_control(*a[:-2],d("y"),"PASS")
    def test_control_slot_swap_rejected(self):
        s=populated();s._controls[5501],s._controls[5502]=s._controls[5502],s._controls[5501];self.assertFalse(s.evidence()["integrity_valid"])
    def test_anchor_requires_controls(self):
        with self.assertRaises(GovernanceRejected):SyntheticReviewChallengeReconsiderationLineage().anchor_source("synthetic:challenge-anchor:a",d("p"),d("i"),d("r"),d("m"),APPLIED_LESSONS,APPLIED_RULES,(),(),1,True,"synthetic:readiness-reviewer:a","synthetic:preflight-reviewer:b")
    def test_anchor_latest(self):
        s=populated();docs=tuple((p,d(p)) for p in PARTIES);routes=tuple((f,canonical_digest(("CHALLENGE_ROUTE",f,docs,d("p")))) for f in FLOWS)
        with self.assertRaises(GovernanceRejected):s.anchor_source("synthetic:challenge-anchor:a",d("p"),d("i"),d("r"),d("m"),APPLIED_LESSONS,APPLIED_RULES,docs,routes,1,False,"synthetic:readiness-reviewer:a","synthetic:preflight-reviewer:b")
    def test_anchor_lessons_rules_exact(self):
        s=populated();docs=tuple((p,d(p)) for p in PARTIES);routes=tuple((f,canonical_digest(("CHALLENGE_ROUTE",f,docs,d("p")))) for f in FLOWS)
        with self.assertRaises(GovernanceRejected):s.anchor_source("synthetic:challenge-anchor:a",d("p"),d("i"),d("r"),d("m"),APPLIED_LESSONS[:-1],APPLIED_RULES,docs,routes,1,True,"synthetic:readiness-reviewer:a","synthetic:preflight-reviewer:b")
    def test_source_role_separation(self):
        s=populated();docs=tuple((p,d(p)) for p in PARTIES);routes=tuple((f,canonical_digest(("CHALLENGE_ROUTE",f,docs,d("p")))) for f in FLOWS)
        with self.assertRaises(GovernanceRejected):s.anchor_source("synthetic:challenge-anchor:a",d("p"),d("i"),d("r"),d("m"),APPLIED_LESSONS,APPLIED_RULES,docs,routes,1,True,"synthetic:readiness-reviewer:same","synthetic:preflight-reviewer:same")
    def test_route_semantic_binding(self):
        s=populated();docs=tuple((p,d(p)) for p in PARTIES);routes=tuple((f,d(f)) for f in FLOWS)
        with self.assertRaises(GovernanceRejected):s.anchor_source("synthetic:challenge-anchor:a",d("p"),d("i"),d("r"),d("m"),APPLIED_LESSONS,APPLIED_RULES,docs,routes,1,True,"synthetic:readiness-reviewer:a","synthetic:preflight-reviewer:b")
    def test_anchor_idempotent(self):
        s,a=anchored();self.assertIs(a,s.anchor_source(a.anchor_id,a.preflight_packet_digest,a.item_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest,a.applied_lesson_ids,a.applied_rule_ids,a.party_document_digests,a.route_binding_digests,a.source_sequence,a.is_latest,a.readiness_reviewer,a.preflight_reviewer))
    def test_challenge_requires_anchor(self):
        with self.assertRaises(GovernanceRejected):SyntheticReviewChallengeReconsiderationLineage().add_challenge("synthetic:challenge:x",FLOWS[0],GROUNDS[0],d("x"),"synthetic:challenger:x")
    def test_challenge_namespace(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected):s.add_challenge("real:x",FLOWS[0],GROUNDS[0],d("x"),"synthetic:challenger:x")
    def test_challenge_document_rehash_substitution(self):
        s,_=challenged();keys=list(s._challenges);first,second=keys[0],keys[-1]
        s._challenges[first]=rehash(s._challenges[first],document_digest=s._challenges[second].document_digest)
        self.assertFalse(s.evidence()["integrity_valid"])
    def test_challenge_challenger_rehash_substitution(self):
        s,_=challenged();key=(FLOWS[0],GROUNDS[0])
        s._challenges[key]=rehash(s._challenges[key],challenger="synthetic:challenger:NURION_PG")
        self.assertFalse(s.evidence()["integrity_valid"])
    def test_exact_twenty_challenges(self):self.assertEqual(len(challenged()[0]._challenges),20)
    def test_every_challenge_has_hold(self):self.assertEqual(challenged()[0].evidence()["hold_count"],20)
    def test_challenge_idempotent_conflict(self):
        s,anchor=anchored();party=FLOW_SOURCE_PARTY[FLOWS[0]];route=dict(anchor.route_binding_digests)[FLOWS[0]]
        document=canonical_digest(("CHALLENGE_DOCUMENT",party,dict(anchor.party_document_digests)[party],FLOWS[0],GROUNDS[0],route))
        a=("synthetic:challenge:x",FLOWS[0],GROUNDS[0],document,f"synthetic:challenger:{party}");x=s.add_challenge(*a);self.assertIs(x,s.add_challenge(*a))
        with self.assertRaises(GovernanceRejected):s.add_challenge(a[0],a[1],a[2],d("y"),a[4])
    def test_finalize_requires_complete(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected):s.finalize("synthetic:reconsideration-receipt:x","synthetic:reconsideration-reviewer:c")
    def test_reconsideration_role_separation(self):
        s,_=challenged()
        with self.assertRaises(GovernanceRejected):s.finalize("synthetic:reconsideration-receipt:x","synthetic:reconsideration-reviewer:checker")
    def test_safe_receipt(self):
        r=completed()[2];self.assertTrue(r.review_complete);self.assertFalse(r.decision_recorded);self.assertFalse(r.approval_recorded);self.assertFalse(r.activation_recorded);self.assertFalse(r.deployment_recorded)
    def test_anchor_document_rehash_tamper(self):
        s,a=anchored();docs=((PARTIES[0],a.party_document_digests[1][1]),(PARTIES[1],a.party_document_digests[0][1]),a.party_document_digests[2]);s._anchor=rehash(a,party_document_digests=docs);self.assertFalse(s.evidence()["integrity_valid"])
    def test_anchor_route_rehash_tamper(self):
        s,a=anchored();routes=((FLOWS[0],d("fake")),)+a.route_binding_digests[1:];s._anchor=rehash(a,route_binding_digests=routes);self.assertFalse(s.evidence()["integrity_valid"])
    def test_challenge_route_rehash_tamper(self):
        s,_=challenged();k=next(iter(s._challenges));s._challenges[k]=rehash(s._challenges[k],route_binding_digest=d("fake"));self.assertFalse(s.evidence()["integrity_valid"])
    def test_challenge_key_swap_rehash_tamper(self):
        s,_=challenged();ks=list(s._challenges)[:2];s._challenges[ks[0]],s._challenges[ks[1]]=s._challenges[ks[1]],s._challenges[ks[0]];self.assertFalse(s.evidence()["integrity_valid"])
    def test_challenge_status_rehash_tamper(self):
        s,_=challenged();k=next(iter(s._challenges));s._challenges[k]=rehash(s._challenges[k],status="RESOLVED");self.assertFalse(s.evidence()["integrity_valid"])
    def test_receipt_decision_rehash_tamper(self):
        s,_,r=completed();s._receipt=rehash(r,decision_recorded=True);self.assertFalse(s.evidence()["integrity_valid"])
    def test_receipt_status_rehash_tamper(self):
        s,_,r=completed();s._receipt=rehash(r,status="APPROVED");self.assertFalse(s.evidence()["integrity_valid"])
    def test_receipt_source_reviewer_rehash_tamper(self):
        s,_,r=completed();s._receipt=rehash(r,source_reviewers=(r.source_reviewers[0],"synthetic:preflight-reviewer:x"));self.assertFalse(s.evidence()["integrity_valid"])
    def test_event_artifact_rehash_tamper(self):
        s,_=anchored();x=s._events[0]|{"artifact_digest":d("fake")};x["digest"]=canonical_digest({k:v for k,v in x.items() if k!="digest"});s._events[0]=x;self.assertFalse(s.evidence()["integrity_valid"])
    def test_missing_hold_fails_closed(self):
        s,_=challenged();s._holds.pop();self.assertFalse(s.evidence()["integrity_valid"])
    def test_missing_challenge_fails_closed(self):
        s,_=challenged();s._challenges.pop(next(iter(s._challenges)));self.assertFalse(s.evidence()["integrity_valid"])
    def test_concurrent_control_converges(self):
        s=SyntheticReviewChallengeReconsiderationLineage();a=(5501,WORKSTREAM_NAMES[0],CONTROL_ASPECTS[0],"synthetic:challenge-requirement:00",d("x"),"PASS")
        with ThreadPoolExecutor(max_workers=8) as p:rows=list(p.map(lambda _:s.add_control(*a),range(20)))
        self.assertEqual(len({x.digest for x in rows}),1)
    def test_complete_evidence(self):
        e=completed()[0].evidence();self.assertTrue(e["complete_reconsideration_evidence"]);self.assertEqual(e["challenge_count"],20);self.assertEqual(e["applied_lesson_ids"],list(APPLIED_LESSONS))
    def test_non_execution(self):
        e=completed()[0].evidence();keys=("external_calls","document_transmissions","electronic_signatures","external_pg_calls","card_network_calls","payment_approvals","cancellations","refunds","settlements","transfers","ledger_writes","credential_reads","deployments","policy_prompt_weight_changes");self.assertEqual(tuple(e[k] for k in keys),(0,)*len(keys));self.assertFalse(e["decision_recorded"]);self.assertFalse(e["approval_recorded"]);self.assertFalse(e["activation_recorded"])

if __name__=="__main__":unittest.main()
