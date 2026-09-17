"""Observation-free expectations for synthetic fixture materialization dry-runs."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from .arkaon.governance import GovernanceRejected,canonical_digest
from .synthetic_fixture_materialization_dry_run_scenario_review import ScenarioReviewDecision,ScenarioReviewState,SyntheticFixtureMaterializationDryRunScenarioReviewDocket,SyntheticFixtureMaterializationDryRunScenarioReviewRecord,_valid_scenario

EXPECTATION_SCOPE="SYNTHETIC_FIXTURE_MATERIALIZATION_DRY_RUN_EXPECTATION_DRAFT_ONLY"
EXPECTATION_STATE="SYNTHETIC_FIXTURE_MATERIALIZATION_DRY_RUN_EXPECTATION_DRAFTED"
EXPECTATION_GATES=("SOURCE_SCENARIO_REVIEW_PASS_LOCKED","SCENARIO_DESCRIPTOR_DIGEST_LOCKED","ROLLBACK_EXPECTATION_DIGEST_LOCKED","NO_OBSERVATIONS_OR_EXECUTION","SEPARATE_ETERNIAN_REVIEW_REQUIRED")
_PREFIX="synthetic:fixture-materialization-dry-run-expectation:"
def _valid(v:object)->bool:return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _valid_source(r:SyntheticFixtureMaterializationDryRunScenarioReviewRecord)->bool:
    return (isinstance(r,SyntheticFixtureMaterializationDryRunScenarioReviewRecord) and r.sequence>0
        and r.submitted_at.tzinfo is not None and r.submitted_at>=r.scenario.drafted_at and _valid(r.previous_digest)
        and r.submission_digest==canonical_digest(r.submission_value())
        and r.state is ScenarioReviewState.READY_FOR_SYNTHETIC_FIXTURE_MATERIALIZATION_DRY_RUN_EXPECTATION_DRAFT
        and r.decision is ScenarioReviewDecision.PASS and r._valid_final() and _valid_scenario(r.scenario))
def _id(scenario_id:str,scenario_digest:str,review_digest:str)->str:
    return _PREFIX+canonical_digest({"scenario_id":scenario_id,"scenario_digest":scenario_digest,"review_digest":review_digest,"scope":EXPECTATION_SCOPE})[:32]
def _descriptor(scenario:str,contract:str,rollback:str)->str:
    return canonical_digest({"scenario":scenario,"contract":contract,"rollback":rollback,"observations_present":False,
        "result_present":False,"materialization_executed":False,"dry_run_executed":False})
@dataclass(frozen=True)
class SyntheticFixtureMaterializationDryRunExpectation:
    sequence:int;source_review:SyntheticFixtureMaterializationDryRunScenarioReviewRecord;expectation_id:str
    source_scenario_id:str;source_scenario_digest:str;source_review_digest:str;scenario_descriptor_digest:str
    dry_run_contract_digest:str;rollback_expectation_digest:str;expectation_descriptor_digest:str
    scope:str;required_gates:tuple[str,...];state:str;drafted_at:datetime;previous_digest:str;expectation_digest:str
    synthetic_only:bool=True;separate_review_required:bool=True;observations_present:bool=False;result_present:bool=False
    fixture_content_present:bool=False;fixture_materialized:bool=False;filesystem_written:bool=False;dry_run_executed:bool=False
    activation_recorded:bool=False;rollback_executed:bool=False;network_accessed:bool=False;money_movement_executed:bool=False;production_activation_allowed:bool=False
    def __post_init__(self)->None:
        source=self.source_review;scenario=source.scenario if _valid_source(source) else None
        if (self.sequence<=0 or scenario is None or self.source_scenario_id!=scenario.scenario_id or self.source_scenario_digest!=scenario.scenario_digest
            or self.source_review_digest!=source.review_digest or self.scenario_descriptor_digest!=scenario.scenario_descriptor_digest
            or self.dry_run_contract_digest!=scenario.dry_run_contract_digest or self.rollback_expectation_digest!=scenario.rollback_expectation_digest
            or self.expectation_id!=_id(self.source_scenario_id,self.source_scenario_digest,self.source_review_digest)
            or self.expectation_descriptor_digest!=_descriptor(self.scenario_descriptor_digest,self.dry_run_contract_digest,self.rollback_expectation_digest)
            or self.scope!=EXPECTATION_SCOPE or self.required_gates!=EXPECTATION_GATES or self.state!=EXPECTATION_STATE or self.drafted_at.tzinfo is None
            or not self.synthetic_only or not self.separate_review_required or any((self.observations_present,self.result_present,self.fixture_content_present,
                self.fixture_materialized,self.filesystem_written,self.dry_run_executed,self.activation_recorded,self.rollback_executed,
                self.network_accessed,self.money_movement_executed,self.production_activation_allowed))
            or self.expectation_digest!=canonical_digest(self.digest_value())):raise GovernanceRejected("valid observation-free expectation required")
    def digest_value(self)->dict[str,object]:
        return {k:(v.isoformat() if isinstance(v,datetime) else v) for k,v in self.__dict__.items() if k not in ("source_review","expectation_digest")}
class SyntheticFixtureMaterializationDryRunExpectationBook:
    def __init__(self)->None:self._items=[];self._by_review={};self._lock=RLock()
    @property
    def expectations(self)->tuple[SyntheticFixtureMaterializationDryRunExpectation,...]:
        with self._lock:return tuple(self._items)
    def draft_from_review(self,docket:SyntheticFixtureMaterializationDryRunScenarioReviewDocket,scenario_id:str,*,drafted_at:datetime)->SyntheticFixtureMaterializationDryRunExpectation:
        if not isinstance(docket,SyntheticFixtureMaterializationDryRunScenarioReviewDocket) or not docket.verify_chain():raise GovernanceRejected("intact typed scenario review docket required")
        review=docket.ready_source(scenario_id)
        if drafted_at.tzinfo is None or not _valid_source(review) or drafted_at<review.reviewed_at:raise GovernanceRejected("passed scenario review required")
        before=docket.evidence()["report_digest"];scenario=review.scenario
        with self._lock:
            if not self.verify_chain():raise GovernanceRejected("existing expectation chain invalid")
            old=self._by_review.get(review.review_digest)
            if old is not None:return old
            previous=self._items[-1].expectation_digest if self._items else "0"*64;eid=_id(scenario.scenario_id,scenario.scenario_digest,review.review_digest)
            descriptor=_descriptor(scenario.scenario_descriptor_digest,scenario.dry_run_contract_digest,scenario.rollback_expectation_digest)
            values={"sequence":len(self._items)+1,"expectation_id":eid,"source_scenario_id":scenario.scenario_id,
                "source_scenario_digest":scenario.scenario_digest,"source_review_digest":review.review_digest,
                "scenario_descriptor_digest":scenario.scenario_descriptor_digest,"dry_run_contract_digest":scenario.dry_run_contract_digest,
                "rollback_expectation_digest":scenario.rollback_expectation_digest,"expectation_descriptor_digest":descriptor,
                "scope":EXPECTATION_SCOPE,"required_gates":EXPECTATION_GATES,"state":EXPECTATION_STATE,"drafted_at":drafted_at.isoformat(),
                "previous_digest":previous,"synthetic_only":True,"separate_review_required":True,"observations_present":False,
                "result_present":False,"fixture_content_present":False,"fixture_materialized":False,"filesystem_written":False,
                "dry_run_executed":False,"activation_recorded":False,"rollback_executed":False,"network_accessed":False,
                "money_movement_executed":False,"production_activation_allowed":False}
            item=SyntheticFixtureMaterializationDryRunExpectation(len(self._items)+1,review,eid,scenario.scenario_id,scenario.scenario_digest,
                review.review_digest,scenario.scenario_descriptor_digest,scenario.dry_run_contract_digest,scenario.rollback_expectation_digest,
                descriptor,EXPECTATION_SCOPE,EXPECTATION_GATES,EXPECTATION_STATE,drafted_at,previous,canonical_digest(values))
            if before!=docket.evidence()["report_digest"]:raise GovernanceRejected("source changed during expectation drafting")
            self._items.append(item);self._by_review[review.review_digest]=item;return item
    def verify_chain(self)->bool:
        with self._lock:
            previous="0"*64
            for n,i in enumerate(self._items,1):
                try:SyntheticFixtureMaterializationDryRunExpectation(**i.__dict__)
                except GovernanceRejected:return False
                if i.sequence!=n or i.previous_digest!=previous:return False
                previous=i.expectation_digest
            return len(self._items)==len(self._by_review) and all(self._by_review.get(i.source_review_digest) is i for i in self._items)
    def evidence(self)->dict[str,object]:
        with self._lock:
            v={"schema":"nurion.pg.synthetic-fixture-materialization-dry-run-expectation-evidence.v1","mode":"UNREGISTERED_SYNTHETIC_ONLY",
               "expectation_count":len(self._items),"expectation_digests":[i.expectation_digest for i in self._items],"expectation_chain_valid":self.verify_chain(),
               "scope":EXPECTATION_SCOPE,"maximum_state":EXPECTATION_STATE,"observations_method_present":False,"fixture_materialization_method_present":False,
               "filesystem_write_method_present":False,"dry_run_execution_method_present":False,"activation_method_present":False,
               "network_access_method_present":False,"automatic_merge_method_present":False,"automatic_deploy_method_present":False,
               "credentials_used":False,"personal_data_used":False,"money_movement_executed":False,"production_activation_allowed":False}
            return {**v,"report_digest":canonical_digest(v)}
