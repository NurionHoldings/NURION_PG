from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import unittest
from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_postgres_recovery_disposition_proof import *
from tests.test_synthetic_postgres_recovery_quarantine_proof import complete as prior_complete

def d(v):return sha256(v.encode()).hexdigest()
def planned():
    prior=prior_complete();proof=SyntheticPostgresRecoveryDispositionProof()
    for cid in range(18301,18701):
        w,a=proof._expected(cid);proof.add_control(cid,w,a,f"synthetic:postgres-recovery-disposition-proof-requirement:{(cid-18301)//20:02}",d(str(cid)),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    proof.anchor(prior,mapping_digest(STAGE_MAPPING),d("registry"),d("manifest"),APPLIED_LESSONS,APPLIED_RULES,prior._snapshot.digest,22,True);return proof
def complete():p=planned();p.finalize("synthetic:postgres-recovery-disposition-proof-docket:final");return p
def valid_proof():return dict(EXPECTED_PROOF)

class Tests(unittest.TestCase):
    def test_exact_400_controls_and_next_boundary(self):
        e=complete().evidence();self.assertEqual((e["registered_control_count"],e["recovery_path_count"],e["human_judgment_hold_count"]),(400,96,48));self.assertTrue(e["complete_postgres_recovery_disposition_contract_evidence"]);self.assertEqual((e["production_database_writes"],e["financial_operations"],e["approval_receipts_issued"]),(0,0,0))
    def test_deterministic_identity_binds_all_fields(self):
        args=("rq_case","review-key",d("case"),"reviewer-1",DISPOSITION_STATE);ident=deterministic_disposition_id(*args);self.assertEqual(ident,deterministic_disposition_id(*args))
        for i in range(len(args)):
            changed=list(args);changed[i]=d("other") if i==2 else "other";
            if i==4:
                with self.assertRaises(GovernanceRejected):deterministic_disposition_id(*changed)
            else:self.assertNotEqual(ident,deterministic_disposition_id(*changed))
    def test_honest_skip_and_exact_actual_pass(self):self.assertEqual(complete().evidence()["postgresql_recovery_disposition_proof_status"],"SKIP_NO_PRECONFIGURED_TEST_DATABASE");self.assertTrue(complete().evidence(valid_proof())["postgresql_recovery_disposition_proof_claimed"])
    def test_conflict_authority_and_overclaim_fail_closed(self):
        for key,value in (("same_payload_replay_row_count",2),("changed_payload_fail_closed",False),("cross_key_fail_closed",False),("quarantine_unchanged",False),("execution_authority",True),("receipt_authority",True),("operator_view_insert_rejected",False),("actual_network_partition_claimed",True),("actual_failover_claimed",True),("fault_injection_performed",True),("production_database_writes",1)):
            bad=valid_proof();bad[key]=value
            with self.assertRaises(GovernanceRejected):complete().evidence(bad)
    def test_wrong_digest_new_key_sequence_fail_closed(self):
        for key in ("new_key_new_sequence_wrong_digest_fail_closed","composite_case_digest_fk_enforced"):
            bad=valid_proof();bad[key]=False
            with self.assertRaises(GovernanceRejected):complete().evidence(bad)
    def test_database_enforces_one_disposition_per_case_and_safe_diagnostics(self):
        source=(Path(__file__).resolve().parents[1]/"scripts/run_postgres_recovery_disposition_integration.py").read_text(encoding="utf-8")
        self.assertIn("case_id text NOT NULL UNIQUE",source)
        self.assertIn("FOREIGN KEY(case_id,case_digest)",source)
        self.assertIn('failed=sorted(key for key,value in invariants.items() if not value)',source)
        self.assertIn('"cross_key_same_case_rejected":cross_failed',source)
    def test_missing_extra_cleanup_and_prior_mutation_fail_closed(self):
        bad=valid_proof();bad.pop("sequence_exact_match")
        with self.assertRaises(GovernanceRejected):complete().evidence(bad)
        bad=valid_proof();bad["extra"]=True
        with self.assertRaises(GovernanceRejected):complete().evidence(bad)
        bad=valid_proof();bad["cleanup_succeeded"]=False
        with self.assertRaises(GovernanceRejected):complete().evidence(bad)
        proof=complete();proof._source._docket=replace(proof._source._docket,production_writes=1);self.assertFalse(proof.evidence()["complete_postgres_recovery_disposition_contract_evidence"])
    def test_recovery_guidance_complete_and_actionable(self):
        self.assertEqual(len(recovery_paths()),3)
        for p in recovery_paths():
            row=dict(p)
            for field in ("cause","recommended","method","alternative","cost","risk","reversibility","validation","stop","resume","rollback"):self.assertIn(field,row)
    def test_multinode_preflight_is_contract_only(self):
        e=complete().evidence();self.assertTrue(e["multinode_preflight_contract_complete"]);self.assertFalse(e["actual_network_partition_claimed"]);self.assertFalse(e["actual_failover_claimed"]);self.assertFalse(e["fault_injection_performed"])

if __name__=="__main__":unittest.main()
