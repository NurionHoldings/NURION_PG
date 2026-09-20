import hashlib
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.synthetic_rebuttal_correction_independent_rereview import *

def d(value): return hashlib.sha256(value.encode()).hexdigest()

def rehash(row, **changes):
    value = replace(row, **changes); payload = {k: v for k, v in value.__dict__.items() if k != "digest"}
    if "source_submissions" in payload: payload["source_submissions"] = tuple(tuple(x.__dict__.values()) for x in payload["source_submissions"])
    return replace(value, digest=canonical_digest(payload))

def sources():
    rows = []
    for position, (flow, kind) in enumerate(CASE_KEYS):
        route = ROUTES[position % 5]; parent = None if not rows else rows[-1].digest
        review = d(f"source-review:{flow}:{kind}")
        if route == "NOT_APPLICABLE_PRESERVED":
            submitter = document = receipt = None; marker = "NO_SUBMISSION_REQUIRED"
        else:
            submitter = RESPONDER[flow]; document = d(f"document:{flow}:{kind}")
            receipt = derived_receipt_digest(flow, kind, review, route, submitter, document)
            marker = "SUBMISSION_RECEIVED_FOR_HUMAN_REVIEW"
        digest = submission_digest(flow, kind, review, route, submitter, document, receipt, marker, parent, position + 1)
        rows.append(SourceSubmission(f"synthetic:rebuttal-correction-submission:{flow}:{kind}", flow, kind,
                                     review, route, submitter, document, receipt, marker, parent,
                                     position + 1, True, True, False, False, digest))
    return tuple(rows)

def populated():
    service = SyntheticRebuttalCorrectionIndependentReReview()
    for control_id in range(10701, 11101):
        workstream, aspect = service._expected(control_id)
        service.add_control(control_id, workstream, aspect, f"synthetic:independent-rereview-requirement:{(control_id-10701)//25:02}", d(str(control_id)), "EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS")
    return service

def source_actors():
    return tuple(f"synthetic:{kind}:source-actor-{position}" for position, kind in enumerate(SOURCE_ACTOR_KINDS))

def anchored():
    service = populated(); rows = sources(); submission_set = canonical_digest(tuple(x.digest for x in rows))
    compiler = "synthetic:submission-docket-compiler:source-compiler"; validator = "synthetic:submission-docket-validator:source-validator"
    docket = canonical_digest(("REBUTTAL_CORRECTION_SUBMISSION_DOCKET_SOURCE", submission_set, compiler, validator))
    anchor = service.anchor("synthetic:independent-rereview-anchor:a", docket, submission_set, d("registry"), d("manifest"), APPLIED_LESSONS, APPLIED_RULES, rows, source_actors(), compiler, validator, 23, True)
    return service, anchor

def reviewed():
    service, anchor = anchored()
    for position, (flow, kind) in enumerate(CASE_KEYS):
        args = (f"synthetic:independent-rereview:{flow}:{kind}", flow, kind)
        if ROUTES[position % 5] == "NOT_APPLICABLE_PRESERVED": service.add_rereview(*args)
        else: service.add_rereview(*args, f"synthetic:independent-human-rereviewer:reviewer-{position}")
    return service, anchor

def completed():
    service, anchor = reviewed()
    docket = service.finalize("synthetic:independent-rereview-docket:d", "synthetic:rereview-docket-compiler:compiler", "synthetic:rereview-docket-validator:validator")
    return service, anchor, docket

class Tests(unittest.TestCase):
    def test_matrix(self): self.assertEqual((WORKSTREAMS[0][0], WORKSTREAMS[-1][1], len(WORKSTREAMS)), (10701, 11100, 16))
    def test_controls(self): self.assertEqual(set(populated()._controls), set(range(10701, 11101)))
    def test_wrong_control(self):
        with self.assertRaises(GovernanceRejected): SyntheticRebuttalCorrectionIndependentReReview().add_control(10701, "BAD", CONTROL_ASPECTS[0], "synthetic:independent-rereview-requirement:00", d("x"), "PASS")
    def test_control_concurrency(self):
        service = SyntheticRebuttalCorrectionIndependentReReview(); args = (10701, WORKSTREAM_NAMES[0], CONTROL_ASPECTS[0], "synthetic:independent-rereview-requirement:00", d("x"), "PASS")
        with ThreadPoolExecutor(max_workers=8) as pool: rows = list(pool.map(lambda _: service.add_control(*args), range(20)))
        self.assertEqual(len({x.digest for x in rows}), 1)
    def test_anchor_requires_controls(self):
        with self.assertRaises(GovernanceRejected): SyntheticRebuttalCorrectionIndependentReReview().anchor("x", d("d"), d("s"), d("r"), d("m"), (), (), (), (), "x", "y", 1, True)
    def test_latest_required(self):
        service, anchor = anchored(); service._anchor = None
        with self.assertRaises(GovernanceRejected): service.anchor(anchor.anchor_id, anchor.source_docket_digest, anchor.submission_set_digest, anchor.lesson_registry_digest, anchor.remediation_manifest_digest, anchor.applied_lesson_ids, anchor.applied_rule_ids, anchor.source_submissions, anchor.source_actor_roles, anchor.source_compiler, anchor.source_validator, anchor.source_sequence, False)
    def test_source_receipt_semantic_tamper(self):
        service, anchor = anchored(); rows = list(anchor.source_submissions); rows[1] = replace(rows[1], receipt_digest=d("unrelated")); rows[1] = replace(rows[1], digest=source_submission_digest(rows[1])); rows = tuple(rows)
        submission_set = canonical_digest(tuple(x.digest for x in rows)); docket = canonical_digest(("REBUTTAL_CORRECTION_SUBMISSION_DOCKET_SOURCE", submission_set, anchor.source_compiler, anchor.source_validator))
        lineage = canonical_digest(("SUBMISSION_VALIDATION_FULL_LINEAGE", docket, submission_set, tuple(x.digest for x in rows), anchor.source_actor_roles, anchor.source_compiler, anchor.source_validator))
        service._anchor = rehash(anchor, source_submissions=rows, submission_set_digest=submission_set, source_docket_digest=docket, source_lineage_digest=lineage)
        self.assertFalse(service.evidence()["integrity_valid"])
    def test_source_actor_full_rehash_tamper_rejected(self):
        service, anchor = anchored(); actors = list(anchor.source_actor_roles)
        actors[0] = "synthetic:wrong-source-reviewer:source-actor-0"; actors = tuple(actors)
        lineage = canonical_digest(("SUBMISSION_VALIDATION_FULL_LINEAGE", anchor.source_docket_digest, anchor.submission_set_digest, tuple(x.digest for x in anchor.source_submissions), actors, anchor.source_compiler, anchor.source_validator))
        service._anchor = rehash(anchor, source_actor_roles=actors, source_lineage_digest=lineage)
        self.assertFalse(service.evidence()["integrity_valid"])
    def test_rereview_requires_anchor(self):
        with self.assertRaises(GovernanceRejected): SyntheticRebuttalCorrectionIndependentReReview().add_rereview("synthetic:independent-rereview:x", FLOWS[0], ANSWER_KINDS[0])
    def test_na_forbids_reviewer(self):
        service, _ = anchored()
        with self.assertRaises(GovernanceRejected): service.add_rereview("synthetic:independent-rereview:x", FLOWS[0], ANSWER_KINDS[0], "synthetic:independent-human-rereviewer:x")
    def test_routed_requires_reviewer(self):
        service, _ = anchored(); service.add_rereview("synthetic:independent-rereview:first", FLOWS[0], ANSWER_KINDS[0])
        with self.assertRaises(GovernanceRejected): service.add_rereview("synthetic:independent-rereview:second", FLOWS[0], ANSWER_KINDS[1])
    def test_immediate_parent_required(self):
        service, _ = anchored()
        with self.assertRaises(GovernanceRejected): service.add_rereview("synthetic:independent-rereview:second", FLOWS[0], ANSWER_KINDS[1], "synthetic:independent-human-rereviewer:x")
    def test_reviewer_reuse_rejected(self):
        service, _ = anchored(); service.add_rereview("synthetic:independent-rereview:first", FLOWS[0], ANSWER_KINDS[0]); reviewer = "synthetic:independent-human-rereviewer:same"
        service.add_rereview("synthetic:independent-rereview:second", FLOWS[0], ANSWER_KINDS[1], reviewer)
        with self.assertRaises(GovernanceRejected): service.add_rereview("synthetic:independent-rereview:third", FLOWS[0], ANSWER_KINDS[2], reviewer)
    def test_source_reviewer_identity_reuse_rejected(self):
        service, anchor = anchored(); service.add_rereview("synthetic:independent-rereview:first", FLOWS[0], ANSWER_KINDS[0])
        identity = anchor.source_actor_roles[0].rsplit(":", 1)[-1]
        with self.assertRaises(GovernanceRejected): service.add_rereview("synthetic:independent-rereview:second", FLOWS[0], ANSWER_KINDS[1], f"synthetic:independent-human-rereviewer:{identity}")
    def test_counts(self):
        evidence = reviewed()[0].evidence()
        self.assertEqual((evidence["rereview_count"], evidence["no_submission_marker_count"], evidence["rebuttal_human_review_pending_count"], evidence["correction_human_review_pending_count"], evidence["hold_count"]), (20, 4, 8, 8, 16))
        self.assertEqual(evidence["source_actor_count"], 32)
    def test_parent_tamper(self):
        service, _ = reviewed(); key = CASE_KEYS[1]; service._rereviews[key] = replace(service._rereviews[key], parent_rereview_digest=d("bad"))
        self.assertFalse(service.evidence()["integrity_valid"])
    def test_missing_hold(self):
        service, _ = reviewed(); service._holds.pop(); self.assertFalse(service.evidence()["integrity_valid"])
    def test_event_tamper(self):
        service, _ = reviewed(); service._events[1]["artifact_digest"] = d("bad"); self.assertFalse(service.evidence()["integrity_valid"])
    def test_finalize_incomplete(self):
        with self.assertRaises(GovernanceRejected): anchored()[0].finalize("synthetic:independent-rereview-docket:d", "synthetic:rereview-docket-compiler:c", "synthetic:rereview-docket-validator:v")
    def test_final_actor_separation(self):
        service, _ = reviewed()
        with self.assertRaises(GovernanceRejected): service.finalize("synthetic:independent-rereview-docket:d", "synthetic:rereview-docket-compiler:reviewer-1", "synthetic:rereview-docket-validator:v")
    def test_safe_docket(self):
        docket = completed()[2]; self.assertTrue(docket.pending_human_reexamination); self.assertFalse(any((docket.concluded, docket.resolved, docket.recommended, docket.accepted, docket.approved, docket.activated, docket.deployed)))
    def test_docket_tamper(self):
        service, _, docket = completed(); service._docket = rehash(docket, concluded=True); self.assertFalse(service.evidence()["integrity_valid"])
    def test_complete(self):
        evidence = completed()[0].evidence(); self.assertTrue(evidence["complete_pending_rereview_docket_evidence"]); self.assertEqual(evidence["maximum_state"], "INDEPENDENT_REREVIEW_DOCKET_ON_HOLD_PENDING_HUMAN_REEXAMINATION")
    def test_non_execution(self):
        evidence = completed()[0].evidence(); keys = ("external_calls", "document_transmissions", "electronic_signatures", "external_pg_calls", "card_network_calls", "payment_approvals", "cancellations", "refunds", "settlements", "transfers", "ledger_writes", "credential_reads", "deployments", "policy_prompt_weight_changes")
        self.assertEqual(tuple(evidence[k] for k in keys), (0,) * len(keys))
    def test_no_conclusion_flags(self):
        evidence = completed()[0].evidence(); self.assertFalse(any(evidence[k] for k in ("concluded", "resolved", "recommended", "accepted", "approved", "activated")))

if __name__ == "__main__": unittest.main()
