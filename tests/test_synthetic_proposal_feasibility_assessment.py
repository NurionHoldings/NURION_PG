from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from hashlib import sha256
import unittest

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.synthetic_proposal_feasibility_assessment import (
    PROPOSAL_KINDS, MAX_PROPOSAL_BATCH, SyntheticProposalFeasibilityAssessment,
)


def digest(value): return sha256(value.encode()).hexdigest()


class ProposalFeasibilityAssessmentTests(unittest.TestCase):
    def intake(self, service, name):
        return service.intake(f"synthetic:decision-intent:{name}", digest(f"ready:{name}"))

    def batched(self, service, name="one"):
        row = self.intake(service, name)
        service.reserve_batch(f"synthetic:proposal-batch:{name}", 1)
        return service.get(row.intent_id)

    def drafted(self, service, name="one", planner="a", kind="SELF_CONTAINED"):
        row = self.batched(service, name)
        return service.propose(f"synthetic:planning-proposal:{name}", row.intent_id, row.version,
                             f"synthetic:planner:{planner}", kind, digest(f"why:{name}"))

    def reviewed(self, service, name="one", planner="a", reviewer="b"):
        row = self.drafted(service, name, planner)
        return service.review(f"synthetic:proposal-review:{name}", row.intent_id, row.version,
                              f"synthetic:reviewer:{reviewer}", True,
                              digest(f"review:{name}"))

    def recorded(self, service, name="one", planner="a", reviewer="b", verifier="c"):
        row = self.reviewed(service, name, planner, reviewer)
        review = service.review_receipt(f"synthetic:proposal-review:{name}")
        return service.record_receipt(f"synthetic:proposal-receipt:{name}", row.intent_id,
                                      row.version, review.digest,
                                      f"synthetic:verifier:{verifier}")

    def test_intake_idempotency_and_conflict(self):
        s = SyntheticProposalFeasibilityAssessment(); row = self.intake(s, "a")
        self.assertIs(row, self.intake(s, "a"))
        with self.assertRaises(GovernanceRejected):
            s.intake(row.intent_id, digest("different"))

    def test_batch_cap_order_idempotency_and_conflict(self):
        s = SyntheticProposalFeasibilityAssessment()
        for i in range(22): self.intake(s, f"{i:02}")
        batch = s.reserve_batch("synthetic:proposal-batch:cap", MAX_PROPOSAL_BATCH)
        self.assertEqual((len(batch.intent_ids), batch.intent_ids[0][-2:]), (20, "00"))
        self.assertIs(batch, s.reserve_batch(batch.batch_id, 20))
        with self.assertRaises(GovernanceRejected): s.reserve_batch(batch.batch_id, 1)
        with self.assertRaises(GovernanceRejected): s.reserve_batch("synthetic:proposal-batch:x", 21)

    def test_concurrent_batches_never_overlap(self):
        s = SyntheticProposalFeasibilityAssessment()
        for i in range(40): self.intake(s, f"{i:02}")
        with ThreadPoolExecutor(max_workers=2) as pool:
            batches = list(pool.map(
                lambda n: s.reserve_batch(f"synthetic:proposal-batch:{n}", 20), (1, 2)))
        ids = batches[0].intent_ids + batches[1].intent_ids
        self.assertEqual(len(ids), len(set(ids)))

    def test_each_allowlisted_proposal_kind_records(self):
        for index, kind in enumerate(sorted(PROPOSAL_KINDS)):
            s = SyntheticProposalFeasibilityAssessment()
            row = self.drafted(s, str(index), kind=kind)
            self.assertEqual((row.proposal_kind, row.status), (kind, "PROPOSAL_DRAFTED"))

    def test_unknown_proposal_kind_fails_closed(self):
        s = SyntheticProposalFeasibilityAssessment(); row = self.batched(s, "unknown")
        with self.assertRaises(GovernanceRejected):
            s.propose("synthetic:planning-proposal:unknown", row.intent_id, row.version,
                    "synthetic:planner:a", "DEPLOY", digest("why"))

    def test_risk_rollback_and_evidence_boundaries_fail_closed(self):
        cases = (("HIGH", True, 2), ("LOW", False, 2), ("MEDIUM", True, 1))
        for index, (risk, rollback, count) in enumerate(cases):
            s = SyntheticProposalFeasibilityAssessment(); row = self.batched(s, f"boundary-{index}")
            with self.assertRaises(GovernanceRejected):
                s.propose(f"synthetic:planning-proposal:boundary-{index}", row.intent_id,
                    row.version, "synthetic:planner:a", "SELF_CONTAINED", digest("why"),
                    risk, rollback, count)

    def test_medium_risk_with_rollback_and_evidence_is_observable_only(self):
        s = SyntheticProposalFeasibilityAssessment(); row = self.batched(s, "medium")
        row = s.propose("synthetic:planning-proposal:medium", row.intent_id, row.version,
            "synthetic:planner:a", "BOUNDED_INTERNAL", digest("why"), "MEDIUM", True, 3)
        artifact = s._proposals["synthetic:planning-proposal:medium"]
        self.assertEqual((artifact.risk_level, artifact.rollback_possible, artifact.evidence_count),
                         ("MEDIUM", True, 3))
        self.assertEqual(row.status, "PROPOSAL_DRAFTED")

    def test_proposal_idempotency_conflict_and_owner_uniqueness(self):
        s = SyntheticProposalFeasibilityAssessment(); base = self.batched(s, "propose")
        args = ("synthetic:planning-proposal:propose", base.intent_id, base.version,
                "synthetic:planner:a", "BOUNDED_INTERNAL", digest("why"))
        row = s.propose(*args); self.assertIs(row, s.propose(*args))
        with self.assertRaises(GovernanceRejected): s.propose(*args[:-1], digest("other"))
        with self.assertRaises(GovernanceRejected):
            s.propose("synthetic:planning-proposal:second", base.intent_id, base.version,
                    "synthetic:planner:a", "BOUNDED_INTERNAL", digest("why"))

    def test_concurrent_exact_draft_converges(self):
        s = SyntheticProposalFeasibilityAssessment(); base = self.batched(s, "propose-race")
        args = ("synthetic:planning-proposal:propose-race", base.intent_id, base.version,
                "synthetic:planner:a", "BOUNDED_INTERNAL", digest("race"))
        with ThreadPoolExecutor(max_workers=8) as pool:
            rows = list(pool.map(lambda _: s.propose(*args), range(32)))
        self.assertEqual({row.digest for row in rows}, {rows[0].digest})
        self.assertEqual(sum(r.intent_id == base.intent_id for r in s._history), 3)

    def test_planner_and_reviewer_must_be_independent(self):
        s = SyntheticProposalFeasibilityAssessment(); row = self.drafted(s, "roles")
        with self.assertRaises(GovernanceRejected):
            s.review("synthetic:proposal-review:roles", row.intent_id, row.version,
                     "synthetic:reviewer:a", True, digest("review"))

    def test_review_idempotency_conflict_and_version_binding(self):
        s = SyntheticProposalFeasibilityAssessment(); row = self.drafted(s, "review")
        args = ("synthetic:proposal-review:review", row.intent_id, row.version,
                "synthetic:reviewer:b", True, digest("review"))
        result = s.review(*args); self.assertIs(result, s.review(*args))
        with self.assertRaises(GovernanceRejected): s.review(*args[:-1], digest("other"))
        with self.assertRaises(GovernanceRejected):
            s.review("synthetic:proposal-review:stale", row.intent_id, row.version - 1,
                     "synthetic:reviewer:c", True, digest("stale"))

    def test_review_rejection_creates_bound_auto_hold(self):
        s = SyntheticProposalFeasibilityAssessment(); row = self.drafted(s, "reject")
        row = s.review("synthetic:proposal-review:reject", row.intent_id, row.version,
                       "synthetic:reviewer:b", False, digest("reject"))
        self.assertEqual((row.status, row.hold_reason), ("HELD", "REVIEW_REJECTED"))
        evidence = s.evidence()
        self.assertTrue(evidence["hold_chain_valid"])
        self.assertTrue(evidence["event_chain_valid"])

    def test_integrity_finding_creates_bound_auto_hold(self):
        s = SyntheticProposalFeasibilityAssessment(); row = self.drafted(s, "integrity-hold")
        row = s.hold_integrity_drift("synthetic:integrity-finding:one", row.intent_id,
                                     row.version, "synthetic:auditor:guard",
                                     digest("integrity-drift"))
        self.assertEqual((row.status, row.hold_reason), ("HELD", "INTEGRITY_DRIFT"))
        evidence = s.evidence()
        self.assertTrue(evidence["artifact_integrity_valid"])
        self.assertTrue(evidence["hold_chain_valid"])

    def test_integrity_finding_idempotency_and_conflict(self):
        s = SyntheticProposalFeasibilityAssessment(); row = self.batched(s, "finding-idem")
        args = ("synthetic:integrity-finding:idem", row.intent_id, row.version,
                "synthetic:auditor:guard", digest("finding"))
        result = s.hold_integrity_drift(*args)
        self.assertIs(result, s.hold_integrity_drift(*args))
        with self.assertRaises(GovernanceRejected):
            s.hold_integrity_drift(*args[:-1], digest("other"))

    def test_integrity_auditor_must_be_independent(self):
        s = SyntheticProposalFeasibilityAssessment(); row = self.drafted(s, "auditor-planner")
        with self.assertRaises(GovernanceRejected):
            s.hold_integrity_drift("synthetic:integrity-finding:planner",
                row.intent_id, row.version, "synthetic:auditor:a", digest("planner"))

        s2 = SyntheticProposalFeasibilityAssessment(); row2 = self.reviewed(s2, "auditor-reviewer")
        with self.assertRaises(GovernanceRejected):
            s2.hold_integrity_drift("synthetic:integrity-finding:reviewer",
                row2.intent_id, row2.version, "synthetic:auditor:b", digest("reviewer"))

        s3 = SyntheticProposalFeasibilityAssessment(); row3 = self.recorded(s3, "auditor-verifier")
        with self.assertRaises(GovernanceRejected):
            s3.hold_integrity_drift("synthetic:integrity-finding:verifier",
                row3.intent_id, row3.version, "synthetic:auditor:c", digest("verifier"))

    def test_independent_auditor_can_hold_recorded_proposal(self):
        s = SyntheticProposalFeasibilityAssessment(); row = self.recorded(s, "post-receipt-hold")
        row = s.hold_integrity_drift("synthetic:integrity-finding:post-receipt",
            row.intent_id, row.version, "synthetic:auditor:d", digest("post-receipt"))
        self.assertEqual((row.status, row.hold_reason), ("HELD", "INTEGRITY_DRIFT"))
        self.assertTrue(s.evidence()["hold_chain_valid"])

    def test_verifier_is_third_independent_role(self):
        for verifier in ("a", "b"):
            s = SyntheticProposalFeasibilityAssessment(); row = self.reviewed(s, verifier)
            review = s.review_receipt(f"synthetic:proposal-review:{verifier}")
            with self.assertRaises(GovernanceRejected):
                s.record_receipt(f"synthetic:proposal-receipt:{verifier}", row.intent_id,
                                 row.version, review.digest,
                                 f"synthetic:verifier:{verifier}")

    def test_receipt_is_inert_and_maximum_state_is_bounded(self):
        s = SyntheticProposalFeasibilityAssessment(); row = self.recorded(s, "inert")
        receipt = s.receipt("synthetic:proposal-receipt:inert")
        self.assertEqual(row.status, "SYNTHETIC_FEASIBILITY_RECORDED")
        self.assertTrue(receipt.non_authorizing and receipt.non_deployable
                        and receipt.non_executable)
        self.assertEqual(s.evidence()["maximum_state"], "SYNTHETIC_FEASIBILITY_RECORDED")

    def test_receipt_idempotency_and_conflict(self):
        s = SyntheticProposalFeasibilityAssessment(); row = self.reviewed(s, "receipt")
        review = s.review_receipt("synthetic:proposal-review:receipt")
        args = ("synthetic:proposal-receipt:receipt", row.intent_id, row.version,
                review.digest, "synthetic:verifier:c")
        result = s.record_receipt(*args); self.assertIs(result, s.record_receipt(*args))
        with self.assertRaises(GovernanceRejected):
            s.record_receipt(args[0], args[1], args[2], args[3], "synthetic:verifier:d")

    def test_concurrent_exact_receipt_records_once(self):
        s = SyntheticProposalFeasibilityAssessment(); row = self.reviewed(s, "receipt-race")
        review = s.review_receipt("synthetic:proposal-review:receipt-race")
        args = ("synthetic:proposal-receipt:receipt-race", row.intent_id, row.version,
                review.digest, "synthetic:verifier:c")
        with ThreadPoolExecutor(max_workers=8) as pool:
            rows = list(pool.map(lambda _: s.record_receipt(*args), range(32)))
        self.assertEqual({item.digest for item in rows}, {rows[0].digest})
        self.assertEqual(len(s._receipts), 1)

    def test_cross_intent_review_replay_is_blocked(self):
        s = SyntheticProposalFeasibilityAssessment()
        first = self.reviewed(s, "first")
        first_review = s.review_receipt("synthetic:proposal-review:first")
        second = self.reviewed(s, "second")
        with self.assertRaises(GovernanceRejected):
            s.record_receipt("synthetic:proposal-receipt:swap", second.intent_id,
                             second.version, first_review.digest, "synthetic:verifier:c")
        self.assertEqual(first.status, "PROPOSAL_REVIEWED")

    def test_same_review_digest_cannot_be_reused(self):
        s = SyntheticProposalFeasibilityAssessment(); self.recorded(s, "used")
        receipt = s.receipt("synthetic:proposal-receipt:used")
        with self.assertRaises(GovernanceRejected):
            s.record_receipt("synthetic:proposal-receipt:again", receipt.intent_id,
                             receipt.source_version, receipt.review_digest,
                             "synthetic:verifier:d")

    def test_upstream_tamper_blocks_review(self):
        s = SyntheticProposalFeasibilityAssessment(); row = self.drafted(s, "tamper-review")
        propose = s._proposals["synthetic:planning-proposal:tamper-review"]
        s._proposals[propose.proposal_id] = replace(propose, proposal_kind="DEPLOY")
        with self.assertRaises(GovernanceRejected):
            s.review("synthetic:proposal-review:tamper-review", row.intent_id, row.version,
                     "synthetic:reviewer:b", True, digest("review"))

    def test_upstream_tamper_blocks_receipt(self):
        s = SyntheticProposalFeasibilityAssessment(); row = self.reviewed(s, "tamper-receipt")
        review = s.review_receipt("synthetic:proposal-review:tamper-receipt")
        s._reviews[review.review_id] = replace(review, accepted=False)
        with self.assertRaises(GovernanceRejected):
            s.record_receipt("synthetic:proposal-receipt:tamper-receipt", row.intent_id,
                             row.version, review.digest, "synthetic:verifier:c")

    def test_non_deployable_boundary_tamper_is_detected(self):
        s = SyntheticProposalFeasibilityAssessment(); self.recorded(s, "boundary")
        proposal = s._proposals["synthetic:planning-proposal:boundary"]
        s._proposals[proposal.proposal_id] = replace(proposal, non_deployable=False)
        self.assertFalse(s.evidence()["artifact_integrity_valid"])

    def test_feasibility_criteria_tamper_is_detected(self):
        for field, value in (("risk_level", "HIGH"), ("rollback_possible", False),
                             ("evidence_count", 1)):
            s = SyntheticProposalFeasibilityAssessment(); self.recorded(s, f"criteria-{field}")
            key = f"synthetic:planning-proposal:criteria-{field}"
            s._proposals[key] = replace(s._proposals[key], **{field: value})
            self.assertFalse(s.evidence()["artifact_integrity_valid"])

    def test_semantic_event_tamper_detected_even_after_rehash(self):
        s = SyntheticProposalFeasibilityAssessment(); self.recorded(s, "event")
        event = s._events[-1]; event["action"] = "PROPOSAL_REVIEWED"
        payload = {k: event[k] for k in ("sequence", "action", "record_digest",
                                         "attachment_digest", "previous_digest")}
        event["digest"] = canonical_digest(payload)
        self.assertFalse(s.evidence()["event_chain_valid"])

    def test_record_batch_hold_and_replay_tamper_detected(self):
        s = SyntheticProposalFeasibilityAssessment(); self.recorded(s, "record")
        row = s._history[0]; s._history[0] = replace(row, intent_digest=digest("changed"))
        self.assertFalse(s.evidence()["history_chain_valid"])
        s = SyntheticProposalFeasibilityAssessment(); self.recorded(s, "index")
        review = s.review_receipt("synthetic:proposal-review:index")
        s._used_review_digests[review.digest] = "synthetic:decision-intent:missing"
        self.assertFalse(s.evidence()["receipt_replay_index_valid"])

    def test_feature_map_and_prohibited_effect_flags(self):
        evidence = SyntheticProposalFeasibilityAssessment().evidence()
        self.assertEqual(evidence["features"], list(range(2101, 2501)))
        self.assertEqual(evidence["feature_count"], 400)
        self.assertEqual(len(evidence["workstreams"]), 16)
        self.assertEqual(sum(x["control_count"] for x in evidence["workstreams"]), 400)
        self.assertTrue(all(w["control_count"] == 25 for w in evidence["workstreams"]))
        self.assertTrue(evidence["synthetic_only"])
        self.assertTrue(evidence["in_memory_only"])
        for key, value in evidence.items():
            if key.endswith(("_allowed", "_used", "_recorded", "_accessed")): self.assertFalse(value, key)

    def test_observation_only_portfolio_is_bounded_unique_and_integral(self):
        s = SyntheticProposalFeasibilityAssessment()
        for index in range(25):
            self.recorded(s, f"portfolio-{index:02}")
        first = s.observe_portfolio(
            "synthetic:feasibility-portfolio:first",
            "synthetic:portfolio-observer:d", 20,
        )
        second = s.observe_portfolio(
            "synthetic:feasibility-portfolio:second",
            "synthetic:portfolio-observer:d", 20,
        )
        self.assertEqual((len(first.intent_ids), len(second.intent_ids)), (20, 5))
        self.assertFalse(set(first.intent_ids).intersection(second.intent_ids))
        self.assertTrue(s.evidence()["portfolio_integrity_valid"])

    def test_portfolio_observer_must_be_independent(self):
        s = SyntheticProposalFeasibilityAssessment(); self.recorded(s, "portfolio-role")
        with self.assertRaises(GovernanceRejected):
            s.observe_portfolio("synthetic:feasibility-portfolio:role",
                                "synthetic:portfolio-observer:a", 1)

    def test_portfolio_aggregate_tamper_is_detected(self):
        s = SyntheticProposalFeasibilityAssessment(); self.recorded(s, "portfolio-tamper")
        portfolio = s.observe_portfolio("synthetic:feasibility-portfolio:tamper",
                                        "synthetic:portfolio-observer:d", 1)
        s._portfolios[portfolio.portfolio_id] = replace(
            portfolio, minimum_evidence_count=portfolio.minimum_evidence_count + 1)
        self.assertFalse(s.evidence()["portfolio_integrity_valid"])

    def test_invalid_namespaces_and_boolean_versions_fail_closed(self):
        s = SyntheticProposalFeasibilityAssessment()
        with self.assertRaises(GovernanceRejected): s.intake("prod:intent", digest("x"))
        row = self.batched(s, "bad")
        with self.assertRaises(GovernanceRejected):
            s.propose("synthetic:planning-proposal:bad", row.intent_id, True,
                    "synthetic:planner:a", "BOUNDED_INTERNAL", digest("why"))


if __name__ == "__main__": unittest.main()
