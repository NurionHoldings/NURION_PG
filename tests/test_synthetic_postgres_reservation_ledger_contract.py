from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from hashlib import sha256
import unittest

from nurion_pg.arkaon.governance import GovernanceRejected,canonical_digest
from nurion_pg.synthetic_postgres_reservation_ledger_contract import *
from tests.test_synthetic_nonissuance_result_seal_reservation import completed as prior_completed

def d(v):return sha256(v.encode()).hexdigest()
def populated():
    s=SyntheticPostgresReservationLedgerContract()
    for cid in range(15901,16301):
        w,a=s._expected(cid);s.add_control(cid,w,a,f"synthetic:postgres-ledger-requirement:{(cid-15901)//25:02}",d(str(cid)),"EXPECTED_REJECTION" if a in NEGATIVE else "PASS")
    return s
def anchored():
    p=prior_completed()[0];s=populated();s.anchor(p,mapping_digest(STAGE_MAPPING),d("registry"),d("manifest"),APPLIED_LESSONS,APPLIED_RULES,p._snapshot.digest,36,True);s.define_schema();return s,p
def planned():
    s,p=anchored()
    for f,k,t in p._reservations:s.plan_row(f"synthetic:postgres-ledger-row-plan:{f}:{k}:{t.lower()}",f,k,t)
    s.define_transaction();return s,p
def completed():
    s,p=planned();s.finalize("synthetic:postgres-ledger-plan-docket:final","synthetic:ledger-plan-compiler:final-c","synthetic:ledger-plan-validator:final-v");return s,p
def rehash_tx_and_docket(s,**changes):
    p={**s._tx.__dict__,**changes};p.pop("digest",None);s._tx=TransactionPlan(**p,digest=canonical_digest(p));dp={**s._docket.__dict__,"transaction_digest":s._tx.digest};dp.pop("digest",None);s._docket=replace(s._docket,transaction_digest=s._tx.digest,digest=canonical_digest(dp))
def rehash_docket(s,**changes):
    p={**s._docket.__dict__,**changes};p.pop("digest",None);s._docket=replace(s._docket,**changes,digest=canonical_digest(p))

class Tests(unittest.TestCase):
    def test_matrix_exactly_400(self):self.assertEqual((len(WORKSTREAMS),len(populated()._controls),WORKSTREAMS[0][0],WORKSTREAMS[-1][1]),(16,400,15901,16300))
    def test_schema_ast_and_deterministic_quoted_ddl(self):
        s,_=anchored();self.assertTrue(schema_valid(s._schema));self.assertEqual(render_ddl(s._schema),s._ddl);self.assertIn('CONSTRAINT "uq_logical_intent" UNIQUE ("flow", "kind", "intent_kind")',s._ddl);self.assertNotIn("DROP ",s._ddl);self.assertNotIn("UPDATE ",s._ddl)
    def test_schema_drift_constraint_delete_nullable_and_wrong_order_rejected(self):
        base=schema_spec()
        for bad in (replace(base,constraints=base.constraints[:-1]),replace(base,columns=tuple(replace(x,nullable=True) if x.name=="payload_digest" else x for x in base.columns)),replace(base,constraints=tuple(replace(x,columns=("kind","flow","intent_kind")) if x.name=="uq_logical_intent" else x for x in base.constraints))):
            bad=replace(bad,digest=schema_digest(bad));self.assertFalse(schema_valid(bad))
    def test_identifier_quoting_fail_closed(self):
        for x in ("Bad","a-b","1table",'x";drop table y'):
            with self.assertRaises(GovernanceRejected):quote_ident(x)
    def test_same_key_same_payload_serial_parallel_converges(self):
        s,p=anchored();key=next(iter(p._reservations));a=(f"synthetic:postgres-ledger-row-plan:{':'.join(key)}",*key);self.assertIs(s.plan_row(*a),s.plan_row(*a))
        s,p=anchored();key=next(iter(p._reservations));a=(f"synthetic:postgres-ledger-row-plan:{':'.join(key)}",*key)
        with ThreadPoolExecutor(max_workers=8) as pool:rows=list(pool.map(lambda _:s.plan_row(*a),range(20)))
        self.assertEqual((len(s._rows),len({id(x) for x in rows})),(1,1))
    def test_routed_materialization_20_way_in_memory_contract(self):
        s,p=anchored();keys=list(p._reservations)
        for key in keys[:2]:s.plan_row(f"synthetic:postgres-ledger-row-plan:{':'.join(key)}",*key)
        key=keys[2];a=(f"synthetic:postgres-ledger-row-plan:{':'.join(key)}",*key)
        with ThreadPoolExecutor(max_workers=8) as pool:rows=list(pool.map(lambda _:s.plan_row(*a),range(20)))
        self.assertEqual((len(s._rows),len({id(x) for x in rows})),(3,1))
    def test_routed_execution_20_way_in_memory_contract(self):
        s,p=anchored();keys=list(p._reservations)
        for key in keys[:3]:s.plan_row(f"synthetic:postgres-ledger-row-plan:{':'.join(key)}",*key)
        key=keys[3];a=(f"synthetic:postgres-ledger-row-plan:{':'.join(key)}",*key)
        with ThreadPoolExecutor(max_workers=8) as pool:rows=list(pool.map(lambda _:s.plan_row(*a),range(20)))
        self.assertEqual((len(s._rows),len({id(x) for x in rows})),(4,1))
    def test_changed_payload_and_cross_key_unique_reuse_rejected(self):
        s,p=anchored();keys=list(p._reservations);key=keys[0];rid=f"synthetic:postgres-ledger-row-plan:{':'.join(key)}";s.plan_row(rid,*key)
        with self.assertRaisesRegex(GovernanceRejected,"logical row payload conflict"):s.plan_row(rid+":changed",*key)
        src=p._reservations[keys[1]];p._reservations[keys[1]]=replace(src,idempotency_key_id=p._reservations[key].idempotency_key_id)
        with self.assertRaises(GovernanceRejected):s.plan_row(f"synthetic:postgres-ledger-row-plan:{':'.join(keys[1])}",*keys[1])
    def test_policy_window_source_result_seal_and_actor_binding_rehash_rejected(self):
        mutations=(("policy_version","synthetic:signature-policy-version:v0"),("observed_epoch",10**20),("source_packet_digest",d("swap")),("result_candidate_digest",d("swap")),("seal_input_digest",d("swap")),("owner_actor","synthetic:reservation-owner:SHARED"),("validator_actor","synthetic:reservation-validator:SHARED"))
        for field,value in mutations:
            s,p=completed();key=list(p._reservations)[2];p._reservations[key]=replace(p._reservations[key],**{field:value});self.assertFalse(s.evidence()["integrity_valid"],field)
    def test_sequence_predecessor_scope_nonce_full_rehash_attacks_rejected(self):
        for field,value in (("sequence",0),("predecessor_row_digest",None),("reservation_scope_digest",d("scope")),("nonce_scope_digest",d("nonce"))):
            s,_=completed();key=list(s._rows)[2];r=s._rows[key];s._rows[key]=replace(r,**{field:value});self.assertFalse(s.evidence()["integrity_valid"],field)
    def test_transaction_semantics_and_crash_recovery_are_explicit(self):
        s,_=completed();t=s._tx;self.assertIn("BEGIN",t.steps);self.assertIn("COMMIT",t.steps);self.assertIn("UNIQUE",t.unique_violation_action);self.assertIn("ROLLBACK",t.crash_before_commit);self.assertIn("READ_BACK",t.crash_after_commit_response_loss);self.assertEqual(t.changed_payload_action,"FAIL_CLOSED_CONFLICT")
    def test_transaction_exact_semantics_full_rehash_attacks_rejected(self):
        changes=(
            {"unique_violation_action":"ON_UNIQUE_VIOLATION_REUSE_SAME_ABORTED_TRANSACTION"},
            {"steps":tuple(x for x in expected_transaction_payload()["steps"] if x!="LOCK_WINNER_FOR_SHARE")},
            {"steps":tuple(x for x in expected_transaction_payload()["steps"] if x!="COMPARE_CANONICAL_PAYLOAD_DIGEST")},
            {"conflict_targets":expected_transaction_payload()["conflict_targets"][:-1]},
            {"conflict_targets":tuple(reversed(expected_transaction_payload()["conflict_targets"]))},
            {"crash_before_commit":expected_transaction_payload()["crash_after_commit_response_loss"],"crash_after_commit_response_loss":expected_transaction_payload()["crash_before_commit"]},
        )
        for change in changes:
            s,_=completed();rehash_tx_and_docket(s,**change);self.assertFalse(s.evidence()["integrity_valid"],change)
    def test_premature_written_committed_receipt_and_authority_rejected(self):
        for field in ("written","committed","receipt_issued"):
            s,_=completed();key=list(s._rows)[2];s._rows[key]=replace(s._rows[key],**{field:True});self.assertFalse(s.evidence()["integrity_valid"])
        s,_=completed();s._docket=replace(s._docket,approved=True,status="APPROVED");self.assertFalse(s.evidence()["integrity_valid"])
    def test_partial_batch_order_and_role_alias_rejected(self):
        s,p=anchored();keys=list(p._reservations)
        with self.assertRaisesRegex(GovernanceRejected,"ordered ledger predecessor"):s.plan_row(f"synthetic:postgres-ledger-row-plan:{':'.join(keys[1])}",*keys[1])
        s,p=planned();actor=next(iter(s._rows.values())).owner_actor_normalized
        with self.assertRaisesRegex(GovernanceRejected,"independent ledger plan roles"):s.finalize("synthetic:postgres-ledger-plan-docket:x",f"synthetic:ledger-plan-compiler:{actor}","synthetic:ledger-plan-validator:v")
    def test_docket_namespace_and_role_alias_full_rehash_rejected(self):
        variants=(
            {"docket_id":"attacker:docket"},
            {"compiler":"attacker:compiler"},
            {"final_validator":"attacker:validator"},
            {"compiler":"synthetic:ledger-plan-compiler:owner-0"},
            {"final_validator":"synthetic:ledger-plan-validator:validator-0"},
            {"compiler":"synthetic:ledger-plan-compiler:shared","final_validator":"synthetic:ledger-plan-validator:shared"},
        )
        for change in variants:
            s,_=completed();rehash_docket(s,**change);self.assertFalse(s.evidence()["integrity_valid"],change)
    def test_snapshot_registry_manifest_full_rehash_rejected(self):
        for field in ("registry_digest","manifest_digest"):
            s,_=completed();sp={**s._snapshot.__dict__,field:"not-a-sha256"};sp.pop("digest");s._snapshot=replace(s._snapshot,**{field:"not-a-sha256"},digest=canonical_digest(sp));rehash_docket(s,snapshot_digest=s._snapshot.digest);self.assertFalse(s.evidence()["integrity_valid"])
    def test_guidance_content_addressed_and_zero_side_effects(self):
        s,_=completed();e=s.evidence();r=next(x for x in s._rows.values() if x.recovery_paths);flat=dict(r.recovery_paths[0][:-2]);self.assertTrue(flat["recommended"]);self.assertIn("rollback",flat);self.assertEqual((e["row_plan_count"],e["recovery_path_count"],e["human_judgment_hold_count"]),(40,64,32));self.assertTrue(e["complete_postgres_reservation_ledger_contract_evidence"]);self.assertEqual(tuple(e[k] for k in ("database_connections","database_url_reads","credential_reads","database_writes","ledger_writes","reservation_commits","approval_receipts_issued","external_pg_calls","deployments")),(0,)*9)
    def test_postgresql_proof_honest_skip_not_sqlite_substitute(self):
        e=completed()[0].evidence();self.assertEqual(e["postgresql_proof_status"],"SKIP_NO_PRECONFIGURED_TEST_DATABASE");self.assertFalse(e["postgresql_proof_claimed"]);self.assertFalse(e["sqlite_used_as_postgresql_proof"])

if __name__=="__main__":unittest.main()
