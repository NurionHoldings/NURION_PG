"""Test-only PostgreSQL proof. DSN is consumed but never printed or persisted."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json,os
from pathlib import Path
from threading import Barrier

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_postgres_ephemeral_repository_proof import *

ROOT=Path(__file__).resolve().parents[1]
ENV="NURION_PG_EPHEMERAL_POSTGRES_DSN"
SCHEMA="nurion_pg_ci_proof_16301"

def value(seed):return sha256(seed.encode()).hexdigest()
def row(seed="winner",idempotency=None,token=None,scope=None,nonce=None,payload=None):
    r={c.name:value(f"{seed}:{c.name}") for c in schema_spec().columns if c.sql_type=="text"}
    r.update({"observed_epoch":100,"expires_at_epoch":200,"sequence":1,"predecessor_row_digest":None,"state":MAX_STATE})
    r["flow"]="materialization";r["kind"]="case-01";r["intent_kind"]="MATERIALIZATION"
    if idempotency:r["idempotency_key_id"]=idempotency
    if token:r["reservation_token_id"]=token
    if scope:r["reservation_scope_digest"]=scope
    if nonce:r["nonce_scope_digest"]=nonce
    r["payload_digest"]=payload or value(f"{seed}:payload")
    return r
def connect(psycopg,dsn):return psycopg.connect(dsn,connect_timeout=5)

def main():
    dsn=os.environ.get(ENV)
    if not dsn:
        print("SKIP_NO_PRECONFIGURED_TEST_DATABASE");return 0
    validated_disposable_target(dsn,SCHEMA,os.environ.get("CI")=="true")
    try:import psycopg
    except ImportError as exc:raise RuntimeError("configured PostgreSQL proof requires psycopg") from exc
    up,down=migration_sql(SCHEMA);cleanup=False;results=[];attempts=0
    admin=connect(psycopg,dsn)
    try:
        with admin.cursor() as cur:
            for statement in up.split(";\n"):
                if statement.strip():cur.execute(statement)
        admin.commit()
        with admin.cursor() as cur:
            cur.execute("SELECT column_name,data_type,is_nullable FROM information_schema.columns WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position",(SCHEMA,TABLE));columns=tuple((n,t,nullable=="YES") for n,t,nullable in cur.fetchall())
            cur.execute("""SELECT c.conname,c.contype,COALESCE(array_agg(a.attname ORDER BY u.ord) FILTER (WHERE a.attname IS NOT NULL),ARRAY[]::text[]),c.condeferrable,c.condeferred,CASE WHEN c.contype='c' THEN pg_get_expr(c.conbin,c.conrelid) ELSE NULL END FROM pg_constraint c LEFT JOIN LATERAL unnest(c.conkey) WITH ORDINALITY AS u(attnum,ord) ON true LEFT JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=u.attnum WHERE c.conrelid=(%s||'.'||%s)::regclass GROUP BY c.oid,c.conname,c.contype,c.condeferrable,c.condeferred,c.conbin,c.conrelid ORDER BY c.oid""",(SCHEMA,TABLE));constraints=cur.fetchall()
            cur.execute("SHOW transaction_isolation");isolation=cur.fetchone()[0].upper()
        expected=fixture_plan(SCHEMA);assert normalize_live_columns(columns)==expected.expected_columns
        assert normalize_live_constraints(constraints)==expected.expected_constraints
        winner=row();barrier=Barrier(20)
        def worker(_):
            c=connect(psycopg,dsn)
            try:barrier.wait();return insert_or_read(c,SCHEMA,winner)[0]
            finally:c.close()
        with ThreadPoolExecutor(max_workers=20) as pool:results=list(pool.map(worker,range(20)))
        attempts+=20
        with admin.cursor() as cur:cur.execute(f'SELECT count(*) FROM "{SCHEMA}"."{TABLE}"');count=cur.fetchone()[0]
        assert count==1 and results.count("INSERTED")==1 and results.count("EXISTING_SAME_PAYLOAD")==19
        changed=dict(winner,payload_digest=value("changed"));c=connect(psycopg,dsn)
        try:
            try:insert_or_read(c,SCHEMA,changed);raise AssertionError("changed payload accepted")
            except GovernanceRejected:pass
        finally:c.close()
        attempts+=1
        conflicts=(
            ("TOKEN",dict(token=winner["reservation_token_id"],kind="case-02")),
            ("SCOPE",dict(scope=winner["reservation_scope_digest"],kind="case-03")),
            ("NONCE",dict(nonce=winner["nonce_scope_digest"],kind="case-04")),
            ("LOGICAL",dict(kind="case-01")),
        )
        for label,change in conflicts:
            cross=row(f"cross-{label.casefold()}");cross["kind"]=change.pop("kind")
            for field,arg in (("reservation_token_id","token"),("reservation_scope_digest","scope"),("nonce_scope_digest","nonce")):
                if arg in change:cross[field]=change[arg]
            c=connect(psycopg,dsn)
            try:
                try:insert_or_read(c,SCHEMA,cross);raise AssertionError(f"cross-key {label} reuse accepted")
                except GovernanceRejected:pass
            finally:c.close()
            attempts+=1
        c=connect(psycopg,dsn)
        try:
            try:
                with c.cursor() as cur:cur.execute(f'INSERT INTO "{SCHEMA}"."{TABLE}" ("row_id") VALUES (%s)',("incomplete",))
            except Exception:pass
            attempts+=1
            try:
                with c.cursor() as cur:cur.execute("SELECT 1")
                raise AssertionError("aborted transaction was reused")
            except psycopg.errors.InFailedSqlTransaction:pass
            c.rollback()
            with c.cursor() as cur:cur.execute(f'SELECT payload_digest FROM "{SCHEMA}"."{TABLE}" WHERE idempotency_key_id=%s',(winner["idempotency_key_id"],));assert cur.fetchone()[0]==winner["payload_digest"]
            c.commit()
        finally:c.close()
        response_loss=row("response-loss");c=connect(psycopg,dsn);insert_or_read(c,SCHEMA,response_loss);c.close();attempts+=1
        c=connect(psycopg,dsn)
        with c.cursor() as cur:cur.execute(f'SELECT payload_digest FROM "{SCHEMA}"."{TABLE}" WHERE idempotency_key_id=%s',(response_loss["idempotency_key_id"],));assert cur.fetchone()[0]==response_loss["payload_digest"]
        c.commit();c.close()
        proof={"status":"PASS_EPHEMERAL_POSTGRESQL","test_only_database_writes":2,"test_only_database_write_attempts":attempts,"production_database_writes":0,"cleanup_succeeded":True,"concurrency_workers":20,"concurrent_row_count":1,"isolation_level":isolation,"conflict_classifications":list(PROOF_CLASSIFICATIONS),"database_url_disclosed":False,"credential_disclosed":False,"live_constraint_parity":True}
    finally:
        try:
            admin.rollback()
            with admin.cursor() as cur:cur.execute(down)
            admin.commit();cleanup=True
        finally:admin.close()
    if not cleanup:raise RuntimeError("ephemeral schema cleanup failed")
    proof["cleanup_succeeded"]=True
    if not integration_proof_valid(proof):raise RuntimeError("ephemeral PostgreSQL proof semantic validation failed")
    out=ROOT/"build/postgres-ephemeral-repository-integration-evidence.json";out.parent.mkdir(exist_ok=True);payload=json.dumps(proof,sort_keys=True,separators=(",",":")).encode();out.write_bytes(payload);out.with_suffix(out.suffix+".sha256").write_text(sha256(payload).hexdigest()+"\n",encoding="utf-8");print("PASS_EPHEMERAL_POSTGRESQL",sha256(payload).hexdigest());return 0
if __name__=="__main__":raise SystemExit(main())
