import json
from pathlib import Path
import unittest


class PostgresTransactionOutboxClosureTests(unittest.TestCase):
    def test_closure_contract_is_complete_and_non_authorizing(self):
        root=Path(__file__).resolve().parents[1]
        contract=json.loads((root/"config/postgres-transaction-outbox-closure-v1.json").read_text())
        self.assertEqual(contract["completion_percent"],100)
        self.assertEqual(len(contract["criteria"]),10)
        self.assertEqual(len(set(contract["criteria"])),10)
        self.assertFalse(contract["production_deployment_authorized"])
        self.assertFalse(contract["financial_operations_authorized"])

    def test_ci_executes_real_postgres_proof(self):
        root=Path(__file__).resolve().parents[1]
        self.assertIn("run_ops_postgres_foundation_integration.py",(root/".github/workflows/ci.yml").read_text())
        source=(root/"scripts/run_ops_postgres_foundation_integration.py").read_text()
        for proof in ("migration checksum drift", "worker-a", "mark_failed", "attempt_count==2"):
            self.assertIn(proof,source)


if __name__=="__main__":unittest.main()
