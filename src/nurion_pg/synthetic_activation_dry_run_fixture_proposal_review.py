"""Independent review of metadata-only activation dry-run fixture proposals."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from threading import RLock
from .arkaon.governance import GovernanceRejected,canonical_digest
from .synthetic_activation_dry_run_fixture_proposals import FIXTURE_PROPOSAL_GATES,FIXTURE_PROPOSAL_SCOPE,FIXTURE_PROPOSAL_STATE,SyntheticActivationDryRunFixtureProposal,SyntheticActivationDryRunFixtureProposalBook,_proposal_id_values

FIXTURE_REVIEW_MAXIMUM_STATE="READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_DRAFT"
_RID="synthetic:activation-dry-run-fixture-proposal-review:"
_REVIEWER="synthetic:eternian-reviewer:activation-dry-run-fixture-proposal:"
class FixtureProposalReviewDecision(StrEnum):PASS="PASS";HOLD="HOLD";REJECT="REJECT"
class FixtureProposalReviewState(StrEnum):
    PENDING_ETERNIAN_REVIEW="PENDING_ETERNIAN_REVIEW"
    READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_DRAFT=FIXTURE_REVIEW_MAXIMUM_STATE
    HELD="HELD";REJECTED="REJECTED"
_STATE={FixtureProposalReviewDecision.PASS:FixtureProposalReviewState.READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_DRAFT,
        FixtureProposalReviewDecision.HOLD:FixtureProposalReviewState.HELD,FixtureProposalReviewDecision.REJECT:FixtureProposalReviewState.REJECTED}
def _digest(v:object)->bool:return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)

@dataclass(frozen=True)
class SyntheticActivationDryRunFixtureProposalReviewRecord:
    sequence:int;proposal:SyntheticActivationDryRunFixtureProposal;submitted_at:datetime;state:FixtureProposalReviewState
    previous_digest:str;submission_digest:str;review_id:str|None=None;reviewer_id:str|None=None
    decision:FixtureProposalReviewDecision|None=None;findings_digest:str|None=None;reviewed_at:datetime|None=None;review_digest:str|None=None
    def __post_init__(self)->None:
        pending=self.state is FixtureProposalReviewState.PENDING_ETERNIAN_REVIEW;fields=(self.review_id,self.reviewer_id,self.decision,self.findings_digest,self.reviewed_at,self.review_digest)
        if (self.sequence<=0 or not isinstance(self.proposal,SyntheticActivationDryRunFixtureProposal)
            or self.proposal.state!=FIXTURE_PROPOSAL_STATE or self.proposal.scope!=FIXTURE_PROPOSAL_SCOPE
            or self.proposal.proposal_digest!=canonical_digest(self.proposal.digest_value())
            or self.submitted_at.tzinfo is None or self.submitted_at<self.proposal.proposed_at or not _digest(self.previous_digest)
            or self.submission_digest!=canonical_digest(self.submission_value())
            or (pending and any(v is not None for v in fields)) or (not pending and any(v is None for v in fields))):
            raise GovernanceRejected("valid fixture proposal review record required")
        if not pending and (not self.review_id.startswith(_RID) or not self.reviewer_id.startswith(_REVIEWER)
            or not isinstance(self.decision,FixtureProposalReviewDecision) or self.state is not _STATE[self.decision]
            or not _digest(self.findings_digest) or self.reviewed_at.tzinfo is None or self.reviewed_at<self.submitted_at
            or self.review_digest!=canonical_digest(self.review_value())):raise GovernanceRejected("valid independent fixture proposal review required")
    def submission_value(self)->dict[str,object]:
        return {"sequence":self.sequence,"proposal_id":self.proposal.proposal_id,"proposal_digest":self.proposal.proposal_digest,
                "submitted_at":self.submitted_at.isoformat(),"submission_state":FixtureProposalReviewState.PENDING_ETERNIAN_REVIEW.value,"previous_digest":self.previous_digest}
    def review_value(self)->dict[str,object]:
        return {"proposal_id":self.proposal.proposal_id,"proposal_digest":self.proposal.proposal_digest,"review_id":self.review_id,
                "reviewer_id":self.reviewer_id,"decision":self.decision.value if self.decision else None,"findings_digest":self.findings_digest,
                "reviewed_at":self.reviewed_at.isoformat() if self.reviewed_at else None,"resulting_state":self.state.value,
                "fixture_creation_allowed":False,"dry_run_execution_allowed":False,"activation_allowed":False,"production_activation_allowed":False}

class SyntheticActivationDryRunFixtureProposalReviewDocket:
    def __init__(self)->None:self._records=[];self._by_proposal={};self._lock=RLock()
    @property
    def records(self)->tuple[SyntheticActivationDryRunFixtureProposalReviewRecord,...]:
        with self._lock:return tuple(self._records)
    def submit(self,book:SyntheticActivationDryRunFixtureProposalBook,proposal_id:str,*,submitted_at:datetime)->SyntheticActivationDryRunFixtureProposalReviewRecord:
        if not isinstance(book,SyntheticActivationDryRunFixtureProposalBook) or not book.verify_proposal_chain():raise GovernanceRejected("intact typed fixture proposal book required")
        if submitted_at.tzinfo is None:raise GovernanceRejected("timezone-aware fixture proposal review submission required")
        matches=[i for i in book.proposals if i.proposal_id==proposal_id]
        if len(matches)!=1:raise GovernanceRejected("exactly one fixture proposal required")
        source=matches[0];before=book.evidence()["report_digest"]
        with self._lock:
            if not self.verify_chain():raise GovernanceRejected("existing fixture proposal review chain invalid")
            old=self._by_proposal.get(proposal_id)
            if old is not None:return old
            previous=self._records[-1].submission_digest if self._records else "0"*64
            values={"sequence":len(self._records)+1,"proposal_id":source.proposal_id,"proposal_digest":source.proposal_digest,
                    "submitted_at":submitted_at.isoformat(),"submission_state":FixtureProposalReviewState.PENDING_ETERNIAN_REVIEW.value,"previous_digest":previous}
            item=SyntheticActivationDryRunFixtureProposalReviewRecord(len(self._records)+1,source,submitted_at,FixtureProposalReviewState.PENDING_ETERNIAN_REVIEW,previous,canonical_digest(values))
            if before!=book.evidence()["report_digest"]:raise GovernanceRejected("fixture proposal changed during review submission")
            self._records.append(item);self._by_proposal[proposal_id]=item;return item
    def record_eternian_review(self,proposal_id:str,*,review_id:str,reviewer_id:str,decision:FixtureProposalReviewDecision,findings_digest:str,reviewed_at:datetime)->SyntheticActivationDryRunFixtureProposalReviewRecord:
        if (not isinstance(review_id,str) or not review_id.startswith(_RID) or not isinstance(reviewer_id,str) or not reviewer_id.startswith(_REVIEWER)
            or not isinstance(decision,FixtureProposalReviewDecision) or not _digest(findings_digest) or reviewed_at.tzinfo is None):raise GovernanceRejected("valid fixture proposal review metadata required")
        with self._lock:
            if not self.verify_chain():raise GovernanceRejected("existing fixture proposal review chain invalid")
            current=self._by_proposal.get(proposal_id)
            if current is None:raise GovernanceRejected("unknown fixture proposal")
            values={"proposal_id":current.proposal.proposal_id,"proposal_digest":current.proposal.proposal_digest,"review_id":review_id,"reviewer_id":reviewer_id,
                    "decision":decision.value,"findings_digest":findings_digest,"reviewed_at":reviewed_at.isoformat(),"resulting_state":_STATE[decision].value,
                    "fixture_creation_allowed":False,"dry_run_execution_allowed":False,"activation_allowed":False,"production_activation_allowed":False}
            digest=canonical_digest(values)
            if current.state is not FixtureProposalReviewState.PENDING_ETERNIAN_REVIEW:
                if current.review_digest==digest:return current
                raise GovernanceRejected("fixture proposal review is immutable")
            item=SyntheticActivationDryRunFixtureProposalReviewRecord(current.sequence,current.proposal,current.submitted_at,_STATE[decision],current.previous_digest,
                    current.submission_digest,review_id,reviewer_id,decision,findings_digest,reviewed_at,digest)
            self._records[current.sequence-1]=item;self._by_proposal[proposal_id]=item;return item
    def ready_source(self,proposal_id:str)->SyntheticActivationDryRunFixtureProposalReviewRecord:
        with self._lock:
            item=self._by_proposal.get(proposal_id)
            if item is None or item.state is not FixtureProposalReviewState.READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_DRAFT or not self.verify_chain():raise GovernanceRejected("passed fixture proposal review required")
            return item
    def verify_chain(self)->bool:
        with self._lock:
            previous="0"*64
            for n,item in enumerate(self._records,1):
                pending=item.state is FixtureProposalReviewState.PENDING_ETERNIAN_REVIEW;fields=(item.review_id,item.reviewer_id,item.decision,item.findings_digest,item.reviewed_at,item.review_digest)
                if (item.sequence!=n or item.previous_digest!=previous or item.submission_digest!=canonical_digest(item.submission_value())
                    or item.proposal.proposal_digest!=canonical_digest(item.proposal.digest_value())
                    or item.proposal.proposal_id!=_proposal_id_values(item.proposal.source_design_id,item.proposal.source_design_digest,item.proposal.source_review_digest)
                    or item.proposal.required_gates!=FIXTURE_PROPOSAL_GATES
                    or item.proposal.state!=FIXTURE_PROPOSAL_STATE or item.proposal.scope!=FIXTURE_PROPOSAL_SCOPE
                    or any((item.proposal.fixture_content_present,item.proposal.fixture_file_created,item.proposal.dry_run_executed,
                            item.proposal.activation_recorded,item.proposal.rollback_executed,item.proposal.network_accessed,
                            item.proposal.money_movement_executed,item.proposal.production_activation_allowed))
                    or (pending and any(v is not None for v in fields))
                    or (not pending and (any(v is None for v in fields) or not isinstance(item.decision,FixtureProposalReviewDecision)
                        or item.state is not _STATE[item.decision] or item.review_digest!=canonical_digest(item.review_value())))):return False
                previous=item.submission_digest
            return len(self._records)==len(self._by_proposal) and all(self._by_proposal.get(i.proposal.proposal_id) is i for i in self._records)
    def evidence(self)->dict[str,object]:
        with self._lock:
            v={"schema":"nurion.pg.synthetic-activation-dry-run-fixture-proposal-review-evidence.v1","mode":"UNREGISTERED_SYNTHETIC_ONLY",
               "record_count":len(self._records),"submission_digests":[i.submission_digest for i in self._records],"review_digests":[i.review_digest for i in self._records if i.review_digest],
               "review_chain_valid":self.verify_chain(),"maximum_state":FIXTURE_REVIEW_MAXIMUM_STATE,"fixture_creation_method_present":False,
               "dry_run_execution_method_present":False,"activation_method_present":False,"rollback_execution_method_present":False,
               "filesystem_write_method_present":False,"network_access_method_present":False,"automatic_merge_method_present":False,
               "automatic_deploy_method_present":False,"credentials_used":False,"personal_data_used":False,"money_movement_executed":False,"production_activation_allowed":False}
            return {**v,"report_digest":canonical_digest(v)}
