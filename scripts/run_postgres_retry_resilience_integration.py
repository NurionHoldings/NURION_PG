"""Actual disposable PostgreSQL 40001 retry proof; no production target or secrets."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json,os
from pathlib import Path
from threading import Barrier,Lock

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_postgres_ephemeral_repository_proof import validated_disposable_target,validated_pg_environment,migration_sql,insert_or_read,TABLE
from nurion_pg.synthetic_postgres_retry_resilience_proof import *
from scripts.run_postgres_ephemeral_repository_integration import connect,row

ROOT=Path(__file__).resolve().parents[1]
ENV="NURION_PG_EPHEMERAL_POSTGRES_DSN"
SCHEMA="nurion_pg_ci_retry_16701"

def main():
    dsn=os.environ.get(ENV);ci_test=os.environ.get("NURION_PG_EPHEMERAL_TEST")=="1"
    if not dsn and not ci_test:print("SKIP_NO_PRECONFIGURED_TEST_DATABASE");return 0
    if dsn:validated_disposable_target(dsn,SCHEMA,os.environ.get("CI")=="true")
    else:validated_pg_environment(os.environ,SCHEMA,os.environ.get("CI")=="true")
    try:import psycopg
    except ImportError as exc:raise RuntimeError("configured PostgreSQL proof requires psycopg") from exc
    up,down=migration_sql(SCHEMA);admin=connect(psycopg,dsn);cleanup=False
    try:
        with admin.cursor() as cur:
            for statement in up.split(";\n"):
                if statement.strip():cur.execute(statement)
            cur.execute(f'CREATE TABLE "{SCHEMA}"."retry_cycle" (slot text PRIMARY KEY, marker integer NOT NULL)')
            cur.execute(f'INSERT INTO "{SCHEMA}"."retry_cycle" VALUES (%s,0),(%s,0)',("a","b"))
        admin.commit()
        barrier=Barrier(2);guard=Lock();failures=[];connection_ids=[]
        def participant(own,other):
            def operation(attempt):
                c=connect(psycopg,dsn)
                try:
                    with c.cursor() as cur:
                        cur.execute("BEGIN ISOLATION LEVEL SERIALIZABLE")
                        cur.execute("SELECT marker FROM {}.{} WHERE slot=%s".format(f'"{SCHEMA}"','"retry_cycle"'),(other,));cur.fetchone()
                        if attempt==1:barrier.wait()
                        cur.execute(f'UPDATE "{SCHEMA}"."retry_cycle" SET marker=marker+1 WHERE slot=%s',(own,))
                    c.commit()
                    with guard:connection_ids.append((own,attempt,c.info.backend_pid))
                    return own
                except Exception as exc:
                    setattr(exc,"_proof_backend_pid",c.info.backend_pid);c.rollback();raise
                finally:c.close()
            def failed(exc,attempt):
                with guard:failures.append((getattr(exc,"sqlstate",None),own,attempt,getattr(exc,"_proof_backend_pid",None)))
            return bounded_retry(operation,on_failure=failed)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda pair:participant(*pair),(('a','b'),('b','a'))))
        serialization=[x for x in failures if x[0]=="40001"]
        if len(serialization)!=1 or sorted(x[0] for x in results)!=["a","b"]:raise RuntimeError("exact single 40001 and bounded recovery required")
        retried=serialization[0][1];failed_pid=serialization[0][3];successful_retry=[pid for owner,attempt,pid in connection_ids if owner==retried and attempt==2]
        if len(successful_retry)!=1 or failed_pid is None or successful_retry[0]==failed_pid:raise RuntimeError("fresh retry connection required")
        timeout=connect(psycopg,dsn)
        try:
            try:
                with timeout.cursor() as cur:cur.execute("SET LOCAL statement_timeout='20ms'");cur.execute("SELECT pg_sleep(0.10)")
                raise AssertionError("timeout not raised")
            except Exception as exc:
                if getattr(exc,"sqlstate",None)!="57014" or classify_sqlstate(exc.sqlstate)!="NON_RETRYABLE_FAIL_CLOSED":raise
                timeout.rollback()
        finally:timeout.close()
        committed=row("retry-response-loss",kind="case-retry-response-loss")
        writer=connect(psycopg,dsn)
        try:
            insert_or_read(writer,SCHEMA,committed)
            try:raise CommitOutcomeUnknown("HARNESS_INJECTED_POST_COMMIT_RESPONSE_LOSS")
            except CommitOutcomeUnknown:pass
        finally:writer.close()
        def readback(expected=committed["payload_digest"]):
            c=connect(psycopg,dsn)
            try:
                with c.cursor() as cur:cur.execute(f'SELECT payload_digest FROM "{SCHEMA}"."{TABLE}" WHERE idempotency_key_id=%s',(committed["idempotency_key_id"],));found=cur.fetchone()
                c.commit();return ("EXISTING_SAME_PAYLOAD",found[0]) if found else None
            finally:c.close()
        resolve_commit_unknown(readback,committed["payload_digest"])
        try:resolve_commit_unknown(readback,sha256(b"wrong").hexdigest());raise AssertionError("payload mismatch accepted")
        except GovernanceRejected:pass
        proof={"status":"PASS_POSTGRES_RETRY_RESILIENCE","serialization_sqlstate":"40001","serialization_failures":1,"serialization_success_attempt":2,"bounded_retry_max_attempts":3,"retry_exhaustion_mode":"UNIT_INJECTED_SQLSTATE_SEQUENCE","retry_exhaustion_fail_closed":True,"actual_retry_exhaustion_claimed":False,"timeout_sqlstate":"57014","timeout_attempts":1,"non_retryable_timeout_fail_closed":True,"fresh_connection_per_retry":True,"commit_unknown_mode":"HARNESS_INJECTED_POST_COMMIT_RESPONSE_LOSS","commit_unknown_readback_confirmed":True,"payload_mismatch_fail_closed":True,"production_database_writes":0,"cleanup_succeeded":True,"credential_disclosed":False,"password_credential_configured":False,"actual_network_partition_claimed":False,"actual_deadlock_claimed":False}
    finally:
        try:
            admin.rollback()
            with admin.cursor() as cur:cur.execute(down)
            admin.commit();cleanup=True
        finally:admin.close()
    if not cleanup:raise RuntimeError("ephemeral retry schema cleanup failed")
    proof["cleanup_succeeded"]=True
    if not integration_proof_valid(proof):raise RuntimeError("PostgreSQL retry proof semantic validation failed")
    out=ROOT/"build/postgres-retry-resilience-integration-evidence.json";out.parent.mkdir(exist_ok=True);payload=json.dumps(proof,sort_keys=True,separators=(",",":")).encode();out.write_bytes(payload);out.with_suffix(out.suffix+".sha256").write_text(sha256(payload).hexdigest()+"\n",encoding="utf-8");print("PASS_POSTGRES_RETRY_RESILIENCE",sha256(payload).hexdigest());return 0
if __name__=="__main__":raise SystemExit(main())
