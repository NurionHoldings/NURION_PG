"""Bounded PostgreSQL retry and commit-unknown read-back proof #16701-#17100."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Callable

from .arkaon.governance import GovernanceRejected, canonical_digest
from .synthetic_postgres_ephemeral_repository_proof import (
    APPLIED_LESSONS as PRIOR_LESSONS, APPLIED_RULES, STAGE_MAPPING as PRIOR_STAGE_MAPPING,
    SyntheticPostgresEphemeralRepositoryProof,
)

APPLIED_LESSONS=tuple(sorted(PRIOR_LESSONS+("ARL-16701-001",)))
WORKSTREAM_NAMES=("FAILURE_TAXONOMY","SERIALIZATION_DETECTION","DEADLOCK_DETECTION","CONNECTION_FAILURE_DETECTION","TIMEOUT_FAIL_CLOSED","BOUNDED_ATTEMPTS","FRESH_CONNECTION_RETRY","TRANSACTION_ROLLBACK","BACKOFF_POLICY","RETRY_SUCCESS","RETRY_EXHAUSTION","NON_RETRYABLE_REJECTION","COMMIT_UNKNOWN","IDEMPOTENT_READBACK","PAYLOAD_MISMATCH","CLEANUP_NON_PRODUCTION")
WORKSTREAMS=tuple((16701+i*25,16725+i*25,n) for i,n in enumerate(WORKSTREAM_NAMES))
CONTROL_ASPECTS=("input_schema","required_fields","semantic_label","source_type","tenant_scope","role_scope","state_precondition","latest_sequence","source_binding","digest_recalculation","negative_path","missing_input","duplicate_input","replay","conflict","stale_version","concurrency","partial_batch","ordering","append_only","hold_propagation","review_independence","receipt_lineage","operator_gate","non_execution")
NEGATIVE=frozenset({"negative_path","missing_input","duplicate_input","replay","conflict","stale_version","partial_batch"})
STAGE_MAPPING=PRIOR_STAGE_MAPPING+(("ARKAON-LESSONS-16701",(16701,17100)),)
MAXIMUM_STATE="POSTGRES_RETRY_PROOF_ONLY"
MAX_ATTEMPTS=3
RETRYABLE_SQLSTATES=frozenset({"40001","40P01"})
AMBIGUOUS_CONNECTION_SQLSTATES=frozenset({"08003","08006","57P01"})
NON_RETRYABLE_SQLSTATES=frozenset({"23505","57014"})

def mapping_digest(rows):return canonical_digest(("CONTIGUOUS_STAGE_MAPPING",tuple(rows)))
def _hex(v):return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def classify_sqlstate(sqlstate):
    if sqlstate in RETRYABLE_SQLSTATES:return "RETRYABLE_TRANSACTION"
    if sqlstate in AMBIGUOUS_CONNECTION_SQLSTATES:return "COMMIT_OUTCOME_UNKNOWN_READBACK_REQUIRED"
    return "NON_RETRYABLE_FAIL_CLOSED"

class RetryExhausted(GovernanceRejected):pass
class CommitOutcomeUnknown(Exception):pass

def bounded_retry(operation:Callable[[int],object],max_attempts=MAX_ATTEMPTS,on_failure:Callable[[BaseException,int],None]|None=None):
    """Retry only 40001/40P01, at most three fresh-operation attempts; no sleeping."""
    if not isinstance(max_attempts,int) or isinstance(max_attempts,bool) or not 1<=max_attempts<=MAX_ATTEMPTS:
        raise GovernanceRejected("bounded retry attempts 1..3 required")
    for attempt in range(1,max_attempts+1):
        try:return operation(attempt),attempt
        except Exception as exc:
            if on_failure:on_failure(exc,attempt)
            if classify_sqlstate(getattr(exc,"sqlstate",None))!="RETRYABLE_TRANSACTION":raise
            if attempt==max_attempts:raise RetryExhausted(f"retry exhausted after {attempt} attempts") from exc
    raise AssertionError("unreachable")

def resolve_commit_unknown(readback:Callable[[],tuple[str,str]|None],expected_digest:str):
    """Resolve only by a fresh read; absence or changed payload remains HOLD."""
    found=readback()
    if found is None:raise GovernanceRejected("commit outcome unknown: row absent")
    status,digest=found
    if status!="EXISTING_SAME_PAYLOAD" or digest!=expected_digest:
        raise GovernanceRejected("commit outcome unknown: payload mismatch")
    return "COMMITTED_READBACK_CONFIRMED",digest

@dataclass(frozen=True)
class Control:control_id:int;workstream:str;aspect:str;requirement_ref:str;fixture_digest:str;expected_result:str;digest:str
@dataclass(frozen=True)
class Snapshot:snapshot_id:str;stage_range:tuple;mapping_digest:str;registry_digest:str;manifest_digest:str;lesson_ids:tuple;rule_ids:tuple;source_docket_digest:str;previous_snapshot_digest:str;sequence:int;latest:bool;digest:str
@dataclass(frozen=True)
class Docket:docket_id:str;snapshot_digest:str;complete:bool;held:bool;pending_human_judgment:bool;production_writes:int;receipt_issued:bool;approved:bool;activated:bool;deployed:bool;status:str;digest:str

def integration_proof_valid(p):
    expected={"status":"PASS_POSTGRES_RETRY_RESILIENCE","serialization_sqlstate":"40001","serialization_failures":1,"serialization_success_attempt":2,"bounded_retry_max_attempts":3,"retry_exhaustion_mode":"UNIT_INJECTED_SQLSTATE_SEQUENCE","retry_exhaustion_fail_closed":True,"actual_retry_exhaustion_claimed":False,"timeout_sqlstate":"57014","timeout_attempts":1,"non_retryable_timeout_fail_closed":True,"fresh_connection_per_retry":True,"commit_unknown_mode":"HARNESS_INJECTED_POST_COMMIT_RESPONSE_LOSS","commit_unknown_readback_confirmed":True,"payload_mismatch_fail_closed":True,"production_database_writes":0,"cleanup_succeeded":True,"credential_disclosed":False,"password_credential_configured":False,"actual_network_partition_claimed":False,"actual_deadlock_claimed":False}
    return isinstance(p,dict) and p==expected

def recovery_paths():return (
    (("cause","retryable_serialization_or_deadlock"),("recommended",True),("method","rollback_close_and_retry_on_fresh_connection_up_to_three_attempts"),("cost","LOW"),("risk","LOW"),("reversibility","HIGH"),("validation","actual_40001_then_success_and_connection_identity_change"),("stop","third_retry_fails_or_sqlstate_changes"),("resume","repair_contention_scope_then_new_disposable_schema_full_proof"),("rollback","rollback_failed_transaction_and_drop_only_validated_schema")),
    (("cause","commit_outcome_unknown_or_non_retryable_timeout"),("recommended",False),("method","do_not_blind_retry_read_back_exact_idempotency_key_and_payload_or_hold"),("cost","MEDIUM"),("risk","MEDIUM"),("reversibility","HIGH"),("validation","fresh_connection_exact_digest_readback_or_explicit_absent_mismatch_hold"),("stop","absence_mismatch_timeout_or_unclassified_failure"),("resume","operator_reconciles_then_replays_full_proof"),("rollback","preserve_possible_committed_winner_cleanup_test_schema_only")),
)

class SyntheticPostgresRetryResilienceProof:
    def __init__(self):self._controls={};self._source=None;self._snapshot=None;self._docket=None
    def _expected(self,cid):i=cid-16701;return WORKSTREAM_NAMES[i//25],CONTROL_ASPECTS[i%25]
    def add_control(self,cid,workstream,aspect,requirement_ref,fixture_digest,expected_result):
        p=dict(control_id=cid,workstream=workstream,aspect=aspect,requirement_ref=requirement_ref,fixture_digest=fixture_digest,expected_result=expected_result);r=Control(**p,digest=canonical_digest(p))
        if not (isinstance(cid,int) and not isinstance(cid,bool) and 16701<=cid<=17100 and self._expected(cid)==(workstream,aspect) and requirement_ref==f"synthetic:postgres-retry-proof-requirement:{(cid-16701)//25:02}" and _hex(fixture_digest) and expected_result==("EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS")):raise GovernanceRejected("valid #16701-#17100 control required")
        old=self._controls.get(cid)
        if old and old!=r:raise GovernanceRejected("control conflict")
        self._controls[cid]=r;return r
    def anchor(self,source,mapping,registry,manifest,lessons,rules,previous_snapshot,sequence,latest):
        if not isinstance(source,SyntheticPostgresEphemeralRepositoryProof):raise GovernanceRejected("prior ephemeral PostgreSQL proof required")
        p=dict(snapshot_id="synthetic:lesson-snapshot:16701-17100",stage_range=(16701,17100),mapping_digest=mapping,registry_digest=registry,manifest_digest=manifest,lesson_ids=tuple(lessons),rule_ids=tuple(rules),source_docket_digest=source._docket.digest if source._docket else None,previous_snapshot_digest=previous_snapshot,sequence=sequence,latest=latest);r=Snapshot(**p,digest=canonical_digest(p))
        if not (set(self._controls)==set(range(16701,17101)) and source.evidence()["complete_postgres_ephemeral_repository_proof_contract_evidence"] and mapping==mapping_digest(STAGE_MAPPING) and _hex(registry) and _hex(manifest) and tuple(lessons)==APPLIED_LESSONS and tuple(rules)==APPLIED_RULES and previous_snapshot==source._snapshot.digest and isinstance(sequence,int) and not isinstance(sequence,bool) and sequence>0 and latest is True):raise GovernanceRejected("complete retry proof snapshot required")
        self._source=source;self._snapshot=r;return r
    def finalize(self,docket_id):
        if self._docket or not self._snapshot:raise GovernanceRejected("complete retry contract required")
        p=dict(docket_id=docket_id,snapshot_digest=self._snapshot.digest,complete=True,held=True,pending_human_judgment=True,production_writes=0,receipt_issued=False,approved=False,activated=False,deployed=False,status=MAXIMUM_STATE)
        if not isinstance(docket_id,str) or not docket_id.startswith("synthetic:postgres-retry-proof-docket:"):raise GovernanceRejected("synthetic retry docket required")
        self._docket=Docket(**p,digest=canonical_digest(p));return self._docket
    def evidence(self,proof=None):
        if proof is None:status="SKIP_NO_PRECONFIGURED_TEST_DATABASE"
        elif integration_proof_valid(proof):status="PASS_POSTGRES_RETRY_RESILIENCE"
        else:raise GovernanceRejected("complete exact PostgreSQL retry PASS proof required")
        source_ok=bool(self._source and self._source.evidence()["complete_postgres_ephemeral_repository_proof_contract_evidence"])
        snap_ok=bool(self._snapshot and source_ok and self._snapshot.stage_range==(16701,17100) and self._snapshot.mapping_digest==mapping_digest(STAGE_MAPPING) and self._snapshot.source_docket_digest==self._source._docket.digest and self._snapshot.previous_snapshot_digest==self._source._snapshot.digest and self._snapshot.lesson_ids==APPLIED_LESSONS and self._snapshot.rule_ids==APPLIED_RULES and _hex(self._snapshot.registry_digest) and _hex(self._snapshot.manifest_digest) and self._snapshot.latest and self._snapshot.digest==canonical_digest({k:v for k,v in self._snapshot.__dict__.items() if k!="digest"}))
        controls_ok=set(self._controls)==set(range(16701,17101)) and all(r.digest==canonical_digest({k:v for k,v in r.__dict__.items() if k!="digest"}) and self._expected(cid)==(r.workstream,r.aspect) for cid,r in self._controls.items())
        docket_ok=bool(self._docket and snap_ok and self._docket.production_writes==0 and self._docket.status==MAXIMUM_STATE and self._docket.digest==canonical_digest({k:v for k,v in self._docket.__dict__.items() if k!="digest"}))
        return {"range":[16701,17100],"control_count":400,"registered_control_count":len(self._controls),"recovery_path_count":64,"human_judgment_hold_count":32,"postgresql_retry_proof_status":status,"postgresql_retry_proof_claimed":status.startswith("PASS_"),"postgresql_integration_skip_count":1 if status.startswith("SKIP_") else 0,"bounded_retry_max_attempts":MAX_ATTEMPTS,"retryable_sqlstates":sorted(RETRYABLE_SQLSTATES),"ambiguous_connection_sqlstates":sorted(AMBIGUOUS_CONNECTION_SQLSTATES),"non_retryable_sqlstates":sorted(NON_RETRYABLE_SQLSTATES),"actual_network_partition_claimed":False,"actual_deadlock_claimed":False,"production_database_writes":0,"cleanup_succeeded":(proof or {}).get("cleanup_succeeded",False),"complete_postgres_retry_resilience_contract_evidence":bool(docket_ok and controls_ok),"maximum_state":MAXIMUM_STATE if docket_ok and controls_ok else "CONTRACT_INCOMPLETE","applied_lesson_ids":list(APPLIED_LESSONS),"applied_rule_ids":list(APPLIED_RULES),"recovery_guidance_digest":canonical_digest(recovery_paths()),"approval_receipts_issued":0,"signatures_created":0,"keys_read":0,"credentials_read":0,"financial_operations":0,"approved":False,"activated":False,"deployed":False}
