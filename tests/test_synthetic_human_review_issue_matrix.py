import hashlib
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.synthetic_human_review_issue_matrix import *

def d(v): return hashlib.sha256(v.encode()).hexdigest()
def rehash(row,**changes):
    value=replace(row,**changes); p={k:v for k,v in value.__dict__.items() if k!="digest"}; return replace(value,digest=canonical_digest(p))
def source_values():
    bundles=[]; claims=[]; manifests=[]; receipts=[]; versions=[]
    for flow in FLOWS:
        for index,kind in enumerate(ANSWER_KINDS):
            claim=(d(f"claim:{flow}:{kind}"),)*2; manifest=(d(f"manifest:{flow}:{kind}"),)*2; receipt=(d(f"receipt:{flow}:{kind}"),)*2; version=(1,1)
            if index==1:claim=(claim[0],d(f"counter-claim:{flow}:{kind}"))
            if index==2:manifest=(manifest[0],d(f"counter-manifest:{flow}:{kind}"))
            if index==3:receipt=(receipt[0],d(f"counter-receipt:{flow}:{kind}"))
            if index==4:version=(1,2)
            bundles.append(bundle_projection_digest(flow,kind,claim,manifest,receipt,version)); claims.append(claim); manifests.append(manifest); receipts.append(receipt); versions.append(version)
    return tuple(bundles),tuple(claims),tuple(manifests),tuple(receipts),tuple(versions)
def populated():
    s=SyntheticHumanReviewIssueMatrix()
    for cid in range(8701,9101):
        ws,a=s._expected(cid); s.add_control(cid,ws,a,f"synthetic:issue-matrix-requirement:{(cid-8701)//25:02}",d(str(cid)),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    return s
def anchored():
    s=populated(); bundles,claims,manifests,receipts,versions=source_values(); reviewers=("synthetic:readiness-reviewer:r1","synthetic:preflight-reviewer:r2","synthetic:reconsideration-reviewer:r3"); compilers=tuple(f"synthetic:packet-compiler:c{i}" for i in range(4))
    bset=canonical_digest(bundles); source=canonical_digest(("SUBMISSION_HOLD_DOCKET_SOURCE",bset,reviewers,compilers,"synthetic:human-deliberation-chair:chair","synthetic:cross-party-validator:cross"))
    a=s.anchor_docket("synthetic:issue-matrix-anchor:a",source,bset,d("registry"),d("manifest"),APPLIED_LESSONS,APPLIED_RULES,bundles,claims,manifests,receipts,versions,reviewers,compilers,"synthetic:human-deliberation-chair:chair","synthetic:cross-party-validator:cross",18,True); return s,a
def issued():
    s,a=anchored()
    for f in FLOWS:
        for k in ANSWER_KINDS:s.add_issue(f"synthetic:human-review-issue:{f}:{k}",f,k)
    return s,a
def completed():
    s,a=issued(); return s,a,s.finalize("synthetic:human-review-issue-matrix:m","synthetic:issue-matrix-compiler:mc","synthetic:issue-matrix-validator:mv")

class TestSyntheticHumanReviewIssueMatrix(unittest.TestCase):
    def test_matrix(self): self.assertEqual((WORKSTREAMS[0][0],WORKSTREAMS[-1][1],len(WORKSTREAMS)),(8701,9100,16)); self.assertTrue(all(e-s+1==25 for s,e,_ in WORKSTREAMS))
    def test_exact_controls(self): self.assertEqual(set(populated()._controls),set(range(8701,9101)))
    def test_wrong_control(self):
        with self.assertRaises(GovernanceRejected): SyntheticHumanReviewIssueMatrix().add_control(8701,"WRONG",CONTROL_ASPECTS[0],"synthetic:issue-matrix-requirement:00",d("x"),"PASS")
    def test_control_idempotency_conflict(self):
        s=SyntheticHumanReviewIssueMatrix(); args=(8701,WORKSTREAM_NAMES[0],CONTROL_ASPECTS[0],"synthetic:issue-matrix-requirement:00",d("x"),"PASS"); r=s.add_control(*args); self.assertIs(r,s.add_control(*args))
        with self.assertRaises(GovernanceRejected):s.add_control(*args[:-2],d("y"),"PASS")
    def test_control_slot_swap(self):
        s=populated(); s._controls[8701],s._controls[8702]=s._controls[8702],s._controls[8701]; self.assertFalse(s.evidence()["integrity_valid"])
    def test_anchor_requires_controls(self):
        with self.assertRaises(GovernanceRejected): SyntheticHumanReviewIssueMatrix().anchor_docket("x",d("d"),d("b"),d("r"),d("m"),(),(),(),(),(),(),(),(),(),"x","y",1,True)
    def test_anchor_latest(self):
        s,a=anchored(); s._anchor=None
        with self.assertRaises(GovernanceRejected): s.anchor_docket(a.anchor_id,a.source_docket_digest,a.bundle_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest,a.applied_lesson_ids,a.applied_rule_ids,a.source_bundle_digests,a.claim_pairs,a.manifest_pairs,a.receipt_pairs,a.version_pairs,a.source_reviewers,a.source_compilers,a.source_chair,a.source_validator,a.source_sequence,False)
    def test_lessons_exact(self):
        s,a=anchored(); s._anchor=None
        with self.assertRaises(GovernanceRejected): s.anchor_docket(a.anchor_id,a.source_docket_digest,a.bundle_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest,a.applied_lesson_ids[:-1],a.applied_rule_ids,a.source_bundle_digests,a.claim_pairs,a.manifest_pairs,a.receipt_pairs,a.version_pairs,a.source_reviewers,a.source_compilers,a.source_chair,a.source_validator,a.source_sequence,True)
    def test_anchor_idempotency(self):
        s,a=anchored(); self.assertIs(a,s.anchor_docket(a.anchor_id,a.source_docket_digest,a.bundle_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest,a.applied_lesson_ids,a.applied_rule_ids,a.source_bundle_digests,a.claim_pairs,a.manifest_pairs,a.receipt_pairs,a.version_pairs,a.source_reviewers,a.source_compilers,a.source_chair,a.source_validator,a.source_sequence,True))
    def test_ordered_bundle_set_full_rehash_tamper(self):
        s,a=anchored(); bundles=list(a.source_bundle_digests); bundles[0]=d("substitute"); bundles=tuple(bundles); bset=canonical_digest(bundles); lineage=canonical_digest(("SUBMISSION_HOLD_DOCKET_FULL_LINEAGE",a.source_docket_digest,bset,bundles,a.claim_pairs,a.manifest_pairs,a.receipt_pairs,a.version_pairs,a.source_reviewers,a.source_compilers,a.source_chair,a.source_validator)); s._anchor=rehash(a,source_bundle_digests=bundles,bundle_set_digest=bset,source_lineage_digest=lineage); self.assertFalse(s.evidence()["integrity_valid"])
    def test_semantic_pairs_full_rehash_cannot_keep_bundle_projection(self):
        s,a=anchored(); claims=list(a.claim_pairs); claims[0]=(claims[0][0],d("forged-claim")); claims=tuple(claims)
        lineage=canonical_digest(("SUBMISSION_HOLD_DOCKET_FULL_LINEAGE",a.source_docket_digest,a.bundle_set_digest,a.source_bundle_digests,claims,a.manifest_pairs,a.receipt_pairs,a.version_pairs,a.source_reviewers,a.source_compilers,a.source_chair,a.source_validator)); s._anchor=rehash(a,claim_pairs=claims,source_lineage_digest=lineage); self.assertFalse(s.evidence()["integrity_valid"])
    def test_partial_source_batch_rejected(self):
        s=populated(); b,c,m,r,v=source_values()
        with self.assertRaises(GovernanceRejected): s.anchor_docket("synthetic:issue-matrix-anchor:a",d("docket"),canonical_digest(b[:-1]),d("r"),d("m"),APPLIED_LESSONS,APPLIED_RULES,b[:-1],c[:-1],m[:-1],r[:-1],v[:-1],("synthetic:readiness-reviewer:r1","synthetic:preflight-reviewer:r2","synthetic:reconsideration-reviewer:r3"),tuple(f"synthetic:packet-compiler:c{i}" for i in range(4)),"synthetic:human-deliberation-chair:chair","synthetic:cross-party-validator:cross",1,True)
    def test_role_collision(self):
        s,a=anchored(); s._anchor=None
        with self.assertRaises(GovernanceRejected): s.anchor_docket(a.anchor_id,a.source_docket_digest,a.bundle_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest,a.applied_lesson_ids,a.applied_rule_ids,a.source_bundle_digests,a.claim_pairs,a.manifest_pairs,a.receipt_pairs,a.version_pairs,a.source_reviewers,a.source_compilers,a.source_chair,"synthetic:cross-party-validator:chair",a.source_sequence,True)
    def test_actual_value_outcomes(self): self.assertEqual([x.outcome for x in issued()[0]._issues.values()],list(OUTCOMES)*4)
    def test_kind_label_cannot_override_actual_values(self):
        s,_=issued(); key=(FLOWS[0],ANSWER_KINDS[0]); s._issues[key]=rehash(s._issues[key],outcome="CLAIM_CONFLICT",neutral_label="HUMAN_REVIEW_CLAIM_CONFLICT"); self.assertFalse(s.evidence()["integrity_valid"])
    def test_claim_pair_rehash_tamper(self):
        s,_=issued(); key=next(iter(s._issues)); row=s._issues[key]; s._issues[key]=rehash(row,claim_pair=(row.claim_pair[0],d("forged")),outcome="CLAIM_CONFLICT",neutral_label="HUMAN_REVIEW_CLAIM_CONFLICT"); self.assertFalse(s.evidence()["integrity_valid"])
    def test_issue_requires_anchor(self):
        with self.assertRaises(GovernanceRejected):SyntheticHumanReviewIssueMatrix().add_issue("synthetic:human-review-issue:x",FLOWS[0],ANSWER_KINDS[0])
    def test_immediate_parent_required(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected):s.add_issue("synthetic:human-review-issue:x",FLOWS[0],ANSWER_KINDS[1])
    def test_exact_twenty_issues_holds(self): self.assertEqual((len(issued()[0]._issues),len(issued()[0]._holds)),(20,20))
    def test_issue_idempotency_conflict(self):
        s,_=anchored(); r=s.add_issue("synthetic:human-review-issue:a",FLOWS[0],ANSWER_KINDS[0]); self.assertIs(r,s.add_issue("synthetic:human-review-issue:a",FLOWS[0],ANSWER_KINDS[0]))
        with self.assertRaises(GovernanceRejected):s.add_issue("synthetic:human-review-issue:b",FLOWS[0],ANSWER_KINDS[0])
    def test_parent_rehash_tamper(self):
        s,_=issued(); key=(FLOWS[0],ANSWER_KINDS[1]); s._issues[key]=rehash(s._issues[key],parent_issue_digest=d("bad")); self.assertFalse(s.evidence()["integrity_valid"])
    def test_issue_conclusion_tamper(self):
        s,_=issued(); key=next(iter(s._issues)); s._issues[key]=rehash(s._issues[key],concluded=True); self.assertFalse(s.evidence()["integrity_valid"])
    def test_finalize_requires_complete(self):
        with self.assertRaises(GovernanceRejected):anchored()[0].finalize("synthetic:human-review-issue-matrix:m","synthetic:issue-matrix-compiler:c","synthetic:issue-matrix-validator:v")
    def test_compiler_role_collision(self):
        s,_=issued()
        with self.assertRaises(GovernanceRejected):s.finalize("synthetic:human-review-issue-matrix:m","synthetic:issue-matrix-compiler:chair","synthetic:issue-matrix-validator:v")
    def test_compiler_validator_collision(self):
        s,_=issued()
        with self.assertRaises(GovernanceRejected):s.finalize("synthetic:human-review-issue-matrix:m","synthetic:issue-matrix-compiler:same","synthetic:issue-matrix-validator:same")
    def test_safe_matrix(self):
        r=completed()[2]; self.assertTrue(r.held); self.assertFalse(any((r.concluded,r.recommended,r.accepted,r.approved,r.activated,r.deployed)))
    def test_matrix_decision_tamper(self):
        s,_,r=completed(); s._matrix=rehash(r,concluded=True); self.assertFalse(s.evidence()["integrity_valid"])
    def test_matrix_issue_set_tamper(self):
        s,_,r=completed(); s._matrix=rehash(r,ordered_issue_set_digest=d("bad")); self.assertFalse(s.evidence()["integrity_valid"])
    def test_missing_issue_fails_closed(self):
        s,_=issued(); s._issues.pop(next(iter(s._issues))); self.assertFalse(s.evidence()["integrity_valid"])
    def test_missing_hold_fails_closed(self):
        s,_=issued(); s._holds.pop(); self.assertFalse(s.evidence()["integrity_valid"])
    def test_event_rehash_tamper(self):
        s,_=anchored(); row=s._events[0]|{"artifact_digest":d("bad")}; row["digest"]=canonical_digest({k:v for k,v in row.items() if k!="digest"}); s._events[0]=row; self.assertFalse(s.evidence()["integrity_valid"])
    def test_concurrent_control_idempotency(self):
        s=SyntheticHumanReviewIssueMatrix(); args=(8701,WORKSTREAM_NAMES[0],CONTROL_ASPECTS[0],"synthetic:issue-matrix-requirement:00",d("x"),"PASS")
        with ThreadPoolExecutor(max_workers=8) as pool:rows=list(pool.map(lambda _:s.add_control(*args),range(20)))
        self.assertEqual(len({x.digest for x in rows}),1)
    def test_complete_evidence(self):
        e=completed()[0].evidence(); self.assertTrue(e["complete_issue_matrix_evidence"]); self.assertEqual((e["issue_count"],e["hold_count"]),(20,20))
    def test_non_execution(self):
        e=completed()[0].evidence(); keys=("external_calls","document_transmissions","electronic_signatures","external_pg_calls","card_network_calls","payment_approvals","cancellations","refunds","settlements","transfers","ledger_writes","credential_reads","deployments","policy_prompt_weight_changes"); self.assertEqual(tuple(e[k] for k in keys),(0,)*len(keys)); self.assertFalse(any(e[k] for k in ("accepted","recommended","concluded","approved","activated")))

if __name__=="__main__":unittest.main()
