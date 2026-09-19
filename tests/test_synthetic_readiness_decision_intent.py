from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from hashlib import sha256
import unittest

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.synthetic_readiness_decision_intent import (
    INTENT_KINDS, MAX_INTENT_BATCH, SyntheticReadinessDecisionIntent,
)


def digest(value): return sha256(value.encode()).hexdigest()


class ReadinessDecisionIntentTests(unittest.TestCase):
    def intake(self, service, name):
        return service.intake(f"synthetic:readiness-docket:{name}", digest(f"ready:{name}"))

    def batched(self, service, name="one"):
        row = self.intake(service, name)
        service.reserve_batch(f"synthetic:intent-batch:{name}", 1)
        return service.get(row.docket_id)

    def drafted(self, service, name="one", operator="a", kind="PROCEED_TO_SYNTHETIC_PLANNING"):
        row = self.batched(service, name)
        return service.draft(f"synthetic:intent-draft:{name}", row.docket_id, row.version,
                             f"synthetic:operator:{operator}", kind, digest(f"why:{name}"))

    def reviewed(self, service, name="one", operator="a", reviewer="b"):
        row = self.drafted(service, name, operator)
        return service.review(f"synthetic:intent-review:{name}", row.docket_id, row.version,
                              f"synthetic:reviewer:{reviewer}", True,
                              digest(f"review:{name}"))

    def recorded(self, service, name="one", operator="a", reviewer="b", verifier="c"):
        row = self.reviewed(service, name, operator, reviewer)
        review = service.review_receipt(f"synthetic:intent-review:{name}")
        return service.record_receipt(f"synthetic:intent-receipt:{name}", row.docket_id,
                                      row.version, review.digest,
                                      f"synthetic:verifier:{verifier}")

    def test_intake_idempotency_and_conflict(self):
        s = SyntheticReadinessDecisionIntent(); row = self.intake(s, "a")
        self.assertIs(row, self.intake(s, "a"))
        with self.assertRaises(GovernanceRejected):
            s.intake(row.docket_id, digest("different"))

    def test_batch_cap_order_idempotency_and_conflict(self):
        s = SyntheticReadinessDecisionIntent()
        for i in range(22): self.intake(s, f"{i:02}")
        batch = s.reserve_batch("synthetic:intent-batch:cap", MAX_INTENT_BATCH)
        self.assertEqual((len(batch.docket_ids), batch.docket_ids[0][-2:]), (20, "00"))
        self.assertIs(batch, s.reserve_batch(batch.batch_id, 20))
        with self.assertRaises(GovernanceRejected): s.reserve_batch(batch.batch_id, 1)
        with self.assertRaises(GovernanceRejected): s.reserve_batch("synthetic:intent-batch:x", 21)

    def test_concurrent_batches_never_overlap(self):
        s = SyntheticReadinessDecisionIntent()
        for i in range(40): self.intake(s, f"{i:02}")
        with ThreadPoolExecutor(max_workers=2) as pool:
            batches = list(pool.map(
                lambda n: s.reserve_batch(f"synthetic:intent-batch:{n}", 20), (1, 2)))
        ids = batches[0].docket_ids + batches[1].docket_ids
        self.assertEqual(len(ids), len(set(ids)))

    def test_each_allowlisted_intent_kind_records(self):
        for index, kind in enumerate(sorted(INTENT_KINDS)):
            s = SyntheticReadinessDecisionIntent()
            row = self.drafted(s, str(index), kind=kind)
            self.assertEqual((row.intent_kind, row.status), (kind, "INTENT_DRAFTED"))

    def test_unknown_intent_kind_fails_closed(self):
        s = SyntheticReadinessDecisionIntent(); row = self.batched(s, "unknown")
        with self.assertRaises(GovernanceRejected):
            s.draft("synthetic:intent-draft:unknown", row.docket_id, row.version,
                    "synthetic:operator:a", "DEPLOY", digest("why"))

    def test_draft_idempotency_conflict_and_owner_uniqueness(self):
        s = SyntheticReadinessDecisionIntent(); base = self.batched(s, "draft")
        args = ("synthetic:intent-draft:draft", base.docket_id, base.version,
                "synthetic:operator:a", "HOLD_FOR_REVIEW", digest("why"))
        row = s.draft(*args); self.assertIs(row, s.draft(*args))
        with self.assertRaises(GovernanceRejected): s.draft(*args[:-1], digest("other"))
        with self.assertRaises(GovernanceRejected):
            s.draft("synthetic:intent-draft:second", base.docket_id, base.version,
                    "synthetic:operator:a", "HOLD_FOR_REVIEW", digest("why"))

    def test_concurrent_exact_draft_converges(self):
        s = SyntheticReadinessDecisionIntent(); base = self.batched(s, "draft-race")
        args = ("synthetic:intent-draft:draft-race", base.docket_id, base.version,
                "synthetic:operator:a", "HOLD_FOR_REVIEW", digest("race"))
        with ThreadPoolExecutor(max_workers=8) as pool:
            rows = list(pool.map(lambda _: s.draft(*args), range(32)))
        self.assertEqual({row.digest for row in rows}, {rows[0].digest})
        self.assertEqual(sum(r.docket_id == base.docket_id for r in s._history), 3)

    def test_operator_and_reviewer_must_be_independent(self):
        s = SyntheticReadinessDecisionIntent(); row = self.drafted(s, "roles")
        with self.assertRaises(GovernanceRejected):
            s.review("synthetic:intent-review:roles", row.docket_id, row.version,
                     "synthetic:reviewer:a", True, digest("review"))

    def test_review_idempotency_conflict_and_version_binding(self):
        s = SyntheticReadinessDecisionIntent(); row = self.drafted(s, "review")
        args = ("synthetic:intent-review:review", row.docket_id, row.version,
                "synthetic:reviewer:b", True, digest("review"))
        result = s.review(*args); self.assertIs(result, s.review(*args))
        with self.assertRaises(GovernanceRejected): s.review(*args[:-1], digest("other"))
        with self.assertRaises(GovernanceRejected):
            s.review("synthetic:intent-review:stale", row.docket_id, row.version - 1,
                     "synthetic:reviewer:c", True, digest("stale"))

    def test_review_rejection_creates_bound_auto_hold(self):
        s = SyntheticReadinessDecisionIntent(); row = self.drafted(s, "reject")
        row = s.review("synthetic:intent-review:reject", row.docket_id, row.version,
                       "synthetic:reviewer:b", False, digest("reject"))
        self.assertEqual((row.status, row.hold_reason), ("HELD", "REVIEW_REJECTED"))
        evidence = s.evidence()
        self.assertTrue(evidence["hold_chain_valid"])
        self.assertTrue(evidence["event_chain_valid"])

    def test_integrity_finding_creates_bound_auto_hold(self):
        s = SyntheticReadinessDecisionIntent(); row = self.drafted(s, "integrity-hold")
        row = s.hold_integrity_drift("synthetic:integrity-finding:one", row.docket_id,
                                     row.version, "synthetic:auditor:guard",
                                     digest("integrity-drift"))
        self.assertEqual((row.status, row.hold_reason), ("HELD", "INTEGRITY_DRIFT"))
        evidence = s.evidence()
        self.assertTrue(evidence["artifact_integrity_valid"])
        self.assertTrue(evidence["hold_chain_valid"])

    def test_integrity_finding_idempotency_and_conflict(self):
        s = SyntheticReadinessDecisionIntent(); row = self.batched(s, "finding-idem")
        args = ("synthetic:integrity-finding:idem", row.docket_id, row.version,
                "synthetic:auditor:guard", digest("finding"))
        result = s.hold_integrity_drift(*args)
        self.assertIs(result, s.hold_integrity_drift(*args))
        with self.assertRaises(GovernanceRejected):
            s.hold_integrity_drift(*args[:-1], digest("other"))

    def test_integrity_auditor_must_be_independent(self):
        s = SyntheticReadinessDecisionIntent(); row = self.drafted(s, "auditor-operator")
        with self.assertRaises(GovernanceRejected):
            s.hold_integrity_drift("synthetic:integrity-finding:operator",
                row.docket_id, row.version, "synthetic:auditor:a", digest("operator"))

        s2 = SyntheticReadinessDecisionIntent(); row2 = self.reviewed(s2, "auditor-reviewer")
        with self.assertRaises(GovernanceRejected):
            s2.hold_integrity_drift("synthetic:integrity-finding:reviewer",
                row2.docket_id, row2.version, "synthetic:auditor:b", digest("reviewer"))

    def test_verifier_is_third_independent_role(self):
        for verifier in ("a", "b"):
            s = SyntheticReadinessDecisionIntent(); row = self.reviewed(s, verifier)
            review = s.review_receipt(f"synthetic:intent-review:{verifier}")
            with self.assertRaises(GovernanceRejected):
                s.record_receipt(f"synthetic:intent-receipt:{verifier}", row.docket_id,
                                 row.version, review.digest,
                                 f"synthetic:verifier:{verifier}")

    def test_receipt_is_inert_and_maximum_state_is_bounded(self):
        s = SyntheticReadinessDecisionIntent(); row = self.recorded(s, "inert")
        receipt = s.receipt("synthetic:intent-receipt:inert")
        self.assertEqual(row.status, "SYNTHETIC_INTENT_RECORDED")
        self.assertTrue(receipt.non_authorizing and receipt.non_executable)
        self.assertEqual(s.evidence()["maximum_state"], "SYNTHETIC_INTENT_RECORDED")

    def test_receipt_idempotency_and_conflict(self):
        s = SyntheticReadinessDecisionIntent(); row = self.reviewed(s, "receipt")
        review = s.review_receipt("synthetic:intent-review:receipt")
        args = ("synthetic:intent-receipt:receipt", row.docket_id, row.version,
                review.digest, "synthetic:verifier:c")
        result = s.record_receipt(*args); self.assertIs(result, s.record_receipt(*args))
        with self.assertRaises(GovernanceRejected):
            s.record_receipt(args[0], args[1], args[2], args[3], "synthetic:verifier:d")

    def test_concurrent_exact_receipt_records_once(self):
        s = SyntheticReadinessDecisionIntent(); row = self.reviewed(s, "receipt-race")
        review = s.review_receipt("synthetic:intent-review:receipt-race")
        args = ("synthetic:intent-receipt:receipt-race", row.docket_id, row.version,
                review.digest, "synthetic:verifier:c")
        with ThreadPoolExecutor(max_workers=8) as pool:
            rows = list(pool.map(lambda _: s.record_receipt(*args), range(32)))
        self.assertEqual({item.digest for item in rows}, {rows[0].digest})
        self.assertEqual(len(s._receipts), 1)

    def test_cross_docket_review_replay_is_blocked(self):
        s = SyntheticReadinessDecisionIntent()
        first = self.reviewed(s, "first")
        first_review = s.review_receipt("synthetic:intent-review:first")
        second = self.reviewed(s, "second")
        with self.assertRaises(GovernanceRejected):
            s.record_receipt("synthetic:intent-receipt:swap", second.docket_id,
                             second.version, first_review.digest, "synthetic:verifier:c")
        self.assertEqual(first.status, "INTENT_REVIEWED")

    def test_same_review_digest_cannot_be_reused(self):
        s = SyntheticReadinessDecisionIntent(); self.recorded(s, "used")
        receipt = s.receipt("synthetic:intent-receipt:used")
        with self.assertRaises(GovernanceRejected):
            s.record_receipt("synthetic:intent-receipt:again", receipt.docket_id,
                             receipt.source_version, receipt.review_digest,
                             "synthetic:verifier:d")

    def test_upstream_tamper_blocks_review(self):
        s = SyntheticReadinessDecisionIntent(); row = self.drafted(s, "tamper-review")
        draft = s._drafts["synthetic:intent-draft:tamper-review"]
        s._drafts[draft.draft_id] = replace(draft, intent_kind="DEPLOY")
        with self.assertRaises(GovernanceRejected):
            s.review("synthetic:intent-review:tamper-review", row.docket_id, row.version,
                     "synthetic:reviewer:b", True, digest("review"))

    def test_upstream_tamper_blocks_receipt(self):
        s = SyntheticReadinessDecisionIntent(); row = self.reviewed(s, "tamper-receipt")
        review = s.review_receipt("synthetic:intent-review:tamper-receipt")
        s._reviews[review.review_id] = replace(review, accepted=False)
        with self.assertRaises(GovernanceRejected):
            s.record_receipt("synthetic:intent-receipt:tamper-receipt", row.docket_id,
                             row.version, review.digest, "synthetic:verifier:c")

    def test_semantic_event_tamper_detected_even_after_rehash(self):
        s = SyntheticReadinessDecisionIntent(); self.recorded(s, "event")
        event = s._events[-1]; event["action"] = "INTENT_REVIEWED"
        payload = {k: event[k] for k in ("sequence", "action", "record_digest",
                                         "attachment_digest", "previous_digest")}
        event["digest"] = canonical_digest(payload)
        self.assertFalse(s.evidence()["event_chain_valid"])

    def test_record_batch_hold_and_replay_tamper_detected(self):
        s = SyntheticReadinessDecisionIntent(); self.recorded(s, "record")
        row = s._history[0]; s._history[0] = replace(row, readiness_digest=digest("changed"))
        self.assertFalse(s.evidence()["history_chain_valid"])
        s = SyntheticReadinessDecisionIntent(); self.recorded(s, "index")
        review = s.review_receipt("synthetic:intent-review:index")
        s._used_review_digests[review.digest] = "synthetic:readiness-docket:missing"
        self.assertFalse(s.evidence()["receipt_replay_index_valid"])

    def test_feature_map_and_prohibited_effect_flags(self):
        evidence = SyntheticReadinessDecisionIntent().evidence()
        self.assertEqual(evidence["features"], list(range(1701, 1901)))
        self.assertEqual(evidence["feature_count"], 200)
        self.assertTrue(all(w["control_count"] == 25 for w in evidence["workstreams"]))
        for key, value in evidence.items():
            if key.endswith(("_allowed", "_used", "_accessed")): self.assertFalse(value, key)

    def test_invalid_namespaces_and_boolean_versions_fail_closed(self):
        s = SyntheticReadinessDecisionIntent()
        with self.assertRaises(GovernanceRejected): s.intake("prod:docket", digest("x"))
        row = self.batched(s, "bad")
        with self.assertRaises(GovernanceRejected):
            s.draft("synthetic:intent-draft:bad", row.docket_id, True,
                    "synthetic:operator:a", "HOLD_FOR_REVIEW", digest("why"))


if __name__ == "__main__": unittest.main()
