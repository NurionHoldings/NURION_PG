"""Non-issuing validation-result seal input and atomic idempotency reservation #15501-#15900."""
from dataclasses import dataclass
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest
from .synthetic_preissuance_dual_signature_input_contract import (
    APPLIED_LESSONS as PRIOR_LESSONS, APPLIED_RULES, REQUIRED_POLICY_VERSION,
    STAGE_MAPPING as PRIOR_STAGE_MAPPING, SyntheticPreissuanceDualSignatureInputContract,
)

APPLIED_LESSONS=tuple(sorted(PRIOR_LESSONS+("ARL-15501-001",)))
WORKSTREAM_NAMES=("SOURCE_PACKET_ANCHOR","STAGE_SNAPSHOT_CHAIN","RESERVATION_IDENTITY","IDEMPOTENCY_SCOPE","RESULT_SEAL_INPUT","POLICY_EXACT_GATE","DETERMINISTIC_EXPIRY","COMPOSITE_IDENTITY","DUAL_SIGNATURE_INPUT_BINDING","SEQUENCE_PREDECESSOR","NONCE_REPLAY_SCOPE","OWNER_VALIDATOR_INDEPENDENCE","ATOMIC_RESERVATION","PARALLEL_IDEMPOTENCY","RECOVERY_GUIDANCE","NON_COMMIT_NON_ISSUANCE")
WORKSTREAMS=tuple((15501+i*25,15525+i*25,n) for i,n in enumerate(WORKSTREAM_NAMES))
CONTROL_ASPECTS=("input_schema","required_fields","semantic_label","source_type","tenant_scope","role_scope","state_precondition","latest_sequence","source_binding","digest_recalculation","negative_path","missing_input","duplicate_input","replay","conflict","stale_version","concurrency","partial_batch","ordering","append_only","hold_propagation","review_independence","receipt_lineage","operator_gate","non_execution")
NEGATIVE=frozenset({"negative_path","missing_input","duplicate_input","replay","conflict","stale_version","partial_batch"})
STAGE_MAPPING=PRIOR_STAGE_MAPPING+(("ARKAON-LESSONS-15501",(15501,15900)),)
SYNTHETIC_OBSERVED_OFFSET=50

def _hex(v):return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _syn(v,k):return isinstance(v,str) and v.startswith(f"synthetic:{k}:")
def _id(v):return v.rsplit(":",1)[-1].casefold()
def mapping_digest(rows):return canonical_digest(("CONTIGUOUS_STAGE_MAPPING",tuple(rows)))

@dataclass(frozen=True)
class Control:control_id:int;workstream:str;aspect:str;requirement_ref:str;fixture_digest:str;expected_result:str;digest:str
@dataclass(frozen=True)
class Snapshot:snapshot_id:str;stage_range:tuple;mapping_digest:str;registry_digest:str;manifest_digest:str;lesson_ids:tuple;rule_ids:tuple;source_docket_digest:str;previous_snapshot_digest:str;sequence:int;latest:bool;digest:str
@dataclass(frozen=True)
class Reservation:
    reservation_id:str;idempotency_key_id:str;reservation_token_id:str;source_packet_id:str;source_packet_digest:str;source_packet_scope_digest:str;source_idempotency_scope_digest:str;source_intent_digest:str;composite_identity_digest:str;issuer_signature_input_digest:str;verifier_signature_input_digest:str;policy_version:str;flow:str;kind:str;intent_kind:str;owner_actor:str;validator_actor:str;observed_epoch:int;expires_at_epoch:int;sequence:int;predecessor_reservation_digest:str|None;reservation_scope_digest:str;nonce_scope_digest:str;result_candidate_digest:str;seal_input_digest:str;state:str;committed:bool;receipt_id:str|None;receipt_digest:str|None;signature_value:str|None;signature_verified:bool;materialized:bool;executed:bool;observed:bool;passed:bool;failed:bool;recovery_paths:tuple;position:int;digest:str
@dataclass(frozen=True)
class Docket:docket_id:str;snapshot_digest:str;reservation_set_digest:str;compiler:str;final_validator:str;role_lineage_digest:str;complete:bool;held:bool;pending_human_judgment:bool;committed:bool;receipt_issued:bool;signature_created:bool;signature_verified:bool;materialized:bool;executed:bool;observed:bool;passed:bool;failed:bool;approved:bool;activated:bool;deployed:bool;status:str;digest:str

def recovery_paths(identity,scope,packet):
    return (("REBUILD_UNEXPIRED_RESERVATION",("cause","reservation_binding_replay_or_expiry"),("recommended",True),("cost","LOW"),("risk","LOW"),("reversibility","HIGH"),("validation","rederive_from_intact_v1_packet_at_synthetic_epoch"),("stop","packet_policy_actor_or_expiry_invalid"),("resume","fresh_key_token_scope_after_independent_validation"),("rollback","discard_uncommitted_reservation_preserve_packet"),identity,scope,packet),("RECONSTRUCT_ORDERED_RESERVATION_BATCH",("cause","predecessor_nonce_owner_or_validator_ambiguity"),("recommended",False),("cost","MEDIUM"),("risk","LOW"),("reversibility","HIGH"),("validation","rebuild_in_canonical_packet_order"),("stop","any_source_packet_unverified_or_expired"),("resume","new_distinct_actor_slots_and_tokens"),("rollback","quarantine_batch_preserve_preissuance_docket"),identity,scope,packet))
def final_invariants():return (("complete",True),("held",True),("pending_human_judgment",True),("committed",False),("receipt_issued",False),("signature_created",False),("signature_verified",False),("materialized",False),("executed",False),("observed",False),("passed",False),("failed",False),("approved",False),("activated",False),("deployed",False),("status","RESERVATION_DOCKET_ON_HOLD_NOT_COMMITTED_NOT_ISSUED"))

class SyntheticNonissuanceResultSealReservation:
    def __init__(self):self._controls={};self._source=None;self._snapshot=None;self._reservations={};self._keys={};self._tokens={};self._docket=None;self._events=[];self._holds=[];self._lock=RLock()
    def _expected(self,cid):i=cid-15501;return WORKSTREAM_NAMES[i//25],CONTROL_ASPECTS[i%25]
    def add_control(self,cid,workstream,aspect,requirement_ref,fixture_digest,expected_result):
        p=dict(control_id=cid,workstream=workstream,aspect=aspect,requirement_ref=requirement_ref,fixture_digest=fixture_digest,expected_result=expected_result);r=Control(**p,digest=canonical_digest(p))
        with self._lock:
            if not self._control_valid(r):raise GovernanceRejected("valid #15501-#15900 control required")
            old=self._controls.get(cid)
            if old:
                if old==r:return old
                raise GovernanceRejected("control conflict")
            self._controls[cid]=r;return r
    def anchor(self,source,mapping,registry,manifest,lessons,rules,previous_snapshot,sequence,latest):
        if not isinstance(source,SyntheticPreissuanceDualSignatureInputContract):raise GovernanceRejected("prior preissuance contract required")
        e=source.evidence();p=dict(snapshot_id="synthetic:lesson-snapshot:15501-15900",stage_range=(15501,15900),mapping_digest=mapping,registry_digest=registry,manifest_digest=manifest,lesson_ids=tuple(lessons),rule_ids=tuple(rules),source_docket_digest=source._docket.digest if source._docket else None,previous_snapshot_digest=previous_snapshot,sequence=sequence,latest=latest);r=Snapshot(**p,digest=canonical_digest(p))
        with self._lock:
            if not(self._registry_valid() and e["complete_preissuance_dual_signature_input_contract_evidence"] and e["integrity_valid"] and mapping==mapping_digest(STAGE_MAPPING) and _hex(registry) and _hex(manifest) and tuple(lessons)==APPLIED_LESSONS and tuple(rules)==APPLIED_RULES and previous_snapshot==source._snapshot.digest and isinstance(sequence,int) and not isinstance(sequence,bool) and sequence>0 and latest is True):raise GovernanceRejected("complete latest reservation snapshot required")
            if self._snapshot:
                if self._source is source and self._snapshot==r:return r
                raise GovernanceRejected("snapshot conflict")
            self._source=source;self._snapshot=r;self._event("RESERVATION_CHAIN_ANCHORED",r.digest);return r
    def reserve(self,reservation_id,idempotency_key_id,reservation_token_id,flow,kind,intent_kind,owner_actor,validator_actor,observed_epoch=None):
        with self._lock:
            key=(flow,kind,intent_kind);source=self._source._packets.get(key) if self._source else None;position=list(self._source._packets).index(key)+1 if source else -1;old=self._reservations.get(key);by_key=self._keys.get(idempotency_key_id);by_token=self._tokens.get(reservation_token_id)
            if not source or position<1:raise GovernanceRejected("source packet required")
            if observed_epoch is None:observed_epoch=source.issued_at_epoch+SYNTHETIC_OBSERVED_OFFSET
            if not all((_syn(reservation_id,"nonissuance-reservation"),_syn(idempotency_key_id,"reservation-idempotency-key"),_syn(reservation_token_id,"reservation-token"),_syn(owner_actor,"reservation-owner"),_syn(validator_actor,"reservation-validator"))):raise GovernanceRejected("complete synthetic reservation inputs required")
            if source.policy_version!=REQUIRED_POLICY_VERSION:raise GovernanceRejected("required signature policy version only")
            if not isinstance(observed_epoch,int) or isinstance(observed_epoch,bool) or not source.issued_at_epoch<=observed_epoch<=source.expires_at_epoch:raise GovernanceRejected("in-window deterministic reservation epoch required")
            if _id(owner_actor)==_id(validator_actor):raise GovernanceRejected("independent reservation actors required")
            occupied=self._all_prior_actors()+tuple(y for k,x in self._reservations.items() if k!=key for y in (x.owner_actor,x.validator_actor))
            if len({_id(x) for x in occupied+(owner_actor,validator_actor)})!=len(occupied)+2:raise GovernanceRejected("global actor identity collision")
            predecessor=None if position==1 else next((x.digest for x in self._reservations.values() if x.position==position-1),None)
            if position>1 and predecessor is None:raise GovernanceRejected("ordered reservation predecessor required")
            scope=canonical_digest(("ATOMIC_RESERVATION_SCOPE_V1",idempotency_key_id,reservation_token_id,source.digest,source.packet_scope_digest,source.source_idempotency_scope_digest,source.composite_identity_digest,source.issuer_signature_input_digest,source.verifier_signature_input_digest,source.policy_version,position,predecessor,owner_actor,validator_actor))
            nonce=canonical_digest(("RESERVATION_NONCE_V1",source.nonce_scope_digest,scope,position,predecessor))
            candidate=canonical_digest(("NONISSUING_VALIDATION_RESULT_CANDIDATE_V1",source.digest,source.issuer_signature_input_digest,source.verifier_signature_input_digest,source.policy_version,"NOT_CRYPTOGRAPHICALLY_VERIFIED"))
            seal=canonical_digest(("NONISSUANCE_RESULT_SEAL_INPUT_V1",candidate,scope,nonce,owner_actor,validator_actor,observed_epoch,source.expires_at_epoch))
            paths=recovery_paths(source.composite_identity_digest,scope,source.digest) if self._source._source._schemas[key].source_actor else ()
            vals=(reservation_id,idempotency_key_id,reservation_token_id,source.packet_id,source.digest,source.packet_scope_digest,source.source_idempotency_scope_digest,source.source_intent_digest,source.composite_identity_digest,source.issuer_signature_input_digest,source.verifier_signature_input_digest,source.policy_version,flow,kind,intent_kind,owner_actor,validator_actor,observed_epoch,source.expires_at_epoch,position,predecessor,scope,nonce,candidate,seal,"RESERVED_NOT_COMMITTED_NOT_ISSUED",False,None,None,None,False,False,False,False,False,False,paths,position);r=Reservation(*vals,canonical_digest(("NONISSUANCE_RESULT_SEAL_RESERVATION_V1",vals)))
            if old:
                if old==r:return old
                raise GovernanceRejected("reservation conflict")
            if by_key:
                if by_key==r:return by_key
                raise GovernanceRejected("idempotency key conflict")
            if by_token:
                if by_token==r:return by_token
                raise GovernanceRejected("reservation token conflict")
            if any(x.reservation_id==reservation_id or x.reservation_scope_digest==scope or x.nonce_scope_digest==nonce or x.result_candidate_digest==candidate or x.seal_input_digest==seal for x in self._reservations.values()):raise GovernanceRejected("cross-key reservation identity or scope replay")
            if not self._reservation_valid(r,key):raise GovernanceRejected("valid non-issuing reservation required")
            self._reservations[key]=r;self._keys[idempotency_key_id]=r;self._tokens[reservation_token_id]=r;self._event("ATOMIC_RESERVATION_RECORDED",r.digest)
            if paths:self._hold("RESERVATION_PENDING_HUMAN_AUTHORITY",r.digest)
            return r
    def finalize(self,docket_id,compiler,final_validator):
        with self._lock:
            if self._docket or tuple(self._reservations)!=tuple(self._source._packets) or not self._integrity():raise GovernanceRejected("complete intact reservation batch required")
            roles=self._all_prior_actors()+tuple(y for x in self._reservations.values() for y in (x.owner_actor,x.validator_actor))+(compiler,final_validator)
            if not _syn(docket_id,"reservation-docket") or not _syn(compiler,"reservation-docket-compiler") or not _syn(final_validator,"reservation-final-validator") or len({_id(x) for x in roles})!=len(roles):raise GovernanceRejected("independent reservation docket roles required")
            p=dict(docket_id=docket_id,snapshot_digest=self._snapshot.digest,reservation_set_digest=canonical_digest(tuple(x.digest for x in self._reservations.values())),compiler=compiler,final_validator=final_validator,role_lineage_digest=canonical_digest(("COMPLETE_RESERVATION_ROLE_LINEAGE",self._source._docket.role_lineage_digest,roles)),**dict(final_invariants()));self._docket=Docket(**p,digest=canonical_digest(p));self._event("RESERVATION_DOCKET_HELD",self._docket.digest);return self._docket
    def _control_valid(self,r):p={k:v for k,v in r.__dict__.items() if k!="digest"};return isinstance(r.control_id,int) and not isinstance(r.control_id,bool) and 15501<=r.control_id<=15900 and self._expected(r.control_id)==(r.workstream,r.aspect) and r.requirement_ref==f"synthetic:reservation-requirement:{(r.control_id-15501)//25:02}" and _hex(r.fixture_digest) and r.expected_result==("EXPECTED_REJECTION" if r.aspect in NEGATIVE else "PASS") and r.digest==canonical_digest(p)
    def _registry_valid(self):return set(self._controls)==set(range(15501,15901)) and all(self._control_valid(x) for x in self._controls.values())
    def _all_prior_actors(self):
        if not self._source:return ()
        base=self._source._all_source_actors();packets=tuple(y for x in self._source._packets.values() for y in (x.issuer_actor,x.verifier_actor));return base+packets
    def _snapshot_valid(self):
        if not self._snapshot or not self._source:return False
        s=self._snapshot;p={k:v for k,v in s.__dict__.items() if k!="digest"};e=self._source.evidence();return e["integrity_valid"] and e["complete_preissuance_dual_signature_input_contract_evidence"] and s.snapshot_id=="synthetic:lesson-snapshot:15501-15900" and s.stage_range==(15501,15900) and s.mapping_digest==mapping_digest(STAGE_MAPPING) and all(_hex(x) for x in (s.registry_digest,s.manifest_digest)) and s.lesson_ids==APPLIED_LESSONS and s.rule_ids==APPLIED_RULES and s.source_docket_digest==self._source._docket.digest and s.previous_snapshot_digest==self._source._snapshot.digest and s.latest is True and isinstance(s.sequence,int) and not isinstance(s.sequence,bool) and s.sequence>0 and s.digest==canonical_digest(p)
    def _reservation_valid(self,r,key):
        source=self._source._packets.get(key);position=list(self._source._packets).index(key)+1 if source else -1;pred=None if position==1 else next((x.digest for x in self._reservations.values() if x.position==position-1),None)
        if not source or not isinstance(r.observed_epoch,int) or isinstance(r.observed_epoch,bool) or not source.issued_at_epoch<=r.observed_epoch<=source.expires_at_epoch:return False
        scope=canonical_digest(("ATOMIC_RESERVATION_SCOPE_V1",r.idempotency_key_id,r.reservation_token_id,source.digest,source.packet_scope_digest,source.source_idempotency_scope_digest,source.composite_identity_digest,source.issuer_signature_input_digest,source.verifier_signature_input_digest,source.policy_version,position,pred,r.owner_actor,r.validator_actor));nonce=canonical_digest(("RESERVATION_NONCE_V1",source.nonce_scope_digest,scope,position,pred));candidate=canonical_digest(("NONISSUING_VALIDATION_RESULT_CANDIDATE_V1",source.digest,source.issuer_signature_input_digest,source.verifier_signature_input_digest,source.policy_version,"NOT_CRYPTOGRAPHICALLY_VERIFIED"));seal=canonical_digest(("NONISSUANCE_RESULT_SEAL_INPUT_V1",candidate,scope,nonce,r.owner_actor,r.validator_actor,r.observed_epoch,source.expires_at_epoch));paths=recovery_paths(source.composite_identity_digest,scope,source.digest) if self._source._source._schemas[key].source_actor else ();vals=(r.reservation_id,r.idempotency_key_id,r.reservation_token_id,source.packet_id,source.digest,source.packet_scope_digest,source.source_idempotency_scope_digest,source.source_intent_digest,source.composite_identity_digest,source.issuer_signature_input_digest,source.verifier_signature_input_digest,source.policy_version,r.flow,r.kind,r.intent_kind,r.owner_actor,r.validator_actor,r.observed_epoch,source.expires_at_epoch,position,pred,scope,nonce,candidate,seal,"RESERVED_NOT_COMMITTED_NOT_ISSUED",False,None,None,None,False,False,False,False,False,False,paths,position)
        occupied=self._all_prior_actors()+tuple(y for k,x in self._reservations.items() if k!=key for y in (x.owner_actor,x.validator_actor));roles=occupied+(r.owner_actor,r.validator_actor)
        return all((_syn(r.reservation_id,"nonissuance-reservation"),_syn(r.idempotency_key_id,"reservation-idempotency-key"),_syn(r.reservation_token_id,"reservation-token"),_syn(r.owner_actor,"reservation-owner"),_syn(r.validator_actor,"reservation-validator"))) and source.policy_version==REQUIRED_POLICY_VERSION and len({_id(x) for x in roles})==len(roles) and tuple(getattr(r,x) for x in Reservation.__dataclass_fields__ if x!="digest")==vals and r.digest==canonical_digest(("NONISSUANCE_RESULT_SEAL_RESERVATION_V1",vals))
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
        rows=tuple(self._reservations.values());unique=(tuple(x.reservation_id for x in rows),tuple(x.idempotency_key_id for x in rows),tuple(x.reservation_token_id for x in rows),tuple(x.reservation_scope_digest for x in rows),tuple(x.nonce_scope_digest for x in rows),tuple(x.result_candidate_digest for x in rows),tuple(x.seal_input_digest for x in rows))
        if not self._registry_valid() or not self._snapshot_valid() or not self._chain(self._events) or not self._chain(self._holds,True) or len(self._keys)!=len(rows) or len(self._tokens)!=len(rows) or any(len(x)!=len(set(x)) for x in unique) or any(self._keys.get(x.idempotency_key_id)!=x or self._tokens.get(x.reservation_token_id)!=x for x in rows) or any(not self._reservation_valid(v,k) for k,v in self._reservations.items()):return False
        events=[("RESERVATION_CHAIN_ANCHORED",self._snapshot.digest)]+[("ATOMIC_RESERVATION_RECORDED",x.digest) for x in rows];holds=[("RESERVATION_PENDING_HUMAN_AUTHORITY",x.digest) for x in rows if x.recovery_paths]
        if self._docket:events.append(("RESERVATION_DOCKET_HELD",self._docket.digest))
        if [(x["action"],x["artifact_digest"]) for x in self._events]!=events or [(x["reason"],x["attachment_digest"]) for x in self._holds]!=holds:return False
        if not self._docket:return True
        r=self._docket;p={k:v for k,v in r.__dict__.items() if k!="digest"};roles=self._all_prior_actors()+tuple(y for x in rows for y in (x.owner_actor,x.validator_actor))+(r.compiler,r.final_validator);return _syn(r.docket_id,"reservation-docket") and _syn(r.compiler,"reservation-docket-compiler") and _syn(r.final_validator,"reservation-final-validator") and len({_id(x) for x in roles})==len(roles) and r.snapshot_digest==self._snapshot.digest and r.reservation_set_digest==canonical_digest(tuple(x.digest for x in rows)) and r.role_lineage_digest==canonical_digest(("COMPLETE_RESERVATION_ROLE_LINEAGE",self._source._docket.role_lineage_digest,roles)) and tuple((k,getattr(r,k)) for k,_ in final_invariants())==final_invariants() and r.digest==canonical_digest(p)
    def evidence(self):
        ok=self._integrity();complete=ok and self._docket is not None and len(self._reservations)==40 and len(self._holds)==32;zero={k:0 for k in ("cryptographic_verifications","signature_values_created","key_material_reads","credential_reads","reservation_commits","approval_receipts_issued","ledger_writes","database_writes","fixture_materializations","probe_executions","observation_values","external_calls","external_pg_calls","card_network_calls","payment_approvals","cancellations","refunds","settlements","transfers","deployments")};return {"range":[15501,15900],"control_count":400,"registered_control_count":len(self._controls),"reservation_count":len(self._reservations),"result_candidate_count":len(self._reservations),"seal_input_count":len(self._reservations),"recovery_path_count":sum(len(x.recovery_paths) for x in self._reservations.values()),"human_judgment_hold_count":len(self._holds),"snapshot_digest":self._snapshot.digest if self._snapshot else None,"final_docket_digest":self._docket.digest if complete else None,"integrity_valid":ok,"complete_nonissuance_result_seal_reservation_evidence":complete,"maximum_state":"RESERVATION_DOCKET_ON_HOLD_NOT_COMMITTED_NOT_ISSUED" if self._docket else "RESERVATION_INCOMPLETE","applied_lesson_ids":list(APPLIED_LESSONS),"applied_rule_ids":list(APPLIED_RULES),"judgment_authority":False,"recommendation_authority":False,"selection_authority":False,"acceptance_authority":False,"resolution_authority":False,"approved":False,"materialized":False,"executed":False,"observed":False,"passed":False,"failed":False,"activated":False,**zero}
