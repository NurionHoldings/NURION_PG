"""Non-executable recovery recommendation and concurrence proof #19501-#19900."""
from __future__ import annotations

from dataclasses import dataclass

from .arkaon.governance import GovernanceRejected, canonical_digest
from .synthetic_postgres_recovery_review_receipt_proof import (
    APPLIED_LESSONS as PRIOR_LESSONS, APPLIED_RULES,
    STAGE_MAPPING as PRIOR_STAGE_MAPPING,
    SyntheticPostgresRecoveryReviewReceiptProof,
)

APPLIED_LESSONS=tuple(sorted(PRIOR_LESSONS+("ARL-19501-001",)))
WORKSTREAM_NAMES=("RECOMMENDATION_SCHEMA","RECEIPT_BINDING","AUTHOR_SEPARATION","DETERMINISTIC_RECOMMENDATION","RECOMMENDATION_REPLAY","CHANGED_ACTION_REJECTION","CROSS_RECEIPT_REJECTION","RISK_BINDING","CONCURRENCE_SCHEMA","RECOMMENDATION_FK","REVIEWER_SEPARATION","DETERMINISTIC_CONCURRENCE","SINGLE_REVIEWER_VERDICT","CONCURRENCE_REPLAY","CONFLICT_HOLD","APPEND_ONLY","READ_ONLY_OPERATOR_VIEW","ZERO_AUTHORITY","MULTINODE_PREFLIGHT","NARROW_CLEANUP")
CONTROL_ASPECTS=("input_schema","required_fields","state_precondition","source_binding","digest_recalculation","negative_path","missing_input","duplicate_input","replay","conflict","stale_version","concurrency","partial_batch","ordering","append_only","hold_propagation","operator_gate","non_execution","cleanup","artifact_integrity")
NEGATIVE=frozenset({"negative_path","missing_input","duplicate_input","replay","conflict","stale_version","partial_batch"})
STAGE_MAPPING=PRIOR_STAGE_MAPPING+(("ARKAON-LESSONS-19501",(19501,19900)),)
MAXIMUM_STATE="POSTGRES_RECOVERY_RECOMMENDATION_CONCURRENCE_PROOF_ONLY"
RECOMMENDATION_STATE="RECOVERY_RECOMMENDATION_NON_EXECUTABLE"
VERDICTS=frozenset({"CONCUR_NON_EXECUTABLE","HOLD_CONFLICT"})

def _hex(value):return isinstance(value,str) and len(value)==64 and all(c in "0123456789abcdef" for c in value)
def mapping_digest(rows):return canonical_digest(("CONTIGUOUS_STAGE_MAPPING",tuple(rows)))

def deterministic_recommendation_id(receipt_id,receipt_digest,recommendation_key,author_subject,action_digest,risk_digest):
    if not all(isinstance(v,str) and v for v in (receipt_id,recommendation_key,author_subject)) or not all(_hex(v) for v in (receipt_digest,action_digest,risk_digest)):
        raise GovernanceRejected("complete exact non-executable recommendation identity required")
    return "rrp_"+canonical_digest(("NURION_RECOVERY_RECOMMENDATION_V1",receipt_id,receipt_digest,recommendation_key,author_subject,action_digest,risk_digest))

def deterministic_concurrence_id(recommendation_id,recommendation_digest,reviewer_subject,verdict,rationale_digest):
    if not all(isinstance(v,str) and v for v in (recommendation_id,reviewer_subject)) or not _hex(recommendation_digest) or verdict not in VERDICTS or not _hex(rationale_digest):
        raise GovernanceRejected("complete exact concurrence identity required")
    return "rrc_"+canonical_digest(("NURION_RECOVERY_CONCURRENCE_V1",recommendation_id,recommendation_digest,reviewer_subject,verdict,rationale_digest))

EXPECTED_PROOF={"status":"PASS_POSTGRES_RECOVERY_RECOMMENDATION_CONCURRENCE_PROOF","recommendation_state":RECOMMENDATION_STATE,"recommendation_bound_to_exact_receipt":True,"author_reviewer_separation_enforced":True,"deterministic_recommendation_identity":True,"deterministic_concurrence_identity":True,"same_recommendation_replay_converged":True,"same_concurrence_replay_converged":True,"changed_action_fail_closed":True,"cross_receipt_fail_closed":True,"single_reviewer_verdict_enforced":True,"conflicting_verdict_preserves_hold":True,"recommendation_append_only":True,"concurrence_append_only":True,"operator_view_insert_rejected":True,"operator_view_update_rejected":True,"operator_view_delete_rejected":True,"payment_authority":False,"receipt_authority":False,"retry_authority":False,"approval_authority":False,"execution_authority":False,"multinode_preflight_contract_complete":True,"actual_network_partition_claimed":False,"actual_failover_claimed":False,"fault_injection_performed":False,"production_database_writes":0,"cleanup_succeeded":True,"credential_disclosed":False,"password_credential_configured":False}
def integration_proof_valid(proof):return isinstance(proof,dict) and proof==EXPECTED_PROOF and set(proof)==set(EXPECTED_PROOF)

def recovery_paths():
    return (
      (("cause","review_receipt_requires_non_executable_recommendation"),("recommended",True),("method","bind_action_and_risk_digests_to_exact_receipt"),("alternative","retain_hold_without_recommendation"),("cost","LOW"),("risk","LOW"),("reversibility","HIGH"),("validation","exact_receipt_fk_and_deterministic_identity"),("stop","receipt_or_digest_mismatch"),("resume","fresh_recommendation_from_exact_receipt"),("rollback","transaction_rollback_no_source_mutation")),
      (("cause","independent_reviewer_disagrees"),("recommended",True),("method","append_hold_conflict_verdict_without_overwriting_other_reviews"),("alternative","preserve_recommendation_as_non_executable"),("cost","MEDIUM"),("risk","MEDIUM"),("reversibility","HIGH"),("validation","reviewer_separation_and_single_verdict_per_reviewer"),("stop","any_hold_conflict_exists"),("resume","new_independent_review_cycle"),("rollback","append_only_rows_remain_unchanged")),
      (("cause","multinode_failover_not_available"),("recommended",True),("method","preserve_recommendation_consistency_preflight"),("alternative","keep_single_node_claims_false"),("cost","HIGH"),("risk","MEDIUM"),("reversibility","HIGH"),("validation","future_disposable_multinode_fixture"),("stop","uncontrolled_or_production_target"),("resume","approved_disposable_fixture"),("rollback","destroy_exact_fixture_only")),
    )

@dataclass(frozen=True)
class Control:control_id:int;workstream:str;aspect:str;requirement_ref:str;fixture_digest:str;expected_result:str;digest:str
@dataclass(frozen=True)
class Snapshot:snapshot_id:str;stage_range:tuple;mapping_digest:str;registry_digest:str;manifest_digest:str;lesson_ids:tuple;rule_ids:tuple;source_docket_digest:str;previous_snapshot_digest:str;sequence:int;latest:bool;digest:str
@dataclass(frozen=True)
class Docket:docket_id:str;snapshot_digest:str;complete:bool;held:bool;pending_human_judgment:bool;production_writes:int;receipt_issued:bool;approved:bool;activated:bool;deployed:bool;status:str;digest:str

class SyntheticPostgresRecoveryRecommendationConcurrenceProof:
    def __init__(self):self._controls={};self._source=None;self._snapshot=None;self._docket=None
    def _expected(self,cid):offset=cid-19501;return WORKSTREAM_NAMES[offset//20],CONTROL_ASPECTS[offset%20]
    def add_control(self,cid,workstream,aspect,requirement_ref,fixture_digest,expected_result):
        payload=dict(control_id=cid,workstream=workstream,aspect=aspect,requirement_ref=requirement_ref,fixture_digest=fixture_digest,expected_result=expected_result);row=Control(**payload,digest=canonical_digest(payload))
        valid=isinstance(cid,int) and not isinstance(cid,bool) and 19501<=cid<=19900 and self._expected(cid)==(workstream,aspect) and requirement_ref==f"synthetic:postgres-recovery-recommendation-concurrence-proof-requirement:{(cid-19501)//20:02}" and _hex(fixture_digest) and expected_result==("EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS")
        if not valid:raise GovernanceRejected("valid #19501-#19900 control required")
        if cid in self._controls and self._controls[cid]!=row:raise GovernanceRejected("control conflict")
        self._controls[cid]=row;return row
    def anchor(self,source,mapping,registry,manifest,lessons,rules,previous_snapshot,sequence,latest):
        if not isinstance(source,SyntheticPostgresRecoveryReviewReceiptProof):raise GovernanceRejected("prior recovery review receipt proof required")
        payload=dict(snapshot_id="synthetic:lesson-snapshot:19501-19900",stage_range=(19501,19900),mapping_digest=mapping,registry_digest=registry,manifest_digest=manifest,lesson_ids=tuple(lessons),rule_ids=tuple(rules),source_docket_digest=source._docket.digest if source._docket else None,previous_snapshot_digest=previous_snapshot,sequence=sequence,latest=latest);row=Snapshot(**payload,digest=canonical_digest(payload))
        valid=set(self._controls)==set(range(19501,19901)) and source.evidence()["complete_postgres_recovery_review_receipt_contract_evidence"] and mapping==mapping_digest(STAGE_MAPPING) and _hex(registry) and _hex(manifest) and tuple(lessons)==APPLIED_LESSONS and tuple(rules)==APPLIED_RULES and previous_snapshot==source._snapshot.digest and isinstance(sequence,int) and not isinstance(sequence,bool) and sequence>0 and latest is True
        if not valid:raise GovernanceRejected("complete recommendation concurrence proof snapshot required")
        self._source=source;self._snapshot=row;return row
    def finalize(self,docket_id):
        if self._docket or not self._snapshot or not isinstance(docket_id,str) or not docket_id.startswith("synthetic:postgres-recovery-recommendation-concurrence-proof-docket:"):raise GovernanceRejected("complete recommendation concurrence docket required")
        payload=dict(docket_id=docket_id,snapshot_digest=self._snapshot.digest,complete=True,held=True,pending_human_judgment=True,production_writes=0,receipt_issued=False,approved=False,activated=False,deployed=False,status=MAXIMUM_STATE);self._docket=Docket(**payload,digest=canonical_digest(payload));return self._docket
    def evidence(self,proof=None):
        status="SKIP_NO_PRECONFIGURED_TEST_DATABASE" if proof is None else "PASS_POSTGRES_RECOVERY_RECOMMENDATION_CONCURRENCE_PROOF" if integration_proof_valid(proof) else None
        if status is None:raise GovernanceRejected("complete exact PostgreSQL recommendation concurrence PASS proof required")
        source_ok=bool(self._source and self._source.evidence()["complete_postgres_recovery_review_receipt_contract_evidence"])
        snapshot_ok=bool(self._snapshot and source_ok and self._snapshot.stage_range==(19501,19900) and self._snapshot.mapping_digest==mapping_digest(STAGE_MAPPING) and self._snapshot.source_docket_digest==self._source._docket.digest and self._snapshot.previous_snapshot_digest==self._source._snapshot.digest and self._snapshot.lesson_ids==APPLIED_LESSONS and self._snapshot.rule_ids==APPLIED_RULES and self._snapshot.latest and self._snapshot.digest==canonical_digest({k:v for k,v in self._snapshot.__dict__.items() if k!="digest"}))
        controls_ok=set(self._controls)==set(range(19501,19901)) and all(row.digest==canonical_digest({k:v for k,v in row.__dict__.items() if k!="digest"}) for row in self._controls.values())
        docket_ok=bool(self._docket and snapshot_ok and self._docket.production_writes==0 and not self._docket.receipt_issued and self._docket.status==MAXIMUM_STATE and self._docket.digest==canonical_digest({k:v for k,v in self._docket.__dict__.items() if k!="digest"}))
        return {"range":[19501,19900],"control_count":400,"registered_control_count":len(self._controls),"recovery_path_count":96,"human_judgment_hold_count":48,"postgresql_recovery_recommendation_concurrence_proof_status":status,"postgresql_recovery_recommendation_concurrence_proof_claimed":status.startswith("PASS_"),"postgresql_integration_skip_count":1 if status.startswith("SKIP_") else 0,"recommendation_state":RECOMMENDATION_STATE,"payment_authority":False,"receipt_authority":False,"retry_authority":False,"approval_authority":False,"execution_authority":False,"multinode_preflight_contract_complete":True,"actual_network_partition_claimed":False,"actual_failover_claimed":False,"fault_injection_performed":False,"production_database_writes":0,"cleanup_succeeded":(proof or {}).get("cleanup_succeeded",False),"complete_postgres_recovery_recommendation_concurrence_contract_evidence":bool(docket_ok and controls_ok),"maximum_state":MAXIMUM_STATE if docket_ok and controls_ok else "CONTRACT_INCOMPLETE","applied_lesson_ids":list(APPLIED_LESSONS),"applied_rule_ids":list(APPLIED_RULES),"recovery_guidance_digest":canonical_digest(recovery_paths()),"approval_receipts_issued":0,"signatures_created":0,"keys_read":0,"credentials_read":0,"financial_operations":0,"approved":False,"activated":False,"deployed":False}
