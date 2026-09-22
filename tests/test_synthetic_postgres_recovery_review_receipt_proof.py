from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import unittest

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_postgres_recovery_review_receipt_proof import *
from tests.test_synthetic_postgres_recovery_supersession_proof import complete as prior_complete


def digest(value): return sha256(value.encode()).hexdigest()


def planned():
    prior = prior_complete(); proof = SyntheticPostgresRecoveryReviewReceiptProof()
    for control_id in range(19101, 19501):
        workstream, aspect = proof._expected(control_id)
        proof.add_control(control_id, workstream, aspect, f"synthetic:postgres-recovery-review-receipt-proof-requirement:{(control_id-19101)//20:02}", digest(str(control_id)), "EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS")
    proof.anchor(prior, mapping_digest(STAGE_MAPPING), digest("registry"), digest("manifest"), APPLIED_LESSONS, APPLIED_RULES, prior._snapshot.digest, 24, True)
    return proof


def complete():
    proof = planned(); proof.finalize("synthetic:postgres-recovery-review-receipt-proof-docket:final"); return proof


class Tests(unittest.TestCase):
    def test_exact_controls_and_non_executable_boundary(self):
        evidence = complete().evidence()
        self.assertEqual((evidence["registered_control_count"], evidence["recovery_path_count"], evidence["human_judgment_hold_count"]), (400, 96, 48))
        self.assertTrue(evidence["complete_postgres_recovery_review_receipt_contract_evidence"])
        self.assertEqual((evidence["production_database_writes"], evidence["financial_operations"], evidence["approval_receipts_issued"]), (0, 0, 0))

    def test_snapshot_identity_binds_exact_current_head(self):
        args = ("case", "supersession", digest("head"), 2, "review-key")
        identity = deterministic_review_snapshot_id(*args)
        self.assertEqual(identity, deterministic_review_snapshot_id(*args))
        for index in range(len(args)):
            changed = list(args); changed[index] = 3 if index == 3 else digest("other") if index == 2 else "other"
            self.assertNotEqual(identity, deterministic_review_snapshot_id(*changed))

    def test_receipt_identity_binds_snapshot_reviewer_and_result(self):
        args = ("snapshot", digest("snapshot"), "reviewer", digest("result"))
        identity = deterministic_review_receipt_id(*args)
        self.assertEqual(identity, deterministic_review_receipt_id(*args))
        for index in range(len(args)):
            changed = list(args); changed[index] = digest("other") if index in (1, 3) else "other"
            self.assertNotEqual(identity, deterministic_review_receipt_id(*changed))

    def test_honest_skip_and_exact_actual_pass(self):
        self.assertEqual(complete().evidence()["postgresql_recovery_review_receipt_proof_status"], "SKIP_NO_PRECONFIGURED_TEST_DATABASE")
        self.assertTrue(complete().evidence(dict(EXPECTED_PROOF))["postgresql_recovery_review_receipt_proof_claimed"])

    def test_database_constraints_replace_application_only_checks(self):
        source = (Path(__file__).resolve().parents[1] / "scripts/run_postgres_recovery_review_receipt_integration.py").read_text(encoding="utf-8")
        for clause in ("require_current_head", "exact_current_head", "UNIQUE(snapshot_id,snapshot_digest)", "UNIQUE", "snapshot_append_only", "receipt_append_only", "default_transaction_read_only=on"):
            self.assertIn(clause, source)

    def test_tamper_authority_and_overclaim_fail_closed(self):
        for key, value in (("stale_head_fail_closed", False), ("receipt_tamper_fail_closed", False), ("single_receipt_enforced", False), ("execution_authority", True), ("receipt_authority", True), ("actual_failover_claimed", True), ("production_database_writes", 1)):
            bad = dict(EXPECTED_PROOF); bad[key] = value
            with self.assertRaises(GovernanceRejected): complete().evidence(bad)

    def test_missing_extra_cleanup_and_prior_mutation_fail_closed(self):
        bad = dict(EXPECTED_PROOF); bad.pop("single_receipt_enforced")
        with self.assertRaises(GovernanceRejected): complete().evidence(bad)
        bad = dict(EXPECTED_PROOF); bad["extra"] = True
        with self.assertRaises(GovernanceRejected): complete().evidence(bad)
        bad = dict(EXPECTED_PROOF); bad["cleanup_succeeded"] = False
        with self.assertRaises(GovernanceRejected): complete().evidence(bad)
        proof = complete(); proof._source._docket = replace(proof._source._docket, production_writes=1)
        self.assertFalse(proof.evidence()["complete_postgres_recovery_review_receipt_contract_evidence"])

    def test_recovery_guidance_complete_and_actionable(self):
        self.assertEqual(len(recovery_paths()), 3)
        for path in recovery_paths():
            row = dict(path)
            for field in ("cause", "recommended", "method", "alternative", "cost", "risk", "reversibility", "validation", "stop", "resume", "rollback"):
                self.assertIn(field, row)

    def test_multinode_preflight_remains_contract_only(self):
        evidence = complete().evidence()
        self.assertTrue(evidence["multinode_preflight_contract_complete"])
        self.assertFalse(evidence["actual_network_partition_claimed"])
        self.assertFalse(evidence["actual_failover_claimed"])
        self.assertFalse(evidence["fault_injection_performed"])


if __name__ == "__main__": unittest.main()
