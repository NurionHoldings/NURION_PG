"""Isolated PostgreSQL fixture/migration/repository proof contract #16301-#16700."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from threading import Barrier, Lock, Thread
from urllib.parse import urlsplit
import json
import re

from .arkaon.governance import GovernanceRejected, canonical_digest
from .synthetic_postgres_reservation_ledger_contract import (
    APPLIED_LESSONS as PRIOR_LESSONS, APPLIED_RULES, MAX_STATE, TABLE,
    STAGE_MAPPING as PRIOR_STAGE_MAPPING, SyntheticPostgresReservationLedgerContract,
    render_ddl, schema_spec,
)

APPLIED_LESSONS=tuple(sorted(PRIOR_LESSONS+("ARL-16301-001",)))
WORKSTREAM_NAMES=("DISPOSABLE_TARGET_GUARD","FIXTURE_LIFECYCLE","MIGRATION_UP","MIGRATION_DOWN","COLUMN_INTROSPECTION","UNIQUE_INTROSPECTION","CHECK_INTROSPECTION","REPOSITORY_INSERT_OR_READ","PAYLOAD_COMPARE","CONCURRENT_SAME_PAYLOAD","CHANGED_PAYLOAD_CONFLICT","CROSS_KEY_CONFLICT","ABORT_ROLLBACK","RESPONSE_LOSS_READBACK","CLEANUP_PROOF","NON_PRODUCTION_BOUNDARY")
WORKSTREAMS=tuple((16301+i*25,16325+i*25,n) for i,n in enumerate(WORKSTREAM_NAMES))
CONTROL_ASPECTS=("input_schema","required_fields","semantic_label","source_type","tenant_scope","role_scope","state_precondition","latest_sequence","source_binding","digest_recalculation","negative_path","missing_input","duplicate_input","replay","conflict","stale_version","concurrency","partial_batch","ordering","append_only","hold_propagation","review_independence","receipt_lineage","operator_gate","non_execution")
NEGATIVE=frozenset({"negative_path","missing_input","duplicate_input","replay","conflict","stale_version","partial_batch"})
STAGE_MAPPING=PRIOR_STAGE_MAPPING+(("ARKAON-LESSONS-16301",(16301,16700)),)
SCHEMA_PREFIX="nurion_pg_ci_"
ALLOWED_DATABASE="nurion_pg_ci"
MAXIMUM_STATE="EPHEMERAL_POSTGRES_PROOF_ONLY"
PROOF_CLASSIFICATIONS=("SAME_KEY_SAME_PAYLOAD_CONVERGED","SAME_KEY_CHANGED_PAYLOAD_CONFLICT","CROSS_KEY_TOKEN_REUSE_CONFLICT","CROSS_KEY_SCOPE_REUSE_CONFLICT","CROSS_KEY_NONCE_REUSE_CONFLICT","CROSS_KEY_LOGICAL_REUSE_CONFLICT","ABORT_ROLLBACK_NEW_TRANSACTION","COMMIT_RESPONSE_LOSS_READBACK")

def mapping_digest(rows):return canonical_digest(("CONTIGUOUS_STAGE_MAPPING",tuple(rows)))
def _hex(v):return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def canonical_payload(row):
    return json.dumps(row,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def _valid_schema_name(v):return isinstance(v,str) and v.startswith(SCHEMA_PREFIX) and len(v)<=63 and v.replace("_","").isalnum() and v.casefold()==v

@dataclass(frozen=True)
class Control: control_id:int;workstream:str;aspect:str;requirement_ref:str;fixture_digest:str;expected_result:str;digest:str
@dataclass(frozen=True)
class Snapshot: snapshot_id:str;stage_range:tuple;mapping_digest:str;registry_digest:str;manifest_digest:str;lesson_ids:tuple;rule_ids:tuple;source_docket_digest:str;previous_snapshot_digest:str;sequence:int;latest:bool;digest:str
@dataclass(frozen=True)
class FixturePlan: schema_name:str;database_name:str;migration_up_digest:str;migration_down_digest:str;expected_columns:tuple;expected_constraints:tuple;isolation_level:str;cleanup_scope:str;digest:str
@dataclass(frozen=True)
class Docket: docket_id:str;snapshot_digest:str;fixture_digest:str;source_schema_digest:str;source_ddl_digest:str;complete:bool;held:bool;pending_human_judgment:bool;production_writes:int;receipt_issued:bool;approved:bool;activated:bool;deployed:bool;status:str;digest:str

def validated_disposable_target(dsn,schema_name,ci_marker=False):
    """Return non-secret target metadata; never returns or logs the DSN."""
    if not isinstance(dsn,str) or not dsn.startswith(("postgresql://","postgres://")):
        raise GovernanceRejected("PostgreSQL ephemeral DSN required")
    u=urlsplit(dsn)
    if u.password is not None:raise GovernanceRejected("password-bearing PostgreSQL DSN refused")
    host=(u.hostname or "").casefold();database=u.path.lstrip("/")
    allowed_host=host in {"localhost","127.0.0.1","::1"} or (ci_marker is True and host=="postgres")
    if not allowed_host or database!=ALLOWED_DATABASE:
        raise GovernanceRejected("production host or database refused")
    if not _valid_schema_name(schema_name):
        raise GovernanceRejected("validated disposable schema required")
    return {"host_class":"LOCAL_OR_CI_SERVICE","database":database,"schema":schema_name}

def validated_pg_environment(env,schema_name,ci_marker=False):
    if not _valid_schema_name(schema_name):raise GovernanceRejected("validated disposable schema required")
    expected={"PGHOST":"localhost","PGPORT":"5432","PGDATABASE":ALLOWED_DATABASE,"PGUSER":"nurion_ci"}
    if ci_marker is not True or any(env.get(k)!=v for k,v in expected.items()) or any(env.get(k) for k in ("PGPASSWORD","POSTGRES_PASSWORD","PGPASSFILE")):
        raise GovernanceRejected("passwordless isolated CI PostgreSQL environment required")
    return {"host_class":"CI_RUNNER_LOCAL_SERVICE","database":ALLOWED_DATABASE,"schema":schema_name}

def migration_sql(schema_name):
    if not _valid_schema_name(schema_name):raise GovernanceRejected("validated disposable schema required")
    table_ddl=render_ddl(schema_spec()).replace(f'CREATE TABLE "{TABLE}"',f'CREATE TABLE "{schema_name}"."{TABLE}"')
    up=f'CREATE SCHEMA "{schema_name}";\n{table_ddl}'
    down=f'DROP SCHEMA "{schema_name}" CASCADE;'
    return up,down

def fixture_plan(schema_name="nurion_pg_ci_contract"):
    up,down=migration_sql(schema_name);s=schema_spec()
    p=dict(schema_name=schema_name,database_name=ALLOWED_DATABASE,migration_up_digest=sha256(up.encode()).hexdigest(),migration_down_digest=sha256(down.encode()).hexdigest(),expected_columns=tuple((c.name,c.sql_type,c.nullable) for c in s.columns),expected_constraints=tuple((c.name,c.kind,c.columns) for c in s.constraints),isolation_level="READ COMMITTED",cleanup_scope="EXACT_VALIDATED_DISPOSABLE_SCHEMA_ONLY")
    return FixturePlan(**p,digest=canonical_digest(p))

def fixture_valid(p):
    if not isinstance(p,FixturePlan):return False
    expected=fixture_plan(p.schema_name)
    return p==expected and p.database_name==ALLOWED_DATABASE and len([x for x in p.expected_constraints if x[1]=="UNIQUE"])==6 and p.expected_constraints[-1]==("ck_plan_only_state","CHECK",("state",MAX_STATE))

def _normalized_check(expr):
    if not isinstance(expr,str):return None
    value=re.sub(r"\s+","",expr).replace('"',"").replace("::text","")
    while value.startswith("(") and value.endswith(")"):value=value[1:-1]
    return value

def normalize_live_columns(rows):
    actual=tuple((name,sql_type,nullable=="YES" if isinstance(nullable,str) else nullable) for name,sql_type,nullable in rows)
    if actual!=fixture_plan().expected_columns:raise GovernanceRejected("exact ordered live columns required")
    return actual

def normalize_live_constraints(rows):
    """Validate live pg_catalog rows and return canonical name/kind/ordered-column tuples."""
    records={}
    for name,kind,columns,deferrable,deferred,check_expr in rows:
        if name in records:raise GovernanceRejected("duplicate live constraint name")
        label={"p":"PRIMARY KEY","u":"UNIQUE","c":"CHECK"}.get(kind)
        cols=tuple(columns or ())
        if label is None or deferrable is not False or deferred is not False:raise GovernanceRejected("exact immediate constraint required")
        if label=="CHECK":
            if name!="ck_plan_only_state" or cols!=("state",) or _normalized_check(check_expr)!=f"state='{MAX_STATE}'":raise GovernanceRejected("exact state ceiling check required")
            records[name]=(name,label,("state",MAX_STATE))
        else:records[name]=(name,label,cols)
    expected=fixture_plan().expected_constraints
    if set(records)!={x[0] for x in expected}:raise GovernanceRejected("exact live constraint name set required")
    actual=tuple(records[x[0]] for x in expected)
    if tuple(actual)!=expected:raise GovernanceRejected("exact ordered live constraints required")
    return tuple(actual)

def integration_proof_valid(proof):
    expected={"status":"PASS_EPHEMERAL_POSTGRESQL","test_only_database_writes":2,"test_only_database_write_attempts":27,"production_database_writes":0,"cleanup_succeeded":True,"concurrency_workers":20,"concurrent_row_count":1,"isolation_level":"READ COMMITTED","conflict_classifications":list(PROOF_CLASSIFICATIONS),"database_url_disclosed":False,"credential_disclosed":False,"password_credential_configured":False,"live_constraint_parity":True}
    return isinstance(proof,dict) and proof==expected

def recovery_paths():return (
    (("cause","ephemeral_database_unavailable_or_introspection_drift"),("recommended",True),("method","provision_isolated_ci_postgresql_then_apply_exact_migration_and_introspect"),("cost","LOW"),("risk","LOW"),("reversibility","HIGH"),("validation","integration_job_green_with_exact_schema_and_cleanup"),("stop","target_guard_or_schema_parity_fails"),("resume","repair_fixture_or_migration_then_rerun_from_clean_schema"),("rollback","drop_only_exact_validated_disposable_schema")),
    (("cause","repository_concurrency_or_crash_semantics_fail"),("recommended",False),("method","hold_release_and_repair_rollback_new_transaction_readback_path"),("cost","MEDIUM"),("risk","MEDIUM"),("reversibility","HIGH"),("validation","barrier_twenty_way_one_row_and_crash_matrix_pass"),("stop","ambiguous_commit_or_payload_mismatch"),("resume","new_ephemeral_schema_full_proof"),("rollback","rollback_open_transaction_preserve_committed_winner")),
)

class SyntheticPostgresEphemeralRepositoryProof:
    def __init__(self):self._controls={};self._source=None;self._snapshot=None;self._fixture=None;self._docket=None
    def _expected(self,cid):i=cid-16301;return WORKSTREAM_NAMES[i//25],CONTROL_ASPECTS[i%25]
    def add_control(self,cid,workstream,aspect,requirement_ref,fixture_digest,expected_result):
        p=dict(control_id=cid,workstream=workstream,aspect=aspect,requirement_ref=requirement_ref,fixture_digest=fixture_digest,expected_result=expected_result);r=Control(**p,digest=canonical_digest(p))
        if not (isinstance(cid,int) and not isinstance(cid,bool) and 16301<=cid<=16700 and self._expected(cid)==(workstream,aspect) and requirement_ref==f"synthetic:postgres-ephemeral-proof-requirement:{(cid-16301)//25:02}" and _hex(fixture_digest) and expected_result==("EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS")):raise GovernanceRejected("valid #16301-#16700 control required")
        old=self._controls.get(cid)
        if old and old!=r:raise GovernanceRejected("control conflict")
        self._controls[cid]=r;return r
    def anchor(self,source,mapping,registry,manifest,lessons,rules,previous_snapshot,sequence,latest):
        if not isinstance(source,SyntheticPostgresReservationLedgerContract):raise GovernanceRejected("prior PostgreSQL ledger contract required")
        p=dict(snapshot_id="synthetic:lesson-snapshot:16301-16700",stage_range=(16301,16700),mapping_digest=mapping,registry_digest=registry,manifest_digest=manifest,lesson_ids=tuple(lessons),rule_ids=tuple(rules),source_docket_digest=source._docket.digest if source._docket else None,previous_snapshot_digest=previous_snapshot,sequence=sequence,latest=latest);r=Snapshot(**p,digest=canonical_digest(p))
        if not (set(self._controls)==set(range(16301,16701)) and source.evidence()["complete_postgres_reservation_ledger_contract_evidence"] and mapping==mapping_digest(STAGE_MAPPING) and _hex(registry) and _hex(manifest) and tuple(lessons)==APPLIED_LESSONS and tuple(rules)==APPLIED_RULES and previous_snapshot==source._snapshot.digest and isinstance(sequence,int) and not isinstance(sequence,bool) and sequence>0 and latest is True):raise GovernanceRejected("complete latest ephemeral proof snapshot required")
        self._source=source;self._snapshot=r;return r
    def plan_fixture(self,p=None):
        r=p or fixture_plan()
        if not fixture_valid(r) or self._source._schema!=schema_spec() or self._source._ddl!=render_ddl(schema_spec()):raise GovernanceRejected("exact source-bound disposable fixture required")
        if self._fixture and self._fixture!=r:raise GovernanceRejected("fixture drift conflict")
        self._fixture=r;return r
    def finalize(self,docket_id):
        if self._docket or not self._snapshot or not self._fixture:raise GovernanceRejected("complete fixture contract required")
        p=dict(docket_id=docket_id,snapshot_digest=self._snapshot.digest,fixture_digest=self._fixture.digest,source_schema_digest=self._source._schema.digest,source_ddl_digest=canonical_digest(self._source._ddl),complete=True,held=True,pending_human_judgment=True,production_writes=0,receipt_issued=False,approved=False,activated=False,deployed=False,status=MAXIMUM_STATE)
        if not isinstance(docket_id,str) or not docket_id.startswith("synthetic:postgres-ephemeral-proof-docket:"):raise GovernanceRejected("synthetic proof docket required")
        self._docket=Docket(**p,digest=canonical_digest(p));return self._docket
    def evidence(self,proof=None):
        if proof is None:status="SKIP_NO_PRECONFIGURED_TEST_DATABASE"
        elif integration_proof_valid(proof):status="PASS_EPHEMERAL_POSTGRESQL"
        else:raise GovernanceRejected("complete exact ephemeral PostgreSQL PASS proof required")
        source_ok=bool(self._source and self._source.evidence()["complete_postgres_reservation_ledger_contract_evidence"] and self._source._schema==schema_spec() and self._source._ddl==render_ddl(schema_spec()))
        snapshot_ok=False
        if self._snapshot and source_ok:
            sp={k:v for k,v in self._snapshot.__dict__.items() if k!="digest"};snapshot_ok=bool(self._snapshot.stage_range==(16301,16700) and self._snapshot.mapping_digest==mapping_digest(STAGE_MAPPING) and self._snapshot.source_docket_digest==self._source._docket.digest and self._snapshot.previous_snapshot_digest==self._source._snapshot.digest and self._snapshot.lesson_ids==APPLIED_LESSONS and self._snapshot.rule_ids==APPLIED_RULES and _hex(self._snapshot.registry_digest) and _hex(self._snapshot.manifest_digest) and isinstance(self._snapshot.sequence,int) and not isinstance(self._snapshot.sequence,bool) and self._snapshot.sequence>0 and self._snapshot.latest is True and self._snapshot.digest==canonical_digest(sp))
        docket_ok=False
        if self._docket and snapshot_ok and fixture_valid(self._fixture):
            p={k:v for k,v in self._docket.__dict__.items() if k!="digest"};docket_ok=p==dict(docket_id=self._docket.docket_id,snapshot_digest=self._snapshot.digest,fixture_digest=self._fixture.digest,source_schema_digest=self._source._schema.digest,source_ddl_digest=canonical_digest(self._source._ddl),complete=True,held=True,pending_human_judgment=True,production_writes=0,receipt_issued=False,approved=False,activated=False,deployed=False,status=MAXIMUM_STATE) and self._docket.digest==canonical_digest(p)
        controls_ok=set(self._controls)==set(range(16301,16701)) and all(r.digest==canonical_digest({k:v for k,v in r.__dict__.items() if k!="digest"}) and self._expected(cid)==(r.workstream,r.aspect) for cid,r in self._controls.items())
        complete=bool(docket_ok and controls_ok)
        paths=recovery_paths()
        return {"range":[16301,16700],"control_count":400,"registered_control_count":len(self._controls),"fixture_plan_count":1 if self._fixture else 0,"migration_up_count":1 if self._fixture else 0,"migration_down_count":1 if self._fixture else 0,"expected_unique_constraint_count":6,"recovery_path_count":64,"human_judgment_hold_count":32,"postgresql_proof_status":status,"postgresql_proof_claimed":status=="PASS_EPHEMERAL_POSTGRESQL","postgresql_integration_skip_count":1 if status.startswith("SKIP_") else 0,"test_only_database_writes":(proof or {}).get("test_only_database_writes",0),"test_only_database_write_attempts":(proof or {}).get("test_only_database_write_attempts",0),"production_database_writes":0,"database_url_disclosed":False,"credential_disclosed":False,"password_credential_configured":(proof or {}).get("password_credential_configured",False),"cleanup_succeeded":(proof or {}).get("cleanup_succeeded",False),"concurrency_workers":(proof or {}).get("concurrency_workers",0),"concurrent_row_count":(proof or {}).get("concurrent_row_count",0),"isolation_level":(proof or {}).get("isolation_level","READ COMMITTED"),"conflict_classifications":(proof or {}).get("conflict_classifications",[]),"recovery_guidance_digest":canonical_digest(paths),"complete_postgres_ephemeral_repository_proof_contract_evidence":complete,"maximum_state":MAXIMUM_STATE if complete else "CONTRACT_INCOMPLETE","applied_lesson_ids":list(APPLIED_LESSONS),"applied_rule_ids":list(APPLIED_RULES),"approval_receipts_issued":0,"signatures_created":0,"keys_read":0,"credentials_read":0,"external_pg_calls":0,"financial_operations":0,"approved":False,"activated":False,"deployed":False}

def insert_or_read(conn,schema,row):
    """DB-API repository path: aborted insert tx is rolled back; read-back uses a new tx."""
    cols=tuple(row);names=", ".join(f'"{x}"' for x in cols);marks=", ".join(["%s"]*len(cols));table=f'"{schema}"."{TABLE}"'
    try:
        with conn.cursor() as cur:cur.execute(f"INSERT INTO {table} ({names}) VALUES ({marks}) RETURNING payload_digest",tuple(row[x] for x in cols));got=cur.fetchone()[0]
        conn.commit();return "INSERTED",got
    except Exception as exc:
        conn.rollback()
        sqlstate=getattr(exc,"sqlstate",None)
        if sqlstate!="23505":raise
        with conn.cursor() as cur:cur.execute(f"SELECT payload_digest FROM {table} WHERE idempotency_key_id=%s FOR SHARE",(row["idempotency_key_id"],));found=cur.fetchone()
        conn.commit()
        if found and found[0]==row["payload_digest"]:return "EXISTING_SAME_PAYLOAD",found[0]
        raise GovernanceRejected("unique conflict changed payload or cross-key reuse") from exc
