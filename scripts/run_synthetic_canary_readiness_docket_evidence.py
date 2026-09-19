from hashlib import sha256
import json
from pathlib import Path

from nurion_pg.synthetic_canary_readiness_docket import SyntheticCanaryReadinessDocket


ROOT = Path(__file__).resolve().parents[1]


def digest(value): return sha256(value.encode()).hexdigest()


def main():
    service = SyntheticCanaryReadinessDocket()
    for name in ("a", "b", "c"):
        service.intake(f"synthetic:completed-canary:{name}", digest(f"completion:{name}"),
                       100, 9000, 100, 500)
    batch = service.reserve_portfolio("synthetic:readiness-batch:evidence", 3)
    row = service.get(batch.canary_ids[0])
    row = service.aggregate(row.canary_id, row.version, "synthetic:aggregator:one",
                            100, 90, 1, 500, digest("metrics:pass"))
    row = service.review("synthetic:readiness-docket:pass", row.canary_id, row.version,
                         "synthetic:reviewer:two", True, digest("review:ready"))
    docket = service.docket("synthetic:readiness-docket:pass")
    assert service.verify_docket(row.canary_id, row.version, docket.digest,
                                  "synthetic:verifier:three").status == "SYNTHETIC_READINESS_REVIEWED"
    failed = service.get(batch.canary_ids[1])
    assert service.aggregate(failed.canary_id, failed.version, "synthetic:aggregator:one",
                             100, 89, 0, 100, digest("metrics:hold")).status == "HELD"
    evidence = service.evidence()
    assert evidence["features"] == list(range(1501, 1701)) and evidence["feature_count"] == 200
    assert evidence["max_portfolio_batch"] == 20
    assert evidence["maximum_state"] == "SYNTHETIC_READINESS_REVIEWED"
    assert all(evidence[k] for k in ("history_chain_valid", "event_chain_valid",
        "receipt_integrity_valid", "batch_integrity_valid", "hold_chain_valid",
        "docket_replay_index_valid"))
    assert not any(v for k, v in evidence.items()
                   if k.endswith(("_allowed", "_used", "_accessed")))
    output = ROOT / "build/synthetic-canary-readiness-docket-evidence.json"
    content = json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    output.write_text(content, encoding="utf-8")
    checksum = sha256(content.encode()).hexdigest()
    output.with_suffix(".json.sha256").write_text(checksum + "\n", encoding="utf-8")
    print("synthetic canary readiness docket #1501-#1700: PASS", checksum)


if __name__ == "__main__": main()
