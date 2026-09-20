"""Non-executed observation readiness manifest and approval gate #13901-#14300."""
from dataclasses import dataclass
from threading import RLock

from .arkaon.governance import GovernanceRejected,canonical_digest
from .synthetic_observation_contract_gate import APPLIED_LESSONS as PRIOR_LESSONS,APPLIED_RULES,CASE_KEYS,SyntheticObservationContractGate

APPLIED_LESSONS=tuple(sorted(PRIOR_LESSONS+("ARL-13901-001",)))
WORKSTREAM_NAMES=("SOURCE_CONTRACT_ANCHOR","STAGE_SNAPSHOT_CHAIN","MANIFEST_IDENTITY","RESOURCE_BUDGET","PRIVACY_CLASSIFICATION","DATA_CLASSIFICATION","DETERMINISM","ISOLATION","TIMEOUT_POLICY","SIDE_EFFECT_PROHIBITION","RECEIPT_SCHEMA","INDEPENDENT_APPROVAL_GATE","RECOVERY_GUIDANCE","STOP_RESUME_ROLLBACK","FULL_LINEAGE_REHASH","NON_EXECUTION_NON_AUTHORITY")
WORKSTREAMS=tuple((13901+i*25,13925+i*25,n) for i,n in enumerate(WORKSTREAM_NAMES))
CONTROL_ASPECTS=("input_schema","required_fields","semantic_label","source_type","tenant_scope","role_scope","state_precondition","latest_sequence","source_binding","digest_recalculation","negative_path","missing_input","duplicate_input","replay","conflict","stale_version","concurrency","partial_batch","ordering","append_only","hold_propagation","review_independence","receipt_lineage","operator_gate","non_execution")
NEGATIVE=frozenset({"negative_path","missing_input","duplicate_input","replay","conflict","stale_version","partial_batch"})
STAGE_MAPPING=(("ARKAON-LESSONS-12301",(9901,12700)),("ARKAON-LESSONS-12701",(12701,13100)),("ARKAON-LESSONS-13101",(13101,13500)),("ARKAON-LESSONS-13501",(13501,13900)),("ARKAON-LESSONS-13901",(13901,14300)))
def _hex(v):return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _syn(v,k):return isinstance(v,str) and v.startswith(f"synthetic:{k}:")
def _id(v):return v.rsplit(":",1)[-1].casefold()
def mapping_digest(rows):return canonical_digest(("CONTIGUOUS_STAGE_MAPPING",tuple(rows)))

@dataclass(frozen=True)
class Control:control_id:int;workstream:str;aspect:str;requirement_ref:str;fixture_digest:str;expected_result:str;digest:str
@dataclass(frozen=True)
class Snapshot:snapshot_id:str;stage_range:tuple;mapping_digest:str;registry_digest:str;manifest_digest:str;lesson_ids:tuple;rule_ids:tuple;source_docket_digest:str;previous_snapshot_digest:str;sequence:int;latest:bool;digest:str
@dataclass(frozen=True)
class Plan:plan_id:str;flow:str;kind:str;source_contract_digest:str;manifest_identity:tuple|None;resource_budget:tuple|None;privacy_classification:tuple|None;data_classification:tuple|None;determinism:tuple|None;isolation:tuple|None;timeout_policy:tuple|None;side_effect_policy:tuple|None;receipt_schema:tuple|None;approval_gate:tuple|None;recovery_paths:tuple;planner:str|None;challenger:str|None;parent_digest:str|None;position:int;status:str;held:bool;pending_human_judgment:bool;materialized:bool;executed:bool;digest:str
@dataclass(frozen=True)
class Docket:docket_id:str;snapshot_digest:str;plan_set_digest:str;compiler:str;validator:str;role_lineage_digest:str;complete:bool;held:bool;pending_human_judgment:bool;materialized:bool;executed:bool;passed:bool;failed:bool;approved:bool;activated:bool;deployed:bool;status:str;digest:str

def readiness_terms(source,flow,kind,snapshot):
    seed=canonical_digest(("READINESS_PLAN",source.digest,flow,kind,snapshot))
    return (("manifest_identity",f"synthetic:observation-readiness:{flow}:{kind}",seed,"PLAN_ONLY_NO_BYTES"),("resource_budget",("cpu_millis",100),("memory_mb",64),("output_bytes",4096),"HARD_LIMITS_NOT_ALLOCATED"),("privacy_classification","NO_PERSONAL_DATA","NO_SECRET","NO_CREDENTIAL","REJECT_UNKNOWN"),("data_classification","SYNTHETIC_METADATA_ONLY","NO_PAYMENT_DATA","NO_LEDGER_DATA","NO_EXTERNAL_INPUT"),("determinism",seed,"FIXED_ORDER","NO_CLOCK_NO_RANDOM_NO_NETWORK"),("isolation","EPHEMERAL_DENY_ALL","NO_FILESYSTEM_WRITE","NO_NETWORK","NO_SHARED_STATE"),("timeout_policy",1000,"ABORT_WITHOUT_RESULT","NO_RETRY_WITHOUT_NEW_APPROVAL"),("side_effect_policy","STRICTLY_PROHIBITED","NO_PG_NO_LEDGER_NO_CREDENTIAL_NO_DEPLOY"),("receipt_schema","PLAN_RECEIPT_V1",("manifest_digest","source_digest","actor_lineage","status"),"NO_OBSERVATION_VALUE"),("approval_gate","TWO_DISTINCT_HUMANS_REQUIRED","MATERIALIZATION_SEPARATE_APPROVAL","EXECUTION_SEPARATE_APPROVAL","PENDING"),(("MINIMAL_PLAN_REPAIR","repair_missing_bound_field","LOW","LOW","HIGH","validate_then_rechallenge","discard_candidate_preserve_source","resume_after_complete_independent_gate"),("FRESH_READINESS_RECONSTRUCTION","rebuild_from_source_contract","MEDIUM","LOW","HIGH","stop_on_source_drift","independent_full_manifest_validation","quarantine_old_plan","resume_after_two-person_gate")))

class SyntheticObservationReadinessManifest:
    def __init__(self):self._controls={};self._source=None;self._snapshot=None;self._plans={};self._docket=None;self._events=[];self._holds=[];self._lock=RLock()
    def _expected(self,cid):i=cid-13901;return WORKSTREAM_NAMES[i//25],CONTROL_ASPECTS[i%25]
    def add_control(self,cid,workstream,aspect,requirement_ref,fixture_digest,expected_result):
        p=dict(control_id=cid,workstream=workstream,aspect=aspect,requirement_ref=requirement_ref,fixture_digest=fixture_digest,expected_result=expected_result);r=Control(**p,digest=canonical_digest(p))
        with self._lock:
            if not self._control_valid(r):raise GovernanceRejected("valid #13901-#14300 control required")
            old=self._controls.get(cid)
            if old:
                if old==r:return old
                raise GovernanceRejected("control conflict")
            self._controls[cid]=r;return r
    def anchor(self,source,mapping,registry,manifest,lessons,rules,previous_snapshot,sequence,latest):
        if not isinstance(source,SyntheticObservationContractGate):raise GovernanceRejected("prior observation contract required")
        e=source.evidence();p=dict(snapshot_id="synthetic:lesson-snapshot:13901-14300",stage_range=(13901,14300),mapping_digest=mapping,registry_digest=registry,manifest_digest=manifest,lesson_ids=tuple(lessons),rule_ids=tuple(rules),source_docket_digest=source._docket.digest if source._docket else None,previous_snapshot_digest=previous_snapshot,sequence=sequence,latest=latest);r=Snapshot(**p,digest=canonical_digest(p))
        with self._lock:
            if not(self._registry_valid() and e["complete_observation_contract_gate_evidence"] and e["integrity_valid"] and mapping==mapping_digest(STAGE_MAPPING) and _hex(registry) and _hex(manifest) and tuple(lessons)==APPLIED_LESSONS and tuple(rules)==APPLIED_RULES and previous_snapshot==source._snapshot.digest and isinstance(sequence,int) and not isinstance(sequence,bool) and sequence>0 and latest is True):raise GovernanceRejected("complete latest readiness snapshot required")
            if self._snapshot:
                if self._source is source and self._snapshot==r:return r
                raise GovernanceRejected("snapshot conflict")
            self._source=source;self._snapshot=r;self._event("READINESS_CHAIN_ANCHORED",r.digest);return r
    def add_plan(self,plan_id,flow,kind,planner=None,challenger=None):
        with self._lock:
            key=(flow,kind);i=CASE_KEYS.index(key) if key in CASE_KEYS else -1
            if not self._snapshot or i<0 or (i and CASE_KEYS[i-1] not in self._plans):raise GovernanceRejected("anchored ordered case required")
            source=self._source._contracts[key];routed=source.pending_human_judgment;parent=None if i==0 else self._plans[CASE_KEYS[i-1]].digest
            if routed:
                if not _syn(planner,"readiness-planner") or not _syn(challenger,"readiness-challenger"):raise GovernanceRejected("independent readiness actors required")
                actors=self._prior_actors()+tuple(y for x in self._plans.values() for y in (x.planner,x.challenger) if y)+(planner,challenger)
                if len({_id(x) for x in actors})!=len(actors):raise GovernanceRejected("actor collision")
                terms=readiness_terms(source,flow,kind,self._snapshot.digest)
            else:
                if planner is not None or challenger is not None:raise GovernanceRejected("N/A forbids actors")
                terms=(None,)*10+((),)
            vals=(plan_id,flow,kind,source.digest,*terms,planner,challenger,parent,i+1,"PLANNED_NOT_MATERIALIZED_NOT_EXECUTED",True,routed,False,False);r=Plan(*vals,canonical_digest(("READINESS_PLAN",vals)))
            if not self._plan_valid(r,key):raise GovernanceRejected("valid non-executed readiness plan required")
            if key in self._plans:
                if self._plans[key]==r:return r
                raise GovernanceRejected("plan conflict")
            if any(x.plan_id==plan_id for x in self._plans.values()):raise GovernanceRejected("duplicate plan id")
            self._plans[key]=r;self._event("READINESS_PLAN_RECORDED",r.digest)
            if routed:self._hold("MATERIALIZATION_AND_EXECUTION_APPROVAL_PENDING",r.digest)
            return r
    def finalize(self,docket_id,compiler,validator):
        with self._lock:
            if self._docket or tuple(self._plans)!=CASE_KEYS or not self._integrity():raise GovernanceRejected("complete intact readiness batch required")
            actors=self._prior_actors()+tuple(y for x in self._plans.values() for y in (x.planner,x.challenger) if y)+(compiler,validator)
            if not _syn(compiler,"readiness-docket-compiler") or not _syn(validator,"readiness-docket-validator") or len({_id(x) for x in actors})!=len(actors):raise GovernanceRejected("independent final actors required")
            p=dict(docket_id=docket_id,snapshot_digest=self._snapshot.digest,plan_set_digest=canonical_digest(tuple(self._plans[k].digest for k in CASE_KEYS)),compiler=compiler,validator=validator,role_lineage_digest=canonical_digest(("COMPLETE_READINESS_ROLE_LINEAGE",self._source._docket.role_lineage_digest,actors)),complete=True,held=True,pending_human_judgment=True,materialized=False,executed=False,passed=False,failed=False,approved=False,activated=False,deployed=False,status="READINESS_DOCKET_ON_HOLD");self._docket=Docket(**p,digest=canonical_digest(p));self._event("READINESS_DOCKET_HELD",self._docket.digest);return self._docket
    def _control_valid(self,r):
        p={k:v for k,v in r.__dict__.items() if k!="digest"};return isinstance(r.control_id,int) and not isinstance(r.control_id,bool) and 13901<=r.control_id<=14300 and self._expected(r.control_id)==(r.workstream,r.aspect) and r.requirement_ref==f"synthetic:readiness-requirement:{(r.control_id-13901)//25:02}" and _hex(r.fixture_digest) and r.expected_result==("EXPECTED_REJECTION" if r.aspect in NEGATIVE else "PASS") and r.digest==canonical_digest(p)
    def _registry_valid(self):return set(self._controls)==set(range(13901,14301)) and all(self._control_valid(x) for x in self._controls.values())
    def _prior_actors(self):
        s=self._source;return s._prior_actors()+tuple(y for x in s._contracts.values() for y in (x.author,x.verifier) if y)+(s._docket.compiler,s._docket.validator)
    def _snapshot_valid(self):
        if not self._snapshot or not self._source:return False
        s=self._snapshot;p={k:v for k,v in s.__dict__.items() if k!="digest"};e=self._source.evidence();return e["integrity_valid"] and e["complete_observation_contract_gate_evidence"] and s.snapshot_id=="synthetic:lesson-snapshot:13901-14300" and s.stage_range==(13901,14300) and s.mapping_digest==mapping_digest(STAGE_MAPPING) and all(_hex(x) for x in (s.registry_digest,s.manifest_digest)) and s.lesson_ids==APPLIED_LESSONS and s.rule_ids==APPLIED_RULES and s.source_docket_digest==self._source._docket.digest and s.previous_snapshot_digest==self._source._snapshot.digest and s.latest is True and isinstance(s.sequence,int) and not isinstance(s.sequence,bool) and s.sequence>0 and s.digest==canonical_digest(p)
    def _plan_valid(self,r,key):
        i=CASE_KEYS.index(key);source=self._source._contracts[key];routed=source.pending_human_judgment;parent=None if i==0 else self._plans.get(CASE_KEYS[i-1]);parent=None if parent is None else parent.digest;terms=readiness_terms(source,*key,self._snapshot.digest) if routed else (None,)*10+((),);actors=(_syn(r.planner,"readiness-planner") and _syn(r.challenger,"readiness-challenger")) if routed else r.planner is None and r.challenger is None;vals=(r.plan_id,r.flow,r.kind,source.digest,*terms,r.planner,r.challenger,parent,i+1,"PLANNED_NOT_MATERIALIZED_NOT_EXECUTED",True,routed,False,False)
        ids=[x.plan_id for k,x in self._plans.items() if k!=key]
        return _syn(r.plan_id,"readiness-plan") and r.plan_id not in ids and (r.flow,r.kind)==key and r.source_contract_digest==source.digest and tuple(getattr(r,x) for x in ("manifest_identity","resource_budget","privacy_classification","data_classification","determinism","isolation","timeout_policy","side_effect_policy","receipt_schema","approval_gate","recovery_paths"))==terms and actors and r.parent_digest==parent and r.position==i+1 and r.status==vals[-5] and r.held is True and r.pending_human_judgment is routed and not r.materialized and not r.executed and r.digest==canonical_digest(("READINESS_PLAN",vals))
    def _event(self,action,artifact):prev=self._events[-1]["digest"] if self._events else None;p=dict(sequence=len(self._events)+1,action=action,artifact_digest=artifact,previous_digest=prev);self._events.append({**p,"digest":canonical_digest(p)})
    def _hold(self,reason,artifact):prev=self._holds[-1]["digest"] if self._holds else None;p=dict(sequence=len(self._holds)+1,reason=reason,attachment_digest=artifact,previous_digest=prev);self._holds.append({**p,"digest":canonical_digest(p)})
    @staticmethod
    def _chain(rows,hold=False):
        prev=None
        for i,r in enumerate(rows,1):
            keys=("sequence","reason","attachment_digest","previous_digest") if hold else ("sequence","action","artifact_digest","previous_digest");p={k:r.get(k) for k in keys}
            if r!={**p,"digest":canonical_digest(p)} or r["sequence"]!=i or r["previous_digest"]!=prev:return False
            prev=r["digest"]
        return True
    def _integrity(self):
        if not self._registry_valid() or not self._snapshot_valid() or not self._chain(self._events) or not self._chain(self._holds,True) or any(not self._plan_valid(v,k) for k,v in self._plans.items()):return False
        events=[("READINESS_CHAIN_ANCHORED",self._snapshot.digest)]+[("READINESS_PLAN_RECORDED",x.digest) for x in self._plans.values()];holds=[("MATERIALIZATION_AND_EXECUTION_APPROVAL_PENDING",x.digest) for x in self._plans.values() if x.pending_human_judgment]
        if self._docket:events.append(("READINESS_DOCKET_HELD",self._docket.digest))
        if [(x["action"],x["artifact_digest"]) for x in self._events]!=events or [(x["reason"],x["attachment_digest"]) for x in self._holds]!=holds:return False
        if not self._docket:return True
        r=self._docket;p={k:v for k,v in r.__dict__.items() if k!="digest"};actors=self._prior_actors()+tuple(y for x in self._plans.values() for y in (x.planner,x.challenger) if y)+(r.compiler,r.validator);return _syn(r.docket_id,"readiness-docket") and _syn(r.compiler,"readiness-docket-compiler") and _syn(r.validator,"readiness-docket-validator") and r.snapshot_digest==self._snapshot.digest and r.plan_set_digest==canonical_digest(tuple(self._plans[k].digest for k in CASE_KEYS)) and r.role_lineage_digest==canonical_digest(("COMPLETE_READINESS_ROLE_LINEAGE",self._source._docket.role_lineage_digest,actors)) and len({_id(x) for x in actors})==len(actors) and (r.complete,r.held,r.pending_human_judgment)==(True,True,True) and not any((r.materialized,r.executed,r.passed,r.failed,r.approved,r.activated,r.deployed)) and r.status=="READINESS_DOCKET_ON_HOLD" and r.digest==canonical_digest(p)
    def evidence(self):
        ok=self._integrity();complete=ok and self._docket is not None and len(self._plans)==20 and len(self._holds)==16;zero={k:0 for k in ("fixture_materializations","probe_executions","observation_values","external_calls","document_transmissions","external_pg_calls","card_network_calls","payment_approvals","cancellations","refunds","settlements","transfers","ledger_writes","credential_reads","deployments")};return {"range":[13901,14300],"control_count":400,"registered_control_count":len(self._controls),"plan_count":len(self._plans),"bound_manifest_count":sum(x.manifest_identity is not None for x in self._plans.values()),"recovery_path_count":sum(len(x.recovery_paths) for x in self._plans.values()),"human_judgment_hold_count":len(self._holds),"snapshot_digest":self._snapshot.digest if self._snapshot else None,"plan_set_digest":self._docket.plan_set_digest if complete else None,"final_docket_digest":self._docket.digest if complete else None,"complete_role_lineage_digest":self._docket.role_lineage_digest if complete else None,"integrity_valid":ok,"complete_observation_readiness_manifest_evidence":complete,"maximum_state":"READINESS_DOCKET_ON_HOLD" if self._docket else "READINESS_INCOMPLETE","applied_lesson_ids":list(APPLIED_LESSONS),"applied_rule_ids":list(APPLIED_RULES),"judgment_authority":False,"materialized":False,"executed":False,"passed":False,"failed":False,"approved":False,"activated":False,**zero}
