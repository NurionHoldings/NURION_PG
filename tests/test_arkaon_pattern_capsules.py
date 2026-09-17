from __future__ import annotations
import json
import unittest
from pathlib import Path
from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.arkaon_pattern_capsules import load_capsules, portfolio_evidence, validate_capsule

ROOT = Path(__file__).resolve().parents[1]
CAPSULES = ROOT / "config" / "arkaon-pattern-capsules"

class PatternCapsuleTests(unittest.TestCase):
    def test_all_capsules_are_ordered_and_fail_closed(self):
        capsules = load_capsules(CAPSULES)
        self.assertGreaterEqual(len(capsules), 1)
        for item in capsules:
            for name, value in item.items():
                if name.endswith("_allowed"):
                    self.assertFalse(value)

    def test_portfolio_is_deterministic_and_non_operational(self):
        one = portfolio_evidence(CAPSULES)
        two = portfolio_evidence(CAPSULES)
        self.assertEqual(one, two)
        self.assertFalse(one["production_allowed"])
        self.assertFalse(one["automatic_merge_allowed"])

    def test_tamper_and_untyped_inputs_fail_closed(self):
        item = json.loads(next(CAPSULES.glob("*.json")).read_text())
        item["production_allowed"] = True
        with self.assertRaises(GovernanceRejected):
            validate_capsule(item)
        with self.assertRaises(GovernanceRejected):
            validate_capsule(object())

if __name__ == "__main__":
    unittest.main()
