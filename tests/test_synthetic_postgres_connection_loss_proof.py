from dataclasses import replace
from hashlib import sha256
import unittest

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_postgres_connection_loss_proof import *
from tests.test_synthetic_postgres_deadlock_proof import complete as prior_complete

def d(v):return sha256(v.encode()).hexdigest()
def planned():
    prior=prior_complete();s=SyntheticPostgresConnectionLossProof()
    for cid in range(17501,17901):
        w,a=s._expected(cid);s.add_control(cid,w,a,f"synthetic:postgres-connection-loss-proof-requirement:{(cid-17501)//25:02}",d(str(cid)),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    s.anchor(prior,mapping_digest(STAGE_MAPPING),d("registry"),d("manifest"),APPLIED_LESSONS,APPLIED_RULES,prior._snapshot.digest,20,True);return s
def complete():s=planned();s.finalize("synthetic:postgres-connection-loss-proof-docket:final");return s
def valid_proof(state="57P01"):
    return {"status":"PASS_POSTGRES_CONNECTION_LOSS_PROOF","termination_function":"ACTUAL_PG_TERMINATE_BACKEND","termination_privilege_preflight":"ACTUAL_DISPOSABLE_POSTGRESQL_GRANTED","precommit_sqlstate":state,"precommit_classification":"CONNECTION_LOSS_FAIL_CLOSED","precommit_row_absent":True,"precommit_blind_retry_count":0,"precommit_outcome":"HOLD_NOT_COMMITTED","committed_before_termination":True,"postcommit_sqlstate":state,"postcommit_classification":"CONNECTION_LOSS_FAIL_CLOSED","fresh_read_only_connection":True,"idempotency_key_exact_match":True,"payload_digest_exact_match":True,"reconciled_outcome":"COMMITTED_CONFIRMED_BY_FRESH_EXACT_READ","postcommit_response_loss_provenance":"ACTUAL_BACKEND_TERMINATION_AFTER_ACKNOWLEDGED_COMMIT_NOT_COMMIT_RESPONSE_LOSS","actual_network_partition_claimed":False,"actual_failover_claimed":False,"production_database_writes":0,"cleanup_succeeded":True,"credential_disclosed":False,"password_credential_configured":False}

class Tests(unittest.TestCase):
    def test_exact_400_controls_and_twentieth_boundary(self):
        e=complete().evidence();self.assertEqual((e["registered_control_count"],e["recovery_path_count"],e["human_judgment_hold_count"]),(400,96,48));self.assertTrue(e["complete_postgres_connection_loss_contract_evidence"]);self.assertEqual((e["production_database_writes"],e["approval_receipts_issued"],e["financial_operations"]),(0,0,0))
    def test_honest_skip_and_exact_actual_termination_pass(self):
        s=complete();self.assertEqual(s.evidence()["postgresql_connection_loss_proof_status"],"SKIP_NO_PRECONFIGURED_TEST_DATABASE")
        for state in ALLOWED_TERMINATION_SQLSTATES:self.assertTrue(s.evidence(valid_proof(state))["actual_backend_termination_claimed"])
    def test_unlisted_or_missing_sqlstate_fails_closed(self):
        for state in (None,"08003","57P02","40001"):
            bad=valid_proof();bad["precommit_sqlstate"]=state
            with self.assertRaisesRegex(GovernanceRejected,"complete exact"):complete().evidence(bad)
            with self.assertRaises(GovernanceRejected):classify_termination_sqlstate(state)
    def test_precommit_requires_absence_hold_and_zero_blind_retry(self):
        for key,value in (("precommit_row_absent",False),("precommit_blind_retry_count",1),("precommit_outcome","RETRIED"),("termination_privilege_preflight","DENIED")):
            bad=valid_proof();bad[key]=value
            with self.assertRaises(GovernanceRejected):complete().evidence(bad)
    def test_commit_reconciliation_is_exact_and_does_not_overclaim(self):
        for key,value in (("committed_before_termination",False),("fresh_read_only_connection",False),("idempotency_key_exact_match",False),("payload_digest_exact_match",False),("actual_network_partition_claimed",True),("actual_failover_claimed",True),("postcommit_response_loss_provenance","ACTUAL_NETWORK_RESPONSE_LOSS")):
            bad=valid_proof();bad[key]=value
            with self.assertRaises(GovernanceRejected):complete().evidence(bad)
    def test_mutated_prior_snapshot_cleanup_and_production_fail_closed(self):
        s=complete();s._source._docket=replace(s._source._docket,production_writes=1);self.assertFalse(s.evidence()["complete_postgres_connection_loss_contract_evidence"])
        for key,value in (("cleanup_succeeded",False),("production_database_writes",1)):
            bad=valid_proof();bad[key]=value
            with self.assertRaises(GovernanceRejected):complete().evidence(bad)
    def test_recovery_guidance_contains_executable_paths(self):
        paths=recovery_paths();self.assertEqual(len(paths),3)
        for path in paths:
            row=dict(path)
            for field in ("cause","recommended","method","alternative","cost","risk","reversibility","validation","stop","resume","rollback"):self.assertIn(field,row)
if __name__=="__main__":unittest.main()
