"""Synthetic/in-memory cross-party answer reconciliation controls #7901-#8300."""
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest

WORKSTREAM_NAMES = (
    "ANSWER_PACKET_SOURCE_ANCHOR", "LESSON_RULE_REGISTRY_BINDING", "TENANT_PROVENANCE",
    "NURION_PROVENANCE", "UPSTREAM_PROVENANCE", "FOUR_DIRECTION_PAIRING",
    "QUESTION_CLAIM_CROSS_CHECK", "MANIFEST_CROSS_CHECK", "RECEIPT_CROSS_CHECK",
    "VERSION_CONFLICT_DETECTION", "MISMATCH_CLASSIFICATION", "HUMAN_RECONCILIATION_QUEUE",
    "REVIEWER_COMPILER_CHAIR_VALIDATOR_LINEAGE", "APPEND_ONLY_CASE_HOLD",
    "INDEPENDENT_RECONCILIATION_VALIDATION", "NON_ACCEPTANCE_NON_EXECUTION_BOUNDARY",
)
WORKSTREAMS = tuple((7901+i*25, 7925+i*25, n) for i, n in enumerate(WORKSTREAM_NAMES))
CONTROL_ASPECTS = (
    "input_schema", "required_fields", "semantic_label", "source_type", "tenant_scope", "role_scope",
    "state_precondition", "latest_sequence", "source_binding", "digest_recalculation", "negative_path",
    "missing_input", "duplicate_input", "replay", "conflict", "stale_version", "concurrency",
    "partial_batch", "ordering", "append_only", "hold_propagation", "review_independence",
    "receipt_lineage", "operator_gate", "non_execution",
)
NEGATIVE = frozenset({"negative_path", "missing_input", "duplicate_input", "replay", "conflict", "stale_version", "partial_batch"})
PARTIES = ("TENANT_AGENCY", "NURION_PG", "UPSTREAM_PG")
FLOWS = ("tenant_to_nurion", "nurion_to_upstream", "upstream_to_nurion", "nurion_to_tenant")
FLOW_PARTIES = {"tenant_to_nurion": ("TENANT_AGENCY", "NURION_PG"), "nurion_to_upstream": ("NURION_PG", "UPSTREAM_PG"), "upstream_to_nurion": ("UPSTREAM_PG", "NURION_PG"), "nurion_to_tenant": ("NURION_PG", "TENANT_AGENCY")}
COUNTER_FLOW = {"tenant_to_nurion":"nurion_to_tenant", "nurion_to_tenant":"tenant_to_nurion", "nurion_to_upstream":"upstream_to_nurion", "upstream_to_nurion":"nurion_to_upstream"}
ANSWER_KINDS = ("ASSUMPTION_RESPONSE", "RESIDUAL_RISK_RESPONSE", "ADDITIONAL_EVIDENCE", "MEANING_CLARIFICATION", "SAFE_BOUNDARY_ACKNOWLEDGEMENT")
COMPARISON_OUTCOMES = ("CONSISTENT", "CLAIM_CONFLICT", "MANIFEST_CONFLICT", "RECEIPT_CONFLICT", "VERSION_CONFLICT")
APPLIED_LESSONS = ("ARL-3901-001", "ARL-4301-001", "ARL-4301-002", "ARL-4301-003", "ARL-4701-001", "ARL-5101-001", "ARL-5501-001", "ARL-5901-001", "ARL-6301-001", "ARL-6701-001", "ARL-7101-001", "ARL-7501-001", "ARL-7901-001")
APPLIED_RULES = tuple(f"ARP-{i:02}" for i in range(1, 9))

def _syn(v, kind): return isinstance(v, str) and v.startswith(f"synthetic:{kind}:")
def _hex(v): return isinstance(v, str) and len(v) == 64 and all(c in "0123456789abcdef" for c in v)
def _identity(v): return v.rsplit(":", 1)[-1].casefold()
def comparison_outcome(source, counterpart):
    """Derive the first material discrepancy from the two anchored records."""
    if source is None or counterpart is None: return None
    if source.claim_digest != counterpart.claim_digest: return "CLAIM_CONFLICT"
    if source.manifest_digest != counterpart.manifest_digest: return "MANIFEST_CONFLICT"
    if source.receipt_digest != counterpart.receipt_digest: return "RECEIPT_CONFLICT"
    if source.version != counterpart.version: return "VERSION_CONFLICT"
    return "CONSISTENT"
def _anchor_digest_payload(p):
    """Convert nested immutable provenance records to a canonical JSON shape."""
    q=dict(p)
    q["answer_provenance"]=tuple(tuple(x.__dict__.values()) for x in q["answer_provenance"])
    return q

@dataclass(frozen=True)
class Control:
    control_id: int; workstream: str; aspect: str; requirement_ref: str; fixture_digest: str; expected_result: str; digest: str

@dataclass(frozen=True)
class AnswerProvenance:
    flow: str; answer_kind: str; source_party: str; counterparty: str; answer_digest: str; claim_digest: str
    manifest_digest: str; receipt_digest: str; version: int; binding_digest: str

@dataclass(frozen=True)
class IntakePacketAnchor:
    anchor_id: str; intake_packet_digest: str; answer_set_digest: str; lesson_registry_digest: str
    remediation_manifest_digest: str; applied_lesson_ids: tuple[str,...]; applied_rule_ids: tuple[str,...]
    answer_provenance: tuple[AnswerProvenance,...]; source_sequence: int; is_latest: bool
    source_reviewers: tuple[str,str,str]; source_compilers: tuple[str,str,str]; source_chair: str
    source_validator: str; source_lineage_digest: str; status: str; digest: str

@dataclass(frozen=True)
class ReconciliationCase:
    case_id: str; flow: str; answer_kind: str; comparison_outcome: str; counterpart_flow: str; anchor_digest: str
    source_binding_digest: str; counterpart_binding_digest: str; comparison_digest: str
    queue_route_digest: str; submitter: str; cross_validator: str; complete: bool; human_review_required: bool
    status: str; digest: str

@dataclass(frozen=True)
class ReconciliationQueuePacket:
    packet_id: str; anchor_digest: str; case_set_digest: str; queue_compiler: str; cross_validator: str
    source_reviewers: tuple[str,str,str]; source_compilers: tuple[str,str,str]; source_chair: str
    source_validator: str; source_lineage_digest: str; complete: bool; accepted: bool; reconciled: bool
    recommended: bool; decided: bool; approved: bool; activated: bool; deployed: bool; status: str; digest: str

class SyntheticCrossPartyAnswerReconciliation:
    """Builds an inert human reconciliation queue; it cannot accept or decide answers."""
    def __init__(self):
        self._controls={}; self._anchor=None; self._cases={}; self._packet=None; self._events=[]; self._holds=[]; self._lock=RLock()

    def _expected(self,cid):
        i=cid-7901; return WORKSTREAM_NAMES[i//25],CONTROL_ASPECTS[i%25]

    def add_control(self,cid,workstream,aspect,requirement_ref,fixture_digest,expected_result):
        p=dict(control_id=cid,workstream=workstream,aspect=aspect,requirement_ref=requirement_ref,fixture_digest=fixture_digest,expected_result=expected_result); r=Control(**p,digest=canonical_digest(p))
        with self._lock:
            if not self._valid_control(r): raise GovernanceRejected("valid #7901-#8300 control required")
            old=self._controls.get(cid)
            if old:
                if old==r:return old
                raise GovernanceRejected("control conflict")
            self._controls[cid]=r; return r

    def anchor_source(self,anchor_id,intake_packet_digest,answer_set_digest,lesson_registry_digest,
                      remediation_manifest_digest,applied_lesson_ids,applied_rule_ids,answer_provenance,
                      source_sequence,is_latest,source_reviewers,source_compilers,source_chair,source_validator):
        provenance=tuple(answer_provenance); reviewers=tuple(source_reviewers); compilers=tuple(source_compilers)
        lineage=canonical_digest(("ANSWER_INTAKE_FULL_LINEAGE",intake_packet_digest,answer_set_digest,reviewers,compilers,source_chair,source_validator))
        p=dict(anchor_id=anchor_id,intake_packet_digest=intake_packet_digest,answer_set_digest=answer_set_digest,
               lesson_registry_digest=lesson_registry_digest,remediation_manifest_digest=remediation_manifest_digest,
               applied_lesson_ids=tuple(applied_lesson_ids),applied_rule_ids=tuple(applied_rule_ids),answer_provenance=provenance,
               source_sequence=source_sequence,is_latest=is_latest,source_reviewers=reviewers,source_compilers=compilers,
               source_chair=source_chair,source_validator=source_validator,source_lineage_digest=lineage,
               status="ANSWER_INTAKE_ANCHORED_NOT_ACCEPTED_NOT_DECIDED")
        r=IntakePacketAnchor(**p,digest=canonical_digest(_anchor_digest_payload(p)))
        with self._lock:
            if not self._anchor_valid(r): raise GovernanceRejected("latest complete intake packet lineage required")
            if self._anchor:
                if self._anchor==r:return self._anchor
                raise GovernanceRejected("anchor conflict")
            self._anchor=r; self._event("ANSWER_INTAKE_ANCHORED",r.digest); return r

    def add_case(self,case_id,flow,answer_kind,submitter,cross_validator):
        with self._lock:
            if not self._anchor: raise GovernanceRejected("intake anchor required")
            source,counter=FLOW_PARTIES.get(flow,(None,None)); counterpart=COUNTER_FLOW.get(flow)
            rows={(x.flow,x.answer_kind):x for x in self._anchor.answer_provenance}
            src=rows.get((flow,answer_kind)); other=rows.get((counterpart,answer_kind)); outcome=comparison_outcome(src,other)
            comparison=canonical_digest(("CROSS_PARTY_COMPARISON",flow,counterpart,answer_kind,outcome,src.binding_digest if src else None,other.binding_digest if other else None))
            route=canonical_digest(("HUMAN_RECONCILIATION_QUEUE",flow,counterpart,answer_kind,outcome,comparison,source,counter))
            p=dict(case_id=case_id,flow=flow,answer_kind=answer_kind,comparison_outcome=outcome,counterpart_flow=counterpart,anchor_digest=self._anchor.digest,
                   source_binding_digest=src.binding_digest if src else None,counterpart_binding_digest=other.binding_digest if other else None,
                   comparison_digest=comparison,queue_route_digest=route,submitter=submitter,cross_validator=cross_validator,
                   complete=True,human_review_required=True,status="HELD_FOR_HUMAN_RECONCILIATION_NOT_ACCEPTED_NOT_DECIDED")
            r=ReconciliationCase(**p,digest=canonical_digest(p)); key=(flow,answer_kind)
            if not self._case_valid(r,key): raise GovernanceRejected("complete synthetic reconciliation case required")
            old=self._cases.get(key)
            if old:
                if old==r:return old
                raise GovernanceRejected("reconciliation case conflict")
            self._cases[key]=r; self._event("RECONCILIATION_CASE_RECORDED",r.digest); self._hold("HUMAN_RECONCILIATION_REQUIRED",r.digest); return r

    def finalize(self,packet_id,queue_compiler):
        with self._lock:
            expected={(f,k) for f in FLOWS for k in ANSWER_KINDS}
            if self._packet or set(self._cases)!=expected or not self._integrity(): raise GovernanceRejected("exact intact reconciliation case set required")
            if not _syn(packet_id,"reconciliation-queue-packet") or not _syn(queue_compiler,"reconciliation-queue-compiler"): raise GovernanceRejected("synthetic queue compiler required")
            occupied=self._source_roles()+tuple(x.submitter for x in self._cases.values())+tuple(x.cross_validator for x in self._cases.values())
            if _identity(queue_compiler) in {_identity(x) for x in occupied}: raise GovernanceRejected("independent queue compiler required")
            validators={x.cross_validator for x in self._cases.values()}
            if len(validators)!=1: raise GovernanceRejected("single independent cross-validator required")
            validator=next(iter(validators)); cset=canonical_digest(tuple(self._cases[k].digest for k in sorted(self._cases)))
            p=dict(packet_id=packet_id,anchor_digest=self._anchor.digest,case_set_digest=cset,queue_compiler=queue_compiler,cross_validator=validator,
                   source_reviewers=self._anchor.source_reviewers,source_compilers=self._anchor.source_compilers,source_chair=self._anchor.source_chair,
                   source_validator=self._anchor.source_validator,source_lineage_digest=self._anchor.source_lineage_digest,complete=True,
                   accepted=False,reconciled=False,recommended=False,decided=False,approved=False,activated=False,deployed=False,
                   status="HUMAN_RECONCILIATION_QUEUE_READY_NOT_ACCEPTED_NOT_DECIDED")
            self._packet=ReconciliationQueuePacket(**p,digest=canonical_digest(p)); self._event("RECONCILIATION_QUEUE_PACKET_RECORDED",self._packet.digest); return self._packet

    def _valid_control(self,r):
        p={k:v for k,v in r.__dict__.items() if k!="digest"}
        return isinstance(r.control_id,int) and not isinstance(r.control_id,bool) and 7901<=r.control_id<=8300 and self._expected(r.control_id)==(r.workstream,r.aspect) and r.requirement_ref==f"synthetic:reconciliation-requirement:{(r.control_id-7901)//25:02}" and _hex(r.fixture_digest) and r.expected_result==("EXPECTED_REJECTION" if r.aspect in NEGATIVE else "PASS") and r.digest==canonical_digest(p)

    def _registry_valid(self): return set(self._controls)==set(range(7901,8301)) and all(k==v.control_id and self._valid_control(v) for k,v in self._controls.items())

    def _source_roles(self): return self._anchor.source_reviewers+self._anchor.source_compilers+(self._anchor.source_chair,self._anchor.source_validator)

    @staticmethod
    def _provenance_valid(x):
        source,counter=FLOW_PARTIES.get(x.flow,(None,None)); p=("ANSWER_PROVENANCE",x.flow,x.answer_kind,source,counter,x.answer_digest,x.claim_digest,x.manifest_digest,x.receipt_digest,x.version)
        return x.answer_kind in ANSWER_KINDS and (x.source_party,x.counterparty)==(source,counter) and all(_hex(v) for v in (x.answer_digest,x.claim_digest,x.manifest_digest,x.receipt_digest)) and isinstance(x.version,int) and not isinstance(x.version,bool) and x.version>0 and x.binding_digest==canonical_digest(p)

    def _anchor_valid(self,a):
        p={k:v for k,v in a.__dict__.items() if k!="digest"}; roles=a.source_reviewers+a.source_compilers+(a.source_chair,a.source_validator)
        keys=tuple((x.flow,x.answer_kind) for x in a.answer_provenance)
        return self._registry_valid() and _syn(a.anchor_id,"reconciliation-anchor") and all(_hex(x) for x in (a.intake_packet_digest,a.answer_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest)) and a.applied_lesson_ids==APPLIED_LESSONS and a.applied_rule_ids==APPLIED_RULES and keys==tuple((f,k) for f in FLOWS for k in ANSWER_KINDS) and all(self._provenance_valid(x) for x in a.answer_provenance) and isinstance(a.source_sequence,int) and not isinstance(a.source_sequence,bool) and a.source_sequence>0 and a.is_latest is True and len(a.source_reviewers)==3 and all(_syn(x,k) for x,k in zip(a.source_reviewers,("readiness-reviewer","preflight-reviewer","reconsideration-reviewer"))) and len(a.source_compilers)==3 and all(_syn(x,"packet-compiler") for x in a.source_compilers) and _syn(a.source_chair,"human-deliberation-chair") and _syn(a.source_validator,"intake-validator") and len({_identity(x) for x in roles})==8 and a.source_lineage_digest==canonical_digest(("ANSWER_INTAKE_FULL_LINEAGE",a.intake_packet_digest,a.answer_set_digest,a.source_reviewers,a.source_compilers,a.source_chair,a.source_validator)) and a.status=="ANSWER_INTAKE_ANCHORED_NOT_ACCEPTED_NOT_DECIDED" and a.digest==canonical_digest(_anchor_digest_payload(p))

    def _case_valid(self,r,key):
        if not self._anchor:return False
        rows={(x.flow,x.answer_kind):x for x in self._anchor.answer_provenance}; counterpart=COUNTER_FLOW.get(r.flow); src=rows.get((r.flow,r.answer_kind)); other=rows.get((counterpart,r.answer_kind)); source,counter=FLOW_PARTIES.get(r.flow,(None,None)); outcome=comparison_outcome(src,other)
        comparison=canonical_digest(("CROSS_PARTY_COMPARISON",r.flow,counterpart,r.answer_kind,outcome,src.binding_digest if src else None,other.binding_digest if other else None)); route=canonical_digest(("HUMAN_RECONCILIATION_QUEUE",r.flow,counterpart,r.answer_kind,outcome,comparison,source,counter)); p={k:v for k,v in r.__dict__.items() if k!="digest"}
        occupied=self._source_roles()
        return key==(r.flow,r.answer_kind) and r.flow in FLOWS and r.answer_kind in ANSWER_KINDS and r.comparison_outcome==outcome and _syn(r.case_id,"reconciliation-case") and r.counterpart_flow==counterpart and r.anchor_digest==self._anchor.digest and src is not None and other is not None and r.source_binding_digest==src.binding_digest and r.counterpart_binding_digest==other.binding_digest and r.comparison_digest==comparison and r.queue_route_digest==route and r.submitter==f"synthetic:reconciliation-submitter:{source}" and _syn(r.cross_validator,"cross-party-validator") and len({_identity(x) for x in occupied+(r.submitter,r.cross_validator)})==len(occupied)+2 and r.complete is True and r.human_review_required is True and r.status=="HELD_FOR_HUMAN_RECONCILIATION_NOT_ACCEPTED_NOT_DECIDED" and r.digest==canonical_digest(p)

    def _event(self,action,artifact):
        prev=self._events[-1]["digest"] if self._events else None; p=dict(sequence=len(self._events)+1,action=action,artifact_digest=artifact,previous_digest=prev); self._events.append({**p,"digest":canonical_digest(p)})
    def _hold(self,reason,artifact):
        prev=self._holds[-1]["digest"] if self._holds else None; p=dict(sequence=len(self._holds)+1,reason=reason,attachment_digest=artifact,previous_digest=prev); self._holds.append({**p,"digest":canonical_digest(p)})
    @staticmethod
    def _chain(chain,event):
        prev=None
        for i,x in enumerate(chain,1):
            keys=("sequence","action","artifact_digest","previous_digest") if event else ("sequence","reason","attachment_digest","previous_digest"); p={k:x.get(k) for k in keys}
            if x!={**p,"digest":canonical_digest(p)} or x["sequence"]!=i or x["previous_digest"]!=prev:return False
            prev=x["digest"]
        return True

    def _integrity(self):
        if not self._registry_valid() or not self._chain(self._events,True) or not self._chain(self._holds,False) or (self._anchor and not self._anchor_valid(self._anchor)) or any(not self._case_valid(v,k) for k,v in self._cases.items()):return False
        if self._packet:
            r=self._packet; p={k:v for k,v in r.__dict__.items() if k!="digest"}; cset=canonical_digest(tuple(self._cases[k].digest for k in sorted(self._cases))); validators={x.cross_validator for x in self._cases.values()}; occupied=self._source_roles()+tuple(x.submitter for x in self._cases.values())+tuple(validators)
            if len(validators)!=1 or not _syn(r.packet_id,"reconciliation-queue-packet") or r.anchor_digest!=self._anchor.digest or r.case_set_digest!=cset or not _syn(r.queue_compiler,"reconciliation-queue-compiler") or _identity(r.queue_compiler) in {_identity(x) for x in occupied} or r.cross_validator!=next(iter(validators)) or r.source_reviewers!=self._anchor.source_reviewers or r.source_compilers!=self._anchor.source_compilers or r.source_chair!=self._anchor.source_chair or r.source_validator!=self._anchor.source_validator or r.source_lineage_digest!=self._anchor.source_lineage_digest or not r.complete or any((r.accepted,r.reconciled,r.recommended,r.decided,r.approved,r.activated,r.deployed)) or r.status!="HUMAN_RECONCILIATION_QUEUE_READY_NOT_ACCEPTED_NOT_DECIDED" or r.digest!=canonical_digest(p):return False
        expected=[]
        if self._anchor:expected.append(("ANSWER_INTAKE_ANCHORED",self._anchor.digest))
        expected.extend(("RECONCILIATION_CASE_RECORDED",x.digest) for x in self._cases.values())
        if self._packet:expected.append(("RECONCILIATION_QUEUE_PACKET_RECORDED",self._packet.digest))
        return [(x["action"],x["artifact_digest"]) for x in self._events]==expected and [(x["reason"],x["attachment_digest"]) for x in self._holds]==[("HUMAN_RECONCILIATION_REQUIRED",x.digest) for x in self._cases.values()]

    def evidence(self):
        ok=self._integrity(); complete=len(self._cases)==20 and self._packet is not None; matrix=WORKSTREAMS==tuple((7901+i*25,7925+i*25,n) for i,n in enumerate(WORKSTREAM_NAMES)) and len(CONTROL_ASPECTS)==25
        return {"range":[7901,8300],"control_count":400,"workstream_count":16,"controls_per_workstream":25,"control_matrix_valid":matrix,"registered_control_count":len(self._controls),"reconciliation_case_count":len(self._cases),"hold_count":len(self._holds),"event_count":len(self._events),"integrity_valid":ok,"complete_reconciliation_queue_evidence":complete and ok,"maximum_state":"HUMAN_RECONCILIATION_QUEUE_READY_NOT_ACCEPTED_NOT_DECIDED" if self._packet else "RECONCILIATION_QUEUE_INCOMPLETE","applied_lesson_ids":list(APPLIED_LESSONS),"applied_rule_ids":list(APPLIED_RULES),"external_calls":0,"external_answer_receipts":0,"document_transmissions":0,"electronic_signatures":0,"external_pg_calls":0,"card_network_calls":0,"payment_approvals":0,"cancellations":0,"refunds":0,"settlements":0,"transfers":0,"ledger_writes":0,"credential_reads":0,"deployments":0,"policy_prompt_weight_changes":0,"accepted":False,"reconciled":False,"recommended":False,"decided":False,"approved":False,"activated":False}
