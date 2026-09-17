"""Validate checked-in governance manifests without network access."""

from __future__ import annotations

import json
from pathlib import Path

from nurion_pg.arkaon.governance import Action, ArkaonGovernor, AuthorityDecision


ROOT = Path(__file__).resolve().parents[1]


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def main() -> None:
    authority = load("governance/authority-policy.json")
    promotion = load("governance/promotion-policy.json")
    blockers = load("config/external-blockers.json")
    workspace = load("arkaon.workspace.json")

    assert authority["default_decision"] == "BLOCKED"
    assert set(authority["forbidden_actions"]) == {
        action.value for action in ArkaonGovernor._BLOCKED_ACTIONS
    }
    assert promotion["production_promotion_allowed"] is False
    assert promotion["automatic_merge_allowed"] is False
    assert promotion["automatic_deploy_allowed"] is False
    assert workspace["production_change_allowed"] is False
    assert workspace["automatic_learning_allowed"] is False
    assert blockers["release_status"] == "BLOCKED"
    assert blockers["automatic_close_allowed"] is False
    assert all(item["status"] == "PENDING" for item in blockers["blockers"])
    assert len({item["id"] for item in blockers["blockers"]}) == len(blockers["blockers"])
    assert AuthorityDecision.BLOCKED.value == "BLOCKED"
    assert Action.RUN_LIVE_PAYMENT.value in authority["forbidden_actions"]
    print("governance manifests: PASS")


if __name__ == "__main__":
    main()

