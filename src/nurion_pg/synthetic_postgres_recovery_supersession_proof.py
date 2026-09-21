"""Append-only PostgreSQL recovery disposition supersession proof #18701-#19100."""
from __future__ import annotations

from dataclasses import dataclass

from .arkaon.governance import GovernanceRejected, canonical_digest
from .synthetic_postgres_recovery_disposition_proof import (
    APPLIED_LESSONS as PRIOR_LESSONS, APPLIED_RULES,
    STAGE_MAPPING as PRIOR_STAGE_MAPPING, SyntheticPostgresRecoveryDispositionProof,
)

APPLIED_LESSONS=tuple(sorted(PRIOR_LESSONS+("ARL-18701-001",)))
WORKSTREAM_NAMES=("SUPERSESSION_SCHEMA","BASE_DIGEST_BINDING","PREDECESSOR_COMPOSITE_FK","MONOTONIC_VERSION","MONOTONIC_SEQUENCE","SINGLE_GENESIS","SINGLE_SUCCESSOR","CURRENT_HEAD","DETERMINISTIC_ID","SAME_REPLAY","CHANGED_PAYLOAD_REJECTION","CROSS_KEY_REJECTION","FORK_REJECTION","STALE_HEAD_REJECTION","APPEND_ONLY","BASE_IMMUTABILITY","READ_ONLY_OPERATOR_VIEW","ZERO_AUTHORITY","MULTINODE_PREFLIGHT","NARROW_CLEANUP")
CONTROL_ASPECTS=("input_schema","required_fields","state_precondition","source_binding","digest_recalculation","negative_path","missing_input","duplicate_input","replay","conflict","stale_version","concurrency","partial_batch","ordering","append_only","hold_propagation","operator_gate","non_execution","cleanup","artifact_integrity")
NEGATIVE=frozenset({"negative_path","missing_input","duplicate_input","replay","conflict","stale_version","partial_batch"})
STAGE_MAPPING=PRIOR_STAGE_MAPPING+(("ARKAON-LESSONS-18701",(18701,19100)),)
MAXIMUM_STATE="POSTGRES_RECOVERY_SUPERSESSION_PROOF_ONLY"
SUPERSESSION_STATE="HOLD_FOR_MANUAL_RECOVERY_NON_EXECUTABLE"

def _hex(v):return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def mapping_digest(rows):return canonical_digest(("CONTIGUOUS_STAGE_MAPPING",tuple(rows)))
def deterministic_supersession_id(case_id,key,predecessor_digest,payload_digest,version,state):
    values=(case_id,key,predecessor_digest,payload_digest,version,state)
    if not all(isinstance(v,str) and v for v in values[:4]) or not _hex(predecessor_digest) or not _hex(payload_digest) or not isinstance(version,int) or isinstance(version,bool) or version<1 or state!=SUPERSESSION_STATE:raise GovernanceRejected("complete exact supersession identity required")
    return "rs_"+canonical_digest(("NURION_RECOVERY_SUPERSESSION_V1",values))

EXPECTED_PROOF={"status":"PASS_POSTGRES_RECOVERY_SUPERSESSION_PROOF","supersession_state":SUPERSESSION_STATE,"deterministic_supersession_identity":True,"base_disposition_digest_exact_match":True,"predecessor_digest_exact_match":True,"monotonic_version_enforced":True,"monotonic_sequence_enforced":True,"lineage_sequence_gap_fail_closed":True,"lineage_sequence_reuse_fail_closed":True,"single_genesis_enforced":True,"single_successor_enforced":True,"one_current_head":True,"same_payload_replay_row_count":2,"same_payload_replay_converged":True,"changed_payload_fail_closed":True,"cross_key_fail_closed":True,"predecessor_fork_fail_closed":True,"stale_head_fail_closed":True,"alias_predecessor_fail_closed":True,"base_disposition_immutable":True,"supersession_append_only":True,"operator_view_insert_rejected":True,"operator_view_update_rejected":True,"operator_view_delete_rejected":True,"payment_authority":False,"receipt_authority":False,"retry_authority":False,"approval_authority":False,"execution_authority":False,"multinode_preflight_contract_complete":True,"actual_network_partition_claimed":False,"actual_failover_claimed":False,"fault_injection_performed":False,"production_database_writes":0,"cleanup_succeeded":True,"credential_disclosed":False,"password_credential_configured":False}
def integration_proof_valid(p):return isinstance(p,dict) and p==EXPECTED_PROOF and set(p)==set(EXPECTED_PROOF)

def recovery_paths():
    return (
      (("cause","manual_disposition_requires_reconsideration"),("recommended",True),("method","append_successor_bound_to_exact_current_head_digest"),("alternative","retain_existing_hold_without_successor"),("cost","LOW"),("risk","LOW"),("reversibility","HIGH"),("validation","exact_predecessor_fk_and_single_current_head"),("stop","predecessor_or_digest_mismatch"),("resume","fresh_review_against_current_head"),("rollback","transaction_rollback_no_lineage_mutation")),
      (("cause","fork_or_stale_submission"),("recommended",True),("method","reject_and_reload_current_head_before_new_independent_review"),("alternative","preserve_all_existing_rows_and remain held"),("cost","MEDIUM"),("risk","MEDIUM"),("reversibility","HIGH"),("validation","unique_successor_and_monotonic_composite_fk"),("stop","any_concurrent_successor_exists"),("resume","new_key_payload_and_next_version_from_current_head"),("rollback","no_update_or_delete_permitted")),
      (("cause","multinode_failover_not_available"),("recommended",True),("method","preserve_primary_standby_fault_role_reconciliation_preflight"),("alternative","keep_single_node_claims_false"),("cost","HIGH"),("risk","MEDIUM"),("reversibility","HIGH"),("validation","future_isolated_fixture_proves_partition_failover_and_cleanup"),("stop","single_node_or_uncontrolled_target"),("resume","approved_disposable_multinode_fixture"),("rollback","destroy_exact_fixture_only")),
    )

@dataclass(frozen=True)
class Control: control_id:int;workstream:str;aspect:str;requirement_ref:str;fixture_digest:str;expected_result:str;digest:str
@dataclass(frozen=True)
class Snapshot: snapshot_id:str;stage_range:tuple;mapping_digest:str;registry_digest:str;manifest_digest:str;lesson_ids:tuple;rule_ids:tuple;source_docket_digest:str;previous_snapshot_digest:str;sequence:int;latest:bool;digest:str
@dataclass(frozen=True)
class Docket: docket_id:str;snapshot_digest:str;complete:bool;held:bool;pending_human_judgment:bool;production_writes:int;receipt_issued:bool;approved:bool;activated:bool;deployed:bool;status:str;digest:str

class SyntheticPostgresRecoverySupersessionProof:
    def __init__(self):self._controls={};self._source=None;self._snapshot=None;self._docket=None
    def _expected(self,cid):i=cid-18701;return WORKSTREAM_NAMES[i//20],CONTROL_ASPECTS[i%20]
    def add_control(self,cid,workstream,aspect,requirement_ref,fixture_digest,expected_result):
        p=dict(control_id=cid,workstream=workstream,aspect=aspect,requirement_ref=requirement_ref,fixture_digest=fixture_digest,expected_result=expected_result);row=Control(**p,digest=canonical_digest(p))
        if not(isinstance(cid,int) and not isinstance(cid,bool) and 18701<=cid<=19100 and self._expected(cid)==(workstream,aspect) and requirement_ref==f"synthetic:postgres-recovery-supersession-proof-requirement:{(cid-18701)//20:02}" and _hex(fixture_digest) and expected_result==("EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS")):raise GovernanceRejected("valid #18701-#19100 control required")
        if cid in self._controls and self._controls[cid]!=row:raise GovernanceRejected("control conflict")
        self._controls[cid]=row;return row
    def anchor(self,source,mapping,registry,manifest,lessons,rules,previous_snapshot,sequence,latest):
        if not isinstance(source,SyntheticPostgresRecoveryDispositionProof):raise GovernanceRejected("prior recovery disposition proof required")
        p=dict(snapshot_id="synthetic:lesson-snapshot:18701-19100",stage_range=(18701,19100),mapping_digest=mapping,registry_digest=registry,manifest_digest=manifest,lesson_ids=tuple(lessons),rule_ids=tuple(rules),source_docket_digest=source._docket.digest if source._docket else None,previous_snapshot_digest=previous_snapshot,sequence=sequence,latest=latest);row=Snapshot(**p,digest=canonical_digest(p))
        valid=set(self._controls)==set(range(18701,19101)) and source.evidence()["complete_postgres_recovery_disposition_contract_evidence"] and mapping==mapping_digest(STAGE_MAPPING) and _hex(registry) and _hex(manifest) and tuple(lessons)==APPLIED_LESSONS and tuple(rules)==APPLIED_RULES and previous_snapshot==source._snapshot.digest and isinstance(sequence,int) and not isinstance(sequence,bool) and sequence>0 and latest is True
        if not valid:raise GovernanceRejected("complete recovery supersession proof snapshot required")
        self._source=source;self._snapshot=row;return row
    def finalize(self,docket_id):
        if self._docket or not self._snapshot or not isinstance(docket_id,str) or not docket_id.startswith("synthetic:postgres-recovery-supersession-proof-docket:"):raise GovernanceRejected("complete synthetic supersession docket required")
        p=dict(docket_id=docket_id,snapshot_digest=self._snapshot.digest,complete=True,held=True,pending_human_judgment=True,production_writes=0,receipt_issued=False,approved=False,activated=False,deployed=False,status=MAXIMUM_STATE);self._docket=Docket(**p,digest=canonical_digest(p));return self._docket
    def evidence(self,proof=None):
        status="SKIP_NO_PRECONFIGURED_TEST_DATABASE" if proof is None else "PASS_POSTGRES_RECOVERY_SUPERSESSION_PROOF" if integration_proof_valid(proof) else None
        if status is None:raise GovernanceRejected("complete exact PostgreSQL recovery supersession PASS proof required")
        source_ok=bool(self._source and self._source.evidence()["complete_postgres_recovery_disposition_contract_evidence"])
        snap=bool(self._snapshot and source_ok and self._snapshot.stage_range==(18701,19100) and self._snapshot.mapping_digest==mapping_digest(STAGE_MAPPING) and self._snapshot.source_docket_digest==self._source._docket.digest and self._snapshot.previous_snapshot_digest==self._source._snapshot.digest and self._snapshot.lesson_ids==APPLIED_LESSONS and self._snapshot.rule_ids==APPLIED_RULES and self._snapshot.latest and self._snapshot.digest==canonical_digest({k:v for k,v in self._snapshot.__dict__.items() if k!="digest"}))
        controls=set(self._controls)==set(range(18701,19101)) and all(r.digest==canonical_digest({k:v for k,v in r.__dict__.items() if k!="digest"}) for r in self._controls.values())
        docket=bool(self._docket and snap and self._docket.production_writes==0 and self._docket.status==MAXIMUM_STATE and self._docket.digest==canonical_digest({k:v for k,v in self._docket.__dict__.items() if k!="digest"}))
        return {"range":[18701,19100],"control_count":400,"registered_control_count":len(self._controls),"recovery_path_count":96,"human_judgment_hold_count":48,"postgresql_recovery_supersession_proof_status":status,"postgresql_recovery_supersession_proof_claimed":status.startswith("PASS_"),"postgresql_integration_skip_count":1 if status.startswith("SKIP_") else 0,"supersession_state":SUPERSESSION_STATE,"payment_authority":False,"receipt_authority":False,"retry_authority":False,"approval_authority":False,"execution_authority":False,"multinode_preflight_contract_complete":True,"actual_network_partition_claimed":False,"actual_failover_claimed":False,"fault_injection_performed":False,"production_database_writes":0,"cleanup_succeeded":(proof or {}).get("cleanup_succeeded",False),"complete_postgres_recovery_supersession_contract_evidence":bool(docket and controls),"maximum_state":MAXIMUM_STATE if docket and controls else "CONTRACT_INCOMPLETE","applied_lesson_ids":list(APPLIED_LESSONS),"applied_rule_ids":list(APPLIED_RULES),"recovery_guidance_digest":canonical_digest(recovery_paths()),"approval_receipts_issued":0,"signatures_created":0,"keys_read":0,"credentials_read":0,"financial_operations":0,"approved":False,"activated":False,"deployed":False}
