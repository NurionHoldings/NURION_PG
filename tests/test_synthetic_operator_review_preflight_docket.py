import hashlib
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.synthetic_operator_review_preflight_docket import *

def d(v): return hashlib.sha256(v.encode()).hexdigest()
def rehash(row,**changes):
    x=replace(row,**changes); p={k:v for k,v in x.__dict__.items() if k!="digest"}; return replace(x,digest=canonical_digest(p))
def populated():
    s=SyntheticOperatorReviewPreflightDocket()
    for cid in range(5101,5501):
        ws,aspect=s._expected(cid); s.add_control(cid,ws,aspect,f"synthetic:preflight-requirement:{(cid-5101)//25:02}",d(str(cid)),"EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS")
    return s
def anchored():
    s=populated(); profiles=tuple((p,d(p)) for p in PARTIES); ops=tuple((p,COMMON_OPERATIONS) for p in PARTIES); toks=tuple((p,COMMON_TOKEN_CLASSES) for p in PARTIES)
    bindings=tuple((p,canonical_digest(("PARTY_CAPABILITY",p,dict(profiles)[p],dict(ops)[p],dict(toks)[p]))) for p in PARTIES)
    a=s.anchor_readiness("synthetic:preflight-anchor:a",d("receipt"),d("plans"),d("results"),d("registry"),d("manifest"),APPLIED_LESSONS,APPLIED_RULES,profiles,bindings,ops,toks,COMMON_OPERATIONS,COMMON_TOKEN_CLASSES,8,True,"synthetic:readiness-reviewer:maker")
    return s,a
def reviewed():
    s,a=anchored()
    for f in FLOWS:
        for sc in SCENARIOS:s.add_review_item(f"synthetic:preflight-item:{f}:{sc}",f,sc,COMMON_OPERATIONS,COMMON_TOKEN_CLASSES)
    return s,a
def completed():
    s,a=reviewed(); return s,a,s.finalize("synthetic:preflight-packet:a","synthetic:preflight-reviewer:checker")

class TestPreflight(unittest.TestCase):
    def test_matrix(self): self.assertEqual((WORKSTREAMS[0][0],WORKSTREAMS[-1][1],len(WORKSTREAMS)),(5101,5500,16)); self.assertTrue(all(b-a+1==25 for a,b,_ in WORKSTREAMS))
    def test_exact_control_ids(self): self.assertEqual(set(populated()._controls),set(range(5101,5501)))
    def test_control_mapping_rejects(self):
        s=SyntheticOperatorReviewPreflightDocket()
        with self.assertRaises(GovernanceRejected):s.add_control(5101,"WRONG",CONTROL_ASPECTS[0],"synthetic:preflight-requirement:00",d("x"),"PASS")
    def test_control_idempotency_and_conflict(self):
        s=SyntheticOperatorReviewPreflightDocket(); args=(5101,WORKSTREAM_NAMES[0],CONTROL_ASPECTS[0],"synthetic:preflight-requirement:00",d("x"),"PASS"); a=s.add_control(*args);self.assertIs(a,s.add_control(*args))
        with self.assertRaises(GovernanceRejected):s.add_control(*args[:-2],d("y"),"PASS")
    def test_anchor_needs_all_controls(self):
        with self.assertRaises(GovernanceRejected):SyntheticOperatorReviewPreflightDocket().anchor_readiness("synthetic:preflight-anchor:a",d("r"),d("p"),d("x"),d("l"),d("m"),APPLIED_LESSONS,APPLIED_RULES,(),(),(),(),COMMON_OPERATIONS,COMMON_TOKEN_CLASSES,1,True,"synthetic:readiness-reviewer:m")
    def test_anchor_latest_only(self):
        s=populated(); profiles=tuple((p,d(p)) for p in PARTIES); specs=tuple((p,COMMON_OPERATIONS) for p in PARTIES); tokens=tuple((p,COMMON_TOKEN_CLASSES) for p in PARTIES)
        bindings=tuple((p,canonical_digest(("PARTY_CAPABILITY",p,dict(profiles)[p],dict(specs)[p],dict(tokens)[p]))) for p in PARTIES)
        with self.assertRaises(GovernanceRejected):s.anchor_readiness("synthetic:preflight-anchor:a",d("r"),d("p"),d("x"),d("l"),d("m"),APPLIED_LESSONS,APPLIED_RULES,profiles,bindings,specs,tokens,COMMON_OPERATIONS,COMMON_TOKEN_CLASSES,1,False,"synthetic:readiness-reviewer:m")
    def test_anchor_requires_all_lessons_and_rules(self):
        s=populated(); profiles=tuple((p,d(p)) for p in PARTIES); specs=tuple((p,COMMON_OPERATIONS) for p in PARTIES); tokens=tuple((p,COMMON_TOKEN_CLASSES) for p in PARTIES)
        bindings=tuple((p,canonical_digest(("PARTY_CAPABILITY",p,dict(profiles)[p],dict(specs)[p],dict(tokens)[p]))) for p in PARTIES)
        with self.assertRaises(GovernanceRejected):s.anchor_readiness("synthetic:preflight-anchor:a",d("r"),d("p"),d("x"),d("l"),d("m"),APPLIED_LESSONS[:-1],APPLIED_RULES,profiles,bindings,specs,tokens,COMMON_OPERATIONS,COMMON_TOKEN_CLASSES,1,True,"synthetic:readiness-reviewer:m")
    def test_common_capability_recalculated(self):
        s=populated(); profiles=tuple((p,d(p)) for p in PARTIES); specs=((PARTIES[0],COMMON_OPERATIONS),(PARTIES[1],COMMON_OPERATIONS),(PARTIES[2],("MAP",))) ; tokens=tuple((p,COMMON_TOKEN_CLASSES) for p in PARTIES)
        bindings=tuple((p,canonical_digest(("PARTY_CAPABILITY",p,dict(profiles)[p],dict(specs)[p],dict(tokens)[p]))) for p in PARTIES)
        with self.assertRaises(GovernanceRejected):s.anchor_readiness("synthetic:preflight-anchor:a",d("r"),d("p"),d("x"),d("l"),d("m"),APPLIED_LESSONS,APPLIED_RULES,profiles,bindings,specs,tokens,COMMON_OPERATIONS,COMMON_TOKEN_CLASSES,1,True,"synthetic:readiness-reviewer:m")
    def test_anchor_idempotency(self):
        s,a=anchored(); self.assertIs(a,s.anchor_readiness(a.anchor_id,a.readiness_receipt_digest,a.plan_set_digest,a.result_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest,a.applied_lesson_ids,a.applied_rule_ids,a.capability_profile_digests,a.capability_binding_digests,a.capability_operations,a.capability_token_classes,a.common_operations,a.common_token_classes,a.source_sequence,a.is_latest,a.readiness_reviewer))
    def test_item_requires_anchor(self):
        with self.assertRaises(GovernanceRejected):SyntheticOperatorReviewPreflightDocket().add_review_item("synthetic:preflight-item:x",FLOWS[0],SCENARIOS[0],COMMON_OPERATIONS,COMMON_TOKEN_CLASSES)
    def test_item_common_capability_only(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected):s.add_review_item("synthetic:preflight-item:x",FLOWS[0],SCENARIOS[0],("EXECUTE",),COMMON_TOKEN_CLASSES)
    def test_item_partial_common_capability_rejected(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected):s.add_review_item("synthetic:preflight-item:x",FLOWS[0],SCENARIOS[0],COMMON_OPERATIONS[:-1],COMMON_TOKEN_CLASSES)
    def test_control_slot_swap_rehash_tamper(self):
        s=populated(); s._controls[5101],s._controls[5102]=s._controls[5102],s._controls[5101]
        self.assertFalse(s.evidence()["integrity_valid"])
    def test_exact_24_items(self): self.assertEqual(len(reviewed()[0]._items),24)
    def test_partial_batches_hold(self): self.assertEqual(reviewed()[0].evidence()["hold_count"],4)
    def test_finalize_requires_complete(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected):s.finalize("synthetic:preflight-packet:x","synthetic:preflight-reviewer:c")
    def test_role_separation(self):
        s,_=reviewed()
        with self.assertRaises(GovernanceRejected):s.finalize("synthetic:preflight-packet:x","synthetic:preflight-reviewer:maker")
    def test_safe_packet(self):
        r=completed()[2]; self.assertTrue(r.review_complete); self.assertFalse(r.approval_recorded);self.assertFalse(r.activation_recorded);self.assertFalse(r.deployment_recorded)
    def test_anchor_source_rehash_tamper(self):
        s,a=anchored();s._anchor=rehash(a,readiness_receipt_digest=d("other"));self.assertFalse(s.evidence()["integrity_valid"])
    def test_anchor_lessons_rehash_tamper(self):
        s,a=anchored();s._anchor=rehash(a,applied_lesson_ids=APPLIED_LESSONS[:-1]);self.assertFalse(s.evidence()["integrity_valid"])
    def test_anchor_rules_rehash_tamper(self):
        s,a=anchored();s._anchor=rehash(a,applied_rule_ids=APPLIED_RULES[:-1]);self.assertFalse(s.evidence()["integrity_valid"])
    def test_anchor_capability_profile_rehash_tamper(self):
        s,a=anchored();specs=((PARTIES[0],COMMON_OPERATIONS),(PARTIES[1],COMMON_OPERATIONS),(PARTIES[2],("MAP",)));s._anchor=rehash(a,capability_operations=specs);self.assertFalse(s.evidence()["integrity_valid"])
    def test_anchor_party_profile_binding_rehash_tamper(self):
        s,a=anchored(); profiles=((PARTIES[0],a.capability_profile_digests[1][1]),(PARTIES[1],a.capability_profile_digests[0][1]),a.capability_profile_digests[2])
        s._anchor=rehash(a,capability_profile_digests=profiles); self.assertFalse(s.evidence()["integrity_valid"])
    def test_item_route_rehash_tamper(self):
        s,_=reviewed();k=next(iter(s._items));s._items[k]=rehash(s._items[k],route_digest=d("forged"));self.assertFalse(s.evidence()["integrity_valid"])
    def test_item_capability_rehash_tamper(self):
        s,_=reviewed();k=next(iter(s._items));s._items[k]=rehash(s._items[k],capability_digest=d("forged"));self.assertFalse(s.evidence()["integrity_valid"])
    def test_item_namespace_rehash_tamper(self):
        s,_=reviewed();k=next(iter(s._items));s._items[k]=rehash(s._items[k],item_id="real:item");self.assertFalse(s.evidence()["integrity_valid"])
    def test_packet_approval_rehash_tamper(self):
        s,_,r=completed();s._packet=rehash(r,approval_recorded=True);self.assertFalse(s.evidence()["integrity_valid"])
    def test_packet_status_rehash_tamper(self):
        s,_,r=completed();s._packet=rehash(r,status="APPROVED");self.assertFalse(s.evidence()["integrity_valid"])
    def test_packet_source_reviewer_rehash_tamper(self):
        s,_,r=completed();s._packet=rehash(r,source_reviewer="synthetic:readiness-reviewer:other");self.assertFalse(s.evidence()["integrity_valid"])
    def test_event_artifact_rehash_tamper(self):
        s,_=anchored();x=s._events[0]|{"artifact_digest":d("fake")};x["digest"]=canonical_digest({k:v for k,v in x.items() if k!="digest"});s._events[0]=x;self.assertFalse(s.evidence()["integrity_valid"])
    def test_hold_attachment_rehash_tamper(self):
        s,_=reviewed();x=s._holds[0]|{"attachment_digest":d("fake")};x["digest"]=canonical_digest({k:v for k,v in x.items() if k!="digest"});s._holds[0]=x;self.assertFalse(s.evidence()["integrity_valid"])
    def test_missing_hold_fails_closed(self):
        s,_=reviewed();s._holds.pop();self.assertFalse(s.evidence()["integrity_valid"])
    def test_concurrent_control_converges(self):
        s=SyntheticOperatorReviewPreflightDocket();args=(5101,WORKSTREAM_NAMES[0],CONTROL_ASPECTS[0],"synthetic:preflight-requirement:00",d("x"),"PASS")
        with ThreadPoolExecutor(max_workers=8) as p:rows=list(p.map(lambda _:s.add_control(*args),range(20)))
        self.assertEqual(len({x.digest for x in rows}),1)
    def test_complete_evidence(self):
        e=completed()[0].evidence();self.assertTrue(e["complete_preflight_evidence"]);self.assertEqual(e["review_item_count"],24);self.assertEqual(e["applied_lesson_ids"],list(APPLIED_LESSONS))
    def test_non_execution(self):
        e=completed()[0].evidence();keys=("external_calls","document_transmissions","electronic_signatures","external_pg_calls","card_network_calls","payment_approvals","cancellations","refunds","settlements","transfers","ledger_writes","credential_reads","deployments","policy_prompt_weight_changes");self.assertEqual(tuple(e[k] for k in keys),(0,)*len(keys));self.assertFalse(e["approval_recorded"]);self.assertFalse(e["activation_recorded"])

if __name__=="__main__":unittest.main()
