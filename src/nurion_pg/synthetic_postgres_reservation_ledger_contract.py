"""PostgreSQL non-writing reservation-ledger schema/transaction contract #15901-#16300."""
from dataclasses import dataclass
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest
from .synthetic_nonissuance_result_seal_reservation import (
    APPLIED_LESSONS as PRIOR_LESSONS, APPLIED_RULES, REQUIRED_POLICY_VERSION,
    STAGE_MAPPING as PRIOR_STAGE_MAPPING, SyntheticNonissuanceResultSealReservation,
)

APPLIED_LESSONS=tuple(sorted(PRIOR_LESSONS+("ARL-15901-001",)))
WORKSTREAM_NAMES=("SCHEMA_AST","IDENTIFIER_QUOTING","APPEND_ONLY_ROW","RESERVATION_UNIQUE","IDEMPOTENCY_UNIQUE","TOKEN_UNIQUE","LOGICAL_UNIQUE","SCOPE_UNIQUE","NONCE_UNIQUE","SOURCE_BINDINGS","POLICY_WINDOW","SEQUENCE_PREDECESSOR","ACTOR_NORMALIZATION","TRANSACTION_PLAN","CRASH_RECOVERY","NON_WRITING_BOUNDARY")
WORKSTREAMS=tuple((15901+i*25,15925+i*25,n) for i,n in enumerate(WORKSTREAM_NAMES))
CONTROL_ASPECTS=("input_schema","required_fields","semantic_label","source_type","tenant_scope","role_scope","state_precondition","latest_sequence","source_binding","digest_recalculation","negative_path","missing_input","duplicate_input","replay","conflict","stale_version","concurrency","partial_batch","ordering","append_only","hold_propagation","review_independence","receipt_lineage","operator_gate","non_execution")
NEGATIVE=frozenset({"negative_path","missing_input","duplicate_input","replay","conflict","stale_version","partial_batch"})
STAGE_MAPPING=PRIOR_STAGE_MAPPING+(("ARKAON-LESSONS-15901",(15901,16300)),)
TABLE="nurion_nonissuance_reservation_ledger_plan"
MAX_STATE="PERSISTENCE_PLAN_ONLY_NOT_WRITTEN"

def _hex(v):return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _syn(v,k):return isinstance(v,str) and v.startswith(f"synthetic:{k}:")
def _id(v):return v.rsplit(":",1)[-1].casefold()
def mapping_digest(rows):return canonical_digest(("CONTIGUOUS_STAGE_MAPPING",tuple(rows)))
def _schema_payload(table,columns,constraints,append_only,update_allowed,delete_allowed,state_ceiling):
    return (table,tuple((x.name,x.sql_type,x.nullable) for x in columns),tuple((x.name,x.kind,x.columns) for x in constraints),append_only,update_allowed,delete_allowed,state_ceiling)
def schema_digest(s):return canonical_digest(_schema_payload(s.table,s.columns,s.constraints,s.append_only,s.update_allowed,s.delete_allowed,s.state_ceiling))

@dataclass(frozen=True)
class Control: control_id:int;workstream:str;aspect:str;requirement_ref:str;fixture_digest:str;expected_result:str;digest:str
@dataclass(frozen=True)
class Column: name:str;sql_type:str;nullable:bool
@dataclass(frozen=True)
class Constraint: name:str;kind:str;columns:tuple
@dataclass(frozen=True)
class Schema:
    table:str;columns:tuple;constraints:tuple;append_only:bool;update_allowed:bool;delete_allowed:bool;state_ceiling:str;digest:str
@dataclass(frozen=True)
class Snapshot: snapshot_id:str;stage_range:tuple;mapping_digest:str;registry_digest:str;manifest_digest:str;lesson_ids:tuple;rule_ids:tuple;source_docket_digest:str;previous_snapshot_digest:str;sequence:int;latest:bool;digest:str
@dataclass(frozen=True)
class LedgerRowPlan:
    row_id:str;reservation_id:str;idempotency_key_id:str;reservation_token_id:str;flow:str;kind:str;intent_kind:str;source_reservation_digest:str;source_packet_digest:str;source_packet_scope_digest:str;source_idempotency_scope_digest:str;source_intent_digest:str;composite_identity_digest:str;issuer_signature_input_digest:str;verifier_signature_input_digest:str;result_candidate_digest:str;seal_input_digest:str;policy_version:str;observed_epoch:int;expires_at_epoch:int;sequence:int;predecessor_row_digest:str|None;reservation_scope_digest:str;nonce_scope_digest:str;owner_actor_normalized:str;validator_actor_normalized:str;payload_digest:str;state:str;written:bool;committed:bool;receipt_issued:bool;recovery_paths:tuple;position:int;digest:str
@dataclass(frozen=True)
class TransactionPlan:
    isolation:str;steps:tuple;conflict_targets:tuple;unique_violation_action:str;same_payload_action:str;changed_payload_action:str;crash_before_commit:str;crash_after_commit_response_loss:str;authority_boundary:str;digest:str
@dataclass(frozen=True)
class Docket: docket_id:str;snapshot_digest:str;schema_digest:str;ddl_digest:str;row_set_digest:str;transaction_digest:str;compiler:str;final_validator:str;complete:bool;held:bool;pending_human_judgment:bool;written:bool;committed:bool;receipt_issued:bool;approved:bool;activated:bool;deployed:bool;status:str;digest:str

def schema_spec():
    names=("row_id","reservation_id","idempotency_key_id","reservation_token_id","flow","kind","intent_kind","source_reservation_digest","source_packet_digest","source_packet_scope_digest","source_idempotency_scope_digest","source_intent_digest","composite_identity_digest","issuer_signature_input_digest","verifier_signature_input_digest","result_candidate_digest","seal_input_digest","policy_version","observed_epoch","expires_at_epoch","sequence","predecessor_row_digest","reservation_scope_digest","nonce_scope_digest","owner_actor_normalized","validator_actor_normalized","payload_digest","state")
    columns=tuple(Column(n,"bigint" if n in {"observed_epoch","expires_at_epoch","sequence"} else "text",n=="predecessor_row_digest") for n in names)
    unique=(("uq_reservation_id",("reservation_id",)),("uq_idempotency_key_id",("idempotency_key_id",)),("uq_reservation_token_id",("reservation_token_id",)),("uq_logical_intent",("flow","kind","intent_kind")),("uq_reservation_scope_digest",("reservation_scope_digest",)),("uq_nonce_scope_digest",("nonce_scope_digest",)))
    constraints=(Constraint("pk_reservation_ledger_plan","PRIMARY KEY",("row_id",)),)+tuple(Constraint(n,"UNIQUE",c) for n,c in unique)+(Constraint("ck_plan_only_state","CHECK",("state",MAX_STATE)),)
    p=dict(table=TABLE,columns=columns,constraints=constraints,append_only=True,update_allowed=False,delete_allowed=False,state_ceiling=MAX_STATE)
    return Schema(**p,digest=canonical_digest(_schema_payload(**p)))

def quote_ident(v):
    if not isinstance(v,str) or not v or any(not(c.islower() or c.isdigit() or c=="_") for c in v) or v[0].isdigit():raise GovernanceRejected("canonical SQL identifier required")
    return '"'+v+'"'

def render_ddl(schema):
    if not schema_valid(schema):raise GovernanceRejected("canonical schema required")
    parts=[f"{quote_ident(c.name)} {c.sql_type}"+("" if c.nullable else " NOT NULL") for c in schema.columns]
    for c in schema.constraints:
        if c.kind=="CHECK":body=f'{quote_ident(c.columns[0])} = \'{c.columns[1]}\''
        else:body=", ".join(quote_ident(x) for x in c.columns)
        parts.append(f"CONSTRAINT {quote_ident(c.name)} {c.kind} ({body})")
    return f"CREATE TABLE {quote_ident(schema.table)} (\n  "+",\n  ".join(parts)+"\n);"

def schema_valid(s):
    if not isinstance(s,Schema):return False
    names=("row_id","reservation_id","idempotency_key_id","reservation_token_id","flow","kind","intent_kind","source_reservation_digest","source_packet_digest","source_packet_scope_digest","source_idempotency_scope_digest","source_intent_digest","composite_identity_digest","issuer_signature_input_digest","verifier_signature_input_digest","result_candidate_digest","seal_input_digest","policy_version","observed_epoch","expires_at_epoch","sequence","predecessor_row_digest","reservation_scope_digest","nonce_scope_digest","owner_actor_normalized","validator_actor_normalized","payload_digest","state")
    expected_columns=tuple((n,"bigint" if n in {"observed_epoch","expires_at_epoch","sequence"} else "text",n=="predecessor_row_digest") for n in names)
    expected_constraints=(("pk_reservation_ledger_plan","PRIMARY KEY",("row_id",)),("uq_reservation_id","UNIQUE",("reservation_id",)),("uq_idempotency_key_id","UNIQUE",("idempotency_key_id",)),("uq_reservation_token_id","UNIQUE",("reservation_token_id",)),("uq_logical_intent","UNIQUE",("flow","kind","intent_kind")),("uq_reservation_scope_digest","UNIQUE",("reservation_scope_digest",)),("uq_nonce_scope_digest","UNIQUE",("nonce_scope_digest",)),("ck_plan_only_state","CHECK",("state",MAX_STATE)))
    actual_columns=tuple((c.name,c.sql_type,c.nullable) for c in s.columns);actual_constraints=tuple((c.name,c.kind,c.columns) for c in s.constraints)
    return s.table==TABLE and actual_columns==expected_columns and actual_constraints==expected_constraints and s.append_only and not s.update_allowed and not s.delete_allowed and s.state_ceiling==MAX_STATE and s.digest==schema_digest(s)

def recovery_paths(row,payload):return (
    (("cause","unique_violation_or_payload_mismatch"),("recommended",True),("method","read_locked_winner_compare_exact_payload_then_return_or_conflict"),("cost","LOW"),("risk","LOW"),("reversibility","HIGH"),("validation","same_payload_converges_changed_payload_conflicts"),("stop","binding_policy_window_or_actor_invalid"),("resume","retry_same_key_same_payload_or_new_key_for_new_operation"),("rollback","rollback_uncommitted_transaction_preserve_source"),row,payload),
    (("cause","crash_boundary_or_response_loss"),("recommended",False),("method","before_commit_retry_after_rollback_after_commit_read_back_by_key"),("cost","MEDIUM"),("risk","LOW"),("reversibility","HIGH"),("validation","crash_matrix_and_read_back_convergence"),("stop","commit_outcome_cannot_be_proven"),("resume","authoritative_read_back_under_same_conflict_target"),("rollback","never_delete_committed_append_only_row"),row,payload))

def expected_transaction_payload():return dict(
    isolation="READ COMMITTED WITH UNIQUE-CONSTRAINT ARBITRATION AND LOCKED READ-BACK",
    steps=("BEGIN","INSERT_OR_READ_ON_UNIQUE_VIOLATION","LOCK_WINNER_FOR_SHARE","COMPARE_CANONICAL_PAYLOAD_DIGEST","APPEND_EVIDENCE_PLAN","COMMIT"),
    conflict_targets=("reservation_id","idempotency_key_id","reservation_token_id","flow,kind,intent_kind","reservation_scope_digest","nonce_scope_digest"),
    unique_violation_action="ON_UNIQUE_VIOLATION_ROLLBACK_WHOLE_TRANSACTION_BEGIN_NEW_TRANSACTION_THEN_LOCK_AND_READ_WINNER",
    same_payload_action="RETURN_SINGLE_EXISTING_ROW",changed_payload_action="FAIL_CLOSED_CONFLICT",
    crash_before_commit="ROLLBACK_AND_RETRY_SAME_KEY_SAME_PAYLOAD",
    crash_after_commit_response_loss="READ_BACK_BY_IDEMPOTENCY_KEY_AND_COMPARE_PAYLOAD",
    authority_boundary="PLAN_ONLY_NO_DATABASE_WRITE_NO_RECEIPT_AUTHORITY")

def transaction_valid(tx):
    if not isinstance(tx,TransactionPlan):return False
    p={k:v for k,v in tx.__dict__.items() if k!="digest"}
    return p==expected_transaction_payload() and tx.digest==canonical_digest(p)

class SyntheticPostgresReservationLedgerContract:
    def __init__(self):self._controls={};self._source=None;self._snapshot=None;self._schema=None;self._ddl=None;self._rows={};self._ids={};self._keys={};self._tokens={};self._scopes={};self._nonces={};self._tx=None;self._docket=None;self._lock=RLock()
    def _expected(self,cid):i=cid-15901;return WORKSTREAM_NAMES[i//25],CONTROL_ASPECTS[i%25]
    def add_control(self,cid,workstream,aspect,requirement_ref,fixture_digest,expected_result):
        p=dict(control_id=cid,workstream=workstream,aspect=aspect,requirement_ref=requirement_ref,fixture_digest=fixture_digest,expected_result=expected_result);r=Control(**p,digest=canonical_digest(p))
        with self._lock:
            if not self._control_valid(r):raise GovernanceRejected("valid #15901-#16300 control required")
            if cid in self._controls:
                if self._controls[cid]==r:return r
                raise GovernanceRejected("control conflict")
            self._controls[cid]=r;return r
    def anchor(self,source,mapping,registry,manifest,lessons,rules,previous_snapshot,sequence,latest):
        if not isinstance(source,SyntheticNonissuanceResultSealReservation):raise GovernanceRejected("prior reservation contract required")
        p=dict(snapshot_id="synthetic:lesson-snapshot:15901-16300",stage_range=(15901,16300),mapping_digest=mapping,registry_digest=registry,manifest_digest=manifest,lesson_ids=tuple(lessons),rule_ids=tuple(rules),source_docket_digest=source._docket.digest if source._docket else None,previous_snapshot_digest=previous_snapshot,sequence=sequence,latest=latest);r=Snapshot(**p,digest=canonical_digest(p))
        if not(self._registry_valid() and source.evidence()["complete_nonissuance_result_seal_reservation_evidence"] and mapping==mapping_digest(STAGE_MAPPING) and _hex(registry) and _hex(manifest) and tuple(lessons)==APPLIED_LESSONS and tuple(rules)==APPLIED_RULES and previous_snapshot==source._snapshot.digest and isinstance(sequence,int) and not isinstance(sequence,bool) and sequence>0 and latest is True):raise GovernanceRejected("complete latest ledger snapshot required")
        self._source=source;self._snapshot=r;return r
    def define_schema(self,schema=None):
        r=schema or schema_spec()
        if not schema_valid(r):raise GovernanceRejected("canonical schema AST required")
        ddl=render_ddl(r)
        if self._schema:
            if self._schema==r:return r
            raise GovernanceRejected("schema drift conflict")
        self._schema=r;self._ddl=ddl;return r
    def plan_row(self,row_id,flow,kind,intent_kind):
        with self._lock:
            key=(flow,kind,intent_kind);src=self._source._reservations.get(key) if self._source else None;old=self._rows.get(key)
            if not src or not self._schema:raise GovernanceRejected("source reservation and schema required")
            position=list(self._source._reservations).index(key)+1;pred=None if position==1 else next((x.digest for x in self._rows.values() if x.position==position-1),None)
            if position>1 and pred is None:raise GovernanceRejected("ordered ledger predecessor required")
            if not _syn(row_id,"postgres-ledger-row-plan"):raise GovernanceRejected("synthetic row plan id required")
            owner=_id(src.owner_actor);validator=_id(src.validator_actor)
            payload=canonical_digest(("POSTGRES_LEDGER_PAYLOAD_V1",src.digest,src.source_packet_digest,src.source_packet_scope_digest,src.source_idempotency_scope_digest,src.source_intent_digest,src.composite_identity_digest,src.issuer_signature_input_digest,src.verifier_signature_input_digest,src.result_candidate_digest,src.seal_input_digest,src.policy_version,src.observed_epoch,src.expires_at_epoch,position,pred,src.reservation_scope_digest,src.nonce_scope_digest,owner,validator,MAX_STATE))
            paths=recovery_paths(row_id,payload) if src.recovery_paths else ()
            vals=(row_id,src.reservation_id,src.idempotency_key_id,src.reservation_token_id,flow,kind,intent_kind,src.digest,src.source_packet_digest,src.source_packet_scope_digest,src.source_idempotency_scope_digest,src.source_intent_digest,src.composite_identity_digest,src.issuer_signature_input_digest,src.verifier_signature_input_digest,src.result_candidate_digest,src.seal_input_digest,src.policy_version,src.observed_epoch,src.expires_at_epoch,position,pred,src.reservation_scope_digest,src.nonce_scope_digest,owner,validator,payload,MAX_STATE,False,False,False,paths,position);r=LedgerRowPlan(*vals,canonical_digest(("POSTGRES_LEDGER_ROW_PLAN_V1",vals)))
            if old:
                if old==r:return old
                raise GovernanceRejected("logical row payload conflict")
            collisions=((self._ids,row_id),(self._keys,src.idempotency_key_id),(self._tokens,src.reservation_token_id),(self._scopes,src.reservation_scope_digest),(self._nonces,src.nonce_scope_digest))
            for index,value in collisions:
                if value in index:
                    if index[value]==r:return index[value]
                    raise GovernanceRejected("unique conflict changed payload or cross-key reuse")
            if not self._row_valid(r,key):raise GovernanceRejected("valid ledger row plan required")
            self._rows[key]=r
            for index,value in collisions:index[value]=r
            return r
    def define_transaction(self):
        p=expected_transaction_payload();self._tx=TransactionPlan(**p,digest=canonical_digest(p));return self._tx
    def finalize(self,docket_id,compiler,final_validator):
        if self._docket or tuple(self._rows)!=tuple(self._source._reservations) or not self._integrity() or not self._tx:raise GovernanceRejected("complete intact ledger plan required")
        roles=tuple(y for x in self._rows.values() for y in (x.owner_actor_normalized,x.validator_actor_normalized))+(_id(compiler),_id(final_validator))
        if not _syn(docket_id,"postgres-ledger-plan-docket") or not _syn(compiler,"ledger-plan-compiler") or not _syn(final_validator,"ledger-plan-validator") or len(set(roles))!=len(roles):raise GovernanceRejected("independent ledger plan roles required")
        p=dict(docket_id=docket_id,snapshot_digest=self._snapshot.digest,schema_digest=self._schema.digest,ddl_digest=canonical_digest(self._ddl),row_set_digest=canonical_digest(tuple(x.digest for x in self._rows.values())),transaction_digest=self._tx.digest,compiler=compiler,final_validator=final_validator,complete=True,held=True,pending_human_judgment=True,written=False,committed=False,receipt_issued=False,approved=False,activated=False,deployed=False,status=MAX_STATE);self._docket=Docket(**p,digest=canonical_digest(p));return self._docket
    def _control_valid(self,r):p={k:v for k,v in r.__dict__.items() if k!="digest"};return isinstance(r.control_id,int) and not isinstance(r.control_id,bool) and 15901<=r.control_id<=16300 and self._expected(r.control_id)==(r.workstream,r.aspect) and r.requirement_ref==f"synthetic:postgres-ledger-requirement:{(r.control_id-15901)//25:02}" and _hex(r.fixture_digest) and r.expected_result==("EXPECTED_REJECTION" if r.aspect in NEGATIVE else "PASS") and r.digest==canonical_digest(p)
    def _registry_valid(self):return set(self._controls)==set(range(15901,16301)) and all(self._control_valid(x) for x in self._controls.values())
    def _row_valid(self,r,key):
        src=self._source._reservations.get(key);position=list(self._source._reservations).index(key)+1 if src else -1;pred=None if position==1 else next((x.digest for x in self._rows.values() if x.position==position-1),None)
        if not src or src.policy_version!=REQUIRED_POLICY_VERSION or not src.observed_epoch<=src.expires_at_epoch or _id(src.owner_actor)==_id(src.validator_actor):return False
        payload=canonical_digest(("POSTGRES_LEDGER_PAYLOAD_V1",src.digest,src.source_packet_digest,src.source_packet_scope_digest,src.source_idempotency_scope_digest,src.source_intent_digest,src.composite_identity_digest,src.issuer_signature_input_digest,src.verifier_signature_input_digest,src.result_candidate_digest,src.seal_input_digest,src.policy_version,src.observed_epoch,src.expires_at_epoch,position,pred,src.reservation_scope_digest,src.nonce_scope_digest,_id(src.owner_actor),_id(src.validator_actor),MAX_STATE));paths=recovery_paths(r.row_id,payload) if src.recovery_paths else ();vals=(r.row_id,src.reservation_id,src.idempotency_key_id,src.reservation_token_id,*key,src.digest,src.source_packet_digest,src.source_packet_scope_digest,src.source_idempotency_scope_digest,src.source_intent_digest,src.composite_identity_digest,src.issuer_signature_input_digest,src.verifier_signature_input_digest,src.result_candidate_digest,src.seal_input_digest,src.policy_version,src.observed_epoch,src.expires_at_epoch,position,pred,src.reservation_scope_digest,src.nonce_scope_digest,_id(src.owner_actor),_id(src.validator_actor),payload,MAX_STATE,False,False,False,paths,position)
        return tuple(getattr(r,k) for k in LedgerRowPlan.__dataclass_fields__ if k!="digest")==vals and r.digest==canonical_digest(("POSTGRES_LEDGER_ROW_PLAN_V1",vals))
    def _docket_valid(self,d):
        if not isinstance(d,Docket) or not self._snapshot or not self._schema or not self._tx:return False
        rows=tuple(self._rows.values());roles=tuple(y for x in rows for y in (x.owner_actor_normalized,x.validator_actor_normalized))+(_id(d.compiler),_id(d.final_validator));p={k:v for k,v in d.__dict__.items() if k!="digest"}
        return _syn(d.docket_id,"postgres-ledger-plan-docket") and _syn(d.compiler,"ledger-plan-compiler") and _syn(d.final_validator,"ledger-plan-validator") and len(set(roles))==len(roles) and d.snapshot_digest==self._snapshot.digest and d.schema_digest==self._schema.digest and d.ddl_digest==canonical_digest(self._ddl) and d.row_set_digest==canonical_digest(tuple(x.digest for x in rows)) and d.transaction_digest==self._tx.digest and (d.complete,d.held,d.pending_human_judgment,d.written,d.committed,d.receipt_issued,d.approved,d.activated,d.deployed,d.status)==(True,True,True,False,False,False,False,False,False,MAX_STATE) and d.digest==canonical_digest(p)
    def _integrity(self):
        if not(self._registry_valid() and self._source and self._source.evidence()["integrity_valid"] and self._snapshot and self._schema and schema_valid(self._schema) and self._ddl==render_ddl(self._schema)):return False
        s=self._snapshot;p={k:v for k,v in s.__dict__.items() if k!="digest"}
        if not(s.snapshot_id=="synthetic:lesson-snapshot:15901-16300" and s.stage_range==(15901,16300) and s.mapping_digest==mapping_digest(STAGE_MAPPING) and _hex(s.registry_digest) and _hex(s.manifest_digest) and s.lesson_ids==APPLIED_LESSONS and s.rule_ids==APPLIED_RULES and s.source_docket_digest==self._source._docket.digest and s.previous_snapshot_digest==self._source._snapshot.digest and isinstance(s.sequence,int) and not isinstance(s.sequence,bool) and s.sequence>0 and s.latest is True and s.digest==canonical_digest(p)):return False
        rows=tuple(self._rows.values());fields=("row_id","reservation_id","idempotency_key_id","reservation_token_id","reservation_scope_digest","nonce_scope_digest")
        if any(len({getattr(x,f) for x in rows})!=len(rows) for f in fields) or any(not self._row_valid(v,k) for k,v in self._rows.items()):return False
        if self._tx and not transaction_valid(self._tx):return False
        if not self._docket:return True
        return self._docket_valid(self._docket)
    def evidence(self):
        ok=self._integrity();complete=ok and self._docket is not None and len(self._rows)==40;zero={k:0 for k in ("database_connections","database_url_reads","credential_reads","database_writes","ledger_writes","reservation_commits","approval_receipts_issued","external_calls","external_pg_calls","card_network_calls","payment_approvals","cancellations","refunds","settlements","transfers","deployments")};return {"range":[15901,16300],"control_count":400,"registered_control_count":len(self._controls),"schema_ast_count":1 if self._schema else 0,"ddl_plan_count":1 if self._ddl else 0,"row_plan_count":len(self._rows),"transaction_plan_count":1 if self._tx else 0,"recovery_path_count":sum(len(x.recovery_paths) for x in self._rows.values()),"human_judgment_hold_count":sum(bool(x.recovery_paths) for x in self._rows.values()),"postgresql_proof_status":"SKIP_NO_PRECONFIGURED_TEST_DATABASE","postgresql_proof_claimed":False,"sqlite_used_as_postgresql_proof":False,"snapshot_digest":self._snapshot.digest if self._snapshot else None,"final_docket_digest":self._docket.digest if complete else None,"integrity_valid":ok,"complete_postgres_reservation_ledger_contract_evidence":complete,"maximum_state":MAX_STATE if self._docket else "PLAN_INCOMPLETE","applied_lesson_ids":list(APPLIED_LESSONS),"applied_rule_ids":list(APPLIED_RULES),"judgment_authority":False,"recommendation_authority":False,"selection_authority":False,"acceptance_authority":False,"resolution_authority":False,"approved":False,"activated":False,**zero}
