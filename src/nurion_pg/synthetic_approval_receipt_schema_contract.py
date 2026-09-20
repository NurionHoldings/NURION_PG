"""Non-issuing approval receipt schema and idempotency contract #14701-#15100."""
from dataclasses import dataclass
from threading import RLock

from .arkaon.governance import GovernanceRejected,canonical_digest
from .synthetic_approval_intent_envelope_gate import (APPLIED_LESSONS as PRIOR_LESSONS,
    APPLIED_RULES,CASE_KEYS,Envelope,SyntheticApprovalIntentEnvelopeGate,composite_identity)

APPLIED_LESSONS=tuple(sorted(PRIOR_LESSONS+("ARL-14701-001",)))
WORKSTREAM_NAMES=("SOURCE_INTENT_ANCHOR","STAGE_SNAPSHOT_CHAIN","RECEIPT_SCHEMA_IDENTITY","IDEMPOTENCY_KEY_CONTRACT","ISSUER_VERIFIER_SEPARATION","INTENT_KIND_SCOPE","SEQUENCE_PREDECESSOR","NONCE_REPLAY_SCOPE","SERIAL_IDEMPOTENCY","PARALLEL_IDEMPOTENCY","CROSS_KEY_CONFLICT","PARTIAL_BATCH","ORDER_INTEGRITY","RECOVERY_GUIDANCE","FULL_LINEAGE_REHASH","NON_ISSUANCE_NON_AUTHORITY")
WORKSTREAMS=tuple((14701+i*25,14725+i*25,n) for i,n in enumerate(WORKSTREAM_NAMES))
CONTROL_ASPECTS=("input_schema","required_fields","semantic_label","source_type","tenant_scope","role_scope","state_precondition","latest_sequence","source_binding","digest_recalculation","negative_path","missing_input","duplicate_input","replay","conflict","stale_version","concurrency","partial_batch","ordering","append_only","hold_propagation","review_independence","receipt_lineage","operator_gate","non_execution")
NEGATIVE=frozenset({"negative_path","missing_input","duplicate_input","replay","conflict","stale_version","partial_batch"})
STAGE_MAPPING=(("ARKAON-LESSONS-12301",(9901,12700)),("ARKAON-LESSONS-12701",(12701,13100)),("ARKAON-LESSONS-13101",(13101,13500)),("ARKAON-LESSONS-13501",(13501,13900)),("ARKAON-LESSONS-13901",(13901,14300)),("ARKAON-LESSONS-14301",(14301,14700)),("ARKAON-LESSONS-14701",(14701,15100)))
def _hex(v):return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _syn(v,k):return isinstance(v,str) and v.startswith(f"synthetic:{k}:")
def _id(v):return v.rsplit(":",1)[-1].casefold()
def mapping_digest(rows):return canonical_digest(("CONTIGUOUS_STAGE_MAPPING",tuple(rows)))

@dataclass(frozen=True)
class Control:control_id:int;workstream:str;aspect:str;requirement_ref:str;fixture_digest:str;expected_result:str;digest:str
@dataclass(frozen=True)
class Snapshot:snapshot_id:str;stage_range:tuple;mapping_digest:str;registry_digest:str;manifest_digest:str;lesson_ids:tuple;rule_ids:tuple;source_docket_digest:str;previous_snapshot_digest:str;sequence:int;latest:bool;digest:str
@dataclass(frozen=True)
class ReceiptSchema:schema_id:str;idempotency_key_id:str;envelope_id:str;plan_id:str;flow:str;kind:str;source_contract_digest:str;readiness_manifest_digest:str;composite_identity_digest:str;intent_kind:str;source_intent_digest:str;source_actor:str|None;source_counter_actor:str|None;issuer_role:str;verifier_role:str;sequence_precondition:int;predecessor_schema_digest:str|None;prior_intent_digest:str|None;nonce_scope_digest:str;idempotency_scope_digest:str;state:str;receipt_id:str|None;receipt_digest:str|None;issued:bool;materialized:bool;executed:bool;observed:bool;passed:bool;failed:bool;recovery_paths:tuple;position:int;digest:str
@dataclass(frozen=True)
class Docket:docket_id:str;snapshot_digest:str;schema_set_digest:str;compiler:str;validator:str;role_lineage_digest:str;complete:bool;held:bool;pending_human_judgment:bool;receipt_issued:bool;materialized:bool;executed:bool;observed:bool;passed:bool;failed:bool;approved:bool;activated:bool;deployed:bool;status:str;digest:str

def recovery_paths(identity,intent,key_scope):return (("REBUILD_SINGLE_SCHEMA",("cause","schema_identity_or_idempotency_scope_mismatch"),("recommended",True),("cost","LOW"),("risk","LOW"),("reversibility","HIGH"),("validation","rederive_from_intact_source_intent"),("stop","source_or_role_drift"),("resume","fresh_key_after_independent_validation"),("rollback","discard_schema_candidate_preserve_intent"),identity,intent,key_scope),("RECONSTRUCT_DUAL_SCHEMA_PAIR",("cause","cross_kind_predecessor_or_replay_ambiguity"),("recommended",False),("cost","MEDIUM"),("risk","LOW"),("reversibility","HIGH"),("validation","rebuild_materialization_then_execution_pair"),("stop","any_lineage_precondition_unverified"),("resume","new_distinct_keys_and_role_slots"),("rollback","quarantine_pair_preserve_source_docket"),identity,intent,key_scope))
def final_invariants():return (("complete",True),("held",True),("pending_human_judgment",True),("receipt_issued",False),("materialized",False),("executed",False),("observed",False),("passed",False),("failed",False),("approved",False),("activated",False),("deployed",False),("status","RECEIPT_SCHEMA_DOCKET_ON_HOLD"))

class SyntheticApprovalReceiptSchemaContract:
    def __init__(self):self._controls={};self._source=None;self._snapshot=None;self._schemas={};self._keys={};self._docket=None;self._events=[];self._holds=[];self._lock=RLock()
    def _expected(self,cid):i=cid-14701;return WORKSTREAM_NAMES[i//25],CONTROL_ASPECTS[i%25]
    def add_control(self,cid,workstream,aspect,requirement_ref,fixture_digest,expected_result):
        p=dict(control_id=cid,workstream=workstream,aspect=aspect,requirement_ref=requirement_ref,fixture_digest=fixture_digest,expected_result=expected_result);r=Control(**p,digest=canonical_digest(p))
        with self._lock:
            if not self._control_valid(r):raise GovernanceRejected("valid #14701-#15100 control required")
            old=self._controls.get(cid)
            if old:
                if old==r:return old
                raise GovernanceRejected("control conflict")
            self._controls[cid]=r;return r
    def anchor(self,source,mapping,registry,manifest,lessons,rules,previous_snapshot,sequence,latest):
        if not isinstance(source,SyntheticApprovalIntentEnvelopeGate):raise GovernanceRejected("prior intent gate required")
        e=source.evidence();p=dict(snapshot_id="synthetic:lesson-snapshot:14701-15100",stage_range=(14701,15100),mapping_digest=mapping,registry_digest=registry,manifest_digest=manifest,lesson_ids=tuple(lessons),rule_ids=tuple(rules),source_docket_digest=source._docket.digest if source._docket else None,previous_snapshot_digest=previous_snapshot,sequence=sequence,latest=latest);r=Snapshot(**p,digest=canonical_digest(p))
        with self._lock:
            if not(self._registry_valid() and e["complete_approval_intent_envelope_gate_evidence"] and e["integrity_valid"] and mapping==mapping_digest(STAGE_MAPPING) and _hex(registry) and _hex(manifest) and tuple(lessons)==APPLIED_LESSONS and tuple(rules)==APPLIED_RULES and previous_snapshot==source._snapshot.digest and isinstance(sequence,int) and not isinstance(sequence,bool) and sequence>0 and latest is True):raise GovernanceRejected("complete latest receipt-schema snapshot required")
            if self._snapshot:
                if self._source is source and self._snapshot==r:return r
                raise GovernanceRejected("snapshot conflict")
            self._source=source;self._snapshot=r;self._event("RECEIPT_SCHEMA_CHAIN_ANCHORED",r.digest);return r
    def add_schema(self,schema_id,idempotency_key_id,flow,kind,intent_kind,issuer_role,verifier_role):
        with self._lock:
            ek=(flow,kind,intent_kind);source=self._source._envelopes.get(ek) if self._source else None;position=list(self._source._envelopes).index(ek)+1 if source else -1;old=self._schemas.get(ek);by_key=self._keys.get(idempotency_key_id)
            if not source or position<1 or not _syn(idempotency_key_id,"approval-receipt-idempotency-key") or not _syn(issuer_role,"approval-receipt-issuer-role") or not _syn(verifier_role,"approval-receipt-verifier-role") or _id(issuer_role)==_id(verifier_role):raise GovernanceRejected("source-bound independent schema roles and key required")
            occupied=self._source_actors()+tuple(y for k,x in self._schemas.items() if k!=ek for y in (x.issuer_role,x.verifier_role))
            if len({_id(x) for x in occupied+(issuer_role,verifier_role)})!=len(occupied)+2:raise GovernanceRejected("receipt role identity collision")
            predecessor=None if position==1 else next((x.digest for k,x in self._schemas.items() if x.position==position-1),None)
            if position>1 and predecessor is None:raise GovernanceRejected("ordered schema predecessor required")
            identity=composite_identity(self._source._source._plans[(flow,kind)]);key_scope=canonical_digest(("APPROVAL_RECEIPT_IDEMPOTENCY_SCOPE_V1",idempotency_key_id,identity,intent_kind,source.digest,position,predecessor));nonce=canonical_digest(("APPROVAL_RECEIPT_SCHEMA_NONCE_V1",identity,intent_kind,source.nonce_scope_digest,position,predecessor));paths=recovery_paths(identity,intent_kind,key_scope) if source.actor else ();vals=(schema_id,idempotency_key_id,source.envelope_id,source.plan_id,flow,kind,source.source_contract_digest,source.readiness_manifest_digest,identity,intent_kind,source.digest,source.actor,source.counter_actor,issuer_role,verifier_role,position,predecessor,source.prior_intent_digest,nonce,key_scope,"SCHEMA_ONLY_NOT_ISSUED",None,None,False,False,False,False,False,False,paths,position);r=ReceiptSchema(*vals,canonical_digest(("APPROVAL_RECEIPT_SCHEMA_CONTRACT",vals)))
            if old:
                if old==r:return old
                raise GovernanceRejected("receipt schema conflict")
            if by_key:
                if by_key==r:return by_key
                raise GovernanceRejected("idempotency key conflict")
            if any(x.schema_id==schema_id or x.idempotency_scope_digest==key_scope or x.nonce_scope_digest==nonce for x in self._schemas.values()):raise GovernanceRejected("cross-key schema identity replay")
            if not self._schema_valid(r,ek):raise GovernanceRejected("valid non-issuing receipt schema required")
            self._schemas[ek]=r;self._keys[idempotency_key_id]=r;self._event("RECEIPT_SCHEMA_RECORDED",r.digest)
            if source.actor:self._hold("APPROVAL_RECEIPT_SCHEMA_PENDING_HUMAN_ISSUANCE",r.digest)
            return r
    def finalize(self,docket_id,compiler,validator):
        with self._lock:
            expected=tuple(self._source._envelopes)
            if self._docket or tuple(self._schemas)!=expected or not self._integrity():raise GovernanceRejected("complete intact schema batch required")
            roles=self._source_actors()+tuple(y for x in self._schemas.values() for y in (x.issuer_role,x.verifier_role))+(compiler,validator)
            if not _syn(compiler,"receipt-schema-docket-compiler") or not _syn(validator,"receipt-schema-docket-validator") or len({_id(x) for x in roles})!=len(roles):raise GovernanceRejected("independent schema docket roles required")
            p=dict(docket_id=docket_id,snapshot_digest=self._snapshot.digest,schema_set_digest=canonical_digest(tuple(x.digest for x in self._schemas.values())),compiler=compiler,validator=validator,role_lineage_digest=canonical_digest(("COMPLETE_RECEIPT_SCHEMA_ROLE_LINEAGE",self._source._docket.role_lineage_digest,roles)),**dict(final_invariants()));self._docket=Docket(**p,digest=canonical_digest(p));self._event("RECEIPT_SCHEMA_DOCKET_HELD",self._docket.digest);return self._docket
    def _control_valid(self,r):
        p={k:v for k,v in r.__dict__.items() if k!="digest"};return isinstance(r.control_id,int) and not isinstance(r.control_id,bool) and 14701<=r.control_id<=15100 and self._expected(r.control_id)==(r.workstream,r.aspect) and r.requirement_ref==f"synthetic:receipt-schema-requirement:{(r.control_id-14701)//25:02}" and _hex(r.fixture_digest) and r.expected_result==("EXPECTED_REJECTION" if r.aspect in NEGATIVE else "PASS") and r.digest==canonical_digest(p)
    def _registry_valid(self):return set(self._controls)==set(range(14701,15101)) and all(self._control_valid(x) for x in self._controls.values())
    def _source_actors(self):return tuple(y for x in self._source._envelopes.values() for y in (x.actor,x.counter_actor) if y) if self._source else ()
    def _snapshot_valid(self):
        if not self._snapshot or not self._source:return False
        s=self._snapshot;p={k:v for k,v in s.__dict__.items() if k!="digest"};e=self._source.evidence();return e["integrity_valid"] and e["complete_approval_intent_envelope_gate_evidence"] and s.snapshot_id=="synthetic:lesson-snapshot:14701-15100" and s.stage_range==(14701,15100) and s.mapping_digest==mapping_digest(STAGE_MAPPING) and all(_hex(x) for x in (s.registry_digest,s.manifest_digest)) and s.lesson_ids==APPLIED_LESSONS and s.rule_ids==APPLIED_RULES and s.source_docket_digest==self._source._docket.digest and s.previous_snapshot_digest==self._source._snapshot.digest and s.latest is True and isinstance(s.sequence,int) and not isinstance(s.sequence,bool) and s.sequence>0 and s.digest==canonical_digest(p)
    def _schema_valid(self,r,key):
        source=self._source._envelopes.get(key);position=list(self._source._envelopes).index(key)+1 if source else -1;predecessor=None if position==1 else next((x.digest for x in self._schemas.values() if x.position==position-1),None);identity=composite_identity(self._source._source._plans[(r.flow,r.kind)]);scope=canonical_digest(("APPROVAL_RECEIPT_IDEMPOTENCY_SCOPE_V1",r.idempotency_key_id,identity,r.intent_kind,source.digest,position,predecessor));nonce=canonical_digest(("APPROVAL_RECEIPT_SCHEMA_NONCE_V1",identity,r.intent_kind,source.nonce_scope_digest,position,predecessor));paths=recovery_paths(identity,r.intent_kind,scope) if source.actor else ();vals=(r.schema_id,r.idempotency_key_id,source.envelope_id,source.plan_id,r.flow,r.kind,source.source_contract_digest,source.readiness_manifest_digest,identity,r.intent_kind,source.digest,source.actor,source.counter_actor,r.issuer_role,r.verifier_role,position,predecessor,source.prior_intent_digest,nonce,scope,"SCHEMA_ONLY_NOT_ISSUED",None,None,False,False,False,False,False,False,paths,position)
        occupied=self._source_actors()+tuple(y for k,x in self._schemas.items() if k!=key for y in (x.issuer_role,x.verifier_role));roles=occupied+(r.issuer_role,r.verifier_role)
        return _syn(r.schema_id,"approval-receipt-schema") and _syn(r.idempotency_key_id,"approval-receipt-idempotency-key") and _syn(r.issuer_role,"approval-receipt-issuer-role") and _syn(r.verifier_role,"approval-receipt-verifier-role") and len({_id(x) for x in roles})==len(roles) and (r.flow,r.kind,r.intent_kind)==key and r.predecessor_schema_digest==predecessor and r.position==position and r.digest==canonical_digest(("APPROVAL_RECEIPT_SCHEMA_CONTRACT",vals)) and tuple(getattr(r,x) for x in ReceiptSchema.__dataclass_fields__ if x!="digest")==vals
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
        if not self._registry_valid() or not self._snapshot_valid() or not self._chain(self._events) or not self._chain(self._holds,True) or len(self._keys)!=len(self._schemas) or any(self._keys.get(x.idempotency_key_id)!=x for x in self._schemas.values()) or any(not self._schema_valid(v,k) for k,v in self._schemas.items()):return False
        events=[("RECEIPT_SCHEMA_CHAIN_ANCHORED",self._snapshot.digest)]+[("RECEIPT_SCHEMA_RECORDED",x.digest) for x in self._schemas.values()];holds=[("APPROVAL_RECEIPT_SCHEMA_PENDING_HUMAN_ISSUANCE",x.digest) for x in self._schemas.values() if x.source_actor]
        if self._docket:events.append(("RECEIPT_SCHEMA_DOCKET_HELD",self._docket.digest))
        if [(x["action"],x["artifact_digest"]) for x in self._events]!=events or [(x["reason"],x["attachment_digest"]) for x in self._holds]!=holds:return False
        if not self._docket:return True
        r=self._docket;p={k:v for k,v in r.__dict__.items() if k!="digest"};roles=self._source_actors()+tuple(y for x in self._schemas.values() for y in (x.issuer_role,x.verifier_role))+(r.compiler,r.validator);return _syn(r.docket_id,"receipt-schema-docket") and _syn(r.compiler,"receipt-schema-docket-compiler") and _syn(r.validator,"receipt-schema-docket-validator") and len({_id(x) for x in roles})==len(roles) and r.snapshot_digest==self._snapshot.digest and r.schema_set_digest==canonical_digest(tuple(x.digest for x in self._schemas.values())) and r.role_lineage_digest==canonical_digest(("COMPLETE_RECEIPT_SCHEMA_ROLE_LINEAGE",self._source._docket.role_lineage_digest,roles)) and tuple((k,getattr(r,k)) for k,_ in final_invariants())==final_invariants() and r.digest==canonical_digest(p)
    def evidence(self):
        ok=self._integrity();complete=ok and self._docket is not None and len(self._schemas)==40 and len(self._holds)==32;zero={k:0 for k in ("approval_receipts_issued","fixture_materializations","probe_executions","observation_values","external_calls","document_transmissions","external_pg_calls","card_network_calls","payment_approvals","cancellations","refunds","settlements","transfers","ledger_writes","credential_reads","deployments")};return {"range":[14701,15100],"control_count":400,"registered_control_count":len(self._controls),"receipt_schema_count":len(self._schemas),"idempotency_key_contract_count":len(self._keys),"recovery_path_count":sum(len(x.recovery_paths) for x in self._schemas.values()),"human_judgment_hold_count":len(self._holds),"snapshot_digest":self._snapshot.digest if self._snapshot else None,"final_docket_digest":self._docket.digest if complete else None,"integrity_valid":ok,"complete_approval_receipt_schema_contract_evidence":complete,"maximum_state":"RECEIPT_SCHEMA_DOCKET_ON_HOLD" if self._docket else "RECEIPT_SCHEMA_INCOMPLETE","applied_lesson_ids":list(APPLIED_LESSONS),"applied_rule_ids":list(APPLIED_RULES),"judgment_authority":False,"recommendation_authority":False,"selection_authority":False,"acceptance_authority":False,"resolution_authority":False,"approved":False,"materialized":False,"executed":False,"observed":False,"passed":False,"failed":False,"activated":False,**zero}
