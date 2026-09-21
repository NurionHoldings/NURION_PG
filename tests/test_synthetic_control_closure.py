import json
from pathlib import Path
import tempfile
import unittest
from scripts.validate_synthetic_control_closure import ROOT,validate


class SyntheticControlClosureTests(unittest.TestCase):
    def test_repository_meets_defined_closure_contract(self):
        evidence=validate()
        self.assertEqual(evidence["completion_percent"],100)
        self.assertEqual(evidence["criteria_passed"],evidence["criteria_total"])
        self.assertFalse(evidence["live_payment_allowed"])
        self.assertFalse(evidence["production_readiness_implied"])

    def test_missing_module_test_pair_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in ("config","governance","src/nurion_pg","tests","scripts","docs",".github/workflows"): (root/name).mkdir(parents=True,exist_ok=True)
            for relative in ("config/synthetic-control-closure-v1.json","governance/authority-policy.json","governance/promotion-policy.json","config/external-blockers.json","arkaon.workspace.json",".github/workflows/ci.yml","docs/70-arkaon-audit-recurrence-prevention.md","config/ethernian-remediation-manifest-v1.json","config/arkaon-lesson-registry-v1.json"):
                source=ROOT/relative
                target=root/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source.read_bytes())
            (root/"src/nurion_pg/synthetic_unpaired.py").write_text("",encoding="utf-8")
            with self.assertRaises(AssertionError):validate(root)

    def test_policy_cannot_claim_production_readiness(self):
        policy=json.loads((ROOT/"config/synthetic-control-closure-v1.json").read_text())
        self.assertFalse(policy["production_readiness_implied"])
        self.assertFalse(policy["commercial_readiness_implied"])


if __name__=="__main__":unittest.main()
