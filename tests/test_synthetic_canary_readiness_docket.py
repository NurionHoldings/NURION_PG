from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from hashlib import sha256
import unittest

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.synthetic_canary_readiness_docket import (
    MAX_PORTFOLIO_BATCH, SyntheticCanaryReadinessDocket,
)


def digest(value): return sha256(value.encode()).hexdigest()


class ReadinessDocketTests(unittest.TestCase):
    def intake(self, service, name, sample=100, completion=9000, error=100, latency=500):
        return service.intake(f"synthetic:completed-canary:{name}", digest(f"complete:{name}"),
                              sample, completion, error, latency)

    def batched(self, service, name="one", **kwargs):
        row = self.intake(service, name, **kwargs)
        service.reserve_portfolio(f"synthetic:readiness-batch:{name}", 1)
        return service.get(row.canary_id)

    def aggregated(self, service, name="one", samples=100, completed=90, errors=1, latency=500, **kwargs):
        row = self.batched(service, name, **kwargs)
        return service.aggregate(row.canary_id, row.version, "synthetic:aggregator:a", samples,
                                 completed, errors, latency, digest(f"metrics:{name}"))

    def reviewed(self, service, name="one"):
        row = self.aggregated(service, name)
        row = service.review(f"synthetic:readiness-docket:{name}", row.canary_id, row.version,
                             "synthetic:reviewer:b", True, digest(f"review:{name}"))
        return row

    def test_intake_idempotency_and_conflict(self):
        s = SyntheticCanaryReadinessDocket(); row = self.intake(s, "a")
        self.assertIs(row, self.intake(s, "a"))
        with self.assertRaises(GovernanceRejected):
            s.intake(row.canary_id, digest("other"), 100, 9000, 100, 500)

    def test_portfolio_cap_order_idempotency_conflict(self):
        s = SyntheticCanaryReadinessDocket()
        for i in range(22): self.intake(s, f"{i:02}")
        b = s.reserve_portfolio("synthetic:readiness-batch:cap", MAX_PORTFOLIO_BATCH)
        self.assertEqual((len(b.canary_ids), b.canary_ids[0][-2:]), (20, "00"))
        self.assertIs(b, s.reserve_portfolio(b.batch_id, 20))
        with self.assertRaises(GovernanceRejected): s.reserve_portfolio(b.batch_id, 1)
        with self.assertRaises(GovernanceRejected): s.reserve_portfolio("synthetic:readiness-batch:x", 21)

    def test_concurrent_portfolios_never_overlap(self):
        s = SyntheticCanaryReadinessDocket()
        for i in range(40): self.intake(s, f"{i:02}")
        with ThreadPoolExecutor(max_workers=2) as pool:
            batches = list(pool.map(lambda n: s.reserve_portfolio(f"synthetic:readiness-batch:{n}", 20), (1,2)))
        ids = batches[0].canary_ids + batches[1].canary_ids
        self.assertEqual(len(ids), len(set(ids)))

    def test_exact_integer_thresholds_pass(self):
        s = SyntheticCanaryReadinessDocket()
        row = self.aggregated(s, "edge", samples=3, completed=2, errors=1,
                              sample=3, completion=6666, error=3334, latency=500)
        self.assertEqual(row.status, "METRICS_ACCEPTED")

    def test_fractional_completion_below_threshold_holds(self):
        s = SyntheticCanaryReadinessDocket()
        row = self.aggregated(s, "fraction", samples=3, completed=2, errors=0,
                              sample=3, completion=6667, error=0, latency=100)
        self.assertEqual((row.status, row.hold_reason), ("HELD", "COMPLETION_REGRESSION"))

    def test_fractional_error_above_threshold_holds(self):
        s = SyntheticCanaryReadinessDocket()
        row = self.aggregated(s, "error", samples=3, completed=3, errors=1,
                              sample=3, completion=10000, error=3333, latency=100)
        self.assertEqual(row.hold_reason, "ERROR_REGRESSION")

    def test_minimum_sample_and_latency_holds(self):
        s = SyntheticCanaryReadinessDocket()
        self.assertEqual(self.aggregated(s, "sample", samples=99, completed=99,
                         errors=0, latency=100).hold_reason, "INSUFFICIENT_SAMPLE")
        self.assertEqual(self.aggregated(s, "slow", samples=100, completed=100,
                         errors=0, latency=501).hold_reason, "LATENCY_REGRESSION")

    def test_error_count_cannot_exceed_completed_count(self):
        s = SyntheticCanaryReadinessDocket(); row = self.batched(s, "contradictory")
        with self.assertRaises(GovernanceRejected):
            s.aggregate(row.canary_id, row.version, "synthetic:aggregator:a",
                        100, 1, 2, 100, digest("contradictory"))

    def test_aggregate_idempotency_and_conflict(self):
        s = SyntheticCanaryReadinessDocket(); row = self.batched(s, "idem")
        args = (row.canary_id, row.version, "synthetic:aggregator:a", 100, 90, 1, 500, digest("m"))
        result = s.aggregate(*args)
        self.assertIs(result, s.aggregate(*args))
        with self.assertRaises(GovernanceRejected): s.aggregate(*args[:-2], 499, args[-1])

    def test_independent_review_and_maximum_state(self):
        s = SyntheticCanaryReadinessDocket(); row = self.aggregated(s, "roles")
        with self.assertRaises(GovernanceRejected):
            s.review("synthetic:readiness-docket:roles", row.canary_id, row.version,
                     "synthetic:reviewer:a", True, digest("r"))
        row = s.review("synthetic:readiness-docket:roles", row.canary_id, row.version,
                       "synthetic:reviewer:b", True, digest("r"))
        self.assertEqual(row.status, "SYNTHETIC_READINESS_REVIEWED")

    def test_review_rechecks_upstream_integrity(self):
        s = SyntheticCanaryReadinessDocket(); row = self.aggregated(s, "review-integrity")
        receipt = s._metrics[row.canary_id]
        s._metrics[row.canary_id] = replace(receipt, completed_count=receipt.completed_count - 1)
        with self.assertRaises(GovernanceRejected):
            s.review("synthetic:readiness-docket:review-integrity", row.canary_id,
                     row.version, "synthetic:reviewer:b", True, digest("review-integrity"))

    def test_review_rejection_holds_and_docket_is_bound(self):
        s = SyntheticCanaryReadinessDocket(); row = self.aggregated(s, "reject")
        row = s.review("synthetic:readiness-docket:reject", row.canary_id, row.version,
                       "synthetic:reviewer:b", False, digest("r"))
        self.assertEqual((row.status, row.hold_reason), ("HELD", "REVIEW_REJECTED"))
        self.assertTrue(s.evidence()["receipt_integrity_valid"])

    def test_unauthorized_docket_cross_replay_and_reuse_blocked(self):
        s = SyntheticCanaryReadinessDocket(); first = self.reviewed(s, "first")
        second = self.reviewed(s, "second")
        docket = s.docket("synthetic:readiness-docket:first")
        with self.assertRaises(GovernanceRejected):
            s.verify_docket(second.canary_id, second.version, docket.digest, "synthetic:verifier:c")
        with self.assertRaises(GovernanceRejected):
            s.verify_docket(first.canary_id, first.version, digest("fabricated"), "synthetic:verifier:c")
        self.assertIs(first, s.verify_docket(first.canary_id, first.version, docket.digest,
                                             "synthetic:verifier:c"))
        with self.assertRaises(GovernanceRejected):
            s.verify_docket(first.canary_id, first.version, docket.digest, "synthetic:verifier:d")

    def test_verifier_role_separation(self):
        s = SyntheticCanaryReadinessDocket(); row = self.reviewed(s, "verify-role")
        docket = s.docket("synthetic:readiness-docket:verify-role")
        with self.assertRaises(GovernanceRejected):
            s.verify_docket(row.canary_id, row.version, docket.digest, "synthetic:verifier:b")

    def test_verifier_identity_is_preserved_in_replay_evidence(self):
        s = SyntheticCanaryReadinessDocket(); row = self.reviewed(s, "verifier-evidence")
        docket = s.docket("synthetic:readiness-docket:verifier-evidence")
        s.verify_docket(row.canary_id, row.version, docket.digest, "synthetic:verifier:c")
        self.assertTrue(s.evidence()["docket_replay_index_valid"])
        s._docket_verifiers[docket.digest] = "synthetic:verifier:b"
        self.assertFalse(s.evidence()["docket_replay_index_valid"])

    def test_stale_version_and_second_docket_fail_closed(self):
        s = SyntheticCanaryReadinessDocket(); row = self.aggregated(s, "stale")
        s.review("synthetic:readiness-docket:one", row.canary_id, row.version,
                 "synthetic:reviewer:b", True, digest("r"))
        with self.assertRaises(GovernanceRejected):
            s.review("synthetic:readiness-docket:two", row.canary_id, row.version,
                     "synthetic:reviewer:c", True, digest("r2"))

    def test_history_event_hold_and_batch_tamper_detected(self):
        s = SyntheticCanaryReadinessDocket(); self.aggregated(s, "held", samples=99, completed=99, errors=0, latency=1)
        self.assertTrue(s.evidence()["history_chain_valid"])
        s._holds[0]["reason"] = "LATENCY_REGRESSION"
        self.assertFalse(s.evidence()["hold_chain_valid"])

    def test_semantic_event_attachment_tamper_detected_even_if_rehashed(self):
        s = SyntheticCanaryReadinessDocket(); row = self.reviewed(s, "semantic")
        event = next(e for e in s._events if e["action"] == "READINESS_REVIEWED")
        event["attachment_digest"] = s._metrics[row.canary_id].digest
        previous = None
        for index, item in enumerate(s._events, 1):
            item["sequence"], item["previous_digest"] = index, previous
            payload = {k: item[k] for k in ("sequence", "action", "record_digest", "attachment_digest", "previous_digest")}
            item["digest"] = canonical_digest(payload); previous = item["digest"]
        self.assertFalse(s.evidence()["event_chain_valid"])

    def test_docket_version_binding_tamper_blocks_verification(self):
        s = SyntheticCanaryReadinessDocket(); row = self.reviewed(s, "tamper")
        docket = s.docket("synthetic:readiness-docket:tamper")
        s._dockets[docket.docket_id] = replace(docket, source_version=docket.source_version - 1)
        with self.assertRaises(GovernanceRejected):
            s.verify_docket(row.canary_id, row.version, docket.digest, "synthetic:verifier:c")

    def test_replay_index_tamper_reports_false_without_crashing(self):
        s = SyntheticCanaryReadinessDocket(); row = self.reviewed(s, "index")
        docket = s.docket("synthetic:readiness-docket:index")
        s._used_dockets[docket.digest] = "synthetic:completed-canary:missing"
        self.assertFalse(s.evidence()["docket_replay_index_valid"])

    def test_feature_map_and_safety_flags(self):
        evidence = SyntheticCanaryReadinessDocket().evidence()
        self.assertEqual(evidence["features"], list(range(1501, 1701)))
        self.assertEqual(evidence["feature_count"], 200)
        self.assertTrue(all(w["control_count"] == 25 for w in evidence["workstreams"]))
        self.assertEqual(evidence["maximum_state"], "SYNTHETIC_READINESS_REVIEWED")
        for key, value in evidence.items():
            if key.endswith(("_allowed", "_used", "_accessed")): self.assertFalse(value, key)

    def test_invalid_inputs_fail_closed(self):
        s = SyntheticCanaryReadinessDocket()
        with self.assertRaises(GovernanceRejected): s.intake("prod:x", digest("x"), 1, 1, 1, 1)
        row = self.batched(s, "invalid")
        with self.assertRaises(GovernanceRejected):
            s.aggregate(row.canary_id, row.version, "prod:actor", 1, 1, 0, 1, digest("x"))


if __name__ == "__main__": unittest.main()
