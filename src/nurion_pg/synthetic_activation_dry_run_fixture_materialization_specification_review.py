"""Independent review of non-executable fixture materialization specifications."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from threading import RLock
from .arkaon.governance import GovernanceRejected,canonical_digest
from .synthetic_activation_dry_run_fixture_materialization_specifications import FIXTURE_MATERIALIZATION_SPECIFICATION_GATES,FIXTURE_MATERIALIZATION_SPECIFICATION_SCOPE,FIXTURE_MATERIALIZATION_SPECIFICATION_STATE,SyntheticActivationDryRunFixtureMaterializationSpecification,SyntheticActivationDryRunFixtureMaterializationSpecificationBook,_descriptor,_id_values,_valid_source

FIXTURE_MATERIALIZATION_SPECIFICATION_REVIEW_MAXIMUM_STATE="READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_MATERIALIZATION_DRY_RUN_PLAN"
_RID="synthetic:activation-dry-run-fixture-materialization-specification-review:"
_REVIEWER="synthetic:eternian-reviewer:activation-dry-run-fixture-materialization-specification:"
class FixtureMaterializationSpecificationReviewDecision(StrEnum):PASS="PASS";HOLD="HOLD";REJECT="REJECT"
class FixtureMaterializationSpecificationReviewState(StrEnum):
    PENDING_ETERNIAN_REVIEW="PENDING_ETERNIAN_REVIEW"
    READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_MATERIALIZATION_DRY_RUN_PLAN=FIXTURE_MATERIALIZATION_SPECIFICATION_REVIEW_MAXIMUM_STATE
    HELD="HELD";REJECTED="REJECTED"
_STATE={FixtureMaterializationSpecificationReviewDecision.PASS:FixtureMaterializationSpecificationReviewState.READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_MATERIALIZATION_DRY_RUN_PLAN,
        FixtureMaterializationSpecificationReviewDecision.HOLD:FixtureMaterializationSpecificationReviewState.HELD,
        FixtureMaterializationSpecificationReviewDecision.REJECT:FixtureMaterializationSpecificationReviewState.REJECTED}
def _valid(v:object)->bool:return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _valid_specification(s:SyntheticActivationDryRunFixtureMaterializationSpecification)->bool:
    source=s.source_review if isinstance(s,SyntheticActivationDryRunFixtureMaterializationSpecification) else None
    plan=source.plan if _valid_source(source) else None
    return (isinstance(s,SyntheticActivationDryRunFixtureMaterializationSpecification) and plan is not None
        and s.source_plan_id==plan.plan_id and s.source_plan_digest==plan.plan_digest and s.source_review_id==source.review_id
        and s.source_review_digest==source.review_digest and s.blueprint_digest==plan.blueprint_digest
        and s.artifact_descriptor_digest==plan.artifact_descriptor_digest and s.fixture_schema_digest==plan.fixture_schema_digest
        and s.synthetic_input_digest==plan.synthetic_input_digest and s.expected_result_digest==plan.expected_result_digest
        and s.rollback_expectation_digest==plan.rollback_expectation_digest
        and s.specification_id==_id_values(s.source_plan_id,s.source_plan_digest,s.source_review_digest)
        and s.specification_descriptor_digest==_descriptor(s.blueprint_digest,s.artifact_descriptor_digest,s.fixture_schema_digest,
            s.synthetic_input_digest,s.expected_result_digest,s.rollback_expectation_digest)
        and s.scope==FIXTURE_MATERIALIZATION_SPECIFICATION_SCOPE and s.required_gates==FIXTURE_MATERIALIZATION_SPECIFICATION_GATES
        and s.state==FIXTURE_MATERIALIZATION_SPECIFICATION_STATE and s.specification_digest==canonical_digest(s.digest_value())
        and s.synthetic_only and s.separate_review_required and not any((s.fixture_content_present,s.fixture_bytes_present,
            s.filesystem_path_present,s.fixture_materialized,s.fixture_file_created,s.filesystem_written,s.dry_run_executed,
            s.activation_recorded,s.rollback_executed,s.network_accessed,s.money_movement_executed,s.production_activation_allowed)))

@dataclass(frozen=True)
class SyntheticActivationDryRunFixtureMaterializationSpecificationReviewRecord:
    sequence:int;specification:SyntheticActivationDryRunFixtureMaterializationSpecification;submitted_at:datetime
    state:FixtureMaterializationSpecificationReviewState;previous_digest:str;submission_digest:str
    review_id:str|None=None;reviewer_id:str|None=None;decision:FixtureMaterializationSpecificationReviewDecision|None=None
    findings_digest:str|None=None;reviewed_at:datetime|None=None;review_digest:str|None=None
    def __post_init__(self)->None:
        pending=self.state is FixtureMaterializationSpecificationReviewState.PENDING_ETERNIAN_REVIEW
        fields=(self.review_id,self.reviewer_id,self.decision,self.findings_digest,self.reviewed_at,self.review_digest)
        if (self.sequence<=0 or not _valid_specification(self.specification) or self.submitted_at.tzinfo is None
            or self.submitted_at<self.specification.specified_at or not _valid(self.previous_digest)
            or self.submission_digest!=canonical_digest(self.submission_value()) or (pending and any(v is not None for v in fields))
            or (not pending and (any(v is None for v in fields) or not self._valid_final()))):
            raise GovernanceRejected("valid fixture materialization specification review record required")
    def _valid_final(self)->bool:
        return (isinstance(self.review_id,str) and self.review_id.startswith(_RID) and isinstance(self.reviewer_id,str)
            and self.reviewer_id.startswith(_REVIEWER) and isinstance(self.decision,FixtureMaterializationSpecificationReviewDecision)
            and self.state is _STATE[self.decision] and _valid(self.findings_digest) and self.reviewed_at is not None
            and self.reviewed_at.tzinfo is not None and self.reviewed_at>=self.submitted_at
            and self.review_digest==canonical_digest(self.review_value()))
    def submission_value(self)->dict[str,object]:
        return {"sequence":self.sequence,"specification_id":self.specification.specification_id,
            "specification_digest":self.specification.specification_digest,"submitted_at":self.submitted_at.isoformat(),
            "submission_state":FixtureMaterializationSpecificationReviewState.PENDING_ETERNIAN_REVIEW.value,"previous_digest":self.previous_digest}
    def review_value(self)->dict[str,object]:
        return {"specification_id":self.specification.specification_id,"specification_digest":self.specification.specification_digest,
            "review_id":self.review_id,"reviewer_id":self.reviewer_id,"decision":self.decision.value if self.decision else None,
            "findings_digest":self.findings_digest,"reviewed_at":self.reviewed_at.isoformat() if self.reviewed_at else None,
            "resulting_state":self.state.value,"fixture_content_allowed":False,"fixture_materialization_allowed":False,
            "filesystem_write_allowed":False,"dry_run_execution_allowed":False,"activation_allowed":False,"production_activation_allowed":False}

class SyntheticActivationDryRunFixtureMaterializationSpecificationReviewDocket:
    def __init__(self)->None:self._records=[];self._by_specification={};self._lock=RLock()
    @property
    def records(self)->tuple[SyntheticActivationDryRunFixtureMaterializationSpecificationReviewRecord,...]:
        with self._lock:return tuple(self._records)
    def submit(self,book:SyntheticActivationDryRunFixtureMaterializationSpecificationBook,specification_id:str,*,submitted_at:datetime)->SyntheticActivationDryRunFixtureMaterializationSpecificationReviewRecord:
        if not isinstance(book,SyntheticActivationDryRunFixtureMaterializationSpecificationBook) or not book.verify_specification_chain():
            raise GovernanceRejected("intact typed fixture materialization specification book required")
        if submitted_at.tzinfo is None:raise GovernanceRejected("timezone-aware specification review submission required")
        matches=[i for i in book.specifications if i.specification_id==specification_id]
        if len(matches)!=1:raise GovernanceRejected("exactly one fixture materialization specification required")
        source=matches[0];before=book.evidence()["report_digest"]
        with self._lock:
            if not self.verify_chain():raise GovernanceRejected("existing specification review chain invalid")
            old=self._by_specification.get(specification_id)
            if old is not None:return old
            previous=self._records[-1].submission_digest if self._records else "0"*64
            values={"sequence":len(self._records)+1,"specification_id":source.specification_id,
                "specification_digest":source.specification_digest,"submitted_at":submitted_at.isoformat(),
                "submission_state":FixtureMaterializationSpecificationReviewState.PENDING_ETERNIAN_REVIEW.value,"previous_digest":previous}
            item=SyntheticActivationDryRunFixtureMaterializationSpecificationReviewRecord(len(self._records)+1,source,submitted_at,
                FixtureMaterializationSpecificationReviewState.PENDING_ETERNIAN_REVIEW,previous,canonical_digest(values))
            if before!=book.evidence()["report_digest"]:raise GovernanceRejected("specification changed during review submission")
            self._records.append(item);self._by_specification[specification_id]=item;return item
    def record_eternian_review(self,specification_id:str,*,review_id:str,reviewer_id:str,decision:FixtureMaterializationSpecificationReviewDecision,
        findings_digest:str,reviewed_at:datetime)->SyntheticActivationDryRunFixtureMaterializationSpecificationReviewRecord:
        if (not isinstance(review_id,str) or not review_id.startswith(_RID) or not isinstance(reviewer_id,str)
            or not reviewer_id.startswith(_REVIEWER) or not isinstance(decision,FixtureMaterializationSpecificationReviewDecision)
            or not _valid(findings_digest) or reviewed_at.tzinfo is None):raise GovernanceRejected("valid specification review metadata required")
        with self._lock:
            if not self.verify_chain():raise GovernanceRejected("existing specification review chain invalid")
            current=self._by_specification.get(specification_id)
            if current is None:raise GovernanceRejected("unknown fixture materialization specification")
            values={"specification_id":current.specification.specification_id,"specification_digest":current.specification.specification_digest,
                "review_id":review_id,"reviewer_id":reviewer_id,"decision":decision.value,"findings_digest":findings_digest,
                "reviewed_at":reviewed_at.isoformat(),"resulting_state":_STATE[decision].value,"fixture_content_allowed":False,
                "fixture_materialization_allowed":False,"filesystem_write_allowed":False,"dry_run_execution_allowed":False,
                "activation_allowed":False,"production_activation_allowed":False};digest=canonical_digest(values)
            if current.state is not FixtureMaterializationSpecificationReviewState.PENDING_ETERNIAN_REVIEW:
                if current.review_digest==digest:return current
                raise GovernanceRejected("fixture materialization specification review is immutable")
            item=SyntheticActivationDryRunFixtureMaterializationSpecificationReviewRecord(current.sequence,current.specification,
                current.submitted_at,_STATE[decision],current.previous_digest,current.submission_digest,review_id,reviewer_id,
                decision,findings_digest,reviewed_at,digest)
            self._records[current.sequence-1]=item;self._by_specification[specification_id]=item;return item
    def ready_source(self,specification_id:str)->SyntheticActivationDryRunFixtureMaterializationSpecificationReviewRecord:
        with self._lock:
            item=self._by_specification.get(specification_id)
            if item is None or item.state is not FixtureMaterializationSpecificationReviewState.READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_MATERIALIZATION_DRY_RUN_PLAN or not self.verify_chain():
                raise GovernanceRejected("passed fixture materialization specification review required")
            return item
    def verify_chain(self)->bool:
        with self._lock:
            previous="0"*64
            for n,i in enumerate(self._records,1):
                pending=i.state is FixtureMaterializationSpecificationReviewState.PENDING_ETERNIAN_REVIEW
                fields=(i.review_id,i.reviewer_id,i.decision,i.findings_digest,i.reviewed_at,i.review_digest)
                if (i.sequence!=n or i.previous_digest!=previous or not _valid_specification(i.specification)
                    or i.submission_digest!=canonical_digest(i.submission_value()) or (pending and any(v is not None for v in fields))
                    or (not pending and (any(v is None for v in fields) or not i._valid_final()))):return False
                previous=i.submission_digest
            return len(self._records)==len(self._by_specification) and all(
                self._by_specification.get(i.specification.specification_id) is i for i in self._records)
    def evidence(self)->dict[str,object]:
        with self._lock:
            v={"schema":"nurion.pg.synthetic-activation-dry-run-fixture-materialization-specification-review-evidence.v1",
               "mode":"UNREGISTERED_SYNTHETIC_ONLY","record_count":len(self._records),
               "submission_digests":[i.submission_digest for i in self._records],
               "review_digests":[i.review_digest for i in self._records if i.review_digest],"review_chain_valid":self.verify_chain(),
               "maximum_state":FIXTURE_MATERIALIZATION_SPECIFICATION_REVIEW_MAXIMUM_STATE,"fixture_content_method_present":False,
               "fixture_bytes_method_present":False,"filesystem_path_method_present":False,"fixture_materialization_method_present":False,
               "fixture_creation_method_present":False,"filesystem_write_method_present":False,"dry_run_execution_method_present":False,
               "activation_method_present":False,"rollback_execution_method_present":False,"network_access_method_present":False,
               "automatic_merge_method_present":False,"automatic_deploy_method_present":False,"credentials_used":False,
               "personal_data_used":False,"money_movement_executed":False,"production_activation_allowed":False}
            return {**v,"report_digest":canonical_digest(v)}
