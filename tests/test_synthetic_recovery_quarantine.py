from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import unittest

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_recovery_quarantine import (
    MAX_PROBE_BATCH,
    SyntheticRecoveryQuarantine,
)


NOW = datetime(2026, 9, 18, tzinfo=UTC)


def digest(value: str) -> str:
    return sha256(value.encode()).hexdigest()


class SyntheticRecoveryQuarantineTests(unittest.TestCase):
    def quarantine(self, service, number, severity="MEDIUM", cooldown=timedelta(minutes=5)):
        return service.quarantine(
            f"synthetic:packet:{number}", digest(f"recovery:{number}"), severity, NOW, cooldown
        )

    def pass_probe(self, service, packet, reviewer="synthetic:reviewer:probe"):
        service.reserve_probe_batch(f"synthetic:probe-batch:{packet.packet_id}", 1)
        current = service.get(packet.packet_id)
        return service.record_probe(
            packet.packet_id, current.version, reviewer, True, digest(f"probe:{packet.packet_id}")
        )

    def approve(self, service, packet, reviewer="synthetic:reviewer:review"):
        return service.review_probe(
            packet.packet_id,
            packet.version,
            reviewer,
            True,
            digest(f"review:{packet.packet_id}"),
            packet.cooldown_until,
        )

    def attest(self, service, packet, suffix="one"):
        return service.attest_release(
            packet.packet_id,
            packet.version,
            "synthetic:issuer:release",
            digest(f"attestation:{suffix}"),
            packet.cooldown_until,
        )

    def test_quarantine_is_idempotent_and_conflicts_fail_closed(self):
        service = SyntheticRecoveryQuarantine()
        item = self.quarantine(service, "one", "HIGH")
        self.assertIs(
            item,
            service.quarantine(item.packet_id, item.recovery_receipt_digest, "HIGH", NOW, timedelta(minutes=5)),
        )
        with self.assertRaises(GovernanceRejected):
            service.quarantine(item.packet_id, digest("different"), "HIGH", NOW, timedelta(minutes=5))

    def test_probe_batch_is_severity_time_id_ordered_and_bounded(self):
        service = SyntheticRecoveryQuarantine()
        self.quarantine(service, "low", "LOW")
        self.quarantine(service, "high-b", "HIGH")
        self.quarantine(service, "critical", "CRITICAL")
        self.quarantine(service, "high-a", "HIGH")
        batch = service.reserve_probe_batch("synthetic:probe-batch:ordered", 3)
        self.assertEqual(
            batch.packet_ids,
            ("synthetic:packet:critical", "synthetic:packet:high-a", "synthetic:packet:high-b"),
        )
        self.assertLessEqual(len(batch.packet_ids), MAX_PROBE_BATCH)

    def test_probe_batch_idempotency_limit_and_conflict(self):
        service = SyntheticRecoveryQuarantine()
        for number in range(22):
            self.quarantine(service, number)
        batch = service.reserve_probe_batch("synthetic:probe-batch:cap", MAX_PROBE_BATCH)
        self.assertEqual(len(batch.packet_ids), MAX_PROBE_BATCH)
        self.assertIs(batch, service.reserve_probe_batch("synthetic:probe-batch:cap", MAX_PROBE_BATCH))
        with self.assertRaises(GovernanceRejected):
            service.reserve_probe_batch("synthetic:probe-batch:cap", 1)
        with self.assertRaises(GovernanceRejected):
            service.reserve_probe_batch("synthetic:probe-batch:over", MAX_PROBE_BATCH + 1)

    def test_concurrent_batches_do_not_overlap(self):
        service = SyntheticRecoveryQuarantine()
        for number in range(20):
            self.quarantine(service, number)
        with ThreadPoolExecutor(max_workers=2) as pool:
            batches = list(
                pool.map(
                    lambda n: service.reserve_probe_batch(f"synthetic:probe-batch:{n}", 10),
                    (1, 2),
                )
            )
        selected = batches[0].packet_ids + batches[1].packet_ids
        self.assertEqual(len(selected), 20)
        self.assertEqual(len(set(selected)), 20)

    def test_failed_probe_enters_hold_state(self):
        service = SyntheticRecoveryQuarantine()
        item = self.quarantine(service, "failed")
        service.reserve_probe_batch("synthetic:probe-batch:failed", 1)
        item = service.get(item.packet_id)
        item = service.record_probe(item.packet_id, item.version, "synthetic:reviewer:probe", False, digest("fail"))
        self.assertEqual(item.status, "HELD")
        self.assertEqual(item.hold_reason, "REVIEW_CONFLICT")

    def test_probe_receipt_is_idempotent_and_conflict_is_rejected(self):
        service = SyntheticRecoveryQuarantine()
        item = self.quarantine(service, "probe")
        service.reserve_probe_batch("synthetic:probe-batch:probe", 1)
        item = service.get(item.packet_id)
        first = service.record_probe(item.packet_id, item.version, "synthetic:reviewer:probe", True, digest("probe"))
        self.assertIs(
            first,
            service.record_probe(item.packet_id, item.version, "synthetic:reviewer:probe", True, digest("probe")),
        )
        with self.assertRaises(GovernanceRejected):
            service.record_probe(item.packet_id, item.version, "synthetic:reviewer:other", True, digest("probe"))

    def test_review_requires_independent_reviewer_and_elapsed_cooldown(self):
        service = SyntheticRecoveryQuarantine()
        item = self.pass_probe(service, self.quarantine(service, "review"))
        with self.assertRaises(GovernanceRejected):
            service.review_probe(item.packet_id, item.version, "synthetic:reviewer:probe", True, digest("review"), item.cooldown_until)
        with self.assertRaises(GovernanceRejected):
            service.review_probe(item.packet_id, item.version, "synthetic:reviewer:review", True, digest("review"), NOW)
        approved = self.approve(service, item)
        self.assertEqual(approved.status, "REVIEW_APPROVED")

    def test_rejected_review_enters_hold_state(self):
        service = SyntheticRecoveryQuarantine()
        item = self.pass_probe(service, self.quarantine(service, "rejected"))
        item = service.review_probe(
            item.packet_id, item.version, "synthetic:reviewer:review", False, digest("reject"), item.cooldown_until
        )
        self.assertEqual(item.status, "HELD")

    def test_attestation_requires_third_role_and_is_idempotent(self):
        service = SyntheticRecoveryQuarantine()
        item = self.approve(service, self.pass_probe(service, self.quarantine(service, "attest")))
        with self.assertRaises(GovernanceRejected):
            service.attest_release(
                item.packet_id, item.version, "synthetic:issuer:release", "z" * 64, item.cooldown_until
            )
        attested = self.attest(service, item)
        self.assertEqual(attested.status, "RELEASE_ATTESTED")
        self.assertIs(attested, self.attest(service, item))

    def test_attestation_digest_cannot_be_replayed_across_packets(self):
        service = SyntheticRecoveryQuarantine()
        first = self.approve(service, self.pass_probe(service, self.quarantine(service, "first")))
        self.attest(service, first, "shared")
        second = self.approve(service, self.pass_probe(service, self.quarantine(service, "second")))
        with self.assertRaises(GovernanceRejected):
            self.attest(service, second, "shared")

    def test_release_requires_current_integral_attestation(self):
        service = SyntheticRecoveryQuarantine()
        item = self.approve(service, self.pass_probe(service, self.quarantine(service, "release")))
        item = self.attest(service, item)
        with self.assertRaises(GovernanceRejected):
            service.release(item.packet_id, item.version, digest("wrong"))
        item = service.release(item.packet_id, item.version, digest("attestation:one"))
        self.assertEqual(item.status, "SYNTHETIC_RELEASED")

    def test_release_rechecks_upstream_receipts_and_audit_chains(self):
        service = SyntheticRecoveryQuarantine()
        item = self.approve(
            service,
            self.pass_probe(service, self.quarantine(service, "release-integrity")),
        )
        item = self.attest(service, item)
        review = service._review_receipts[item.packet_id]
        service._review_receipts[item.packet_id] = replace(
            review, reviewer="synthetic:reviewer:tampered"
        )
        with self.assertRaises(GovernanceRejected):
            service.release(item.packet_id, item.version, digest("attestation:one"))

        service2 = SyntheticRecoveryQuarantine()
        item2 = self.approve(
            service2,
            self.pass_probe(service2, self.quarantine(service2, "release-chain")),
        )
        item2 = self.attest(service2, item2)
        service2._events[0]["action"] = "TAMPERED"
        with self.assertRaises(GovernanceRejected):
            service2.release(item2.packet_id, item2.version, digest("attestation:one"))

    def test_active_emergency_hold_blocks_attestation_and_release(self):
        service = SyntheticRecoveryQuarantine()
        item = self.approve(service, self.pass_probe(service, self.quarantine(service, "held-attest")))
        service.place_hold("synthetic:hold:one", "INTEGRITY_DRIFT", NOW)
        with self.assertRaises(GovernanceRejected):
            self.attest(service, item)
        service.clear_hold("synthetic:hold:one", "synthetic:hold-reviewer:one", digest("clear"), NOW)
        item = self.attest(service, item)
        service.place_hold("synthetic:hold:two", "RELAY_REGRESSION", NOW)
        with self.assertRaises(GovernanceRejected):
            service.release(item.packet_id, item.version, digest("attestation:one"))

    def test_hold_is_idempotent_bounded_and_independently_cleared(self):
        service = SyntheticRecoveryQuarantine()
        hold = service.place_hold("synthetic:hold:one", "REVIEW_CONFLICT", NOW)
        self.assertEqual(hold, service.place_hold("synthetic:hold:one", "REVIEW_CONFLICT", NOW))
        with self.assertRaises(GovernanceRejected):
            service.place_hold("synthetic:hold:two", "REVIEW_CONFLICT", NOW)
        with self.assertRaises(GovernanceRejected):
            service.clear_hold("synthetic:hold:wrong", "synthetic:hold-reviewer:one", digest("clear"), NOW)
        service.clear_hold("synthetic:hold:one", "synthetic:hold-reviewer:one", digest("clear"), NOW)
        self.assertFalse(service.evidence()["hold_active"])

    def test_history_event_receipt_batch_replay_and_hold_tamper_detected(self):
        service = SyntheticRecoveryQuarantine()
        item = self.approve(service, self.pass_probe(service, self.quarantine(service, "audit")))
        self.attest(service, item)
        evidence = service.evidence()
        for key in (
            "history_chain_valid", "event_chain_valid", "receipt_integrity_valid",
            "batch_integrity_valid", "replay_index_valid", "hold_history_valid",
        ):
            self.assertTrue(evidence[key], key)

        service._events[0]["action"] = "TAMPERED"
        self.assertFalse(service.evidence()["event_chain_valid"])

        service2 = SyntheticRecoveryQuarantine()
        item2 = self.quarantine(service2, "history")
        service2._history[0] = replace(item2, severity="CRITICAL")
        self.assertFalse(service2.evidence()["history_chain_valid"])

        service3 = SyntheticRecoveryQuarantine()
        item3 = self.quarantine(service3, "receipt")
        item3 = self.pass_probe(service3, item3)
        receipt = service3._probe_receipts[item3.packet_id]
        service3._probe_receipts[item3.packet_id] = replace(receipt, reviewer="tampered")
        self.assertFalse(service3.evidence()["receipt_integrity_valid"])
        self.assertFalse(service3.evidence()["event_chain_valid"])

        service4 = SyntheticRecoveryQuarantine()
        service4.place_hold("synthetic:hold:audit", "INTEGRITY_DRIFT", NOW)
        service4.clear_hold(
            "synthetic:hold:audit",
            "synthetic:hold-reviewer:audit",
            digest("clear-audit"),
            NOW,
        )
        service4._hold_history[0]["reason"] = "TAMPERED"
        self.assertFalse(service4.evidence()["hold_history_valid"])

    def test_feature_portfolio_and_safety_flags(self):
        evidence = SyntheticRecoveryQuarantine().evidence()
        self.assertEqual(evidence["features"], list(range(1101, 1301)))
        self.assertEqual(evidence["feature_count"], 200)
        self.assertEqual(len(evidence["workstreams"]), 8)
        self.assertTrue(all(row["control_count"] == 25 for row in evidence["workstreams"]))
        for key, value in evidence.items():
            if key.endswith("_allowed") or key.endswith("_used") or key.endswith("_accessed") or key.endswith("_recorded"):
                self.assertFalse(value, key)

    def test_invalid_namespaces_versions_and_cooldowns_fail_closed(self):
        service = SyntheticRecoveryQuarantine()
        with self.assertRaises(GovernanceRejected):
            service.quarantine("production:packet:one", digest("x"), "HIGH", NOW, timedelta(minutes=5))
        with self.assertRaises(GovernanceRejected):
            self.quarantine(service, "short", cooldown=timedelta(minutes=4))
        with self.assertRaises(GovernanceRejected):
            self.quarantine(service, "long", cooldown=timedelta(hours=25))
        item = self.quarantine(service, "stale")
        service.reserve_probe_batch("synthetic:probe-batch:stale", 1)
        with self.assertRaises(GovernanceRejected):
            service.record_probe(item.packet_id, 99, "synthetic:reviewer:probe", True, digest("probe"))


if __name__ == "__main__":
    unittest.main()
