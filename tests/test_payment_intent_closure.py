import json
from pathlib import Path
import unittest


class PaymentIntentClosureTests(unittest.TestCase):
    def test_closure_is_complete_but_non_authorizing(self):
        root=Path(__file__).resolve().parents[1]
        value=json.loads((root/"config/payment-intent-api-closure-v1.json").read_text())
        self.assertEqual(value["completion_percent"],100);self.assertEqual(len(value["criteria"]),12);self.assertEqual(len(set(value["criteria"])),12)
        self.assertFalse(value["external_provider_connected"]);self.assertFalse(value["production_deployment_authorized"]);self.assertFalse(value["financial_operations_authorized"])

    def test_public_routes_never_apply_provider_success(self):
        root=Path(__file__).resolve().parents[1]
        app=(root/"src/nurion_pg/api/app.py").read_text();repo=(root/"src/nurion_pg/storage/payment_repository.py").read_text()
        self.assertNotIn("apply_provider_result(",app);self.assertIn("Internal adapter boundary",repo)


if __name__=="__main__":unittest.main()
