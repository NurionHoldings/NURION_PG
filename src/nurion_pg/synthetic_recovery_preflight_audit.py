"""Automatic snapshot-chain and unresolved-cause diagnostic preflight #13101-#13500."""
from dataclasses import dataclass
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest
from .synthetic_versioned_lesson_recovery_guidance import (
    APPLIED_LESSONS as PRIOR_LESSONS, APPLIED_RULES, CASE_KEYS,
    SyntheticVersionedLessonRecoveryGuidance,
)

APPLIED_LESSONS=tuple(sorted(PRIOR_LESSONS+("ARL-13101-001",)))
WORKSTREAM_NAMES=("SOURCE_GUIDANCE_ANCHOR","AUTOMATIC_STAGE_MAPPING","RANGE_GAP_DETECTION","RANGE_OVERLAP_DETECTION","LESSON_CHAIN_MONOTONICITY","PREDECESSOR_CHAIN_RECONSTRUCTION","CAUSE_CLASSIFICATION","CAUSE_SOURCE_BINDING","OPTION_STRATEGY_DIFFERENTIATION","OPTION_PREFLIGHT_CONTRACT","ASSUMPTION_FALSIFIER_STOP","VALIDATION_AND_RESIDUAL_RISK","COST_RISK_REVERSIBILITY","ESCALATION_ROLLBACK_RESUME","APPEND_ONLY_HOLD_LINEAGE","NON_AUTHORITY_NON_EXECUTION")
WORKSTREAMS=tuple((13101+i*25,13125+i*25,n) for i,n in enumerate(WORKSTREAM_NAMES))
CONTROL_ASPECTS=("input_schema","required_fields","semantic_label","source_type","tenant_scope","role_scope","state_precondition","latest_sequence","source_binding","digest_recalculation","negative_path","missing_input","duplicate_input","replay","conflict","stale_version","concurrency","partial_batch","ordering","append_only","hold_propagation","review_independence","receipt_lineage","operator_gate","non_execution")
NEGATIVE=frozenset({"negative_path","missing_input","duplicate_input","replay","conflict","stale_version","partial_batch"})
CAUSES=("SOURCE_SEMANTIC_MISMATCH","LINEAGE_DISCONTINUITY","STAGE_SNAPSHOT_DRIFT","ACTOR_OR_ORDER_CONFLICT")
STAGE_MAPPING=(("ARKAON-LESSONS-12301",(9901,12700)),("ARKAON-LESSONS-12701",(12701,13100)),("ARKAON-LESSONS-13101",(13101,13500)))
def _hex(v):return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _syn(v,k):return isinstance(v,str) and v.startswith(f"synthetic:{k}:")
def _id(v):return v.rsplit(":",1)[-1].casefold()

@dataclass(frozen=True)
class Control:control_id:int;workstream:str;aspect:str;requirement_ref:str;fixture_digest:str;expected_result:str;digest:str
@dataclass(frozen=True)
class Snapshot:snapshot_id:str;stage_range:tuple;mapping_digest:str;registry_digest:str;manifest_digest:str;lesson_ids:tuple;rule_ids:tuple;source_docket_digest:str;previous_snapshot_digest:str;sequence:int;latest:bool;digest:str
@dataclass(frozen=True)
class Audit:audit_id:str;flow:str;kind:str;source_guidance_digest:str;cause_evidence:tuple|None;cause:str|None;auditor:str|None;verifier:str|None;marker:str;parent_digest:str|None;position:int;options:tuple;held:bool;pending_human_judgment:bool;ranked:bool;selected:bool;concluded:bool;recommended:bool;accepted:bool;resolved:bool;digest:str
@dataclass(frozen=True)
class Docket:docket_id:str;snapshot_digest:str;audit_set_digest:str;compiler:str;validator:str;role_lineage_digest:str;complete:bool;held:bool;pending_human_judgment:bool;ranked:bool;selected:bool;concluded:bool;recommended:bool;accepted:bool;resolved:bool;approved:bool;activated:bool;deployed:bool;status:str;digest:str

def mapping_digest(rows):return canonical_digest(("CONTIGUOUS_STAGE_MAPPING",tuple(rows)))
def cause_evidence(guidance,challenge,snapshot_digest):
    probes=tuple((cause,"NOT_RUN") for cause in CAUSES)
    body=("CAUSE_EVIDENCE",guidance.digest,challenge.digest,snapshot_digest,guidance.rejection_reason,probes,"NO_EXTERNAL_OR_MUTATING_PROBE")
    return body+(canonical_digest(body),)
def classified_cause(evidence):
    if not evidence:return None
    probes=evidence[5];passed=[cause for cause,status in probes if status=="PASS"]
    return passed[0] if len(passed)==1 and all(status in ("PASS","FAIL") for _,status in probes) else "CAUSE_UNDETERMINED"
def recovery_options(source,cause):
    strategies=(("MINIMAL_DIAGNOSTIC_BINDING","READ_ONLY_CANONICAL_RECONSTRUCTION","LOW","HIGH"),("INDEPENDENT_CAUSE_REVALIDATION","FRESH_ACTOR_SEPARATE_FIXTURE","MEDIUM","MEDIUM"))
    out=[]
    for name,preflight,cost,reversibility in strategies:
        body=(name,cause,source.digest,("assumption","UNVERIFIED",cause,source.digest),("disconfirming_test",f"FAIL_IF_{cause}_PERSISTS",source.digest),("stop_condition","ANY_PREFLIGHT_FAILURE_OR_SOURCE_DRIFT"),("preflight",preflight,"READ_ONLY","NO_EXTERNAL_EFFECT"),("validation_criteria",f"{cause}_CLEARED","SOURCE_DIGEST_UNCHANGED","INDEPENDENT_VERIFIER_PASS"),("residual_risk","HUMAN_CONTEXT_NOT_MACHINE_PROVABLE"),("cost",cost),("risk",f"{name}_INCOMPLETE"),("reversibility",reversibility),("escalation","HUMAN_REVIEW_AND_HOLD"),("rollback","DISCARD_CANDIDATE_PRESERVE_SOURCE_DOCKET"),("resume","ALL_PREFLIGHT_AND_VALIDATION_PASS_PLUS_HUMAN_GATE"))
        out.append(body+(canonical_digest(("CAUSE_FIT_RECOVERY_OPTION",body)),))
    return tuple(out)

class SyntheticRecoveryPreflightAudit:
    def __init__(self):self._controls={};self._source=None;self._snapshot=None;self._audits={};self._docket=None;self._events=[];self._holds=[];self._lock=RLock()
    def _expected(self,cid):i=cid-13101;return WORKSTREAM_NAMES[i//25],CONTROL_ASPECTS[i%25]
    def add_control(self,cid,workstream,aspect,requirement_ref,fixture_digest,expected_result):
        p=dict(control_id=cid,workstream=workstream,aspect=aspect,requirement_ref=requirement_ref,fixture_digest=fixture_digest,expected_result=expected_result);r=Control(**p,digest=canonical_digest(p))
        with self._lock:
            if not self._control_valid(r):raise GovernanceRejected("valid #13101-#13500 control required")
            old=self._controls.get(cid)
            if old:
                if old==r:return old
                raise GovernanceRejected("control conflict")
            self._controls[cid]=r;return r
    def anchor(self,source,mapping,registry,manifest,lessons,rules,previous_snapshot,sequence,latest):
        if not isinstance(source,SyntheticVersionedLessonRecoveryGuidance):raise GovernanceRejected("prior recovery guidance required")
        e=source.evidence();p=dict(snapshot_id="synthetic:lesson-snapshot:13101-13500",stage_range=(13101,13500),mapping_digest=mapping,registry_digest=registry,manifest_digest=manifest,lesson_ids=tuple(lessons),rule_ids=tuple(rules),source_docket_digest=source._docket.digest if source._docket else None,previous_snapshot_digest=previous_snapshot,sequence=sequence,latest=latest);r=Snapshot(**p,digest=canonical_digest(p))
        with self._lock:
            if not (self._registry_valid() and e["complete_versioned_recovery_guidance_evidence"] and e["integrity_valid"] and e["judgment_authority"] is False and mapping==mapping_digest(STAGE_MAPPING) and _hex(registry) and _hex(manifest) and tuple(lessons)==APPLIED_LESSONS and tuple(rules)==APPLIED_RULES and previous_snapshot==source._snapshot.digest and isinstance(sequence,int) and not isinstance(sequence,bool) and sequence>0 and latest is True):raise GovernanceRejected("complete latest automated stage snapshot required")
            if self._snapshot:
                if self._source is source and self._snapshot==r:return r
                raise GovernanceRejected("snapshot conflict")
            self._source=source;self._snapshot=r;self._event("AUTOMATED_STAGE_CHAIN_ANCHORED",r.digest);return r
    def add_audit(self,audit_id,flow,kind,auditor=None,verifier=None):
        with self._lock:
            key=(flow,kind);i=CASE_KEYS.index(key) if key in CASE_KEYS else -1
            if not self._snapshot or i<0:raise GovernanceRejected("anchored known case required")
            if i and CASE_KEYS[i-1] not in self._audits:raise GovernanceRejected("immediate prior audit required")
            source=self._source._guidance[key];challenge=self._source._source._challenges[key];routed=bool(source.alternatives);parent=None if i==0 else self._audits[CASE_KEYS[i-1]].digest
            if routed:
                if not _syn(auditor,"recovery-preflight-auditor") or not _syn(verifier,"recovery-preflight-verifier"):raise GovernanceRejected("independent preflight actors required")
                actors=self._prior_actors()+tuple(y for x in self._audits.values() for y in (x.auditor,x.verifier) if y)+(auditor,verifier)
                if len({_id(x) for x in actors})!=len(actors):raise GovernanceRejected("actor collision")
                evidence=cause_evidence(source,challenge,self._snapshot.digest);cause=classified_cause(evidence);marker="CAUSE_UNDETERMINED_DIAGNOSTIC_PREFLIGHT_PENDING_HUMAN_JUDGMENT";options=recovery_options(source,cause)
            else:
                if auditor is not None or verifier is not None:raise GovernanceRejected("N/A forbids actors")
                evidence=None;cause=None;marker="NO_RECOVERY_PREFLIGHT_REQUIRED";options=()
            values=(audit_id,flow,kind,source.digest,evidence,cause,auditor,verifier,marker,parent,i+1,options,True,routed,False,False,False,False,False,False);r=Audit(*values,canonical_digest(("RECOVERY_PREFLIGHT_AUDIT",values)))
            if not self._audit_valid(r,key):raise GovernanceRejected("valid cause-fit audit required")
            old=self._audits.get(key)
            if old:
                if old==r:return old
                raise GovernanceRejected("audit conflict")
            if any(x.audit_id==audit_id for x in self._audits.values()):raise GovernanceRejected("duplicate audit id")
            self._audits[key]=r;self._event("RECOVERY_PREFLIGHT_AUDITED",r.digest)
            if routed:self._hold("HUMAN_RECOVERY_SELECTION_REQUIRED",r.digest)
            return r
    def finalize(self,docket_id,compiler,validator):
        with self._lock:
            if self._docket or tuple(self._audits)!=CASE_KEYS or not self._integrity():raise GovernanceRejected("complete intact audit batch required")
            actors=self._prior_actors()+tuple(y for x in self._audits.values() for y in (x.auditor,x.verifier) if y)+(compiler,validator)
            if not _syn(compiler,"preflight-docket-compiler") or not _syn(validator,"preflight-docket-validator") or len({_id(x) for x in actors})!=len(actors):raise GovernanceRejected("independent final actors required")
            aset=canonical_digest(tuple(self._audits[k].digest for k in CASE_KEYS));lineage=canonical_digest(("COMPLETE_PREFLIGHT_ROLE_LINEAGE",self._source._docket.role_lineage_digest,actors));p=dict(docket_id=docket_id,snapshot_digest=self._snapshot.digest,audit_set_digest=aset,compiler=compiler,validator=validator,role_lineage_digest=lineage,complete=True,held=True,pending_human_judgment=True,ranked=False,selected=False,concluded=False,recommended=False,accepted=False,resolved=False,approved=False,activated=False,deployed=False,status="RECOVERY_PREFLIGHT_DOCKET_ON_HOLD");self._docket=Docket(**p,digest=canonical_digest(p));self._event("RECOVERY_PREFLIGHT_DOCKET_HELD",self._docket.digest);return self._docket
    def _control_valid(self,r):
        p={k:v for k,v in r.__dict__.items() if k!="digest"};return isinstance(r.control_id,int) and not isinstance(r.control_id,bool) and 13101<=r.control_id<=13500 and self._expected(r.control_id)==(r.workstream,r.aspect) and r.requirement_ref==f"synthetic:recovery-preflight-requirement:{(r.control_id-13101)//25:02}" and _hex(r.fixture_digest) and r.expected_result==("EXPECTED_REJECTION" if r.aspect in NEGATIVE else "PASS") and r.digest==canonical_digest(p)
    def _registry_valid(self):return set(self._controls)==set(range(13101,13501)) and all(self._control_valid(x) for x in self._controls.values())
    def _prior_actors(self):
        s=self._source;return s._prior_actors()+tuple(y for x in s._guidance.values() for y in (x.reviewer,x.verifier) if y)+(s._docket.compiler,s._docket.validator)
    def _snapshot_valid(self):
        if not self._snapshot or not self._source:return False
        s=self._snapshot;p={k:v for k,v in s.__dict__.items() if k!="digest"};e=self._source.evidence();return e["integrity_valid"] and e["complete_versioned_recovery_guidance_evidence"] and s.snapshot_id=="synthetic:lesson-snapshot:13101-13500" and s.stage_range==(13101,13500) and s.mapping_digest==mapping_digest(STAGE_MAPPING) and all(_hex(x) for x in (s.registry_digest,s.manifest_digest)) and s.lesson_ids==APPLIED_LESSONS and s.rule_ids==APPLIED_RULES and s.source_docket_digest==self._source._docket.digest and s.previous_snapshot_digest==self._source._snapshot.digest and s.latest is True and isinstance(s.sequence,int) and not isinstance(s.sequence,bool) and s.sequence>0 and s.digest==canonical_digest(p)
    def _audit_valid(self,r,key):
        i=CASE_KEYS.index(key);source=self._source._guidance[key];challenge=self._source._source._challenges[key];routed=bool(source.alternatives);parent=None if i==0 else self._audits.get(CASE_KEYS[i-1]);parent=None if parent is None else parent.digest;evidence=cause_evidence(source,challenge,self._snapshot.digest) if routed else None;cause=classified_cause(evidence) if routed else None;options=recovery_options(source,cause) if routed else ();marker="CAUSE_UNDETERMINED_DIAGNOSTIC_PREFLIGHT_PENDING_HUMAN_JUDGMENT" if routed else "NO_RECOVERY_PREFLIGHT_REQUIRED";state=(_syn(r.auditor,"recovery-preflight-auditor") and _syn(r.verifier,"recovery-preflight-verifier")) if routed else (r.auditor is None and r.verifier is None);values=(r.audit_id,r.flow,r.kind,source.digest,evidence,cause,r.auditor,r.verifier,marker,parent,i+1,options,True,routed,False,False,False,False,False,False);ids=[x.audit_id for k,x in self._audits.items() if k!=key];return _syn(r.audit_id,"recovery-preflight-audit") and r.audit_id not in ids and (r.flow,r.kind)==key and state and r.source_guidance_digest==source.digest and r.cause_evidence==evidence and r.cause==cause and r.marker==marker and r.parent_digest==parent and r.position==i+1 and r.options==options and len(options) in (0,2) and (not options or options[0][0]!=options[1][0] and options[0][6]!=options[1][6]) and r.held is True and r.pending_human_judgment is routed and not any((r.ranked,r.selected,r.concluded,r.recommended,r.accepted,r.resolved)) and r.digest==canonical_digest(("RECOVERY_PREFLIGHT_AUDIT",values))
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
        if not self._registry_valid() or not self._snapshot_valid() or not self._chain(self._events) or not self._chain(self._holds,True) or any(not self._audit_valid(v,k) for k,v in self._audits.items()):return False
        events=[("AUTOMATED_STAGE_CHAIN_ANCHORED",self._snapshot.digest)]+[("RECOVERY_PREFLIGHT_AUDITED",x.digest) for x in self._audits.values()];holds=[("HUMAN_RECOVERY_SELECTION_REQUIRED",x.digest) for x in self._audits.values() if x.pending_human_judgment]
        if self._docket:events.append(("RECOVERY_PREFLIGHT_DOCKET_HELD",self._docket.digest))
        if [(x["action"],x["artifact_digest"]) for x in self._events]!=events or [(x["reason"],x["attachment_digest"]) for x in self._holds]!=holds:return False
        if not self._docket:return True
        r=self._docket;p={k:v for k,v in r.__dict__.items() if k!="digest"};actors=self._prior_actors()+tuple(y for x in self._audits.values() for y in (x.auditor,x.verifier) if y)+(r.compiler,r.validator);lineage=canonical_digest(("COMPLETE_PREFLIGHT_ROLE_LINEAGE",self._source._docket.role_lineage_digest,actors));return _syn(r.docket_id,"preflight-docket") and _syn(r.compiler,"preflight-docket-compiler") and _syn(r.validator,"preflight-docket-validator") and r.snapshot_digest==self._snapshot.digest and r.audit_set_digest==canonical_digest(tuple(self._audits[k].digest for k in CASE_KEYS)) and r.role_lineage_digest==lineage and len({_id(x) for x in actors})==len(actors) and r.complete is r.held is r.pending_human_judgment is True and r.status=="RECOVERY_PREFLIGHT_DOCKET_ON_HOLD" and not any((r.ranked,r.selected,r.concluded,r.recommended,r.accepted,r.resolved,r.approved,r.activated,r.deployed)) and r.digest==canonical_digest(p)
    def evidence(self):
        ok=self._integrity();complete=ok and self._docket is not None and len(self._audits)==20 and len(self._holds)==16;zero={k:0 for k in ("external_calls","document_transmissions","external_pg_calls","card_network_calls","payment_approvals","cancellations","refunds","settlements","transfers","ledger_writes","credential_reads","deployments")};return {"range":[13101,13500],"control_count":400,"registered_control_count":len(self._controls),"audit_count":len(self._audits),"diagnostic_option_count":sum(len(x.options) for x in self._audits.values()),"undetermined_cause_count":sum(x.cause=="CAUSE_UNDETERMINED" for x in self._audits.values()),"no_preflight_marker_count":sum(not x.options for x in self._audits.values()),"human_judgment_hold_count":len(self._holds),"snapshot_digest":self._snapshot.digest if self._snapshot else None,"mapping_digest":self._snapshot.mapping_digest if self._snapshot else None,"audit_set_digest":self._docket.audit_set_digest if complete else None,"final_docket_digest":self._docket.digest if complete else None,"complete_role_lineage_digest":self._docket.role_lineage_digest if complete else None,"integrity_valid":ok,"complete_recovery_preflight_audit_evidence":complete,"maximum_state":"RECOVERY_PREFLIGHT_DOCKET_ON_HOLD" if self._docket else "AUDIT_INCOMPLETE","applied_lesson_ids":list(APPLIED_LESSONS),"applied_rule_ids":list(APPLIED_RULES),"judgment_authority":False,"ranked":False,"selected":False,"concluded":False,"recommended":False,"accepted":False,"resolved":False,"approved":False,"activated":False,**zero}
