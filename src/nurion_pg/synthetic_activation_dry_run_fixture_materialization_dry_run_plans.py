"""Non-executable dry-run plans for synthetic fixture materialization."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from .arkaon.governance import GovernanceRejected,canonical_digest
from .synthetic_activation_dry_run_fixture_materialization_specification_review import FixtureMaterializationSpecificationReviewDecision,FixtureMaterializationSpecificationReviewState,SyntheticActivationDryRunFixtureMaterializationSpecificationReviewDocket,SyntheticActivationDryRunFixtureMaterializationSpecificationReviewRecord,_valid_specification

MATERIALIZATION_DRY_RUN_PLAN_SCOPE="SYNTHETIC_FIXTURE_MATERIALIZATION_DRY_RUN_PLAN_DRAFT_ONLY"
MATERIALIZATION_DRY_RUN_PLAN_STATE="SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_MATERIALIZATION_DRY_RUN_PLAN_DRAFTED"
MATERIALIZATION_DRY_RUN_PLAN_GATES=("SOURCE_SPECIFICATION_REVIEW_PASS_LOCKED","SPECIFICATION_DESCRIPTOR_DIGEST_LOCKED","NO_CONTENT_BYTES_PATH_OR_FILE","NO_EXECUTION","SEPARATE_ETERNIAN_REVIEW_REQUIRED")
_PREFIX="synthetic:activation-dry-run-fixture-materialization-dry-run-plan:"
def _valid(v:object)->bool:return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _valid_source(r:SyntheticActivationDryRunFixtureMaterializationSpecificationReviewRecord)->bool:
    return (isinstance(r,SyntheticActivationDryRunFixtureMaterializationSpecificationReviewRecord)
        and r.state is FixtureMaterializationSpecificationReviewState.READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_MATERIALIZATION_DRY_RUN_PLAN
        and r.decision is FixtureMaterializationSpecificationReviewDecision.PASS and r._valid_final() and _valid_specification(r.specification))
def _id_values(specification_id:str,specification_digest:str,review_digest:str)->str:
    return _PREFIX+canonical_digest({"specification_id":specification_id,"specification_digest":specification_digest,
        "review_digest":review_digest,"scope":MATERIALIZATION_DRY_RUN_PLAN_SCOPE})[:32]
def _contract(specification_descriptor:str,blueprint:str,artifact:str,rollback:str)->str:
    return canonical_digest({"specification_descriptor":specification_descriptor,"blueprint":blueprint,"artifact":artifact,
        "rollback":rollback,"content_present":False,"bytes_present":False,"path_present":False,"file_present":False,
        "materialization_executed":False,"dry_run_executed":False})

@dataclass(frozen=True)
class SyntheticActivationDryRunFixtureMaterializationDryRunPlan:
    sequence:int;source_review:SyntheticActivationDryRunFixtureMaterializationSpecificationReviewRecord;plan_id:str
    source_specification_id:str;source_specification_digest:str;source_review_id:str;source_review_digest:str
    specification_descriptor_digest:str;blueprint_digest:str;artifact_descriptor_digest:str;rollback_expectation_digest:str
    dry_run_contract_digest:str;scope:str;required_gates:tuple[str,...];state:str;planned_at:datetime;previous_digest:str;plan_digest:str
    synthetic_only:bool=True;separate_review_required:bool=True;fixture_content_present:bool=False;fixture_bytes_present:bool=False
    filesystem_path_present:bool=False;fixture_file_present:bool=False;fixture_materialized:bool=False;filesystem_written:bool=False
    dry_run_executed:bool=False;activation_recorded:bool=False;rollback_executed:bool=False;network_accessed:bool=False
    money_movement_executed:bool=False;production_activation_allowed:bool=False
    def __post_init__(self)->None:
        source=self.source_review;spec=source.specification if _valid_source(source) else None
        if (self.sequence<=0 or spec is None or self.source_specification_id!=spec.specification_id
            or self.source_specification_digest!=spec.specification_digest or self.source_review_id!=source.review_id
            or self.source_review_digest!=source.review_digest or self.specification_descriptor_digest!=spec.specification_descriptor_digest
            or self.blueprint_digest!=spec.blueprint_digest or self.artifact_descriptor_digest!=spec.artifact_descriptor_digest
            or self.rollback_expectation_digest!=spec.rollback_expectation_digest or not self.plan_id.startswith(_PREFIX)
            or any(not _valid(v) for v in (self.source_specification_digest,self.source_review_digest,self.specification_descriptor_digest,
                self.blueprint_digest,self.artifact_descriptor_digest,self.rollback_expectation_digest,self.dry_run_contract_digest,self.previous_digest))
            or self.scope!=MATERIALIZATION_DRY_RUN_PLAN_SCOPE or self.required_gates!=MATERIALIZATION_DRY_RUN_PLAN_GATES
            or self.state!=MATERIALIZATION_DRY_RUN_PLAN_STATE or self.planned_at.tzinfo is None
            or not self.synthetic_only or not self.separate_review_required
            or any((self.fixture_content_present,self.fixture_bytes_present,self.filesystem_path_present,self.fixture_file_present,
                self.fixture_materialized,self.filesystem_written,self.dry_run_executed,self.activation_recorded,self.rollback_executed,
                self.network_accessed,self.money_movement_executed,self.production_activation_allowed))
            or self.plan_digest!=canonical_digest(self.digest_value())):raise GovernanceRejected("valid non-executable materialization dry-run plan required")
    def digest_value(self)->dict[str,object]:
        return {"sequence":self.sequence,"plan_id":self.plan_id,"source_specification_id":self.source_specification_id,
            "source_specification_digest":self.source_specification_digest,"source_review_id":self.source_review_id,
            "source_review_digest":self.source_review_digest,"specification_descriptor_digest":self.specification_descriptor_digest,
            "blueprint_digest":self.blueprint_digest,"artifact_descriptor_digest":self.artifact_descriptor_digest,
            "rollback_expectation_digest":self.rollback_expectation_digest,"dry_run_contract_digest":self.dry_run_contract_digest,
            "scope":self.scope,"required_gates":self.required_gates,"state":self.state,"planned_at":self.planned_at.isoformat(),
            "previous_digest":self.previous_digest,"synthetic_only":self.synthetic_only,"separate_review_required":self.separate_review_required,
            "fixture_content_present":self.fixture_content_present,"fixture_bytes_present":self.fixture_bytes_present,
            "filesystem_path_present":self.filesystem_path_present,"fixture_file_present":self.fixture_file_present,
            "fixture_materialized":self.fixture_materialized,"filesystem_written":self.filesystem_written,
            "dry_run_executed":self.dry_run_executed,"activation_recorded":self.activation_recorded,"rollback_executed":self.rollback_executed,
            "network_accessed":self.network_accessed,"money_movement_executed":self.money_movement_executed,
            "production_activation_allowed":self.production_activation_allowed}

class SyntheticActivationDryRunFixtureMaterializationDryRunPlanBook:
    def __init__(self)->None:self._plans=[];self._by_review={};self._lock=RLock()
    @property
    def plans(self)->tuple[SyntheticActivationDryRunFixtureMaterializationDryRunPlan,...]:
        with self._lock:return tuple(self._plans)
    def plan_from_review(self,docket:SyntheticActivationDryRunFixtureMaterializationSpecificationReviewDocket,specification_id:str,*,planned_at:datetime)->SyntheticActivationDryRunFixtureMaterializationDryRunPlan:
        if not isinstance(docket,SyntheticActivationDryRunFixtureMaterializationSpecificationReviewDocket) or not docket.verify_chain():
            raise GovernanceRejected("intact typed materialization specification review docket required")
        if planned_at.tzinfo is None:raise GovernanceRejected("timezone-aware materialization dry-run plan required")
        review=docket.ready_source(specification_id)
        if not _valid_source(review) or planned_at<review.reviewed_at:raise GovernanceRejected("passed materialization specification review required")
        before=docket.evidence()["report_digest"];spec=review.specification
        with self._lock:
            if not self.verify_plan_chain():raise GovernanceRejected("existing materialization dry-run plan chain invalid")
            old=self._by_review.get(review.review_digest)
            if old is not None:return old
            previous=self._plans[-1].plan_digest if self._plans else "0"*64
            pid=_id_values(spec.specification_id,spec.specification_digest,review.review_digest)
            contract=_contract(spec.specification_descriptor_digest,spec.blueprint_digest,spec.artifact_descriptor_digest,spec.rollback_expectation_digest)
            values={"sequence":len(self._plans)+1,"plan_id":pid,"source_specification_id":spec.specification_id,
                "source_specification_digest":spec.specification_digest,"source_review_id":review.review_id,"source_review_digest":review.review_digest,
                "specification_descriptor_digest":spec.specification_descriptor_digest,"blueprint_digest":spec.blueprint_digest,
                "artifact_descriptor_digest":spec.artifact_descriptor_digest,"rollback_expectation_digest":spec.rollback_expectation_digest,
                "dry_run_contract_digest":contract,"scope":MATERIALIZATION_DRY_RUN_PLAN_SCOPE,"required_gates":MATERIALIZATION_DRY_RUN_PLAN_GATES,
                "state":MATERIALIZATION_DRY_RUN_PLAN_STATE,"planned_at":planned_at.isoformat(),"previous_digest":previous,"synthetic_only":True,
                "separate_review_required":True,"fixture_content_present":False,"fixture_bytes_present":False,"filesystem_path_present":False,
                "fixture_file_present":False,"fixture_materialized":False,"filesystem_written":False,"dry_run_executed":False,
                "activation_recorded":False,"rollback_executed":False,"network_accessed":False,"money_movement_executed":False,
                "production_activation_allowed":False}
            item=SyntheticActivationDryRunFixtureMaterializationDryRunPlan(len(self._plans)+1,review,pid,spec.specification_id,
                spec.specification_digest,review.review_id,review.review_digest,spec.specification_descriptor_digest,spec.blueprint_digest,
                spec.artifact_descriptor_digest,spec.rollback_expectation_digest,contract,MATERIALIZATION_DRY_RUN_PLAN_SCOPE,
                MATERIALIZATION_DRY_RUN_PLAN_GATES,MATERIALIZATION_DRY_RUN_PLAN_STATE,planned_at,previous,canonical_digest(values))
            if before!=docket.evidence()["report_digest"]:raise GovernanceRejected("specification review changed during dry-run planning")
            self._plans.append(item);self._by_review[review.review_digest]=item;return item
    def verify_plan_chain(self)->bool:
        with self._lock:
            previous="0"*64
            for n,i in enumerate(self._plans,1):
                source=i.source_review;spec=source.specification if _valid_source(source) else None
                if (i.sequence!=n or i.previous_digest!=previous or spec is None or i.source_specification_id!=spec.specification_id
                    or i.source_specification_digest!=spec.specification_digest or i.source_review_id!=source.review_id
                    or i.source_review_digest!=source.review_digest or i.specification_descriptor_digest!=spec.specification_descriptor_digest
                    or i.blueprint_digest!=spec.blueprint_digest or i.artifact_descriptor_digest!=spec.artifact_descriptor_digest
                    or i.rollback_expectation_digest!=spec.rollback_expectation_digest
                    or i.plan_id!=_id_values(i.source_specification_id,i.source_specification_digest,i.source_review_digest)
                    or i.dry_run_contract_digest!=_contract(i.specification_descriptor_digest,i.blueprint_digest,i.artifact_descriptor_digest,i.rollback_expectation_digest)
                    or i.plan_digest!=canonical_digest(i.digest_value()) or i.scope!=MATERIALIZATION_DRY_RUN_PLAN_SCOPE
                    or i.required_gates!=MATERIALIZATION_DRY_RUN_PLAN_GATES or i.state!=MATERIALIZATION_DRY_RUN_PLAN_STATE
                    or not i.synthetic_only or not i.separate_review_required or any((i.fixture_content_present,i.fixture_bytes_present,
                        i.filesystem_path_present,i.fixture_file_present,i.fixture_materialized,i.filesystem_written,i.dry_run_executed,
                        i.activation_recorded,i.rollback_executed,i.network_accessed,i.money_movement_executed,i.production_activation_allowed))):return False
                previous=i.plan_digest
            return len(self._plans)==len(self._by_review) and all(self._by_review.get(i.source_review_digest) is i for i in self._plans)
    def evidence(self)->dict[str,object]:
        with self._lock:
            v={"schema":"nurion.pg.synthetic-activation-dry-run-fixture-materialization-dry-run-plan-evidence.v1",
               "mode":"UNREGISTERED_SYNTHETIC_ONLY","plan_count":len(self._plans),"plan_digests":[i.plan_digest for i in self._plans],
               "plan_chain_valid":self.verify_plan_chain(),"scope":MATERIALIZATION_DRY_RUN_PLAN_SCOPE,"maximum_state":MATERIALIZATION_DRY_RUN_PLAN_STATE,
               "fixture_content_method_present":False,"fixture_bytes_method_present":False,"filesystem_path_method_present":False,
               "fixture_file_method_present":False,"fixture_materialization_method_present":False,"filesystem_write_method_present":False,
               "dry_run_execution_method_present":False,"activation_method_present":False,"rollback_execution_method_present":False,
               "network_access_method_present":False,"automatic_merge_method_present":False,"automatic_deploy_method_present":False,
               "credentials_used":False,"personal_data_used":False,"money_movement_executed":False,"production_activation_allowed":False}
            return {**v,"report_digest":canonical_digest(v)}
