from hashlib import sha256
import json
from pathlib import Path

from nurion_pg.synthetic_feasibility_decision_portfolio import DecisionPortfolio
from nurion_pg.synthetic_decision_portfolio_briefing import (
    SyntheticDecisionPortfolioBriefing,
)

ROOT = Path(__file__).resolve().parents[1]


def digest(value): return sha256(value.encode()).hexdigest()


def source(name, status="SYNTHETIC_DECISION_PORTFOLIO_RECORDED"):
    values = dict(portfolio_id=f"synthetic:decision-portfolio:{name}",
        curator=f"synthetic:portfolio-curator:curator-{name}", requested_limit=2,
        docket_ids=(f"synthetic:feasibility-portfolio:{name}-a", f"synthetic:feasibility-portfolio:{name}-b"),
        decision_counts=(("HOLD", 0), ("OBSERVE", 1), ("REASSESS", 1)),
        recorded_count=2, held_count=0, status=status, version=3,
        previous_digest=digest(f"previous:{name}"))
    draft = DecisionPortfolio(**values, digest="placeholder")
    return DecisionPortfolio(**values, digest=SyntheticDecisionPortfolioBriefing._source_digest(draft))


def main():
    service = SyntheticDecisionPortfolioBriefing()
    for name in ("a", "b", "c"): service.intake(source(name))
    row = service.author("synthetic:portfolio-briefing:evidence",
        "synthetic:briefing-author:author", 3)
    row = service.review("synthetic:briefing-review:evidence", row.briefing_id,
        row.version, "synthetic:briefing-reviewer:reviewer", True, digest("finding"))
    review = service.review_artifact("synthetic:briefing-review:evidence")
    row = service.record("synthetic:briefing-receipt:evidence", row.briefing_id,
        row.version, review.digest, "synthetic:briefing-verifier:verifier")
    evidence = service.evidence()
    assert row.status == evidence["maximum_state"]
    assert evidence["control_range"] == [2901, 3100]
    assert evidence["control_count"] == 200 and evidence["workstream_count"] == 8
    assert evidence["capability_ready"] and evidence["integrity_valid"]
    assert evidence["operator_action_required"] and not evidence["approval_recorded"]
    assert evidence["fixed_template"] and not evidence["free_prompt_generation"]
    assert evidence["external_calls"] == evidence["external_url_calls"] == 0
    assert evidence["ledger_writes"] == evidence["runtime_policy_mutations"] == 0
    output = ROOT / "build/synthetic-decision-portfolio-briefing-evidence.json"
    output.parent.mkdir(exist_ok=True)
    content = json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    output.write_text(content, encoding="utf-8")
    checksum = sha256(content.encode()).hexdigest()
    output.with_suffix(".json.sha256").write_text(checksum + "\n", encoding="utf-8")
    print("synthetic decision portfolio briefing #2901-#3100: PASS", checksum)


if __name__ == "__main__": main()
