"""Stage-scoped lesson snapshot and non-binding recovery guidance #12701-#13100."""
from dataclasses import dataclass
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest
from .synthetic_option_methodology_independent_challenge import (
    APPLIED_LESSONS as PRIOR_LESSONS, APPLIED_RULES, CASE_KEYS,
    SyntheticOptionMethodologyIndependentChallenge,
)

APPLIED_LESSONS=tuple(sorted(PRIOR_LESSONS if "ARL-12701-001" in PRIOR_LESSONS else PRIOR_LESSONS+("ARL-12701-001",)))
WORKSTREAM_NAMES=(
    "PRIOR_METHODOLOGY_DOCKET_ANCHOR","STAGE_SCOPED_LESSON_SNAPSHOT",
    "REGISTRY_MANIFEST_CONTENT_BINDING","SNAPSHOT_PREDECESSOR_CHAIN",
    "SOURCE_CHALLENGE_RECONSTRUCTION","REJECTION_REASON_EXPLANATION",
    "SAFE_DEFAULT_CANDIDATE","TWO_RECOVERY_ALTERNATIVES",
    "ASSUMPTION_FALSIFIER_BINDING","STOP_AND_VALIDATION_BINDING",
    "RISK_COST_REVERSIBILITY","ESCALATION_ROLLBACK_RESUME",
    "APPEND_ONLY_GUIDANCE_EVENT","UNRESOLVED_HUMAN_HOLD_CHAIN",
    "PARTIAL_BATCH_LATEST_CONCURRENCY","NON_AUTHORITY_NON_EXECUTION_BOUNDARY",
)
WORKSTREAMS=tuple((12701+i*25,12725+i*25,n) for i,n in enumerate(WORKSTREAM_NAMES))
CONTROL_ASPECTS=("input_schema","required_fields","semantic_label","source_type","tenant_scope","role_scope","state_precondition","latest_sequence","source_binding","digest_recalculation","negative_path","missing_input","duplicate_input","replay","conflict","stale_version","concurrency","partial_batch","ordering","append_only","hold_propagation","review_independence","receipt_lineage","operator_gate","non_execution")
NEGATIVE=frozenset({"negative_path","missing_input","duplicate_input","replay","conflict","stale_version","partial_batch"})
def _syn(v,k):return isinstance(v,str) and v.startswith(f"synthetic:{k}:")
def _hex(v):return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _identity(v):return v.rsplit(":",1)[-1].casefold()

@dataclass(frozen=True)
class Control:control_id:int;workstream:str;aspect:str;requirement_ref:str;fixture_digest:str;expected_result:str;digest:str
@dataclass(frozen=True)
class LessonSnapshot:
    snapshot_id:str;stage_range:tuple;registry_digest:str;manifest_digest:str;lesson_ids:tuple;rule_ids:tuple;source_docket_digest:str;previous_registry_snapshot_digest:str;previous_snapshot_digest:str;sequence:int;latest:bool;digest:str
@dataclass(frozen=True)
class Guidance:
    guidance_id:str;flow:str;answer_kind:str;source_challenge_digest:str;reviewer:str|None;verifier:str|None;marker:str;parent_digest:str|None;position:int;rejection_reason:str|None;safe_candidate:tuple|None;alternatives:tuple;projection_digest:str;held:bool;pending_human_judgment:bool;ranked:bool;selected:bool;concluded:bool;recommended:bool;accepted:bool;resolved:bool;digest:str
@dataclass(frozen=True)
class Docket:
    docket_id:str;snapshot_digest:str;guidance_set_digest:str;compiler:str;validator:str;role_lineage_digest:str;complete:bool;held:bool;pending_human_judgment:bool;ranked:bool;selected:bool;concluded:bool;recommended:bool;accepted:bool;resolved:bool;approved:bool;activated:bool;deployed:bool;status:str;digest:str

def recovery_alternatives(source):
    rows=[]
    for i,(name,*_) in enumerate(source.methodology_cards):
        mode=("MINIMAL_SAFE_BINDING","STAGE_VERSIONED_SNAPSHOT")[i]
        body=(mode,source.digest,name,("assumption","UNVERIFIED",source.digest),("disconfirming_test","RECONSTRUCT_SOURCE_AND_COMPARE_CANONICAL_CARD"),("stop_condition","DIGEST_OR_SEMANTIC_MISMATCH"),("validation_criteria","SOURCE_RECONSTRUCTION_PASS","NEGATIVE_REHASH_REJECTED","HUMAN_OWNER_CONFIRMED"),("residual_risk","UNASSESSED"),("cost","LOW" if i==0 else "MEDIUM"),("risk","LESSON_PROPAGATION_DRIFT" if i==0 else "SNAPSHOT_MIGRATION_COMPLEXITY"),("reversibility","HIGH"),("escalation","HUMAN_REVIEW_AND_HOLD"),("rollback","PRESERVE_PRIOR_DOCKET_NO_EXECUTION"),("resume","ALL_VALIDATION_CRITERIA_PASS_AND_HUMAN_GATE"))
        rows.append(body+(canonical_digest(("RECOVERY_ALTERNATIVE",body)),))
    return tuple(rows)
def projection(source,reviewer,verifier,marker,reason,candidate,alternatives):return canonical_digest(("RECOVERY_GUIDANCE_PROJECTION",source,reviewer,verifier,marker,reason,candidate,alternatives))
def source_stage_snapshot_digest(snapshot_id,stage_range,lesson_ids,rule_ids,registry_snapshot_digest,manifest_digest,source_docket_digest):return canonical_digest(("SOURCE_STAGE_LESSON_SNAPSHOT",snapshot_id,stage_range,lesson_ids,rule_ids,registry_snapshot_digest,manifest_digest,source_docket_digest))

class SyntheticVersionedLessonRecoveryGuidance:
    def __init__(self):self._controls={};self._source=None;self._snapshot=None;self._guidance={};self._docket=None;self._events=[];self._holds=[];self._lock=RLock()
    def _expected(self,cid):i=cid-12701;return WORKSTREAM_NAMES[i//25],CONTROL_ASPECTS[i%25]
    def add_control(self,cid,workstream,aspect,requirement_ref,fixture_digest,expected_result):
        p=dict(control_id=cid,workstream=workstream,aspect=aspect,requirement_ref=requirement_ref,fixture_digest=fixture_digest,expected_result=expected_result);r=Control(**p,digest=canonical_digest(p))
        with self._lock:
            if not self._control_valid(r):raise GovernanceRejected("valid #12701-#13100 control required")
            old=self._controls.get(cid)
            if old:
                if old==r:return old
                raise GovernanceRejected("control conflict")
            self._controls[cid]=r;return r
    def anchor(self,service,registry,manifest,lessons,rules,previous_registry_snapshot,previous_snapshot,sequence,latest):
        if not isinstance(service,SyntheticOptionMethodologyIndependentChallenge):raise GovernanceRejected("prior methodology service required")
        e=service.evidence();d=service._docket
        p=dict(snapshot_id="synthetic:lesson-snapshot:12701-13100",stage_range=(12701,13100),registry_digest=registry,manifest_digest=manifest,lesson_ids=tuple(lessons),rule_ids=tuple(rules),source_docket_digest=d.digest if d else None,previous_registry_snapshot_digest=previous_registry_snapshot,previous_snapshot_digest=previous_snapshot,sequence=sequence,latest=latest);r=LessonSnapshot(**p,digest=canonical_digest(p))
        with self._lock:
            expected_previous=source_stage_snapshot_digest("ARKAON-LESSONS-12301",(9901,12700),PRIOR_LESSONS,tuple(rules),previous_registry_snapshot,manifest,d.digest if d else None)
            if not (self._registry_valid() and e["complete_option_methodology_challenge_evidence"] and e["integrity_valid"] and e["judgment_authority"] is False and d and _hex(registry) and _hex(manifest) and tuple(lessons)==APPLIED_LESSONS and tuple(rules)==APPLIED_RULES and _hex(previous_registry_snapshot) and previous_snapshot==expected_previous and isinstance(sequence,int) and not isinstance(sequence,bool) and sequence>0 and latest is True):raise GovernanceRejected("complete latest stage snapshot required")
            if self._snapshot:
                if self._source is service and self._snapshot==r:return r
                raise GovernanceRejected("snapshot conflict")
            self._source=service;self._snapshot=r;self._event("VERSIONED_LESSON_SNAPSHOT_ANCHORED",r.digest);return r
    def add_guidance(self,guidance_id,flow,kind,reviewer=None,verifier=None):
        with self._lock:
            key=(flow,kind)
            if not self._snapshot or key not in CASE_KEYS:raise GovernanceRejected("anchored snapshot required")
            i=CASE_KEYS.index(key);source=self._source._challenges[key];previous=None if i==0 else self._guidance.get(CASE_KEYS[i-1])
            if i and previous is None:raise GovernanceRejected("immediate prior guidance required")
            if not source.methodology_cards:
                if reviewer is not None or verifier is not None:raise GovernanceRejected("N/A forbids actors")
                marker="NO_RECOVERY_GUIDANCE_REQUIRED";reason=None;candidate=None;alts=()
            else:
                if not _syn(reviewer,"recovery-guidance-reviewer") or not _syn(verifier,"recovery-guidance-verifier"):raise GovernanceRejected("independent guidance actors required")
                occupied=self._prior_actors()+tuple(y for x in self._guidance.values() for y in (x.reviewer,x.verifier) if y)
                if len({_identity(x) for x in occupied+(reviewer,verifier)})!=len(occupied)+2:raise GovernanceRejected("actor collision")
                marker="NONBINDING_RECOVERY_GUIDANCE_PENDING_HUMAN_JUDGMENT";reason="FAIL_CLOSED_SEMANTIC_OR_LINEAGE_MISMATCH";alts=recovery_alternatives(source);candidate=("safe_default_candidate","MINIMAL_SAFE_BINDING","NONBINDING","HUMAN_DETERMINATION_REQUIRED")
            parent=None if previous is None else previous.digest;proj=projection(source.digest,reviewer,verifier,marker,reason,candidate,alts);values=(guidance_id,flow,kind,source.digest,reviewer,verifier,marker,parent,i+1,reason,candidate,alts,proj,True,bool(alts),False,False,False,False,False,False);r=Guidance(*values,canonical_digest(("VERSIONED_LESSON_RECOVERY_GUIDANCE",values)))
            if not self._guidance_valid(r,key):raise GovernanceRejected("valid recovery guidance required")
            old=self._guidance.get(key)
            if old:
                if old==r:return old
                raise GovernanceRejected("guidance conflict")
            self._guidance[key]=r;self._event("RECOVERY_GUIDANCE_RECORDED",r.digest)
            if r.pending_human_judgment:self._hold("HUMAN_RECOVERY_PATH_JUDGMENT_REQUIRED",r.digest)
            return r
    def finalize(self,docket_id,compiler,validator):
        with self._lock:
            if self._docket or tuple(self._guidance)!=CASE_KEYS or not self._integrity():raise GovernanceRejected("complete intact batch required")
            actors=self._prior_actors()+tuple(y for x in self._guidance.values() for y in (x.reviewer,x.verifier) if y)+(compiler,validator)
            if not _syn(compiler,"recovery-docket-compiler") or not _syn(validator,"recovery-docket-validator") or len({_identity(x) for x in actors})!=len(actors):raise GovernanceRejected("independent final actors required")
            gset=canonical_digest(tuple(self._guidance[k].digest for k in CASE_KEYS));lineage=canonical_digest(("COMPLETE_RECOVERY_GUIDANCE_ROLE_LINEAGE",self._source._docket.role_lineage_digest,actors));p=dict(docket_id=docket_id,snapshot_digest=self._snapshot.digest,guidance_set_digest=gset,compiler=compiler,validator=validator,role_lineage_digest=lineage,complete=True,held=True,pending_human_judgment=True,ranked=False,selected=False,concluded=False,recommended=False,accepted=False,resolved=False,approved=False,activated=False,deployed=False,status="RECOVERY_GUIDANCE_DOCKET_ON_HOLD");self._docket=Docket(**p,digest=canonical_digest(p));self._event("RECOVERY_GUIDANCE_DOCKET_HELD",self._docket.digest);return self._docket
    def _control_valid(self,r):
        p={k:v for k,v in r.__dict__.items() if k!="digest"};return isinstance(r.control_id,int) and not isinstance(r.control_id,bool) and 12701<=r.control_id<=13100 and self._expected(r.control_id)==(r.workstream,r.aspect) and r.requirement_ref==f"synthetic:recovery-guidance-requirement:{(r.control_id-12701)//25:02}" and _hex(r.fixture_digest) and r.expected_result==("EXPECTED_REJECTION" if r.aspect in NEGATIVE else "PASS") and r.digest==canonical_digest(p)
    def _registry_valid(self):return set(self._controls)==set(range(12701,13101)) and all(self._control_valid(x) for x in self._controls.values())
    def _snapshot_valid(self):
        if not self._snapshot or not self._source:return False
        s=self._snapshot;e=self._source.evidence();p={k:v for k,v in s.__dict__.items() if k!="digest"};previous=source_stage_snapshot_digest("ARKAON-LESSONS-12301",(9901,12700),PRIOR_LESSONS,s.rule_ids,s.previous_registry_snapshot_digest,s.manifest_digest,self._source._docket.digest);return e["integrity_valid"] and e["complete_option_methodology_challenge_evidence"] and e["judgment_authority"] is False and s.snapshot_id=="synthetic:lesson-snapshot:12701-13100" and s.stage_range==(12701,13100) and _hex(s.registry_digest) and _hex(s.manifest_digest) and s.lesson_ids==APPLIED_LESSONS and s.rule_ids==APPLIED_RULES and s.source_docket_digest==self._source._docket.digest and _hex(s.previous_registry_snapshot_digest) and s.previous_snapshot_digest==previous and isinstance(s.sequence,int) and not isinstance(s.sequence,bool) and s.sequence>0 and s.latest is True and s.digest==canonical_digest(p)
    def _prior_actors(self):
        svc=self._source;return svc._prior_actors()+tuple(y for x in svc._challenges.values() for y in (x.challenger,x.custodian) if y)+(svc._docket.compiler,svc._docket.validator)
    def _guidance_valid(self,r,key):
        i=CASE_KEYS.index(key);source=self._source._challenges[key];previous=None if i==0 else self._guidance.get(CASE_KEYS[i-1]);parent=None if previous is None else previous.digest;alts=recovery_alternatives(source) if source.methodology_cards else ();marker="NONBINDING_RECOVERY_GUIDANCE_PENDING_HUMAN_JUDGMENT" if alts else "NO_RECOVERY_GUIDANCE_REQUIRED";reason="FAIL_CLOSED_SEMANTIC_OR_LINEAGE_MISMATCH" if alts else None;candidate=("safe_default_candidate","MINIMAL_SAFE_BINDING","NONBINDING","HUMAN_DETERMINATION_REQUIRED") if alts else None;state=(_syn(r.reviewer,"recovery-guidance-reviewer") and _syn(r.verifier,"recovery-guidance-verifier")) if alts else (r.reviewer is None and r.verifier is None);proj=projection(source.digest,r.reviewer,r.verifier,marker,reason,candidate,alts);values=(r.guidance_id,r.flow,r.answer_kind,source.digest,r.reviewer,r.verifier,marker,parent,i+1,reason,candidate,alts,proj,True,bool(alts),False,False,False,False,False,False);ids=[x.guidance_id for k,x in self._guidance.items() if k!=key];return _syn(r.guidance_id,"versioned-recovery-guidance") and r.guidance_id not in ids and (r.flow,r.answer_kind)==key and state and r.parent_digest==parent and r.position==i+1 and r.rejection_reason==reason and r.safe_candidate==candidate and r.alternatives==alts and len(alts) in (0,2) and r.projection_digest==proj and r.held is True and r.pending_human_judgment is bool(alts) and not any((r.ranked,r.selected,r.concluded,r.recommended,r.accepted,r.resolved)) and r.digest==canonical_digest(("VERSIONED_LESSON_RECOVERY_GUIDANCE",values))
    def _event(self,action,artifact):prev=self._events[-1]["digest"] if self._events else None;p=dict(sequence=len(self._events)+1,action=action,artifact_digest=artifact,previous_digest=prev);self._events.append({**p,"digest":canonical_digest(p)})
    def _hold(self,reason,artifact):prev=self._holds[-1]["digest"] if self._holds else None;p=dict(sequence=len(self._holds)+1,reason=reason,attachment_digest=artifact,previous_digest=prev);self._holds.append({**p,"digest":canonical_digest(p)})
    @staticmethod
    def _chain(rows,kind):
        prev=None
        for i,r in enumerate(rows,1):
            keys=("sequence","action","artifact_digest","previous_digest") if kind=="event" else ("sequence","reason","attachment_digest","previous_digest");p={k:r.get(k) for k in keys}
            if r!={**p,"digest":canonical_digest(p)} or r["sequence"]!=i or r["previous_digest"]!=prev:return False
            prev=r["digest"]
        return True
    def _integrity(self):
        if not self._registry_valid() or not self._snapshot_valid() or not self._chain(self._events,"event") or not self._chain(self._holds,"hold") or any(not self._guidance_valid(v,k) for k,v in self._guidance.items()):return False
        events=[("VERSIONED_LESSON_SNAPSHOT_ANCHORED",self._snapshot.digest)]+[("RECOVERY_GUIDANCE_RECORDED",x.digest) for x in self._guidance.values()];holds=[("HUMAN_RECOVERY_PATH_JUDGMENT_REQUIRED",x.digest) for x in self._guidance.values() if x.pending_human_judgment]
        if self._docket:events.append(("RECOVERY_GUIDANCE_DOCKET_HELD",self._docket.digest))
        if [(x["action"],x["artifact_digest"]) for x in self._events]!=events or [(x["reason"],x["attachment_digest"]) for x in self._holds]!=holds:return False
        if self._docket:
            r=self._docket;p={k:v for k,v in r.__dict__.items() if k!="digest"};actors=self._prior_actors()+tuple(y for x in self._guidance.values() for y in (x.reviewer,x.verifier) if y)+(r.compiler,r.validator);lineage=canonical_digest(("COMPLETE_RECOVERY_GUIDANCE_ROLE_LINEAGE",self._source._docket.role_lineage_digest,actors));return _syn(r.docket_id,"recovery-guidance-docket") and _syn(r.compiler,"recovery-docket-compiler") and _syn(r.validator,"recovery-docket-validator") and r.complete is True and r.held is True and r.pending_human_judgment is True and r.status=="RECOVERY_GUIDANCE_DOCKET_ON_HOLD" and r.snapshot_digest==self._snapshot.digest and r.guidance_set_digest==canonical_digest(tuple(self._guidance[k].digest for k in CASE_KEYS)) and r.role_lineage_digest==lineage and len({_identity(x) for x in actors})==len(actors) and r.digest==canonical_digest(p) and not any((r.ranked,r.selected,r.concluded,r.recommended,r.accepted,r.resolved,r.approved,r.activated,r.deployed))
        return True
    def evidence(self):
        ok=self._integrity();complete=ok and self._docket is not None and len(self._guidance)==20 and len(self._holds)==16;zero={k:0 for k in ("external_calls","document_transmissions","external_pg_calls","card_network_calls","payment_approvals","cancellations","refunds","settlements","transfers","ledger_writes","credential_reads","deployments")};return {"range":[12701,13100],"control_count":400,"registered_control_count":len(self._controls),"guidance_count":len(self._guidance),"recovery_alternative_count":sum(len(x.alternatives) for x in self._guidance.values()),"no_guidance_marker_count":sum(not x.alternatives for x in self._guidance.values()),"human_judgment_hold_count":len(self._holds),"lesson_snapshot_digest":self._snapshot.digest if self._snapshot else None,"previous_snapshot_digest":self._snapshot.previous_snapshot_digest if self._snapshot else None,"guidance_set_digest":self._docket.guidance_set_digest if complete else None,"final_docket_digest":self._docket.digest if complete else None,"complete_role_lineage_digest":self._docket.role_lineage_digest if complete else None,"integrity_valid":ok,"complete_versioned_recovery_guidance_evidence":complete,"maximum_state":"RECOVERY_GUIDANCE_DOCKET_ON_HOLD" if self._docket else "GUIDANCE_INCOMPLETE","applied_lesson_ids":list(APPLIED_LESSONS),"applied_rule_ids":list(APPLIED_RULES),"judgment_authority":False,"ranked":False,"selected":False,"concluded":False,"recommended":False,"accepted":False,"resolved":False,"approved":False,"activated":False,**zero}
