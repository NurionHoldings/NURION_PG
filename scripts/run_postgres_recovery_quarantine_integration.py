"""Actual append-only recovery quarantine proof against disposable PostgreSQL only."""
from hashlib import sha256
import json, os
from pathlib import Path

from nurion_pg.synthetic_postgres_ephemeral_repository_proof import validated_disposable_target, validated_pg_environment
from nurion_pg.synthetic_postgres_recovery_quarantine_proof import CASE_STATE, deterministic_case_id, integration_proof_valid
from scripts.run_postgres_ephemeral_repository_integration import connect

ROOT=Path(__file__).resolve().parents[1];ENV="NURION_PG_EPHEMERAL_POSTGRES_DSN";SCHEMA="nurion_pg_ci_recovery_quarantine_17901"


def exact_insert_or_read(connection, table, record):
    fields=("case_id","source_event_id","idempotency_key","payload_digest","sqlstate","provenance","observed_at","case_sequence","case_state")
    values=tuple(record[field] for field in fields)
    with connection.cursor() as cur:
        cur.execute(f'''INSERT INTO {table} ({','.join(fields)}) VALUES ({','.join(['%s']*len(fields))}) ON CONFLICT (case_id) DO NOTHING''',values)
        cur.execute(f'''SELECT {','.join(fields)} FROM {table} WHERE case_id=%s FOR SHARE''',(record["case_id"],));rows=cur.fetchall()
    if len(rows)!=1 or rows[0]!=values:
        connection.rollback();raise RuntimeError("quarantine replay conflict; exact original case preserved")
    connection.commit()


def rejected(connection, operation):
    try:
        operation();connection.commit()
    except Exception:
        connection.rollback();return True
    return False


def main():
    dsn=os.environ.get(ENV);ci_test=os.environ.get("NURION_PG_EPHEMERAL_TEST")=="1"
    if not dsn and not ci_test:print("SKIP_NO_PRECONFIGURED_TEST_DATABASE");return 0
    if dsn:validated_disposable_target(dsn,SCHEMA,os.environ.get("CI")=="true")
    else:validated_pg_environment(os.environ,SCHEMA,os.environ.get("CI")=="true")
    try:import psycopg
    except ImportError as exc:raise RuntimeError("configured PostgreSQL proof requires psycopg") from exc
    admin=connect(psycopg,dsn);cleanup=False;cases=f'"{SCHEMA}"."recovery_quarantine_cases"';source=f'"{SCHEMA}"."precommit_source_rows"'
    try:
        with admin.cursor() as cur:
            cur.execute(f'CREATE SCHEMA "{SCHEMA}"')
            cur.execute(f'''CREATE TABLE {source} (source_event_id text PRIMARY KEY, retry_count integer NOT NULL CHECK (retry_count=0))''')
            cur.execute(f'''CREATE TABLE {cases} (
                case_id text PRIMARY KEY,
                source_event_id text NOT NULL UNIQUE,
                idempotency_key text NOT NULL UNIQUE,
                payload_digest text NOT NULL CHECK (payload_digest ~ '^[0-9a-f]{{64}}$'),
                sqlstate text NOT NULL CHECK (sqlstate IN ('57P01','08006')),
                provenance text NOT NULL CHECK (provenance='ACTUAL_PRECOMMIT_BACKEND_TERMINATION'),
                observed_at timestamptz NOT NULL,
                case_sequence bigint NOT NULL UNIQUE CHECK (case_sequence>0),
                case_state text NOT NULL CHECK (case_state='{CASE_STATE}'),
                UNIQUE (source_event_id,idempotency_key,payload_digest,sqlstate,provenance,observed_at,case_sequence,case_state)
            )''')
            cur.execute(f'''CREATE FUNCTION "{SCHEMA}".reject_quarantine_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'append-only quarantine'; END $$''')
            cur.execute(f'''CREATE TRIGGER quarantine_append_only BEFORE UPDATE OR DELETE ON {cases} FOR EACH ROW EXECUTE FUNCTION "{SCHEMA}".reject_quarantine_mutation()''')
            cur.execute(f'''CREATE VIEW "{SCHEMA}"."recovery_quarantine_operator_packet" AS
                SELECT case_id,source_event_id,idempotency_key,payload_digest,sqlstate,provenance,observed_at,case_sequence,case_state,
                       false AS payment_authority,false AS receipt_authority,false AS retry_authority,false AS approval_authority
                FROM {cases}
                GROUP BY case_id,source_event_id,idempotency_key,payload_digest,sqlstate,provenance,observed_at,case_sequence,case_state''')
        admin.commit()

        event="source-event-precommit-17901";key="idempotency-precommit-17901";payload=sha256(b"held-precommit-payload").hexdigest();sqlstate="57P01";provenance="ACTUAL_PRECOMMIT_BACKEND_TERMINATION";observed="2026-01-01T00:00:00+00:00";sequence=1
        case_id=deterministic_case_id(event,key,payload,sqlstate,provenance)
        record={"case_id":case_id,"source_event_id":event,"idempotency_key":key,"payload_digest":payload,"sqlstate":sqlstate,"provenance":provenance,"observed_at":observed,"case_sequence":sequence,"case_state":CASE_STATE}
        exact_insert_or_read(admin,cases,record);exact_insert_or_read(admin,cases,record)

        changed=dict(record,payload_digest=sha256(b"changed-payload").hexdigest())
        changed["case_id"]=deterministic_case_id(changed["source_event_id"],changed["idempotency_key"],changed["payload_digest"],changed["sqlstate"],changed["provenance"])
        changed_failed=rejected(admin,lambda: exact_insert_or_read(admin,cases,changed))
        cross=dict(record,idempotency_key="cross-key",case_sequence=2)
        cross["case_id"]=deterministic_case_id(cross["source_event_id"],cross["idempotency_key"],cross["payload_digest"],cross["sqlstate"],cross["provenance"])
        cross_failed=rejected(admin,lambda: exact_insert_or_read(admin,cases,cross))
        update_failed=rejected(admin,lambda: admin.execute(f'UPDATE {cases} SET case_sequence=99 WHERE case_id=%s',(case_id,)))
        delete_failed=rejected(admin,lambda: admin.execute(f'DELETE FROM {cases} WHERE case_id=%s',(case_id,)))
        operator_view=f'"{SCHEMA}"."recovery_quarantine_operator_packet"'
        view_insert_failed=rejected(admin,lambda: admin.execute(f'INSERT INTO {operator_view} (case_id) VALUES (%s)',("forbidden-view-insert",)))
        view_update_failed=rejected(admin,lambda: admin.execute(f'UPDATE {operator_view} SET case_sequence=99 WHERE case_id=%s',(case_id,)))
        view_delete_failed=rejected(admin,lambda: admin.execute(f'DELETE FROM {operator_view} WHERE case_id=%s',(case_id,)))

        verify=connect(psycopg,dsn)
        try:
            verify.autocommit=True
            with verify.cursor() as cur:
                cur.execute("SET default_transaction_read_only=on")
                cur.execute(f'SELECT count(*) FROM {source}');source_count=cur.fetchone()[0]
                cur.execute(f'SELECT COALESCE(sum(retry_count),0) FROM {source}');retry_count=cur.fetchone()[0]
                cur.execute(f'''SELECT case_id,source_event_id,idempotency_key,payload_digest,sqlstate,provenance,
                    observed_at = %s::timestamptz AS observed_at_exact,case_sequence,case_state,
                    payment_authority,receipt_authority,retry_authority,approval_authority
                    FROM {operator_view} WHERE case_id=%s''',(observed,case_id));rows=cur.fetchall()
                cur.execute(f'SELECT count(*) FROM {cases}');row_count=cur.fetchone()[0]
        finally:verify.close()
        exact=len(rows)==1 and rows[0][0:6]==(case_id,event,key,payload,sqlstate,provenance) and rows[0][6:] == (True,sequence,CASE_STATE,False,False,False,False)
        if not exact or row_count!=1 or source_count or retry_count or not all((changed_failed,cross_failed,update_failed,delete_failed,view_insert_failed,view_update_failed,view_delete_failed)):
            raise RuntimeError("recovery quarantine integration invariant failed; proof HOLD")
        proof={"status":"PASS_POSTGRES_RECOVERY_QUARANTINE_PROOF","case_state":CASE_STATE,"deterministic_case_identity":case_id==deterministic_case_id(event,key,payload,sqlstate,provenance),"source_event_exact_match":True,"idempotency_key_exact_match":True,"payload_digest_exact_match":True,"sqlstate_exact_match":True,"provenance_exact_match":True,"observed_at_exact_match":rows[0][6] is True,"sequence_exact_match":True,"same_payload_replay_row_count":row_count,"same_payload_replay_converged":True,"changed_payload_fail_closed":changed_failed,"cross_key_fail_closed":cross_failed,"append_only":update_failed and delete_failed,"payment_authority":False,"receipt_authority":False,"retry_authority":False,"approval_authority":False,"fresh_read_only_operator_packet":True,"reconciliation_view_read_only":True,"operator_view_insert_rejected":view_insert_failed,"operator_view_update_rejected":view_update_failed,"operator_view_delete_rejected":view_delete_failed,"precommit_source_row_count":source_count,"precommit_source_retry_count":retry_count,"actual_network_partition_claimed":False,"actual_failover_claimed":False,"production_database_writes":0,"cleanup_succeeded":True,"credential_disclosed":False,"password_credential_configured":False}
    finally:
        try:
            admin.rollback()
            with admin.cursor() as cur:cur.execute(f'DROP SCHEMA IF EXISTS "{SCHEMA}" CASCADE')
            admin.commit();cleanup=True
        finally:admin.close()
    if not cleanup:raise RuntimeError("ephemeral recovery quarantine schema cleanup failed")
    if not integration_proof_valid(proof):raise RuntimeError("PostgreSQL recovery quarantine semantic validation failed")
    out=ROOT/"build/postgres-recovery-quarantine-integration-evidence.json";out.parent.mkdir(exist_ok=True);payload_bytes=json.dumps(proof,sort_keys=True,separators=(",",":")).encode();out.write_bytes(payload_bytes);digest=sha256(payload_bytes).hexdigest();out.with_suffix(out.suffix+".sha256").write_text(digest+"\n",encoding="utf-8");print("PASS_POSTGRES_RECOVERY_QUARANTINE_PROOF",digest);return 0
if __name__=="__main__":raise SystemExit(main())
