"""Actual current-head review snapshot/receipt proof on disposable PostgreSQL."""
from hashlib import sha256
import json
import os
from pathlib import Path

from nurion_pg.synthetic_postgres_ephemeral_repository_proof import validated_disposable_target, validated_pg_environment
from nurion_pg.synthetic_postgres_recovery_review_receipt_proof import (
    EXPECTED_PROOF, REVIEW_STATE, deterministic_review_receipt_id,
    deterministic_review_snapshot_id, integration_proof_valid,
)
from scripts.run_postgres_ephemeral_repository_integration import connect

ROOT = Path(__file__).resolve().parents[1]
ENV = "NURION_PG_EPHEMERAL_POSTGRES_DSN"
SCHEMA = "nurion_pg_ci_recovery_review_receipt_19101"


def rejected(connection, operation):
    try:
        operation(); connection.commit()
    except Exception:
        connection.rollback(); return True
    return False


def insert_or_exact(connection, table, fields, row, key):
    values = tuple(row[field] for field in fields)
    with connection.cursor() as cursor:
        cursor.execute(f"INSERT INTO {table} ({','.join(fields)}) VALUES ({','.join(['%s']*len(fields))}) ON CONFLICT ({key}) DO NOTHING", values)
        cursor.execute(f"SELECT {','.join(fields)} FROM {table} WHERE {key}=%s FOR SHARE", (row[key],))
        found = cursor.fetchall()
    if found != [values]:
        connection.rollback(); raise RuntimeError("review evidence replay conflict; original preserved")
    connection.commit()


def main():
    dsn = os.environ.get(ENV); ci_test = os.environ.get("NURION_PG_EPHEMERAL_TEST") == "1"
    if not dsn and not ci_test:
        print("SKIP_NO_PRECONFIGURED_TEST_DATABASE"); return 0
    if dsn: validated_disposable_target(dsn, SCHEMA, os.environ.get("CI") == "true")
    else: validated_pg_environment(os.environ, SCHEMA, os.environ.get("CI") == "true")
    try: import psycopg
    except ImportError as exc: raise RuntimeError("configured PostgreSQL proof requires psycopg") from exc
    admin = connect(psycopg, dsn); cleanup = False
    source = f'"{SCHEMA}"."recovery_supersessions"'
    snapshots = f'"{SCHEMA}"."recovery_review_snapshots"'
    receipts = f'"{SCHEMA}"."recovery_review_receipts"'
    view = f'"{SCHEMA}"."recovery_review_operator_view"'
    try:
        with admin.cursor() as cursor:
            cursor.execute(f'CREATE SCHEMA "{SCHEMA}"')
            cursor.execute(f"""CREATE TABLE {source}(
              supersession_id text PRIMARY KEY, case_id text NOT NULL, supersession_digest text NOT NULL,
              version bigint NOT NULL CHECK(version>0), predecessor_supersession_id text,
              state text NOT NULL, UNIQUE(case_id,supersession_id,supersession_digest,version),
              FOREIGN KEY(predecessor_supersession_id) REFERENCES {source}(supersession_id))""")
            cursor.execute(f"""CREATE TABLE {snapshots}(
              snapshot_id text PRIMARY KEY, review_key text NOT NULL UNIQUE, case_id text NOT NULL,
              supersession_id text NOT NULL, supersession_digest text NOT NULL, version bigint NOT NULL,
              snapshot_digest text NOT NULL UNIQUE, state text NOT NULL CHECK(state='{REVIEW_STATE}'),
              UNIQUE(snapshot_id,snapshot_digest),
              FOREIGN KEY(case_id,supersession_id,supersession_digest,version)
                REFERENCES {source}(case_id,supersession_id,supersession_digest,version))""")
            cursor.execute(f"""CREATE TABLE {receipts}(
              receipt_id text PRIMARY KEY, snapshot_id text NOT NULL UNIQUE, snapshot_digest text NOT NULL,
              reviewer_subject text NOT NULL, result_digest text NOT NULL, receipt_digest text NOT NULL UNIQUE,
              state text NOT NULL CHECK(state='{REVIEW_STATE}'),
              FOREIGN KEY(snapshot_id,snapshot_digest) REFERENCES {snapshots}(snapshot_id,snapshot_digest))""")
            cursor.execute(f"""CREATE FUNCTION "{SCHEMA}".require_current_head() RETURNS trigger LANGUAGE plpgsql AS $$
              BEGIN IF EXISTS(SELECT 1 FROM {source} child WHERE child.predecessor_supersession_id=NEW.supersession_id)
              THEN RAISE EXCEPTION 'review snapshot requires exact current head'; END IF; RETURN NEW; END $$""")
            cursor.execute(f'CREATE TRIGGER exact_current_head BEFORE INSERT ON {snapshots} FOR EACH ROW EXECUTE FUNCTION "{SCHEMA}".require_current_head()')
            cursor.execute(f"""CREATE FUNCTION "{SCHEMA}".reject_review_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
              BEGIN RAISE EXCEPTION 'append-only review evidence'; END $$""")
            for name, table in (("source_immutable", source), ("snapshot_append_only", snapshots), ("receipt_append_only", receipts)):
                cursor.execute(f'CREATE TRIGGER {name} BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION "{SCHEMA}".reject_review_mutation()')
            cursor.execute(f"""CREATE VIEW {view} AS SELECT s.snapshot_id,s.case_id,s.supersession_id,s.supersession_digest,s.version,
              r.receipt_id,r.reviewer_subject,r.result_digest,s.state,
              false AS payment_authority,false AS receipt_authority,false AS retry_authority,
              false AS approval_authority,false AS execution_authority
              FROM {snapshots} s LEFT JOIN {receipts} r USING(snapshot_id,snapshot_digest)""")
        admin.commit()
        case = "rq_case_19101"; old_id = "rs_old"; head_id = "rs_head"
        old_digest = sha256(b"old").hexdigest(); head_digest = sha256(b"head").hexdigest()
        admin.execute(f"INSERT INTO {source} VALUES(%s,%s,%s,1,NULL,'HOLD_FOR_MANUAL_RECOVERY_NON_EXECUTABLE')", (old_id, case, old_digest))
        admin.execute(f"INSERT INTO {source} VALUES(%s,%s,%s,2,%s,'HOLD_FOR_MANUAL_RECOVERY_NON_EXECUTABLE')", (head_id, case, head_digest, old_id)); admin.commit()
        snapshot_id = deterministic_review_snapshot_id(case, head_id, head_digest, 2, "review-key")
        snapshot_digest = sha256((snapshot_id + head_digest).encode()).hexdigest()
        snapshot = dict(snapshot_id=snapshot_id, review_key="review-key", case_id=case, supersession_id=head_id, supersession_digest=head_digest, version=2, snapshot_digest=snapshot_digest, state=REVIEW_STATE)
        snapshot_fields = tuple(snapshot)
        insert_or_exact(admin, snapshots, snapshot_fields, snapshot, "snapshot_id"); insert_or_exact(admin, snapshots, snapshot_fields, snapshot, "snapshot_id")
        result_digest = sha256(b"non-executable-review-result").hexdigest()
        receipt_id = deterministic_review_receipt_id(snapshot_id, snapshot_digest, "reviewer:independent", result_digest)
        receipt_digest = sha256((receipt_id + result_digest).encode()).hexdigest()
        receipt = dict(receipt_id=receipt_id, snapshot_id=snapshot_id, snapshot_digest=snapshot_digest, reviewer_subject="reviewer:independent", result_digest=result_digest, receipt_digest=receipt_digest, state=REVIEW_STATE)
        receipt_fields = tuple(receipt)
        insert_or_exact(admin, receipts, receipt_fields, receipt, "receipt_id"); insert_or_exact(admin, receipts, receipt_fields, receipt, "receipt_id")
        stale_id = deterministic_review_snapshot_id(case, old_id, old_digest, 1, "stale-key")
        stale = dict(snapshot, snapshot_id=stale_id, review_key="stale-key", supersession_id=old_id, supersession_digest=old_digest, version=1, snapshot_digest=sha256(stale_id.encode()).hexdigest())
        stale_rejected = rejected(admin, lambda: insert_or_exact(admin, snapshots, snapshot_fields, stale, "snapshot_id"))
        changed = dict(snapshot, snapshot_digest=sha256(b"changed").hexdigest())
        changed_rejected = rejected(admin, lambda: insert_or_exact(admin, snapshots, snapshot_fields, changed, "snapshot_id"))
        cross = dict(snapshot, snapshot_id=deterministic_review_snapshot_id("other-case", head_id, head_digest, 2, "cross-key"), review_key="cross-key", case_id="other-case")
        cross["snapshot_digest"] = sha256(cross["snapshot_id"].encode()).hexdigest()
        cross_rejected = rejected(admin, lambda: insert_or_exact(admin, snapshots, snapshot_fields, cross, "snapshot_id"))
        tampered = dict(receipt, receipt_id=deterministic_review_receipt_id(snapshot_id, snapshot_digest, "reviewer:other", result_digest), reviewer_subject="reviewer:other", receipt_digest=sha256(b"tampered").hexdigest())
        tamper_rejected = rejected(admin, lambda: insert_or_exact(admin, receipts, receipt_fields, tampered, "receipt_id"))
        snapshot_update = rejected(admin, lambda: admin.execute(f"UPDATE {snapshots} SET version=9 WHERE snapshot_id=%s", (snapshot_id,)))
        snapshot_delete = rejected(admin, lambda: admin.execute(f"DELETE FROM {snapshots} WHERE snapshot_id=%s", (snapshot_id,)))
        receipt_update = rejected(admin, lambda: admin.execute(f"UPDATE {receipts} SET reviewer_subject='other' WHERE receipt_id=%s", (receipt_id,)))
        receipt_delete = rejected(admin, lambda: admin.execute(f"DELETE FROM {receipts} WHERE receipt_id=%s", (receipt_id,)))
        view_insert = rejected(admin, lambda: admin.execute(f"INSERT INTO {view}(snapshot_id) VALUES('forbidden')"))
        view_update = rejected(admin, lambda: admin.execute(f"UPDATE {view} SET version=9 WHERE snapshot_id=%s", (snapshot_id,)))
        view_delete = rejected(admin, lambda: admin.execute(f"DELETE FROM {view} WHERE snapshot_id=%s", (snapshot_id,)))
        verify = connect(psycopg, dsn)
        try:
            verify.autocommit = True
            with verify.cursor() as cursor:
                cursor.execute("SET default_transaction_read_only=on")
                cursor.execute(f"SELECT snapshot_id,receipt_id,state,payment_authority,receipt_authority,retry_authority,approval_authority,execution_authority FROM {view}")
                rows = cursor.fetchall()
        finally: verify.close()
        exact = rows == [(snapshot_id, receipt_id, REVIEW_STATE, False, False, False, False, False)]
        checks = (exact, stale_rejected, changed_rejected, cross_rejected, tamper_rejected, snapshot_update, snapshot_delete, receipt_update, receipt_delete, view_insert, view_update, view_delete)
        if not all(checks): raise RuntimeError("recovery review receipt invariant failed; proof HOLD")
        proof = dict(EXPECTED_PROOF)
    finally:
        try:
            admin.rollback(); admin.execute(f'DROP SCHEMA IF EXISTS "{SCHEMA}" CASCADE'); admin.commit(); cleanup = True
        finally: admin.close()
    proof["cleanup_succeeded"] = cleanup
    if not integration_proof_valid(proof): raise RuntimeError("PostgreSQL recovery review receipt validation or cleanup failed")
    out = ROOT / "build/postgres-recovery-review-receipt-integration-evidence.json"; out.parent.mkdir(exist_ok=True)
    payload = json.dumps(proof, sort_keys=True, separators=(",", ":")).encode(); out.write_bytes(payload)
    digest = sha256(payload).hexdigest(); out.with_suffix(out.suffix + ".sha256").write_text(digest + "\n", encoding="utf-8")
    print("PASS_POSTGRES_RECOVERY_REVIEW_RECEIPT_PROOF", digest); return 0


if __name__ == "__main__": raise SystemExit(main())
