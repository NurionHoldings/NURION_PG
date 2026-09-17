"""Non-materialized metadata drafts for synthetic activation dry-run fixtures."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from .arkaon.governance import GovernanceRejected,canonical_digest
from .synthetic_activation_dry_run_fixture_proposal_review import FixtureProposalReviewState,SyntheticActivationDryRunFixtureProposalReviewDocket,SyntheticActivationDryRunFixtureProposalReviewRecord

FIXTURE_DRAFT_STATE="SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_DRAFTED"
FIXTURE_DRAFT_SCOPE="SYNTHETIC_FIXTURE_BLUEPRINT_DIGESTS_ONLY"
FIXTURE_DRAFT_GATES=("PASSED_FIXTURE_PROPOSAL_REVIEW_ONLY","EXACT_PROPOSAL_AND_REVIEW_DIGESTS_ONLY","EXACT_SCHEMA_INPUT_RESULT_ROLLBACK_DIGESTS_ONLY",
    "IMMUTABLE_BLUEPRINT_DIGEST_REQUIRED","SEPARATE_ETERNIAN_REVIEW_REQUIRED","NO_FIXTURE_CONTENT_OR_SERIALIZATION","NO_FIXTURE_FILE_CREATION",
    "NO_DRY_RUN_EXECUTION_METHOD","NO_ACTIVATION_OR_ROLLBACK_EXECUTION_METHOD","NO_PAYMENT_NETWORK_OR_DEPLOYMENT_EFFECT")
def _valid(v:object)->bool:return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _id_values(proposal_id:str,proposal_digest:str,review_digest:str)->str:
    return "synthetic:activation-dry-run-fixture-draft:"+canonical_digest({"proposal_id":proposal_id,"proposal_digest":proposal_digest,"review_digest":review_digest,"scope":FIXTURE_DRAFT_SCOPE})[:32]
def _id(r:SyntheticActivationDryRunFixtureProposalReviewRecord)->str:return _id_values(r.proposal.proposal_id,r.proposal.proposal_digest,r.review_digest)
def _blueprint(schema:str,synthetic_input:str,expected:str,rollback:str)->str:
    return canonical_digest({"schema":schema,"input":synthetic_input,"expected":expected,"rollback":rollback,"materialized":False})

@dataclass(frozen=True)
class SyntheticActivationDryRunFixtureDraft:
    sequence:int;draft_id:str;source_proposal_id:str;source_proposal_digest:str;source_review_id:str;source_review_digest:str
    fixture_schema_digest:str;synthetic_input_digest:str;expected_result_digest:str;rollback_expectation_digest:str;blueprint_digest:str
    required_gates:tuple[str,...];drafted_at:datetime;previous_digest:str;draft_digest:str
    state:str=FIXTURE_DRAFT_STATE;scope:str=FIXTURE_DRAFT_SCOPE;synthetic_only:bool=True;separate_review_required:bool=True
    fixture_content_present:bool=False;fixture_serialized:bool=False;fixture_file_created:bool=False;dry_run_executed:bool=False
    activation_recorded:bool=False;rollback_executed:bool=False;network_accessed:bool=False;money_movement_executed:bool=False;production_activation_allowed:bool=False
    def __post_init__(self)->None:
        if (self.sequence<=0 or self.draft_id!=_id_values(self.source_proposal_id,self.source_proposal_digest,self.source_review_digest)
            or not all(_valid(v) for v in (self.source_proposal_digest,self.source_review_digest,self.fixture_schema_digest,self.synthetic_input_digest,
                self.expected_result_digest,self.rollback_expectation_digest,self.blueprint_digest,self.previous_digest))
            or self.required_gates!=FIXTURE_DRAFT_GATES or self.drafted_at.tzinfo is None or self.state!=FIXTURE_DRAFT_STATE or self.scope!=FIXTURE_DRAFT_SCOPE
            or not self.synthetic_only or not self.separate_review_required or any((self.fixture_content_present,self.fixture_serialized,self.fixture_file_created,
                self.dry_run_executed,self.activation_recorded,self.rollback_executed,self.network_accessed,self.money_movement_executed,self.production_activation_allowed))
            or self.draft_digest!=canonical_digest(self.digest_value())):raise GovernanceRejected("valid non-materialized fixture draft required")
    def digest_value(self)->dict[str,object]:
        return {"sequence":self.sequence,"draft_id":self.draft_id,"source_proposal_id":self.source_proposal_id,"source_proposal_digest":self.source_proposal_digest,
            "source_review_id":self.source_review_id,"source_review_digest":self.source_review_digest,"fixture_schema_digest":self.fixture_schema_digest,
            "synthetic_input_digest":self.synthetic_input_digest,"expected_result_digest":self.expected_result_digest,"rollback_expectation_digest":self.rollback_expectation_digest,
            "blueprint_digest":self.blueprint_digest,"required_gates":list(self.required_gates),"drafted_at":self.drafted_at.isoformat(),"previous_digest":self.previous_digest,
            "state":self.state,"scope":self.scope,"synthetic_only":True,"separate_review_required":True,"fixture_content_present":False,
            "fixture_serialized":False,"fixture_file_created":False,"dry_run_executed":False,"activation_recorded":False,"rollback_executed":False,
            "network_accessed":False,"money_movement_executed":False,"production_activation_allowed":False}

class SyntheticActivationDryRunFixtureDraftBook:
    def __init__(self)->None:self._drafts=[];self._by_review={};self._lock=RLock()
    @property
    def drafts(self)->tuple[SyntheticActivationDryRunFixtureDraft,...]:
        with self._lock:return tuple(self._drafts)
    def draft_from_review(self,docket:SyntheticActivationDryRunFixtureProposalReviewDocket,proposal_id:str,*,drafted_at:datetime)->SyntheticActivationDryRunFixtureDraft:
        if not isinstance(docket,SyntheticActivationDryRunFixtureProposalReviewDocket) or not docket.verify_chain():raise GovernanceRejected("intact typed fixture proposal review docket required")
        if drafted_at.tzinfo is None:raise GovernanceRejected("timezone-aware fixture draft time required")
        before=docket.evidence()["report_digest"];review=docket.ready_source(proposal_id)
        if review.state is not FixtureProposalReviewState.READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_DRAFT or review.review_id is None or review.review_digest is None or review.reviewed_at is None or drafted_at<review.reviewed_at:
            raise GovernanceRejected("passed current fixture proposal review required")
        p=review.proposal
        with self._lock:
            if not self.verify_draft_chain():raise GovernanceRejected("existing fixture draft chain invalid")
            old=self._by_review.get(review.review_digest)
            if old is not None:return old
            blueprint=_blueprint(p.fixture_schema_digest,p.synthetic_input_digest,p.expected_result_digest,p.rollback_expectation_digest)
            previous=self._drafts[-1].draft_digest if self._drafts else "0"*64;did=_id(review)
            values={"sequence":len(self._drafts)+1,"draft_id":did,"source_proposal_id":p.proposal_id,"source_proposal_digest":p.proposal_digest,
                "source_review_id":review.review_id,"source_review_digest":review.review_digest,"fixture_schema_digest":p.fixture_schema_digest,
                "synthetic_input_digest":p.synthetic_input_digest,"expected_result_digest":p.expected_result_digest,"rollback_expectation_digest":p.rollback_expectation_digest,
                "blueprint_digest":blueprint,"required_gates":list(FIXTURE_DRAFT_GATES),"drafted_at":drafted_at.isoformat(),"previous_digest":previous,
                "state":FIXTURE_DRAFT_STATE,"scope":FIXTURE_DRAFT_SCOPE,"synthetic_only":True,"separate_review_required":True,"fixture_content_present":False,
                "fixture_serialized":False,"fixture_file_created":False,"dry_run_executed":False,"activation_recorded":False,"rollback_executed":False,
                "network_accessed":False,"money_movement_executed":False,"production_activation_allowed":False}
            item=SyntheticActivationDryRunFixtureDraft(values["sequence"],did,p.proposal_id,p.proposal_digest,review.review_id,review.review_digest,
                p.fixture_schema_digest,p.synthetic_input_digest,p.expected_result_digest,p.rollback_expectation_digest,blueprint,FIXTURE_DRAFT_GATES,drafted_at,previous,canonical_digest(values))
            if before!=docket.evidence()["report_digest"]:raise GovernanceRejected("fixture proposal review changed during draft")
            self._drafts.append(item);self._by_review[review.review_digest]=item;return item
    def verify_draft_chain(self)->bool:
        with self._lock:
            previous="0"*64
            for n,i in enumerate(self._drafts,1):
                if (i.sequence!=n or i.previous_digest!=previous or i.draft_id!=_id_values(i.source_proposal_id,i.source_proposal_digest,i.source_review_digest)
                    or i.draft_digest!=canonical_digest(i.digest_value()) or i.required_gates!=FIXTURE_DRAFT_GATES or i.state!=FIXTURE_DRAFT_STATE or i.scope!=FIXTURE_DRAFT_SCOPE
                    or i.blueprint_digest!=_blueprint(i.fixture_schema_digest,i.synthetic_input_digest,i.expected_result_digest,i.rollback_expectation_digest)
                    or not i.synthetic_only or not i.separate_review_required or any((i.fixture_content_present,i.fixture_serialized,i.fixture_file_created,
                        i.dry_run_executed,i.activation_recorded,i.rollback_executed,i.network_accessed,i.money_movement_executed,i.production_activation_allowed))):return False
                previous=i.draft_digest
            return len(self._drafts)==len(self._by_review) and all(self._by_review.get(i.source_review_digest) is i for i in self._drafts)
    def evidence(self)->dict[str,object]:
        with self._lock:
            v={"schema":"nurion.pg.synthetic-activation-dry-run-fixture-draft-evidence.v1","mode":"UNREGISTERED_SYNTHETIC_ONLY","draft_count":len(self._drafts),
               "draft_digests":[i.draft_digest for i in self._drafts],"draft_chain_valid":self.verify_draft_chain(),"maximum_state":FIXTURE_DRAFT_STATE,"scope":FIXTURE_DRAFT_SCOPE,
               "separate_review_required":True,"fixture_content_present":False,"fixture_serialization_method_present":False,"fixture_creation_method_present":False,
               "dry_run_execution_method_present":False,"activation_method_present":False,"rollback_execution_method_present":False,"filesystem_write_method_present":False,
               "network_access_method_present":False,"automatic_merge_method_present":False,"automatic_deploy_method_present":False,"credentials_used":False,
               "personal_data_used":False,"money_movement_executed":False,"production_activation_allowed":False}
            return {**v,"report_digest":canonical_digest(v)}
