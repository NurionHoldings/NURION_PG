"""Actual pg_terminate_backend boundary proof against disposable PostgreSQL only."""
from hashlib import sha256
import json,os
from pathlib import Path

from nurion_pg.synthetic_postgres_ephemeral_repository_proof import validated_disposable_target,validated_pg_environment
from nurion_pg.synthetic_postgres_connection_loss_proof import classify_termination_sqlstate,integration_proof_valid
from scripts.run_postgres_ephemeral_repository_integration import connect

ROOT=Path(__file__).resolve().parents[1];ENV="NURION_PG_EPHEMERAL_POSTGRES_DSN";SCHEMA="nurion_pg_ci_connection_loss_17501"

def observed_state(exc):
    state=getattr(exc,"sqlstate",None)
    classify_termination_sqlstate(state)
    return state

def terminate(admin,pid):
    with admin.cursor() as cur:
        cur.execute("SELECT pg_terminate_backend(%s)",(pid,));result=cur.fetchone()[0]
    admin.commit()
    if result is not True:raise RuntimeError("pg_terminate_backend privilege/result preflight failed; proof HOLD")

def main():
    dsn=os.environ.get(ENV);ci_test=os.environ.get("NURION_PG_EPHEMERAL_TEST")=="1"
    if not dsn and not ci_test:print("SKIP_NO_PRECONFIGURED_TEST_DATABASE");return 0
    if dsn:validated_disposable_target(dsn,SCHEMA,os.environ.get("CI")=="true")
    else:validated_pg_environment(os.environ,SCHEMA,os.environ.get("CI")=="true")
    try:import psycopg
    except ImportError as exc:raise RuntimeError("configured PostgreSQL proof requires psycopg") from exc
    admin=connect(psycopg,dsn);cleanup=False;table=f'"{SCHEMA}"."connection_loss_rows"'
    try:
        with admin.cursor() as cur:
            cur.execute(f'CREATE SCHEMA "{SCHEMA}"')
            cur.execute(f'CREATE TABLE {table} (idempotency_key text PRIMARY KEY, payload_digest text NOT NULL)')
        admin.commit()

        pre=connect(psycopg,dsn);pre_state=None
        try:
            with pre.cursor() as cur:cur.execute(f'INSERT INTO {table} VALUES (%s,%s)',("precommit-key","precommit-digest"))
            terminate(admin,pre.info.backend_pid)
            try:
                pre.commit();raise AssertionError("terminated pre-commit backend unexpectedly committed")
            except Exception as exc:pre_state=observed_state(exc)
        finally:pre.close()
        fresh=connect(psycopg,dsn)
        try:
            fresh.autocommit=True
            with fresh.cursor() as cur:
                cur.execute("SET default_transaction_read_only=on")
                cur.execute(f'SELECT count(*) FROM {table} WHERE idempotency_key=%s',("precommit-key",));pre_absent=cur.fetchone()[0]==0
        finally:fresh.close()
        if not pre_absent:raise RuntimeError("pre-commit termination outcome ambiguous; exact absence required")

        post=connect(psycopg,dsn);key="committed-key";payload=sha256(b"committed-payload").hexdigest()
        try:
            with post.cursor() as cur:cur.execute(f'INSERT INTO {table} VALUES (%s,%s)',(key,payload))
            post.commit()  # acknowledged commit: this does not claim lost COMMIT response
            terminate(admin,post.info.backend_pid)
            try:
                with post.cursor() as cur:cur.execute("SELECT 1")
                raise AssertionError("terminated post-commit backend remained usable")
            except Exception as exc:post_state=observed_state(exc)
        finally:post.close()
        verify=connect(psycopg,dsn)
        try:
            verify.autocommit=True
            with verify.cursor() as cur:
                cur.execute("SET default_transaction_read_only=on")
                cur.execute(f'SELECT idempotency_key,payload_digest FROM {table} WHERE idempotency_key=%s',(key,));rows=cur.fetchall()
        finally:verify.close()
        exact=len(rows)==1 and rows[0]==(key,payload)
        if not exact:raise RuntimeError("post-commit exact reconciliation failed; proof HOLD")
        proof={"status":"PASS_POSTGRES_CONNECTION_LOSS_PROOF","termination_function":"ACTUAL_PG_TERMINATE_BACKEND","termination_privilege_preflight":"ACTUAL_DISPOSABLE_POSTGRESQL_GRANTED","precommit_sqlstate":pre_state,"precommit_classification":"CONNECTION_LOSS_FAIL_CLOSED","precommit_row_absent":True,"precommit_blind_retry_count":0,"precommit_outcome":"HOLD_NOT_COMMITTED","committed_before_termination":True,"postcommit_sqlstate":post_state,"postcommit_classification":"CONNECTION_LOSS_FAIL_CLOSED","fresh_read_only_connection":True,"idempotency_key_exact_match":True,"payload_digest_exact_match":True,"reconciled_outcome":"COMMITTED_CONFIRMED_BY_FRESH_EXACT_READ","postcommit_response_loss_provenance":"ACTUAL_BACKEND_TERMINATION_AFTER_ACKNOWLEDGED_COMMIT_NOT_COMMIT_RESPONSE_LOSS","actual_network_partition_claimed":False,"actual_failover_claimed":False,"production_database_writes":0,"cleanup_succeeded":True,"credential_disclosed":False,"password_credential_configured":False}
    finally:
        try:
            admin.rollback()
            with admin.cursor() as cur:cur.execute(f'DROP SCHEMA IF EXISTS "{SCHEMA}" CASCADE')
            admin.commit();cleanup=True
        finally:admin.close()
    if not cleanup:raise RuntimeError("ephemeral connection-loss schema cleanup failed")
    if not integration_proof_valid(proof):raise RuntimeError("PostgreSQL connection-loss semantic validation failed")
    out=ROOT/"build/postgres-connection-loss-integration-evidence.json";out.parent.mkdir(exist_ok=True);payload_bytes=json.dumps(proof,sort_keys=True,separators=(",",":")).encode();out.write_bytes(payload_bytes);digest=sha256(payload_bytes).hexdigest();out.with_suffix(out.suffix+".sha256").write_text(digest+"\n",encoding="utf-8");print("PASS_POSTGRES_CONNECTION_LOSS_PROOF",digest);return 0
if __name__=="__main__":raise SystemExit(main())
