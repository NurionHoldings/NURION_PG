from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path

from nurion_pg.synthetic_release_canary_observation import SyntheticReleaseCanaryObservation

ROOT = Path(__file__).resolve().parents[1]

def digest(value): return sha256(value.encode()).hexdigest()

def main():
    service = SyntheticReleaseCanaryObservation()
    for name in ("a", "b", "c"):
        service.intake(f"synthetic:canary:{name}", digest(f"release:{name}"), 100, 500)
    batch = service.reserve_batch("synthetic:canary-batch:evidence", 3)
    row = service.get(batch.canary_ids[0])
    row = service.observe(row.canary_id, row.version, "synthetic:observer:one", 100, 1, 500, digest("edge-pass"))
    row = service.review(row.canary_id, row.version, "synthetic:reviewer:two", True, digest("approved"))
    row = service.issue_completion(row.canary_id, row.version, "synthetic:issuer:three", datetime(2026, 9, 18, tzinfo=UTC))
    receipt = service._receipts[row.canary_id]
    assert service.complete(row.canary_id, row.version, receipt.digest).status == "OBSERVATION_COMPLETE"
    failed = service.get(batch.canary_ids[1])
    assert service.observe(failed.canary_id, failed.version, "synthetic:observer:one", 100, 2, 100, digest("regression")).status == "HELD"
    evidence = service.evidence()
    assert evidence["features"] == list(range(1301, 1501)) and evidence["feature_count"] == 200
    assert evidence["max_canary_batch"] == 10
    assert all(evidence[k] for k in ("history_chain_valid", "event_chain_valid", "receipt_integrity_valid", "batch_integrity_valid", "hold_chain_valid", "replay_index_valid"))
    assert not any(v for k,v in evidence.items() if k.endswith(("_allowed", "_used", "_recorded", "_accessed")))
    output = ROOT / "build/synthetic-release-canary-observation-evidence.json"
    content = json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    output.write_text(content, encoding="utf-8")
    checksum = sha256(content.encode()).hexdigest()
    output.with_suffix(".json.sha256").write_text(checksum + "\n", encoding="utf-8")
    print("synthetic release canary observation #1301-#1500: PASS", checksum)

if __name__ == "__main__": main()
