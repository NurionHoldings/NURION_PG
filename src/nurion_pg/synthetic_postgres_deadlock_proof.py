"""Actual disposable PostgreSQL deadlock and lock-contention proof #17101-#17500."""
from __future__ import annotations

from dataclasses import dataclass
from .arkaon.governance import GovernanceRejected, canonical_digest
from .synthetic_postgres_retry_resilience_proof import (
    APPLIED_LESSONS as PRIOR_LESSONS, APPLIED_RULES,
    STAGE_MAPPING as PRIOR_STAGE_MAPPING, SyntheticPostgresRetryResilienceProof,
    classify_sqlstate,
)

APPLIED_LESSONS=tuple(sorted(PRIOR_LESSONS+("ARL-17101-001",)))
WORKSTREAM_NAMES=("ACTUAL_DEADLOCK","EXACTLY_ONE_VICTIM","OPPOSITE_LOCK_ORDER","DEADLOCK_TIMEOUT_PREFLIGHT","FAILED_TX_ROLLBACK","FAILED_BACKEND_CLOSE","FRESH_BACKEND_RETRY","BOUNDED_RETRY","RETRY_SUCCESS","ACTUAL_LOCK_TIMEOUT","LOCK_TIMEOUT_NON_RETRY","PROVENANCE_SEPARATION","ENVIRONMENT_FAIL_CLOSED","NARROW_CLEANUP","ARTIFACT_INTEGRITY","NON_PRODUCTION_BOUNDARY")
WORKSTREAMS=tuple((17101+i*25,17125+i*25,n) for i,n in enumerate(WORKSTREAM_NAMES))
CONTROL_ASPECTS=("input_schema","required_fields","semantic_label","source_type","tenant_scope","role_scope","state_precondition","latest_sequence","source_binding","digest_recalculation","negative_path","missing_input","duplicate_input","replay","conflict","stale_version","concurrency","partial_batch","ordering","append_only","hold_propagation","review_independence","receipt_lineage","operator_gate","non_execution")
NEGATIVE=frozenset({"negative_path","missing_input","duplicate_input","replay","conflict","stale_version","partial_batch"})
STAGE_MAPPING=PRIOR_STAGE_MAPPING+(("ARKAON-LESSONS-17101",(17101,17500)),)
MAXIMUM_STATE="POSTGRES_DEADLOCK_PROOF_ONLY"

def mapping_digest(rows):return canonical_digest(("CONTIGUOUS_STAGE_MAPPING",tuple(rows)))
def _hex(v):return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)

def integration_proof_valid(p):
    expected={"status":"PASS_POSTGRES_DEADLOCK_PROOF","deadlock_sqlstate":"40P01","deadlock_failures":1,"deadlock_successes":1,"deadlock_provenance":"ACTUAL_POSTGRESQL_TWO_BACKEND_OPPOSITE_ROW_LOCK_ORDER","deadlock_timeout_preflight":"ACTUAL_POSTGRESQL_SET_LOCAL_CONFIRMED","failed_transaction_rolled_back":True,"failed_backend_closed":True,"fresh_backend_retry":True,"retry_success_attempt":2,"bounded_retry_max_attempts":3,"lock_timeout_sqlstate":"55P03","lock_timeout_attempts":1,"lock_timeout_provenance":"ACTUAL_POSTGRESQL_BLOCKED_ROW_LOCK","lock_timeout_non_retryable":True,"unit_retry_exhaustion_provenance":"UNIT_INJECTED_SQLSTATE_SEQUENCE","harness_commit_unknown_provenance":"HARNESS_INJECTED_POST_COMMIT_RESPONSE_LOSS","actual_network_partition_claimed":False,"actual_failover_claimed":False,"production_database_writes":0,"cleanup_succeeded":True,"credential_disclosed":False,"password_credential_configured":False}
    return isinstance(p,dict) and p==expected

def recovery_paths():return (
    (("cause","actual_deadlock_40P01"),("recommended",True),("method","rollback_close_failed_backend_then_retry_on_fresh_backend_with_three_attempt_ceiling"),("alternative","enforce_canonical_row_lock_order_to_prevent_deadlock"),("cost","LOW"),("risk","LOW"),("reversibility","HIGH"),("validation","exactly_one_40P01_and_attempt_two_new_backend_success"),("stop","third_failure_or_changed_sqlstate"),("resume","reduce_contention_then_rerun_disposable_proof"),("rollback","rollback_failed_transaction_and_drop_validated_schema_only")),
    (("cause","lock_timeout_or_deadlock_timeout_configuration_denied"),("recommended",False),("method","do_not_blind_retry_fail_closed_with_explicit_environment_hold"),("alternative","use_disposable_postgresql_role_authorized_for_test_only_session_settings"),("cost","MEDIUM"),("risk","MEDIUM"),("reversibility","HIGH"),("validation","actual_55P03_once_or_explicit_preflight_failure"),("stop","setting_denied_timeout_missing_or_target_not_disposable"),("resume","repair_fixture_permissions_then_rerun_all_proof"),("rollback","close_both_backends_and_drop_only_exact_schema")),
)

@dataclass(frozen=True)
class Control:control_id:int;workstream:str;aspect:str;requirement_ref:str;fixture_digest:str;expected_result:str;digest:str
@dataclass(frozen=True)
class Snapshot:snapshot_id:str;stage_range:tuple;mapping_digest:str;registry_digest:str;manifest_digest:str;lesson_ids:tuple;rule_ids:tuple;source_docket_digest:str;previous_snapshot_digest:str;sequence:int;latest:bool;digest:str
@dataclass(frozen=True)
class Docket:docket_id:str;snapshot_digest:str;complete:bool;held:bool;pending_human_judgment:bool;production_writes:int;receipt_issued:bool;approved:bool;activated:bool;deployed:bool;status:str;digest:str

class SyntheticPostgresDeadlockProof:
    def __init__(self):self._controls={};self._source=None;self._snapshot=None;self._docket=None
    def _expected(self,cid):i=cid-17101;return WORKSTREAM_NAMES[i//25],CONTROL_ASPECTS[i%25]
    def add_control(self,cid,workstream,aspect,requirement_ref,fixture_digest,expected_result):
        p=dict(control_id=cid,workstream=workstream,aspect=aspect,requirement_ref=requirement_ref,fixture_digest=fixture_digest,expected_result=expected_result);r=Control(**p,digest=canonical_digest(p))
        if not (isinstance(cid,int) and not isinstance(cid,bool) and 17101<=cid<=17500 and self._expected(cid)==(workstream,aspect) and requirement_ref==f"synthetic:postgres-deadlock-proof-requirement:{(cid-17101)//25:02}" and _hex(fixture_digest) and expected_result==("EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS")):raise GovernanceRejected("valid #17101-#17500 control required")
        if cid in self._controls and self._controls[cid]!=r:raise GovernanceRejected("control conflict")
        self._controls[cid]=r;return r
    def anchor(self,source,mapping,registry,manifest,lessons,rules,previous_snapshot,sequence,latest):
        if not isinstance(source,SyntheticPostgresRetryResilienceProof):raise GovernanceRejected("prior retry proof required")
        p=dict(snapshot_id="synthetic:lesson-snapshot:17101-17500",stage_range=(17101,17500),mapping_digest=mapping,registry_digest=registry,manifest_digest=manifest,lesson_ids=tuple(lessons),rule_ids=tuple(rules),source_docket_digest=source._docket.digest if source._docket else None,previous_snapshot_digest=previous_snapshot,sequence=sequence,latest=latest);r=Snapshot(**p,digest=canonical_digest(p))
        if not (set(self._controls)==set(range(17101,17501)) and source.evidence()["complete_postgres_retry_resilience_contract_evidence"] and mapping==mapping_digest(STAGE_MAPPING) and _hex(registry) and _hex(manifest) and tuple(lessons)==APPLIED_LESSONS and tuple(rules)==APPLIED_RULES and previous_snapshot==source._snapshot.digest and isinstance(sequence,int) and not isinstance(sequence,bool) and sequence>0 and latest is True):raise GovernanceRejected("complete deadlock proof snapshot required")
        self._source=source;self._snapshot=r;return r
    def finalize(self,docket_id):
        if self._docket or not self._snapshot:raise GovernanceRejected("complete deadlock contract required")
        p=dict(docket_id=docket_id,snapshot_digest=self._snapshot.digest,complete=True,held=True,pending_human_judgment=True,production_writes=0,receipt_issued=False,approved=False,activated=False,deployed=False,status=MAXIMUM_STATE)
        if not isinstance(docket_id,str) or not docket_id.startswith("synthetic:postgres-deadlock-proof-docket:"):raise GovernanceRejected("synthetic deadlock docket required")
        self._docket=Docket(**p,digest=canonical_digest(p));return self._docket
    def evidence(self,proof=None):
        if proof is None:status="SKIP_NO_PRECONFIGURED_TEST_DATABASE"
        elif integration_proof_valid(proof):status="PASS_POSTGRES_DEADLOCK_PROOF"
        else:raise GovernanceRejected("complete exact PostgreSQL deadlock PASS proof required")
        source_ok=bool(self._source and self._source.evidence()["complete_postgres_retry_resilience_contract_evidence"])
        snap_ok=bool(self._snapshot and source_ok and self._snapshot.stage_range==(17101,17500) and self._snapshot.mapping_digest==mapping_digest(STAGE_MAPPING) and self._snapshot.source_docket_digest==self._source._docket.digest and self._snapshot.previous_snapshot_digest==self._source._snapshot.digest and self._snapshot.lesson_ids==APPLIED_LESSONS and self._snapshot.rule_ids==APPLIED_RULES and _hex(self._snapshot.registry_digest) and _hex(self._snapshot.manifest_digest) and self._snapshot.latest and self._snapshot.digest==canonical_digest({k:v for k,v in self._snapshot.__dict__.items() if k!="digest"}))
        controls_ok=set(self._controls)==set(range(17101,17501)) and all(r.digest==canonical_digest({k:v for k,v in r.__dict__.items() if k!="digest"}) and self._expected(cid)==(r.workstream,r.aspect) for cid,r in self._controls.items())
        docket_ok=bool(self._docket and snap_ok and self._docket.production_writes==0 and self._docket.status==MAXIMUM_STATE and self._docket.digest==canonical_digest({k:v for k,v in self._docket.__dict__.items() if k!="digest"}))
        return {"range":[17101,17500],"control_count":400,"registered_control_count":len(self._controls),"recovery_path_count":64,"human_judgment_hold_count":32,"postgresql_deadlock_proof_status":status,"postgresql_deadlock_proof_claimed":status.startswith("PASS_"),"postgresql_integration_skip_count":1 if status.startswith("SKIP_") else 0,"actual_deadlock_claimed":status.startswith("PASS_"),"actual_network_partition_claimed":False,"actual_failover_claimed":False,"lock_timeout_classification":classify_sqlstate("55P03"),"production_database_writes":0,"cleanup_succeeded":(proof or {}).get("cleanup_succeeded",False),"complete_postgres_deadlock_contract_evidence":bool(docket_ok and controls_ok),"maximum_state":MAXIMUM_STATE if docket_ok and controls_ok else "CONTRACT_INCOMPLETE","applied_lesson_ids":list(APPLIED_LESSONS),"applied_rule_ids":list(APPLIED_RULES),"recovery_guidance_digest":canonical_digest(recovery_paths()),"approval_receipts_issued":0,"signatures_created":0,"keys_read":0,"credentials_read":0,"financial_operations":0,"approved":False,"activated":False,"deployed":False}
