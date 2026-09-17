"""Independent review of non-materialized synthetic fixture drafts."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from threading import RLock
from .arkaon.governance import GovernanceRejected,canonical_digest
from .synthetic_activation_dry_run_fixture_drafts import FIXTURE_DRAFT_GATES,FIXTURE_DRAFT_SCOPE,FIXTURE_DRAFT_STATE,SyntheticActivationDryRunFixtureDraft,SyntheticActivationDryRunFixtureDraftBook,_blueprint,_id_values

FIXTURE_DRAFT_REVIEW_MAXIMUM_STATE="READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_MATERIALIZATION_PLAN"
_RID="synthetic:activation-dry-run-fixture-draft-review:"
_REVIEWER="synthetic:eternian-reviewer:activation-dry-run-fixture-draft:"
class FixtureDraftReviewDecision(StrEnum):PASS="PASS";HOLD="HOLD";REJECT="REJECT"
class FixtureDraftReviewState(StrEnum):
    PENDING_ETERNIAN_REVIEW="PENDING_ETERNIAN_REVIEW"
    READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_MATERIALIZATION_PLAN=FIXTURE_DRAFT_REVIEW_MAXIMUM_STATE
    HELD="HELD";REJECTED="REJECTED"
_STATE={FixtureDraftReviewDecision.PASS:FixtureDraftReviewState.READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_MATERIALIZATION_PLAN,
        FixtureDraftReviewDecision.HOLD:FixtureDraftReviewState.HELD,FixtureDraftReviewDecision.REJECT:FixtureDraftReviewState.REJECTED}
def _valid(v:object)->bool:return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)

@dataclass(frozen=True)
class SyntheticActivationDryRunFixtureDraftReviewRecord:
    sequence:int;draft:SyntheticActivationDryRunFixtureDraft;submitted_at:datetime;state:FixtureDraftReviewState;previous_digest:str;submission_digest:str
    review_id:str|None=None;reviewer_id:str|None=None;decision:FixtureDraftReviewDecision|None=None;findings_digest:str|None=None;reviewed_at:datetime|None=None;review_digest:str|None=None
    def __post_init__(self)->None:
        pending=self.state is FixtureDraftReviewState.PENDING_ETERNIAN_REVIEW;fields=(self.review_id,self.reviewer_id,self.decision,self.findings_digest,self.reviewed_at,self.review_digest)
        if (self.sequence<=0 or not _valid_draft(self.draft) or self.submitted_at.tzinfo is None or self.submitted_at<self.draft.drafted_at
            or not _valid(self.previous_digest) or self.submission_digest!=canonical_digest(self.submission_value())
            or (pending and any(v is not None for v in fields)) or (not pending and any(v is None for v in fields))):raise GovernanceRejected("valid fixture draft review record required")
        if not pending and (not self.review_id.startswith(_RID) or not self.reviewer_id.startswith(_REVIEWER) or not isinstance(self.decision,FixtureDraftReviewDecision)
            or self.state is not _STATE[self.decision] or not _valid(self.findings_digest) or self.reviewed_at.tzinfo is None or self.reviewed_at<self.submitted_at
            or self.review_digest!=canonical_digest(self.review_value())):raise GovernanceRejected("valid independent fixture draft review required")
    def submission_value(self)->dict[str,object]:return {"sequence":self.sequence,"draft_id":self.draft.draft_id,"draft_digest":self.draft.draft_digest,
        "submitted_at":self.submitted_at.isoformat(),"submission_state":FixtureDraftReviewState.PENDING_ETERNIAN_REVIEW.value,"previous_digest":self.previous_digest}
    def review_value(self)->dict[str,object]:return {"draft_id":self.draft.draft_id,"draft_digest":self.draft.draft_digest,"review_id":self.review_id,
        "reviewer_id":self.reviewer_id,"decision":self.decision.value if self.decision else None,"findings_digest":self.findings_digest,
        "reviewed_at":self.reviewed_at.isoformat() if self.reviewed_at else None,"resulting_state":self.state.value,
        "fixture_materialization_allowed":False,"fixture_creation_allowed":False,"dry_run_execution_allowed":False,"activation_allowed":False,"production_activation_allowed":False}

def _valid_draft(d:SyntheticActivationDryRunFixtureDraft)->bool:
    return (isinstance(d,SyntheticActivationDryRunFixtureDraft) and d.state==FIXTURE_DRAFT_STATE and d.scope==FIXTURE_DRAFT_SCOPE
        and d.required_gates==FIXTURE_DRAFT_GATES and d.draft_id==_id_values(d.source_proposal_id,d.source_proposal_digest,d.source_review_digest)
        and d.blueprint_digest==_blueprint(d.fixture_schema_digest,d.synthetic_input_digest,d.expected_result_digest,d.rollback_expectation_digest)
        and d.draft_digest==canonical_digest(d.digest_value()) and not any((d.fixture_content_present,d.fixture_serialized,d.fixture_file_created,d.dry_run_executed,
            d.activation_recorded,d.rollback_executed,d.network_accessed,d.money_movement_executed,d.production_activation_allowed)))

class SyntheticActivationDryRunFixtureDraftReviewDocket:
    def __init__(self)->None:self._records=[];self._by_draft={};self._lock=RLock()
    @property
    def records(self)->tuple[SyntheticActivationDryRunFixtureDraftReviewRecord,...]:
        with self._lock:return tuple(self._records)
    def submit(self,book:SyntheticActivationDryRunFixtureDraftBook,draft_id:str,*,submitted_at:datetime)->SyntheticActivationDryRunFixtureDraftReviewRecord:
        if not isinstance(book,SyntheticActivationDryRunFixtureDraftBook) or not book.verify_draft_chain():raise GovernanceRejected("intact typed fixture draft book required")
        if submitted_at.tzinfo is None:raise GovernanceRejected("timezone-aware fixture draft review submission required")
        matches=[i for i in book.drafts if i.draft_id==draft_id]
        if len(matches)!=1:raise GovernanceRejected("exactly one fixture draft required")
        source=matches[0];before=book.evidence()["report_digest"]
        with self._lock:
            if not self.verify_chain():raise GovernanceRejected("existing fixture draft review chain invalid")
            old=self._by_draft.get(draft_id)
            if old is not None:return old
            previous=self._records[-1].submission_digest if self._records else "0"*64;values={"sequence":len(self._records)+1,"draft_id":source.draft_id,
                "draft_digest":source.draft_digest,"submitted_at":submitted_at.isoformat(),"submission_state":FixtureDraftReviewState.PENDING_ETERNIAN_REVIEW.value,"previous_digest":previous}
            item=SyntheticActivationDryRunFixtureDraftReviewRecord(len(self._records)+1,source,submitted_at,FixtureDraftReviewState.PENDING_ETERNIAN_REVIEW,previous,canonical_digest(values))
            if before!=book.evidence()["report_digest"]:raise GovernanceRejected("fixture draft changed during review submission")
            self._records.append(item);self._by_draft[draft_id]=item;return item
    def record_eternian_review(self,draft_id:str,*,review_id:str,reviewer_id:str,decision:FixtureDraftReviewDecision,findings_digest:str,reviewed_at:datetime)->SyntheticActivationDryRunFixtureDraftReviewRecord:
        if (not isinstance(review_id,str) or not review_id.startswith(_RID) or not isinstance(reviewer_id,str) or not reviewer_id.startswith(_REVIEWER)
            or not isinstance(decision,FixtureDraftReviewDecision) or not _valid(findings_digest) or reviewed_at.tzinfo is None):raise GovernanceRejected("valid fixture draft review metadata required")
        with self._lock:
            if not self.verify_chain():raise GovernanceRejected("existing fixture draft review chain invalid")
            current=self._by_draft.get(draft_id)
            if current is None:raise GovernanceRejected("unknown fixture draft")
            values={"draft_id":current.draft.draft_id,"draft_digest":current.draft.draft_digest,"review_id":review_id,"reviewer_id":reviewer_id,
                "decision":decision.value,"findings_digest":findings_digest,"reviewed_at":reviewed_at.isoformat(),"resulting_state":_STATE[decision].value,
                "fixture_materialization_allowed":False,"fixture_creation_allowed":False,"dry_run_execution_allowed":False,"activation_allowed":False,"production_activation_allowed":False};digest=canonical_digest(values)
            if current.state is not FixtureDraftReviewState.PENDING_ETERNIAN_REVIEW:
                if current.review_digest==digest:return current
                raise GovernanceRejected("fixture draft review is immutable")
            item=SyntheticActivationDryRunFixtureDraftReviewRecord(current.sequence,current.draft,current.submitted_at,_STATE[decision],current.previous_digest,current.submission_digest,
                review_id,reviewer_id,decision,findings_digest,reviewed_at,digest);self._records[current.sequence-1]=item;self._by_draft[draft_id]=item;return item
    def ready_source(self,draft_id:str)->SyntheticActivationDryRunFixtureDraftReviewRecord:
        with self._lock:
            item=self._by_draft.get(draft_id)
            if item is None or item.state is not FixtureDraftReviewState.READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_MATERIALIZATION_PLAN or not self.verify_chain():raise GovernanceRejected("passed fixture draft review required")
            return item
    def verify_chain(self)->bool:
        with self._lock:
            previous="0"*64
            for n,i in enumerate(self._records,1):
                pending=i.state is FixtureDraftReviewState.PENDING_ETERNIAN_REVIEW;fields=(i.review_id,i.reviewer_id,i.decision,i.findings_digest,i.reviewed_at,i.review_digest)
                if (i.sequence!=n or i.previous_digest!=previous or i.submission_digest!=canonical_digest(i.submission_value()) or not _valid_draft(i.draft)
                    or (pending and any(v is not None for v in fields)) or (not pending and (any(v is None for v in fields) or not isinstance(i.decision,FixtureDraftReviewDecision)
                    or i.state is not _STATE[i.decision] or i.review_digest!=canonical_digest(i.review_value())))):return False
                previous=i.submission_digest
            return len(self._records)==len(self._by_draft) and all(self._by_draft.get(i.draft.draft_id) is i for i in self._records)
    def evidence(self)->dict[str,object]:
        with self._lock:
            v={"schema":"nurion.pg.synthetic-activation-dry-run-fixture-draft-review-evidence.v1","mode":"UNREGISTERED_SYNTHETIC_ONLY","record_count":len(self._records),
               "submission_digests":[i.submission_digest for i in self._records],"review_digests":[i.review_digest for i in self._records if i.review_digest],"review_chain_valid":self.verify_chain(),
               "maximum_state":FIXTURE_DRAFT_REVIEW_MAXIMUM_STATE,"fixture_materialization_method_present":False,"fixture_creation_method_present":False,
               "dry_run_execution_method_present":False,"activation_method_present":False,"rollback_execution_method_present":False,"filesystem_write_method_present":False,
               "network_access_method_present":False,"automatic_merge_method_present":False,"automatic_deploy_method_present":False,"credentials_used":False,
               "personal_data_used":False,"money_movement_executed":False,"production_activation_allowed":False};return {**v,"report_digest":canonical_digest(v)}
