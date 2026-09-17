"""Content-free synthetic fixture materialization dry-run scenarios."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from .arkaon.governance import GovernanceRejected,canonical_digest
from .synthetic_activation_dry_run_fixture_materialization_dry_run_plan_review import MaterializationDryRunPlanReviewDecision,MaterializationDryRunPlanReviewState,SyntheticActivationDryRunFixtureMaterializationDryRunPlanReviewDocket,SyntheticActivationDryRunFixtureMaterializationDryRunPlanReviewRecord,_valid_plan

SCENARIO_SCOPE="SYNTHETIC_FIXTURE_MATERIALIZATION_DRY_RUN_SCENARIO_DRAFT_ONLY"
SCENARIO_STATE="SYNTHETIC_FIXTURE_MATERIALIZATION_DRY_RUN_SCENARIO_DRAFTED"
SCENARIO_GATES=("SOURCE_DRY_RUN_PLAN_REVIEW_PASS_LOCKED","DRY_RUN_CONTRACT_DIGEST_LOCKED","NO_CONTENT_BYTES_PATH_OR_FILE","NO_EXECUTION","SEPARATE_ETERNIAN_REVIEW_REQUIRED")
_PREFIX="synthetic:fixture-materialization-dry-run-scenario:"
def _valid(v:object)->bool:return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _valid_source(r:SyntheticActivationDryRunFixtureMaterializationDryRunPlanReviewRecord)->bool:
    return (isinstance(r,SyntheticActivationDryRunFixtureMaterializationDryRunPlanReviewRecord) and r.sequence>0
        and r.submitted_at.tzinfo is not None and r.submitted_at>=r.plan.planned_at and _valid(r.previous_digest)
        and r.submission_digest==canonical_digest(r.submission_value())
        and r.state is MaterializationDryRunPlanReviewState.READY_FOR_SYNTHETIC_FIXTURE_MATERIALIZATION_DRY_RUN_SCENARIO_DRAFT
        and r.decision is MaterializationDryRunPlanReviewDecision.PASS and r._valid_final() and _valid_plan(r.plan))
def _id(plan_id:str,plan_digest:str,review_digest:str)->str:
    return _PREFIX+canonical_digest({"plan_id":plan_id,"plan_digest":plan_digest,"review_digest":review_digest,"scope":SCENARIO_SCOPE})[:32]
def _descriptor(contract:str,specification:str,rollback:str)->str:
    return canonical_digest({"contract":contract,"specification":specification,"rollback":rollback,"observations_present":False,
        "fixture_content_present":False,"materialization_executed":False,"dry_run_executed":False})
@dataclass(frozen=True)
class SyntheticFixtureMaterializationDryRunScenario:
    sequence:int;source_review:SyntheticActivationDryRunFixtureMaterializationDryRunPlanReviewRecord;scenario_id:str
    source_plan_id:str;source_plan_digest:str;source_review_digest:str;dry_run_contract_digest:str
    specification_descriptor_digest:str;rollback_expectation_digest:str;scenario_descriptor_digest:str
    scope:str;required_gates:tuple[str,...];state:str;drafted_at:datetime;previous_digest:str;scenario_digest:str
    synthetic_only:bool=True;separate_review_required:bool=True;observations_present:bool=False;fixture_content_present:bool=False
    fixture_bytes_present:bool=False;filesystem_path_present:bool=False;fixture_file_present:bool=False;fixture_materialized:bool=False
    filesystem_written:bool=False;dry_run_executed:bool=False;activation_recorded:bool=False;rollback_executed:bool=False
    network_accessed:bool=False;money_movement_executed:bool=False;production_activation_allowed:bool=False
    def __post_init__(self)->None:
        source=self.source_review;plan=source.plan if _valid_source(source) else None
        if (self.sequence<=0 or plan is None or self.source_plan_id!=plan.plan_id or self.source_plan_digest!=plan.plan_digest
            or self.source_review_digest!=source.review_digest or self.dry_run_contract_digest!=plan.dry_run_contract_digest
            or self.specification_descriptor_digest!=plan.specification_descriptor_digest or self.rollback_expectation_digest!=plan.rollback_expectation_digest
            or self.scenario_id!=_id(self.source_plan_id,self.source_plan_digest,self.source_review_digest)
            or self.scenario_descriptor_digest!=_descriptor(self.dry_run_contract_digest,self.specification_descriptor_digest,self.rollback_expectation_digest)
            or self.scope!=SCENARIO_SCOPE or self.required_gates!=SCENARIO_GATES or self.state!=SCENARIO_STATE or self.drafted_at.tzinfo is None
            or not self.synthetic_only or not self.separate_review_required or any((self.observations_present,self.fixture_content_present,
                self.fixture_bytes_present,self.filesystem_path_present,self.fixture_file_present,self.fixture_materialized,self.filesystem_written,
                self.dry_run_executed,self.activation_recorded,self.rollback_executed,self.network_accessed,self.money_movement_executed,self.production_activation_allowed))
            or self.scenario_digest!=canonical_digest(self.digest_value())):raise GovernanceRejected("valid content-free materialization dry-run scenario required")
    def digest_value(self)->dict[str,object]:
        return {k:(v.isoformat() if isinstance(v,datetime) else v) for k,v in self.__dict__.items() if k not in ("source_review","scenario_digest")}
class SyntheticFixtureMaterializationDryRunScenarioBook:
    def __init__(self)->None:self._items=[];self._by_review={};self._lock=RLock()
    @property
    def scenarios(self)->tuple[SyntheticFixtureMaterializationDryRunScenario,...]:
        with self._lock:return tuple(self._items)
    def draft_from_review(self,docket:SyntheticActivationDryRunFixtureMaterializationDryRunPlanReviewDocket,plan_id:str,*,drafted_at:datetime)->SyntheticFixtureMaterializationDryRunScenario:
        if not isinstance(docket,SyntheticActivationDryRunFixtureMaterializationDryRunPlanReviewDocket) or not docket.verify_chain():raise GovernanceRejected("intact typed dry-run plan review docket required")
        review=docket.ready_source(plan_id)
        if drafted_at.tzinfo is None or not _valid_source(review) or drafted_at<review.reviewed_at:raise GovernanceRejected("passed dry-run plan review required")
        before=docket.evidence()["report_digest"];plan=review.plan
        with self._lock:
            if not self.verify_chain():raise GovernanceRejected("existing scenario chain invalid")
            old=self._by_review.get(review.review_digest)
            if old is not None:return old
            previous=self._items[-1].scenario_digest if self._items else "0"*64;sid=_id(plan.plan_id,plan.plan_digest,review.review_digest)
            descriptor=_descriptor(plan.dry_run_contract_digest,plan.specification_descriptor_digest,plan.rollback_expectation_digest)
            values={"sequence":len(self._items)+1,"scenario_id":sid,"source_plan_id":plan.plan_id,"source_plan_digest":plan.plan_digest,
                "source_review_digest":review.review_digest,"dry_run_contract_digest":plan.dry_run_contract_digest,
                "specification_descriptor_digest":plan.specification_descriptor_digest,"rollback_expectation_digest":plan.rollback_expectation_digest,
                "scenario_descriptor_digest":descriptor,"scope":SCENARIO_SCOPE,"required_gates":SCENARIO_GATES,"state":SCENARIO_STATE,
                "drafted_at":drafted_at.isoformat(),"previous_digest":previous,"synthetic_only":True,"separate_review_required":True,
                "observations_present":False,"fixture_content_present":False,"fixture_bytes_present":False,"filesystem_path_present":False,
                "fixture_file_present":False,"fixture_materialized":False,"filesystem_written":False,"dry_run_executed":False,
                "activation_recorded":False,"rollback_executed":False,"network_accessed":False,"money_movement_executed":False,"production_activation_allowed":False}
            item=SyntheticFixtureMaterializationDryRunScenario(len(self._items)+1,review,sid,plan.plan_id,plan.plan_digest,review.review_digest,
                plan.dry_run_contract_digest,plan.specification_descriptor_digest,plan.rollback_expectation_digest,descriptor,SCENARIO_SCOPE,
                SCENARIO_GATES,SCENARIO_STATE,drafted_at,previous,canonical_digest(values))
            if before!=docket.evidence()["report_digest"]:raise GovernanceRejected("source changed during scenario drafting")
            self._items.append(item);self._by_review[review.review_digest]=item;return item
    def verify_chain(self)->bool:
        with self._lock:
            previous="0"*64
            for n,i in enumerate(self._items,1):
                try:SyntheticFixtureMaterializationDryRunScenario(**i.__dict__)
                except GovernanceRejected:return False
                if i.sequence!=n or i.previous_digest!=previous:return False
                previous=i.scenario_digest
            return len(self._items)==len(self._by_review) and all(self._by_review.get(i.source_review_digest) is i for i in self._items)
    def evidence(self)->dict[str,object]:
        with self._lock:
            v={"schema":"nurion.pg.synthetic-fixture-materialization-dry-run-scenario-evidence.v1","mode":"UNREGISTERED_SYNTHETIC_ONLY",
               "scenario_count":len(self._items),"scenario_digests":[i.scenario_digest for i in self._items],"scenario_chain_valid":self.verify_chain(),
               "scope":SCENARIO_SCOPE,"maximum_state":SCENARIO_STATE,"fixture_content_method_present":False,"fixture_materialization_method_present":False,
               "filesystem_write_method_present":False,"dry_run_execution_method_present":False,"activation_method_present":False,
               "network_access_method_present":False,"automatic_merge_method_present":False,"automatic_deploy_method_present":False,
               "credentials_used":False,"personal_data_used":False,"money_movement_executed":False,"production_activation_allowed":False}
            return {**v,"report_digest":canonical_digest(v)}
