import hashlib
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.synthetic_answer_material_intake_validation import *

def d(v): return hashlib.sha256(v.encode()).hexdigest()
def rehash(r, **changes):
    x = replace(r, **changes); p = {k:v for k,v in x.__dict__.items() if k != "digest"}; return replace(x, digest=canonical_digest(p))
def populated():
    s = SyntheticAnswerMaterialIntakeValidation()
    for cid in range(7501, 7901):
        ws,a = s._expected(cid); s.add_control(cid, ws, a, f"synthetic:answer-intake-requirement:{(cid-7501)//25:02}", d(str(cid)), "EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    return s
def anchored():
    s = populated(); docs = tuple((p,d(p)) for p in PARTIES); docket=d("question-docket"); qset=d("question-set")
    routes = tuple((f,canonical_digest(("ANSWER_INTAKE_ROUTE",f,FLOW_PARTIES[f],docs,docket,qset))) for f in FLOWS)
    reviewers=("synthetic:readiness-reviewer:r1","synthetic:preflight-reviewer:r2","synthetic:reconsideration-reviewer:r3")
    compilers=("synthetic:packet-compiler:c1","synthetic:packet-compiler:c2","synthetic:packet-compiler:c3")
    a=s.anchor_source("synthetic:answer-intake-anchor:a",docket,qset,d("registry"),d("manifest"),APPLIED_LESSONS,APPLIED_RULES,docs,routes,15,True,reviewers,compilers,"synthetic:human-deliberation-chair:chair")
    return s,a
def answer_args(a, flow, kind):
    source,counter=FLOW_PARTIES[flow]; route=dict(a.route_binding_digests)[flow]
    q=canonical_digest(("SOURCE_QUESTION",a.question_set_digest,flow,kind,source,counter,route)); doc=dict(a.party_document_digests)[source]
    claim=canonical_digest(("SYNTHETIC_SEMANTIC_CLAIM",q,source,counter,doc,route)); manifest=canonical_digest(("SYNTHETIC_MATERIAL_MANIFEST",q,source,counter,claim,route,1))
    answer=canonical_digest(("SYNTHETIC_ANSWER_DOCUMENT",q,source,counter,1,claim,manifest)); receipt=canonical_digest(("SYNTHETIC_SOURCE_RECEIPT",source,flow,kind,answer,manifest,1,None))
    return (f"synthetic:answer-material:{flow}:{kind}",flow,kind,q,answer,manifest,receipt,1,None,claim,f"synthetic:answer-submitter:{source}",f"synthetic:intake-reviewer:{counter}")
def answered():
    s,a=anchored()
    for f in FLOWS:
        for k in ANSWER_KINDS:s.add_answer_material(*answer_args(a,f,k))
    return s,a
def completed():
    s,a=answered(); return s,a,s.finalize("synthetic:answer-intake-packet:a","synthetic:intake-validator:validator")

class TestAnswerMaterialIntakeValidation(unittest.TestCase):
    def test_matrix(self): self.assertEqual((WORKSTREAMS[0][0],WORKSTREAMS[-1][1],len(WORKSTREAMS)),(7501,7900,16)); self.assertTrue(all(b-a+1==25 for a,b,_ in WORKSTREAMS))
    def test_exact_controls(self): self.assertEqual(set(populated()._controls),set(range(7501,7901)))
    def test_wrong_control_mapping(self):
        with self.assertRaises(GovernanceRejected): SyntheticAnswerMaterialIntakeValidation().add_control(7501,"WRONG",CONTROL_ASPECTS[0],"synthetic:answer-intake-requirement:00",d("x"),"PASS")
    def test_control_idempotency_and_conflict(self):
        s=SyntheticAnswerMaterialIntakeValidation(); args=(7501,WORKSTREAM_NAMES[0],CONTROL_ASPECTS[0],"synthetic:answer-intake-requirement:00",d("x"),"PASS"); x=s.add_control(*args); self.assertIs(x,s.add_control(*args))
        with self.assertRaises(GovernanceRejected): s.add_control(*args[:-2],d("y"),"PASS")
    def test_control_slot_swap(self):
        s=populated(); s._controls[7501],s._controls[7502]=s._controls[7502],s._controls[7501]; self.assertFalse(s.evidence()["integrity_valid"])
    def test_anchor_requires_controls(self):
        with self.assertRaises(GovernanceRejected): SyntheticAnswerMaterialIntakeValidation().anchor_source("synthetic:answer-intake-anchor:a",d("d"),d("q"),d("r"),d("m"),APPLIED_LESSONS,APPLIED_RULES,(),(),1,True,(),(),"x")
    def test_anchor_latest(self):
        s,a=anchored(); s._anchor=None
        with self.assertRaises(GovernanceRejected): s.anchor_source(a.anchor_id,a.question_docket_digest,a.question_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest,a.applied_lesson_ids,a.applied_rule_ids,a.party_document_digests,a.route_binding_digests,a.source_sequence,False,a.source_reviewers,a.source_compilers,a.source_chair)
    def test_lessons_exact(self):
        s,a=anchored(); s._anchor=None
        with self.assertRaises(GovernanceRejected): s.anchor_source(a.anchor_id,a.question_docket_digest,a.question_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest,a.applied_lesson_ids[:-1],a.applied_rule_ids,a.party_document_digests,a.route_binding_digests,a.source_sequence,True,a.source_reviewers,a.source_compilers,a.source_chair)
    def test_anchor_idempotent(self):
        s,a=anchored(); self.assertIs(a,s.anchor_source(a.anchor_id,a.question_docket_digest,a.question_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest,a.applied_lesson_ids,a.applied_rule_ids,a.party_document_digests,a.route_binding_digests,a.source_sequence,a.is_latest,a.source_reviewers,a.source_compilers,a.source_chair))
    def test_source_role_collision(self):
        s,a=anchored(); s._anchor=None; c=(a.source_compilers[0],a.source_compilers[1],"synthetic:packet-compiler:r1")
        with self.assertRaises(GovernanceRejected): s.anchor_source(a.anchor_id,a.question_docket_digest,a.question_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest,a.applied_lesson_ids,a.applied_rule_ids,a.party_document_digests,a.route_binding_digests,a.source_sequence,True,a.source_reviewers,c,a.source_chair)
    def test_route_binding_tamper(self):
        s,a=anchored(); s._anchor=rehash(a,route_binding_digests=tuple((f,d(f)) for f in FLOWS)); self.assertFalse(s.evidence()["integrity_valid"])
    def test_source_chair_tamper_rehashed(self):
        s,a=anchored(); s._anchor=rehash(a,source_chair="synthetic:human-deliberation-chair:substitute"); self.assertFalse(s.evidence()["integrity_valid"])
    def test_source_reviewer_tamper_rehashed(self):
        s,a=anchored(); s._anchor=rehash(a,source_reviewers=(a.source_reviewers[0],a.source_reviewers[1],"synthetic:reconsideration-reviewer:x")); self.assertFalse(s.evidence()["integrity_valid"])
    def test_question_set_tamper_rehashed(self):
        s,a=anchored(); s._anchor=rehash(a,question_set_digest=d("other")); self.assertFalse(s.evidence()["integrity_valid"])
    def test_answer_requires_anchor(self):
        with self.assertRaises(GovernanceRejected): SyntheticAnswerMaterialIntakeValidation().add_answer_material("synthetic:answer-material:x",FLOWS[0],ANSWER_KINDS[0],*[d(str(i)) for i in range(5)],1,None,d("c"),"synthetic:answer-submitter:x","synthetic:intake-reviewer:y")
    def test_exact_twenty_answers_holds(self): self.assertEqual((len(answered()[0]._answers),len(answered()[0]._holds)),(20,20))
    def test_answer_idempotency_conflict(self):
        s,a=anchored(); args=answer_args(a,FLOWS[0],ANSWER_KINDS[0]); x=s.add_answer_material(*args); self.assertIs(x,s.add_answer_material(*args))
        bad=list(args); bad[9]=d("bad")
        with self.assertRaises(GovernanceRejected): s.add_answer_material(*bad)
    def test_partial_material_rejected(self):
        s,a=anchored()
        with self.assertRaises(GovernanceRejected): s.add_answer_material(*answer_args(a,FLOWS[0],ANSWER_KINDS[0]),complete=False)
    def test_semantic_conflict_rejected(self):
        s,a=anchored()
        with self.assertRaises(GovernanceRejected): s.add_answer_material(*answer_args(a,FLOWS[0],ANSWER_KINDS[0]),conflict_free=False)
    def test_stale_version_rejected(self):
        s,a=anchored(); args=list(answer_args(a,FLOWS[0],ANSWER_KINDS[0])); args[7]=2
        with self.assertRaises(GovernanceRejected): s.add_answer_material(*args)
    def test_previous_version_injection_rejected(self):
        s,a=anchored(); args=list(answer_args(a,FLOWS[0],ANSWER_KINDS[0])); args[8]=d("previous")
        with self.assertRaises(GovernanceRejected): s.add_answer_material(*args)
    def _tamper(self, field, value):
        s,_=answered(); k=next(iter(s._answers)); s._answers[k]=rehash(s._answers[k],**{field:value}); self.assertFalse(s.evidence()["integrity_valid"])
    def test_question_digest_tamper(self): self._tamper("question_digest",d("bad"))
    def test_answer_document_tamper(self): self._tamper("answer_document_digest",d("bad"))
    def test_manifest_tamper(self): self._tamper("material_manifest_digest",d("bad"))
    def test_receipt_tamper(self): self._tamper("source_receipt_digest",d("bad"))
    def test_claim_tamper(self): self._tamper("semantic_claim_digest",d("bad"))
    def test_claim_manifest_answer_receipt_chain_rehash_tamper(self):
        s,_=answered(); key=next(iter(s._answers)); row=s._answers[key]; claim=d("substitute-claim")
        manifest=canonical_digest(("SYNTHETIC_MATERIAL_MANIFEST",row.question_digest,row.source_party,row.counterparty,claim,row.route_binding_digest,row.document_version))
        answer=canonical_digest(("SYNTHETIC_ANSWER_DOCUMENT",row.question_digest,row.source_party,row.counterparty,row.document_version,claim,manifest))
        receipt=canonical_digest(("SYNTHETIC_SOURCE_RECEIPT",row.source_party,row.flow,row.kind,answer,manifest,row.document_version,row.previous_version_digest))
        s._answers[key]=rehash(row,semantic_claim_digest=claim,material_manifest_digest=manifest,answer_document_digest=answer,source_receipt_digest=receipt)
        self.assertFalse(s.evidence()["integrity_valid"])
    def test_submitter_tamper(self): self._tamper("submitter","synthetic:answer-submitter:wrong")
    def test_reviewer_tamper(self): self._tamper("intake_reviewer","synthetic:intake-reviewer:wrong")
    def test_status_tamper(self): self._tamper("status","ACCEPTED")
    def test_answer_key_swap(self):
        s,_=answered(); keys=list(s._answers)[:2]; s._answers[keys[0]],s._answers[keys[1]]=s._answers[keys[1]],s._answers[keys[0]]; self.assertFalse(s.evidence()["integrity_valid"])
    def test_finalize_requires_complete(self):
        with self.assertRaises(GovernanceRejected): anchored()[0].finalize("synthetic:answer-intake-packet:a","synthetic:intake-validator:v")
    def test_validator_role_separation(self):
        s,_=answered()
        with self.assertRaises(GovernanceRejected): s.finalize("synthetic:answer-intake-packet:a","synthetic:intake-validator:chair")
    def test_safe_packet(self):
        r=completed()[2]; self.assertTrue(r.complete); self.assertFalse(any((r.accepted,r.transmitted,r.signed,r.recommended,r.decided,r.approved,r.activated,r.deployed)))
    def test_packet_decision_tamper(self):
        s,_,r=completed(); s._packet=rehash(r,decided=True); self.assertFalse(s.evidence()["integrity_valid"])
    def test_packet_lineage_tamper(self):
        s,_,r=completed(); s._packet=rehash(r,source_lineage_digest=d("bad")); self.assertFalse(s.evidence()["integrity_valid"])
    def test_missing_answer_fail_closed(self):
        s,_=answered(); s._answers.pop(next(iter(s._answers))); self.assertFalse(s.evidence()["integrity_valid"])
    def test_missing_hold_fail_closed(self):
        s,_=answered(); s._holds.pop(); self.assertFalse(s.evidence()["integrity_valid"])
    def test_event_tamper_rehashed(self):
        s,_=anchored(); x=s._events[0]|{"artifact_digest":d("bad")}; x["digest"]=canonical_digest({k:v for k,v in x.items() if k!="digest"}); s._events[0]=x; self.assertFalse(s.evidence()["integrity_valid"])
    def test_concurrent_control_idempotency(self):
        s=SyntheticAnswerMaterialIntakeValidation(); args=(7501,WORKSTREAM_NAMES[0],CONTROL_ASPECTS[0],"synthetic:answer-intake-requirement:00",d("x"),"PASS")
        with ThreadPoolExecutor(max_workers=8) as p: rows=list(p.map(lambda _:s.add_control(*args),range(20)))
        self.assertEqual(len({x.digest for x in rows}),1)
    def test_complete_evidence(self):
        e=completed()[0].evidence(); self.assertTrue(e["complete_answer_material_validation_evidence"]); self.assertEqual((e["answer_material_count"],e["hold_count"]),(20,20))
    def test_non_execution(self):
        e=completed()[0].evidence(); keys=("external_calls","external_answer_receipts","document_transmissions","electronic_signatures","external_pg_calls","card_network_calls","payment_approvals","cancellations","refunds","settlements","transfers","ledger_writes","credential_reads","deployments","policy_prompt_weight_changes")
        self.assertEqual(tuple(e[k] for k in keys),(0,)*len(keys)); self.assertFalse(any(e[k] for k in ("accepted","recommended","decided","approved","activated")))

if __name__ == "__main__": unittest.main()
