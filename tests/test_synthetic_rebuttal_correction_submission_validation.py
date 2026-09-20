import hashlib
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.synthetic_rebuttal_correction_submission_validation import *

def d(value): return hashlib.sha256(value.encode()).hexdigest()

def rehash(row, **changes):
    value = replace(row, **changes); payload = {k: v for k, v in value.__dict__.items() if k != "digest"}
    if "source_reviews" in payload: payload["source_reviews"] = tuple(tuple(x.__dict__.values()) for x in payload["source_reviews"])
    return replace(value, digest=canonical_digest(payload))

def reviews():
    rows = []
    for pos, (flow, kind) in enumerate(CASE_KEYS):
        route = ROUTES[pos % 5]; previous = None if not rows else rows[-1].digest
        reviewer = None if route == "NOT_APPLICABLE_PRESERVED" else f"synthetic:response-independent-reviewer:r-{flow}-{kind}"
        custodian = None if route == "NOT_APPLICABLE_PRESERVED" else f"synthetic:{'rebuttal-custodian' if route == 'REBUTTAL_OPPORTUNITY_REQUIRED' else 'correction-request-compiler'}:c-{flow}-{kind}"
        row = SourceReview(f"synthetic:response-review:{flow}:{kind}", flow, kind, d(f"intake:{flow}:{kind}"), route, reviewer, custodian, previous, pos+1, True, False, False, False, "")
        rows.append(replace(row, digest=review_digest(row)))
    return tuple(rows)

def populated():
    service = SyntheticRebuttalCorrectionSubmissionValidation()
    for control_id in range(10301, 10701):
        workstream, aspect = service._expected(control_id)
        service.add_control(control_id, workstream, aspect, f"synthetic:submission-validation-requirement:{(control_id-10301)//25:02}", d(str(control_id)), "EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS")
    return service

def anchored():
    service = populated(); rows = reviews(); review_set = canonical_digest(tuple(x.digest for x in rows))
    compiler = "synthetic:review-docket-compiler:source-compiler"; validator = "synthetic:review-docket-validator:source-validator"
    source_docket = canonical_digest(("RESPONSE_REVIEW_REBUTTAL_CORRECTION_DOCKET_SOURCE", review_set, compiler, validator))
    anchor = service.anchor("synthetic:submission-validation-anchor:a", source_docket, review_set, d("registry"), d("manifest"), APPLIED_LESSONS, APPLIED_RULES, rows, compiler, validator, 22, True)
    return service, anchor

def submitted():
    service, anchor = anchored()
    for pos, (flow, kind) in enumerate(CASE_KEYS):
        submission_id = f"synthetic:rebuttal-correction-submission:{flow}:{kind}"
        if ROUTES[pos % 5] == "NOT_APPLICABLE_PRESERVED": service.add_submission(submission_id, flow, kind)
        else: service.add_submission(submission_id, flow, kind, d(f"document:{flow}:{kind}"), d(f"receipt:{flow}:{kind}"))
    return service, anchor

def completed():
    service, anchor = submitted()
    docket = service.finalize("synthetic:submission-validation-docket:d", "synthetic:submission-docket-compiler:compiler", "synthetic:submission-docket-validator:validator")
    return service, anchor, docket

class Tests(unittest.TestCase):
    def test_matrix(self): self.assertEqual((WORKSTREAMS[0][0], WORKSTREAMS[-1][1], len(WORKSTREAMS)), (10301, 10700, 16))
    def test_controls(self): self.assertEqual(set(populated()._controls), set(range(10301, 10701)))
    def test_wrong_control(self):
        with self.assertRaises(GovernanceRejected): SyntheticRebuttalCorrectionSubmissionValidation().add_control(10301, "BAD", CONTROL_ASPECTS[0], "synthetic:submission-validation-requirement:00", d("x"), "PASS")
    def test_control_concurrency(self):
        service = SyntheticRebuttalCorrectionSubmissionValidation(); args = (10301, WORKSTREAM_NAMES[0], CONTROL_ASPECTS[0], "synthetic:submission-validation-requirement:00", d("x"), "PASS")
        with ThreadPoolExecutor(max_workers=8) as pool: rows = list(pool.map(lambda _: service.add_control(*args), range(20)))
        self.assertEqual(len({x.digest for x in rows}), 1)
    def test_anchor_requires_controls(self):
        with self.assertRaises(GovernanceRejected): SyntheticRebuttalCorrectionSubmissionValidation().anchor("x", d("d"), d("s"), d("r"), d("m"), (), (), (), "x", "y", 1, True)
    def test_lessons_exact(self):
        service, anchor = anchored(); service._anchor = None
        with self.assertRaises(GovernanceRejected): service.anchor(anchor.anchor_id, anchor.source_docket_digest, anchor.review_set_digest, anchor.lesson_registry_digest, anchor.remediation_manifest_digest, anchor.applied_lesson_ids[:-1], anchor.applied_rule_ids, anchor.source_reviews, anchor.source_compiler, anchor.source_validator, anchor.source_sequence, True)
    def test_latest_required(self):
        service, anchor = anchored(); service._anchor = None
        with self.assertRaises(GovernanceRejected): service.anchor(anchor.anchor_id, anchor.source_docket_digest, anchor.review_set_digest, anchor.lesson_registry_digest, anchor.remediation_manifest_digest, anchor.applied_lesson_ids, anchor.applied_rule_ids, anchor.source_reviews, anchor.source_compiler, anchor.source_validator, anchor.source_sequence, False)
    def test_source_route_full_rehash_tamper(self):
        service, anchor = anchored(); rows = list(anchor.source_reviews); rows[1] = rehash(rows[1], route="CORRECTION_REQUEST_REQUIRED"); rows = tuple(rows)
        review_set = canonical_digest(tuple(x.digest for x in rows)); lineage = canonical_digest(("RESPONSE_REVIEW_FULL_LINEAGE", anchor.source_docket_digest, review_set, tuple(x.digest for x in rows), anchor.source_compiler, anchor.source_validator))
        source_docket = canonical_digest(("RESPONSE_REVIEW_REBUTTAL_CORRECTION_DOCKET_SOURCE", review_set, anchor.source_compiler, anchor.source_validator))
        service._anchor = rehash(anchor, source_reviews=rows, review_set_digest=review_set, source_lineage_digest=lineage, source_docket_digest=source_docket)
        self.assertFalse(service.evidence()["integrity_valid"])
    def test_source_actor_namespace_rehash_tamper(self):
        service, anchor = anchored(); rows = list(anchor.source_reviews); rows[1] = rehash(rows[1], reviewer="synthetic:wrong:r-1"); rows = tuple(rows)
        review_set = canonical_digest(tuple(x.digest for x in rows)); lineage = canonical_digest(("RESPONSE_REVIEW_FULL_LINEAGE", anchor.source_docket_digest, review_set, tuple(x.digest for x in rows), anchor.source_compiler, anchor.source_validator))
        source_docket = canonical_digest(("RESPONSE_REVIEW_REBUTTAL_CORRECTION_DOCKET_SOURCE", review_set, anchor.source_compiler, anchor.source_validator))
        service._anchor = rehash(anchor, source_reviews=rows, review_set_digest=review_set, source_lineage_digest=lineage, source_docket_digest=source_docket)
        self.assertFalse(service.evidence()["integrity_valid"])
    def test_submission_requires_anchor(self):
        with self.assertRaises(GovernanceRejected): SyntheticRebuttalCorrectionSubmissionValidation().add_submission("synthetic:rebuttal-correction-submission:x", FLOWS[0], ANSWER_KINDS[0])
    def test_na_forbids_material(self):
        service, _ = anchored()
        with self.assertRaises(GovernanceRejected): service.add_submission("synthetic:rebuttal-correction-submission:x", FLOWS[0], ANSWER_KINDS[0], d("doc"), d("receipt"))
    def test_routed_submission_requires_material(self):
        service, _ = anchored(); service.add_submission("synthetic:rebuttal-correction-submission:first", FLOWS[0], ANSWER_KINDS[0])
        with self.assertRaises(GovernanceRejected): service.add_submission("synthetic:rebuttal-correction-submission:second", FLOWS[0], ANSWER_KINDS[1])
    def test_immediate_parent_required(self):
        service, _ = anchored()
        with self.assertRaises(GovernanceRejected): service.add_submission("synthetic:rebuttal-correction-submission:second", FLOWS[0], ANSWER_KINDS[1], d("doc"), d("receipt"))
    def test_counts(self):
        service, _ = submitted(); evidence = service.evidence()
        self.assertEqual((evidence["submission_count"], evidence["no_submission_count"], evidence["rebuttal_submission_count"], evidence["correction_submission_count"], evidence["hold_count"]), (20, 4, 8, 8, 16))
    def test_submitter_derived_from_flow(self):
        service, _ = submitted(); key = (FLOWS[0], ANSWER_KINDS[1]); service._submissions[key] = replace(service._submissions[key], submitter_party="UPSTREAM_PG")
        self.assertFalse(service.evidence()["integrity_valid"])
    def test_receipt_rehash_tamper(self):
        service, _ = submitted(); key = (FLOWS[0], ANSWER_KINDS[1]); row = service._submissions[key]
        service._submissions[key] = replace(row, receipt_digest=d("replacement"), digest=submission_digest(row.flow, row.answer_kind, row.source_review_digest, row.route, row.submitter_party, row.document_digest, d("replacement"), row.marker, row.parent_submission_digest, row.position))
        self.assertFalse(service.evidence()["integrity_valid"])
    def test_parent_rehash_tamper(self):
        service, _ = submitted(); key = (FLOWS[0], ANSWER_KINDS[1]); row = service._submissions[key]
        service._submissions[key] = replace(row, parent_submission_digest=d("bad"), digest=submission_digest(row.flow, row.answer_kind, row.source_review_digest, row.route, row.submitter_party, row.document_digest, row.receipt_digest, row.marker, d("bad"), row.position))
        self.assertFalse(service.evidence()["integrity_valid"])
    def test_finalize_incomplete(self):
        with self.assertRaises(GovernanceRejected): anchored()[0].finalize("synthetic:submission-validation-docket:d", "synthetic:submission-docket-compiler:c", "synthetic:submission-docket-validator:v")
    def test_final_actor_separation(self):
        service, anchor = submitted()
        with self.assertRaises(GovernanceRejected): service.finalize("synthetic:submission-validation-docket:d", f"synthetic:submission-docket-compiler:{anchor.source_compiler.rsplit(':',1)[-1]}", "synthetic:submission-docket-validator:v")
    def test_safe_docket(self):
        docket = completed()[2]; self.assertTrue(docket.held); self.assertFalse(any((docket.resolved, docket.recommended, docket.accepted, docket.approved, docket.activated, docket.deployed)))
    def test_docket_tamper(self):
        service, _, docket = completed(); service._docket = rehash(docket, resolved=True); self.assertFalse(service.evidence()["integrity_valid"])
    def test_missing_hold(self):
        service, _ = submitted(); service._holds.pop(); self.assertFalse(service.evidence()["integrity_valid"])
    def test_complete(self):
        evidence = completed()[0].evidence(); self.assertTrue(evidence["complete_submission_docket_evidence"]); self.assertEqual(evidence["maximum_state"], "REBUTTAL_CORRECTION_SUBMISSIONS_VALIDATED_ON_HOLD_NOT_RESOLVED")
    def test_non_execution(self):
        evidence = completed()[0].evidence(); keys = ("external_calls", "document_transmissions", "electronic_signatures", "external_pg_calls", "card_network_calls", "payment_approvals", "cancellations", "refunds", "settlements", "transfers", "ledger_writes", "credential_reads", "deployments", "policy_prompt_weight_changes")
        self.assertEqual(tuple(evidence[k] for k in keys), (0,)*len(keys))

if __name__ == "__main__": unittest.main()
