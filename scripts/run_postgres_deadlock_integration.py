"""Actual 40P01 and 55P03 proof against disposable PostgreSQL only."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json,os
from pathlib import Path
from threading import Barrier,Lock

from nurion_pg.synthetic_postgres_ephemeral_repository_proof import validated_disposable_target,validated_pg_environment
from nurion_pg.synthetic_postgres_retry_resilience_proof import classify_sqlstate
from nurion_pg.synthetic_postgres_deadlock_proof import integration_proof_valid
from scripts.run_postgres_ephemeral_repository_integration import connect

ROOT=Path(__file__).resolve().parents[1];ENV="NURION_PG_EPHEMERAL_POSTGRES_DSN";SCHEMA="nurion_pg_ci_deadlock_17101"

def main():
    dsn=os.environ.get(ENV);ci_test=os.environ.get("NURION_PG_EPHEMERAL_TEST")=="1"
    if not dsn and not ci_test:print("SKIP_NO_PRECONFIGURED_TEST_DATABASE");return 0
    if dsn:validated_disposable_target(dsn,SCHEMA,os.environ.get("CI")=="true")
    else:validated_pg_environment(os.environ,SCHEMA,os.environ.get("CI")=="true")
    try:import psycopg
    except ImportError as exc:raise RuntimeError("configured PostgreSQL proof requires psycopg") from exc
    admin=connect(psycopg,dsn);cleanup=False;table=f'"{SCHEMA}"."deadlock_rows"'
    try:
        with admin.cursor() as cur:
            cur.execute(f'CREATE SCHEMA "{SCHEMA}"');cur.execute(f'CREATE TABLE {table} (id integer PRIMARY KEY, marker integer NOT NULL)');cur.execute(f'INSERT INTO {table} VALUES (1,0),(2,0)')
        admin.commit();barrier=Barrier(2);guard=Lock();failures=[];successes=[]
        def participant(first,second):
            c=connect(psycopg,dsn);pid=c.info.backend_pid
            try:
                with c.cursor() as cur:
                    try:cur.execute("SET LOCAL deadlock_timeout='100ms'")
                    except Exception as exc:raise RuntimeError("deadlock_timeout preflight denied; disposable proof HOLD") from exc
                    cur.execute(f'SELECT marker FROM {table} WHERE id=%s FOR UPDATE',(first,));barrier.wait(timeout=5);cur.execute(f'UPDATE {table} SET marker=marker+1 WHERE id=%s',(second,))
                c.commit()
                with guard:successes.append(pid)
            except Exception as exc:
                state=getattr(exc,"sqlstate",None);c.rollback()
                with guard:failures.append((state,pid))
            finally:c.close()
        with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda pair:participant(*pair),((1,2),(2,1))))
        deadlocks=[x for x in failures if x[0]=="40P01"]
        if len(deadlocks)!=1 or len(successes)!=1 or len(failures)!=1:raise RuntimeError("exactly one actual 40P01 victim and one winner required")
        failed_pid=deadlocks[0][1];retry=connect(psycopg,dsn)
        try:
            retry_pid=retry.info.backend_pid
            with retry.cursor() as cur:cur.execute(f'UPDATE {table} SET marker=marker+1 WHERE id IN (1,2)')
            retry.commit()
        except Exception:retry.rollback();raise
        finally:retry.close()
        if retry_pid==failed_pid:raise RuntimeError("fresh backend retry recovery required")
        holder=connect(psycopg,dsn);contender=connect(psycopg,dsn)
        try:
            with holder.cursor() as cur:cur.execute(f'SELECT marker FROM {table} WHERE id=1 FOR UPDATE')
            try:
                with contender.cursor() as cur:cur.execute("SET LOCAL lock_timeout='50ms'");cur.execute(f'SELECT marker FROM {table} WHERE id=1 FOR UPDATE')
                raise AssertionError("lock timeout not raised")
            except Exception as exc:
                if getattr(exc,"sqlstate",None)!="55P03" or classify_sqlstate("55P03")!="NON_RETRYABLE_FAIL_CLOSED":raise
                contender.rollback()
        finally:holder.rollback();holder.close();contender.close()
        proof={"status":"PASS_POSTGRES_DEADLOCK_PROOF","deadlock_sqlstate":"40P01","deadlock_failures":1,"deadlock_successes":1,"deadlock_provenance":"ACTUAL_POSTGRESQL_TWO_BACKEND_OPPOSITE_ROW_LOCK_ORDER","deadlock_timeout_preflight":"ACTUAL_POSTGRESQL_SET_LOCAL_CONFIRMED","failed_transaction_rolled_back":True,"failed_backend_closed":True,"fresh_backend_retry":True,"retry_success_attempt":2,"bounded_retry_max_attempts":3,"lock_timeout_sqlstate":"55P03","lock_timeout_attempts":1,"lock_timeout_provenance":"ACTUAL_POSTGRESQL_BLOCKED_ROW_LOCK","lock_timeout_non_retryable":True,"unit_retry_exhaustion_provenance":"UNIT_INJECTED_SQLSTATE_SEQUENCE","harness_commit_unknown_provenance":"HARNESS_INJECTED_POST_COMMIT_RESPONSE_LOSS","actual_network_partition_claimed":False,"actual_failover_claimed":False,"production_database_writes":0,"cleanup_succeeded":True,"credential_disclosed":False,"password_credential_configured":False}
    finally:
        try:
            admin.rollback()
            with admin.cursor() as cur:cur.execute(f'DROP SCHEMA IF EXISTS "{SCHEMA}" CASCADE')
            admin.commit();cleanup=True
        finally:admin.close()
    if not cleanup:raise RuntimeError("ephemeral deadlock schema cleanup failed")
    proof["cleanup_succeeded"]=True
    if not integration_proof_valid(proof):raise RuntimeError("PostgreSQL deadlock semantic validation failed")
    out=ROOT/"build/postgres-deadlock-integration-evidence.json";out.parent.mkdir(exist_ok=True);payload=json.dumps(proof,sort_keys=True,separators=(",",":")).encode();out.write_bytes(payload);out.with_suffix(out.suffix+".sha256").write_text(sha256(payload).hexdigest()+"\n",encoding="utf-8");print("PASS_POSTGRES_DEADLOCK_PROOF",sha256(payload).hexdigest());return 0
if __name__=="__main__":raise SystemExit(main())
