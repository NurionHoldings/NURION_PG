from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import unittest

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_postgres_recovery_recommendation_concurrence_proof import *
from tests.test_synthetic_postgres_recovery_review_receipt_proof import complete as prior_complete

def d(value):return sha256(value.encode()).hexdigest()
def planned():
    prior=prior_complete();proof=SyntheticPostgresRecoveryRecommendationConcurrenceProof()
    for cid in range(19501,19901):
        workstream,aspect=proof._expected(cid);proof.add_control(cid,workstream,aspect,f"synthetic:postgres-recovery-recommendation-concurrence-proof-requirement:{(cid-19501)//20:02}",d(str(cid)),"EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS")
    proof.anchor(prior,mapping_digest(STAGE_MAPPING),d("registry"),d("manifest"),APPLIED_LESSONS,APPLIED_RULES,prior._snapshot.digest,25,True);return proof
def complete():proof=planned();proof.finalize("synthetic:postgres-recovery-recommendation-concurrence-proof-docket:final");return proof

class Tests(unittest.TestCase):
    def test_exact_controls_and_non_executable_boundary(self):
        evidence=complete().evidence();self.assertEqual((evidence["registered_control_count"],evidence["recovery_path_count"],evidence["human_judgment_hold_count"]),(400,96,48));self.assertTrue(evidence["complete_postgres_recovery_recommendation_concurrence_contract_evidence"]);self.assertEqual((evidence["production_database_writes"],evidence["financial_operations"],evidence["approval_receipts_issued"]),(0,0,0))
    def test_recommendation_identity_binds_receipt_author_action_and_risk(self):
        args=("receipt",d("receipt"),"key","author",d("action"),d("risk"));identity=deterministic_recommendation_id(*args);self.assertEqual(identity,deterministic_recommendation_id(*args))
        for index in range(len(args)):
            changed=list(args);changed[index]=d("other") if index in (1,4,5) else "other";self.assertNotEqual(identity,deterministic_recommendation_id(*changed))
    def test_concurrence_identity_binds_recommendation_reviewer_verdict_and_rationale(self):
        args=("recommendation",d("recommendation"),"reviewer","CONCUR_NON_EXECUTABLE",d("rationale"));identity=deterministic_concurrence_id(*args);self.assertEqual(identity,deterministic_concurrence_id(*args))
        for index in range(len(args)):
            changed=list(args);changed[index]=d("other") if index in (1,4) else "HOLD_CONFLICT" if index==3 else "other";self.assertNotEqual(identity,deterministic_concurrence_id(*changed))
    def test_honest_skip_and_exact_actual_pass(self):self.assertEqual(complete().evidence()["postgresql_recovery_recommendation_concurrence_proof_status"],"SKIP_NO_PRECONFIGURED_TEST_DATABASE");self.assertTrue(complete().evidence(dict(EXPECTED_PROOF))["postgresql_recovery_recommendation_concurrence_proof_claimed"])
    def test_database_constraints_replace_application_only_checks(self):
        source=(Path(__file__).resolve().parents[1]/"scripts/run_postgres_recovery_recommendation_concurrence_integration.py").read_text(encoding="utf-8")
        for clause in ("author_subject<>reviewer_subject","UNIQUE(recommendation_id,reviewer_subject)","HOLD_CONFLICT","recommendation_append_only","concurrence_append_only","default_transaction_read_only=on"):self.assertIn(clause,source)
    def test_conflict_authority_and_overclaim_fail_closed(self):
        for key,value in (("author_reviewer_separation_enforced",False),("conflicting_verdict_preserves_hold",False),("single_reviewer_verdict_enforced",False),("execution_authority",True),("approval_authority",True),("actual_failover_claimed",True),("production_database_writes",1)):
            bad=dict(EXPECTED_PROOF);bad[key]=value
            with self.assertRaises(GovernanceRejected):complete().evidence(bad)
    def test_missing_extra_cleanup_and_prior_mutation_fail_closed(self):
        bad=dict(EXPECTED_PROOF);bad.pop("single_reviewer_verdict_enforced")
        with self.assertRaises(GovernanceRejected):complete().evidence(bad)
        bad=dict(EXPECTED_PROOF);bad["extra"]=True
        with self.assertRaises(GovernanceRejected):complete().evidence(bad)
        bad=dict(EXPECTED_PROOF);bad["cleanup_succeeded"]=False
        with self.assertRaises(GovernanceRejected):complete().evidence(bad)
        proof=complete();proof._source._docket=replace(proof._source._docket,production_writes=1);self.assertFalse(proof.evidence()["complete_postgres_recovery_recommendation_concurrence_contract_evidence"])
    def test_recovery_guidance_complete_and_actionable(self):
        self.assertEqual(len(recovery_paths()),3)
        for path in recovery_paths():
            row=dict(path)
            for field in ("cause","recommended","method","alternative","cost","risk","reversibility","validation","stop","resume","rollback"):self.assertIn(field,row)
    def test_multinode_preflight_remains_contract_only(self):
        evidence=complete().evidence();self.assertTrue(evidence["multinode_preflight_contract_complete"]);self.assertFalse(evidence["actual_network_partition_claimed"]);self.assertFalse(evidence["actual_failover_claimed"]);self.assertFalse(evidence["fault_injection_performed"])

if __name__=="__main__":unittest.main()
