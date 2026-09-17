from __future__ import annotations
import json
from hashlib import sha256
from pathlib import Path
from nurion_pg.arkaon_pattern_capsules import portfolio_evidence

ROOT = Path(__file__).resolve().parents[1]

def main():
    report = portfolio_evidence(ROOT / "config" / "arkaon-pattern-capsules")
    output = ROOT / "build" / "arkaon-pattern-capsule-portfolio-evidence.json"
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload)
    digest = sha256(payload.encode()).hexdigest()
    output.with_suffix(".json.sha256").write_text(digest + "\n")
    print(f"ARKAON pattern capsule portfolio: PASS {digest}")
    return report

if __name__ == "__main__":
    main()
