import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
POLICY=ROOT/"config/arkaon-audit-recurrence-prevention.json"
REQUIRED={f"ARP-{i:02}" for i in range(1,9)}
FIELDS={"cause","attack","precheck","negative_test","done"}

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.policy=json.loads(POLICY.read_text(encoding="utf-8"))
    def test_exact_required_rules(self):
        ids=[x["id"] for x in self.policy["rules"]]; self.assertEqual(set(ids),REQUIRED); self.assertEqual(len(ids),len(set(ids)))
    def test_every_rule_is_actionable(self):
        for rule in self.policy["rules"]:
            self.assertTrue(FIELDS <= set(rule)); self.assertTrue(all(isinstance(rule[k],str) and rule[k].strip() for k in FIELDS))
    def test_completion_gate_matches_rules(self):
        gate=self.policy["completion_gate"]; self.assertEqual(set(gate["required_rule_ids"]),REQUIRED); self.assertEqual(set(gate["required_fields"]),FIELDS); self.assertTrue(gate["fail_closed"]); self.assertTrue(gate["requires_dedicated_negative_tests"])
    def test_no_automatic_operating_mutation(self):
        self.assertEqual(self.policy["mode"],"DEVELOPMENT_GUIDANCE_ONLY"); self.assertFalse(self.policy["automatic_prompt_policy_weight_change"])

if __name__=="__main__": unittest.main()
