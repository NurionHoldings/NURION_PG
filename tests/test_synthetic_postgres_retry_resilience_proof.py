from hashlib import sha256
from dataclasses import replace
import unittest

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_postgres_retry_resilience_proof import *
from tests.test_synthetic_postgres_ephemeral_repository_proof import complete as prior_complete

def d(v):return sha256(v.encode()).hexdigest()
def planned():
    prior=prior_complete();s=SyntheticPostgresRetryResilienceProof()
    for cid in range(16701,17101):
        w,a=s._expected(cid);s.add_control(cid,w,a,f"synthetic:postgres-retry-proof-requirement:{(cid-16701)//25:02}",d(str(cid)),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    s.anchor(prior,mapping_digest(STAGE_MAPPING),d("registry"),d("manifest"),APPLIED_LESSONS,APPLIED_RULES,prior._snapshot.digest,18,True);return s
def complete():s=planned();s.finalize("synthetic:postgres-retry-proof-docket:final");return s
def valid_proof():return {"status":"PASS_POSTGRES_RETRY_RESILIENCE","serialization_sqlstate":"40001","serialization_failures":1,"serialization_success_attempt":2,"bounded_retry_max_attempts":3,"retry_exhaustion_mode":"UNIT_INJECTED_SQLSTATE_SEQUENCE","retry_exhaustion_fail_closed":True,"actual_retry_exhaustion_claimed":False,"timeout_sqlstate":"57014","timeout_attempts":1,"non_retryable_timeout_fail_closed":True,"fresh_connection_per_retry":True,"commit_unknown_mode":"HARNESS_INJECTED_POST_COMMIT_RESPONSE_LOSS","commit_unknown_readback_confirmed":True,"payload_mismatch_fail_closed":True,"production_database_writes":0,"cleanup_succeeded":True,"credential_disclosed":False,"password_credential_configured":False,"actual_network_partition_claimed":False,"actual_deadlock_claimed":False}

class SqlError(Exception):
    def __init__(self,state):self.sqlstate=state

class Tests(unittest.TestCase):
    def test_exact_400_controls_and_eighteenth_boundary(self):
        e=complete().evidence();self.assertEqual((e["registered_control_count"],e["recovery_path_count"],e["human_judgment_hold_count"]),(400,64,32));self.assertTrue(e["complete_postgres_retry_resilience_contract_evidence"]);self.assertEqual((e["production_database_writes"],e["approval_receipts_issued"],e["financial_operations"]),(0,0,0))
    def test_honest_skip_and_exact_pass(self):
        s=complete();self.assertEqual(s.evidence()["postgresql_retry_proof_status"],"SKIP_NO_PRECONFIGURED_TEST_DATABASE");self.assertTrue(s.evidence(valid_proof())["postgresql_retry_proof_claimed"])
        bad=valid_proof();bad["actual_network_partition_claimed"]=True
        with self.assertRaisesRegex(GovernanceRejected,"complete exact"):s.evidence(bad)
    def test_serialization_and_deadlock_only_are_blind_retryable(self):
        self.assertEqual(classify_sqlstate("40001"),"RETRYABLE_TRANSACTION");self.assertEqual(classify_sqlstate("40P01"),"RETRYABLE_TRANSACTION")
        for state in ("08006","57P01"):self.assertEqual(classify_sqlstate(state),"COMMIT_OUTCOME_UNKNOWN_READBACK_REQUIRED")
        for state in ("57014","23505",None):self.assertEqual(classify_sqlstate(state),"NON_RETRYABLE_FAIL_CLOSED")
    def test_bounded_retry_succeeds_with_fresh_attempt_identity(self):
        seen=[]
        def operation(attempt):
            seen.append(attempt)
            if attempt<3:raise SqlError("40001")
            return "ok"
        self.assertEqual(bounded_retry(operation),("ok",3));self.assertEqual(seen,[1,2,3])
    def test_retry_exhaustion_fail_closed(self):
        failures=[]
        with self.assertRaisesRegex(RetryExhausted,"3 attempts"):bounded_retry(lambda _:(_ for _ in ()).throw(SqlError("40P01")),on_failure=lambda e,a:failures.append((e.sqlstate,a)))
        self.assertEqual(failures,[("40P01",1),("40P01",2),("40P01",3)])
        with self.assertRaises(GovernanceRejected):bounded_retry(lambda _:None,4)
    def test_timeout_and_unique_are_not_retried(self):
        for state in ("57014","23505"):
            seen=[]
            with self.assertRaises(SqlError):bounded_retry(lambda a:(seen.append(a),(_ for _ in ()).throw(SqlError(state)))[1])
            self.assertEqual(seen,[1])
    def test_commit_unknown_exact_readback_or_hold(self):
        digest=d("payload");self.assertEqual(resolve_commit_unknown(lambda:("EXISTING_SAME_PAYLOAD",digest),digest),("COMMITTED_READBACK_CONFIRMED",digest))
        for result in (None,("INSERTED",digest),("EXISTING_SAME_PAYLOAD",d("changed")),("OTHER",digest)):
            with self.assertRaisesRegex(GovernanceRejected,"commit outcome unknown"):resolve_commit_unknown(lambda r=result:r,digest)
    def test_mutated_source_snapshot_and_proof_fail_closed(self):
        s=complete();s._source._docket=replace(s._source._docket,production_writes=1);self.assertFalse(s.evidence()["complete_postgres_retry_resilience_contract_evidence"])
        for key,value in (("serialization_failures",0),("serialization_success_attempt",3),("bounded_retry_max_attempts",4),("retry_exhaustion_mode","ACTUAL_POSTGRESQL"),("retry_exhaustion_fail_closed",False),("actual_retry_exhaustion_claimed",True),("timeout_sqlstate","40001"),("timeout_attempts",2),("cleanup_succeeded",False),("production_database_writes",1),("actual_deadlock_claimed",True)):
            bad=valid_proof();bad[key]=value
            with self.assertRaises(GovernanceRejected):complete().evidence(bad)

if __name__=="__main__":unittest.main()
