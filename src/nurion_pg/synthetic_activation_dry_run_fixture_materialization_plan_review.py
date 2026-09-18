"""Independent review of metadata-only synthetic fixture materialization plans."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from threading import RLock
from .arkaon.governance import GovernanceRejected,canonical_digest
from .synthetic_activation_dry_run_fixture_materialization_plans import FIXTURE_MATERIALIZATION_PLAN_GATES,FIXTURE_MATERIALIZATION_PLAN_SCOPE,FIXTURE_MATERIALIZATION_PLAN_STATE,SyntheticActivationDryRunFixtureMaterializationPlan,SyntheticActivationDryRunFixtureMaterializationPlanBook,_descriptor,_id_values,_valid_source

FIXTURE_MATERIALIZATION_PLAN_REVIEW_MAXIMUM_STATE="READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_MATERIALIZATION_SPECIFICATION"
_RID="synthetic:activation-dry-run-fixture-materialization-plan-review:"
_REVIEWER="synthetic:eternian-reviewer:activation-dry-run-fixture-materialization-plan:"
class FixtureMaterializationPlanReviewDecision(StrEnum):PASS="PASS";HOLD="HOLD";REJECT="REJECT"
class FixtureMaterializationPlanReviewState(StrEnum):
    PENDING_ETERNIAN_REVIEW="PENDING_ETERNIAN_REVIEW"
    READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_MATERIALIZATION_SPECIFICATION=FIXTURE_MATERIALIZATION_PLAN_REVIEW_MAXIMUM_STATE
    HELD="HELD";REJECTED="REJECTED"
_STATE={FixtureMaterializationPlanReviewDecision.PASS:FixtureMaterializationPlanReviewState.READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_MATERIALIZATION_SPECIFICATION,
        FixtureMaterializationPlanReviewDecision.HOLD:FixtureMaterializationPlanReviewState.HELD,FixtureMaterializationPlanReviewDecision.REJECT:FixtureMaterializationPlanReviewState.REJECTED}
def _valid(v:object)->bool:return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _valid_plan(p:SyntheticActivationDryRunFixtureMaterializationPlan)->bool:
    source=p.source_review if isinstance(p,SyntheticActivationDryRunFixtureMaterializationPlan) else None
    draft=source.draft if _valid_source(source) else None
    return (isinstance(p,SyntheticActivationDryRunFixtureMaterializationPlan) and draft is not None and p.source_draft_id==draft.draft_id
        and p.source_draft_digest==draft.draft_digest and p.source_review_id==source.review_id and p.source_review_digest==source.review_digest
        and p.blueprint_digest==draft.blueprint_digest and p.fixture_schema_digest==draft.fixture_schema_digest
        and p.synthetic_input_digest==draft.synthetic_input_digest and p.expected_result_digest==draft.expected_result_digest
        and p.rollback_expectation_digest==draft.rollback_expectation_digest
        and p.plan_id==_id_values(p.source_draft_id,p.source_draft_digest,p.source_review_digest)
        and p.artifact_descriptor_digest==_descriptor(p.blueprint_digest,p.fixture_schema_digest,p.synthetic_input_digest,p.expected_result_digest,p.rollback_expectation_digest)
        and p.scope==FIXTURE_MATERIALIZATION_PLAN_SCOPE and p.required_gates==FIXTURE_MATERIALIZATION_PLAN_GATES and p.state==FIXTURE_MATERIALIZATION_PLAN_STATE
        and p.plan_digest==canonical_digest(p.digest_value()) and p.synthetic_only and p.separate_review_required
        and not any((p.fixture_content_present,p.fixture_bytes_present,p.fixture_materialized,p.fixture_file_created,p.filesystem_written,p.dry_run_executed,
            p.activation_recorded,p.rollback_executed,p.network_accessed,p.money_movement_executed,p.production_activation_allowed)))

@dataclass(frozen=True)
class SyntheticActivationDryRunFixtureMaterializationPlanReviewRecord:
    sequence:int;plan:SyntheticActivationDryRunFixtureMaterializationPlan;submitted_at:datetime;state:FixtureMaterializationPlanReviewState;previous_digest:str;submission_digest:str
    review_id:str|None=None;reviewer_id:str|None=None;decision:FixtureMaterializationPlanReviewDecision|None=None;findings_digest:str|None=None;reviewed_at:datetime|None=None;review_digest:str|None=None
    def __post_init__(self)->None:
        pending=self.state is FixtureMaterializationPlanReviewState.PENDING_ETERNIAN_REVIEW;fields=(self.review_id,self.reviewer_id,self.decision,self.findings_digest,self.reviewed_at,self.review_digest)
        if (self.sequence<=0 or not _valid_plan(self.plan) or self.submitted_at.tzinfo is None or self.submitted_at<self.plan.planned_at
            or not _valid(self.previous_digest) or self.submission_digest!=canonical_digest(self.submission_value())
            or (pending and any(v is not None for v in fields)) or (not pending and any(v is None for v in fields))):raise GovernanceRejected("valid fixture materialization plan review record required")
        if not pending and (not self.review_id.startswith(_RID) or not self.reviewer_id.startswith(_REVIEWER) or not isinstance(self.decision,FixtureMaterializationPlanReviewDecision)
            or self.state is not _STATE[self.decision] or not _valid(self.findings_digest) or self.reviewed_at.tzinfo is None or self.reviewed_at<self.submitted_at
            or self.review_digest!=canonical_digest(self.review_value())):raise GovernanceRejected("valid independent fixture materialization plan review required")
    def submission_value(self)->dict[str,object]:
        return {"sequence":self.sequence,"plan_id":self.plan.plan_id,"plan_digest":self.plan.plan_digest,"submitted_at":self.submitted_at.isoformat(),
            "submission_state":FixtureMaterializationPlanReviewState.PENDING_ETERNIAN_REVIEW.value,"previous_digest":self.previous_digest}
    def review_value(self)->dict[str,object]:
        return {"plan_id":self.plan.plan_id,"plan_digest":self.plan.plan_digest,"review_id":self.review_id,"reviewer_id":self.reviewer_id,
            "decision":self.decision.value if self.decision else None,"findings_digest":self.findings_digest,
            "reviewed_at":self.reviewed_at.isoformat() if self.reviewed_at else None,"resulting_state":self.state.value,
            "fixture_content_allowed":False,"fixture_materialization_allowed":False,"filesystem_write_allowed":False,"dry_run_execution_allowed":False,
            "activation_allowed":False,"production_activation_allowed":False}

class SyntheticActivationDryRunFixtureMaterializationPlanReviewDocket:
    def __init__(self)->None:self._records=[];self._by_plan={};self._lock=RLock()
    @property
    def records(self)->tuple[SyntheticActivationDryRunFixtureMaterializationPlanReviewRecord,...]:
        with self._lock:return tuple(self._records)
    def submit(self,book:SyntheticActivationDryRunFixtureMaterializationPlanBook,plan_id:str,*,submitted_at:datetime)->SyntheticActivationDryRunFixtureMaterializationPlanReviewRecord:
        if not isinstance(book,SyntheticActivationDryRunFixtureMaterializationPlanBook) or not book.verify_plan_chain():raise GovernanceRejected("intact typed fixture materialization plan book required")
        if submitted_at.tzinfo is None:raise GovernanceRejected("timezone-aware fixture materialization plan review submission required")
        matches=[i for i in book.plans if i.plan_id==plan_id]
        if len(matches)!=1:raise GovernanceRejected("exactly one fixture materialization plan required")
        source=matches[0];before=book.evidence()["report_digest"]
        with self._lock:
            if not self.verify_chain():raise GovernanceRejected("existing fixture materialization plan review chain invalid")
            old=self._by_plan.get(plan_id)
            if old is not None:return old
            previous=self._records[-1].submission_digest if self._records else "0"*64
            values={"sequence":len(self._records)+1,"plan_id":source.plan_id,"plan_digest":source.plan_digest,"submitted_at":submitted_at.isoformat(),
                "submission_state":FixtureMaterializationPlanReviewState.PENDING_ETERNIAN_REVIEW.value,"previous_digest":previous}
            item=SyntheticActivationDryRunFixtureMaterializationPlanReviewRecord(len(self._records)+1,source,submitted_at,
                FixtureMaterializationPlanReviewState.PENDING_ETERNIAN_REVIEW,previous,canonical_digest(values))
            if before!=book.evidence()["report_digest"]:raise GovernanceRejected("fixture materialization plan changed during review submission")
            self._records.append(item);self._by_plan[plan_id]=item;return item
    def record_eternian_review(self,plan_id:str,*,review_id:str,reviewer_id:str,decision:FixtureMaterializationPlanReviewDecision,findings_digest:str,reviewed_at:datetime)->SyntheticActivationDryRunFixtureMaterializationPlanReviewRecord:
        if (not isinstance(review_id,str) or not review_id.startswith(_RID) or not isinstance(reviewer_id,str) or not reviewer_id.startswith(_REVIEWER)
            or not isinstance(decision,FixtureMaterializationPlanReviewDecision) or not _valid(findings_digest) or reviewed_at.tzinfo is None):raise GovernanceRejected("valid fixture materialization plan review metadata required")
        with self._lock:
            if not self.verify_chain():raise GovernanceRejected("existing fixture materialization plan review chain invalid")
            current=self._by_plan.get(plan_id)
            if current is None:raise GovernanceRejected("unknown fixture materialization plan")
            values={"plan_id":current.plan.plan_id,"plan_digest":current.plan.plan_digest,"review_id":review_id,"reviewer_id":reviewer_id,
                "decision":decision.value,"findings_digest":findings_digest,"reviewed_at":reviewed_at.isoformat(),"resulting_state":_STATE[decision].value,
                "fixture_content_allowed":False,"fixture_materialization_allowed":False,"filesystem_write_allowed":False,"dry_run_execution_allowed":False,
                "activation_allowed":False,"production_activation_allowed":False};digest=canonical_digest(values)
            if current.state is not FixtureMaterializationPlanReviewState.PENDING_ETERNIAN_REVIEW:
                if current.review_digest==digest:return current
                raise GovernanceRejected("fixture materialization plan review is immutable")
            item=SyntheticActivationDryRunFixtureMaterializationPlanReviewRecord(current.sequence,current.plan,current.submitted_at,_STATE[decision],
                current.previous_digest,current.submission_digest,review_id,reviewer_id,decision,findings_digest,reviewed_at,digest)
            self._records[current.sequence-1]=item;self._by_plan[plan_id]=item;return item
    def ready_source(self,plan_id:str)->SyntheticActivationDryRunFixtureMaterializationPlanReviewRecord:
        with self._lock:
            item=self._by_plan.get(plan_id)
            if item is None or item.state is not FixtureMaterializationPlanReviewState.READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_MATERIALIZATION_SPECIFICATION or not self.verify_chain():
                raise GovernanceRejected("passed fixture materialization plan review required")
            return item
    def verify_chain(self)->bool:
        with self._lock:
            previous="0"*64
            for n,i in enumerate(self._records,1):
                pending=i.state is FixtureMaterializationPlanReviewState.PENDING_ETERNIAN_REVIEW;fields=(i.review_id,i.reviewer_id,i.decision,i.findings_digest,i.reviewed_at,i.review_digest)
                if (i.sequence!=n or i.previous_digest!=previous or i.submission_digest!=canonical_digest(i.submission_value()) or not _valid_plan(i.plan)
                    or (pending and any(v is not None for v in fields)) or (not pending and (any(v is None for v in fields)
                    or not isinstance(i.decision,FixtureMaterializationPlanReviewDecision) or i.state is not _STATE[i.decision]
                    or not i.review_id.startswith(_RID) or not i.reviewer_id.startswith(_REVIEWER) or not _valid(i.findings_digest)
                    or i.reviewed_at.tzinfo is None or i.reviewed_at<i.submitted_at or i.review_digest!=canonical_digest(i.review_value())))):return False
                previous=i.submission_digest
            return len(self._records)==len(self._by_plan) and all(self._by_plan.get(i.plan.plan_id) is i for i in self._records)
    def evidence(self)->dict[str,object]:
        with self._lock:
            v={"schema":"nurion.pg.synthetic-activation-dry-run-fixture-materialization-plan-review-evidence.v1","mode":"UNREGISTERED_SYNTHETIC_ONLY",
               "record_count":len(self._records),"submission_digests":[i.submission_digest for i in self._records],
               "review_digests":[i.review_digest for i in self._records if i.review_digest],"review_chain_valid":self.verify_chain(),
               "maximum_state":FIXTURE_MATERIALIZATION_PLAN_REVIEW_MAXIMUM_STATE,"fixture_content_method_present":False,
               "fixture_materialization_method_present":False,"fixture_creation_method_present":False,"filesystem_write_method_present":False,
               "dry_run_execution_method_present":False,"activation_method_present":False,"rollback_execution_method_present":False,
               "network_access_method_present":False,"automatic_merge_method_present":False,"automatic_deploy_method_present":False,
               "credentials_used":False,"personal_data_used":False,"money_movement_executed":False,"production_activation_allowed":False}
            return {**v,"report_digest":canonical_digest(v)}
