from hashlib import sha256
import json
from pathlib import Path

from nurion_pg.synthetic_intent_planning_proposal import SyntheticIntentPlanningProposal


ROOT = Path(__file__).resolve().parents[1]


def digest(value): return sha256(value.encode()).hexdigest()


def main():
    service = SyntheticIntentPlanningProposal()
    for name in ("a", "b", "c"):
        service.intake(f"synthetic:decision-intent:{name}", digest(f"readiness:{name}"))
    batch = service.reserve_batch("synthetic:proposal-batch:evidence", 3)
    row = service.get(batch.intent_ids[0])
    row = service.propose("synthetic:planning-proposal:a", row.intent_id, row.version,
                        "synthetic:planner:one", "DRAFT_ROLLBACK_PLAN",
                        digest("rationale:a"))
    row = service.review("synthetic:proposal-review:a", row.intent_id, row.version,
                         "synthetic:reviewer:two", True, digest("review:a"))
    review = service.review_receipt("synthetic:proposal-review:a")
    row = service.record_receipt("synthetic:proposal-receipt:a", row.intent_id, row.version,
                                 review.digest, "synthetic:verifier:three")
    assert row.status == "SYNTHETIC_PROPOSAL_RECORDED"
    rejected = service.get(batch.intent_ids[1])
    rejected = service.propose("synthetic:planning-proposal:b", rejected.intent_id, rejected.version,
                             "synthetic:planner:one", "DRAFT_OBSERVATION_PLAN",
                             digest("rationale:b"))
    rejected = service.review("synthetic:proposal-review:b", rejected.intent_id,
                              rejected.version, "synthetic:reviewer:two", False,
                              digest("review:b"))
    assert rejected.status == "HELD"
    evidence = service.evidence()
    assert evidence["features"] == list(range(1901, 2101))
    assert evidence["feature_count"] == 200 and evidence["max_proposal_batch"] == 20
    assert evidence["maximum_state"] == "SYNTHETIC_PROPOSAL_RECORDED"
    assert all(evidence[key] for key in ("history_chain_valid", "event_chain_valid",
        "artifact_integrity_valid", "batch_integrity_valid", "hold_chain_valid",
        "receipt_replay_index_valid"))
    assert not any(value for key, value in evidence.items()
                   if key.endswith(("_allowed", "_used", "_accessed")))
    output = ROOT / "build/synthetic-intent-planning-proposal-evidence.json"
    content = json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    output.write_text(content, encoding="utf-8")
    checksum = sha256(content.encode()).hexdigest()
    output.with_suffix(".json.sha256").write_text(checksum + "\n", encoding="utf-8")
    print("synthetic intent planning proposal #1901-#2100: PASS", checksum)


if __name__ == "__main__": main()
