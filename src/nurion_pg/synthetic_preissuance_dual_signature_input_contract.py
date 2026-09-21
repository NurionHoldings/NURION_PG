"""Pre-issuance validation packets and dual signature-input contract #15101-#15500.

This layer only derives deterministic, content-addressed inputs.  It never reads
keys, creates signatures, issues receipts, or calls an external verifier.
"""
from dataclasses import dataclass
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest
from .synthetic_approval_receipt_schema_contract import (
    APPLIED_LESSONS as PRIOR_LESSONS, APPLIED_RULES, ReceiptSchema,
    STAGE_MAPPING as PRIOR_STAGE_MAPPING, SyntheticApprovalReceiptSchemaContract,
)

APPLIED_LESSONS=tuple(sorted(PRIOR_LESSONS+("ARL-15101-001",)))
WORKSTREAM_NAMES=("SOURCE_SCHEMA_ANCHOR","STAGE_SNAPSHOT_CHAIN","PACKET_IDENTITY","IDEMPOTENCY_SCOPE","ISSUER_INPUT","VERIFIER_INPUT","ACTOR_INDEPENDENCE","CHALLENGE_DOMAIN_SEPARATION","AUDIENCE_PURPOSE_BINDING","POLICY_VERSION","DETERMINISTIC_EXPIRY","SEQUENCE_PREDECESSOR","NONCE_REPLAY_SCOPE","PARALLEL_IDEMPOTENCY","RECOVERY_GUIDANCE","NON_ISSUANCE_NON_AUTHORITY")
WORKSTREAMS=tuple((15101+i*25,15125+i*25,n) for i,n in enumerate(WORKSTREAM_NAMES))
CONTROL_ASPECTS=("input_schema","required_fields","semantic_label","source_type","tenant_scope","role_scope","state_precondition","latest_sequence","source_binding","digest_recalculation","negative_path","missing_input","duplicate_input","replay","conflict","stale_version","concurrency","partial_batch","ordering","append_only","hold_propagation","review_independence","receipt_lineage","operator_gate","non_execution")
NEGATIVE=frozenset({"negative_path","missing_input","duplicate_input","replay","conflict","stale_version","partial_batch"})
STAGE_MAPPING=PRIOR_STAGE_MAPPING+(("ARKAON-LESSONS-15101",(15101,15500)),)
SYNTHETIC_EPOCH=2_000_000_000
REQUIRED_POLICY_VERSION="synthetic:signature-policy-version:v1"

def _hex(v):return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _syn(v,k):return isinstance(v,str) and v.startswith(f"synthetic:{k}:")
def _id(v):return v.rsplit(":",1)[-1].casefold()
def mapping_digest(rows):return canonical_digest(("CONTIGUOUS_STAGE_MAPPING",tuple(rows)))

@dataclass(frozen=True)
class Control:control_id:int;workstream:str;aspect:str;requirement_ref:str;fixture_digest:str;expected_result:str;digest:str
@dataclass(frozen=True)
class Snapshot:snapshot_id:str;stage_range:tuple;mapping_digest:str;registry_digest:str;manifest_digest:str;lesson_ids:tuple;rule_ids:tuple;source_docket_digest:str;previous_snapshot_digest:str;sequence:int;latest:bool;digest:str
@dataclass(frozen=True)
class ValidationPacket:
    packet_id:str;idempotency_key_id:str;source_schema_id:str;source_schema_digest:str;source_idempotency_scope_digest:str;source_intent_digest:str;composite_identity_digest:str;flow:str;kind:str;intent_kind:str;issuer_actor:str;verifier_actor:str;issuer_domain:str;verifier_domain:str;issuer_challenge:str;verifier_challenge:str;issuer_audience:str;verifier_audience:str;issuer_purpose:str;verifier_purpose:str;policy_version:str;issued_at_epoch:int;expires_at_epoch:int;sequence:int;predecessor_packet_digest:str|None;nonce_scope_digest:str;packet_scope_digest:str;issuer_signature_input_digest:str;verifier_signature_input_digest:str;state:str;signature_value:str|None;receipt_id:str|None;receipt_digest:str|None;issued:bool;verified:bool;materialized:bool;executed:bool;observed:bool;passed:bool;failed:bool;recovery_paths:tuple;position:int;digest:str
@dataclass(frozen=True)
class Docket:docket_id:str;snapshot_digest:str;packet_set_digest:str;compiler:str;validator:str;role_lineage_digest:str;complete:bool;held:bool;pending_human_judgment:bool;receipt_issued:bool;signature_created:bool;signature_verified:bool;materialized:bool;executed:bool;observed:bool;passed:bool;failed:bool;approved:bool;activated:bool;deployed:bool;status:str;digest:str

def recovery_paths(identity,intent,scope):
    return (("REBUILD_SIGNATURE_INPUT_PACKET",("cause","input_binding_or_idempotency_mismatch"),("recommended",True),("cost","LOW"),("risk","LOW"),("reversibility","HIGH"),("validation","rederive_both_inputs_from_intact_schema"),("stop","source_actor_policy_or_challenge_drift"),("resume","fresh_key_after_independent_validation"),("rollback","discard_packet_preserve_schema"),identity,intent,scope),("RECONSTRUCT_ORDERED_PACKET_PAIR",("cause","predecessor_nonce_or_dual_role_ambiguity"),("recommended",False),("cost","MEDIUM"),("risk","LOW"),("reversibility","HIGH"),("validation","rebuild_in_canonical_order"),("stop","any_source_precondition_unverified"),("resume","new_distinct_actor_slots_and_challenges"),("rollback","quarantine_batch_preserve_source_docket"),identity,intent,scope))
def final_invariants():return (("complete",True),("held",True),("pending_human_judgment",True),("receipt_issued",False),("signature_created",False),("signature_verified",False),("materialized",False),("executed",False),("observed",False),("passed",False),("failed",False),("approved",False),("activated",False),("deployed",False),("status","PREISSUANCE_SIGNATURE_INPUT_DOCKET_ON_HOLD"))

class SyntheticPreissuanceDualSignatureInputContract:
    def __init__(self):self._controls={};self._source=None;self._snapshot=None;self._packets={};self._keys={};self._docket=None;self._events=[];self._holds=[];self._lock=RLock()
    def _expected(self,cid):i=cid-15101;return WORKSTREAM_NAMES[i//25],CONTROL_ASPECTS[i%25]
    def add_control(self,cid,workstream,aspect,requirement_ref,fixture_digest,expected_result):
        p=dict(control_id=cid,workstream=workstream,aspect=aspect,requirement_ref=requirement_ref,fixture_digest=fixture_digest,expected_result=expected_result);r=Control(**p,digest=canonical_digest(p))
        with self._lock:
            if not self._control_valid(r):raise GovernanceRejected("valid #15101-#15500 control required")
            old=self._controls.get(cid)
            if old:
                if old==r:return old
                raise GovernanceRejected("control conflict")
            self._controls[cid]=r;return r
    def anchor(self,source,mapping,registry,manifest,lessons,rules,previous_snapshot,sequence,latest):
        if not isinstance(source,SyntheticApprovalReceiptSchemaContract):raise GovernanceRejected("prior receipt schema contract required")
        e=source.evidence();p=dict(snapshot_id="synthetic:lesson-snapshot:15101-15500",stage_range=(15101,15500),mapping_digest=mapping,registry_digest=registry,manifest_digest=manifest,lesson_ids=tuple(lessons),rule_ids=tuple(rules),source_docket_digest=source._docket.digest if source._docket else None,previous_snapshot_digest=previous_snapshot,sequence=sequence,latest=latest);r=Snapshot(**p,digest=canonical_digest(p))
        with self._lock:
            if not(self._registry_valid() and e["complete_approval_receipt_schema_contract_evidence"] and e["integrity_valid"] and mapping==mapping_digest(STAGE_MAPPING) and _hex(registry) and _hex(manifest) and tuple(lessons)==APPLIED_LESSONS and tuple(rules)==APPLIED_RULES and previous_snapshot==source._snapshot.digest and isinstance(sequence,int) and not isinstance(sequence,bool) and sequence>0 and latest is True):raise GovernanceRejected("complete latest preissuance snapshot required")
            if self._snapshot:
                if self._source is source and self._snapshot==r:return r
                raise GovernanceRejected("snapshot conflict")
            self._source=source;self._snapshot=r;self._event("PREISSUANCE_CHAIN_ANCHORED",r.digest);return r
    def add_packet(self,packet_id,idempotency_key_id,flow,kind,intent_kind,issuer_actor,verifier_actor,issuer_challenge,verifier_challenge,issuer_audience,verifier_audience,issuer_purpose,verifier_purpose,policy_version):
        with self._lock:
            key=(flow,kind,intent_kind);source=self._source._schemas.get(key) if self._source else None;position=list(self._source._schemas).index(key)+1 if source else -1;old=self._packets.get(key);by_key=self._keys.get(idempotency_key_id)
            if not source or position<1:raise GovernanceRejected("source schema required")
            issuer_domain=f"synthetic:signature-domain:issuer:{position}";verifier_domain=f"synthetic:signature-domain:verifier:{position}"
            if not all((_syn(packet_id,"preissuance-validation-packet"),_syn(idempotency_key_id,"preissuance-packet-idempotency-key"),_syn(issuer_actor,"preissuance-issuer"),_syn(verifier_actor,"preissuance-verifier"),_syn(issuer_challenge,"issuer-challenge"),_syn(verifier_challenge,"verifier-challenge"),_syn(issuer_audience,"issuer-audience"),_syn(verifier_audience,"verifier-audience"),_syn(issuer_purpose,"issuer-purpose"),_syn(verifier_purpose,"verifier-purpose"))):raise GovernanceRejected("complete synthetic dual inputs required")
            if policy_version!=REQUIRED_POLICY_VERSION:raise GovernanceRejected("required signature policy version only")
            if issuer_challenge==verifier_challenge or _id(issuer_actor)==_id(verifier_actor):raise GovernanceRejected("independent actors and challenges required")
            occupied=self._all_source_actors()+tuple(y for k,x in self._packets.items() if k!=key for y in (x.issuer_actor,x.verifier_actor))
            if len({_id(x) for x in occupied+(issuer_actor,verifier_actor)})!=len(occupied)+2:raise GovernanceRejected("global actor identity collision")
            predecessor=None if position==1 else next((x.digest for x in self._packets.values() if x.position==position-1),None)
            if position>1 and predecessor is None:raise GovernanceRejected("ordered packet predecessor required")
            issued_at=SYNTHETIC_EPOCH+position*100;expires_at=issued_at+300;identity=source.composite_identity_digest
            scope=canonical_digest(("PREISSUANCE_PACKET_SCOPE_V1",idempotency_key_id,source.digest,source.idempotency_scope_digest,identity,position,predecessor,policy_version))
            nonce=canonical_digest(("PREISSUANCE_PACKET_NONCE_V1",source.nonce_scope_digest,scope,position,predecessor))
            issuer_input=canonical_digest(("ISSUER_SIGNATURE_INPUT_V1",source.digest,scope,nonce,issuer_actor,issuer_domain,issuer_challenge,issuer_audience,issuer_purpose,policy_version,issued_at,expires_at))
            verifier_input=canonical_digest(("VERIFIER_SIGNATURE_INPUT_V1",source.digest,scope,nonce,verifier_actor,verifier_domain,verifier_challenge,verifier_audience,verifier_purpose,policy_version,issued_at,expires_at,issuer_input))
            paths=recovery_paths(identity,intent_kind,scope) if source.source_actor else ()
            vals=(packet_id,idempotency_key_id,source.schema_id,source.digest,source.idempotency_scope_digest,source.source_intent_digest,identity,flow,kind,intent_kind,issuer_actor,verifier_actor,issuer_domain,verifier_domain,issuer_challenge,verifier_challenge,issuer_audience,verifier_audience,issuer_purpose,verifier_purpose,policy_version,issued_at,expires_at,position,predecessor,nonce,scope,issuer_input,verifier_input,"INPUT_ONLY_NOT_SIGNED",None,None,None,False,False,False,False,False,False,False,paths,position);r=ValidationPacket(*vals,canonical_digest(("PREISSUANCE_DUAL_SIGNATURE_INPUT_CONTRACT",vals)))
            if old:
                if old==r:return old
                raise GovernanceRejected("validation packet conflict")
            if by_key:
                if by_key==r:return by_key
                raise GovernanceRejected("idempotency key conflict")
            if any(x.packet_id==packet_id or x.packet_scope_digest==scope or x.nonce_scope_digest==nonce or issuer_challenge in (x.issuer_challenge,x.verifier_challenge) or verifier_challenge in (x.issuer_challenge,x.verifier_challenge) or issuer_input in (x.issuer_signature_input_digest,x.verifier_signature_input_digest) or verifier_input in (x.issuer_signature_input_digest,x.verifier_signature_input_digest) for x in self._packets.values()):raise GovernanceRejected("cross-key packet identity or input replay")
            if not self._packet_valid(r,key):raise GovernanceRejected("valid non-signing validation packet required")
            self._packets[key]=r;self._keys[idempotency_key_id]=r;self._event("PREISSUANCE_PACKET_RECORDED",r.digest)
            if source.source_actor:self._hold("DUAL_SIGNATURE_INPUT_PENDING_HUMAN_AUTHORITY",r.digest)
            return r
    def finalize(self,docket_id,compiler,validator):
        with self._lock:
            if self._docket or tuple(self._packets)!=tuple(self._source._schemas) or not self._integrity():raise GovernanceRejected("complete intact packet batch required")
            roles=self._all_source_actors()+tuple(y for x in self._packets.values() for y in (x.issuer_actor,x.verifier_actor))+(compiler,validator)
            if not _syn(compiler,"preissuance-docket-compiler") or not _syn(validator,"preissuance-docket-validator") or len({_id(x) for x in roles})!=len(roles):raise GovernanceRejected("independent packet docket roles required")
            p=dict(docket_id=docket_id,snapshot_digest=self._snapshot.digest,packet_set_digest=canonical_digest(tuple(x.digest for x in self._packets.values())),compiler=compiler,validator=validator,role_lineage_digest=canonical_digest(("COMPLETE_PREISSUANCE_ROLE_LINEAGE",self._source._docket.role_lineage_digest,roles)),**dict(final_invariants()));self._docket=Docket(**p,digest=canonical_digest(p));self._event("PREISSUANCE_DOCKET_HELD",self._docket.digest);return self._docket
    def _control_valid(self,r):
        p={k:v for k,v in r.__dict__.items() if k!="digest"};return isinstance(r.control_id,int) and not isinstance(r.control_id,bool) and 15101<=r.control_id<=15500 and self._expected(r.control_id)==(r.workstream,r.aspect) and r.requirement_ref==f"synthetic:preissuance-input-requirement:{(r.control_id-15101)//25:02}" and _hex(r.fixture_digest) and r.expected_result==("EXPECTED_REJECTION" if r.aspect in NEGATIVE else "PASS") and r.digest==canonical_digest(p)
    def _registry_valid(self):return set(self._controls)==set(range(15101,15501)) and all(self._control_valid(x) for x in self._controls.values())
    def _all_source_actors(self):
        if not self._source:return ()
        env=tuple(y for x in self._source._source._envelopes.values() for y in (x.actor,x.counter_actor) if y);roles=tuple(y for x in self._source._schemas.values() for y in (x.issuer_role,x.verifier_role));return env+roles
    def _snapshot_valid(self):
        if not self._snapshot or not self._source:return False
        s=self._snapshot;p={k:v for k,v in s.__dict__.items() if k!="digest"};e=self._source.evidence();return e["integrity_valid"] and e["complete_approval_receipt_schema_contract_evidence"] and s.snapshot_id=="synthetic:lesson-snapshot:15101-15500" and s.stage_range==(15101,15500) and s.mapping_digest==mapping_digest(STAGE_MAPPING) and all(_hex(x) for x in (s.registry_digest,s.manifest_digest)) and s.lesson_ids==APPLIED_LESSONS and s.rule_ids==APPLIED_RULES and s.source_docket_digest==self._source._docket.digest and s.previous_snapshot_digest==self._source._snapshot.digest and s.latest is True and isinstance(s.sequence,int) and not isinstance(s.sequence,bool) and s.sequence>0 and s.digest==canonical_digest(p)
    def _packet_valid(self,r,key):
        source=self._source._schemas.get(key);position=list(self._source._schemas).index(key)+1 if source else -1;pred=None if position==1 else next((x.digest for x in self._packets.values() if x.position==position-1),None)
        if not source:return False
        issued=SYNTHETIC_EPOCH+position*100;expires=issued+300;scope=canonical_digest(("PREISSUANCE_PACKET_SCOPE_V1",r.idempotency_key_id,source.digest,source.idempotency_scope_digest,source.composite_identity_digest,position,pred,r.policy_version));nonce=canonical_digest(("PREISSUANCE_PACKET_NONCE_V1",source.nonce_scope_digest,scope,position,pred));ii=canonical_digest(("ISSUER_SIGNATURE_INPUT_V1",source.digest,scope,nonce,r.issuer_actor,f"synthetic:signature-domain:issuer:{position}",r.issuer_challenge,r.issuer_audience,r.issuer_purpose,r.policy_version,issued,expires));vi=canonical_digest(("VERIFIER_SIGNATURE_INPUT_V1",source.digest,scope,nonce,r.verifier_actor,f"synthetic:signature-domain:verifier:{position}",r.verifier_challenge,r.verifier_audience,r.verifier_purpose,r.policy_version,issued,expires,ii));paths=recovery_paths(source.composite_identity_digest,r.intent_kind,scope) if source.source_actor else ();vals=(r.packet_id,r.idempotency_key_id,source.schema_id,source.digest,source.idempotency_scope_digest,source.source_intent_digest,source.composite_identity_digest,r.flow,r.kind,r.intent_kind,r.issuer_actor,r.verifier_actor,f"synthetic:signature-domain:issuer:{position}",f"synthetic:signature-domain:verifier:{position}",r.issuer_challenge,r.verifier_challenge,r.issuer_audience,r.verifier_audience,r.issuer_purpose,r.verifier_purpose,r.policy_version,issued,expires,position,pred,nonce,scope,ii,vi,"INPUT_ONLY_NOT_SIGNED",None,None,None,False,False,False,False,False,False,False,paths,position)
        occupied=self._all_source_actors()+tuple(y for k,x in self._packets.items() if k!=key for y in (x.issuer_actor,x.verifier_actor));roles=occupied+(r.issuer_actor,r.verifier_actor)
        namespaces=((r.packet_id,"preissuance-validation-packet"),(r.idempotency_key_id,"preissuance-packet-idempotency-key"),(r.issuer_actor,"preissuance-issuer"),(r.verifier_actor,"preissuance-verifier"),(r.issuer_challenge,"issuer-challenge"),(r.verifier_challenge,"verifier-challenge"),(r.issuer_audience,"issuer-audience"),(r.verifier_audience,"verifier-audience"),(r.issuer_purpose,"issuer-purpose"),(r.verifier_purpose,"verifier-purpose"),(r.policy_version,"signature-policy-version"))
        return all(_syn(v,n) for v,n in namespaces) and r.policy_version==REQUIRED_POLICY_VERSION and len({_id(x) for x in roles})==len(roles) and r.issuer_challenge!=r.verifier_challenge and r.expires_at_epoch-r.issued_at_epoch==300 and tuple(getattr(r,x) for x in ValidationPacket.__dataclass_fields__ if x!="digest")==vals and r.digest==canonical_digest(("PREISSUANCE_DUAL_SIGNATURE_INPUT_CONTRACT",vals))
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
        rows=tuple(self._packets.values());unique=(tuple(x.packet_id for x in rows),tuple(x.packet_scope_digest for x in rows),tuple(x.nonce_scope_digest for x in rows),tuple(y for x in rows for y in (x.issuer_challenge,x.verifier_challenge)),tuple(y for x in rows for y in (x.issuer_signature_input_digest,x.verifier_signature_input_digest)))
        if not self._registry_valid() or not self._snapshot_valid() or not self._chain(self._events) or not self._chain(self._holds,True) or len(self._keys)!=len(self._packets) or any(len(x)!=len(set(x)) for x in unique) or any(self._keys.get(x.idempotency_key_id)!=x for x in rows) or any(not self._packet_valid(v,k) for k,v in self._packets.items()):return False
        events=[("PREISSUANCE_CHAIN_ANCHORED",self._snapshot.digest)]+[("PREISSUANCE_PACKET_RECORDED",x.digest) for x in self._packets.values()];holds=[("DUAL_SIGNATURE_INPUT_PENDING_HUMAN_AUTHORITY",x.digest) for x in self._packets.values() if x.source_schema_digest and self._source._schemas[(x.flow,x.kind,x.intent_kind)].source_actor]
        if self._docket:events.append(("PREISSUANCE_DOCKET_HELD",self._docket.digest))
        if [(x["action"],x["artifact_digest"]) for x in self._events]!=events or [(x["reason"],x["attachment_digest"]) for x in self._holds]!=holds:return False
        if not self._docket:return True
        r=self._docket;p={k:v for k,v in r.__dict__.items() if k!="digest"};roles=self._all_source_actors()+tuple(y for x in self._packets.values() for y in (x.issuer_actor,x.verifier_actor))+(r.compiler,r.validator);return _syn(r.docket_id,"preissuance-docket") and _syn(r.compiler,"preissuance-docket-compiler") and _syn(r.validator,"preissuance-docket-validator") and len({_id(x) for x in roles})==len(roles) and r.snapshot_digest==self._snapshot.digest and r.packet_set_digest==canonical_digest(tuple(x.digest for x in self._packets.values())) and r.role_lineage_digest==canonical_digest(("COMPLETE_PREISSUANCE_ROLE_LINEAGE",self._source._docket.role_lineage_digest,roles)) and tuple((k,getattr(r,k)) for k,_ in final_invariants())==final_invariants() and r.digest==canonical_digest(p)
    def evidence(self):
        ok=self._integrity();complete=ok and self._docket is not None and len(self._packets)==40 and len(self._holds)==32;zero={k:0 for k in ("signature_values_created","signature_verifications","key_material_reads","credential_reads","approval_receipts_issued","ledger_writes","fixture_materializations","probe_executions","observation_values","external_calls","external_pg_calls","card_network_calls","payment_approvals","cancellations","refunds","settlements","transfers","deployments")};return {"range":[15101,15500],"control_count":400,"registered_control_count":len(self._controls),"validation_packet_count":len(self._packets),"dual_signature_input_count":len(self._packets)*2,"idempotency_key_contract_count":len(self._keys),"recovery_path_count":sum(len(x.recovery_paths) for x in self._packets.values()),"human_judgment_hold_count":len(self._holds),"snapshot_digest":self._snapshot.digest if self._snapshot else None,"final_docket_digest":self._docket.digest if complete else None,"integrity_valid":ok,"complete_preissuance_dual_signature_input_contract_evidence":complete,"maximum_state":"PREISSUANCE_SIGNATURE_INPUT_DOCKET_ON_HOLD" if self._docket else "PREISSUANCE_INPUT_INCOMPLETE","applied_lesson_ids":list(APPLIED_LESSONS),"applied_rule_ids":list(APPLIED_RULES),"judgment_authority":False,"recommendation_authority":False,"selection_authority":False,"acceptance_authority":False,"resolution_authority":False,"approved":False,"materialized":False,"executed":False,"observed":False,"passed":False,"failed":False,"activated":False,**zero}
