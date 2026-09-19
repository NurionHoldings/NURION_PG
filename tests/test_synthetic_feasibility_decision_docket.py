from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from hashlib import sha256
import unittest
from unittest.mock import patch

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_feasibility_decision_docket import (
    DECISIONS, MAX_DOCKET_BATCH, SyntheticFeasibilityDecisionDocket,
)
from nurion_pg.synthetic_proposal_feasibility_assessment import PortfolioObservation
from nurion_pg.arkaon.governance import canonical_digest


def digest(value): return sha256(value.encode()).hexdigest()


class FeasibilityDecisionDocketTests(unittest.TestCase):
    def intake(self, service, name="one", observer="observer"):
        return service.intake(f"synthetic:feasibility-portfolio:{name}", digest(f"p:{name}"),
                              1, 5, f"synthetic:portfolio-observer:{observer}")

    def batched(self, service, name="one", observer="observer"):
        row = self.intake(service, name, observer)
        service.reserve_batch(f"synthetic:docket-batch:{name}", 1)
        return service.get(row.portfolio_id)

    def drafted(self, service, name="one", observer="observer", analyst="analyst",
                decision="OBSERVE"):
        row = self.batched(service, name, observer)
        return service.draft(f"synthetic:decision-draft:{name}", row.portfolio_id, row.version,
            row.source_version, row.portfolio_digest, f"synthetic:docket-analyst:{analyst}",
            decision, digest(f"why:{name}"))

    def reviewed(self, service, name="one", reviewer="reviewer"):
        row = self.drafted(service, name)
        return service.review(f"synthetic:docket-review:{name}", row.portfolio_id, row.version,
            f"synthetic:docket-reviewer:{reviewer}", True, digest(f"review:{name}"))

    def recorded(self, service, name="one", verifier="verifier"):
        row = self.reviewed(service, name)
        review = service.review_receipt(f"synthetic:docket-review:{name}")
        return service.record_receipt(f"synthetic:docket-receipt:{name}", row.portfolio_id,
            row.version, review.digest, f"synthetic:docket-verifier:{verifier}")

    def test_control_matrix_is_exactly_200(self):
        evidence = SyntheticFeasibilityDecisionDocket().evidence()
        self.assertEqual((evidence["control_count"], evidence["workstream_count"]), (200, 8))
        self.assertTrue(evidence["exactly_25_controls_per_workstream"])

    def test_intake_idempotency_and_conflict(self):
        s = SyntheticFeasibilityDecisionDocket(); row = self.intake(s)
        self.assertIs(row, self.intake(s))
        with self.assertRaises(GovernanceRejected):
            s.intake(row.portfolio_id, digest("other"), 1, 5, row.observer)

    def test_intake_rejects_non_synthetic_and_unbounded_members(self):
        s = SyntheticFeasibilityDecisionDocket()
        with self.assertRaises(GovernanceRejected):
            s.intake("real:portfolio:x", digest("x"), 1, 1, "synthetic:portfolio-observer:o")
        with self.assertRaises(GovernanceRejected):
            s.intake("synthetic:feasibility-portfolio:x", digest("x"), 1, 21,
                     "synthetic:portfolio-observer:o")

    def test_typed_upstream_observation_is_verified_at_boundary(self):
        payload = {"portfolio_id": "synthetic:feasibility-portfolio:typed",
            "observer": "synthetic:portfolio-observer:o",
            "intent_ids": ("synthetic:decision-intent:a",),
            "risk_counts": (("LOW", 1), ("MEDIUM", 0)),
            "kind_counts": (("BOUNDED_INTERNAL", 0), ("SELF_CONTAINED", 1),
                            ("SYNTHETIC_FIXTURE_ONLY", 0)),
            "all_rollback_possible": True, "minimum_evidence_count": 2}
        observation = PortfolioObservation(**payload, digest=canonical_digest(payload))
        s = SyntheticFeasibilityDecisionDocket()
        row = s.intake_observation(observation)
        self.assertEqual((row.portfolio_digest, row.member_count), (observation.digest, 1))
        with self.assertRaises(GovernanceRejected):
            SyntheticFeasibilityDecisionDocket().intake_observation(
                replace(observation, minimum_evidence_count=1))

    def test_typed_upstream_semantic_aggregates_fail_closed_even_when_rehashed(self):
        base = {"portfolio_id": "synthetic:feasibility-portfolio:semantic",
            "observer": "synthetic:portfolio-observer:o",
            "intent_ids": ("synthetic:decision-intent:a",),
            "risk_counts": (("LOW", 0), ("MEDIUM", 0)),
            "kind_counts": (("SELF_CONTAINED", 1), ("BOUNDED_INTERNAL", 0),
                            ("SYNTHETIC_FIXTURE_ONLY", 0)),
            "all_rollback_possible": True, "minimum_evidence_count": 2}
        for mutation in (
            {},
            {"risk_counts": (("LOW", 1), ("HIGH", 0))},
            {"kind_counts": (("SELF_CONTAINED", 0), ("BOUNDED_INTERNAL", 0),
                             ("SYNTHETIC_FIXTURE_ONLY", 0))},
            {"all_rollback_possible": False},
            {"intent_ids": ("real:intent:a",), "risk_counts": (("LOW", 1), ("MEDIUM", 0))},
        ):
            payload = {**base, **mutation}
            observation = PortfolioObservation(**payload, digest=canonical_digest(payload))
            with self.assertRaises(GovernanceRejected):
                SyntheticFeasibilityDecisionDocket().intake_observation(observation)
        valid = {**base, "risk_counts": (("LOW", 1), ("MEDIUM", 0))}
        observation = PortfolioObservation(**valid, digest=canonical_digest(valid))
        with self.assertRaises(GovernanceRejected):
            SyntheticFeasibilityDecisionDocket().intake_observation(observation, 2)

    def test_batch_cap_order_idempotency_and_conflict(self):
        s = SyntheticFeasibilityDecisionDocket()
        for i in range(22): self.intake(s, f"{i:02}")
        batch = s.reserve_batch("synthetic:docket-batch:cap", MAX_DOCKET_BATCH)
        self.assertEqual((len(batch.portfolio_ids), batch.portfolio_ids[0][-2:]), (20, "00"))
        self.assertIs(batch, s.reserve_batch(batch.batch_id, 20))
        with self.assertRaises(GovernanceRejected): s.reserve_batch(batch.batch_id, 1)
        with self.assertRaises(GovernanceRejected): s.reserve_batch("synthetic:docket-batch:x", 21)

    def test_concurrent_batches_do_not_overlap(self):
        s = SyntheticFeasibilityDecisionDocket()
        for i in range(40): self.intake(s, f"{i:02}")
        with ThreadPoolExecutor(max_workers=2) as pool:
            batches = list(pool.map(lambda value:
                s.reserve_batch(f"synthetic:docket-batch:{value}", 20), (1, 2)))
        ids = batches[0].portfolio_ids + batches[1].portfolio_ids
        self.assertEqual(len(ids), len(set(ids)))

    def test_each_allowlisted_decision_is_inert(self):
        for index, decision in enumerate(sorted(DECISIONS)):
            s = SyntheticFeasibilityDecisionDocket()
            row = self.drafted(s, str(index), decision=decision)
            artifact = s._drafts[f"synthetic:decision-draft:{index}"]
            self.assertEqual((row.decision, row.status), (decision, "DOCKET_DRAFTED"))
            self.assertTrue(artifact.non_authorizing and artifact.non_deployable
                            and artifact.non_executable)

    def test_unknown_decision_fails_closed(self):
        s = SyntheticFeasibilityDecisionDocket(); row = self.batched(s)
        with self.assertRaises(GovernanceRejected):
            s.draft("synthetic:decision-draft:x", row.portfolio_id, row.version,
                row.source_version, row.portfolio_digest, "synthetic:docket-analyst:a",
                "APPROVE", digest("why"))

    def test_source_version_and_digest_are_bound(self):
        for version_offset, source_digest in ((1, None), (0, digest("wrong"))):
            s = SyntheticFeasibilityDecisionDocket(); row = self.batched(s)
            with self.assertRaises(GovernanceRejected):
                s.draft("synthetic:decision-draft:x", row.portfolio_id, row.version,
                    row.source_version + version_offset, source_digest or row.portfolio_digest,
                    "synthetic:docket-analyst:a", "OBSERVE", digest("why"))

    def test_observer_analyst_role_separation(self):
        s = SyntheticFeasibilityDecisionDocket(); row = self.batched(s, observer="same")
        with self.assertRaises(GovernanceRejected):
            s.draft("synthetic:decision-draft:x", row.portfolio_id, row.version,
                row.source_version, row.portfolio_digest, "synthetic:docket-analyst:same",
                "OBSERVE", digest("why"))

    def test_draft_idempotency_conflict_and_uniqueness(self):
        s = SyntheticFeasibilityDecisionDocket(); row = self.batched(s)
        args = ("synthetic:decision-draft:x", row.portfolio_id, row.version,
            row.source_version, row.portfolio_digest, "synthetic:docket-analyst:a",
            "OBSERVE", digest("why"))
        result = s.draft(*args); self.assertIs(result, s.draft(*args))
        with self.assertRaises(GovernanceRejected): s.draft(*args[:-1], digest("other"))
        with self.assertRaises(GovernanceRejected):
            s.draft("synthetic:decision-draft:y", *args[1:])

    def test_concurrent_exact_draft_converges(self):
        s = SyntheticFeasibilityDecisionDocket(); row = self.batched(s)
        args = ("synthetic:decision-draft:x", row.portfolio_id, row.version,
            row.source_version, row.portfolio_digest, "synthetic:docket-analyst:a",
            "OBSERVE", digest("why"))
        with ThreadPoolExecutor(max_workers=8) as pool:
            rows = list(pool.map(lambda _: s.draft(*args), range(32)))
        self.assertEqual(len({row.digest for row in rows}), 1)
        self.assertEqual(len(s._drafts), 1)

    def test_reviewer_is_independent(self):
        for identity in ("observer", "analyst"):
            s = SyntheticFeasibilityDecisionDocket(); row = self.drafted(s)
            with self.assertRaises(GovernanceRejected):
                s.review("synthetic:docket-review:x", row.portfolio_id, row.version,
                    f"synthetic:docket-reviewer:{identity}", True, digest("review"))

    def test_review_idempotency_conflict_and_stale_version(self):
        s = SyntheticFeasibilityDecisionDocket(); row = self.drafted(s)
        args = ("synthetic:docket-review:x", row.portfolio_id, row.version,
                "synthetic:docket-reviewer:r", True, digest("review"))
        result = s.review(*args); self.assertIs(result, s.review(*args))
        with self.assertRaises(GovernanceRejected): s.review(*args[:-1], digest("other"))
        with self.assertRaises(GovernanceRejected):
            s.review("synthetic:docket-review:y", row.portfolio_id, row.version - 1,
                     "synthetic:docket-reviewer:y", True, digest("y"))

    def test_rejected_review_creates_bound_auto_hold(self):
        s = SyntheticFeasibilityDecisionDocket(); row = self.drafted(s)
        row = s.review("synthetic:docket-review:x", row.portfolio_id, row.version,
            "synthetic:docket-reviewer:r", False, digest("reject"))
        self.assertEqual((row.status, row.hold_reason), ("HELD", "REVIEW_REJECTED"))
        self.assertTrue(s.evidence()["hold_chain_valid"])

    def test_verifier_is_fourth_independent_role(self):
        for identity in ("observer", "analyst", "reviewer"):
            s = SyntheticFeasibilityDecisionDocket(); row = self.reviewed(s)
            review = s.review_receipt("synthetic:docket-review:one")
            with self.assertRaises(GovernanceRejected):
                s.record_receipt("synthetic:docket-receipt:x", row.portfolio_id, row.version,
                    review.digest, f"synthetic:docket-verifier:{identity}")

    def test_receipt_is_inert_and_maximum_state_bounded(self):
        s = SyntheticFeasibilityDecisionDocket(); row = self.recorded(s)
        receipt = s.receipt("synthetic:docket-receipt:one")
        self.assertEqual(row.status, "SYNTHETIC_DECISION_DOCKET_RECORDED")
        self.assertTrue(receipt.non_authorizing and receipt.non_deployable
                        and receipt.non_executable)
        evidence = s.evidence()
        self.assertEqual(evidence["maximum_state"], row.status)
        self.assertEqual((evidence["external_calls"], evidence["ledger_writes"],
                          evidence["runtime_policy_mutations"]), (0, 0, 0))

    def test_receipt_idempotency_conflict_and_replay(self):
        s = SyntheticFeasibilityDecisionDocket(); row = self.reviewed(s)
        review = s.review_receipt("synthetic:docket-review:one")
        args = ("synthetic:docket-receipt:x", row.portfolio_id, row.version,
                review.digest, "synthetic:docket-verifier:v")
        result = s.record_receipt(*args); self.assertIs(result, s.record_receipt(*args))
        with self.assertRaises(GovernanceRejected):
            s.record_receipt(args[0], args[1], args[2], args[3],
                             "synthetic:docket-verifier:z")
        s._portfolio_receipts.pop(row.portfolio_id)
        with self.assertRaises(GovernanceRejected):
            s.record_receipt("synthetic:docket-receipt:y", row.portfolio_id, row.version,
                             review.digest, "synthetic:docket-verifier:z")

    def test_concurrent_exact_receipt_converges(self):
        s = SyntheticFeasibilityDecisionDocket(); row = self.reviewed(s)
        review = s.review_receipt("synthetic:docket-review:one")
        args = ("synthetic:docket-receipt:x", row.portfolio_id, row.version,
                review.digest, "synthetic:docket-verifier:v")
        with ThreadPoolExecutor(max_workers=8) as pool:
            rows = list(pool.map(lambda _: s.record_receipt(*args), range(32)))
        self.assertEqual(len({row.digest for row in rows}), 1)
        self.assertEqual(len(s._receipts), 1)

    def test_integrity_drift_hold_and_auditor_separation(self):
        s = SyntheticFeasibilityDecisionDocket(); row = self.drafted(s)
        with self.assertRaises(GovernanceRejected):
            s.hold_integrity_drift(row.portfolio_id, row.version,
                "synthetic:docket-auditor:analyst", digest("finding"))
        row = s.hold_integrity_drift(row.portfolio_id, row.version,
            "synthetic:docket-auditor:audit", digest("finding"))
        self.assertEqual((row.status, row.hold_reason), ("HELD", "INTEGRITY_DRIFT"))

    def test_post_receipt_auditor_must_differ_from_verifier(self):
        s = SyntheticFeasibilityDecisionDocket(); row = self.recorded(s, verifier="same")
        with self.assertRaises(GovernanceRejected):
            s.hold_integrity_drift(row.portfolio_id, row.version,
                "synthetic:docket-auditor:same", digest("finding"))

    def test_tampered_record_event_batch_artifact_and_hold_are_detected(self):
        services = []
        s1 = SyntheticFeasibilityDecisionDocket(); self.recorded(s1); services.append(s1)
        s2 = SyntheticFeasibilityDecisionDocket(); self.recorded(s2); services.append(s2)
        s3 = SyntheticFeasibilityDecisionDocket(); self.recorded(s3); services.append(s3)
        s4 = SyntheticFeasibilityDecisionDocket(); self.recorded(s4); services.append(s4)
        s5 = SyntheticFeasibilityDecisionDocket(); row = self.drafted(s5)
        s5.hold_integrity_drift(row.portfolio_id, row.version,
            "synthetic:docket-auditor:audit", digest("finding")); services.append(s5)
        services[0]._history[0] = replace(services[0]._history[0], member_count=2)
        services[1]._events[0]["action"] = "TAMPER"
        batch = services[2]._batches["synthetic:docket-batch:one"]
        services[2]._batches[batch.batch_id] = replace(batch, requested_limit=2)
        draft = services[3]._drafts["synthetic:decision-draft:one"]
        services[3]._drafts[draft.draft_id] = replace(draft, decision="HOLD")
        services[4]._holds[0]["reason"] = "TAMPER"
        keys = ("record_integrity_valid", "event_chain_valid", "batch_integrity_valid",
                "artifact_integrity_valid", "hold_chain_valid")
        for service, key in zip(services, keys): self.assertFalse(service.evidence()[key])

    def test_semantic_event_tamper_fails_even_after_rehash(self):
        s = SyntheticFeasibilityDecisionDocket(); self.recorded(s)
        event = s._events[0]
        event["action"] = "DOCKET_REVIEWED"
        payload = {key: event[key] for key in (
            "sequence", "action", "record_digest", "attachment_digest", "previous_digest")}
        event["digest"] = canonical_digest(payload)
        self.assertFalse(s.evidence()["event_chain_valid"])

    def test_evidence_is_deterministic(self):
        def produce():
            service = SyntheticFeasibilityDecisionDocket(); self.recorded(service)
            return service.evidence()
        self.assertEqual(produce(), produce())

    def test_evidence_reports_all_integrity_chains(self):
        s = SyntheticFeasibilityDecisionDocket(); self.recorded(s)
        evidence = s.evidence()
        self.assertTrue(evidence["integrity_valid"])
        self.assertTrue(all(evidence[key] for key in (
            "record_integrity_valid", "event_chain_valid", "batch_integrity_valid",
            "artifact_integrity_valid", "hold_chain_valid")))

    def test_capability_gap_evidence_is_ready_and_audit_observable(self):
        s = SyntheticFeasibilityDecisionDocket(); self.recorded(s)
        result = s.capability_gap_evidence()
        self.assertEqual((result["observed_count"], result["missing_controls"],
                          result["capability_gaps"]), (200, (), ()))
        self.assertFalse(result["fail_closed"])
        self.assertTrue(result["audit_observable"])
        self.assertTrue(s.evidence()["capability_ready"])

    def test_missing_control_self_assessment_fails_closed(self):
        import nurion_pg.synthetic_feasibility_decision_docket as module
        broken = module.WORKSTREAMS[:-1] + ((2677, 2700, "BROKEN"),)
        with patch.object(module, "WORKSTREAMS", broken):
            result = SyntheticFeasibilityDecisionDocket().capability_gap_evidence()
        self.assertTrue(result["fail_closed"])
        self.assertEqual(result["missing_controls"], (2676,))
        self.assertIn("CONTROL_MATRIX_GAP", result["capability_gaps"])

    def test_integrity_tamper_self_assessment_fails_closed(self):
        s = SyntheticFeasibilityDecisionDocket(); self.recorded(s)
        s._events[0]["action"] = "TAMPER"
        result = s.capability_gap_evidence()
        self.assertTrue(result["fail_closed"])
        self.assertIn("INTEGRITY_OBSERVABILITY_GAP", result["capability_gaps"])


if __name__ == "__main__":
    unittest.main()
