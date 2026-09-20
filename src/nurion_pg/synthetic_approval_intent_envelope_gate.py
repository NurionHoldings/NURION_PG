"""Composite plan identity and dual pending approval-intent envelopes #14301-#14700."""
from dataclasses import dataclass
from threading import RLock

from .arkaon.governance import GovernanceRejected,canonical_digest
from .synthetic_observation_readiness_manifest import APPLIED_LESSONS as PRIOR_LESSONS,APPLIED_RULES,CASE_KEYS,SyntheticObservationReadinessManifest

APPLIED_LESSONS=tuple(sorted(PRIOR_LESSONS+("ARL-14301-001",)))
WORKSTREAM_NAMES=("SOURCE_READINESS_ANCHOR","STAGE_SNAPSHOT_CHAIN","COMPOSITE_PLAN_IDENTITY","MATERIALIZATION_INTENT_SCHEMA","EXECUTION_INTENT_SCHEMA","ACTOR_SEPARATION","SEQUENCE_PRECONDITION","NONCE_REPLAY_SCOPE","PENDING_ENVELOPE","FINAL_DOCKET_INTERFACE","RECOVERY_GUIDANCE","STOP_RESUME_ROLLBACK","ORDER_CONCURRENCY","PARTIAL_BATCH","FULL_LINEAGE_REHASH","NON_EXECUTION_NON_AUTHORITY")
WORKSTREAMS=tuple((14301+i*25,14325+i*25,n) for i,n in enumerate(WORKSTREAM_NAMES))
CONTROL_ASPECTS=("input_schema","required_fields","semantic_label","source_type","tenant_scope","role_scope","state_precondition","latest_sequence","source_binding","digest_recalculation","negative_path","missing_input","duplicate_input","replay","conflict","stale_version","concurrency","partial_batch","ordering","append_only","hold_propagation","review_independence","receipt_lineage","operator_gate","non_execution")
NEGATIVE=frozenset({"negative_path","missing_input","duplicate_input","replay","conflict","stale_version","partial_batch"})
STAGE_MAPPING=(("ARKAON-LESSONS-12301",(9901,12700)),("ARKAON-LESSONS-12701",(12701,13100)),("ARKAON-LESSONS-13101",(13101,13500)),("ARKAON-LESSONS-13501",(13501,13900)),("ARKAON-LESSONS-13901",(13901,14300)),("ARKAON-LESSONS-14301",(14301,14700)))
def _hex(v):return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _syn(v,k):return isinstance(v,str) and v.startswith(f"synthetic:{k}:")
def _id(v):return v.rsplit(":",1)[-1].casefold()
def mapping_digest(rows):return canonical_digest(("CONTIGUOUS_STAGE_MAPPING",tuple(rows)))

@dataclass(frozen=True)
class Control:control_id:int;workstream:str;aspect:str;requirement_ref:str;fixture_digest:str;expected_result:str;digest:str
@dataclass(frozen=True)
class Snapshot:snapshot_id:str;stage_range:tuple;mapping_digest:str;registry_digest:str;manifest_digest:str;lesson_ids:tuple;rule_ids:tuple;source_docket_digest:str;previous_snapshot_digest:str;sequence:int;latest:bool;digest:str
@dataclass(frozen=True)
class Envelope:envelope_id:str;plan_id:str;flow:str;kind:str;source_contract_digest:str;readiness_manifest_digest:str;composite_identity_digest:str;intent_kind:str;actor:str;counter_actor:str;sequence_precondition:int;prior_intent_digest:str|None;nonce_scope_digest:str;state:str;receipt_issued:bool;materialized:bool;executed:bool;recovery_paths:tuple;parent_digest:str|None;position:int;digest:str
@dataclass(frozen=True)
class Docket:docket_id:str;snapshot_digest:str;envelope_set_digest:str;compiler:str;validator:str;role_lineage_digest:str;complete:bool;held:bool;pending_human_judgment:bool;receipt_issued:bool;materialized:bool;executed:bool;passed:bool;failed:bool;approved:bool;activated:bool;deployed:bool;status:str;digest:str

def composite_identity(plan):return canonical_digest(("COMPOSITE_PLAN_IDENTITY_V1",plan.plan_id,plan.flow,plan.kind,plan.source_contract_digest,plan.digest))
def recovery_paths(identity,kind):return (("MINIMAL_ENVELOPE_REPAIR",("cause","missing_or_mismatched_identity_or_sequence"),("cost","LOW"),("risk","LOW"),("reversibility","HIGH"),("validation","rebuild_and_independent_schema_check"),("stop","source_or_actor_drift"),("resume","fresh_nonce_scope_after_full_validation"),("rollback","discard_pending_envelope_preserve_plan"),identity,kind),("FRESH_DUAL_INTENT_RECONSTRUCTION",("cause","cross_kind_actor_or_replay_ambiguity"),("cost","MEDIUM"),("risk","LOW"),("reversibility","HIGH"),("validation","reconstruct_both_pending_envelopes_from_source"),("stop","any_precondition_unverified"),("resume","new_independent_actors_and_sequence"),("rollback","quarantine_both_candidates"),identity,kind))
def final_docket_invariants():return (("complete",True),("held",True),("pending_human_judgment",True),("receipt_issued",False),("materialized",False),("executed",False),("passed",False),("failed",False),("approved",False),("activated",False),("deployed",False),("status","APPROVAL_INTENT_DOCKET_ON_HOLD"))

class SyntheticApprovalIntentEnvelopeGate:
    def __init__(self):self._controls={};self._source=None;self._snapshot=None;self._envelopes={};self._docket=None;self._events=[];self._holds=[];self._lock=RLock()
    def _expected(self,cid):i=cid-14301;return WORKSTREAM_NAMES[i//25],CONTROL_ASPECTS[i%25]
    def add_control(self,cid,workstream,aspect,requirement_ref,fixture_digest,expected_result):
        p=dict(control_id=cid,workstream=workstream,aspect=aspect,requirement_ref=requirement_ref,fixture_digest=fixture_digest,expected_result=expected_result);r=Control(**p,digest=canonical_digest(p))
        with self._lock:
            if not self._control_valid(r):raise GovernanceRejected("valid #14301-#14700 control required")
            old=self._controls.get(cid)
            if old:
                if old==r:return old
                raise GovernanceRejected("control conflict")
            self._controls[cid]=r;return r
    def anchor(self,source,mapping,registry,manifest,lessons,rules,previous_snapshot,sequence,latest):
        if not isinstance(source,SyntheticObservationReadinessManifest):raise GovernanceRejected("prior readiness manifest required")
        e=source.evidence();p=dict(snapshot_id="synthetic:lesson-snapshot:14301-14700",stage_range=(14301,14700),mapping_digest=mapping,registry_digest=registry,manifest_digest=manifest,lesson_ids=tuple(lessons),rule_ids=tuple(rules),source_docket_digest=source._docket.digest if source._docket else None,previous_snapshot_digest=previous_snapshot,sequence=sequence,latest=latest);r=Snapshot(**p,digest=canonical_digest(p))
        with self._lock:
            if not(self._registry_valid() and e["complete_observation_readiness_manifest_evidence"] and e["integrity_valid"] and mapping==mapping_digest(STAGE_MAPPING) and _hex(registry) and _hex(manifest) and tuple(lessons)==APPLIED_LESSONS and tuple(rules)==APPLIED_RULES and previous_snapshot==source._snapshot.digest and isinstance(sequence,int) and not isinstance(sequence,bool) and sequence>0 and latest is True):raise GovernanceRejected("complete latest envelope snapshot required")
            if self._snapshot:
                if self._source is source and self._snapshot==r:return r
                raise GovernanceRejected("snapshot conflict")
            self._source=source;self._snapshot=r;self._event("INTENT_CHAIN_ANCHORED",r.digest);return r
    def add_envelope(self,envelope_id,flow,kind,intent_kind,actor=None,counter_actor=None):
        with self._lock:
            key=(flow,kind);i=CASE_KEYS.index(key) if key in CASE_KEYS else -1;ek=(flow,kind,intent_kind)
            if not self._snapshot or i<0 or intent_kind not in ("MATERIALIZATION","EXECUTION") or (intent_kind=="EXECUTION" and (flow,kind,"MATERIALIZATION") not in self._envelopes) or (i and intent_kind=="MATERIALIZATION" and (CASE_KEYS[i-1][0],CASE_KEYS[i-1][1],"EXECUTION") not in self._envelopes):raise GovernanceRejected("anchored ordered dual intent required")
            plan=self._source._plans[key];routed=plan.pending_human_judgment;identity=composite_identity(plan);position=i*2+(1 if intent_kind=="MATERIALIZATION" else 2);prior=self._envelopes.get((flow,kind,"MATERIALIZATION")) if intent_kind=="EXECUTION" else None;parent=None if position==1 else next((x.digest for k,x in self._envelopes.items() if k!=ek and x.position==position-1),None);old=self._envelopes.get(ek)
            if routed:
                if not _syn(actor,"approval-intent-actor") or not _syn(counter_actor,"approval-intent-counter-actor"):raise GovernanceRejected("independent pending-intent actors required")
                actors=self._prior_actors()+tuple(y for k,x in self._envelopes.items() if k!=ek for y in (x.actor,x.counter_actor) if y)+(actor,counter_actor)
                if len({_id(x) for x in actors})!=len(actors):raise GovernanceRejected("actor collision")
            elif actor is not None or counter_actor is not None:raise GovernanceRejected("N/A forbids actors")
            nonce=canonical_digest(("PENDING_NONCE_SCOPE",identity,intent_kind,position,prior.digest if prior else None));paths=recovery_paths(identity,intent_kind) if routed else ();vals=(envelope_id,plan.plan_id,flow,kind,plan.source_contract_digest,plan.digest,identity,intent_kind,actor,counter_actor,position,prior.digest if prior else None,nonce,"PENDING_NOT_ISSUED",False,False,False,paths,parent,position);r=Envelope(*vals,canonical_digest(("APPROVAL_INTENT_ENVELOPE",vals)))
            if not self._envelope_valid(r,ek):raise GovernanceRejected("valid pending approval-intent envelope required")
            if old:
                if old==r:return old
                raise GovernanceRejected("envelope conflict")
            if any(x.envelope_id==envelope_id or x.nonce_scope_digest==nonce for k,x in self._envelopes.items() if k!=ek):raise GovernanceRejected("intent replay")
            self._envelopes[ek]=r;self._event("PENDING_INTENT_RECORDED",r.digest)
            if routed:self._hold(f"{intent_kind}_APPROVAL_PENDING",r.digest)
            return r
    def finalize(self,docket_id,compiler,validator):
        with self._lock:
            expected=tuple((f,k,t) for f,k in CASE_KEYS for t in ("MATERIALIZATION","EXECUTION"))
            if self._docket or tuple(self._envelopes)!=expected or not self._integrity():raise GovernanceRejected("complete intact dual-intent batch required")
            actors=self._prior_actors()+tuple(y for x in self._envelopes.values() for y in (x.actor,x.counter_actor) if y)+(compiler,validator)
            if not _syn(compiler,"intent-docket-compiler") or not _syn(validator,"intent-docket-validator") or len({_id(x) for x in actors})!=len(actors):raise GovernanceRejected("independent final actors required")
            p=dict(docket_id=docket_id,snapshot_digest=self._snapshot.digest,envelope_set_digest=canonical_digest(tuple(x.digest for x in self._envelopes.values())),compiler=compiler,validator=validator,role_lineage_digest=canonical_digest(("COMPLETE_INTENT_ROLE_LINEAGE",self._source._docket.role_lineage_digest,actors)),**dict(final_docket_invariants()));self._docket=Docket(**p,digest=canonical_digest(p));self._event("APPROVAL_INTENT_DOCKET_HELD",self._docket.digest);return self._docket
    def _control_valid(self,r):
        p={k:v for k,v in r.__dict__.items() if k!="digest"};return isinstance(r.control_id,int) and not isinstance(r.control_id,bool) and 14301<=r.control_id<=14700 and self._expected(r.control_id)==(r.workstream,r.aspect) and r.requirement_ref==f"synthetic:intent-requirement:{(r.control_id-14301)//25:02}" and _hex(r.fixture_digest) and r.expected_result==("EXPECTED_REJECTION" if r.aspect in NEGATIVE else "PASS") and r.digest==canonical_digest(p)
    def _registry_valid(self):return set(self._controls)==set(range(14301,14701)) and all(self._control_valid(x) for x in self._controls.values())
    def _prior_actors(self):
        s=self._source;return s._prior_actors()+tuple(y for x in s._plans.values() for y in (x.planner,x.challenger) if y)+(s._docket.compiler,s._docket.validator)
    def _snapshot_valid(self):
        if not self._snapshot or not self._source:return False
        s=self._snapshot;p={k:v for k,v in s.__dict__.items() if k!="digest"};e=self._source.evidence();return e["integrity_valid"] and e["complete_observation_readiness_manifest_evidence"] and s.snapshot_id=="synthetic:lesson-snapshot:14301-14700" and s.stage_range==(14301,14700) and s.mapping_digest==mapping_digest(STAGE_MAPPING) and all(_hex(x) for x in (s.registry_digest,s.manifest_digest)) and s.lesson_ids==APPLIED_LESSONS and s.rule_ids==APPLIED_RULES and s.source_docket_digest==self._source._docket.digest and s.previous_snapshot_digest==self._source._snapshot.digest and s.latest is True and isinstance(s.sequence,int) and not isinstance(s.sequence,bool) and s.sequence>0 and s.digest==canonical_digest(p)
    def _envelope_valid(self,r,key):
        flow,kind,intent=key;i=CASE_KEYS.index((flow,kind));plan=self._source._plans[(flow,kind)];routed=plan.pending_human_judgment;position=i*2+(1 if intent=="MATERIALIZATION" else 2);prior=self._envelopes.get((flow,kind,"MATERIALIZATION")) if intent=="EXECUTION" else None;parent=None if position==1 else next((x.digest for x in self._envelopes.values() if x.position==position-1),None);identity=composite_identity(plan);nonce=canonical_digest(("PENDING_NONCE_SCOPE",identity,intent,position,prior.digest if prior else None));actors=(_syn(r.actor,"approval-intent-actor") and _syn(r.counter_actor,"approval-intent-counter-actor")) if routed else r.actor is None and r.counter_actor is None;paths=recovery_paths(identity,intent) if routed else ();vals=(r.envelope_id,plan.plan_id,flow,kind,plan.source_contract_digest,plan.digest,identity,intent,r.actor,r.counter_actor,position,prior.digest if prior else None,nonce,"PENDING_NOT_ISSUED",False,False,False,paths,parent,position)
        others=[x for k,x in self._envelopes.items() if k!=key];return _syn(r.envelope_id,"approval-intent-envelope") and not any(x.envelope_id==r.envelope_id or x.nonce_scope_digest==nonce for x in others) and (r.flow,r.kind,r.intent_kind)==key and actors and r.parent_digest==parent and r.position==position and tuple(getattr(r,x) for x in ("plan_id","source_contract_digest","readiness_manifest_digest","composite_identity_digest"))==(plan.plan_id,plan.source_contract_digest,plan.digest,identity) and r.sequence_precondition==position and r.prior_intent_digest==(prior.digest if prior else None) and r.nonce_scope_digest==nonce and r.state=="PENDING_NOT_ISSUED" and not any((r.receipt_issued,r.materialized,r.executed)) and r.recovery_paths==paths and r.digest==canonical_digest(("APPROVAL_INTENT_ENVELOPE",vals))
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
        if not self._registry_valid() or not self._snapshot_valid() or not self._chain(self._events) or not self._chain(self._holds,True) or any(not self._envelope_valid(v,k) for k,v in self._envelopes.items()):return False
        events=[("INTENT_CHAIN_ANCHORED",self._snapshot.digest)]+[("PENDING_INTENT_RECORDED",x.digest) for x in self._envelopes.values()];holds=[(f"{x.intent_kind}_APPROVAL_PENDING",x.digest) for x in self._envelopes.values() if x.actor]
        if self._docket:events.append(("APPROVAL_INTENT_DOCKET_HELD",self._docket.digest))
        if [(x["action"],x["artifact_digest"]) for x in self._events]!=events or [(x["reason"],x["attachment_digest"]) for x in self._holds]!=holds:return False
        if not self._docket:return True
        r=self._docket;p={k:v for k,v in r.__dict__.items() if k!="digest"};actors=self._prior_actors()+tuple(y for x in self._envelopes.values() for y in (x.actor,x.counter_actor) if y)+(r.compiler,r.validator);return _syn(r.docket_id,"intent-docket") and _syn(r.compiler,"intent-docket-compiler") and _syn(r.validator,"intent-docket-validator") and r.snapshot_digest==self._snapshot.digest and r.envelope_set_digest==canonical_digest(tuple(x.digest for x in self._envelopes.values())) and r.role_lineage_digest==canonical_digest(("COMPLETE_INTENT_ROLE_LINEAGE",self._source._docket.role_lineage_digest,actors)) and len({_id(x) for x in actors})==len(actors) and tuple((k,getattr(r,k)) for k,_ in final_docket_invariants())==final_docket_invariants() and r.digest==canonical_digest(p)
    def evidence(self):
        ok=self._integrity();complete=ok and self._docket is not None and len(self._envelopes)==40 and len(self._holds)==32;zero={k:0 for k in ("approval_receipts_issued","fixture_materializations","probe_executions","observation_values","external_calls","document_transmissions","external_pg_calls","card_network_calls","payment_approvals","cancellations","refunds","settlements","transfers","ledger_writes","credential_reads","deployments")};return {"range":[14301,14700],"control_count":400,"registered_control_count":len(self._controls),"envelope_count":len(self._envelopes),"materialization_intent_count":sum(x.intent_kind=="MATERIALIZATION" for x in self._envelopes.values()),"execution_intent_count":sum(x.intent_kind=="EXECUTION" for x in self._envelopes.values()),"recovery_path_count":sum(len(x.recovery_paths) for x in self._envelopes.values()),"human_judgment_hold_count":len(self._holds),"snapshot_digest":self._snapshot.digest if self._snapshot else None,"final_docket_digest":self._docket.digest if complete else None,"complete_role_lineage_digest":self._docket.role_lineage_digest if complete else None,"integrity_valid":ok,"complete_approval_intent_envelope_gate_evidence":complete,"maximum_state":"APPROVAL_INTENT_DOCKET_ON_HOLD" if self._docket else "INTENT_SCHEMA_INCOMPLETE","applied_lesson_ids":list(APPLIED_LESSONS),"applied_rule_ids":list(APPLIED_RULES),"judgment_authority":False,"recommendation_authority":False,"selection_authority":False,"acceptance_authority":False,"resolution_authority":False,"approved":False,"materialized":False,"executed":False,"passed":False,"failed":False,"activated":False,**zero}
