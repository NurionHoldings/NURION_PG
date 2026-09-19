from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path

from nurion_pg.synthetic_recovery_quarantine import SyntheticRecoveryQuarantine


ROOT = Path(__file__).resolve().parents[1]


def digest(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def main() -> None:
    now = datetime(2026, 9, 18, tzinfo=UTC)
    service = SyntheticRecoveryQuarantine()
    packets = [
        service.quarantine(
            f"synthetic:packet:evidence:{number}",
            digest(f"recovery:{number}"),
            severity,
            now + timedelta(seconds=number),
            timedelta(minutes=5),
        )
        for number, severity in enumerate(("LOW", "MEDIUM", "HIGH", "CRITICAL"))
    ]
    batch = service.reserve_probe_batch("synthetic:probe-batch:evidence", 2)
    assert batch.packet_ids == (
        "synthetic:packet:evidence:3",
        "synthetic:packet:evidence:2",
    )
    released = service.get(batch.packet_ids[0])
    released = service.record_probe(
        released.packet_id,
        released.version,
        "synthetic:reviewer:probe",
        True,
        digest("probe-pass"),
    )
    released = service.review_probe(
        released.packet_id,
        released.version,
        "synthetic:reviewer:review",
        True,
        digest("review-approve"),
        released.cooldown_until,
    )
    released = service.attest_release(
        released.packet_id,
        released.version,
        "synthetic:issuer:release",
        digest("release-attestation"),
        released.cooldown_until,
    )
    released = service.release(
        released.packet_id, released.version, digest("release-attestation")
    )
    assert released.status == "SYNTHETIC_RELEASED"

    failed = service.get(batch.packet_ids[1])
    failed = service.record_probe(
        failed.packet_id,
        failed.version,
        "synthetic:reviewer:probe",
        False,
        digest("probe-fail"),
    )
    assert failed.status == "HELD"

    service.place_hold("synthetic:hold:evidence", "RELAY_REGRESSION", now)
    service.clear_hold(
        "synthetic:hold:evidence",
        "synthetic:hold-reviewer:evidence",
        digest("hold-clearance"),
        now,
    )

    evidence = service.evidence()
    assert evidence["features"] == list(range(1101, 1301))
    assert evidence["feature_count"] == 200
    assert len(evidence["workstreams"]) == 8
    assert all(row["control_count"] == 25 for row in evidence["workstreams"])
    assert evidence["max_probe_batch"] == 20
    assert evidence["history_chain_valid"]
    assert evidence["event_chain_valid"]
    assert evidence["receipt_integrity_valid"]
    assert evidence["batch_integrity_valid"]
    assert evidence["replay_index_valid"]
    assert evidence["hold_history_valid"]
    assert evidence["attestation_count"] == 1
    forbidden = (
        "automatic_approval_allowed",
        "external_delivery_used",
        "external_pg_api_used",
        "production_outcome_recorded",
        "production_credentials_accessed",
        "payment_or_ledger_effect_allowed",
        "runtime_policy_change_allowed",
        "pattern_promotion_allowed",
        "merge_allowed",
        "deployment_allowed",
    )
    assert not any(evidence[key] for key in forbidden)

    output = ROOT / "build/synthetic-recovery-quarantine-evidence.json"
    output.parent.mkdir(exist_ok=True)
    content = json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    output.write_text(content, encoding="utf-8")
    evidence_sha = sha256(content.encode()).hexdigest()
    output.with_suffix(".json.sha256").write_text(evidence_sha + "\n", encoding="utf-8")
    print("synthetic recovery quarantine #1101-#1300: PASS", evidence_sha)


if __name__ == "__main__":
    main()
