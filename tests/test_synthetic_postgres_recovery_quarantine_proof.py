from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import unittest

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_postgres_recovery_quarantine_proof import *
from tests.test_synthetic_postgres_connection_loss_proof import complete as prior_complete


def d(value): return sha256(value.encode()).hexdigest()


def planned():
    prior = prior_complete(); proof = SyntheticPostgresRecoveryQuarantineProof()
    for cid in range(17901, 18301):
        workstream, aspect = proof._expected(cid)
        proof.add_control(cid, workstream, aspect, f"synthetic:postgres-recovery-quarantine-proof-requirement:{(cid-17901)//20:02}", d(str(cid)), "EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS")
    proof.anchor(prior, mapping_digest(STAGE_MAPPING), d("registry"), d("manifest"), APPLIED_LESSONS, APPLIED_RULES, prior._snapshot.digest, 21, True)
    return proof


def complete():
    proof = planned(); proof.finalize("synthetic:postgres-recovery-quarantine-proof-docket:final"); return proof


def valid_proof():
    return {"status":"PASS_POSTGRES_RECOVERY_QUARANTINE_PROOF","case_state":CASE_STATE,"deterministic_case_identity":True,"source_event_exact_match":True,"idempotency_key_exact_match":True,"payload_digest_exact_match":True,"sqlstate_exact_match":True,"provenance_exact_match":True,"observed_at_exact_match":True,"sequence_exact_match":True,"same_payload_replay_row_count":1,"same_payload_replay_converged":True,"changed_payload_fail_closed":True,"cross_key_fail_closed":True,"append_only":True,"payment_authority":False,"receipt_authority":False,"retry_authority":False,"approval_authority":False,"fresh_read_only_operator_packet":True,"reconciliation_view_read_only":True,"operator_view_insert_rejected":True,"operator_view_update_rejected":True,"operator_view_delete_rejected":True,"precommit_source_row_count":0,"precommit_source_retry_count":0,"actual_network_partition_claimed":False,"actual_failover_claimed":False,"production_database_writes":0,"cleanup_succeeded":True,"credential_disclosed":False,"password_credential_configured":False}


class Tests(unittest.TestCase):
    def test_exact_400_controls_and_twenty_first_boundary(self):
        evidence = complete().evidence()
        self.assertEqual((evidence["registered_control_count"], evidence["recovery_path_count"], evidence["human_judgment_hold_count"]), (400,96,48))
        self.assertTrue(evidence["complete_postgres_recovery_quarantine_contract_evidence"])
        self.assertEqual((evidence["production_database_writes"], evidence["financial_operations"], evidence["approval_receipts_issued"]), (0,0,0))

    def test_deterministic_identity_binds_all_fields(self):
        args=("event-1","key-1",d("payload"),"57P01","ACTUAL_PRECOMMIT_BACKEND_TERMINATION")
        case_id=deterministic_case_id(*args);self.assertEqual(case_id,deterministic_case_id(*args))
        for index in range(len(args)):
            changed=list(args);changed[index]=d("other") if index==2 else "other"
            self.assertNotEqual(case_id,deterministic_case_id(*changed))
        with self.assertRaises(GovernanceRejected):deterministic_case_id("","key",d("p"),"57P01","prov")

    def test_honest_skip_and_exact_actual_pass(self):
        proof=complete();self.assertEqual(proof.evidence()["postgresql_recovery_quarantine_proof_status"],"SKIP_NO_PRECONFIGURED_TEST_DATABASE")
        self.assertTrue(proof.evidence(valid_proof())["postgresql_recovery_quarantine_proof_claimed"])

    def test_changed_replay_authority_source_write_and_overclaim_fail_closed(self):
        mutations=(("same_payload_replay_row_count",2),("changed_payload_fail_closed",False),("cross_key_fail_closed",False),("retry_authority",True),("payment_authority",True),("operator_view_insert_rejected",False),("operator_view_update_rejected",False),("operator_view_delete_rejected",False),("precommit_source_row_count",1),("precommit_source_retry_count",1),("actual_network_partition_claimed",True),("actual_failover_claimed",True),("production_database_writes",1))
        for key,value in mutations:
            bad=valid_proof();bad[key]=value
            with self.assertRaises(GovernanceRejected):complete().evidence(bad)

    def test_missing_unknown_and_extra_proof_fields_fail_closed(self):
        for mutation in ("missing","extra"):
            bad=valid_proof()
            if mutation=="missing":bad.pop("sequence_exact_match")
            else:bad["unexpected"]=True
            with self.assertRaises(GovernanceRejected):complete().evidence(bad)

    def test_mutated_prior_snapshot_cleanup_and_append_only_fail_closed(self):
        proof=complete();proof._source._docket=replace(proof._source._docket,production_writes=1)
        self.assertFalse(proof.evidence()["complete_postgres_recovery_quarantine_contract_evidence"])
        for key,value in (("cleanup_succeeded",False),("append_only",False),("fresh_read_only_operator_packet",False),("reconciliation_view_read_only",False)):
            bad=valid_proof();bad[key]=value
            with self.assertRaises(GovernanceRejected):complete().evidence(bad)

    def test_recovery_guidance_is_complete_and_actionable(self):
        paths=recovery_paths();self.assertEqual(len(paths),3)
        for path in paths:
            row=dict(path)
            for field in ("cause","recommended","method","alternative","cost","risk","reversibility","validation","stop","resume","rollback"):self.assertIn(field,row)

    def test_integration_replay_uses_database_timestamptz_equality(self):
        source=(Path(__file__).resolve().parents[1]/"scripts/run_postgres_recovery_quarantine_integration.py").read_text(encoding="utf-8")
        self.assertGreaterEqual(source.count("observed_at = %s::timestamptz"),2)
        self.assertNotIn("observed_at::text",source)
        self.assertNotIn("startswith(",source)
        self.assertIn("expected=values[:6]+(True,)+values[7:]",source)


if __name__ == "__main__": unittest.main()
