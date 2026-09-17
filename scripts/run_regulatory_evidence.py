"""Validate the checked-in regulatory registry and emit review evidence."""

from __future__ import annotations

import json
from datetime import datetime
from hashlib import sha256
from pathlib import Path

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.arkaon.regulatory_evidence import (
    RegulatoryClaim,
    RegulatoryEvidence,
    RegulatoryRegistry,
    SourceAuthority,
)


ROOT = Path(__file__).resolve().parents[1]


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value)


def load_registry() -> RegulatoryRegistry:
    raw = json.loads((ROOT / "config/regulatory-evidence-registry.json").read_text(encoding="utf-8"))
    if (
        raw.get("platform_status") != "UNREGISTERED_SYNTHETIC_ONLY"
        or raw.get("automatic_update_allowed") is not False
        or raw.get("operational_use_allowed") is not False
    ):
        raise GovernanceRejected("registry cannot enable automatic or operational use")
    retrieved_at = parse_time(raw["retrieved_at"])
    registry = RegulatoryRegistry()
    for item in raw["sources"]:
        claims = tuple(RegulatoryClaim(**claim) for claim in item["claims"])
        registry.register(
            RegulatoryEvidence(
                evidence_id=item["evidence_id"],
                url=item["url"],
                title=item["title"],
                authority=SourceAuthority(item["authority"]),
                publisher=item["publisher"],
                published_on=item["published_on"],
                retrieved_at=retrieved_at,
                revalidate_after=parse_time(item["revalidate_after"]),
                document_version=item["document_version"],
                claims=claims,
                claim_snapshot_digest=item["claim_snapshot_digest"],
                official_verified=item["official_verified"],
                content_capture_complete=item["content_capture_complete"],
                conflicts_with=tuple(item["conflicts_with"]),
            )
        )
    return registry


def main() -> None:
    registry = load_registry()
    now = datetime.fromisoformat("2026-09-17T08:00:00+09:00")
    report = registry.report(now=now)
    report["requirement_views"] = [
        registry.requirement_view(key, now=now)
        for key in (
            "pg_business_classification",
            "pg_settlement_funds_external_management",
            "pg_capital_tier_change",
        )
    ]
    output = ROOT / "build/regulatory-evidence-report.json"
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode("utf-8")).hexdigest()
    output.with_suffix(".json.sha256").write_text(digest + "\n", encoding="ascii")
    if report["production_activation_allowed"] is not False:
        raise SystemExit("regulatory evidence must never activate production")
    print(f"regulatory evidence registry: PASS {digest}")


if __name__ == "__main__":
    main()
