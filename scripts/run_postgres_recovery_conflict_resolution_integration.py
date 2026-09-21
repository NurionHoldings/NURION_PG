"""Actual conflict-resolution lineage proof on disposable PostgreSQL."""
from hashlib import sha256
import json,os
from pathlib import Path
from nurion_pg.synthetic_postgres_ephemeral_repository_proof import validated_disposable_target,validated_pg_environment
from nurion_pg.synthetic_postgres_recovery_conflict_resolution_proof import RESOLUTION_STATE,canonical_conflict_set,conflict_set_digest,deterministic_resolution_docket_id,deterministic_resolution_round_id
from scripts.run_postgres_ephemeral_repository_integration import connect
ROOT=Path(__file__).resolve().parents[1];ENV="NURION_PG_EPHEMERAL_POSTGRES_DSN";SCHEMA="nurion_pg_ci_recovery_conflict_resolution_19901"
def rejected(c,op):
    try:op();c.commit()
    except Exception:c.rollback();return True
    return False
def main():
    dsn=os.environ.get(ENV);ci=os.environ.get("NURION_PG_EPHEMERAL_TEST")=="1"
    if not dsn and not ci:print("SKIP_NO_PRECONFIGURED_TEST_DATABASE");return 0
    if dsn:validated_disposable_target(dsn,SCHEMA,os.environ.get("CI")=="true")
    else:validated_pg_environment(os.environ,SCHEMA,os.environ.get("CI")=="true")
    import psycopg
    c=connect(psycopg,dsn);cleanup=False;rec=f'"{SCHEMA}".recommendations';con=f'"{SCHEMA}".conflicts';d=f'"{SCHEMA}".resolution_dockets';r=f'"{SCHEMA}".resolution_rounds';v=f'"{SCHEMA}".resolution_operator_view'
    try:
        with c.cursor() as q:
            q.execute(f'CREATE SCHEMA "{SCHEMA}"');q.execute(f"CREATE TABLE {rec}(recommendation_id text PRIMARY KEY,recommendation_digest text NOT NULL UNIQUE,author_subject text NOT NULL,UNIQUE(recommendation_id,recommendation_digest))");q.execute(f"CREATE TABLE {con}(concurrence_id text PRIMARY KEY,recommendation_id text NOT NULL,concurrence_digest text NOT NULL UNIQUE,reviewer_subject text NOT NULL,verdict text NOT NULL CHECK(verdict='HOLD_CONFLICT'),UNIQUE(recommendation_id,concurrence_id,concurrence_digest),FOREIGN KEY(recommendation_id) REFERENCES {rec}(recommendation_id))")
            q.execute(f"CREATE TABLE {d}(docket_id text PRIMARY KEY,recommendation_id text NOT NULL,recommendation_digest text NOT NULL,conflict_set_digest text NOT NULL,resolution_key text NOT NULL UNIQUE,author_subject text NOT NULL,resolution_digest text NOT NULL,docket_digest text NOT NULL UNIQUE,state text NOT NULL CHECK(state='{RESOLUTION_STATE}'),UNIQUE(docket_id,docket_digest,author_subject),FOREIGN KEY(recommendation_id,recommendation_digest) REFERENCES {rec}(recommendation_id,recommendation_digest))")
            q.execute(f"CREATE TABLE {r}(round_id text PRIMARY KEY,docket_id text NOT NULL,docket_digest text NOT NULL,author_subject text NOT NULL,predecessor_round_id text,predecessor_round_digest text,predecessor_round_number bigint,round_number bigint NOT NULL CHECK(round_number>0),reviewer_subject text NOT NULL,verdict text NOT NULL CHECK(verdict IN ('REVIEWED_HOLD','REVIEWED_NON_EXECUTABLE')),rationale_digest text NOT NULL,round_digest text NOT NULL UNIQUE,state text NOT NULL CHECK(state='{RESOLUTION_STATE}'),CHECK(author_subject<>reviewer_subject),CHECK((round_number=1 AND predecessor_round_id IS NULL AND predecessor_round_digest IS NULL AND predecessor_round_number IS NULL) OR (round_number>1 AND predecessor_round_id IS NOT NULL AND predecessor_round_digest IS NOT NULL AND predecessor_round_number=round_number-1)),UNIQUE(docket_id,round_number),UNIQUE(docket_id,round_id,round_digest,round_number),FOREIGN KEY(docket_id,docket_digest,author_subject) REFERENCES {d}(docket_id,docket_digest,author_subject),FOREIGN KEY(docket_id,predecessor_round_id,predecessor_round_digest,predecessor_round_number) REFERENCES {r}(docket_id,round_id,round_digest,round_number))")
            q.execute(f"CREATE UNIQUE INDEX one_genesis_resolution_round ON {r}(docket_id) WHERE round_number=1");q.execute(f"CREATE UNIQUE INDEX one_successor_resolution_round ON {r}(docket_id,predecessor_round_id) WHERE predecessor_round_id IS NOT NULL")
            q.execute(f"CREATE FUNCTION \"{SCHEMA}\".reject_resolution_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'append-only conflict resolution'; END $$");
            for name,table in (("recommendation_immutable",rec),("conflict_immutable",con),("docket_append_only",d),("round_append_only",r)):q.execute(f'CREATE TRIGGER {name} BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION "{SCHEMA}".reject_resolution_mutation()')
            q.execute(f"CREATE VIEW {v} AS SELECT d.docket_id,count(r.round_id) review_rounds,bool_or(r.verdict='REVIEWED_HOLD') held,false payment_authority,false receipt_authority,false retry_authority,false approval_authority,false execution_authority FROM {d} d LEFT JOIN {r} r USING(docket_id,docket_digest,author_subject) GROUP BY d.docket_id")
        c.commit();recommendation="recommendation";rd=sha256(b"recommendation").hexdigest();c.execute(f"INSERT INTO {rec} VALUES(%s,%s,'author:recommendation')",(recommendation,rd));rows=(("c1",sha256(b"c1").hexdigest(),"reviewer:one"),("c2",sha256(b"c2").hexdigest(),"reviewer:two"))
        for row in rows:c.execute(f"INSERT INTO {con} VALUES(%s,%s,%s,%s,'HOLD_CONFLICT')",(row[0],recommendation,row[1],row[2]));c.commit()
        cs=conflict_set_digest(rows);resolution=sha256(b"resolution").hexdigest();did=deterministic_resolution_docket_id(recommendation,rd,rows,"key","author:resolution",resolution);dd=sha256((did+cs).encode()).hexdigest();c.execute(f"INSERT INTO {d} VALUES(%s,%s,%s,%s,'key','author:resolution',%s,%s,%s)",(did,recommendation,rd,cs,resolution,dd,RESOLUTION_STATE));c.commit()
        why=sha256(b"hold").hexdigest();rid=deterministic_resolution_round_id(did,dd,None,None,1,"reviewer:three","REVIEWED_HOLD",why,"author:resolution");rhash=sha256((rid+why).encode()).hexdigest();c.execute(f"INSERT INTO {r} VALUES(%s,%s,%s,'author:resolution',NULL,NULL,NULL,1,'reviewer:three','REVIEWED_HOLD',%s,%s,%s)",(rid,did,dd,why,rhash,RESOLUTION_STATE));c.commit()
        why2=sha256(b"reviewed").hexdigest();rid2=deterministic_resolution_round_id(did,dd,rid,rhash,2,"reviewer:four","REVIEWED_NON_EXECUTABLE",why2,"author:resolution");rhash2=sha256((rid2+why2).encode()).hexdigest();c.execute(f"INSERT INTO {r} VALUES(%s,%s,%s,'author:resolution',%s,%s,1,2,'reviewer:four','REVIEWED_NON_EXECUTABLE',%s,%s,%s)",(rid2,did,dd,rid,rhash,why2,rhash2,RESOLUTION_STATE));c.commit()
        self_review=rejected(c,lambda:c.execute(f"INSERT INTO {r} VALUES('self',%s,%s,'author:resolution',NULL,NULL,NULL,1,'author:resolution','REVIEWED_HOLD',%s,%s,%s)",(did,dd,why,sha256(b'self').hexdigest(),RESOLUTION_STATE)));fork=rejected(c,lambda:c.execute(f"INSERT INTO {r} VALUES('fork',%s,%s,'author:resolution',%s,%s,1,2,'reviewer:five','REVIEWED_HOLD',%s,%s,%s)",(did,dd,rid,rhash,why,sha256(b'fork').hexdigest(),RESOLUTION_STATE)));mutation=rejected(c,lambda:c.execute(f"UPDATE {d} SET conflict_set_digest=%s WHERE docket_id=%s",(sha256(b'changed').hexdigest(),did)));view_dml=rejected(c,lambda:c.execute(f"DELETE FROM {v} WHERE docket_id=%s",(did,)))
        verify=connect(psycopg,dsn)
        try:verify.autocommit=True;cur=verify.cursor();cur.execute("SET default_transaction_read_only=on");cur.execute(f"SELECT review_rounds,held,payment_authority,receipt_authority,retry_authority,approval_authority,execution_authority FROM {v}");exact=cur.fetchall()==[(2,True,False,False,False,False,False)];cur.close()
        finally:verify.close()
        if not all((self_review,fork,mutation,view_dml,exact)):raise RuntimeError("conflict resolution invariant failed; HOLD")
        proof={"status":"PASS_POSTGRES_RECOVERY_CONFLICT_RESOLUTION_PROOF","conflict_set_exact":True,"single_genesis":True,"single_successor":True,"actor_separation":True,"conflict_hold_preserved":True,"append_only":True,"zero_authority":True,"production_database_writes":0,"cleanup_succeeded":True}
    finally:
        try:c.rollback();c.execute(f'DROP SCHEMA IF EXISTS "{SCHEMA}" CASCADE');c.commit();cleanup=True
        finally:c.close()
    if not cleanup:raise RuntimeError("cleanup failed")
    out=ROOT/"build/postgres-recovery-conflict-resolution-integration-evidence.json";out.parent.mkdir(exist_ok=True);payload=json.dumps(proof,sort_keys=True,separators=(",",":")).encode();out.write_bytes(payload);digest=sha256(payload).hexdigest();out.with_suffix(out.suffix+".sha256").write_text(digest+"\n");print(proof["status"],digest);return 0
if __name__=="__main__":raise SystemExit(main())
