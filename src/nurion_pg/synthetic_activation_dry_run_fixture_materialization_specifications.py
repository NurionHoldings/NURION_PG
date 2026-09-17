"""Non-executable specifications for synthetic fixture materialization."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from .arkaon.governance import GovernanceRejected,canonical_digest
from .synthetic_activation_dry_run_fixture_materialization_plan_review import FixtureMaterializationPlanReviewDecision,FixtureMaterializationPlanReviewState,SyntheticActivationDryRunFixtureMaterializationPlanReviewDocket,SyntheticActivationDryRunFixtureMaterializationPlanReviewRecord,_valid_plan

FIXTURE_MATERIALIZATION_SPECIFICATION_SCOPE="SYNTHETIC_FIXTURE_MATERIALIZATION_SPECIFICATION_DRAFT_ONLY"
FIXTURE_MATERIALIZATION_SPECIFICATION_STATE="SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_MATERIALIZATION_SPECIFICATION_DRAFTED"
FIXTURE_MATERIALIZATION_SPECIFICATION_GATES=("SOURCE_PLAN_REVIEW_PASS_LOCKED","FIXTURE_BLUEPRINT_DIGEST_LOCKED","ARTIFACT_DESCRIPTOR_DIGEST_LOCKED","NO_CONTENT_OR_BYTES","SEPARATE_ETERNIAN_REVIEW_REQUIRED")
_PREFIX="synthetic:activation-dry-run-fixture-materialization-specification:"
def _valid(v:object)->bool:return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _valid_source(r:SyntheticActivationDryRunFixtureMaterializationPlanReviewRecord)->bool:
    return (isinstance(r,SyntheticActivationDryRunFixtureMaterializationPlanReviewRecord)
        and r.state is FixtureMaterializationPlanReviewState.READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_MATERIALIZATION_SPECIFICATION
        and r.decision is FixtureMaterializationPlanReviewDecision.PASS
        and isinstance(r.review_id,str) and r.review_id.startswith("synthetic:activation-dry-run-fixture-materialization-plan-review:")
        and isinstance(r.reviewer_id,str) and r.reviewer_id.startswith("synthetic:eternian-reviewer:activation-dry-run-fixture-materialization-plan:")
        and _valid(r.findings_digest) and r.reviewed_at is not None and r.reviewed_at.tzinfo is not None and r.reviewed_at>=r.submitted_at
        and r.review_digest==canonical_digest(r.review_value()) and _valid_plan(r.plan))
def _id_values(plan_id:str,plan_digest:str,review_digest:str)->str:
    return _PREFIX+canonical_digest({"plan_id":plan_id,"plan_digest":plan_digest,"review_digest":review_digest,"scope":FIXTURE_MATERIALIZATION_SPECIFICATION_SCOPE})[:32]
def _descriptor(blueprint:str,artifact:str,schema:str,synthetic_input:str,expected:str,rollback:str)->str:
    return canonical_digest({"blueprint":blueprint,"artifact":artifact,"schema":schema,"input":synthetic_input,"expected":expected,"rollback":rollback,
        "fixture_content_present":False,"fixture_bytes_present":False,"filesystem_path_present":False,"materialized":False})

@dataclass(frozen=True)
class SyntheticActivationDryRunFixtureMaterializationSpecification:
    sequence:int;source_review:SyntheticActivationDryRunFixtureMaterializationPlanReviewRecord;specification_id:str
    source_plan_id:str;source_plan_digest:str;source_review_id:str;source_review_digest:str;blueprint_digest:str;artifact_descriptor_digest:str
    fixture_schema_digest:str;synthetic_input_digest:str;expected_result_digest:str;rollback_expectation_digest:str;specification_descriptor_digest:str
    scope:str;required_gates:tuple[str,...];state:str;specified_at:datetime;previous_digest:str;specification_digest:str
    synthetic_only:bool=True;separate_review_required:bool=True;fixture_content_present:bool=False;fixture_bytes_present:bool=False
    filesystem_path_present:bool=False;fixture_materialized:bool=False;fixture_file_created:bool=False;filesystem_written:bool=False
    dry_run_executed:bool=False;activation_recorded:bool=False;rollback_executed:bool=False;network_accessed:bool=False
    money_movement_executed:bool=False;production_activation_allowed:bool=False
    def __post_init__(self)->None:
        source=self.source_review;plan=source.plan if _valid_source(source) else None
        if (self.sequence<=0 or plan is None or self.source_plan_id!=plan.plan_id or self.source_plan_digest!=plan.plan_digest
            or self.source_review_id!=source.review_id or self.source_review_digest!=source.review_digest or self.blueprint_digest!=plan.blueprint_digest
            or self.artifact_descriptor_digest!=plan.artifact_descriptor_digest or self.fixture_schema_digest!=plan.fixture_schema_digest
            or self.synthetic_input_digest!=plan.synthetic_input_digest or self.expected_result_digest!=plan.expected_result_digest
            or self.rollback_expectation_digest!=plan.rollback_expectation_digest or not self.specification_id.startswith(_PREFIX)
            or any(not _valid(v) for v in (self.source_plan_digest,self.source_review_digest,self.blueprint_digest,self.artifact_descriptor_digest,
                self.fixture_schema_digest,self.synthetic_input_digest,self.expected_result_digest,self.rollback_expectation_digest,
                self.specification_descriptor_digest,self.previous_digest)) or self.scope!=FIXTURE_MATERIALIZATION_SPECIFICATION_SCOPE
            or self.required_gates!=FIXTURE_MATERIALIZATION_SPECIFICATION_GATES or self.state!=FIXTURE_MATERIALIZATION_SPECIFICATION_STATE
            or self.specified_at.tzinfo is None or not self.synthetic_only or not self.separate_review_required
            or any((self.fixture_content_present,self.fixture_bytes_present,self.filesystem_path_present,self.fixture_materialized,self.fixture_file_created,
                self.filesystem_written,self.dry_run_executed,self.activation_recorded,self.rollback_executed,self.network_accessed,
                self.money_movement_executed,self.production_activation_allowed)) or self.specification_digest!=canonical_digest(self.digest_value())):
            raise GovernanceRejected("valid non-executable fixture materialization specification required")
    def digest_value(self)->dict[str,object]:
        return {"sequence":self.sequence,"specification_id":self.specification_id,"source_plan_id":self.source_plan_id,"source_plan_digest":self.source_plan_digest,
            "source_review_id":self.source_review_id,"source_review_digest":self.source_review_digest,"blueprint_digest":self.blueprint_digest,
            "artifact_descriptor_digest":self.artifact_descriptor_digest,"fixture_schema_digest":self.fixture_schema_digest,
            "synthetic_input_digest":self.synthetic_input_digest,"expected_result_digest":self.expected_result_digest,
            "rollback_expectation_digest":self.rollback_expectation_digest,"specification_descriptor_digest":self.specification_descriptor_digest,
            "scope":self.scope,"required_gates":self.required_gates,"state":self.state,"specified_at":self.specified_at.isoformat(),
            "previous_digest":self.previous_digest,"synthetic_only":self.synthetic_only,"separate_review_required":self.separate_review_required,
            "fixture_content_present":self.fixture_content_present,"fixture_bytes_present":self.fixture_bytes_present,
            "filesystem_path_present":self.filesystem_path_present,"fixture_materialized":self.fixture_materialized,
            "fixture_file_created":self.fixture_file_created,"filesystem_written":self.filesystem_written,"dry_run_executed":self.dry_run_executed,
            "activation_recorded":self.activation_recorded,"rollback_executed":self.rollback_executed,"network_accessed":self.network_accessed,
            "money_movement_executed":self.money_movement_executed,"production_activation_allowed":self.production_activation_allowed}

class SyntheticActivationDryRunFixtureMaterializationSpecificationBook:
    def __init__(self)->None:self._specifications=[];self._by_review={};self._lock=RLock()
    @property
    def specifications(self)->tuple[SyntheticActivationDryRunFixtureMaterializationSpecification,...]:
        with self._lock:return tuple(self._specifications)
    def specify_from_review(self,docket:SyntheticActivationDryRunFixtureMaterializationPlanReviewDocket,plan_id:str,*,specified_at:datetime)->SyntheticActivationDryRunFixtureMaterializationSpecification:
        if not isinstance(docket,SyntheticActivationDryRunFixtureMaterializationPlanReviewDocket) or not docket.verify_chain():raise GovernanceRejected("intact typed materialization plan review docket required")
        if specified_at.tzinfo is None:raise GovernanceRejected("timezone-aware fixture materialization specification required")
        review=docket.ready_source(plan_id)
        if not _valid_source(review) or specified_at<review.reviewed_at:raise GovernanceRejected("passed materialization plan review required")
        before=docket.evidence()["report_digest"];plan=review.plan
        with self._lock:
            if not self.verify_specification_chain():raise GovernanceRejected("existing fixture materialization specification chain invalid")
            old=self._by_review.get(review.review_digest)
            if old is not None:return old
            previous=self._specifications[-1].specification_digest if self._specifications else "0"*64
            sid=_id_values(plan.plan_id,plan.plan_digest,review.review_digest)
            descriptor=_descriptor(plan.blueprint_digest,plan.artifact_descriptor_digest,plan.fixture_schema_digest,plan.synthetic_input_digest,plan.expected_result_digest,plan.rollback_expectation_digest)
            values={"sequence":len(self._specifications)+1,"specification_id":sid,"source_plan_id":plan.plan_id,"source_plan_digest":plan.plan_digest,
                "source_review_id":review.review_id,"source_review_digest":review.review_digest,"blueprint_digest":plan.blueprint_digest,
                "artifact_descriptor_digest":plan.artifact_descriptor_digest,"fixture_schema_digest":plan.fixture_schema_digest,
                "synthetic_input_digest":plan.synthetic_input_digest,"expected_result_digest":plan.expected_result_digest,
                "rollback_expectation_digest":plan.rollback_expectation_digest,"specification_descriptor_digest":descriptor,
                "scope":FIXTURE_MATERIALIZATION_SPECIFICATION_SCOPE,"required_gates":FIXTURE_MATERIALIZATION_SPECIFICATION_GATES,
                "state":FIXTURE_MATERIALIZATION_SPECIFICATION_STATE,"specified_at":specified_at.isoformat(),"previous_digest":previous,
                "synthetic_only":True,"separate_review_required":True,"fixture_content_present":False,"fixture_bytes_present":False,
                "filesystem_path_present":False,"fixture_materialized":False,"fixture_file_created":False,"filesystem_written":False,
                "dry_run_executed":False,"activation_recorded":False,"rollback_executed":False,"network_accessed":False,
                "money_movement_executed":False,"production_activation_allowed":False}
            item=SyntheticActivationDryRunFixtureMaterializationSpecification(len(self._specifications)+1,review,sid,plan.plan_id,plan.plan_digest,
                review.review_id,review.review_digest,plan.blueprint_digest,plan.artifact_descriptor_digest,plan.fixture_schema_digest,
                plan.synthetic_input_digest,plan.expected_result_digest,plan.rollback_expectation_digest,descriptor,
                FIXTURE_MATERIALIZATION_SPECIFICATION_SCOPE,FIXTURE_MATERIALIZATION_SPECIFICATION_GATES,FIXTURE_MATERIALIZATION_SPECIFICATION_STATE,
                specified_at,previous,canonical_digest(values))
            if before!=docket.evidence()["report_digest"]:raise GovernanceRejected("materialization plan review changed during specification")
            self._specifications.append(item);self._by_review[review.review_digest]=item;return item
    def verify_specification_chain(self)->bool:
        with self._lock:
            previous="0"*64
            for n,i in enumerate(self._specifications,1):
                source=i.source_review;plan=source.plan if _valid_source(source) else None
                if (i.sequence!=n or i.previous_digest!=previous or plan is None or i.source_plan_id!=plan.plan_id or i.source_plan_digest!=plan.plan_digest
                    or i.source_review_id!=source.review_id or i.source_review_digest!=source.review_digest or i.blueprint_digest!=plan.blueprint_digest
                    or i.artifact_descriptor_digest!=plan.artifact_descriptor_digest or i.fixture_schema_digest!=plan.fixture_schema_digest
                    or i.synthetic_input_digest!=plan.synthetic_input_digest or i.expected_result_digest!=plan.expected_result_digest
                    or i.rollback_expectation_digest!=plan.rollback_expectation_digest
                    or i.specification_id!=_id_values(i.source_plan_id,i.source_plan_digest,i.source_review_digest)
                    or i.specification_descriptor_digest!=_descriptor(i.blueprint_digest,i.artifact_descriptor_digest,i.fixture_schema_digest,
                        i.synthetic_input_digest,i.expected_result_digest,i.rollback_expectation_digest)
                    or i.specification_digest!=canonical_digest(i.digest_value()) or i.scope!=FIXTURE_MATERIALIZATION_SPECIFICATION_SCOPE
                    or i.required_gates!=FIXTURE_MATERIALIZATION_SPECIFICATION_GATES or i.state!=FIXTURE_MATERIALIZATION_SPECIFICATION_STATE
                    or not i.synthetic_only or not i.separate_review_required or any((i.fixture_content_present,i.fixture_bytes_present,
                        i.filesystem_path_present,i.fixture_materialized,i.fixture_file_created,i.filesystem_written,i.dry_run_executed,
                        i.activation_recorded,i.rollback_executed,i.network_accessed,i.money_movement_executed,i.production_activation_allowed))):return False
                previous=i.specification_digest
            return len(self._specifications)==len(self._by_review) and all(self._by_review.get(i.source_review_digest) is i for i in self._specifications)
    def evidence(self)->dict[str,object]:
        with self._lock:
            v={"schema":"nurion.pg.synthetic-activation-dry-run-fixture-materialization-specification-evidence.v1","mode":"UNREGISTERED_SYNTHETIC_ONLY",
               "specification_count":len(self._specifications),"specification_digests":[i.specification_digest for i in self._specifications],
               "specification_chain_valid":self.verify_specification_chain(),"scope":FIXTURE_MATERIALIZATION_SPECIFICATION_SCOPE,
               "maximum_state":FIXTURE_MATERIALIZATION_SPECIFICATION_STATE,"fixture_content_method_present":False,"fixture_bytes_method_present":False,
               "filesystem_path_method_present":False,"fixture_materialization_method_present":False,"fixture_creation_method_present":False,
               "filesystem_write_method_present":False,"dry_run_execution_method_present":False,"activation_method_present":False,
               "rollback_execution_method_present":False,"network_access_method_present":False,"automatic_merge_method_present":False,
               "automatic_deploy_method_present":False,"credentials_used":False,"personal_data_used":False,"money_movement_executed":False,
               "production_activation_allowed":False};return {**v,"report_digest":canonical_digest(v)}
