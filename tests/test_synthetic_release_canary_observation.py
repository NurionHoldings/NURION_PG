from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
import unittest

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.synthetic_release_canary_observation import MAX_CANARY_BATCH, SyntheticReleaseCanaryObservation


NOW = datetime(2026, 9, 18, tzinfo=UTC)


def digest(value): return sha256(value.encode()).hexdigest()


class CanaryTests(unittest.TestCase):
    def intake(self, service, name, error=100, latency=500):
        return service.intake(f"synthetic:canary:{name}", digest(f"release:{name}"), error, latency)

    def observed(self, service, name="one", errors=0, latency=100, observer="synthetic:observer:a"):
        row = self.intake(service, name)
        service.reserve_batch(f"synthetic:canary-batch:{name}", 1)
        row = service.get(row.canary_id)
        return service.observe(row.canary_id, row.version, observer, 100, errors, latency, digest(f"obs:{name}"))

    def reviewed(self, service, name="one"):
        row = self.observed(service, name)
        return service.review(row.canary_id, row.version, "synthetic:reviewer:b", True, digest(f"review:{name}"))

    def test_intake_idempotent_and_conflict(self):
        s = SyntheticReleaseCanaryObservation(); row = self.intake(s, "a")
        self.assertIs(row, self.intake(s, "a"))
        with self.assertRaises(GovernanceRejected): s.intake(row.canary_id, digest("other"), 100, 500)

    def test_batch_cap_order_idempotency_and_conflict(self):
        s = SyntheticReleaseCanaryObservation()
        for i in range(12): self.intake(s, f"{i:02}")
        batch = s.reserve_batch("synthetic:canary-batch:cap", MAX_CANARY_BATCH)
        self.assertEqual(len(batch.canary_ids), 10)
        self.assertIs(batch, s.reserve_batch(batch.batch_id, 10))
        with self.assertRaises(GovernanceRejected): s.reserve_batch(batch.batch_id, 1)
        with self.assertRaises(GovernanceRejected): s.reserve_batch("synthetic:canary-batch:over", 11)

    def test_concurrent_batches_do_not_overlap(self):
        s = SyntheticReleaseCanaryObservation()
        for i in range(20): self.intake(s, f"{i:02}")
        with ThreadPoolExecutor(max_workers=2) as p:
            batches = list(p.map(lambda n: s.reserve_batch(f"synthetic:canary-batch:{n}", 10), (1,2)))
        ids = batches[0].canary_ids + batches[1].canary_ids
        self.assertEqual(len(ids), len(set(ids)))

    def test_threshold_exact_boundaries_pass(self):
        s = SyntheticReleaseCanaryObservation(); row = self.intake(s, "edge", 100, 500)
        s.reserve_batch("synthetic:canary-batch:edge", 1); row = s.get(row.canary_id)
        row = s.observe(row.canary_id, row.version, "synthetic:observer:a", 100, 1, 500, digest("edge"))
        self.assertEqual(row.status, "THRESHOLD_PASSED")

    def test_fractional_error_rate_above_budget_is_held(self):
        s = SyntheticReleaseCanaryObservation(); row = self.intake(s, "fraction", 3333, 500)
        s.reserve_batch("synthetic:canary-batch:fraction", 1); row = s.get(row.canary_id)
        row = s.observe(row.canary_id, row.version, "synthetic:observer:a", 3, 1, 100, digest("fraction"))
        self.assertEqual((row.status, row.hold_reason), ("HELD", "ERROR_RATE_REGRESSION"))

    def test_error_regression_auto_holds(self):
        s = SyntheticReleaseCanaryObservation(); row = self.observed(s, "err", errors=2)
        self.assertEqual((row.status, row.hold_reason), ("HELD", "ERROR_RATE_REGRESSION"))

    def test_latency_regression_auto_holds(self):
        s = SyntheticReleaseCanaryObservation(); row = self.observed(s, "slow", latency=501)
        self.assertEqual((row.status, row.hold_reason), ("HELD", "LATENCY_REGRESSION"))

    def test_observation_idempotency_and_conflict(self):
        s = SyntheticReleaseCanaryObservation(); row = self.intake(s, "idem")
        s.reserve_batch("synthetic:canary-batch:idem", 1); row = s.get(row.canary_id)
        result = s.observe(row.canary_id, row.version, "synthetic:observer:a", 10, 0, 10, digest("obs"))
        self.assertIs(result, s.observe(row.canary_id, row.version, "synthetic:observer:a", 10, 0, 10, digest("obs")))
        with self.assertRaises(GovernanceRejected): s.observe(row.canary_id, row.version, "synthetic:observer:a", 10, 1, 10, digest("obs"))

    def test_review_requires_independent_role(self):
        s = SyntheticReleaseCanaryObservation(); row = self.observed(s, "role")
        with self.assertRaises(GovernanceRejected): s.review(row.canary_id, row.version, "synthetic:reviewer:a", True, digest("r"))
        row = s.review(row.canary_id, row.version, "synthetic:reviewer:b", True, digest("r"))
        self.assertEqual(row.status, "REVIEW_APPROVED")

    def test_review_rejection_auto_holds(self):
        s = SyntheticReleaseCanaryObservation(); row = self.observed(s, "reject")
        row = s.review(row.canary_id, row.version, "synthetic:reviewer:b", False, digest("r"))
        self.assertEqual(row.hold_reason, "REVIEW_REJECTED")

    def test_completion_receipt_version_binding_and_replay(self):
        s = SyntheticReleaseCanaryObservation(); row = self.reviewed(s, "done")
        row = s.issue_completion(row.canary_id, row.version, "synthetic:issuer:c", NOW)
        receipt = s._receipts[row.canary_id]
        with self.assertRaises(GovernanceRejected): s.complete(row.canary_id, row.version - 1, receipt.digest)
        row = s.complete(row.canary_id, row.version, receipt.digest)
        self.assertEqual(row.status, "OBSERVATION_COMPLETE")
        with self.assertRaises(GovernanceRejected): s.complete(row.canary_id, row.version, receipt.digest)

    def test_issuer_role_separation(self):
        s = SyntheticReleaseCanaryObservation(); row = self.reviewed(s, "issuer")
        with self.assertRaises(GovernanceRejected): s.issue_completion(row.canary_id, row.version, "synthetic:issuer:b", NOW)

    def test_receipt_tamper_blocks_completion(self):
        s = SyntheticReleaseCanaryObservation(); row = self.reviewed(s, "tamper")
        row = s.issue_completion(row.canary_id, row.version, "synthetic:issuer:c", NOW)
        receipt = s._receipts[row.canary_id]
        s._reviews[row.canary_id] = replace(s._reviews[row.canary_id], approved=False)
        with self.assertRaises(GovernanceRejected): s.complete(row.canary_id, row.version, receipt.digest)

    def test_current_index_tamper_blocks_completion(self):
        s = SyntheticReleaseCanaryObservation(); row = self.reviewed(s, "row-tamper")
        row = s.issue_completion(row.canary_id, row.version, "synthetic:issuer:c", NOW)
        receipt = s._receipts[row.canary_id]
        s._rows[row.canary_id] = replace(row, latency_budget_ms=501)
        with self.assertRaises(GovernanceRejected):
            s.complete(row.canary_id, row.version, receipt.digest)

    def test_history_event_batch_hold_tamper_detected(self):
        s = SyntheticReleaseCanaryObservation(); self.observed(s, "audit", errors=2)
        self.assertTrue(s.evidence()["history_chain_valid"])
        s._events[0]["action"] = "TAMPERED"
        self.assertFalse(s.evidence()["event_chain_valid"])

    def test_recomputed_but_semantically_wrong_attachment_is_detected(self):
        s = SyntheticReleaseCanaryObservation(); row = self.reviewed(s, "semantic")
        event = next(e for e in s._events if e["action"] == "REVIEW_APPROVED")
        event["attachment_digest"] = s._observations[row.canary_id].digest
        previous = None
        for sequence, item in enumerate(s._events, 1):
            item["sequence"] = sequence
            item["previous_digest"] = previous
            payload = {k: item[k] for k in ("sequence", "action", "record_digest", "attachment_digest", "previous_digest")}
            item["digest"] = canonical_digest(payload)
            previous = item["digest"]
        self.assertFalse(s.evidence()["event_chain_valid"])

    def test_portfolio_and_safety_flags(self):
        e = SyntheticReleaseCanaryObservation().evidence()
        self.assertEqual(e["features"], list(range(1301,1501)))
        self.assertEqual(e["feature_count"], 200)
        self.assertTrue(all(w["control_count"] == 25 for w in e["workstreams"]))
        for k,v in e.items():
            if k.endswith(("_allowed", "_used", "_recorded", "_accessed")): self.assertFalse(v, k)

    def test_invalid_inputs_and_stale_version_fail_closed(self):
        s = SyntheticReleaseCanaryObservation()
        with self.assertRaises(GovernanceRejected): s.intake("prod:x", digest("x"), 1, 1)
        row = self.intake(s, "stale"); s.reserve_batch("synthetic:canary-batch:stale", 1)
        with self.assertRaises(GovernanceRejected): s.observe(row.canary_id, 99, "synthetic:observer:a", 1, 0, 1, digest("x"))


if __name__ == "__main__": unittest.main()
