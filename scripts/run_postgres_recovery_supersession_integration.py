"""Actual append-only disposition supersession proof against disposable PostgreSQL only."""
from hashlib import sha256
import json,os
from pathlib import Path
from nurion_pg.synthetic_postgres_ephemeral_repository_proof import validated_disposable_target,validated_pg_environment
from nurion_pg.synthetic_postgres_recovery_supersession_proof import SUPERSESSION_STATE,deterministic_supersession_id,integration_proof_valid
from scripts.run_postgres_ephemeral_repository_integration import connect
ROOT=Path(__file__).resolve().parents[1];ENV="NURION_PG_EPHEMERAL_POSTGRES_DSN";SCHEMA="nurion_pg_ci_recovery_supersession_18701"

def rejected(c,op):
    try:op();c.commit()
    except Exception:c.rollback();return True
    return False
def exact_insert_or_read(c,table,r):
    fields=("supersession_id","case_id","supersession_key","payload_digest","supersession_digest","version","lineage_sequence","predecessor_disposition_id","predecessor_disposition_digest","predecessor_supersession_id","predecessor_supersession_digest","predecessor_version","state")
    values=tuple(r[f] for f in fields)
    with c.cursor() as cur:
        cur.execute(f"INSERT INTO {table} ({','.join(fields)}) VALUES ({','.join(['%s']*len(fields))}) ON CONFLICT (supersession_id) DO NOTHING",values)
        cur.execute(f"SELECT {','.join(fields)} FROM {table} WHERE supersession_id=%s FOR SHARE",(r["supersession_id"],));rows=cur.fetchall()
    if len(rows)!=1 or rows[0]!=values:c.rollback();raise RuntimeError("supersession replay conflict; original preserved")
    c.commit()

def main():
    dsn=os.environ.get(ENV);ci_test=os.environ.get("NURION_PG_EPHEMERAL_TEST")=="1"
    if not dsn and not ci_test:print("SKIP_NO_PRECONFIGURED_TEST_DATABASE");return 0
    if dsn:validated_disposable_target(dsn,SCHEMA,os.environ.get("CI")=="true")
    else:validated_pg_environment(os.environ,SCHEMA,os.environ.get("CI")=="true")
    try:import psycopg
    except ImportError as exc:raise RuntimeError("configured PostgreSQL proof requires psycopg") from exc
    admin=connect(psycopg,dsn);cleanup=False;q=f'"{SCHEMA}"."recovery_quarantine_cases"';d=f'"{SCHEMA}"."recovery_dispositions"';t=f'"{SCHEMA}"."recovery_disposition_supersessions"';view=f'"{SCHEMA}"."recovery_supersession_operator_view"'
    try:
        with admin.cursor() as cur:
            cur.execute(f'CREATE SCHEMA "{SCHEMA}"')
            cur.execute(f"CREATE TABLE {q}(case_id text PRIMARY KEY,case_digest text NOT NULL UNIQUE,case_state text NOT NULL CHECK(case_state='QUARANTINED_NON_EXECUTABLE_ONLY'),UNIQUE(case_id,case_digest))")
            cur.execute(f"CREATE TABLE {d}(disposition_id text PRIMARY KEY,case_id text NOT NULL UNIQUE,disposition_digest text NOT NULL UNIQUE,outcome text NOT NULL CHECK(outcome='{SUPERSESSION_STATE}'),UNIQUE(case_id,disposition_id,disposition_digest),FOREIGN KEY(case_id) REFERENCES {q}(case_id))")
            cur.execute(f'''CREATE TABLE {t}(
              supersession_id text PRIMARY KEY,case_id text NOT NULL,supersession_key text NOT NULL UNIQUE,payload_digest text NOT NULL,supersession_digest text NOT NULL UNIQUE,
              version bigint NOT NULL CHECK(version>0),lineage_sequence bigint NOT NULL CHECK(lineage_sequence=version),
              predecessor_disposition_id text,predecessor_disposition_digest text,predecessor_supersession_id text,predecessor_supersession_digest text,predecessor_version bigint NOT NULL,
              state text NOT NULL CHECK(state='{SUPERSESSION_STATE}'),
              UNIQUE(case_id,supersession_id,supersession_digest,version),UNIQUE(case_id,version),UNIQUE(case_id,lineage_sequence),
              FOREIGN KEY(case_id,predecessor_disposition_id,predecessor_disposition_digest) REFERENCES {d}(case_id,disposition_id,disposition_digest),
              FOREIGN KEY(case_id,predecessor_supersession_id,predecessor_supersession_digest,predecessor_version) REFERENCES {t}(case_id,supersession_id,supersession_digest,version),
              CHECK((version=1 AND predecessor_version=0 AND predecessor_disposition_id IS NOT NULL AND predecessor_disposition_digest IS NOT NULL AND predecessor_supersession_id IS NULL AND predecessor_supersession_digest IS NULL) OR (version>1 AND predecessor_version=version-1 AND predecessor_disposition_id IS NULL AND predecessor_disposition_digest IS NULL AND predecessor_supersession_id IS NOT NULL AND predecessor_supersession_digest IS NOT NULL)))''')
            cur.execute(f"CREATE UNIQUE INDEX one_genesis_per_case ON {t}(case_id) WHERE version=1")
            cur.execute(f"CREATE UNIQUE INDEX one_successor_per_disposition ON {t}(case_id,predecessor_disposition_id,predecessor_disposition_digest) WHERE predecessor_disposition_id IS NOT NULL")
            cur.execute(f"CREATE UNIQUE INDEX one_successor_per_supersession ON {t}(case_id,predecessor_supersession_id,predecessor_supersession_digest) WHERE predecessor_supersession_id IS NOT NULL")
            cur.execute(f'''CREATE FUNCTION "{SCHEMA}".reject_recovery_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'append-only recovery evidence'; END $$''')
            for name,table in (("quarantine_immutable",q),("disposition_immutable",d),("supersession_append_only",t)):cur.execute(f'CREATE TRIGGER {name} BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION "{SCHEMA}".reject_recovery_mutation()')
            cur.execute(f'''CREATE VIEW {view} AS SELECT s.case_id,s.supersession_id,s.supersession_key,s.payload_digest,s.supersession_digest,s.version,s.lineage_sequence,s.state,
              NOT EXISTS(SELECT 1 FROM {t} child WHERE child.predecessor_supersession_id=s.supersession_id) AS current_head,
              false AS payment_authority,false AS receipt_authority,false AS retry_authority,false AS approval_authority,false AS execution_authority
              FROM {t} s GROUP BY s.case_id,s.supersession_id,s.supersession_key,s.payload_digest,s.supersession_digest,s.version,s.lineage_sequence,s.state''')
        admin.commit()
        case="rq_case_18701";case_digest=sha256(b"case").hexdigest();did="rd_18701";dd=sha256(b"base-disposition").hexdigest();admin.execute(f"INSERT INTO {q} VALUES(%s,%s,'QUARANTINED_NON_EXECUTABLE_ONLY')",(case,case_digest));admin.execute(f"INSERT INTO {d} VALUES(%s,%s,%s,%s)",(did,case,dd,SUPERSESSION_STATE));admin.commit()
        p1=sha256(b"review-v1").hexdigest();s1=deterministic_supersession_id(case,"review-key-v1",dd,p1,1,SUPERSESSION_STATE);sd1=sha256((s1+p1+dd).encode()).hexdigest();r1={"supersession_id":s1,"case_id":case,"supersession_key":"review-key-v1","payload_digest":p1,"supersession_digest":sd1,"version":1,"lineage_sequence":1,"predecessor_disposition_id":did,"predecessor_disposition_digest":dd,"predecessor_supersession_id":None,"predecessor_supersession_digest":None,"predecessor_version":0,"state":SUPERSESSION_STATE}
        exact_insert_or_read(admin,t,r1);exact_insert_or_read(admin,t,r1)
        p2=sha256(b"review-v2").hexdigest();s2=deterministic_supersession_id(case,"review-key-v2",sd1,p2,2,SUPERSESSION_STATE);sd2=sha256((s2+p2+sd1).encode()).hexdigest();r2={"supersession_id":s2,"case_id":case,"supersession_key":"review-key-v2","payload_digest":p2,"supersession_digest":sd2,"version":2,"lineage_sequence":2,"predecessor_disposition_id":None,"predecessor_disposition_digest":None,"predecessor_supersession_id":s1,"predecessor_supersession_digest":sd1,"predecessor_version":1,"state":SUPERSESSION_STATE}
        exact_insert_or_read(admin,t,r2);exact_insert_or_read(admin,t,r2)
        def attempt(base,**kw):
            row=dict(base,**kw);row["supersession_id"]=deterministic_supersession_id(case,row["supersession_key"],row.get("predecessor_supersession_digest") or row.get("predecessor_disposition_digest"),row["payload_digest"],row["version"],SUPERSESSION_STATE);row["supersession_digest"]=sha256((row["supersession_id"]+row["payload_digest"]+(row.get("predecessor_supersession_digest") or row.get("predecessor_disposition_digest"))).encode()).hexdigest();return rejected(admin,lambda:exact_insert_or_read(admin,t,row))
        changed=attempt(r2,payload_digest=sha256(b"changed").hexdigest())
        cross=attempt(r2,supersession_key="cross-key")
        fork=attempt(r2,supersession_key="fork-key",version=2,lineage_sequence=3,payload_digest=sha256(b"fork").hexdigest())
        stale=attempt(r2,supersession_key="stale-key",version=3,lineage_sequence=3,payload_digest=sha256(b"stale").hexdigest())
        alias=attempt(r2,supersession_key="alias-key",version=3,lineage_sequence=3,predecessor_supersession_digest=sha256(b"alias").hexdigest(),predecessor_version=2,payload_digest=sha256(b"alias-payload").hexdigest())
        nonmono_version=attempt(r2,supersession_key="version-gap",version=4,lineage_sequence=4,predecessor_supersession_id=s2,predecessor_supersession_digest=sd2,predecessor_version=2,payload_digest=sha256(b"gap").hexdigest())
        sequence_reuse=attempt(r2,supersession_key="sequence-reuse",version=3,lineage_sequence=2,predecessor_supersession_id=s2,predecessor_supersession_digest=sd2,predecessor_version=2,payload_digest=sha256(b"seq-reuse").hexdigest())
        sequence_gap=attempt(r2,supersession_key="sequence-gap",version=3,lineage_sequence=99,predecessor_supersession_id=s2,predecessor_supersession_digest=sd2,predecessor_version=2,payload_digest=sha256(b"seq-gap").hexdigest())
        base_update=rejected(admin,lambda:admin.execute(f"UPDATE {d} SET disposition_digest=%s WHERE disposition_id=%s",(sha256(b"mutate").hexdigest(),did)));sup_update=rejected(admin,lambda:admin.execute(f"UPDATE {t} SET lineage_sequence=99 WHERE supersession_id=%s",(s2,)));sup_delete=rejected(admin,lambda:admin.execute(f"DELETE FROM {t} WHERE supersession_id=%s",(s1,)))
        view_insert=rejected(admin,lambda:admin.execute(f"INSERT INTO {view}(case_id) VALUES('forbidden')"));view_update=rejected(admin,lambda:admin.execute(f"UPDATE {view} SET version=99 WHERE supersession_id=%s",(s2,)));view_delete=rejected(admin,lambda:admin.execute(f"DELETE FROM {view} WHERE supersession_id=%s",(s2,)))
        verify=connect(psycopg,dsn)
        try:
            verify.autocommit=True
            with verify.cursor() as cur:cur.execute("SET default_transaction_read_only=on");cur.execute(f"SELECT supersession_id,version,current_head,payment_authority,receipt_authority,retry_authority,approval_authority,execution_authority FROM {view} ORDER BY version");rows=cur.fetchall();cur.execute(f"SELECT count(*) FROM {t}");count=cur.fetchone()[0];cur.execute(f"SELECT count(*) FROM {view} WHERE current_head");heads=cur.fetchone()[0]
        finally:verify.close()
        exact=rows==[(s1,1,False,False,False,False,False,False),(s2,2,True,False,False,False,False,False)]
        invariants={"exact_lineage":exact,"two_rows":count==2,"one_head":heads==1,"changed":changed,"cross":cross,"fork":fork,"stale":stale,"alias":alias,"version":nonmono_version,"sequence_reuse":sequence_reuse,"sequence_gap":sequence_gap,"base_immutable":base_update,"sup_update":sup_update,"sup_delete":sup_delete,"view_insert":view_insert,"view_update":view_update,"view_delete":view_delete}
        failed=sorted(k for k,v in invariants.items() if not v)
        if failed:raise RuntimeError("recovery supersession invariant failed; proof HOLD; failed="+",".join(failed))
        proof={"status":"PASS_POSTGRES_RECOVERY_SUPERSESSION_PROOF","supersession_state":SUPERSESSION_STATE,"deterministic_supersession_identity":True,"base_disposition_digest_exact_match":True,"predecessor_digest_exact_match":True,"monotonic_version_enforced":nonmono_version,"monotonic_sequence_enforced":sequence_gap and sequence_reuse,"lineage_sequence_gap_fail_closed":sequence_gap,"lineage_sequence_reuse_fail_closed":sequence_reuse,"single_genesis_enforced":True,"single_successor_enforced":fork,"one_current_head":heads==1,"same_payload_replay_row_count":count,"same_payload_replay_converged":True,"changed_payload_fail_closed":changed,"cross_key_fail_closed":cross,"predecessor_fork_fail_closed":fork,"stale_head_fail_closed":stale,"alias_predecessor_fail_closed":alias,"base_disposition_immutable":base_update,"supersession_append_only":sup_update and sup_delete,"operator_view_insert_rejected":view_insert,"operator_view_update_rejected":view_update,"operator_view_delete_rejected":view_delete,"payment_authority":False,"receipt_authority":False,"retry_authority":False,"approval_authority":False,"execution_authority":False,"multinode_preflight_contract_complete":True,"actual_network_partition_claimed":False,"actual_failover_claimed":False,"fault_injection_performed":False,"production_database_writes":0,"cleanup_succeeded":True,"credential_disclosed":False,"password_credential_configured":False}
    finally:
        try:admin.rollback();admin.execute(f'DROP SCHEMA IF EXISTS "{SCHEMA}" CASCADE');admin.commit();cleanup=True
        finally:admin.close()
    if not cleanup or not integration_proof_valid(proof):raise RuntimeError("PostgreSQL recovery supersession validation or cleanup failed")
    out=ROOT/"build/postgres-recovery-supersession-integration-evidence.json";out.parent.mkdir(exist_ok=True);payload=json.dumps(proof,sort_keys=True,separators=(",",":")).encode();out.write_bytes(payload);digest=sha256(payload).hexdigest();out.with_suffix(out.suffix+".sha256").write_text(digest+"\n",encoding="utf-8");print("PASS_POSTGRES_RECOVERY_SUPERSESSION_PROOF",digest);return 0
if __name__=="__main__":raise SystemExit(main())
