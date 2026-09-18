from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import unittest

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_priority_delivery_recovery import (
    MAX_BATCH_SIZE,
    MAX_GAP_REPORT,
    SyntheticPriorityDeliveryRecovery,
)


NOW = datetime(2026, 9, 18, tzinfo=UTC)


def digest(value: str) -> str:
    return sha256(value.encode()).hexdigest()


class SyntheticPriorityDeliveryRecoveryTests(unittest.TestCase):
    def packet(self, service, number, priority="NORMAL"):
        return service.enqueue(
            f"synthetic:packet:{number}", digest(f"intent:{number}"), priority, NOW
        )

    def stabilize(self, service, relay="synthetic:relay:1"):
        for number in range(3):
            state = service.observe_relay(
                relay, True, f"synthetic:key:stable:{number}"
            )
        self.assertTrue(state[2])
        return relay

    def test_priority_schedule_is_deterministic_and_bounded(self):
        service = SyntheticPriorityDeliveryRecovery()
        self.packet(service, "low", "LOW")
        self.packet(service, "normal", "NORMAL")
        self.packet(service, "critical", "CRITICAL")
        self.packet(service, "high", "HIGH")
        batch = service.reserve_batch("synthetic:batch:1", 3)
        self.assertEqual(
            batch.packet_ids,
            (
                "synthetic:packet:critical",
                "synthetic:packet:high",
                "synthetic:packet:normal",
            ),
        )
        self.assertLessEqual(len(batch.packet_ids), MAX_BATCH_SIZE)

    def test_same_priority_orders_by_time_then_packet_id(self):
        service = SyntheticPriorityDeliveryRecovery()
        service.enqueue("synthetic:packet:b", digest("b"), "HIGH", NOW)
        service.enqueue(
            "synthetic:packet:c", digest("c"), "HIGH", NOW - timedelta(seconds=1)
        )
        service.enqueue("synthetic:packet:a", digest("a"), "HIGH", NOW)
        self.assertEqual(
            service.reserve_batch("synthetic:batch:sort", 3).packet_ids,
            ("synthetic:packet:c", "synthetic:packet:a", "synthetic:packet:b"),
        )

    def test_batch_cap_idempotency_and_conflict(self):
        service = SyntheticPriorityDeliveryRecovery()
        for number in range(35):
            self.packet(service, number)
        batch = service.reserve_batch("synthetic:batch:cap", MAX_BATCH_SIZE)
        self.assertEqual(len(batch.packet_ids), MAX_BATCH_SIZE)
        self.assertIs(
            batch, service.reserve_batch("synthetic:batch:cap", MAX_BATCH_SIZE)
        )
        with self.assertRaises(GovernanceRejected):
            service.reserve_batch("synthetic:batch:cap", 1)
        with self.assertRaises(GovernanceRejected):
            service.reserve_batch("synthetic:batch:too-large", 31)

    def test_concurrent_batch_reservations_do_not_overlap(self):
        service = SyntheticPriorityDeliveryRecovery()
        for number in range(30):
            self.packet(service, number)
        with ThreadPoolExecutor(max_workers=2) as pool:
            batches = list(
                pool.map(
                    lambda value: service.reserve_batch(
                        f"synthetic:batch:{value}", 15
                    ),
                    (1, 2),
                )
            )
        selected = batches[0].packet_ids + batches[1].packet_ids
        self.assertEqual(len(selected), 30)
        self.assertEqual(len(set(selected)), 30)

    def test_fulfilled_duplicate_is_archived_not_reserved(self):
        service = SyntheticPriorityDeliveryRecovery()
        original = self.packet(service, "original", "HIGH")
        service.reserve_batch("synthetic:batch:fulfill", 1)
        original = service.get(original.packet_id)
        fulfilled = service.fulfill(original.packet_id, original.version, NOW)
        duplicate = service.enqueue(
            "synthetic:packet:duplicate",
            fulfilled.intent_digest,
            "CRITICAL",
            NOW + timedelta(seconds=1),
        )
        self.assertEqual(duplicate.status, "DUPLICATE_FULFILLED_ARCHIVED")
        self.assertEqual(duplicate.archive_reason, "FULFILLED_INTENT")
        self.assertEqual(
            service.reserve_batch("synthetic:batch:after-duplicate", 30).packet_ids, ()
        )

    def test_enqueue_and_relay_observations_are_idempotent(self):
        service = SyntheticPriorityDeliveryRecovery()
        packet = self.packet(service, "one")
        self.assertIs(
            packet,
            service.enqueue(packet.packet_id, packet.intent_digest, "NORMAL", NOW),
        )
        first = service.observe_relay(
            "synthetic:relay:1", False, "synthetic:key:observation"
        )
        self.assertEqual(
            first,
            service.observe_relay(
                "synthetic:relay:1", False, "synthetic:key:observation"
            ),
        )
        with self.assertRaises(GovernanceRejected):
            service.observe_relay(
                "synthetic:relay:1", True, "synthetic:key:observation"
            )

    def test_unstable_relay_blocks_recovery(self):
        service = SyntheticPriorityDeliveryRecovery()
        packet = self.packet(service, "recover")
        packet = service.archive_recoverable(
            packet.packet_id, packet.version, "RELAY_UNSTABLE"
        )
        service.observe_relay(
            "synthetic:relay:1", False, "synthetic:key:failure"
        )
        with self.assertRaises(GovernanceRejected):
            service.verify_recovery(
                packet.packet_id,
                packet.version,
                "synthetic:verifier:1",
                digest("receipt"),
                "synthetic:relay:1",
            )

    def test_relay_failure_after_verification_blocks_recovery(self):
        service = SyntheticPriorityDeliveryRecovery()
        item = service.enqueue(
            "synthetic:packet:relay-race",
            digest("intent:relay-race"),
            "HIGH",
            NOW,
        )
        service.reserve_batch("synthetic:batch:relay-race", 1)
        reserved = service.get(item.packet_id)
        archived = service.archive_recoverable(
            item.packet_id,
            reserved.version,
            "RELAY_UNSTABLE",
        )
        relay = self.stabilize(service)
        verified = service.verify_recovery(
            item.packet_id,
            archived.version,
            "synthetic:verifier:relay-race",
            "b" * 64,
            relay,
        )
        service.observe_relay(relay, False, "synthetic:key:post-verification-failure")

        with self.assertRaises(GovernanceRejected):
            service.recover(item.packet_id, verified.version)

    def test_verified_recovery_returns_packet_to_queue(self):
        service = SyntheticPriorityDeliveryRecovery()
        packet = self.packet(service, "recover")
        packet = service.archive_recoverable(
            packet.packet_id, packet.version, "BOUNDED_RETRY"
        )
        relay = self.stabilize(service)
        source_version = packet.version
        packet = service.verify_recovery(
            packet.packet_id,
            source_version,
            "synthetic:verifier:1",
            digest("recovery-receipt"),
            relay,
        )
        self.assertIs(
            packet,
            service.verify_recovery(
                packet.packet_id,
                source_version,
                "synthetic:verifier:1",
                digest("recovery-receipt"),
                relay,
            ),
        )
        packet = service.recover(packet.packet_id, packet.version)
        self.assertEqual(packet.status, "QUEUED")
        self.assertEqual(
            service.reserve_batch("synthetic:batch:recovered", 1).packet_ids,
            (packet.packet_id,),
        )

    def test_recovery_receipt_conflict_and_tamper_fail_closed(self):
        service = SyntheticPriorityDeliveryRecovery()
        packet = self.packet(service, "receipt")
        packet = service.archive_recoverable(
            packet.packet_id, packet.version, "MANUAL_REVIEW"
        )
        relay = self.stabilize(service)
        source_version = packet.version
        packet = service.verify_recovery(
            packet.packet_id,
            source_version,
            "synthetic:verifier:1",
            digest("receipt"),
            relay,
        )
        with self.assertRaises(GovernanceRejected):
            service.verify_recovery(
                packet.packet_id,
                source_version,
                "synthetic:verifier:2",
                digest("other"),
                relay,
            )
        receipt = service._receipts[packet.packet_id]
        service._receipts[packet.packet_id] = replace(receipt, verifier="tampered")
        evidence = service.evidence()
        self.assertFalse(evidence["receipt_integrity_valid"])
        self.assertFalse(evidence["event_chain_valid"])
        with self.assertRaises(GovernanceRejected):
            service.recover(packet.packet_id, packet.version)

    def test_fulfilled_intent_cannot_be_recovered_from_old_archive(self):
        service = SyntheticPriorityDeliveryRecovery()
        archived = self.packet(service, "archived")
        archived = service.archive_recoverable(
            archived.packet_id, archived.version, "MANUAL_REVIEW"
        )
        current = service.enqueue(
            "synthetic:packet:current",
            archived.intent_digest,
            "NORMAL",
            NOW + timedelta(seconds=1),
        )
        service.reserve_batch("synthetic:batch:current", 1)
        current = service.get(current.packet_id)
        service.fulfill(current.packet_id, current.version, NOW)
        relay = self.stabilize(service)
        archived = service.verify_recovery(
            archived.packet_id,
            archived.version,
            "synthetic:verifier:1",
            digest("old-archive"),
            relay,
        )
        with self.assertRaises(GovernanceRejected):
            service.recover(archived.packet_id, archived.version)

    def test_gap_report_is_unique_local_and_bounded(self):
        service = SyntheticPriorityDeliveryRecovery()
        gaps = [f"GAP_{number:02d}" for number in range(MAX_GAP_REPORT)]
        self.assertEqual(service.report_gaps(reversed(gaps)), tuple(gaps))
        with self.assertRaises(GovernanceRejected):
            service.report_gaps(gaps + ["OVER_LIMIT"])
        with self.assertRaises(GovernanceRejected):
            service.report_gaps(("DUPLICATE", "DUPLICATE"))
        with self.assertRaises(GovernanceRejected):
            service.report_gaps(("https://external.invalid/gap",))

    def test_feature_portfolio_and_safety_flags(self):
        evidence = SyntheticPriorityDeliveryRecovery().evidence()
        self.assertEqual(evidence["features"], list(range(901, 1101)))
        self.assertEqual(evidence["feature_count"], 200)
        self.assertEqual(len(evidence["workstreams"]), 8)
        self.assertTrue(
            all(row["control_count"] == 25 for row in evidence["workstreams"])
        )
        for key, value in evidence.items():
            if key.endswith("_allowed") or key.endswith("_used") or key.endswith(
                "_accessed"
            ) or key.endswith("_recorded"):
                self.assertFalse(value, key)

    def test_history_event_and_batch_integrity_detect_tamper(self):
        service = SyntheticPriorityDeliveryRecovery()
        self.packet(service, "audit", "HIGH")
        service.reserve_batch("synthetic:batch:audit", 1)
        evidence = service.evidence()
        self.assertTrue(evidence["history_chain_valid"])
        self.assertTrue(evidence["event_chain_valid"])
        self.assertTrue(evidence["batch_integrity_valid"])
        service._events[0]["action"] = "TAMPERED"
        self.assertFalse(service.evidence()["event_chain_valid"])

        service2 = SyntheticPriorityDeliveryRecovery()
        row = self.packet(service2, "history")
        service2._history[0] = replace(row, priority="CRITICAL")
        self.assertFalse(service2.evidence()["history_chain_valid"])

        service3 = SyntheticPriorityDeliveryRecovery()
        self.packet(service3, "batch")
        batch = service3.reserve_batch("synthetic:batch:tamper", 1)
        service3._batches[batch.batch_id] = replace(batch, requested_limit=2)
        self.assertFalse(service3.evidence()["batch_integrity_valid"])

    def test_invalid_input_and_stale_versions_fail_closed(self):
        service = SyntheticPriorityDeliveryRecovery()
        packet = self.packet(service, "valid")
        with self.assertRaises(GovernanceRejected):
            service.enqueue("production:packet:1", digest("x"), "HIGH", NOW)
        with self.assertRaises(GovernanceRejected):
            service.enqueue("synthetic:packet:bad", "z" * 64, "HIGH", NOW)
        with self.assertRaises(GovernanceRejected):
            service.archive_recoverable(packet.packet_id, 99, "BOUNDED_RETRY")
        with self.assertRaises(GovernanceRejected):
            service.archive_recoverable(packet.packet_id, packet.version, "UNBOUNDED")


if __name__ == "__main__":
    unittest.main()
