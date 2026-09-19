from hashlib import sha256
import json
from pathlib import Path

from nurion_pg.synthetic_proposal_feasibility_assessment import SyntheticProposalFeasibilityAssessment


ROOT = Path(__file__).resolve().parents[1]


def digest(value): return sha256(value.encode()).hexdigest()


def main():
    service = SyntheticProposalFeasibilityAssessment()
    for name in ("a", "b", "c"):
        service.intake(f"synthetic:decision-intent:{name}", digest(f"readiness:{name}"))
    batch = service.reserve_batch("synthetic:proposal-batch:evidence", 3)
    row = service.get(batch.intent_ids[0])
    row = service.propose("synthetic:planning-proposal:a", row.intent_id, row.version,
                        "synthetic:planner:one", "SELF_CONTAINED",
                        digest("rationale:a"))
    row = service.review("synthetic:proposal-review:a", row.intent_id, row.version,
                         "synthetic:reviewer:two", True, digest("review:a"))
    review = service.review_receipt("synthetic:proposal-review:a")
    row = service.record_receipt("synthetic:proposal-receipt:a", row.intent_id, row.version,
                                 review.digest, "synthetic:verifier:three")
    assert row.status == "SYNTHETIC_FEASIBILITY_RECORDED"
    rejected = service.get(batch.intent_ids[1])
    rejected = service.propose("synthetic:planning-proposal:b", rejected.intent_id, rejected.version,
                             "synthetic:planner:one", "BOUNDED_INTERNAL",
                             digest("rationale:b"))
    rejected = service.review("synthetic:proposal-review:b", rejected.intent_id,
                              rejected.version, "synthetic:reviewer:two", False,
                              digest("review:b"))
    assert rejected.status == "HELD"
    evidence = service.evidence()
    assert evidence["features"] == list(range(2101, 2501))
    assert evidence["feature_count"] == 400 and evidence["max_proposal_batch"] == 20
    assert len(evidence["workstreams"]) == 16
    assert evidence["assessment_features"] == list(range(2101, 2301))
    assert evidence["portfolio_features"] == list(range(2301, 2501))
    assert evidence["maximum_state"] == "SYNTHETIC_FEASIBILITY_RECORDED"
    assert all(evidence[key] for key in ("history_chain_valid", "event_chain_valid",
        "artifact_integrity_valid", "batch_integrity_valid", "hold_chain_valid",
        "receipt_replay_index_valid"))
    assert not any(value for key, value in evidence.items()
                   if key.endswith(("_allowed", "_used", "_accessed")))
    output = ROOT / "build/synthetic-proposal-feasibility-assessment-evidence.json"
    content = json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    output.write_text(content, encoding="utf-8")
    checksum = sha256(content.encode()).hexdigest()
    output.with_suffix(".json.sha256").write_text(checksum + "\n", encoding="utf-8")
    print("synthetic proposal feasibility assessment #2101-#2500: PASS", checksum)


if __name__ == "__main__": main()
