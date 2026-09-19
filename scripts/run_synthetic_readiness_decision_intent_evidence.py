from hashlib import sha256
import json
from pathlib import Path

from nurion_pg.synthetic_readiness_decision_intent import SyntheticReadinessDecisionIntent


ROOT = Path(__file__).resolve().parents[1]


def digest(value): return sha256(value.encode()).hexdigest()


def main():
    service = SyntheticReadinessDecisionIntent()
    for name in ("a", "b", "c"):
        service.intake(f"synthetic:readiness-docket:{name}", digest(f"readiness:{name}"))
    batch = service.reserve_batch("synthetic:intent-batch:evidence", 3)
    row = service.get(batch.docket_ids[0])
    row = service.draft("synthetic:intent-draft:a", row.docket_id, row.version,
                        "synthetic:operator:one", "PROCEED_TO_SYNTHETIC_PLANNING",
                        digest("rationale:a"))
    row = service.review("synthetic:intent-review:a", row.docket_id, row.version,
                         "synthetic:reviewer:two", True, digest("review:a"))
    review = service.review_receipt("synthetic:intent-review:a")
    row = service.record_receipt("synthetic:intent-receipt:a", row.docket_id, row.version,
                                 review.digest, "synthetic:verifier:three")
    assert row.status == "SYNTHETIC_INTENT_RECORDED"
    rejected = service.get(batch.docket_ids[1])
    rejected = service.draft("synthetic:intent-draft:b", rejected.docket_id, rejected.version,
                             "synthetic:operator:one", "HOLD_FOR_REVIEW",
                             digest("rationale:b"))
    rejected = service.review("synthetic:intent-review:b", rejected.docket_id,
                              rejected.version, "synthetic:reviewer:two", False,
                              digest("review:b"))
    assert rejected.status == "HELD"
    evidence = service.evidence()
    assert evidence["features"] == list(range(1701, 1901))
    assert evidence["feature_count"] == 200 and evidence["max_intent_batch"] == 20
    assert evidence["maximum_state"] == "SYNTHETIC_INTENT_RECORDED"
    assert all(evidence[key] for key in ("history_chain_valid", "event_chain_valid",
        "artifact_integrity_valid", "batch_integrity_valid", "hold_chain_valid",
        "receipt_replay_index_valid"))
    assert not any(value for key, value in evidence.items()
                   if key.endswith(("_allowed", "_used", "_accessed")))
    output = ROOT / "build/synthetic-readiness-decision-intent-evidence.json"
    content = json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    output.write_text(content, encoding="utf-8")
    checksum = sha256(content.encode()).hexdigest()
    output.with_suffix(".json.sha256").write_text(checksum + "\n", encoding="utf-8")
    print("synthetic readiness decision intent #1701-#1900: PASS", checksum)


if __name__ == "__main__": main()
