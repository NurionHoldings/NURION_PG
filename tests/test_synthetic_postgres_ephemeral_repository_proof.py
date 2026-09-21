from dataclasses import replace
from hashlib import sha256
import unittest

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.synthetic_postgres_ephemeral_repository_proof import *
from tests.test_synthetic_postgres_reservation_ledger_contract import completed as prior_completed

def d(v):return sha256(v.encode()).hexdigest()
def planned():
    prior=prior_completed()[0];s=SyntheticPostgresEphemeralRepositoryProof()
    for cid in range(16301,16701):
        w,a=s._expected(cid);s.add_control(cid,w,a,f"synthetic:postgres-ephemeral-proof-requirement:{(cid-16301)//25:02}",d(str(cid)),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    s.anchor(prior,mapping_digest(STAGE_MAPPING),d("registry"),d("manifest"),APPLIED_LESSONS,APPLIED_RULES,prior._snapshot.digest,17,True)
    return s
def complete():
    s=planned();s.plan_fixture();s.finalize("synthetic:postgres-ephemeral-proof-docket:final");return s
def valid_proof():return {"status":"PASS_EPHEMERAL_POSTGRESQL","test_only_database_writes":2,"test_only_database_write_attempts":27,"production_database_writes":0,"cleanup_succeeded":True,"concurrency_workers":20,"concurrent_row_count":1,"isolation_level":"READ COMMITTED","conflict_classifications":list(PROOF_CLASSIFICATIONS),"database_url_disclosed":False,"credential_disclosed":False,"live_constraint_parity":True}
def live_constraints():
    return [(n,{"PRIMARY KEY":"p","UNIQUE":"u","CHECK":"c"}[k],list(c[:1] if k=="CHECK" else c),False,False,f"((state = '{MAX_STATE}'::text))" if k=="CHECK" else None) for n,k,c in fixture_plan().expected_constraints]

class Tests(unittest.TestCase):
    def test_exact_400_controls_and_final_boundary(self):
        e=complete().evidence();self.assertEqual((e["registered_control_count"],e["expected_unique_constraint_count"],e["recovery_path_count"],e["human_judgment_hold_count"]),(400,6,64,32));self.assertTrue(e["complete_postgres_ephemeral_repository_proof_contract_evidence"]);self.assertEqual((e["production_database_writes"],e["approval_receipts_issued"],e["financial_operations"]),(0,0,0))
    def test_honest_skip_and_pass_are_distinct(self):
        s=complete();skip=s.evidence();self.assertEqual(skip["postgresql_proof_status"],"SKIP_NO_PRECONFIGURED_TEST_DATABASE");self.assertFalse(skip["postgresql_proof_claimed"]);self.assertEqual(skip["postgresql_integration_skip_count"],1)
        passed=s.evidence(valid_proof());self.assertTrue(passed["postgresql_proof_claimed"]);self.assertEqual(passed["production_database_writes"],0)
    def test_production_host_database_and_schema_refused(self):
        bad=("postgresql://u:p@prod.example.com/nurion_pg_ci","postgresql://u:p@localhost/nurion_prod")
        for x in bad:
            with self.assertRaisesRegex(GovernanceRejected,"production host or database refused"):validated_disposable_target(x,"nurion_pg_ci_x")
        with self.assertRaisesRegex(GovernanceRejected,"validated disposable schema"):validated_disposable_target("postgresql://u:p@localhost/nurion_pg_ci","public")
        self.assertEqual(validated_disposable_target("postgresql://u:p@postgres/nurion_pg_ci","nurion_pg_ci_x",True)["database"],ALLOWED_DATABASE)
    def test_migration_is_exact_and_cleanup_is_narrow(self):
        up,down=migration_sql("nurion_pg_ci_contract");self.assertIn('CREATE SCHEMA "nurion_pg_ci_contract"',up);self.assertIn(f'CREATE TABLE "nurion_pg_ci_contract"."{TABLE}"',up);self.assertEqual(down,'DROP SCHEMA "nurion_pg_ci_contract" CASCADE;');self.assertNotIn("DROP DATABASE",down)
    def test_schema_constraint_nullability_check_and_order_drift_rejected(self):
        p=fixture_plan();self.assertTrue(fixture_valid(p))
        for bad in (replace(p,expected_columns=p.expected_columns[::-1]),replace(p,expected_constraints=p.expected_constraints[:-1]),replace(p,isolation_level="SERIALIZABLE")):
            with self.assertRaisesRegex(GovernanceRejected,"exact source-bound"):planned().plan_fixture(bad)
    def test_live_introspection_wrong_target_order_missing_nullable_and_relaxed_check_rejected(self):
        rows=live_constraints();self.assertEqual(normalize_live_constraints(rows),fixture_plan().expected_constraints)
        attacks=[]
        wrong=list(rows);wrong[1]=(wrong[1][0],wrong[1][1],["payload_digest"],False,False,None);attacks.append(wrong)
        reversed_order=list(rows);reversed_order[4]=(reversed_order[4][0],reversed_order[4][1],list(reversed(reversed_order[4][2])),False,False,None);attacks.append(reversed_order)
        attacks.append(rows[:-2]+rows[-1:])
        relaxed=list(rows);relaxed[-1]=(relaxed[-1][0],"c",["state"],False,False,"state IN ('PERSISTENCE_PLAN_ONLY_NOT_WRITTEN','WRITTEN')");attacks.append(relaxed)
        for bad in attacks:
            with self.assertRaises(GovernanceRejected):normalize_live_constraints(bad)
        columns=[(n,t,"YES" if nullable else "NO") for n,t,nullable in fixture_plan().expected_columns];self.assertEqual(normalize_live_columns(columns),fixture_plan().expected_columns)
        columns[0]=(columns[0][0],columns[0][1],"YES")
        with self.assertRaisesRegex(GovernanceRejected,"exact ordered live columns"):normalize_live_columns(columns)
    def test_source_schema_and_ddl_drift_rejected(self):
        s=planned();s._source._ddl += " -- drift"
        with self.assertRaisesRegex(GovernanceRejected,"exact source-bound"):s.plan_fixture()
        s=complete();s._source._ddl += " -- post-finalize-drift";self.assertFalse(s.evidence()["complete_postgres_ephemeral_repository_proof_contract_evidence"])
    def test_snapshot_registry_manifest_and_sequence_rejected(self):
        prior=prior_completed()[0]
        for reg,man,seq in (("x",d("m"),17),(d("r"),"x",17),(d("r"),d("m"),False)):
            s=SyntheticPostgresEphemeralRepositoryProof()
            for cid in range(16301,16701):
                w,a=s._expected(cid);s.add_control(cid,w,a,f"synthetic:postgres-ephemeral-proof-requirement:{(cid-16301)//25:02}",d(str(cid)),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
            with self.assertRaises(GovernanceRejected):s.anchor(prior,mapping_digest(STAGE_MAPPING),reg,man,APPLIED_LESSONS,APPLIED_RULES,prior._snapshot.digest,seq,True)
    def test_unknown_or_failed_proof_cannot_be_claimed_pass(self):
        s=complete()
        with self.assertRaises(GovernanceRejected):s.evidence({"status":"PASS"})
        with self.assertRaises(GovernanceRejected):s.evidence({"status":"SKIP_NO_PRECONFIGURED_TEST_DATABASE"})
    def test_incomplete_or_mutated_pass_proof_fails_closed(self):
        s=complete();base=valid_proof()
        mutations=[]
        for key,value in (("cleanup_succeeded",False),("test_only_database_writes",3),("test_only_database_write_attempts",26),("production_database_writes",1),("concurrency_workers",19),("concurrent_row_count",2),("isolation_level","SERIALIZABLE"),("database_url_disclosed",True),("credential_disclosed",True),("live_constraint_parity",False)):
            mutations.append(dict(base,**{key:value}))
        missing=dict(base);missing.pop("cleanup_succeeded");mutations.append(missing)
        fewer=dict(base);fewer["conflict_classifications"]=fewer["conflict_classifications"][:-1];mutations.append(fewer)
        extra=dict(base);extra["conflict_classifications"]=extra["conflict_classifications"]+["EXTRA"];mutations.append(extra)
        for bad in mutations:
            with self.assertRaisesRegex(GovernanceRejected,"complete exact"):s.evidence(bad)

if __name__=="__main__":unittest.main()
