from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import unittest
from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_postgres_recovery_supersession_proof import *
from tests.test_synthetic_postgres_recovery_disposition_proof import complete as prior_complete

def d(v):return sha256(v.encode()).hexdigest()
def planned():
    prior=prior_complete();proof=SyntheticPostgresRecoverySupersessionProof()
    for cid in range(18701,19101):
        w,a=proof._expected(cid);proof.add_control(cid,w,a,f"synthetic:postgres-recovery-supersession-proof-requirement:{(cid-18701)//20:02}",d(str(cid)),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    proof.anchor(prior,mapping_digest(STAGE_MAPPING),d("registry"),d("manifest"),APPLIED_LESSONS,APPLIED_RULES,prior._snapshot.digest,23,True);return proof
def complete():p=planned();p.finalize("synthetic:postgres-recovery-supersession-proof-docket:final");return p
def valid_proof():return dict(EXPECTED_PROOF)

class Tests(unittest.TestCase):
    def test_exact_400_controls_and_next_boundary(self):
        e=complete().evidence();self.assertEqual((e["registered_control_count"],e["recovery_path_count"],e["human_judgment_hold_count"]),(400,96,48));self.assertTrue(e["complete_postgres_recovery_supersession_contract_evidence"]);self.assertEqual((e["production_database_writes"],e["financial_operations"],e["approval_receipts_issued"]),(0,0,0))
    def test_deterministic_identity_binds_predecessor_payload_and_version(self):
        args=("case","key",d("pred"),d("payload"),2,SUPERSESSION_STATE);ident=deterministic_supersession_id(*args);self.assertEqual(ident,deterministic_supersession_id(*args))
        for i in range(5):
            changed=list(args);changed[i]=3 if i==4 else d("other") if i in (2,3) else "other";self.assertNotEqual(ident,deterministic_supersession_id(*changed))
    def test_honest_skip_and_exact_actual_pass(self):self.assertEqual(complete().evidence()["postgresql_recovery_supersession_proof_status"],"SKIP_NO_PRECONFIGURED_TEST_DATABASE");self.assertTrue(complete().evidence(valid_proof())["postgresql_recovery_supersession_proof_claimed"])
    def test_fork_stale_alias_authority_and_overclaim_fail_closed(self):
        for key,value in (("predecessor_fork_fail_closed",False),("stale_head_fail_closed",False),("alias_predecessor_fail_closed",False),("lineage_sequence_gap_fail_closed",False),("lineage_sequence_reuse_fail_closed",False),("one_current_head",False),("base_disposition_immutable",False),("execution_authority",True),("receipt_authority",True),("actual_network_partition_claimed",True),("actual_failover_claimed",True),("fault_injection_performed",True),("production_database_writes",1)):
            bad=valid_proof();bad[key]=value
            with self.assertRaises(GovernanceRejected):complete().evidence(bad)
    def test_database_constraints_replace_application_only_race_checks(self):
        source=(Path(__file__).resolve().parents[1]/"scripts/run_postgres_recovery_supersession_integration.py").read_text(encoding="utf-8")
        for clause in ("one_genesis_per_case","one_successor_per_supersession","FOREIGN KEY(case_id,predecessor_supersession_id,predecessor_supersession_digest,predecessor_version)","predecessor_version=version-1","lineage_sequence=version","UNIQUE(case_id,version)","UNIQUE(case_id,lineage_sequence)","lineage_sequence=99"):self.assertIn(clause,source)
    def test_missing_extra_cleanup_and_prior_mutation_fail_closed(self):
        bad=valid_proof();bad.pop("one_current_head")
        with self.assertRaises(GovernanceRejected):complete().evidence(bad)
        bad=valid_proof();bad["extra"]=True
        with self.assertRaises(GovernanceRejected):complete().evidence(bad)
        bad=valid_proof();bad["cleanup_succeeded"]=False
        with self.assertRaises(GovernanceRejected):complete().evidence(bad)
        proof=complete();proof._source._docket=replace(proof._source._docket,production_writes=1);self.assertFalse(proof.evidence()["complete_postgres_recovery_supersession_contract_evidence"])
    def test_recovery_guidance_complete_and_actionable(self):
        self.assertEqual(len(recovery_paths()),3)
        for p in recovery_paths():
            row=dict(p)
            for field in ("cause","recommended","method","alternative","cost","risk","reversibility","validation","stop","resume","rollback"):self.assertIn(field,row)
    def test_multinode_preflight_remains_contract_only(self):
        e=complete().evidence();self.assertTrue(e["multinode_preflight_contract_complete"]);self.assertFalse(e["actual_network_partition_claimed"]);self.assertFalse(e["actual_failover_claimed"]);self.assertFalse(e["fault_injection_performed"])
if __name__=="__main__":unittest.main()
