from hashlib import sha256
import json
from pathlib import Path

from nurion_pg.synthetic_feasibility_decision_docket import SyntheticFeasibilityDecisionDocket


ROOT = Path(__file__).resolve().parents[1]


def digest(value): return sha256(value.encode()).hexdigest()


def main():
    service = SyntheticFeasibilityDecisionDocket()
    for name in ("a", "b", "c"):
        service.intake(f"synthetic:feasibility-portfolio:{name}", digest(f"portfolio:{name}"),
                       1, 5, f"synthetic:portfolio-observer:observer-{name}")
    batch = service.reserve_batch("synthetic:docket-batch:evidence", 3)
    row = service.get(batch.portfolio_ids[0])
    row = service.draft("synthetic:decision-draft:a", row.portfolio_id, row.version,
        row.source_version, row.portfolio_digest, "synthetic:docket-analyst:analyst",
        "OBSERVE", digest("rationale:a"))
    row = service.review("synthetic:docket-review:a", row.portfolio_id, row.version,
        "synthetic:docket-reviewer:reviewer", True, digest("review:a"))
    review = service.review_receipt("synthetic:docket-review:a")
    row = service.record_receipt("synthetic:docket-receipt:a", row.portfolio_id,
        row.version, review.digest, "synthetic:docket-verifier:verifier")
    assert row.status == "SYNTHETIC_DECISION_DOCKET_RECORDED"
    rejected = service.get(batch.portfolio_ids[1])
    rejected = service.draft("synthetic:decision-draft:b", rejected.portfolio_id,
        rejected.version, rejected.source_version, rejected.portfolio_digest,
        "synthetic:docket-analyst:analyst", "REASSESS", digest("rationale:b"))
    rejected = service.review("synthetic:docket-review:b", rejected.portfolio_id,
        rejected.version, "synthetic:docket-reviewer:reviewer", False, digest("review:b"))
    assert rejected.status == "HELD"
    evidence = service.evidence()
    assert evidence["control_range"] == [2501, 2700]
    assert evidence["control_count"] == 200 and evidence["workstream_count"] == 8
    assert evidence["exactly_25_controls_per_workstream"]
    assert evidence["maximum_batch"] == 20
    assert evidence["maximum_state"] == "SYNTHETIC_DECISION_DOCKET_RECORDED"
    assert evidence["capability_ready"]
    assert not evidence["capability_gap_evidence"]["fail_closed"]
    assert all(evidence[key] for key in ("record_integrity_valid", "event_chain_valid",
        "batch_integrity_valid", "artifact_integrity_valid", "hold_chain_valid",
        "integrity_valid"))
    assert evidence["external_calls"] == evidence["ledger_writes"] == 0
    assert evidence["runtime_policy_mutations"] == 0
    output = ROOT / "build/synthetic-feasibility-decision-docket-evidence.json"
    content = json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    output.write_text(content, encoding="utf-8")
    checksum = sha256(content.encode()).hexdigest()
    output.with_suffix(".json.sha256").write_text(checksum + "\n", encoding="utf-8")
    print("synthetic feasibility decision docket #2501-#2700: PASS", checksum)


if __name__ == "__main__": main()
