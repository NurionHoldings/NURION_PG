from hashlib import sha256
import json
from pathlib import Path

from nurion_pg.synthetic_feasibility_decision_docket import (
    DocketRecord, MAXIMUM_STATE as SOURCE_RECORDED,
    SyntheticFeasibilityDecisionDocket,
)
from nurion_pg.synthetic_feasibility_decision_portfolio import (
    SyntheticFeasibilityDecisionPortfolio,
)


ROOT = Path(__file__).resolve().parents[1]


def digest(value): return sha256(value.encode()).hexdigest()


def source(name, status, decision):
    values = dict(portfolio_id=f"synthetic:feasibility-portfolio:{name}",
        portfolio_digest=digest(f"portfolio:{name}"), source_version=1, member_count=3,
        observer=f"synthetic:portfolio-observer:observer-{name}", status=status,
        version=5, analyst=f"synthetic:docket-analyst:analyst-{name}", decision=decision,
        hold_reason="REVIEW_REJECTED" if status == "HELD" else None,
        previous_digest=digest(f"previous:{name}"))
    value = SyntheticFeasibilityDecisionDocket._record_digest(
        values["portfolio_id"], values["portfolio_digest"], values["source_version"],
        values["member_count"], values["observer"], values["status"], values["version"],
        values["analyst"], values["decision"], values["hold_reason"], values["previous_digest"])
    return DocketRecord(**values, digest=value)


def main():
    service = SyntheticFeasibilityDecisionPortfolio()
    for name, status, decision in (("a", SOURCE_RECORDED, "OBSERVE"),
                                   ("b", SOURCE_RECORDED, "REASSESS"),
                                   ("c", "HELD", "HOLD")):
        service.intake(source(name, status, decision))
    row = service.curate("synthetic:decision-portfolio:evidence",
        "synthetic:portfolio-curator:curator", 3)
    assert dict(row.decision_counts) == {"HOLD": 1, "OBSERVE": 1, "REASSESS": 1}
    assert (row.recorded_count, row.held_count) == (2, 1)
    row = service.review("synthetic:portfolio-review:evidence", row.portfolio_id,
        row.version, "synthetic:portfolio-reviewer:reviewer", True, digest("finding"))
    review = service.review_artifact("synthetic:portfolio-review:evidence")
    row = service.record("synthetic:portfolio-receipt:evidence", row.portfolio_id,
        row.version, review.digest, "synthetic:portfolio-verifier:verifier")
    evidence = service.evidence()
    assert row.status == evidence["maximum_state"]
    assert evidence["control_range"] == [2701, 2900]
    assert evidence["control_count"] == 200 and evidence["workstream_count"] == 8
    assert evidence["exactly_25_controls_per_workstream"]
    assert evidence["maximum_batch"] == 20 and evidence["capability_ready"]
    assert not evidence["capability_gap_evidence"]["fail_closed"]
    assert all(evidence[key] for key in ("source_integrity_valid",
        "portfolio_integrity_valid", "event_chain_valid", "artifact_integrity_valid",
        "hold_chain_valid", "integrity_valid"))
    assert evidence["external_calls"] == evidence["ledger_writes"] == 0
    assert evidence["runtime_policy_mutations"] == 0
    output = ROOT / "build/synthetic-feasibility-decision-portfolio-evidence.json"
    content = json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    output.write_text(content, encoding="utf-8")
    checksum = sha256(content.encode()).hexdigest()
    output.with_suffix(".json.sha256").write_text(checksum + "\n", encoding="utf-8")
    print("synthetic feasibility decision portfolio #2701-#2900: PASS", checksum)


if __name__ == "__main__": main()
