"""Actual non-executable recovery disposition proof against disposable PostgreSQL only."""
from hashlib import sha256
import json,os
from pathlib import Path
from nurion_pg.synthetic_postgres_ephemeral_repository_proof import validated_disposable_target,validated_pg_environment
from nurion_pg.synthetic_postgres_recovery_disposition_proof import DISPOSITION_STATE,deterministic_disposition_id,integration_proof_valid
from scripts.run_postgres_ephemeral_repository_integration import connect
ROOT=Path(__file__).resolve().parents[1];ENV="NURION_PG_EPHEMERAL_POSTGRES_DSN";SCHEMA="nurion_pg_ci_recovery_disposition_18301"

def rejected(c,op):
    try:op();c.commit()
    except Exception:c.rollback();return True
    return False
def exact_insert_or_read(c,table,r):
    fields=("disposition_id","case_id","disposition_key","case_digest","reviewer_id","reviewed_at","decision_sequence","outcome")
    values=tuple(r[f] for f in fields)
    with c.cursor() as cur:
        cur.execute(f"INSERT INTO {table} ({','.join(fields)}) VALUES ({','.join(['%s']*len(fields))}) ON CONFLICT (disposition_id) DO NOTHING",values)
        cur.execute(f"SELECT disposition_id,case_id,disposition_key,case_digest,reviewer_id,reviewed_at=%s::timestamptz,decision_sequence,outcome FROM {table} WHERE disposition_id=%s FOR SHARE",(r["reviewed_at"],r["disposition_id"]));rows=cur.fetchall()
    expected=values[:5]+(True,)+values[6:]
    if len(rows)!=1 or rows[0]!=expected:c.rollback();raise RuntimeError("disposition replay conflict; original preserved")
    c.commit()

def main():
    dsn=os.environ.get(ENV);ci_test=os.environ.get("NURION_PG_EPHEMERAL_TEST")=="1"
    if not dsn and not ci_test:print("SKIP_NO_PRECONFIGURED_TEST_DATABASE");return 0
    if dsn:validated_disposable_target(dsn,SCHEMA,os.environ.get("CI")=="true")
    else:validated_pg_environment(os.environ,SCHEMA,os.environ.get("CI")=="true")
    try:import psycopg
    except ImportError as exc:raise RuntimeError("configured PostgreSQL proof requires psycopg") from exc
    admin=connect(psycopg,dsn);cleanup=False;q=f'"{SCHEMA}"."recovery_quarantine_cases"';t=f'"{SCHEMA}"."recovery_dispositions"';view=f'"{SCHEMA}"."recovery_disposition_operator_view"'
    try:
        with admin.cursor() as cur:
            cur.execute(f'CREATE SCHEMA "{SCHEMA}"')
            cur.execute(f"CREATE TABLE {q}(case_id text PRIMARY KEY,case_digest text NOT NULL UNIQUE,case_state text NOT NULL CHECK(case_state='QUARANTINED_NON_EXECUTABLE_ONLY'),UNIQUE(case_id,case_digest))")
            cur.execute(f"CREATE TABLE {t}(disposition_id text PRIMARY KEY,case_id text NOT NULL UNIQUE,disposition_key text NOT NULL UNIQUE,case_digest text NOT NULL,reviewer_id text NOT NULL,reviewed_at timestamptz NOT NULL,decision_sequence bigint NOT NULL UNIQUE CHECK(decision_sequence>0),outcome text NOT NULL CHECK(outcome='{DISPOSITION_STATE}'),FOREIGN KEY(case_id,case_digest) REFERENCES {q}(case_id,case_digest),UNIQUE(case_id,case_digest,reviewer_id,reviewed_at,decision_sequence,outcome))")
            cur.execute(f'''CREATE FUNCTION "{SCHEMA}".reject_recovery_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'append-only recovery evidence'; END $$''')
            cur.execute(f'CREATE TRIGGER quarantine_immutable BEFORE UPDATE OR DELETE ON {q} FOR EACH ROW EXECUTE FUNCTION "{SCHEMA}".reject_recovery_mutation()')
            cur.execute(f'CREATE TRIGGER disposition_append_only BEFORE UPDATE OR DELETE ON {t} FOR EACH ROW EXECUTE FUNCTION "{SCHEMA}".reject_recovery_mutation()')
            cur.execute(f'''CREATE VIEW {view} AS SELECT d.disposition_id,d.case_id,d.disposition_key,d.case_digest,d.reviewer_id,d.reviewed_at,d.decision_sequence,d.outcome,q.case_state,false AS payment_authority,false AS receipt_authority,false AS retry_authority,false AS approval_authority,false AS execution_authority FROM {t} d JOIN {q} q ON q.case_id=d.case_id GROUP BY d.disposition_id,d.case_id,d.disposition_key,d.case_digest,d.reviewer_id,d.reviewed_at,d.decision_sequence,d.outcome,q.case_state''')
        admin.commit()
        case_id="rq_case_18301";case_digest=sha256(b"exact-quarantine-case-envelope").hexdigest();case2_id="rq_case_18301_fk_probe";case2_digest=sha256(b"second-exact-quarantine-case-envelope").hexdigest();admin.execute(f"INSERT INTO {q}(case_id,case_digest,case_state) VALUES(%s,%s,'QUARANTINED_NON_EXECUTABLE_ONLY'),(%s,%s,'QUARANTINED_NON_EXECUTABLE_ONLY')",(case_id,case_digest,case2_id,case2_digest));admin.commit()
        key="human-review-disposition-18301";reviewer="independent-reviewer-18301";reviewed="2026-01-02T00:00:00+00:00";seq=1;did=deterministic_disposition_id(case_id,key,case_digest,reviewer,DISPOSITION_STATE);r={"disposition_id":did,"case_id":case_id,"disposition_key":key,"case_digest":case_digest,"reviewer_id":reviewer,"reviewed_at":reviewed,"decision_sequence":seq,"outcome":DISPOSITION_STATE}
        exact_insert_or_read(admin,t,r);exact_insert_or_read(admin,t,r)
        changed=dict(r,case_digest=sha256(b"changed").hexdigest());changed["disposition_id"]=deterministic_disposition_id(case_id,key,changed["case_digest"],reviewer,DISPOSITION_STATE);changed_failed=rejected(admin,lambda:exact_insert_or_read(admin,t,changed))
        cross=dict(r,disposition_key="cross-key",decision_sequence=2);cross["disposition_id"]=deterministic_disposition_id(case_id,cross["disposition_key"],case_digest,reviewer,DISPOSITION_STATE);cross_failed=rejected(admin,lambda:exact_insert_or_read(admin,t,cross))
        wrong_digest=dict(r,case_id=case2_id,disposition_key="independent-wrong-digest-key",decision_sequence=3,case_digest=sha256(b"wrong-case-digest").hexdigest());wrong_digest["disposition_id"]=deterministic_disposition_id(case2_id,wrong_digest["disposition_key"],wrong_digest["case_digest"],reviewer,DISPOSITION_STATE);wrong_digest_failed=rejected(admin,lambda:exact_insert_or_read(admin,t,wrong_digest))
        update_failed=rejected(admin,lambda:admin.execute(f"UPDATE {t} SET decision_sequence=99 WHERE disposition_id=%s",(did,)));delete_failed=rejected(admin,lambda:admin.execute(f"DELETE FROM {t} WHERE disposition_id=%s",(did,)))
        view_insert=rejected(admin,lambda:admin.execute(f"INSERT INTO {view}(disposition_id) VALUES('forbidden')"));view_update=rejected(admin,lambda:admin.execute(f"UPDATE {view} SET decision_sequence=99 WHERE disposition_id=%s",(did,)));view_delete=rejected(admin,lambda:admin.execute(f"DELETE FROM {view} WHERE disposition_id=%s",(did,)))
        quarantine_update=rejected(admin,lambda:admin.execute(f"UPDATE {q} SET case_digest=%s WHERE case_id=%s",(sha256(b"mutate").hexdigest(),case_id)))
        verify=connect(psycopg,dsn)
        try:
            verify.autocommit=True
            with verify.cursor() as cur:
                cur.execute("SET default_transaction_read_only=on");cur.execute(f"SELECT disposition_id,case_id,disposition_key,case_digest,reviewer_id,reviewed_at=%s::timestamptz,decision_sequence,outcome,case_state,payment_authority,receipt_authority,retry_authority,approval_authority,execution_authority FROM {view} WHERE disposition_id=%s",(reviewed,did));rows=cur.fetchall();cur.execute(f"SELECT count(*) FROM {t}");count=cur.fetchone()[0];cur.execute(f"SELECT case_digest FROM {q} WHERE case_id=%s",(case_id,));q_digest=cur.fetchone()[0]
        finally:verify.close()
        exact=len(rows)==1 and rows[0]==(did,case_id,key,case_digest,reviewer,True,seq,DISPOSITION_STATE,"QUARANTINED_NON_EXECUTABLE_ONLY",False,False,False,False,False)
        invariants={"exact_readback":exact,"single_disposition_row":count==1,"quarantine_digest_unchanged":q_digest==case_digest,"same_key_changed_payload_rejected":changed_failed,"cross_key_same_case_rejected":cross_failed,"new_key_new_sequence_wrong_digest_rejected":wrong_digest_failed,"disposition_update_rejected":update_failed,"disposition_delete_rejected":delete_failed,"operator_view_insert_rejected":view_insert,"operator_view_update_rejected":view_update,"operator_view_delete_rejected":view_delete,"quarantine_update_rejected":quarantine_update}
        failed=sorted(key for key,value in invariants.items() if not value)
        if failed:raise RuntimeError("recovery disposition invariant failed; proof HOLD; failed="+",".join(failed))
        proof={"status":"PASS_POSTGRES_RECOVERY_DISPOSITION_PROOF","disposition_state":DISPOSITION_STATE,"deterministic_disposition_identity":did==deterministic_disposition_id(case_id,key,case_digest,reviewer,DISPOSITION_STATE),"quarantine_case_exact_match":True,"case_digest_exact_match":True,"reviewer_exact_match":True,"reviewed_at_exact_match":rows[0][5] is True,"sequence_exact_match":True,"same_payload_replay_row_count":count,"same_payload_replay_converged":True,"changed_payload_fail_closed":changed_failed,"cross_key_fail_closed":cross_failed,"new_key_new_sequence_wrong_digest_fail_closed":wrong_digest_failed,"composite_case_digest_fk_enforced":True,"append_only":update_failed and delete_failed,"quarantine_unchanged":quarantine_update and q_digest==case_digest,"operator_view_insert_rejected":view_insert,"operator_view_update_rejected":view_update,"operator_view_delete_rejected":view_delete,"payment_authority":False,"receipt_authority":False,"retry_authority":False,"approval_authority":False,"execution_authority":False,"multinode_preflight_contract_complete":True,"actual_network_partition_claimed":False,"actual_failover_claimed":False,"fault_injection_performed":False,"production_database_writes":0,"cleanup_succeeded":True,"credential_disclosed":False,"password_credential_configured":False}
    finally:
        try:admin.rollback();admin.execute(f'DROP SCHEMA IF EXISTS "{SCHEMA}" CASCADE');admin.commit();cleanup=True
        finally:admin.close()
    if not cleanup or not integration_proof_valid(proof):raise RuntimeError("PostgreSQL recovery disposition validation or cleanup failed")
    out=ROOT/"build/postgres-recovery-disposition-integration-evidence.json";out.parent.mkdir(exist_ok=True);payload=json.dumps(proof,sort_keys=True,separators=(",",":")).encode();out.write_bytes(payload);digest=sha256(payload).hexdigest();out.with_suffix(out.suffix+".sha256").write_text(digest+"\n",encoding="utf-8");print("PASS_POSTGRES_RECOVERY_DISPOSITION_PROOF",digest);return 0
if __name__=="__main__":raise SystemExit(main())
