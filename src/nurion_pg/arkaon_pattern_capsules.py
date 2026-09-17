"""Fail-closed declarative ARKAON pattern capsules for synthetic PG evaluation."""
from __future__ import annotations
import json
from pathlib import Path
from .arkaon.governance import GovernanceRejected, canonical_digest

FOUNDRY_COMMIT = "24ae4a601ee449649e40804119fa37667f731076"
STATUS = "ETHERNIAN_REVIEW_REQUIRED"
FORBIDDEN = (
    "production_allowed", "network_allowed", "real_credentials_allowed",
    "money_movement_allowed", "deployment_allowed", "automatic_merge_allowed",
    "self_modification_allowed",
)

def validate_capsule(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise GovernanceRejected("typed capsule object required")
    feature = value.get("feature")
    pattern_id = value.get("pattern_id")
    controls = value.get("controls")
    if (
        not isinstance(feature, int) or not 68 <= feature <= 100
        or not isinstance(pattern_id, str) or not pattern_id.startswith("apf.public.")
        or value.get("mode") != "UNREGISTERED_SYNTHETIC_ONLY"
        or value.get("foundry_commit") != FOUNDRY_COMMIT
        or value.get("status") != STATUS
        or not isinstance(controls, list) or not controls
        or any(not isinstance(item, str) or not item.strip() for item in controls)
        or not isinstance(value.get("maximum_state"), str)
        or not value["maximum_state"].startswith("SYNTHETIC_")
        or any(value.get(name) is not False for name in FORBIDDEN)
    ):
        raise GovernanceRejected("valid fail-closed synthetic capsule required")
    unsigned = {key: item for key, item in value.items() if key != "capsule_digest"}
    if value.get("capsule_digest") != canonical_digest(unsigned):
        raise GovernanceRejected("capsule digest mismatch")
    return value

def load_capsules(root: Path) -> tuple[dict[str, object], ...]:
    if not isinstance(root, Path) or not root.is_dir():
        raise GovernanceRejected("capsule directory required")
    capsules = tuple(validate_capsule(json.loads(path.read_text())) for path in sorted(root.glob("*.json")))
    features = tuple(item["feature"] for item in capsules)
    if not capsules or len(features) != len(set(features)) or features != tuple(sorted(features)):
        raise GovernanceRejected("unique ordered capsule features required")
    return capsules

def portfolio_evidence(root: Path) -> dict[str, object]:
    capsules = load_capsules(root)
    values = {
        "schema": "nurion.pg.arkaon-pattern-capsule-portfolio-evidence.v1",
        "mode": "UNREGISTERED_SYNTHETIC_ONLY",
        "features": [item["feature"] for item in capsules],
        "capsule_digests": [item["capsule_digest"] for item in capsules],
        "maximum_state": "SYNTHETIC_PATTERN_CAPSULES_VALIDATED",
        "production_allowed": False,
        "network_allowed": False,
        "real_credentials_allowed": False,
        "money_movement_allowed": False,
        "deployment_allowed": False,
        "automatic_merge_allowed": False,
    }
    return {**values, "report_digest": canonical_digest(values)}
