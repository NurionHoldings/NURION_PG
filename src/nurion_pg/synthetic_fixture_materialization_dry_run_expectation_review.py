"""Independent review of observation-free materialization dry-run expectations."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from threading import RLock
from .arkaon.governance import GovernanceRejected,canonical_digest
from .synthetic_fixture_materialization_dry_run_expectations import EXPECTATION_GATES,EXPECTATION_SCOPE,EXPECTATION_STATE,SyntheticFixtureMaterializationDryRunExpectation,SyntheticFixtureMaterializationDryRunExpectationBook,_descriptor,_id,_valid_source

EXPECTATION_REVIEW_MAXIMUM_STATE="READY_FOR_SYNTHETIC_FIXTURE_MATERIALIZATION_DRY_RUN_ASSERTION_DRAFT"
_RID="synthetic:fixture-materialization-dry-run-expectation-review:"
_REVIEWER="synthetic:eternian-reviewer:fixture-materialization-dry-run-expectation:"
class ExpectationReviewDecision(StrEnum):PASS="PASS";HOLD="HOLD";REJECT="REJECT"
class ExpectationReviewState(StrEnum):
    PENDING_ETERNIAN_REVIEW="PENDING_ETERNIAN_REVIEW"
    READY_FOR_SYNTHETIC_FIXTURE_MATERIALIZATION_DRY_RUN_ASSERTION_DRAFT=EXPECTATION_REVIEW_MAXIMUM_STATE
    HELD="HELD";REJECTED="REJECTED"
_STATE={ExpectationReviewDecision.PASS:ExpectationReviewState.READY_FOR_SYNTHETIC_FIXTURE_MATERIALIZATION_DRY_RUN_ASSERTION_DRAFT,
        ExpectationReviewDecision.HOLD:ExpectationReviewState.HELD,ExpectationReviewDecision.REJECT:ExpectationReviewState.REJECTED}
def _valid(v:object)->bool:return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _valid_expectation(e:SyntheticFixtureMaterializationDryRunExpectation)->bool:
    source=e.source_review if isinstance(e,SyntheticFixtureMaterializationDryRunExpectation) else None
    scenario=source.scenario if _valid_source(source) else None
    return (scenario is not None and e.source_scenario_id==scenario.scenario_id and e.source_scenario_digest==scenario.scenario_digest
        and e.source_review_digest==source.review_digest and e.scenario_descriptor_digest==scenario.scenario_descriptor_digest
        and e.dry_run_contract_digest==scenario.dry_run_contract_digest and e.rollback_expectation_digest==scenario.rollback_expectation_digest
        and e.expectation_id==_id(e.source_scenario_id,e.source_scenario_digest,e.source_review_digest)
        and e.expectation_descriptor_digest==_descriptor(e.scenario_descriptor_digest,e.dry_run_contract_digest,e.rollback_expectation_digest)
        and e.scope==EXPECTATION_SCOPE and e.required_gates==EXPECTATION_GATES and e.state==EXPECTATION_STATE
        and e.expectation_digest==canonical_digest(e.digest_value()) and e.synthetic_only and e.separate_review_required
        and not any((e.observations_present,e.result_present,e.fixture_content_present,e.fixture_materialized,e.filesystem_written,
            e.dry_run_executed,e.activation_recorded,e.rollback_executed,e.network_accessed,e.money_movement_executed,e.production_activation_allowed)))
@dataclass(frozen=True)
class SyntheticFixtureMaterializationDryRunExpectationReviewRecord:
    sequence:int;expectation:SyntheticFixtureMaterializationDryRunExpectation;submitted_at:datetime;state:ExpectationReviewState;previous_digest:str;submission_digest:str
    review_id:str|None=None;reviewer_id:str|None=None;decision:ExpectationReviewDecision|None=None;findings_digest:str|None=None;reviewed_at:datetime|None=None;review_digest:str|None=None
    def __post_init__(self)->None:
        pending=self.state is ExpectationReviewState.PENDING_ETERNIAN_REVIEW;fields=(self.review_id,self.reviewer_id,self.decision,self.findings_digest,self.reviewed_at,self.review_digest)
        if (self.sequence<=0 or not _valid_expectation(self.expectation) or self.submitted_at.tzinfo is None or self.submitted_at<self.expectation.drafted_at
            or not _valid(self.previous_digest) or self.submission_digest!=canonical_digest(self.submission_value())
            or (pending and any(v is not None for v in fields)) or (not pending and (any(v is None for v in fields) or not self._valid_final()))):
            raise GovernanceRejected("valid expectation review record required")
    def _valid_final(self)->bool:
        return (isinstance(self.review_id,str) and self.review_id.startswith(_RID) and isinstance(self.reviewer_id,str) and self.reviewer_id.startswith(_REVIEWER)
            and isinstance(self.decision,ExpectationReviewDecision) and self.state is _STATE[self.decision] and _valid(self.findings_digest)
            and self.reviewed_at is not None and self.reviewed_at.tzinfo is not None and self.reviewed_at>=self.submitted_at
            and self.review_digest==canonical_digest(self.review_value()))
    def submission_value(self)->dict[str,object]:return {"sequence":self.sequence,"expectation_id":self.expectation.expectation_id,
        "expectation_digest":self.expectation.expectation_digest,"submitted_at":self.submitted_at.isoformat(),
        "submission_state":ExpectationReviewState.PENDING_ETERNIAN_REVIEW.value,"previous_digest":self.previous_digest}
    def review_value(self)->dict[str,object]:return {"expectation_id":self.expectation.expectation_id,"expectation_digest":self.expectation.expectation_digest,
        "review_id":self.review_id,"reviewer_id":self.reviewer_id,"decision":self.decision.value if self.decision else None,
        "findings_digest":self.findings_digest,"reviewed_at":self.reviewed_at.isoformat() if self.reviewed_at else None,"resulting_state":self.state.value,
        "fixture_materialization_allowed":False,"dry_run_execution_allowed":False,"filesystem_write_allowed":False,"activation_allowed":False}
class SyntheticFixtureMaterializationDryRunExpectationReviewDocket:
    def __init__(self)->None:self._records=[];self._by_expectation={};self._lock=RLock()
    @property
    def records(self)->tuple[SyntheticFixtureMaterializationDryRunExpectationReviewRecord,...]:
        with self._lock:return tuple(self._records)
    def submit(self,book:SyntheticFixtureMaterializationDryRunExpectationBook,expectation_id:str,*,submitted_at:datetime)->SyntheticFixtureMaterializationDryRunExpectationReviewRecord:
        if not isinstance(book,SyntheticFixtureMaterializationDryRunExpectationBook) or not book.verify_chain():raise GovernanceRejected("intact typed expectation book required")
        matches=[i for i in book.expectations if i.expectation_id==expectation_id]
        if submitted_at.tzinfo is None or len(matches)!=1:raise GovernanceRejected("valid expectation review submission required")
        source=matches[0];before=book.evidence()["report_digest"]
        with self._lock:
            if not self.verify_chain():raise GovernanceRejected("existing expectation review chain invalid")
            old=self._by_expectation.get(expectation_id)
            if old is not None:return old
            previous=self._records[-1].submission_digest if self._records else "0"*64;values={"sequence":len(self._records)+1,
                "expectation_id":source.expectation_id,"expectation_digest":source.expectation_digest,"submitted_at":submitted_at.isoformat(),
                "submission_state":ExpectationReviewState.PENDING_ETERNIAN_REVIEW.value,"previous_digest":previous}
            item=SyntheticFixtureMaterializationDryRunExpectationReviewRecord(len(self._records)+1,source,submitted_at,ExpectationReviewState.PENDING_ETERNIAN_REVIEW,previous,canonical_digest(values))
            if before!=book.evidence()["report_digest"]:raise GovernanceRejected("expectation changed during review submission")
            self._records.append(item);self._by_expectation[expectation_id]=item;return item
    def record_eternian_review(self,expectation_id:str,*,review_id:str,reviewer_id:str,decision:ExpectationReviewDecision,findings_digest:str,reviewed_at:datetime)->SyntheticFixtureMaterializationDryRunExpectationReviewRecord:
        if (not isinstance(review_id,str) or not review_id.startswith(_RID) or not isinstance(reviewer_id,str) or not reviewer_id.startswith(_REVIEWER)
            or not isinstance(decision,ExpectationReviewDecision) or not _valid(findings_digest) or reviewed_at.tzinfo is None):raise GovernanceRejected("valid expectation review metadata required")
        with self._lock:
            if not self.verify_chain():raise GovernanceRejected("existing expectation review chain invalid")
            current=self._by_expectation.get(expectation_id)
            if current is None:raise GovernanceRejected("unknown expectation")
            values={"expectation_id":current.expectation.expectation_id,"expectation_digest":current.expectation.expectation_digest,
                "review_id":review_id,"reviewer_id":reviewer_id,"decision":decision.value,"findings_digest":findings_digest,
                "reviewed_at":reviewed_at.isoformat(),"resulting_state":_STATE[decision].value,"fixture_materialization_allowed":False,
                "dry_run_execution_allowed":False,"filesystem_write_allowed":False,"activation_allowed":False};digest=canonical_digest(values)
            if current.state is not ExpectationReviewState.PENDING_ETERNIAN_REVIEW:
                if current.review_digest==digest:return current
                raise GovernanceRejected("expectation review is immutable")
            item=SyntheticFixtureMaterializationDryRunExpectationReviewRecord(current.sequence,current.expectation,current.submitted_at,
                _STATE[decision],current.previous_digest,current.submission_digest,review_id,reviewer_id,decision,findings_digest,reviewed_at,digest)
            self._records[current.sequence-1]=item;self._by_expectation[expectation_id]=item;return item
    def ready_source(self,expectation_id:str)->SyntheticFixtureMaterializationDryRunExpectationReviewRecord:
        with self._lock:
            item=self._by_expectation.get(expectation_id)
            if item is None or item.state is not ExpectationReviewState.READY_FOR_SYNTHETIC_FIXTURE_MATERIALIZATION_DRY_RUN_ASSERTION_DRAFT or not self.verify_chain():raise GovernanceRejected("passed expectation review required")
            return item
    def verify_chain(self)->bool:
        with self._lock:
            previous="0"*64
            for n,i in enumerate(self._records,1):
                pending=i.state is ExpectationReviewState.PENDING_ETERNIAN_REVIEW;fields=(i.review_id,i.reviewer_id,i.decision,i.findings_digest,i.reviewed_at,i.review_digest)
                if (i.sequence!=n or i.previous_digest!=previous or not _valid_expectation(i.expectation) or i.submitted_at.tzinfo is None
                    or i.submitted_at<i.expectation.drafted_at or i.submission_digest!=canonical_digest(i.submission_value())
                    or (pending and any(v is not None for v in fields)) or (not pending and (any(v is None for v in fields) or not i._valid_final()))):return False
                previous=i.submission_digest
            return len(self._records)==len(self._by_expectation) and all(self._by_expectation.get(i.expectation.expectation_id) is i for i in self._records)
    def evidence(self)->dict[str,object]:
        with self._lock:
            v={"schema":"nurion.pg.synthetic-fixture-materialization-dry-run-expectation-review-evidence.v1","mode":"UNREGISTERED_SYNTHETIC_ONLY",
               "record_count":len(self._records),"submission_digests":[i.submission_digest for i in self._records],
               "review_digests":[i.review_digest for i in self._records if i.review_digest],"review_chain_valid":self.verify_chain(),
               "maximum_state":EXPECTATION_REVIEW_MAXIMUM_STATE,"fixture_materialization_method_present":False,
               "filesystem_write_method_present":False,"dry_run_execution_method_present":False,"activation_method_present":False,
               "network_access_method_present":False,"automatic_merge_method_present":False,"automatic_deploy_method_present":False,
               "credentials_used":False,"personal_data_used":False,"money_movement_executed":False,"production_activation_allowed":False}
            return {**v,"report_digest":canonical_digest(v)}
