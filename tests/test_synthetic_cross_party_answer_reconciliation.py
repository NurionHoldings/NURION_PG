import hashlib
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.synthetic_cross_party_answer_reconciliation import *

def d(v): return hashlib.sha256(v.encode()).hexdigest()
def rehash(r,**changes):
    x=replace(r,**changes); p={k:v for k,v in x.__dict__.items() if k!="digest"}
    if "answer_provenance" in p: p["answer_provenance"]=tuple(tuple(v.__dict__.values()) for v in p["answer_provenance"])
    return replace(x,digest=canonical_digest(p))
def provenance():
    out=[]
    for f in FLOWS:
        source,counter=FLOW_PARTIES[f]
        for k in ANSWER_KINDS:
            pair="tenant-nurion" if "tenant" in f else "nurion-upstream"
            side="a" if f in ("tenant_to_nurion","nurion_to_upstream") else "b"
            claim=d(f"claim:{pair}:{k}:{side}" if k=="RESIDUAL_RISK_RESPONSE" else f"claim:{pair}:{k}")
            manifest=d(f"manifest:{pair}:{k}:{side}" if k=="ADDITIONAL_EVIDENCE" else f"manifest:{pair}:{k}")
            receipt=d(f"receipt:{pair}:{k}:{side}" if k=="MEANING_CLARIFICATION" else f"receipt:{pair}:{k}")
            version=2 if k=="SAFE_BOUNDARY_ACKNOWLEDGEMENT" and side=="b" else 1
            vals=(d(f"answer:{f}:{k}"),claim,manifest,receipt)
            binding=canonical_digest(("ANSWER_PROVENANCE",f,k,source,counter,*vals,version))
            out.append(AnswerProvenance(f,k,source,counter,*vals,version,binding))
    return tuple(out)
def populated():
    s=SyntheticCrossPartyAnswerReconciliation()
    for cid in range(7901,8301):
        ws,a=s._expected(cid); s.add_control(cid,ws,a,f"synthetic:reconciliation-requirement:{(cid-7901)//25:02}",d(str(cid)),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    return s
def anchored():
    s=populated(); reviewers=("synthetic:readiness-reviewer:r1","synthetic:preflight-reviewer:r2","synthetic:reconsideration-reviewer:r3"); compilers=("synthetic:packet-compiler:c1","synthetic:packet-compiler:c2","synthetic:packet-compiler:c3")
    a=s.anchor_source("synthetic:reconciliation-anchor:a",d("packet"),d("answer-set"),d("registry"),d("manifest"),APPLIED_LESSONS,APPLIED_RULES,provenance(),16,True,reviewers,compilers,"synthetic:human-deliberation-chair:chair","synthetic:intake-validator:intake")
    return s,a
def cargs(f,k): return (f"synthetic:reconciliation-case:{f}:{k}",f,k,f"synthetic:reconciliation-submitter:{FLOW_PARTIES[f][0]}","synthetic:cross-party-validator:cross")
def cased():
    s,a=anchored()
    for f in FLOWS:
        for k in ANSWER_KINDS:s.add_case(*cargs(f,k))
    return s,a
def completed():
    s,a=cased(); return s,a,s.finalize("synthetic:reconciliation-queue-packet:a","synthetic:reconciliation-queue-compiler:queue")

class TestCrossPartyAnswerReconciliation(unittest.TestCase):
    def test_matrix(self): self.assertEqual((WORKSTREAMS[0][0],WORKSTREAMS[-1][1],len(WORKSTREAMS)),(7901,8300,16)); self.assertTrue(all(b-a+1==25 for a,b,_ in WORKSTREAMS))
    def test_exact_controls(self): self.assertEqual(set(populated()._controls),set(range(7901,8301)))
    def test_wrong_control(self):
        with self.assertRaises(GovernanceRejected): SyntheticCrossPartyAnswerReconciliation().add_control(7901,"WRONG",CONTROL_ASPECTS[0],"synthetic:reconciliation-requirement:00",d("x"),"PASS")
    def test_control_idempotency_conflict(self):
        s=SyntheticCrossPartyAnswerReconciliation(); args=(7901,WORKSTREAM_NAMES[0],CONTROL_ASPECTS[0],"synthetic:reconciliation-requirement:00",d("x"),"PASS"); x=s.add_control(*args); self.assertIs(x,s.add_control(*args))
        with self.assertRaises(GovernanceRejected): s.add_control(*args[:-2],d("y"),"PASS")
    def test_control_slot_swap(self):
        s=populated(); s._controls[7901],s._controls[7902]=s._controls[7902],s._controls[7901]; self.assertFalse(s.evidence()["integrity_valid"])
    def test_anchor_requires_controls(self):
        with self.assertRaises(GovernanceRejected): SyntheticCrossPartyAnswerReconciliation().anchor_source("synthetic:reconciliation-anchor:a",d("p"),d("a"),d("r"),d("m"),APPLIED_LESSONS,APPLIED_RULES,(),1,True,(),(),"x","y")
    def test_anchor_latest(self):
        s,a=anchored(); s._anchor=None
        with self.assertRaises(GovernanceRejected): s.anchor_source(a.anchor_id,a.intake_packet_digest,a.answer_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest,a.applied_lesson_ids,a.applied_rule_ids,a.answer_provenance,a.source_sequence,False,a.source_reviewers,a.source_compilers,a.source_chair,a.source_validator)
    def test_lessons_exact(self):
        s,a=anchored(); s._anchor=None
        with self.assertRaises(GovernanceRejected): s.anchor_source(a.anchor_id,a.intake_packet_digest,a.answer_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest,a.applied_lesson_ids[:-1],a.applied_rule_ids,a.answer_provenance,a.source_sequence,True,a.source_reviewers,a.source_compilers,a.source_chair,a.source_validator)
    def test_anchor_idempotent(self):
        s,a=anchored(); self.assertIs(a,s.anchor_source(a.anchor_id,a.intake_packet_digest,a.answer_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest,a.applied_lesson_ids,a.applied_rule_ids,a.answer_provenance,a.source_sequence,a.is_latest,a.source_reviewers,a.source_compilers,a.source_chair,a.source_validator))
    def test_source_role_collision(self):
        s,a=anchored(); s._anchor=None
        with self.assertRaises(GovernanceRejected): s.anchor_source(a.anchor_id,a.intake_packet_digest,a.answer_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest,a.applied_lesson_ids,a.applied_rule_ids,a.answer_provenance,a.source_sequence,True,a.source_reviewers,a.source_compilers,a.source_chair,"synthetic:intake-validator:chair")
    def test_provenance_order_tamper(self):
        s,a=anchored(); rows=list(a.answer_provenance); rows[0],rows[1]=rows[1],rows[0]; s._anchor=rehash(a,answer_provenance=tuple(rows)); self.assertFalse(s.evidence()["integrity_valid"])
    def test_provenance_binding_tamper(self):
        s,a=anchored(); rows=list(a.answer_provenance); rows[0]=replace(rows[0],binding_digest=d("bad")); s._anchor=rehash(a,answer_provenance=tuple(rows)); self.assertFalse(s.evidence()["integrity_valid"])
    def test_source_validator_tamper_rehashed(self):
        s,a=anchored(); s._anchor=rehash(a,source_validator="synthetic:intake-validator:other"); self.assertFalse(s.evidence()["integrity_valid"])
    def test_case_requires_anchor(self):
        with self.assertRaises(GovernanceRejected): SyntheticCrossPartyAnswerReconciliation().add_case(*cargs(FLOWS[0],ANSWER_KINDS[0]))
    def test_exact_twenty_cases_holds(self): self.assertEqual((len(cased()[0]._cases),len(cased()[0]._holds)),(20,20))
    def test_all_conflict_classes_present(self): self.assertEqual({x.comparison_outcome for x in cased()[0]._cases.values()},set(COMPARISON_OUTCOMES))
    def test_outcome_is_derived_from_provenance_not_answer_kind(self):
        rows=provenance(); index={(x.flow,x.answer_kind):x for x in rows}
        expected=dict(zip(ANSWER_KINDS,COMPARISON_OUTCOMES))
        self.assertEqual({k:comparison_outcome(index[(FLOWS[0],k)],index[(COUNTER_FLOW[FLOWS[0]],k)]) for k in ANSWER_KINDS},expected)
    def test_case_idempotency_conflict(self):
        s,_=anchored(); args=cargs(FLOWS[0],ANSWER_KINDS[0]); x=s.add_case(*args); self.assertIs(x,s.add_case(*args))
        with self.assertRaises(GovernanceRejected): s.add_case(args[0]+":other",*args[1:])
    def test_cross_validator_role_collision(self):
        s,_=anchored(); args=list(cargs(FLOWS[0],ANSWER_KINDS[0])); args[-1]="synthetic:cross-party-validator:chair"
        with self.assertRaises(GovernanceRejected): s.add_case(*args)
    def _tamper(self,field,value):
        s,_=cased(); key=next(iter(s._cases)); s._cases[key]=rehash(s._cases[key],**{field:value}); self.assertFalse(s.evidence()["integrity_valid"])
    def test_source_binding_tamper(self): self._tamper("source_binding_digest",d("bad"))
    def test_counterpart_binding_tamper(self): self._tamper("counterpart_binding_digest",d("bad"))
    def test_comparison_tamper(self): self._tamper("comparison_digest",d("bad"))
    def test_route_tamper(self): self._tamper("queue_route_digest",d("bad"))
    def test_status_tamper(self): self._tamper("status","ACCEPTED")
    def test_case_key_swap(self):
        s,_=cased(); keys=list(s._cases)[:2]; s._cases[keys[0]],s._cases[keys[1]]=s._cases[keys[1]],s._cases[keys[0]]; self.assertFalse(s.evidence()["integrity_valid"])
    def test_rehashed_cross_pair_substitution(self):
        s,_=cased(); key=next(iter(s._cases)); row=s._cases[key]; fake=d("substitute"); comp=canonical_digest(("CROSS_PARTY_COMPARISON",row.flow,row.counterpart_flow,row.answer_kind,row.comparison_outcome,fake,fake)); route=canonical_digest(("HUMAN_RECONCILIATION_QUEUE",row.flow,row.counterpart_flow,row.answer_kind,row.comparison_outcome,comp,*FLOW_PARTIES[row.flow])); s._cases[key]=rehash(row,source_binding_digest=fake,counterpart_binding_digest=fake,comparison_digest=comp,queue_route_digest=route); self.assertFalse(s.evidence()["integrity_valid"])
    def test_rehashed_kind_label_cannot_override_actual_outcome(self):
        s,_=cased(); key=(FLOWS[0],ANSWER_KINDS[0]); row=s._cases[key]; outcome="CLAIM_CONFLICT"
        comp=canonical_digest(("CROSS_PARTY_COMPARISON",row.flow,row.counterpart_flow,row.answer_kind,outcome,row.source_binding_digest,row.counterpart_binding_digest)); route=canonical_digest(("HUMAN_RECONCILIATION_QUEUE",row.flow,row.counterpart_flow,row.answer_kind,outcome,comp,*FLOW_PARTIES[row.flow]))
        s._cases[key]=rehash(row,comparison_outcome=outcome,comparison_digest=comp,queue_route_digest=route); self.assertFalse(s.evidence()["integrity_valid"])
    def test_finalize_requires_complete(self):
        with self.assertRaises(GovernanceRejected): anchored()[0].finalize("synthetic:reconciliation-queue-packet:a","synthetic:reconciliation-queue-compiler:q")
    def test_queue_compiler_separation(self):
        s,_=cased()
        with self.assertRaises(GovernanceRejected): s.finalize("synthetic:reconciliation-queue-packet:a","synthetic:reconciliation-queue-compiler:chair")
    def test_safe_packet(self):
        r=completed()[2]; self.assertTrue(r.complete); self.assertFalse(any((r.accepted,r.reconciled,r.recommended,r.decided,r.approved,r.activated,r.deployed)))
    def test_packet_decision_tamper(self):
        s,_,r=completed(); s._packet=rehash(r,decided=True); self.assertFalse(s.evidence()["integrity_valid"])
    def test_packet_lineage_tamper(self):
        s,_,r=completed(); s._packet=rehash(r,source_lineage_digest=d("bad")); self.assertFalse(s.evidence()["integrity_valid"])
    def test_missing_case_fail_closed(self):
        s,_=cased(); s._cases.pop(next(iter(s._cases))); self.assertFalse(s.evidence()["integrity_valid"])
    def test_missing_hold_fail_closed(self):
        s,_=cased(); s._holds.pop(); self.assertFalse(s.evidence()["integrity_valid"])
    def test_event_tamper_rehashed(self):
        s,_=anchored(); x=s._events[0]|{"artifact_digest":d("bad")}; x["digest"]=canonical_digest({k:v for k,v in x.items() if k!="digest"}); s._events[0]=x; self.assertFalse(s.evidence()["integrity_valid"])
    def test_concurrent_control_idempotency(self):
        s=SyntheticCrossPartyAnswerReconciliation(); args=(7901,WORKSTREAM_NAMES[0],CONTROL_ASPECTS[0],"synthetic:reconciliation-requirement:00",d("x"),"PASS")
        with ThreadPoolExecutor(max_workers=8) as p: rows=list(p.map(lambda _:s.add_control(*args),range(20)))
        self.assertEqual(len({x.digest for x in rows}),1)
    def test_complete_evidence(self):
        e=completed()[0].evidence(); self.assertTrue(e["complete_reconciliation_queue_evidence"]); self.assertEqual((e["reconciliation_case_count"],e["hold_count"]),(20,20))
    def test_non_execution(self):
        e=completed()[0].evidence(); keys=("external_calls","external_answer_receipts","document_transmissions","electronic_signatures","external_pg_calls","card_network_calls","payment_approvals","cancellations","refunds","settlements","transfers","ledger_writes","credential_reads","deployments","policy_prompt_weight_changes")
        self.assertEqual(tuple(e[k] for k in keys),(0,)*len(keys)); self.assertFalse(any(e[k] for k in ("accepted","reconciled","recommended","decided","approved","activated")))

if __name__=="__main__": unittest.main()
