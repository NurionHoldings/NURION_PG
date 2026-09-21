"""Actual recovery recommendation/concurrence proof on disposable PostgreSQL."""
from hashlib import sha256
import json,os
from pathlib import Path
from nurion_pg.synthetic_postgres_ephemeral_repository_proof import validated_disposable_target,validated_pg_environment
from nurion_pg.synthetic_postgres_recovery_recommendation_concurrence_proof import EXPECTED_PROOF,RECOMMENDATION_STATE,deterministic_concurrence_id,deterministic_recommendation_id,integration_proof_valid
from scripts.run_postgres_ephemeral_repository_integration import connect
ROOT=Path(__file__).resolve().parents[1];ENV="NURION_PG_EPHEMERAL_POSTGRES_DSN";SCHEMA="nurion_pg_ci_recovery_recommendation_19501"

def rejected(connection,operation):
    try:operation();connection.commit()
    except Exception:connection.rollback();return True
    return False
def exact_insert(connection,table,fields,row,key):
    values=tuple(row[field] for field in fields)
    with connection.cursor() as cursor:
        cursor.execute(f"INSERT INTO {table} ({','.join(fields)}) VALUES ({','.join(['%s']*len(fields))}) ON CONFLICT ({key}) DO NOTHING",values)
        cursor.execute(f"SELECT {','.join(fields)} FROM {table} WHERE {key}=%s FOR SHARE",(row[key],));found=cursor.fetchall()
    if found!=[values]:connection.rollback();raise RuntimeError("recommendation evidence replay conflict; original preserved")
    connection.commit()

def main():
    dsn=os.environ.get(ENV);ci_test=os.environ.get("NURION_PG_EPHEMERAL_TEST")=="1"
    if not dsn and not ci_test:print("SKIP_NO_PRECONFIGURED_TEST_DATABASE");return 0
    if dsn:validated_disposable_target(dsn,SCHEMA,os.environ.get("CI")=="true")
    else:validated_pg_environment(os.environ,SCHEMA,os.environ.get("CI")=="true")
    try:import psycopg
    except ImportError as exc:raise RuntimeError("configured PostgreSQL proof requires psycopg") from exc
    admin=connect(psycopg,dsn);cleanup=False
    receipts=f'"{SCHEMA}"."review_receipts"';recommendations=f'"{SCHEMA}"."recovery_recommendations"';concurrences=f'"{SCHEMA}"."recommendation_concurrences"';view=f'"{SCHEMA}"."recommendation_operator_view"'
    try:
        with admin.cursor() as cursor:
            cursor.execute(f'CREATE SCHEMA "{SCHEMA}"')
            cursor.execute(f"CREATE TABLE {receipts}(receipt_id text PRIMARY KEY,receipt_digest text NOT NULL UNIQUE,reviewer_subject text NOT NULL,state text NOT NULL,UNIQUE(receipt_id,receipt_digest))")
            cursor.execute(f"""CREATE TABLE {recommendations}(recommendation_id text PRIMARY KEY,receipt_id text NOT NULL,receipt_digest text NOT NULL,recommendation_key text NOT NULL UNIQUE,author_subject text NOT NULL,action_digest text NOT NULL,risk_digest text NOT NULL,recommendation_digest text NOT NULL UNIQUE,state text NOT NULL CHECK(state='{RECOMMENDATION_STATE}'),UNIQUE(recommendation_id,recommendation_digest,author_subject),FOREIGN KEY(receipt_id,receipt_digest) REFERENCES {receipts}(receipt_id,receipt_digest))""")
            cursor.execute(f"""CREATE TABLE {concurrences}(concurrence_id text PRIMARY KEY,recommendation_id text NOT NULL,recommendation_digest text NOT NULL,author_subject text NOT NULL,reviewer_subject text NOT NULL,verdict text NOT NULL CHECK(verdict IN ('CONCUR_NON_EXECUTABLE','HOLD_CONFLICT')),rationale_digest text NOT NULL,concurrence_digest text NOT NULL UNIQUE,state text NOT NULL CHECK(state='{RECOMMENDATION_STATE}'),UNIQUE(recommendation_id,reviewer_subject),CHECK(author_subject<>reviewer_subject),FOREIGN KEY(recommendation_id,recommendation_digest,author_subject) REFERENCES {recommendations}(recommendation_id,recommendation_digest,author_subject))""")
            cursor.execute(f"""CREATE FUNCTION "{SCHEMA}".reject_recommendation_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'append-only recommendation evidence'; END $$""")
            for name,table in (("receipt_immutable",receipts),("recommendation_append_only",recommendations),("concurrence_append_only",concurrences)):cursor.execute(f'CREATE TRIGGER {name} BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION "{SCHEMA}".reject_recommendation_mutation()')
            cursor.execute(f"""CREATE VIEW {view} AS SELECT r.recommendation_id,r.receipt_id,r.author_subject,r.action_digest,r.risk_digest,r.state,count(c.concurrence_id) AS review_count,bool_or(c.verdict='HOLD_CONFLICT') AS conflict_hold,false AS payment_authority,false AS receipt_authority,false AS retry_authority,false AS approval_authority,false AS execution_authority FROM {recommendations} r LEFT JOIN {concurrences} c USING(recommendation_id,recommendation_digest,author_subject) GROUP BY r.recommendation_id,r.receipt_id,r.author_subject,r.action_digest,r.risk_digest,r.state""")
        admin.commit()
        receipt_id="rrr_19501";receipt_digest=sha256(b"receipt").hexdigest();admin.execute(f"INSERT INTO {receipts} VALUES(%s,%s,%s,'REVIEW_RECORDED_NON_EXECUTABLE')",(receipt_id,receipt_digest,"reviewer:source"));admin.commit()
        action=sha256(b"action").hexdigest();risk=sha256(b"risk").hexdigest();author="author:independent";rid=deterministic_recommendation_id(receipt_id,receipt_digest,"recommendation-key",author,action,risk);rd=sha256((rid+action+risk).encode()).hexdigest()
        recommendation=dict(recommendation_id=rid,receipt_id=receipt_id,receipt_digest=receipt_digest,recommendation_key="recommendation-key",author_subject=author,action_digest=action,risk_digest=risk,recommendation_digest=rd,state=RECOMMENDATION_STATE);rf=tuple(recommendation);exact_insert(admin,recommendations,rf,recommendation,"recommendation_id");exact_insert(admin,recommendations,rf,recommendation,"recommendation_id")
        rationale1=sha256(b"concur").hexdigest();cid1=deterministic_concurrence_id(rid,rd,"reviewer:one","CONCUR_NON_EXECUTABLE",rationale1);cd1=sha256((cid1+rationale1).encode()).hexdigest();c1=dict(concurrence_id=cid1,recommendation_id=rid,recommendation_digest=rd,author_subject=author,reviewer_subject="reviewer:one",verdict="CONCUR_NON_EXECUTABLE",rationale_digest=rationale1,concurrence_digest=cd1,state=RECOMMENDATION_STATE);cf=tuple(c1);exact_insert(admin,concurrences,cf,c1,"concurrence_id");exact_insert(admin,concurrences,cf,c1,"concurrence_id")
        rationale2=sha256(b"hold").hexdigest();cid2=deterministic_concurrence_id(rid,rd,"reviewer:two","HOLD_CONFLICT",rationale2);c2=dict(c1,concurrence_id=cid2,reviewer_subject="reviewer:two",verdict="HOLD_CONFLICT",rationale_digest=rationale2,concurrence_digest=sha256((cid2+rationale2).encode()).hexdigest());exact_insert(admin,concurrences,cf,c2,"concurrence_id")
        changed=dict(recommendation,action_digest=sha256(b"changed").hexdigest());changed_rejected=rejected(admin,lambda:exact_insert(admin,recommendations,rf,changed,"recommendation_id"))
        cross=dict(recommendation,recommendation_id=deterministic_recommendation_id("other",receipt_digest,"cross",author,action,risk),receipt_id="other",recommendation_key="cross");cross["recommendation_digest"]=sha256(cross["recommendation_id"].encode()).hexdigest();cross_rejected=rejected(admin,lambda:exact_insert(admin,recommendations,rf,cross,"recommendation_id"))
        same_reviewer=dict(c1,concurrence_id=deterministic_concurrence_id(rid,rd,"reviewer:one","HOLD_CONFLICT",rationale2),verdict="HOLD_CONFLICT",rationale_digest=rationale2);same_reviewer["concurrence_digest"]=sha256(same_reviewer["concurrence_id"].encode()).hexdigest();single_reviewer=rejected(admin,lambda:exact_insert(admin,concurrences,cf,same_reviewer,"concurrence_id"))
        self_review=dict(c1,concurrence_id=deterministic_concurrence_id(rid,rd,author,"CONCUR_NON_EXECUTABLE",rationale1),reviewer_subject=author);self_review["concurrence_digest"]=sha256(self_review["concurrence_id"].encode()).hexdigest();separation=rejected(admin,lambda:exact_insert(admin,concurrences,cf,self_review,"concurrence_id"))
        rec_update=rejected(admin,lambda:admin.execute(f"UPDATE {recommendations} SET action_digest=%s WHERE recommendation_id=%s",(sha256(b"mutate").hexdigest(),rid)));rec_delete=rejected(admin,lambda:admin.execute(f"DELETE FROM {recommendations} WHERE recommendation_id=%s",(rid,)));con_update=rejected(admin,lambda:admin.execute(f"UPDATE {concurrences} SET verdict='HOLD_CONFLICT' WHERE concurrence_id=%s",(cid1,)));con_delete=rejected(admin,lambda:admin.execute(f"DELETE FROM {concurrences} WHERE concurrence_id=%s",(cid1,)))
        view_insert=rejected(admin,lambda:admin.execute(f"INSERT INTO {view}(recommendation_id) VALUES('forbidden')"));view_update=rejected(admin,lambda:admin.execute(f"UPDATE {view} SET author_subject='other' WHERE recommendation_id=%s",(rid,)));view_delete=rejected(admin,lambda:admin.execute(f"DELETE FROM {view} WHERE recommendation_id=%s",(rid,)))
        verify=connect(psycopg,dsn)
        try:
            verify.autocommit=True
            with verify.cursor() as cursor:cursor.execute("SET default_transaction_read_only=on");cursor.execute(f"SELECT recommendation_id,review_count,conflict_hold,payment_authority,receipt_authority,retry_authority,approval_authority,execution_authority FROM {view}");rows=cursor.fetchall()
        finally:verify.close()
        exact=rows==[(rid,2,True,False,False,False,False,False)]
        if not all((exact,changed_rejected,cross_rejected,single_reviewer,separation,rec_update,rec_delete,con_update,con_delete,view_insert,view_update,view_delete)):raise RuntimeError("recovery recommendation concurrence invariant failed; proof HOLD")
        proof=dict(EXPECTED_PROOF)
    finally:
        try:admin.rollback();admin.execute(f'DROP SCHEMA IF EXISTS "{SCHEMA}" CASCADE');admin.commit();cleanup=True
        finally:admin.close()
    proof["cleanup_succeeded"]=cleanup
    if not integration_proof_valid(proof):raise RuntimeError("PostgreSQL recommendation concurrence validation or cleanup failed")
    out=ROOT/"build/postgres-recovery-recommendation-concurrence-integration-evidence.json";out.parent.mkdir(exist_ok=True);payload=json.dumps(proof,sort_keys=True,separators=(",",":")).encode();out.write_bytes(payload);digest=sha256(payload).hexdigest();out.with_suffix(out.suffix+".sha256").write_text(digest+"\n",encoding="utf-8");print("PASS_POSTGRES_RECOVERY_RECOMMENDATION_CONCURRENCE_PROOF",digest);return 0
if __name__=="__main__":raise SystemExit(main())
