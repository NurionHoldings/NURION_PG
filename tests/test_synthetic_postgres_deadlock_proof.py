from dataclasses import replace
from hashlib import sha256
import unittest

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_postgres_deadlock_proof import *
from tests.test_synthetic_postgres_retry_resilience_proof import complete as prior_complete

def d(v):return sha256(v.encode()).hexdigest()
def planned():
    prior=prior_complete();s=SyntheticPostgresDeadlockProof()
    for cid in range(17101,17501):
        w,a=s._expected(cid);s.add_control(cid,w,a,f"synthetic:postgres-deadlock-proof-requirement:{(cid-17101)//25:02}",d(str(cid)),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    s.anchor(prior,mapping_digest(STAGE_MAPPING),d("registry"),d("manifest"),APPLIED_LESSONS,APPLIED_RULES,prior._snapshot.digest,19,True);return s
def complete():s=planned();s.finalize("synthetic:postgres-deadlock-proof-docket:final");return s
def valid_proof():return {"status":"PASS_POSTGRES_DEADLOCK_PROOF","deadlock_sqlstate":"40P01","deadlock_failures":1,"deadlock_successes":1,"deadlock_provenance":"ACTUAL_POSTGRESQL_TWO_BACKEND_OPPOSITE_ROW_LOCK_ORDER","deadlock_timeout_preflight":"ACTUAL_POSTGRESQL_SET_LOCAL_CONFIRMED","failed_transaction_rolled_back":True,"failed_backend_closed":True,"fresh_backend_retry":True,"retry_success_attempt":2,"bounded_retry_max_attempts":3,"lock_timeout_sqlstate":"55P03","lock_timeout_attempts":1,"lock_timeout_provenance":"ACTUAL_POSTGRESQL_BLOCKED_ROW_LOCK","lock_timeout_non_retryable":True,"unit_retry_exhaustion_provenance":"UNIT_INJECTED_SQLSTATE_SEQUENCE","harness_commit_unknown_provenance":"HARNESS_INJECTED_POST_COMMIT_RESPONSE_LOSS","actual_network_partition_claimed":False,"actual_failover_claimed":False,"production_database_writes":0,"cleanup_succeeded":True,"credential_disclosed":False,"password_credential_configured":False}

class Tests(unittest.TestCase):
    def test_exact_400_controls_and_nineteenth_boundary(self):
        e=complete().evidence();self.assertEqual((e["registered_control_count"],e["recovery_path_count"],e["human_judgment_hold_count"]),(400,64,32));self.assertTrue(e["complete_postgres_deadlock_contract_evidence"]);self.assertEqual((e["production_database_writes"],e["approval_receipts_issued"],e["financial_operations"]),(0,0,0))
    def test_honest_skip_and_exact_actual_provenance_pass(self):
        s=complete();self.assertEqual(s.evidence()["postgresql_deadlock_proof_status"],"SKIP_NO_PRECONFIGURED_TEST_DATABASE");self.assertTrue(s.evidence(valid_proof())["actual_deadlock_claimed"])
        for key,value in (("deadlock_provenance","UNIT_INJECTED"),("lock_timeout_provenance","HARNESS_INJECTED"),("actual_network_partition_claimed",True),("actual_failover_claimed",True)):
            bad=valid_proof();bad[key]=value
            with self.assertRaisesRegex(GovernanceRejected,"complete exact"):s.evidence(bad)
    def test_40p01_retryable_and_55p03_non_retryable(self):
        self.assertEqual(classify_sqlstate("40P01"),"RETRYABLE_TRANSACTION");self.assertEqual(classify_sqlstate("55P03"),"NON_RETRYABLE_FAIL_CLOSED")
    def test_deadlock_timeout_permission_and_missing_actual_result_fail_closed(self):
        for key,value in (("deadlock_timeout_preflight","DENIED"),("deadlock_failures",0),("deadlock_successes",2),("failed_transaction_rolled_back",False),("failed_backend_closed",False),("fresh_backend_retry",False),("retry_success_attempt",3),("lock_timeout_attempts",2),("cleanup_succeeded",False),("production_database_writes",1)):
            bad=valid_proof();bad[key]=value
            with self.assertRaises(GovernanceRejected):complete().evidence(bad)
    def test_mutated_prior_and_snapshot_fail_closed(self):
        s=complete();s._source._docket=replace(s._source._docket,production_writes=1);self.assertFalse(s.evidence()["complete_postgres_deadlock_contract_evidence"])
        with self.assertRaises(GovernanceRejected):planned().finalize("wrong")
    def test_recovery_guidance_contains_executable_paths(self):
        paths=recovery_paths();self.assertEqual(len(paths),2)
        for path in paths:
            row=dict(path)
            for field in ("cause","recommended","method","alternative","cost","risk","reversibility","validation","stop","resume","rollback"):self.assertIn(field,row)

if __name__=="__main__":unittest.main()
