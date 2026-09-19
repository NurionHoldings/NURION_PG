from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path

from nurion_pg.synthetic_priority_delivery_recovery import (
    SyntheticPriorityDeliveryRecovery,
)


ROOT = Path(__file__).resolve().parents[1]


def digest(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def main() -> None:
    now = datetime(2026, 9, 18, tzinfo=UTC)
    service = SyntheticPriorityDeliveryRecovery()
    priorities = ("LOW", "NORMAL", "HIGH", "CRITICAL")
    packets = [
        service.enqueue(
            f"synthetic:packet:evidence:{number}",
            digest(f"intent:{number}"),
            priority,
            now + timedelta(seconds=number),
        )
        for number, priority in enumerate(priorities)
    ]
    batch = service.reserve_batch("synthetic:batch:evidence", 2)
    assert batch.packet_ids == (
        "synthetic:packet:evidence:3",
        "synthetic:packet:evidence:2",
    )
    fulfilled = service.get(batch.packet_ids[0])
    service.fulfill(fulfilled.packet_id, fulfilled.version, now)
    duplicate = service.enqueue(
        "synthetic:packet:evidence:duplicate",
        fulfilled.intent_digest,
        "CRITICAL",
        now + timedelta(minutes=1),
    )
    assert duplicate.status == "DUPLICATE_FULFILLED_ARCHIVED"

    recoverable = service.archive_recoverable(
        packets[0].packet_id, packets[0].version, "RELAY_UNSTABLE"
    )
    for number in range(3):
        service.observe_relay(
            "synthetic:relay:evidence",
            True,
            f"synthetic:key:relay:{number}",
        )
    recoverable = service.verify_recovery(
        recoverable.packet_id,
        recoverable.version,
        "synthetic:verifier:evidence",
        digest("recovery-receipt"),
        "synthetic:relay:evidence",
    )
    service.recover(recoverable.packet_id, recoverable.version)
    service.report_gaps(("ARCHIVE_LAG", "RELAY_RETRY"))

    evidence = service.evidence()
    assert evidence["features"] == list(range(901, 1101))
    assert evidence["feature_count"] == 200
    assert len(evidence["workstreams"]) == 8
    assert all(row["control_count"] == 25 for row in evidence["workstreams"])
    assert evidence["max_batch_size"] == 30
    assert evidence["max_gap_report"] == 50
    assert evidence["history_chain_valid"]
    assert evidence["event_chain_valid"]
    assert evidence["receipt_integrity_valid"]
    assert evidence["batch_integrity_valid"]
    assert evidence["recovery_receipt_count"] == 1
    forbidden = (
        "automatic_approval_allowed",
        "external_delivery_used",
        "external_pg_api_used",
        "production_outcome_recorded",
        "pattern_promotion_allowed",
        "production_credentials_accessed",
        "payment_or_ledger_effect_allowed",
        "merge_allowed",
        "deployment_allowed",
    )
    assert not any(evidence[key] for key in forbidden)

    output = ROOT / "build/synthetic-priority-delivery-recovery-evidence.json"
    output.parent.mkdir(exist_ok=True)
    content = json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    output.write_text(content, encoding="utf-8")
    evidence_sha = sha256(content.encode()).hexdigest()
    output.with_suffix(".json.sha256").write_text(evidence_sha + "\n", encoding="utf-8")
    print("synthetic priority delivery recovery #901-#1100: PASS", evidence_sha)


if __name__ == "__main__":
    main()
