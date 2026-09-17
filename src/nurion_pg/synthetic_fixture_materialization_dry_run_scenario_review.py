"""Independent review of content-free materialization dry-run scenarios."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from threading import RLock
from .arkaon.governance import GovernanceRejected,canonical_digest
from .synthetic_fixture_materialization_dry_run_scenarios import SCENARIO_GATES,SCENARIO_SCOPE,SCENARIO_STATE,SyntheticFixtureMaterializationDryRunScenario,SyntheticFixtureMaterializationDryRunScenarioBook,_descriptor,_id,_valid_source

SCENARIO_REVIEW_MAXIMUM_STATE="READY_FOR_SYNTHETIC_FIXTURE_MATERIALIZATION_DRY_RUN_EXPECTATION_DRAFT"
_RID="synthetic:fixture-materialization-dry-run-scenario-review:"
_REVIEWER="synthetic:eternian-reviewer:fixture-materialization-dry-run-scenario:"
class ScenarioReviewDecision(StrEnum):PASS="PASS";HOLD="HOLD";REJECT="REJECT"
class ScenarioReviewState(StrEnum):
    PENDING_ETERNIAN_REVIEW="PENDING_ETERNIAN_REVIEW"
    READY_FOR_SYNTHETIC_FIXTURE_MATERIALIZATION_DRY_RUN_EXPECTATION_DRAFT=SCENARIO_REVIEW_MAXIMUM_STATE
    HELD="HELD";REJECTED="REJECTED"
_STATE={ScenarioReviewDecision.PASS:ScenarioReviewState.READY_FOR_SYNTHETIC_FIXTURE_MATERIALIZATION_DRY_RUN_EXPECTATION_DRAFT,
        ScenarioReviewDecision.HOLD:ScenarioReviewState.HELD,ScenarioReviewDecision.REJECT:ScenarioReviewState.REJECTED}
def _valid(v:object)->bool:return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _valid_scenario(s:SyntheticFixtureMaterializationDryRunScenario)->bool:
    source=s.source_review if isinstance(s,SyntheticFixtureMaterializationDryRunScenario) else None
    plan=source.plan if _valid_source(source) else None
    return (plan is not None and s.source_plan_id==plan.plan_id and s.source_plan_digest==plan.plan_digest and s.source_review_digest==source.review_digest
        and s.dry_run_contract_digest==plan.dry_run_contract_digest and s.specification_descriptor_digest==plan.specification_descriptor_digest
        and s.rollback_expectation_digest==plan.rollback_expectation_digest and s.scenario_id==_id(s.source_plan_id,s.source_plan_digest,s.source_review_digest)
        and s.scenario_descriptor_digest==_descriptor(s.dry_run_contract_digest,s.specification_descriptor_digest,s.rollback_expectation_digest)
        and s.scope==SCENARIO_SCOPE and s.required_gates==SCENARIO_GATES and s.state==SCENARIO_STATE and s.scenario_digest==canonical_digest(s.digest_value())
        and s.synthetic_only and s.separate_review_required and not any((s.observations_present,s.fixture_content_present,s.fixture_bytes_present,
            s.filesystem_path_present,s.fixture_file_present,s.fixture_materialized,s.filesystem_written,s.dry_run_executed,s.activation_recorded,
            s.rollback_executed,s.network_accessed,s.money_movement_executed,s.production_activation_allowed)))
@dataclass(frozen=True)
class SyntheticFixtureMaterializationDryRunScenarioReviewRecord:
    sequence:int;scenario:SyntheticFixtureMaterializationDryRunScenario;submitted_at:datetime;state:ScenarioReviewState;previous_digest:str;submission_digest:str
    review_id:str|None=None;reviewer_id:str|None=None;decision:ScenarioReviewDecision|None=None;findings_digest:str|None=None;reviewed_at:datetime|None=None;review_digest:str|None=None
    def __post_init__(self)->None:
        pending=self.state is ScenarioReviewState.PENDING_ETERNIAN_REVIEW;fields=(self.review_id,self.reviewer_id,self.decision,self.findings_digest,self.reviewed_at,self.review_digest)
        if (self.sequence<=0 or not _valid_scenario(self.scenario) or self.submitted_at.tzinfo is None or self.submitted_at<self.scenario.drafted_at
            or not _valid(self.previous_digest) or self.submission_digest!=canonical_digest(self.submission_value())
            or (pending and any(v is not None for v in fields)) or (not pending and (any(v is None for v in fields) or not self._valid_final()))):
            raise GovernanceRejected("valid scenario review record required")
    def _valid_final(self)->bool:
        return (isinstance(self.review_id,str) and self.review_id.startswith(_RID) and isinstance(self.reviewer_id,str) and self.reviewer_id.startswith(_REVIEWER)
            and isinstance(self.decision,ScenarioReviewDecision) and self.state is _STATE[self.decision] and _valid(self.findings_digest)
            and self.reviewed_at is not None and self.reviewed_at.tzinfo is not None and self.reviewed_at>=self.submitted_at
            and self.review_digest==canonical_digest(self.review_value()))
    def submission_value(self)->dict[str,object]:return {"sequence":self.sequence,"scenario_id":self.scenario.scenario_id,"scenario_digest":self.scenario.scenario_digest,
        "submitted_at":self.submitted_at.isoformat(),"submission_state":ScenarioReviewState.PENDING_ETERNIAN_REVIEW.value,"previous_digest":self.previous_digest}
    def review_value(self)->dict[str,object]:return {"scenario_id":self.scenario.scenario_id,"scenario_digest":self.scenario.scenario_digest,
        "review_id":self.review_id,"reviewer_id":self.reviewer_id,"decision":self.decision.value if self.decision else None,
        "findings_digest":self.findings_digest,"reviewed_at":self.reviewed_at.isoformat() if self.reviewed_at else None,"resulting_state":self.state.value,
        "fixture_materialization_allowed":False,"dry_run_execution_allowed":False,"filesystem_write_allowed":False,"activation_allowed":False}
class SyntheticFixtureMaterializationDryRunScenarioReviewDocket:
    def __init__(self)->None:self._records=[];self._by_scenario={};self._lock=RLock()
    @property
    def records(self)->tuple[SyntheticFixtureMaterializationDryRunScenarioReviewRecord,...]:
        with self._lock:return tuple(self._records)
    def submit(self,book:SyntheticFixtureMaterializationDryRunScenarioBook,scenario_id:str,*,submitted_at:datetime)->SyntheticFixtureMaterializationDryRunScenarioReviewRecord:
        if not isinstance(book,SyntheticFixtureMaterializationDryRunScenarioBook) or not book.verify_chain():raise GovernanceRejected("intact typed scenario book required")
        matches=[i for i in book.scenarios if i.scenario_id==scenario_id]
        if submitted_at.tzinfo is None or len(matches)!=1:raise GovernanceRejected("valid scenario review submission required")
        source=matches[0];before=book.evidence()["report_digest"]
        with self._lock:
            if not self.verify_chain():raise GovernanceRejected("existing scenario review chain invalid")
            old=self._by_scenario.get(scenario_id)
            if old is not None:return old
            previous=self._records[-1].submission_digest if self._records else "0"*64;values={"sequence":len(self._records)+1,
                "scenario_id":source.scenario_id,"scenario_digest":source.scenario_digest,"submitted_at":submitted_at.isoformat(),
                "submission_state":ScenarioReviewState.PENDING_ETERNIAN_REVIEW.value,"previous_digest":previous}
            item=SyntheticFixtureMaterializationDryRunScenarioReviewRecord(len(self._records)+1,source,submitted_at,ScenarioReviewState.PENDING_ETERNIAN_REVIEW,previous,canonical_digest(values))
            if before!=book.evidence()["report_digest"]:raise GovernanceRejected("scenario changed during review submission")
            self._records.append(item);self._by_scenario[scenario_id]=item;return item
    def record_eternian_review(self,scenario_id:str,*,review_id:str,reviewer_id:str,decision:ScenarioReviewDecision,findings_digest:str,reviewed_at:datetime)->SyntheticFixtureMaterializationDryRunScenarioReviewRecord:
        if (not isinstance(review_id,str) or not review_id.startswith(_RID) or not isinstance(reviewer_id,str) or not reviewer_id.startswith(_REVIEWER)
            or not isinstance(decision,ScenarioReviewDecision) or not _valid(findings_digest) or reviewed_at.tzinfo is None):raise GovernanceRejected("valid scenario review metadata required")
        with self._lock:
            if not self.verify_chain():raise GovernanceRejected("existing scenario review chain invalid")
            current=self._by_scenario.get(scenario_id)
            if current is None:raise GovernanceRejected("unknown scenario")
            values={"scenario_id":current.scenario.scenario_id,"scenario_digest":current.scenario.scenario_digest,"review_id":review_id,
                "reviewer_id":reviewer_id,"decision":decision.value,"findings_digest":findings_digest,"reviewed_at":reviewed_at.isoformat(),
                "resulting_state":_STATE[decision].value,"fixture_materialization_allowed":False,"dry_run_execution_allowed":False,
                "filesystem_write_allowed":False,"activation_allowed":False};digest=canonical_digest(values)
            if current.state is not ScenarioReviewState.PENDING_ETERNIAN_REVIEW:
                if current.review_digest==digest:return current
                raise GovernanceRejected("scenario review is immutable")
            item=SyntheticFixtureMaterializationDryRunScenarioReviewRecord(current.sequence,current.scenario,current.submitted_at,_STATE[decision],
                current.previous_digest,current.submission_digest,review_id,reviewer_id,decision,findings_digest,reviewed_at,digest)
            self._records[current.sequence-1]=item;self._by_scenario[scenario_id]=item;return item
    def ready_source(self,scenario_id:str)->SyntheticFixtureMaterializationDryRunScenarioReviewRecord:
        with self._lock:
            item=self._by_scenario.get(scenario_id)
            if item is None or item.state is not ScenarioReviewState.READY_FOR_SYNTHETIC_FIXTURE_MATERIALIZATION_DRY_RUN_EXPECTATION_DRAFT or not self.verify_chain():
                raise GovernanceRejected("passed scenario review required")
            return item
    def verify_chain(self)->bool:
        with self._lock:
            previous="0"*64
            for n,i in enumerate(self._records,1):
                pending=i.state is ScenarioReviewState.PENDING_ETERNIAN_REVIEW;fields=(i.review_id,i.reviewer_id,i.decision,i.findings_digest,i.reviewed_at,i.review_digest)
                if (i.sequence!=n or i.previous_digest!=previous or not _valid_scenario(i.scenario) or i.submitted_at.tzinfo is None
                    or i.submitted_at<i.scenario.drafted_at or i.submission_digest!=canonical_digest(i.submission_value())
                    or (pending and any(v is not None for v in fields)) or (not pending and (any(v is None for v in fields) or not i._valid_final()))):return False
                previous=i.submission_digest
            return len(self._records)==len(self._by_scenario) and all(self._by_scenario.get(i.scenario.scenario_id) is i for i in self._records)
    def evidence(self)->dict[str,object]:
        with self._lock:
            v={"schema":"nurion.pg.synthetic-fixture-materialization-dry-run-scenario-review-evidence.v1","mode":"UNREGISTERED_SYNTHETIC_ONLY",
               "record_count":len(self._records),"submission_digests":[i.submission_digest for i in self._records],
               "review_digests":[i.review_digest for i in self._records if i.review_digest],
               "review_chain_valid":self.verify_chain(),"maximum_state":SCENARIO_REVIEW_MAXIMUM_STATE,
               "fixture_materialization_method_present":False,"filesystem_write_method_present":False,"dry_run_execution_method_present":False,
               "activation_method_present":False,"network_access_method_present":False,"automatic_merge_method_present":False,
               "automatic_deploy_method_present":False,"credentials_used":False,"personal_data_used":False,"money_movement_executed":False,
               "production_activation_allowed":False};return {**v,"report_digest":canonical_digest(v)}
