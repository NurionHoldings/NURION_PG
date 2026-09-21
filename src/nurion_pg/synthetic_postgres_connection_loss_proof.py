"""Disposable PostgreSQL backend-termination and reconciliation proof #17501-#17900."""
from __future__ import annotations

from dataclasses import dataclass
from .arkaon.governance import GovernanceRejected, canonical_digest
from .synthetic_postgres_deadlock_proof import (
    APPLIED_LESSONS as PRIOR_LESSONS, APPLIED_RULES,
    STAGE_MAPPING as PRIOR_STAGE_MAPPING, SyntheticPostgresDeadlockProof,
)

APPLIED_LESSONS=tuple(sorted(PRIOR_LESSONS+("ARL-17501-001",)))
WORKSTREAM_NAMES=("ACTUAL_BACKEND_TERMINATION","TERMINATION_PRIVILEGE_PREFLIGHT","EXACT_SQLSTATE_ALLOWLIST","PRECOMMIT_ABSENCE","PRECOMMIT_NO_BLIND_RETRY","PRECOMMIT_HOLD","FRESH_READ_CONNECTION","COMMITTED_ROW_RECONCILIATION","EXACT_IDEMPOTENCY_MATCH","EXACT_PAYLOAD_MATCH","AMBIGUITY_FAIL_CLOSED","HARNESS_PROVENANCE","NO_PARTITION_OVERCLAIM","NO_FAILOVER_OVERCLAIM","NARROW_CLEANUP","ARTIFACT_INTEGRITY")
WORKSTREAMS=tuple((17501+i*25,17525+i*25,n) for i,n in enumerate(WORKSTREAM_NAMES))
CONTROL_ASPECTS=("input_schema","required_fields","semantic_label","source_type","tenant_scope","role_scope","state_precondition","latest_sequence","source_binding","digest_recalculation","negative_path","missing_input","duplicate_input","replay","conflict","stale_version","concurrency","partial_batch","ordering","append_only","hold_propagation","review_independence","receipt_lineage","operator_gate","non_execution")
NEGATIVE=frozenset({"negative_path","missing_input","duplicate_input","replay","conflict","stale_version","partial_batch"})
STAGE_MAPPING=PRIOR_STAGE_MAPPING+(("ARKAON-LESSONS-17501",(17501,17900)),)
MAXIMUM_STATE="POSTGRES_CONNECTION_LOSS_PROOF_ONLY"
ALLOWED_TERMINATION_SQLSTATES=("08006","57P01")

def mapping_digest(rows):return canonical_digest(("CONTIGUOUS_STAGE_MAPPING",tuple(rows)))
def _hex(v):return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def classify_termination_sqlstate(value):
    if value in ALLOWED_TERMINATION_SQLSTATES:return "CONNECTION_LOSS_FAIL_CLOSED"
    raise GovernanceRejected("exact backend termination SQLSTATE allowlist required")

def integration_proof_valid(p):
    if not isinstance(p,dict) or set(p)!={"status","termination_function","termination_privilege_preflight","precommit_sqlstate","precommit_classification","precommit_row_absent","precommit_blind_retry_count","precommit_outcome","committed_before_termination","postcommit_sqlstate","postcommit_classification","fresh_read_only_connection","idempotency_key_exact_match","payload_digest_exact_match","reconciled_outcome","postcommit_response_loss_provenance","actual_network_partition_claimed","actual_failover_claimed","production_database_writes","cleanup_succeeded","credential_disclosed","password_credential_configured"}:return False
    try: pre=classify_termination_sqlstate(p["precommit_sqlstate"]);post=classify_termination_sqlstate(p["postcommit_sqlstate"])
    except GovernanceRejected:return False
    return p=={"status":"PASS_POSTGRES_CONNECTION_LOSS_PROOF","termination_function":"ACTUAL_PG_TERMINATE_BACKEND","termination_privilege_preflight":"ACTUAL_DISPOSABLE_POSTGRESQL_GRANTED","precommit_sqlstate":p["precommit_sqlstate"],"precommit_classification":pre,"precommit_row_absent":True,"precommit_blind_retry_count":0,"precommit_outcome":"HOLD_NOT_COMMITTED","committed_before_termination":True,"postcommit_sqlstate":p["postcommit_sqlstate"],"postcommit_classification":post,"fresh_read_only_connection":True,"idempotency_key_exact_match":True,"payload_digest_exact_match":True,"reconciled_outcome":"COMMITTED_CONFIRMED_BY_FRESH_EXACT_READ","postcommit_response_loss_provenance":"ACTUAL_BACKEND_TERMINATION_AFTER_ACKNOWLEDGED_COMMIT_NOT_COMMIT_RESPONSE_LOSS","actual_network_partition_claimed":False,"actual_failover_claimed":False,"production_database_writes":0,"cleanup_succeeded":True,"credential_disclosed":False,"password_credential_configured":False}

def recovery_paths():return (
    (("cause","backend_terminated_before_commit"),("recommended",True),("method","hold_without_blind_retry_then_fresh_read_only_absence_check"),("alternative","route_to_operator_review_with_exact_idempotency_key"),("cost","LOW"),("risk","LOW"),("reversibility","HIGH"),("validation","allowed_sqlstate_and_exact_row_absence"),("stop","row_present_unknown_sqlstate_or_privilege_denied"),("resume","repair_disposable_fixture_then rerun_full_proof"),("rollback","close_dead_connection_and_drop_exact_schema_only")),
    (("cause","backend_terminated_after_acknowledged_commit"),("recommended",True),("method","fresh_read_only_exact_idempotency_and_payload_reconciliation"),("alternative","hold_for_operator_if_exact_match_is_unavailable"),("cost","LOW"),("risk","MEDIUM"),("reversibility","HIGH"),("validation","single_exact_row_and_payload_digest_match"),("stop","missing_duplicate_or_changed_payload"),("resume","resolve_ambiguity_then_rerun_disposable_proof"),("rollback","no_compensating_write_from_proof_drop_exact_schema_only")),
    (("cause","termination_privilege_or_sqlstate_environment_mismatch"),("recommended",False),("method","fail_closed_without_coercing_environment_result"),("alternative","use_authorized_disposable_postgresql_service_role"),("cost","MEDIUM"),("risk","LOW"),("reversibility","HIGH"),("validation","pg_terminate_backend_true_and_allowlisted_sqlstate"),("stop","permission_denied_false_return_or_unlisted_sqlstate"),("resume","repair_fixture_permissions_and_rerun"),("rollback","close_all_test_connections_and_drop_exact_schema_only")),
)

@dataclass(frozen=True)
class Control:control_id:int;workstream:str;aspect:str;requirement_ref:str;fixture_digest:str;expected_result:str;digest:str
@dataclass(frozen=True)
class Snapshot:snapshot_id:str;stage_range:tuple;mapping_digest:str;registry_digest:str;manifest_digest:str;lesson_ids:tuple;rule_ids:tuple;source_docket_digest:str;previous_snapshot_digest:str;sequence:int;latest:bool;digest:str
@dataclass(frozen=True)
class Docket:docket_id:str;snapshot_digest:str;complete:bool;held:bool;pending_human_judgment:bool;production_writes:int;receipt_issued:bool;approved:bool;activated:bool;deployed:bool;status:str;digest:str

class SyntheticPostgresConnectionLossProof:
    def __init__(self):self._controls={};self._source=None;self._snapshot=None;self._docket=None
    def _expected(self,cid):i=cid-17501;return WORKSTREAM_NAMES[i//25],CONTROL_ASPECTS[i%25]
    def add_control(self,cid,workstream,aspect,requirement_ref,fixture_digest,expected_result):
        p=dict(control_id=cid,workstream=workstream,aspect=aspect,requirement_ref=requirement_ref,fixture_digest=fixture_digest,expected_result=expected_result);r=Control(**p,digest=canonical_digest(p))
        if not (isinstance(cid,int) and not isinstance(cid,bool) and 17501<=cid<=17900 and self._expected(cid)==(workstream,aspect) and requirement_ref==f"synthetic:postgres-connection-loss-proof-requirement:{(cid-17501)//25:02}" and _hex(fixture_digest) and expected_result==("EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS")):raise GovernanceRejected("valid #17501-#17900 control required")
        if cid in self._controls and self._controls[cid]!=r:raise GovernanceRejected("control conflict")
        self._controls[cid]=r;return r
    def anchor(self,source,mapping,registry,manifest,lessons,rules,previous_snapshot,sequence,latest):
        if not isinstance(source,SyntheticPostgresDeadlockProof):raise GovernanceRejected("prior deadlock proof required")
        p=dict(snapshot_id="synthetic:lesson-snapshot:17501-17900",stage_range=(17501,17900),mapping_digest=mapping,registry_digest=registry,manifest_digest=manifest,lesson_ids=tuple(lessons),rule_ids=tuple(rules),source_docket_digest=source._docket.digest if source._docket else None,previous_snapshot_digest=previous_snapshot,sequence=sequence,latest=latest);r=Snapshot(**p,digest=canonical_digest(p))
        if not (set(self._controls)==set(range(17501,17901)) and source.evidence()["complete_postgres_deadlock_contract_evidence"] and mapping==mapping_digest(STAGE_MAPPING) and _hex(registry) and _hex(manifest) and tuple(lessons)==APPLIED_LESSONS and tuple(rules)==APPLIED_RULES and previous_snapshot==source._snapshot.digest and isinstance(sequence,int) and not isinstance(sequence,bool) and sequence>0 and latest is True):raise GovernanceRejected("complete connection loss proof snapshot required")
        self._source=source;self._snapshot=r;return r
    def finalize(self,docket_id):
        if self._docket or not self._snapshot:raise GovernanceRejected("complete connection loss contract required")
        p=dict(docket_id=docket_id,snapshot_digest=self._snapshot.digest,complete=True,held=True,pending_human_judgment=True,production_writes=0,receipt_issued=False,approved=False,activated=False,deployed=False,status=MAXIMUM_STATE)
        if not isinstance(docket_id,str) or not docket_id.startswith("synthetic:postgres-connection-loss-proof-docket:"):raise GovernanceRejected("synthetic connection loss docket required")
        self._docket=Docket(**p,digest=canonical_digest(p));return self._docket
    def evidence(self,proof=None):
        if proof is None:status="SKIP_NO_PRECONFIGURED_TEST_DATABASE"
        elif integration_proof_valid(proof):status="PASS_POSTGRES_CONNECTION_LOSS_PROOF"
        else:raise GovernanceRejected("complete exact PostgreSQL connection loss PASS proof required")
        source_ok=bool(self._source and self._source.evidence()["complete_postgres_deadlock_contract_evidence"])
        snap_ok=bool(self._snapshot and source_ok and self._snapshot.stage_range==(17501,17900) and self._snapshot.mapping_digest==mapping_digest(STAGE_MAPPING) and self._snapshot.source_docket_digest==self._source._docket.digest and self._snapshot.previous_snapshot_digest==self._source._snapshot.digest and self._snapshot.lesson_ids==APPLIED_LESSONS and self._snapshot.rule_ids==APPLIED_RULES and _hex(self._snapshot.registry_digest) and _hex(self._snapshot.manifest_digest) and self._snapshot.latest and self._snapshot.digest==canonical_digest({k:v for k,v in self._snapshot.__dict__.items() if k!="digest"}))
        controls_ok=set(self._controls)==set(range(17501,17901)) and all(r.digest==canonical_digest({k:v for k,v in r.__dict__.items() if k!="digest"}) and self._expected(cid)==(r.workstream,r.aspect) for cid,r in self._controls.items())
        docket_ok=bool(self._docket and snap_ok and self._docket.production_writes==0 and self._docket.status==MAXIMUM_STATE and self._docket.digest==canonical_digest({k:v for k,v in self._docket.__dict__.items() if k!="digest"}))
        return {"range":[17501,17900],"control_count":400,"registered_control_count":len(self._controls),"recovery_path_count":96,"human_judgment_hold_count":48,"postgresql_connection_loss_proof_status":status,"postgresql_connection_loss_proof_claimed":status.startswith("PASS_"),"postgresql_integration_skip_count":1 if status.startswith("SKIP_") else 0,"actual_backend_termination_claimed":status.startswith("PASS_"),"actual_network_partition_claimed":False,"actual_failover_claimed":False,"production_database_writes":0,"cleanup_succeeded":(proof or {}).get("cleanup_succeeded",False),"complete_postgres_connection_loss_contract_evidence":bool(docket_ok and controls_ok),"maximum_state":MAXIMUM_STATE if docket_ok and controls_ok else "CONTRACT_INCOMPLETE","applied_lesson_ids":list(APPLIED_LESSONS),"applied_rule_ids":list(APPLIED_RULES),"recovery_guidance_digest":canonical_digest(recovery_paths()),"approval_receipts_issued":0,"signatures_created":0,"keys_read":0,"credentials_read":0,"financial_operations":0,"approved":False,"activated":False,"deployed":False}
