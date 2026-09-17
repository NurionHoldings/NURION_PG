"""Metadata-only plans for synthetic fixture materialization."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from .arkaon.governance import GovernanceRejected,canonical_digest
from .synthetic_activation_dry_run_fixture_draft_review import FixtureDraftReviewDecision,FixtureDraftReviewState,SyntheticActivationDryRunFixtureDraftReviewDocket,SyntheticActivationDryRunFixtureDraftReviewRecord,_valid_draft

FIXTURE_MATERIALIZATION_PLAN_SCOPE="SYNTHETIC_FIXTURE_MATERIALIZATION_PLAN_DRAFT_ONLY"
FIXTURE_MATERIALIZATION_PLAN_STATE="SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_MATERIALIZATION_PLAN_DRAFTED"
FIXTURE_MATERIALIZATION_PLAN_GATES=("FIXTURE_BLUEPRINT_DIGEST_LOCKED","SYNTHETIC_INPUT_DIGEST_LOCKED","EXPECTED_RESULT_DIGEST_LOCKED","ROLLBACK_EXPECTATION_DIGEST_LOCKED","SEPARATE_ETERNIAN_REVIEW_REQUIRED")
_PREFIX="synthetic:activation-dry-run-fixture-materialization-plan:"
def _valid(v:object)->bool:return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _id_values(draft_id:str,draft_digest:str,review_digest:str)->str:
    return _PREFIX+canonical_digest({"draft_id":draft_id,"draft_digest":draft_digest,"review_digest":review_digest,"scope":FIXTURE_MATERIALIZATION_PLAN_SCOPE})[:32]
def _descriptor(blueprint:str,schema:str,synthetic_input:str,expected:str,rollback:str)->str:
    return canonical_digest({"blueprint":blueprint,"schema":schema,"input":synthetic_input,"expected":expected,"rollback":rollback,"content_present":False,"materialized":False})
def _valid_source(r:SyntheticActivationDryRunFixtureDraftReviewRecord)->bool:
    return (isinstance(r,SyntheticActivationDryRunFixtureDraftReviewRecord) and r.state is FixtureDraftReviewState.READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_MATERIALIZATION_PLAN
        and r.decision is FixtureDraftReviewDecision.PASS and r.review_digest==canonical_digest(r.review_value()) and _valid_draft(r.draft))

@dataclass(frozen=True)
class SyntheticActivationDryRunFixtureMaterializationPlan:
    sequence:int;plan_id:str;source_draft_id:str;source_draft_digest:str;source_review_id:str;source_review_digest:str
    blueprint_digest:str;fixture_schema_digest:str;synthetic_input_digest:str;expected_result_digest:str;rollback_expectation_digest:str
    artifact_descriptor_digest:str;scope:str;required_gates:tuple[str,...];state:str;planned_at:datetime;previous_digest:str;plan_digest:str
    synthetic_only:bool=True;separate_review_required:bool=True;fixture_content_present:bool=False;fixture_bytes_present:bool=False
    fixture_materialized:bool=False;fixture_file_created:bool=False;filesystem_written:bool=False;dry_run_executed:bool=False
    activation_recorded:bool=False;rollback_executed:bool=False;network_accessed:bool=False;money_movement_executed:bool=False;production_activation_allowed:bool=False
    def __post_init__(self)->None:
        if (self.sequence<=0 or not self.plan_id.startswith(_PREFIX) or any(not _valid(v) for v in (self.source_draft_digest,self.source_review_digest,self.blueprint_digest,
            self.fixture_schema_digest,self.synthetic_input_digest,self.expected_result_digest,self.rollback_expectation_digest,self.artifact_descriptor_digest,self.previous_digest))
            or self.scope!=FIXTURE_MATERIALIZATION_PLAN_SCOPE or self.required_gates!=FIXTURE_MATERIALIZATION_PLAN_GATES or self.state!=FIXTURE_MATERIALIZATION_PLAN_STATE
            or self.planned_at.tzinfo is None or not self.synthetic_only or not self.separate_review_required
            or any((self.fixture_content_present,self.fixture_bytes_present,self.fixture_materialized,self.fixture_file_created,self.filesystem_written,self.dry_run_executed,
                self.activation_recorded,self.rollback_executed,self.network_accessed,self.money_movement_executed,self.production_activation_allowed))
            or self.plan_digest!=canonical_digest(self.digest_value())):raise GovernanceRejected("valid metadata-only fixture materialization plan required")
    def digest_value(self)->dict[str,object]:
        return {"sequence":self.sequence,"plan_id":self.plan_id,"source_draft_id":self.source_draft_id,"source_draft_digest":self.source_draft_digest,
            "source_review_id":self.source_review_id,"source_review_digest":self.source_review_digest,"blueprint_digest":self.blueprint_digest,
            "fixture_schema_digest":self.fixture_schema_digest,"synthetic_input_digest":self.synthetic_input_digest,"expected_result_digest":self.expected_result_digest,
            "rollback_expectation_digest":self.rollback_expectation_digest,"artifact_descriptor_digest":self.artifact_descriptor_digest,"scope":self.scope,
            "required_gates":self.required_gates,"state":self.state,"planned_at":self.planned_at.isoformat(),"previous_digest":self.previous_digest,
            "synthetic_only":self.synthetic_only,"separate_review_required":self.separate_review_required,"fixture_content_present":self.fixture_content_present,
            "fixture_bytes_present":self.fixture_bytes_present,"fixture_materialized":self.fixture_materialized,"fixture_file_created":self.fixture_file_created,
            "filesystem_written":self.filesystem_written,"dry_run_executed":self.dry_run_executed,"activation_recorded":self.activation_recorded,
            "rollback_executed":self.rollback_executed,"network_accessed":self.network_accessed,"money_movement_executed":self.money_movement_executed,
            "production_activation_allowed":self.production_activation_allowed}

class SyntheticActivationDryRunFixtureMaterializationPlanBook:
    def __init__(self)->None:self._plans=[];self._by_review={};self._lock=RLock()
    @property
    def plans(self)->tuple[SyntheticActivationDryRunFixtureMaterializationPlan,...]:
        with self._lock:return tuple(self._plans)
    def plan_from_review(self,docket:SyntheticActivationDryRunFixtureDraftReviewDocket,draft_id:str,*,planned_at:datetime)->SyntheticActivationDryRunFixtureMaterializationPlan:
        if not isinstance(docket,SyntheticActivationDryRunFixtureDraftReviewDocket) or not docket.verify_chain():raise GovernanceRejected("intact typed fixture draft review docket required")
        if planned_at.tzinfo is None:raise GovernanceRejected("timezone-aware fixture materialization planning required")
        review=docket.ready_source(draft_id)
        if not _valid_source(review) or planned_at<review.reviewed_at:raise GovernanceRejected("passed fixture draft review required")
        before=docket.evidence()["report_digest"];d=review.draft
        with self._lock:
            if not self.verify_plan_chain():raise GovernanceRejected("existing fixture materialization plan chain invalid")
            old=self._by_review.get(review.review_digest)
            if old is not None:return old
            previous=self._plans[-1].plan_digest if self._plans else "0"*64;pid=_id_values(d.draft_id,d.draft_digest,review.review_digest)
            descriptor=_descriptor(d.blueprint_digest,d.fixture_schema_digest,d.synthetic_input_digest,d.expected_result_digest,d.rollback_expectation_digest)
            values={"sequence":len(self._plans)+1,"plan_id":pid,"source_draft_id":d.draft_id,"source_draft_digest":d.draft_digest,"source_review_id":review.review_id,
                "source_review_digest":review.review_digest,"blueprint_digest":d.blueprint_digest,"fixture_schema_digest":d.fixture_schema_digest,
                "synthetic_input_digest":d.synthetic_input_digest,"expected_result_digest":d.expected_result_digest,"rollback_expectation_digest":d.rollback_expectation_digest,
                "artifact_descriptor_digest":descriptor,"scope":FIXTURE_MATERIALIZATION_PLAN_SCOPE,"required_gates":FIXTURE_MATERIALIZATION_PLAN_GATES,
                "state":FIXTURE_MATERIALIZATION_PLAN_STATE,"planned_at":planned_at.isoformat(),"previous_digest":previous,"synthetic_only":True,
                "separate_review_required":True,"fixture_content_present":False,"fixture_bytes_present":False,"fixture_materialized":False,"fixture_file_created":False,
                "filesystem_written":False,"dry_run_executed":False,"activation_recorded":False,"rollback_executed":False,"network_accessed":False,
                "money_movement_executed":False,"production_activation_allowed":False}
            item=SyntheticActivationDryRunFixtureMaterializationPlan(len(self._plans)+1,pid,d.draft_id,d.draft_digest,review.review_id,review.review_digest,
                d.blueprint_digest,d.fixture_schema_digest,d.synthetic_input_digest,d.expected_result_digest,d.rollback_expectation_digest,descriptor,
                FIXTURE_MATERIALIZATION_PLAN_SCOPE,FIXTURE_MATERIALIZATION_PLAN_GATES,FIXTURE_MATERIALIZATION_PLAN_STATE,planned_at,previous,canonical_digest(values))
            if before!=docket.evidence()["report_digest"]:raise GovernanceRejected("fixture draft review changed during materialization planning")
            self._plans.append(item);self._by_review[review.review_digest]=item;return item
    def verify_plan_chain(self)->bool:
        with self._lock:
            previous="0"*64
            for n,i in enumerate(self._plans,1):
                if (i.sequence!=n or i.previous_digest!=previous or i.plan_id!=_id_values(i.source_draft_id,i.source_draft_digest,i.source_review_digest)
                    or i.artifact_descriptor_digest!=_descriptor(i.blueprint_digest,i.fixture_schema_digest,i.synthetic_input_digest,i.expected_result_digest,i.rollback_expectation_digest)
                    or i.plan_digest!=canonical_digest(i.digest_value()) or i.scope!=FIXTURE_MATERIALIZATION_PLAN_SCOPE or i.required_gates!=FIXTURE_MATERIALIZATION_PLAN_GATES
                    or i.state!=FIXTURE_MATERIALIZATION_PLAN_STATE or not i.synthetic_only or not i.separate_review_required
                    or any((i.fixture_content_present,i.fixture_bytes_present,i.fixture_materialized,i.fixture_file_created,i.filesystem_written,i.dry_run_executed,
                        i.activation_recorded,i.rollback_executed,i.network_accessed,i.money_movement_executed,i.production_activation_allowed))):return False
                previous=i.plan_digest
            return len(self._plans)==len(self._by_review) and all(self._by_review.get(i.source_review_digest) is i for i in self._plans)
    def evidence(self)->dict[str,object]:
        with self._lock:
            v={"schema":"nurion.pg.synthetic-activation-dry-run-fixture-materialization-plan-evidence.v1","mode":"UNREGISTERED_SYNTHETIC_ONLY",
               "plan_count":len(self._plans),"plan_digests":[i.plan_digest for i in self._plans],"plan_chain_valid":self.verify_plan_chain(),
               "scope":FIXTURE_MATERIALIZATION_PLAN_SCOPE,"maximum_state":FIXTURE_MATERIALIZATION_PLAN_STATE,"fixture_content_method_present":False,
               "fixture_materialization_method_present":False,"fixture_creation_method_present":False,"filesystem_write_method_present":False,
               "dry_run_execution_method_present":False,"activation_method_present":False,"rollback_execution_method_present":False,"network_access_method_present":False,
               "automatic_merge_method_present":False,"automatic_deploy_method_present":False,"credentials_used":False,"personal_data_used":False,
               "money_movement_executed":False,"production_activation_allowed":False};return {**v,"report_digest":canonical_digest(v)}
