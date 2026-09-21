"""Content-free synthetic observation contract and independent gate #13501-#13900."""
from dataclasses import dataclass
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest
from .synthetic_recovery_preflight_audit import (
    APPLIED_LESSONS as PRIOR_LESSONS, APPLIED_RULES, CASE_KEYS,
    SyntheticRecoveryPreflightAudit,
)

APPLIED_LESSONS=tuple(sorted(PRIOR_LESSONS+("ARL-13501-001",)))
WORKSTREAM_NAMES=("SOURCE_PREFLIGHT_ANCHOR","STAGE_SNAPSHOT_CHAIN","OBSERVATION_SCHEMA","FIXTURE_IDENTITY","INPUT_IDENTITY","EXPECTED_OUTCOME","OUTCOME_VOCABULARY","EVIDENCE_COMPLETENESS","INDEPENDENT_VERIFIER_GATE","AMBIGUOUS_RESULT_POLICY","CONTRADICTORY_RESULT_POLICY","RECOVERY_PATHS","STOP_RESUME_ROLLBACK","APPEND_ONLY_HOLD_LINEAGE","FULL_REHASH_RESISTANCE","NON_AUTHORITY_NON_EXECUTION")
WORKSTREAMS=tuple((13501+i*25,13525+i*25,n) for i,n in enumerate(WORKSTREAM_NAMES))
CONTROL_ASPECTS=("input_schema","required_fields","semantic_label","source_type","tenant_scope","role_scope","state_precondition","latest_sequence","source_binding","digest_recalculation","negative_path","missing_input","duplicate_input","replay","conflict","stale_version","concurrency","partial_batch","ordering","append_only","hold_propagation","review_independence","receipt_lineage","operator_gate","non_execution")
NEGATIVE=frozenset({"negative_path","missing_input","duplicate_input","replay","conflict","stale_version","partial_batch"})
STAGE_MAPPING=(("ARKAON-LESSONS-12301",(9901,12700)),("ARKAON-LESSONS-12701",(12701,13100)),("ARKAON-LESSONS-13101",(13101,13500)),("ARKAON-LESSONS-13501",(13501,13900)))
def _hex(v):return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _syn(v,k):return isinstance(v,str) and v.startswith(f"synthetic:{k}:")
def _id(v):return v.rsplit(":",1)[-1].casefold()
def mapping_digest(rows):return canonical_digest(("CONTIGUOUS_STAGE_MAPPING",tuple(rows)))

@dataclass(frozen=True)
class Control:control_id:int;workstream:str;aspect:str;requirement_ref:str;fixture_digest:str;expected_result:str;digest:str
@dataclass(frozen=True)
class Snapshot:snapshot_id:str;stage_range:tuple;mapping_digest:str;registry_digest:str;manifest_digest:str;lesson_ids:tuple;rule_ids:tuple;source_docket_digest:str;previous_snapshot_digest:str;sequence:int;latest:bool;digest:str
@dataclass(frozen=True)
class Contract:contract_id:str;flow:str;kind:str;source_audit_digest:str;fixture_identity:tuple|None;input_identity:tuple|None;expected_outcome:tuple|None;observation_status:str;observed_outcome:str|None;evidence_completeness:bool;verifier_gate:str;ambiguous_policy:tuple|None;contradictory_policy:tuple|None;recovery_paths:tuple;author:str|None;verifier:str|None;parent_digest:str|None;position:int;held:bool;pending_human_judgment:bool;passed:bool;failed:bool;digest:str
@dataclass(frozen=True)
class Docket:docket_id:str;snapshot_digest:str;contract_set_digest:str;compiler:str;validator:str;role_lineage_digest:str;complete:bool;held:bool;pending_human_judgment:bool;passed:bool;failed:bool;ranked:bool;selected:bool;concluded:bool;recommended:bool;accepted:bool;resolved:bool;approved:bool;activated:bool;deployed:bool;status:str;digest:str

def observation_terms(source,flow,kind,snapshot_digest):
    fixture=("fixture_identity",f"synthetic:content-free-fixture:{flow}:{kind}",canonical_digest(("FIXTURE_IDENTITY",source.digest,flow,kind,snapshot_digest)),"NO_BYTES_NO_FILE_NO_EXTERNAL_SOURCE")
    inputs=("input_identity",source.digest,snapshot_digest,canonical_digest(("INPUT_SET",source.digest,fixture[2])),"IDENTITY_ONLY_NO_VALUE")
    expected=("expected_outcome","EXACTLY_ONE_OF_PASS_FAIL",("PASS_REQUIRES","FIXTURE_IDENTITY_MATCH","INPUT_IDENTITY_MATCH","ALL_REQUIRED_EVIDENCE_PRESENT","INDEPENDENT_VERIFIER_PASS"),("FAIL_REQUIRES","SOURCE_BOUND_ASSERTION_MISMATCH","COMPLETE_EVIDENCE","INDEPENDENT_VERIFIER_CONFIRMATION"),"NOT_EVALUATED")
    ambiguous=("ambiguous_result","HOLD","NO_PASS_FAIL_CLAIM","FRESH_INDEPENDENT_REOBSERVATION_REQUIRED")
    contradictory=("contradictory_result","HOLD","PRESERVE_BOTH_RECEIPTS","SEPARATE_FIXTURE_AND_VERIFIER_RECONCILIATION_REQUIRED")
    paths=(("MINIMAL_CONTRACT_REPAIR","fix_missing_identity_or_evidence","LOW","LOW","HIGH","STOP_ON_SOURCE_DRIFT","validate_complete_contract_then_new_verifier","discard_candidate_preserve_source","resume_after_complete_plus_human_gate"),("INDEPENDENT_SYNTHETIC_REOBSERVATION_PLAN","fresh_content_free_fixture_and_actor","MEDIUM","MEDIUM","HIGH","STOP_ON_AMBIGUITY_OR_CONTRADICTION","two_receipt_reconciliation","quarantine_conflicting_receipts","resume_after_reconciliation_plus_human_gate"))
    return fixture,inputs,expected,ambiguous,contradictory,paths

class SyntheticObservationContractGate:
    def __init__(self):self._controls={};self._source=None;self._snapshot=None;self._contracts={};self._docket=None;self._events=[];self._holds=[];self._lock=RLock()
    def _expected(self,cid):i=cid-13501;return WORKSTREAM_NAMES[i//25],CONTROL_ASPECTS[i%25]
    def add_control(self,cid,workstream,aspect,requirement_ref,fixture_digest,expected_result):
        p=dict(control_id=cid,workstream=workstream,aspect=aspect,requirement_ref=requirement_ref,fixture_digest=fixture_digest,expected_result=expected_result);r=Control(**p,digest=canonical_digest(p))
        with self._lock:
            if not self._control_valid(r):raise GovernanceRejected("valid #13501-#13900 control required")
            old=self._controls.get(cid)
            if old:
                if old==r:return old
                raise GovernanceRejected("control conflict")
            self._controls[cid]=r;return r
    def anchor(self,source,mapping,registry,manifest,lessons,rules,previous_snapshot,sequence,latest):
        if not isinstance(source,SyntheticRecoveryPreflightAudit):raise GovernanceRejected("prior preflight audit required")
        e=source.evidence();p=dict(snapshot_id="synthetic:lesson-snapshot:13501-13900",stage_range=(13501,13900),mapping_digest=mapping,registry_digest=registry,manifest_digest=manifest,lesson_ids=tuple(lessons),rule_ids=tuple(rules),source_docket_digest=source._docket.digest if source._docket else None,previous_snapshot_digest=previous_snapshot,sequence=sequence,latest=latest);r=Snapshot(**p,digest=canonical_digest(p))
        with self._lock:
            if not (self._registry_valid() and e["complete_recovery_preflight_audit_evidence"] and e["integrity_valid"] and e["judgment_authority"] is False and mapping==mapping_digest(STAGE_MAPPING) and _hex(registry) and _hex(manifest) and tuple(lessons)==APPLIED_LESSONS and tuple(rules)==APPLIED_RULES and previous_snapshot==source._snapshot.digest and isinstance(sequence,int) and not isinstance(sequence,bool) and sequence>0 and latest is True):raise GovernanceRejected("complete latest observation snapshot required")
            if self._snapshot:
                if self._source is source and self._snapshot==r:return r
                raise GovernanceRejected("snapshot conflict")
            self._source=source;self._snapshot=r;self._event("OBSERVATION_CONTRACT_CHAIN_ANCHORED",r.digest);return r
    def add_contract(self,contract_id,flow,kind,author=None,verifier=None):
        with self._lock:
            key=(flow,kind);i=CASE_KEYS.index(key) if key in CASE_KEYS else -1
            if not self._snapshot or i<0:raise GovernanceRejected("anchored known case required")
            if i and CASE_KEYS[i-1] not in self._contracts:raise GovernanceRejected("immediate prior contract required")
            source=self._source._audits[key];routed=source.pending_human_judgment;parent=None if i==0 else self._contracts[CASE_KEYS[i-1]].digest
            if routed:
                if not _syn(author,"observation-contract-author") or not _syn(verifier,"observation-contract-verifier"):raise GovernanceRejected("independent contract actors required")
                actors=self._prior_actors()+tuple(y for x in self._contracts.values() for y in (x.author,x.verifier) if y)+(author,verifier)
                if len({_id(x) for x in actors})!=len(actors):raise GovernanceRejected("actor collision")
                fixture,inputs,expected,ambiguous,contradictory,paths=observation_terms(source,flow,kind,self._snapshot.digest)
            else:
                if author is not None or verifier is not None:raise GovernanceRejected("N/A forbids actors")
                fixture=inputs=expected=ambiguous=contradictory=None;paths=()
            values=(contract_id,flow,kind,source.digest,fixture,inputs,expected,"NOT_RUN",None,False,"PENDING_NOT_EXECUTED",ambiguous,contradictory,paths,author,verifier,parent,i+1,True,routed,False,False);r=Contract(*values,canonical_digest(("OBSERVATION_CONTRACT",values)))
            if not self._contract_valid(r,key):raise GovernanceRejected("valid non-executed observation contract required")
            old=self._contracts.get(key)
            if old:
                if old==r:return old
                raise GovernanceRejected("contract conflict")
            if any(x.contract_id==contract_id for x in self._contracts.values()):raise GovernanceRejected("duplicate contract id")
            self._contracts[key]=r;self._event("OBSERVATION_CONTRACT_RECORDED",r.digest)
            if routed:self._hold("OBSERVATION_NOT_RUN_HUMAN_GATE_REQUIRED",r.digest)
            return r
    def finalize(self,docket_id,compiler,validator):
        with self._lock:
            if self._docket or tuple(self._contracts)!=CASE_KEYS or not self._integrity():raise GovernanceRejected("complete intact contract batch required")
            actors=self._prior_actors()+tuple(y for x in self._contracts.values() for y in (x.author,x.verifier) if y)+(compiler,validator)
            if not _syn(compiler,"observation-docket-compiler") or not _syn(validator,"observation-docket-validator") or len({_id(x) for x in actors})!=len(actors):raise GovernanceRejected("independent final actors required")
            cset=canonical_digest(tuple(self._contracts[k].digest for k in CASE_KEYS));lineage=canonical_digest(("COMPLETE_OBSERVATION_CONTRACT_ROLE_LINEAGE",self._source._docket.role_lineage_digest,actors));p=dict(docket_id=docket_id,snapshot_digest=self._snapshot.digest,contract_set_digest=cset,compiler=compiler,validator=validator,role_lineage_digest=lineage,complete=True,held=True,pending_human_judgment=True,passed=False,failed=False,ranked=False,selected=False,concluded=False,recommended=False,accepted=False,resolved=False,approved=False,activated=False,deployed=False,status="OBSERVATION_CONTRACT_DOCKET_ON_HOLD");self._docket=Docket(**p,digest=canonical_digest(p));self._event("OBSERVATION_CONTRACT_DOCKET_HELD",self._docket.digest);return self._docket
    def _control_valid(self,r):
        p={k:v for k,v in r.__dict__.items() if k!="digest"};return isinstance(r.control_id,int) and not isinstance(r.control_id,bool) and 13501<=r.control_id<=13900 and self._expected(r.control_id)==(r.workstream,r.aspect) and r.requirement_ref==f"synthetic:observation-contract-requirement:{(r.control_id-13501)//25:02}" and _hex(r.fixture_digest) and r.expected_result==("EXPECTED_REJECTION" if r.aspect in NEGATIVE else "PASS") and r.digest==canonical_digest(p)
    def _registry_valid(self):return set(self._controls)==set(range(13501,13901)) and all(self._control_valid(x) for x in self._controls.values())
    def _prior_actors(self):
        s=self._source;return s._prior_actors()+tuple(y for x in s._audits.values() for y in (x.auditor,x.verifier) if y)+(s._docket.compiler,s._docket.validator)
    def _snapshot_valid(self):
        if not self._snapshot or not self._source:return False
        s=self._snapshot;p={k:v for k,v in s.__dict__.items() if k!="digest"};e=self._source.evidence();return e["integrity_valid"] and e["complete_recovery_preflight_audit_evidence"] and s.snapshot_id=="synthetic:lesson-snapshot:13501-13900" and s.stage_range==(13501,13900) and s.mapping_digest==mapping_digest(STAGE_MAPPING) and all(_hex(x) for x in (s.registry_digest,s.manifest_digest)) and s.lesson_ids==APPLIED_LESSONS and s.rule_ids==APPLIED_RULES and s.source_docket_digest==self._source._docket.digest and s.previous_snapshot_digest==self._source._snapshot.digest and s.latest is True and isinstance(s.sequence,int) and not isinstance(s.sequence,bool) and s.sequence>0 and s.digest==canonical_digest(p)
    def _contract_valid(self,r,key):
        i=CASE_KEYS.index(key);source=self._source._audits[key];routed=source.pending_human_judgment;parent=None if i==0 else self._contracts.get(CASE_KEYS[i-1]);parent=None if parent is None else parent.digest
        if routed:fixture,inputs,expected,ambiguous,contradictory,paths=observation_terms(source,*key,self._snapshot.digest);state=_syn(r.author,"observation-contract-author") and _syn(r.verifier,"observation-contract-verifier")
        else:fixture=inputs=expected=ambiguous=contradictory=None;paths=();state=r.author is None and r.verifier is None
        values=(r.contract_id,r.flow,r.kind,source.digest,fixture,inputs,expected,"NOT_RUN",None,False,"PENDING_NOT_EXECUTED",ambiguous,contradictory,paths,r.author,r.verifier,parent,i+1,True,routed,False,False);ids=[x.contract_id for k,x in self._contracts.items() if k!=key]
        return _syn(r.contract_id,"observation-contract") and r.contract_id not in ids and (r.flow,r.kind)==key and state and r.source_audit_digest==source.digest and r.fixture_identity==fixture and r.input_identity==inputs and r.expected_outcome==expected and r.observation_status=="NOT_RUN" and r.observed_outcome is None and r.evidence_completeness is False and r.verifier_gate=="PENDING_NOT_EXECUTED" and r.ambiguous_policy==ambiguous and r.contradictory_policy==contradictory and r.recovery_paths==paths and len(paths) in (0,2) and r.parent_digest==parent and r.position==i+1 and r.held is True and r.pending_human_judgment is routed and not r.passed and not r.failed and r.digest==canonical_digest(("OBSERVATION_CONTRACT",values))
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
        if not self._registry_valid() or not self._snapshot_valid() or not self._chain(self._events) or not self._chain(self._holds,True) or any(not self._contract_valid(v,k) for k,v in self._contracts.items()):return False
        events=[("OBSERVATION_CONTRACT_CHAIN_ANCHORED",self._snapshot.digest)]+[("OBSERVATION_CONTRACT_RECORDED",x.digest) for x in self._contracts.values()];holds=[("OBSERVATION_NOT_RUN_HUMAN_GATE_REQUIRED",x.digest) for x in self._contracts.values() if x.pending_human_judgment]
        if self._docket:events.append(("OBSERVATION_CONTRACT_DOCKET_HELD",self._docket.digest))
        if [(x["action"],x["artifact_digest"]) for x in self._events]!=events or [(x["reason"],x["attachment_digest"]) for x in self._holds]!=holds:return False
        if not self._docket:return True
        r=self._docket;p={k:v for k,v in r.__dict__.items() if k!="digest"};actors=self._prior_actors()+tuple(y for x in self._contracts.values() for y in (x.author,x.verifier) if y)+(r.compiler,r.validator);lineage=canonical_digest(("COMPLETE_OBSERVATION_CONTRACT_ROLE_LINEAGE",self._source._docket.role_lineage_digest,actors));return _syn(r.docket_id,"observation-docket") and _syn(r.compiler,"observation-docket-compiler") and _syn(r.validator,"observation-docket-validator") and r.snapshot_digest==self._snapshot.digest and r.contract_set_digest==canonical_digest(tuple(self._contracts[k].digest for k in CASE_KEYS)) and r.role_lineage_digest==lineage and len({_id(x) for x in actors})==len(actors) and r.complete is True and r.held is True and r.pending_human_judgment is True and r.passed is False and r.failed is False and r.ranked is False and r.selected is False and r.concluded is False and r.recommended is False and r.accepted is False and r.resolved is False and r.approved is False and r.activated is False and r.deployed is False and r.status=="OBSERVATION_CONTRACT_DOCKET_ON_HOLD" and r.digest==canonical_digest(p)
    def evidence(self):
        ok=self._integrity();complete=ok and self._docket is not None and len(self._contracts)==20 and len(self._holds)==16;zero={k:0 for k in ("probe_executions","observation_values","external_calls","document_transmissions","external_pg_calls","card_network_calls","payment_approvals","cancellations","refunds","settlements","transfers","ledger_writes","credential_reads","deployments")};return {"range":[13501,13900],"control_count":400,"registered_control_count":len(self._controls),"contract_count":len(self._contracts),"content_free_fixture_count":sum(x.fixture_identity is not None for x in self._contracts.values()),"recovery_path_count":sum(len(x.recovery_paths) for x in self._contracts.values()),"not_run_count":sum(x.observation_status=="NOT_RUN" and x.pending_human_judgment for x in self._contracts.values()),"human_judgment_hold_count":len(self._holds),"snapshot_digest":self._snapshot.digest if self._snapshot else None,"contract_set_digest":self._docket.contract_set_digest if complete else None,"final_docket_digest":self._docket.digest if complete else None,"complete_role_lineage_digest":self._docket.role_lineage_digest if complete else None,"integrity_valid":ok,"complete_observation_contract_gate_evidence":complete,"maximum_state":"OBSERVATION_CONTRACT_DOCKET_ON_HOLD" if self._docket else "CONTRACT_INCOMPLETE","applied_lesson_ids":list(APPLIED_LESSONS),"applied_rule_ids":list(APPLIED_RULES),"judgment_authority":False,"passed":False,"failed":False,"ranked":False,"selected":False,"concluded":False,"recommended":False,"accepted":False,"resolved":False,"approved":False,"activated":False,**zero}
