"""Metadata-only proposals for synthetic activation dry-run fixtures."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from .arkaon.governance import GovernanceRejected,canonical_digest
from .synthetic_activation_dry_run_design_review import (
    DryRunDesignReviewState,SyntheticActivationDryRunDesignReviewDocket,SyntheticActivationDryRunDesignReviewRecord,
)

FIXTURE_PROPOSAL_STATE="SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_PROPOSED"
FIXTURE_PROPOSAL_SCOPE="SYNTHETIC_FIXTURE_METADATA_PROPOSAL_ONLY"
FIXTURE_PROPOSAL_GATES=("PASSED_DRY_RUN_DESIGN_REVIEW_ONLY","EXACT_DESIGN_AND_REVIEW_DIGESTS_ONLY",
    "SYNTHETIC_INPUT_DIGEST_ONLY","EXPECTED_RESULT_DIGEST_ONLY","ROLLBACK_EXPECTATION_REQUIRED",
    "SEPARATE_ETERNIAN_REVIEW_REQUIRED","NO_FIXTURE_CONTENT_OR_FILE_CREATION","NO_DRY_RUN_EXECUTION_METHOD",
    "NO_ACTIVATION_OR_ROLLBACK_EXECUTION_METHOD","NO_PAYMENT_NETWORK_OR_DEPLOYMENT_EFFECT")

def _valid_digest(v:object)->bool:return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _proposal_id(r:SyntheticActivationDryRunDesignReviewRecord)->str:
    return "synthetic:activation-dry-run-fixture-proposal:"+canonical_digest({"design_id":r.design.design_id,"design_digest":r.design.design_digest,"review_digest":r.review_digest,"scope":FIXTURE_PROPOSAL_SCOPE})[:32]

@dataclass(frozen=True)
class SyntheticActivationDryRunFixtureProposal:
    sequence:int;proposal_id:str;source_design_id:str;source_design_digest:str;source_review_id:str;source_review_digest:str
    fixture_schema_digest:str;synthetic_input_digest:str;expected_result_digest:str;rollback_expectation_digest:str
    required_gates:tuple[str,...];proposed_at:datetime;previous_digest:str;proposal_digest:str
    state:str=FIXTURE_PROPOSAL_STATE;scope:str=FIXTURE_PROPOSAL_SCOPE;synthetic_only:bool=True;separate_review_required:bool=True
    fixture_content_present:bool=False;fixture_file_created:bool=False;dry_run_executed:bool=False;activation_recorded:bool=False
    rollback_executed:bool=False;network_accessed:bool=False;money_movement_executed:bool=False;production_activation_allowed:bool=False
    def __post_init__(self)->None:
        if (self.sequence<=0 or not self.proposal_id.startswith("synthetic:activation-dry-run-fixture-proposal:")
            or not self.source_design_id.startswith("synthetic:limited-promotion-activation-dry-run-design:")
            or not self.source_review_id.startswith("synthetic:activation-dry-run-design-review:")
            or not all(_valid_digest(v) for v in (self.source_design_digest,self.source_review_digest,self.fixture_schema_digest,
                self.synthetic_input_digest,self.expected_result_digest,self.rollback_expectation_digest,self.previous_digest))
            or self.required_gates!=FIXTURE_PROPOSAL_GATES or self.proposed_at.tzinfo is None
            or self.state!=FIXTURE_PROPOSAL_STATE or self.scope!=FIXTURE_PROPOSAL_SCOPE or not self.synthetic_only or not self.separate_review_required
            or any((self.fixture_content_present,self.fixture_file_created,self.dry_run_executed,self.activation_recorded,self.rollback_executed,
                    self.network_accessed,self.money_movement_executed,self.production_activation_allowed))
            or self.proposal_digest!=canonical_digest(self.digest_value())):raise GovernanceRejected("valid metadata-only fixture proposal required")
    def digest_value(self)->dict[str,object]:
        return {"sequence":self.sequence,"proposal_id":self.proposal_id,"source_design_id":self.source_design_id,
            "source_design_digest":self.source_design_digest,"source_review_id":self.source_review_id,"source_review_digest":self.source_review_digest,
            "fixture_schema_digest":self.fixture_schema_digest,"synthetic_input_digest":self.synthetic_input_digest,
            "expected_result_digest":self.expected_result_digest,"rollback_expectation_digest":self.rollback_expectation_digest,
            "required_gates":list(self.required_gates),"proposed_at":self.proposed_at.isoformat(),"previous_digest":self.previous_digest,
            "state":self.state,"scope":self.scope,"synthetic_only":True,"separate_review_required":True,
            "fixture_content_present":False,"fixture_file_created":False,"dry_run_executed":False,"activation_recorded":False,
            "rollback_executed":False,"network_accessed":False,"money_movement_executed":False,"production_activation_allowed":False}

class SyntheticActivationDryRunFixtureProposalBook:
    def __init__(self)->None:self._proposals=[];self._by_review={};self._lock=RLock()
    @property
    def proposals(self)->tuple[SyntheticActivationDryRunFixtureProposal,...]:
        with self._lock:return tuple(self._proposals)
    def propose_from_review(self,docket:SyntheticActivationDryRunDesignReviewDocket,design_id:str,*,proposed_at:datetime)->SyntheticActivationDryRunFixtureProposal:
        if not isinstance(docket,SyntheticActivationDryRunDesignReviewDocket) or not docket.verify_chain():raise GovernanceRejected("intact typed design review docket required")
        if proposed_at.tzinfo is None:raise GovernanceRejected("timezone-aware fixture proposal time required")
        before=docket.evidence()["report_digest"];review=docket.ready_source(design_id)
        if review.state is not DryRunDesignReviewState.READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_PROPOSAL or review.review_id is None or review.review_digest is None or review.reviewed_at is None or proposed_at<review.reviewed_at:
            raise GovernanceRejected("passed current design review required")
        design=review.design
        with self._lock:
            if not self.verify_proposal_chain():raise GovernanceRejected("existing fixture proposal chain invalid")
            existing=self._by_review.get(review.review_digest)
            if existing is not None:return existing
            schema=canonical_digest({"schema":"synthetic-activation-dry-run-fixture.v1","scope":design.scope})
            synthetic_input=canonical_digest({"candidate":design.candidate_digest,"cohort":design.cohort_digest,"sample":design.synthetic_sample_size})
            expected=canonical_digest({"observation_window":design.observation_window_seconds,"results":list(design.observation_result_digests)})
            rollback=canonical_digest({"triggers":list(design.rollback_triggers),"execution_allowed":False})
            previous=self._proposals[-1].proposal_digest if self._proposals else "0"*64;pid=_proposal_id(review)
            values={"sequence":len(self._proposals)+1,"proposal_id":pid,"source_design_id":design.design_id,"source_design_digest":design.design_digest,
                "source_review_id":review.review_id,"source_review_digest":review.review_digest,"fixture_schema_digest":schema,
                "synthetic_input_digest":synthetic_input,"expected_result_digest":expected,"rollback_expectation_digest":rollback,
                "required_gates":list(FIXTURE_PROPOSAL_GATES),"proposed_at":proposed_at.isoformat(),"previous_digest":previous,
                "state":FIXTURE_PROPOSAL_STATE,"scope":FIXTURE_PROPOSAL_SCOPE,"synthetic_only":True,"separate_review_required":True,
                "fixture_content_present":False,"fixture_file_created":False,"dry_run_executed":False,"activation_recorded":False,
                "rollback_executed":False,"network_accessed":False,"money_movement_executed":False,"production_activation_allowed":False}
            item=SyntheticActivationDryRunFixtureProposal(values["sequence"],pid,design.design_id,design.design_digest,review.review_id,review.review_digest,
                schema,synthetic_input,expected,rollback,FIXTURE_PROPOSAL_GATES,proposed_at,previous,canonical_digest(values))
            if before!=docket.evidence()["report_digest"]:raise GovernanceRejected("design review changed during fixture proposal")
            self._proposals.append(item);self._by_review[review.review_digest]=item;return item
    def verify_proposal_chain(self)->bool:
        with self._lock:
            previous="0"*64
            for sequence,item in enumerate(self._proposals,1):
                if (item.sequence!=sequence or item.previous_digest!=previous or item.proposal_digest!=canonical_digest(item.digest_value())
                    or item.required_gates!=FIXTURE_PROPOSAL_GATES or item.state!=FIXTURE_PROPOSAL_STATE or item.scope!=FIXTURE_PROPOSAL_SCOPE
                    or any((item.fixture_content_present,item.fixture_file_created,item.dry_run_executed,item.activation_recorded,item.rollback_executed,
                            item.network_accessed,item.money_movement_executed,item.production_activation_allowed))):return False
                previous=item.proposal_digest
            return len(self._proposals)==len(self._by_review) and all(self._by_review.get(i.source_review_digest) is i for i in self._proposals)
    def evidence(self)->dict[str,object]:
        with self._lock:
            value={"schema":"nurion.pg.synthetic-activation-dry-run-fixture-proposal-evidence.v1","mode":"UNREGISTERED_SYNTHETIC_ONLY",
                "proposal_count":len(self._proposals),"proposal_digests":[i.proposal_digest for i in self._proposals],"proposal_chain_valid":self.verify_proposal_chain(),
                "maximum_state":FIXTURE_PROPOSAL_STATE,"scope":FIXTURE_PROPOSAL_SCOPE,"separate_review_required":True,
                "fixture_content_present":False,"fixture_creation_method_present":False,"dry_run_execution_method_present":False,
                "activation_method_present":False,"rollback_execution_method_present":False,"filesystem_write_method_present":False,
                "network_access_method_present":False,"automatic_merge_method_present":False,"automatic_deploy_method_present":False,
                "credentials_used":False,"personal_data_used":False,"money_movement_executed":False,"production_activation_allowed":False}
            return {**value,"report_digest":canonical_digest(value)}
