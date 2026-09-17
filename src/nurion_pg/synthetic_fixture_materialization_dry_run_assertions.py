"""Unevaluated assertions for synthetic fixture materialization dry-runs."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from .arkaon.governance import GovernanceRejected,canonical_digest
from .synthetic_fixture_materialization_dry_run_expectation_review import ExpectationReviewDecision,ExpectationReviewState,SyntheticFixtureMaterializationDryRunExpectationReviewDocket,SyntheticFixtureMaterializationDryRunExpectationReviewRecord,_valid_expectation
ASSERTION_SCOPE="SYNTHETIC_FIXTURE_MATERIALIZATION_DRY_RUN_ASSERTION_DRAFT_ONLY"
ASSERTION_STATE="SYNTHETIC_FIXTURE_MATERIALIZATION_DRY_RUN_ASSERTION_DRAFTED"
ASSERTION_GATES=("SOURCE_EXPECTATION_REVIEW_PASS_LOCKED","EXPECTATION_DESCRIPTOR_DIGEST_LOCKED","NO_EVALUATION_OR_RESULT","NO_EXECUTION","SEPARATE_ETERNIAN_REVIEW_REQUIRED")
_PREFIX="synthetic:fixture-materialization-dry-run-assertion:"
def _valid(v:object)->bool:return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _valid_source(r:SyntheticFixtureMaterializationDryRunExpectationReviewRecord)->bool:
    return (isinstance(r,SyntheticFixtureMaterializationDryRunExpectationReviewRecord) and r.sequence>0
        and r.submitted_at.tzinfo is not None and r.submitted_at>=r.expectation.drafted_at and _valid(r.previous_digest)
        and r.submission_digest==canonical_digest(r.submission_value())
        and r.state is ExpectationReviewState.READY_FOR_SYNTHETIC_FIXTURE_MATERIALIZATION_DRY_RUN_ASSERTION_DRAFT
        and r.decision is ExpectationReviewDecision.PASS and r._valid_final() and _valid_expectation(r.expectation))
def _id(expectation_id:str,expectation_digest:str,review_digest:str)->str:
    return _PREFIX+canonical_digest({"expectation_id":expectation_id,"expectation_digest":expectation_digest,"review_digest":review_digest,"scope":ASSERTION_SCOPE})[:32]
def _descriptor(expectation:str,scenario:str,rollback:str)->str:
    return canonical_digest({"expectation":expectation,"scenario":scenario,"rollback":rollback,"evaluation_present":False,"result_present":False,"dry_run_executed":False})
@dataclass(frozen=True)
class SyntheticFixtureMaterializationDryRunAssertion:
    sequence:int;source_review:SyntheticFixtureMaterializationDryRunExpectationReviewRecord;assertion_id:str
    source_expectation_id:str;source_expectation_digest:str;source_review_digest:str;expectation_descriptor_digest:str
    scenario_descriptor_digest:str;rollback_expectation_digest:str;assertion_descriptor_digest:str
    scope:str;required_gates:tuple[str,...];state:str;drafted_at:datetime;previous_digest:str;assertion_digest:str
    synthetic_only:bool=True;separate_review_required:bool=True;evaluation_present:bool=False;result_present:bool=False
    fixture_materialized:bool=False;filesystem_written:bool=False;dry_run_executed:bool=False;activation_recorded:bool=False
    rollback_executed:bool=False;network_accessed:bool=False;money_movement_executed:bool=False;production_activation_allowed:bool=False
    def __post_init__(self)->None:
        source=self.source_review;e=source.expectation if _valid_source(source) else None
        if (self.sequence<=0 or e is None or self.source_expectation_id!=e.expectation_id or self.source_expectation_digest!=e.expectation_digest
            or self.source_review_digest!=source.review_digest or self.expectation_descriptor_digest!=e.expectation_descriptor_digest
            or self.scenario_descriptor_digest!=e.scenario_descriptor_digest or self.rollback_expectation_digest!=e.rollback_expectation_digest
            or self.assertion_id!=_id(self.source_expectation_id,self.source_expectation_digest,self.source_review_digest)
            or self.assertion_descriptor_digest!=_descriptor(self.expectation_descriptor_digest,self.scenario_descriptor_digest,self.rollback_expectation_digest)
            or self.scope!=ASSERTION_SCOPE or self.required_gates!=ASSERTION_GATES or self.state!=ASSERTION_STATE or self.drafted_at.tzinfo is None
            or not self.synthetic_only or not self.separate_review_required or any((self.evaluation_present,self.result_present,self.fixture_materialized,
                self.filesystem_written,self.dry_run_executed,self.activation_recorded,self.rollback_executed,self.network_accessed,
                self.money_movement_executed,self.production_activation_allowed)) or self.assertion_digest!=canonical_digest(self.digest_value())):
            raise GovernanceRejected("valid unevaluated assertion required")
    def digest_value(self)->dict[str,object]:return {k:(v.isoformat() if isinstance(v,datetime) else v) for k,v in self.__dict__.items() if k not in ("source_review","assertion_digest")}
class SyntheticFixtureMaterializationDryRunAssertionBook:
    def __init__(self)->None:self._items=[];self._by_review={};self._lock=RLock()
    @property
    def assertions(self)->tuple[SyntheticFixtureMaterializationDryRunAssertion,...]:
        with self._lock:return tuple(self._items)
    def draft_from_review(self,docket:SyntheticFixtureMaterializationDryRunExpectationReviewDocket,expectation_id:str,*,drafted_at:datetime)->SyntheticFixtureMaterializationDryRunAssertion:
        if not isinstance(docket,SyntheticFixtureMaterializationDryRunExpectationReviewDocket) or not docket.verify_chain():raise GovernanceRejected("intact typed expectation review docket required")
        review=docket.ready_source(expectation_id)
        if drafted_at.tzinfo is None or not _valid_source(review) or drafted_at<review.reviewed_at:raise GovernanceRejected("passed expectation review required")
        before=docket.evidence()["report_digest"];e=review.expectation
        with self._lock:
            if not self.verify_chain():raise GovernanceRejected("existing assertion chain invalid")
            old=self._by_review.get(review.review_digest)
            if old is not None:return old
            previous=self._items[-1].assertion_digest if self._items else "0"*64;aid=_id(e.expectation_id,e.expectation_digest,review.review_digest)
            descriptor=_descriptor(e.expectation_descriptor_digest,e.scenario_descriptor_digest,e.rollback_expectation_digest)
            values={"sequence":len(self._items)+1,"assertion_id":aid,"source_expectation_id":e.expectation_id,
                "source_expectation_digest":e.expectation_digest,"source_review_digest":review.review_digest,
                "expectation_descriptor_digest":e.expectation_descriptor_digest,"scenario_descriptor_digest":e.scenario_descriptor_digest,
                "rollback_expectation_digest":e.rollback_expectation_digest,"assertion_descriptor_digest":descriptor,"scope":ASSERTION_SCOPE,
                "required_gates":ASSERTION_GATES,"state":ASSERTION_STATE,"drafted_at":drafted_at.isoformat(),"previous_digest":previous,
                "synthetic_only":True,"separate_review_required":True,"evaluation_present":False,"result_present":False,
                "fixture_materialized":False,"filesystem_written":False,"dry_run_executed":False,"activation_recorded":False,
                "rollback_executed":False,"network_accessed":False,"money_movement_executed":False,"production_activation_allowed":False}
            item=SyntheticFixtureMaterializationDryRunAssertion(len(self._items)+1,review,aid,e.expectation_id,e.expectation_digest,
                review.review_digest,e.expectation_descriptor_digest,e.scenario_descriptor_digest,e.rollback_expectation_digest,descriptor,
                ASSERTION_SCOPE,ASSERTION_GATES,ASSERTION_STATE,drafted_at,previous,canonical_digest(values))
            if before!=docket.evidence()["report_digest"]:raise GovernanceRejected("source changed during assertion drafting")
            self._items.append(item);self._by_review[review.review_digest]=item;return item
    def verify_chain(self)->bool:
        with self._lock:
            previous="0"*64
            for n,i in enumerate(self._items,1):
                try:SyntheticFixtureMaterializationDryRunAssertion(**i.__dict__)
                except GovernanceRejected:return False
                if i.sequence!=n or i.previous_digest!=previous:return False
                previous=i.assertion_digest
            return len(self._items)==len(self._by_review) and all(self._by_review.get(i.source_review_digest) is i for i in self._items)
    def evidence(self)->dict[str,object]:
        with self._lock:
            v={"schema":"nurion.pg.synthetic-fixture-materialization-dry-run-assertion-evidence.v1","mode":"UNREGISTERED_SYNTHETIC_ONLY",
               "assertion_count":len(self._items),"assertion_digests":[i.assertion_digest for i in self._items],"assertion_chain_valid":self.verify_chain(),
               "scope":ASSERTION_SCOPE,"maximum_state":ASSERTION_STATE,"evaluation_method_present":False,"result_method_present":False,
               "fixture_materialization_method_present":False,"filesystem_write_method_present":False,"dry_run_execution_method_present":False,
               "activation_method_present":False,"network_access_method_present":False,"automatic_merge_method_present":False,
               "automatic_deploy_method_present":False,"credentials_used":False,"personal_data_used":False,"money_movement_executed":False,
               "production_activation_allowed":False};return {**v,"report_digest":canonical_digest(v)}
