"""Generate deterministic synthetic ARKAON bootstrap evidence."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from nurion_pg.arkaon.governance import (
    Action,
    ArkaonGovernor,
    AuthorityDecision,
    CAPABILITY_DOMAINS,
    CapabilityProfile,
    canonical_digest,
)


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    profile = CapabilityProfile(
        profile_id="NURION_PG_ARKAON_SYNTHETIC",
        version="0.1.0",
        domains=CAPABILITY_DOMAINS,
    )
    governor = ArkaonGovernor(profile)
    cases = json.loads(
        (ROOT / "synthetic/benchmark-cases.json").read_text(encoding="utf-8")
    )
    results = []
    for case in cases["cases"]:
        actual = governor.decide(Action(case["action"])).value
        results.append({"id": case["id"], "expected": case["expected"], "actual": actual})
    passed = all(item["expected"] == item["actual"] for item in results)
    report = {
        "schema": "nurion.pg.arkaon-bootstrap-evidence.v1",
        "profile_id": profile.profile_id,
        "profile_version": profile.version,
        "platform_status": "UNREGISTERED_SYNTHETIC_ONLY",
        "results": results,
        "passed": passed,
        "synthetic_only": True,
        "contains_real_transaction_data": False,
        "production_activation_allowed": False,
        "operator_approval_present": False,
        "external_release_status": "BLOCKED",
    }
    report["report_digest"] = canonical_digest(report)
    output = ROOT / "build/arkaon-bootstrap-evidence.json"
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode("utf-8")).hexdigest()
    output.with_suffix(".json.sha256").write_text(digest + "\n", encoding="ascii")
    if not passed or governor.decide(Action.RUN_LIVE_PAYMENT) is not AuthorityDecision.BLOCKED:
        raise SystemExit("fail-closed bootstrap benchmark failed")
    print(f"ARKAON bootstrap evidence: PASS {digest}")


if __name__ == "__main__":
    main()

