import hashlib
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.synthetic_reconciliation_submission_lineage import *

def d(value): return hashlib.sha256(value.encode()).hexdigest()
def rehash(row, **changes):
    value = replace(row, **changes); payload = {k:v for k,v in value.__dict__.items() if k != "digest"}
    if "source_cases" in payload: payload["source_cases"] = tuple(tuple(x.__dict__.values()) for x in payload["source_cases"])
    return replace(value, digest=canonical_digest(payload))
def source_cases():
    rows=[]
    for flow in FLOWS:
        for index,kind in enumerate(ANSWER_KINDS):
            common=(d(f"claim:{flow}:{kind}"),d(f"manifest:{flow}:{kind}"),d(f"receipt:{flow}:{kind}"))
            source_claim,source_manifest,source_receipt=common; counter_claim,counter_manifest,counter_receipt=common
            source_version=counter_version=1
            if index==1: counter_claim=d(f"counter-claim:{flow}:{kind}")
            if index==2: counter_manifest=d(f"counter-manifest:{flow}:{kind}")
            if index==3: counter_receipt=d(f"counter-receipt:{flow}:{kind}")
            if index==4: counter_version=2
            source_binding=d(f"source:{flow}:{kind}"); counter_binding=d(f"counter:{flow}:{kind}"); outcome=COMPARISON_OUTCOMES[index]
            comparison=canonical_digest(("SOURCE_RECONCILIATION_COMPARISON",flow,kind,outcome,source_binding,counter_binding)); route=canonical_digest(("SOURCE_HUMAN_RECONCILIATION_QUEUE",flow,kind,outcome,comparison,*FLOW_PARTIES[flow]))
            vals=(source_binding,counter_binding,source_claim,counter_claim,source_manifest,counter_manifest,source_receipt,counter_receipt,source_version,counter_version,comparison,route)
            case=canonical_digest(("SOURCE_RECONCILIATION_CASE",flow,kind,outcome,*vals)); rows.append(SourceCase(flow,kind,outcome,*vals,case))
    return tuple(rows)
def populated():
    service=SyntheticReconciliationSubmissionLineage()
    for cid in range(8301,8701):
        ws,aspect=service._expected(cid); service.add_control(cid,ws,aspect,f"synthetic:submission-lineage-requirement:{(cid-8301)//25:02}",d(str(cid)),"EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS")
    return service
def anchored():
    service=populated(); reviewers=("synthetic:readiness-reviewer:r1","synthetic:preflight-reviewer:r2","synthetic:reconsideration-reviewer:r3"); compilers=tuple(f"synthetic:packet-compiler:c{i}" for i in range(1,5))
    cases=source_cases(); case_set=canonical_digest(tuple(x.case_digest for x in cases))
    anchor=service.anchor_queue("synthetic:submission-lineage-anchor:a",d("queue"),case_set,d("registry"),d("manifest"),APPLIED_LESSONS,APPLIED_RULES,cases,17,True,reviewers,compilers,"synthetic:human-deliberation-chair:chair","synthetic:cross-party-validator:cross")
    return service,anchor
def submission_args(flow,kind,submission_kind):
    party=expected_author(flow,submission_kind)
    return (f"synthetic:reconciliation-submission:{flow}:{kind}:{submission_kind}",flow,kind,submission_kind,party,f"synthetic:submission-author:{party}","synthetic:submission-lineage-validator:lineage")
def submitted():
    service,anchor=anchored()
    for flow in FLOWS:
        for kind in ANSWER_KINDS:
            for submission_kind in SUBMISSION_KINDS: service.add_submission(*submission_args(flow,kind,submission_kind))
    return service,anchor
def bundled():
    service,anchor=submitted()
    for flow in FLOWS:
        for kind in ANSWER_KINDS: service.build_bundle(f"synthetic:submission-bundle:{flow}:{kind}",flow,kind,"synthetic:submission-bundle-compiler:bundle")
    return service,anchor
def completed():
    service,anchor=bundled(); return service,anchor,service.finalize("synthetic:submission-hold-docket:a","synthetic:submission-docket-compiler:docket")

class TestSyntheticReconciliationSubmissionLineage(unittest.TestCase):
    def test_matrix(self): self.assertEqual((WORKSTREAMS[0][0],WORKSTREAMS[-1][1],len(WORKSTREAMS)),(8301,8700,16)); self.assertTrue(all(end-start+1==25 for start,end,_ in WORKSTREAMS))
    def test_exact_controls(self): self.assertEqual(set(populated()._controls),set(range(8301,8701)))
    def test_wrong_control(self):
        with self.assertRaises(GovernanceRejected): SyntheticReconciliationSubmissionLineage().add_control(8301,"WRONG",CONTROL_ASPECTS[0],"synthetic:submission-lineage-requirement:00",d("x"),"PASS")
    def test_control_idempotency_conflict(self):
        s=SyntheticReconciliationSubmissionLineage(); args=(8301,WORKSTREAM_NAMES[0],CONTROL_ASPECTS[0],"synthetic:submission-lineage-requirement:00",d("x"),"PASS"); row=s.add_control(*args); self.assertIs(row,s.add_control(*args))
        with self.assertRaises(GovernanceRejected): s.add_control(*args[:-2],d("y"),"PASS")
    def test_control_slot_swap(self):
        s=populated(); s._controls[8301],s._controls[8302]=s._controls[8302],s._controls[8301]; self.assertFalse(s.evidence()["integrity_valid"])
    def test_anchor_requires_controls(self):
        with self.assertRaises(GovernanceRejected): SyntheticReconciliationSubmissionLineage().anchor_queue("synthetic:submission-lineage-anchor:a",d("q"),d("c"),d("r"),d("m"),APPLIED_LESSONS,APPLIED_RULES,(),1,True,(),(),"x","y")
    def test_anchor_latest(self):
        s,a=anchored(); s._anchor=None
        with self.assertRaises(GovernanceRejected): s.anchor_queue(a.anchor_id,a.queue_packet_digest,a.case_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest,a.applied_lesson_ids,a.applied_rule_ids,a.source_cases,a.source_sequence,False,a.source_reviewers,a.source_compilers,a.source_chair,a.source_validator)
    def test_lessons_exact(self):
        s,a=anchored(); s._anchor=None
        with self.assertRaises(GovernanceRejected): s.anchor_queue(a.anchor_id,a.queue_packet_digest,a.case_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest,a.applied_lesson_ids[:-1],a.applied_rule_ids,a.source_cases,a.source_sequence,True,a.source_reviewers,a.source_compilers,a.source_chair,a.source_validator)
    def test_anchor_idempotency(self):
        s,a=anchored(); self.assertIs(a,s.anchor_queue(a.anchor_id,a.queue_packet_digest,a.case_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest,a.applied_lesson_ids,a.applied_rule_ids,a.source_cases,a.source_sequence,a.is_latest,a.source_reviewers,a.source_compilers,a.source_chair,a.source_validator))
    def test_source_case_order_tamper(self):
        s,a=anchored(); rows=list(a.source_cases); rows[0],rows[1]=rows[1],rows[0]; s._anchor=rehash(a,source_cases=tuple(rows)); self.assertFalse(s.evidence()["integrity_valid"])
    def test_source_case_semantic_rehash_tamper(self):
        s,a=anchored(); rows=list(a.source_cases); row=rows[0]
        payload=("SOURCE_RECONCILIATION_CASE",row.flow,row.answer_kind,"VERSION_CONFLICT",row.source_binding_digest,row.counterpart_binding_digest,row.source_claim_digest,row.counterpart_claim_digest,row.source_manifest_digest,row.counterpart_manifest_digest,row.source_receipt_digest,row.counterpart_receipt_digest,row.source_version,row.counterpart_version,row.comparison_digest,row.queue_route_digest)
        rows[0]=replace(row,comparison_outcome="VERSION_CONFLICT",case_digest=canonical_digest(payload)); s._anchor=rehash(a,source_cases=tuple(rows)); self.assertFalse(s.evidence()["integrity_valid"])
    def test_source_case_inner_digest_tamper(self):
        s,a=anchored(); rows=list(a.source_cases); rows[0]=replace(rows[0],case_digest=d("bad")); s._anchor=rehash(a,source_cases=tuple(rows)); self.assertFalse(s.evidence()["integrity_valid"])
    def test_case_set_full_rehash_substitution(self):
        s,a=anchored(); rows=list(a.source_cases); row=rows[0]; binding=d("substituted-binding")
        comparison=canonical_digest(("SOURCE_RECONCILIATION_COMPARISON",row.flow,row.answer_kind,row.comparison_outcome,binding,row.counterpart_binding_digest)); route=canonical_digest(("SOURCE_HUMAN_RECONCILIATION_QUEUE",row.flow,row.answer_kind,row.comparison_outcome,comparison,*FLOW_PARTIES[row.flow]))
        payload=("SOURCE_RECONCILIATION_CASE",row.flow,row.answer_kind,row.comparison_outcome,binding,row.counterpart_binding_digest,row.source_claim_digest,row.counterpart_claim_digest,row.source_manifest_digest,row.counterpart_manifest_digest,row.source_receipt_digest,row.counterpart_receipt_digest,row.source_version,row.counterpart_version,comparison,route)
        rows[0]=replace(row,source_binding_digest=binding,comparison_digest=comparison,queue_route_digest=route,case_digest=canonical_digest(payload)); s._anchor=rehash(a,source_cases=tuple(rows)); self.assertFalse(s.evidence()["integrity_valid"])
    def test_source_route_full_rehash_tamper(self):
        s,a=anchored(); rows=list(a.source_cases); row=rows[0]; fake=d("fake-route")
        payload=("SOURCE_RECONCILIATION_CASE",row.flow,row.answer_kind,row.comparison_outcome,row.source_binding_digest,row.counterpart_binding_digest,row.source_claim_digest,row.counterpart_claim_digest,row.source_manifest_digest,row.counterpart_manifest_digest,row.source_receipt_digest,row.counterpart_receipt_digest,row.source_version,row.counterpart_version,row.comparison_digest,fake)
        rows[0]=replace(row,queue_route_digest=fake,case_digest=canonical_digest(payload)); s._anchor=rehash(a,source_cases=tuple(rows)); self.assertFalse(s.evidence()["integrity_valid"])
    def test_source_role_collision(self):
        s,a=anchored(); s._anchor=None
        with self.assertRaises(GovernanceRejected): s.anchor_queue(a.anchor_id,a.queue_packet_digest,a.case_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest,a.applied_lesson_ids,a.applied_rule_ids,a.source_cases,a.source_sequence,True,a.source_reviewers,a.source_compilers,a.source_chair,"synthetic:cross-party-validator:chair")
    def test_submission_requires_anchor(self):
        with self.assertRaises(GovernanceRejected): SyntheticReconciliationSubmissionLineage().add_submission(*submission_args(FLOWS[0],ANSWER_KINDS[0],SUBMISSION_KINDS[0]))
    def test_counterargument_requires_proposal(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected): s.add_submission(*submission_args(FLOWS[0],ANSWER_KINDS[0],SUBMISSION_KINDS[1]))
    def test_evidence_requires_immediate_counterargument(self):
        s,_=anchored(); s.add_submission(*submission_args(FLOWS[0],ANSWER_KINDS[0],SUBMISSION_KINDS[0]))
        with self.assertRaises(GovernanceRejected): s.add_submission(*submission_args(FLOWS[0],ANSWER_KINDS[0],SUBMISSION_KINDS[2]))
    def test_actual_author_is_derived_from_flow_and_kind(self):
        self.assertEqual(expected_author("tenant_to_nurion","NONBINDING_PROPOSAL"),"TENANT_AGENCY"); self.assertEqual(expected_author("tenant_to_nurion","NONBINDING_COUNTERARGUMENT"),"NURION_PG")
    def test_wrong_author_rejected(self):
        s,_=anchored(); args=list(submission_args(FLOWS[0],ANSWER_KINDS[0],SUBMISSION_KINDS[0])); args[4]="NURION_PG"
        with self.assertRaises(GovernanceRejected): s.add_submission(*args)
    def test_exact_sixty_submissions(self): self.assertEqual(len(submitted()[0]._submissions),60)
    def test_submission_idempotency_conflict(self):
        s,_=anchored(); args=submission_args(FLOWS[0],ANSWER_KINDS[0],SUBMISSION_KINDS[0]); row=s.add_submission(*args); self.assertIs(row,s.add_submission(*args))
        with self.assertRaises(GovernanceRejected): s.add_submission(args[0]+":other",*args[1:])
    def test_submission_content_rehash_tamper(self):
        s,_=submitted(); key=next(iter(s._submissions)); s._submissions[key]=rehash(s._submissions[key],content_digest=d("forged")); self.assertFalse(s.evidence()["integrity_valid"])
    def test_submission_author_rehash_tamper(self):
        s,_=submitted(); key=next(iter(s._submissions)); s._submissions[key]=rehash(s._submissions[key],author_party="UPSTREAM_PG"); self.assertFalse(s.evidence()["integrity_valid"])
    def test_parent_lineage_rehash_tamper(self):
        s,_=submitted(); key=(FLOWS[0],ANSWER_KINDS[0],SUBMISSION_KINDS[1]); s._submissions[key]=rehash(s._submissions[key],parent_submission_digest=d("other")); self.assertFalse(s.evidence()["integrity_valid"])
    def test_author_validator_role_collision(self):
        s,_=anchored(); args=list(submission_args(FLOWS[0],ANSWER_KINDS[0],SUBMISSION_KINDS[0])); args[-1]="synthetic:submission-lineage-validator:chair"
        with self.assertRaises(GovernanceRejected): s.add_submission(*args)
    def test_bundle_requires_all_three(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected): s.build_bundle("synthetic:submission-bundle:a",FLOWS[0],ANSWER_KINDS[0],"synthetic:submission-bundle-compiler:b")
    def test_exact_twenty_bundles_holds(self): self.assertEqual((len(bundled()[0]._bundles),len(bundled()[0]._holds)),(20,20))
    def _bundle_tamper(self,field,value):
        s,_=bundled(); key=next(iter(s._bundles)); s._bundles[key]=rehash(s._bundles[key],**{field:value}); self.assertFalse(s.evidence()["integrity_valid"])
    def test_bundle_source_tamper(self): self._bundle_tamper("source_case_digest",d("bad"))
    def test_bundle_document_tamper(self): self._bundle_tamper("counterargument_digest",d("bad"))
    def test_hold_route_rehash_tamper(self): self._bundle_tamper("hold_route_digest",d("bad"))
    def test_bundle_acceptance_rehash_tamper(self): self._bundle_tamper("accepted",True)
    def test_bundle_compiler_collision(self):
        s,_=submitted()
        with self.assertRaises(GovernanceRejected): s.build_bundle("synthetic:submission-bundle:a",FLOWS[0],ANSWER_KINDS[0],"synthetic:submission-bundle-compiler:lineage")
    def test_finalize_requires_complete(self):
        with self.assertRaises(GovernanceRejected): anchored()[0].finalize("synthetic:submission-hold-docket:a","synthetic:submission-docket-compiler:d")
    def test_safe_docket(self):
        row=completed()[2]; self.assertTrue(row.complete); self.assertFalse(any((row.accepted,row.recommended,row.decided,row.approved,row.activated,row.deployed)))
    def test_docket_decision_tamper(self):
        s,_,row=completed(); s._docket=rehash(row,decided=True); self.assertFalse(s.evidence()["integrity_valid"])
    def test_docket_lineage_tamper(self):
        s,_,row=completed(); s._docket=rehash(row,source_lineage_digest=d("bad")); self.assertFalse(s.evidence()["integrity_valid"])
    def test_missing_bundle_fails_closed(self):
        s,_=bundled(); s._bundles.pop(next(iter(s._bundles))); self.assertFalse(s.evidence()["integrity_valid"])
    def test_missing_hold_fails_closed(self):
        s,_=bundled(); s._holds.pop(); self.assertFalse(s.evidence()["integrity_valid"])
    def test_event_rehash_tamper(self):
        s,_=anchored(); row=s._events[0]|{"artifact_digest":d("bad")}; row["digest"]=canonical_digest({k:v for k,v in row.items() if k!="digest"}); s._events[0]=row; self.assertFalse(s.evidence()["integrity_valid"])
    def test_concurrent_control_idempotency(self):
        s=SyntheticReconciliationSubmissionLineage(); args=(8301,WORKSTREAM_NAMES[0],CONTROL_ASPECTS[0],"synthetic:submission-lineage-requirement:00",d("x"),"PASS")
        with ThreadPoolExecutor(max_workers=8) as pool: rows=list(pool.map(lambda _:s.add_control(*args),range(20)))
        self.assertEqual(len({x.digest for x in rows}),1)
    def test_complete_evidence(self):
        evidence=completed()[0].evidence(); self.assertTrue(evidence["complete_submission_hold_evidence"]); self.assertEqual((evidence["submission_count"],evidence["bundle_count"],evidence["hold_count"]),(60,20,20))
    def test_non_execution(self):
        evidence=completed()[0].evidence(); keys=("external_calls","document_transmissions","electronic_signatures","external_pg_calls","card_network_calls","payment_approvals","cancellations","refunds","settlements","transfers","ledger_writes","credential_reads","deployments","policy_prompt_weight_changes")
        self.assertEqual(tuple(evidence[k] for k in keys),(0,)*len(keys)); self.assertFalse(any(evidence[k] for k in ("accepted","recommended","decided","approved","activated")))

if __name__ == "__main__": unittest.main()
