"""Synthetic/in-memory operator review preflight docket controls #5101-#5500."""
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest


WORKSTREAM_NAMES = (
    "READINESS_RECEIPT_SOURCE_ANCHOR", "LESSON_AND_RULE_APPLICATION",
    "PARTY_CAPABILITY_RECALCULATION", "REHEARSAL_SET_COMPLETENESS",
    "TENANT_DOCUMENT_REVIEW", "NURION_DOCUMENT_REVIEW",
    "UPSTREAM_DOCUMENT_REVIEW", "FOUR_DIRECTION_ROUTE_REVIEW",
    "TOKEN_AND_SCHEMA_PREFLIGHT", "REPLAY_AND_ORDERING_PREFLIGHT",
    "FAILURE_AND_PARTIAL_BATCH_PREFLIGHT", "REVIEW_QUESTION_DOCKET",
    "FINDING_AND_HOLD_CLASSIFICATION", "INDEPENDENT_PREFLIGHT_REVIEW",
    "APPEND_ONLY_EVENT_HOLD_LINEAGE", "NON_APPROVAL_ACTIVATION_BOUNDARY",
)
WORKSTREAMS = tuple((5101+i*25, 5125+i*25, n) for i,n in enumerate(WORKSTREAM_NAMES))
CONTROL_ASPECTS = (
    "input_schema","required_fields","semantic_label","source_type","tenant_scope",
    "role_scope","state_precondition","latest_sequence","source_binding","digest_recalculation",
    "negative_path","missing_input","duplicate_input","replay","conflict","stale_version",
    "concurrency","partial_batch","ordering","append_only","hold_propagation",
    "review_independence","receipt_lineage","operator_gate","non_execution",
)
NEGATIVE = frozenset({"negative_path","missing_input","duplicate_input","replay","conflict","stale_version","partial_batch"})
PARTIES = ("TENANT_AGENCY","NURION_PG","UPSTREAM_PG")
FLOWS = ("tenant_to_nurion","nurion_to_upstream","upstream_to_nurion","nurion_to_tenant")
SCENARIOS = ("DOCUMENT","TOKEN","REPLAY","ORDERING","FAILURE","PARTIAL_BATCH")
COMMON_OPERATIONS = ("MAP","VALIDATE","MOCK_ACK")
COMMON_TOKEN_CLASSES = ("REFERENCE","SESSIONLESS_FIXTURE")
APPLIED_LESSONS = ("ARL-3901-001","ARL-4301-001","ARL-4301-002","ARL-4301-003","ARL-4701-001","ARL-5101-001")
APPLIED_RULES = tuple(f"ARP-{i:02}" for i in range(1,9))

def _syn(v,k): return isinstance(v,str) and v.startswith(f"synthetic:{k}:")
def _hex(v): return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _identity(v): return v.rsplit(":",1)[-1].casefold()

@dataclass(frozen=True)
class Control:
    control_id:int; workstream:str; aspect:str; requirement_ref:str; fixture_digest:str; expected_result:str; digest:str

@dataclass(frozen=True)
class PreflightAnchor:
    anchor_id:str; readiness_receipt_digest:str; plan_set_digest:str; result_set_digest:str
    lesson_registry_digest:str; remediation_manifest_digest:str
    applied_lesson_ids:tuple[str,...]; applied_rule_ids:tuple[str,...]
    capability_profile_digests:tuple[tuple[str,str],...]
    capability_binding_digests:tuple[tuple[str,str],...]
    capability_operations:tuple[tuple[str,tuple[str,...]],...]
    capability_token_classes:tuple[tuple[str,tuple[str,...]],...]
    common_operations:tuple[str,...]; common_token_classes:tuple[str,...]
    source_sequence:int; is_latest:bool; readiness_reviewer:str; status:str; digest:str

@dataclass(frozen=True)
class ReviewItem:
    item_id:str; flow:str; scenario:str; anchor_digest:str; route_digest:str
    capability_digest:str; expected_outcome:str; status:str; digest:str

@dataclass(frozen=True)
class DecisionPacket:
    packet_id:str; anchor_digest:str; item_set_digest:str; reviewer:str; source_reviewer:str
    review_complete:bool; approval_recorded:bool; activation_recorded:bool; deployment_recorded:bool
    status:str; digest:str

class SyntheticOperatorReviewPreflightDocket:
    """Creates an inert review packet; it cannot approve, activate, deploy or transmit."""
    def __init__(self):
        self._controls={}; self._anchor=None; self._items={}; self._packet=None
        self._events=[]; self._holds=[]; self._lock=RLock()

    def add_control(self, control_id, workstream, aspect, requirement_ref, fixture_digest, expected_result):
        p=dict(control_id=control_id,workstream=workstream,aspect=aspect,requirement_ref=requirement_ref,
               fixture_digest=fixture_digest,expected_result=expected_result)
        row=Control(**p,digest=canonical_digest(p))
        with self._lock:
            if not self._valid_control(row): raise GovernanceRejected("valid #5101-#5500 control required")
            prior=self._controls.get(control_id)
            if prior:
                if prior==row:return prior
                raise GovernanceRejected("control conflict")
            self._controls[control_id]=row; return row

    def anchor_readiness(self, anchor_id, readiness_receipt_digest, plan_set_digest, result_set_digest,
                         lesson_registry_digest, remediation_manifest_digest, applied_lesson_ids, applied_rule_ids,
                         capability_profile_digests, capability_binding_digests, capability_operations, capability_token_classes,
                         common_operations, common_token_classes, source_sequence, is_latest, readiness_reviewer):
        p=dict(anchor_id=anchor_id,readiness_receipt_digest=readiness_receipt_digest,
               plan_set_digest=plan_set_digest,result_set_digest=result_set_digest,
               lesson_registry_digest=lesson_registry_digest,remediation_manifest_digest=remediation_manifest_digest,
               applied_lesson_ids=tuple(applied_lesson_ids),applied_rule_ids=tuple(applied_rule_ids),
               capability_profile_digests=tuple(capability_profile_digests),
               capability_binding_digests=tuple(capability_binding_digests),
               capability_operations=tuple((x,tuple(v)) for x,v in capability_operations),
               capability_token_classes=tuple((x,tuple(v)) for x,v in capability_token_classes),
               common_operations=tuple(common_operations),common_token_classes=tuple(common_token_classes),
               source_sequence=source_sequence,is_latest=is_latest,readiness_reviewer=readiness_reviewer,
               status="READINESS_SOURCE_ACCEPTED_NOT_ACTIVATED")
        row=PreflightAnchor(**p,digest=canonical_digest(p))
        with self._lock:
            if not self._anchor_valid(row): raise GovernanceRejected("latest readiness source and learned rules required")
            if self._anchor:
                if self._anchor==row:return self._anchor
                raise GovernanceRejected("anchor conflict")
            self._anchor=row; self._event("READINESS_ANCHORED",row.digest); return row

    def add_review_item(self,item_id,flow,scenario,operations,token_classes):
        with self._lock:
            if self._anchor is None: raise GovernanceRejected("anchor required")
            ops,tokens=tuple(operations),tuple(token_classes)
            p=dict(item_id=item_id,flow=flow,scenario=scenario,anchor_digest=self._anchor.digest,
                   route_digest=canonical_digest(("PREFLIGHT_ROUTE",self._anchor.readiness_receipt_digest,flow)),
                   capability_digest=canonical_digest(("PREFLIGHT_CAPABILITY",ops,tokens)),
                   expected_outcome="HOLD_REVIEW" if scenario=="PARTIAL_BATCH" else "SYNTHETIC_REVIEW_PASS",
                   status="REVIEW_ITEM_INERT")
            row=ReviewItem(**p,digest=canonical_digest(p)); key=(flow,scenario)
            if (not _syn(item_id,"preflight-item") or flow not in FLOWS or scenario not in SCENARIOS
                    or ops!=self._anchor.common_operations or tokens!=self._anchor.common_token_classes):
                raise GovernanceRejected("common-capability synthetic item required")
            prior=self._items.get(key)
            if prior:
                if prior==row:return row
                raise GovernanceRejected("item conflict")
            self._items[key]=row; self._event("REVIEW_ITEM_RECORDED",row.digest)
            if scenario=="PARTIAL_BATCH": self._hold("PARTIAL_BATCH_REQUIRES_HOLD",row.digest)
            return row

    def finalize(self,packet_id,reviewer):
        with self._lock:
            if self._packet or set(self._items)!={(f,s) for f in FLOWS for s in SCENARIOS} or not self._integrity():
                raise GovernanceRejected("exact intact 24-item review required")
            if not _syn(packet_id,"preflight-packet") or not _syn(reviewer,"preflight-reviewer"):
                raise GovernanceRejected("synthetic independent reviewer required")
            if _identity(reviewer)==_identity(self._anchor.readiness_reviewer):
                raise GovernanceRejected("maker checker separation required")
            item_set=canonical_digest(tuple(self._items[k].digest for k in sorted(self._items)))
            p=dict(packet_id=packet_id,anchor_digest=self._anchor.digest,item_set_digest=item_set,
                   reviewer=reviewer,source_reviewer=self._anchor.readiness_reviewer,review_complete=True,
                   approval_recorded=False,activation_recorded=False,deployment_recorded=False,
                   status="OPERATOR_REVIEW_DOCKET_READY_NOT_APPROVED_NOT_ACTIVATED")
            self._packet=DecisionPacket(**p,digest=canonical_digest(p)); self._event("PREFLIGHT_PACKET_RECORDED",self._packet.digest)
            return self._packet

    def _expected(self,cid): i=cid-5101; return WORKSTREAM_NAMES[i//25],CONTROL_ASPECTS[i%25]
    def _valid_control(self,r):
        p={k:v for k,v in r.__dict__.items() if k!="digest"}
        return (isinstance(r.control_id,int) and not isinstance(r.control_id,bool) and 5101<=r.control_id<=5500
                and self._expected(r.control_id)==(r.workstream,r.aspect)
                and r.requirement_ref==f"synthetic:preflight-requirement:{(r.control_id-5101)//25:02}"
                and _hex(r.fixture_digest) and r.expected_result==("EXPECTED_REJECTION" if r.aspect in NEGATIVE else "PASS")
                and r.digest==canonical_digest(p))
    def _registry_valid(self):
        return (set(self._controls)==set(range(5101,5501))
                and all(key==row.control_id and self._valid_control(row) for key,row in self._controls.items()))
    def _anchor_valid(self,a):
        if not self._registry_valid():return False
        ops=set.intersection(*(set(v) for _,v in a.capability_operations)) if a.capability_operations else set()
        toks=set.intersection(*(set(v) for _,v in a.capability_token_classes)) if a.capability_token_classes else set()
        p={k:v for k,v in a.__dict__.items() if k!="digest"}
        return (_syn(a.anchor_id,"preflight-anchor") and all(_hex(x) for x in (a.readiness_receipt_digest,a.plan_set_digest,a.result_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest))
                and a.applied_lesson_ids==APPLIED_LESSONS and a.applied_rule_ids==APPLIED_RULES
                and tuple(x for x,_ in a.capability_profile_digests)==PARTIES and all(_hex(v) for _,v in a.capability_profile_digests)
                and tuple(x for x,_ in a.capability_binding_digests)==PARTIES
                and a.capability_binding_digests==tuple((party,canonical_digest(("PARTY_CAPABILITY",party,profile,dict(a.capability_operations)[party],dict(a.capability_token_classes)[party]))) for party,profile in a.capability_profile_digests)
                and tuple(x for x,_ in a.capability_operations)==PARTIES and tuple(x for x,_ in a.capability_token_classes)==PARTIES
                and ops==set(COMMON_OPERATIONS) and toks==set(COMMON_TOKEN_CLASSES)
                and a.common_operations==COMMON_OPERATIONS and a.common_token_classes==COMMON_TOKEN_CLASSES
                and isinstance(a.source_sequence,int) and not isinstance(a.source_sequence,bool) and a.source_sequence>0 and a.is_latest is True
                and _syn(a.readiness_reviewer,"readiness-reviewer") and a.status=="READINESS_SOURCE_ACCEPTED_NOT_ACTIVATED"
                and a.digest==canonical_digest(p))
    def _event(self,action,artifact):
        prev=self._events[-1]["digest"] if self._events else None
        p=dict(sequence=len(self._events)+1,action=action,artifact_digest=artifact,previous_digest=prev)
        self._events.append({**p,"digest":canonical_digest(p)})
    def _hold(self,reason,artifact):
        prev=self._holds[-1]["digest"] if self._holds else None
        p=dict(sequence=len(self._holds)+1,reason=reason,attachment_digest=artifact,previous_digest=prev)
        self._holds.append({**p,"digest":canonical_digest(p)})
    @staticmethod
    def _chain(chain,event):
        prev=None
        for i,x in enumerate(chain,1):
            keys=("sequence","action","artifact_digest","previous_digest") if event else ("sequence","reason","attachment_digest","previous_digest")
            p={k:x.get(k) for k in keys}
            if x!={**p,"digest":canonical_digest(p)} or x["sequence"]!=i or x["previous_digest"]!=prev:return False
            prev=x["digest"]
        return True
    def _integrity(self):
        if not self._registry_valid() or not self._chain(self._events,True) or not self._chain(self._holds,False):return False
        if self._anchor and not self._anchor_valid(self._anchor):return False
        for key,r in self._items.items():
            p={k:v for k,v in r.__dict__.items() if k!="digest"}; expected="HOLD_REVIEW" if r.scenario=="PARTIAL_BATCH" else "SYNTHETIC_REVIEW_PASS"
            if (key!=(r.flow,r.scenario) or r.anchor_digest!=self._anchor.digest or not _syn(r.item_id,"preflight-item")
                    or r.route_digest!=canonical_digest(("PREFLIGHT_ROUTE",self._anchor.readiness_receipt_digest,r.flow))
                    or r.capability_digest!=canonical_digest(("PREFLIGHT_CAPABILITY",COMMON_OPERATIONS,COMMON_TOKEN_CLASSES))
                    or r.expected_outcome!=expected or r.status!="REVIEW_ITEM_INERT" or r.digest!=canonical_digest(p)):return False
        if self._packet:
            r=self._packet;p={k:v for k,v in r.__dict__.items() if k!="digest"}
            item_set=canonical_digest(tuple(self._items[k].digest for k in sorted(self._items)))
            if (not _syn(r.packet_id,"preflight-packet") or r.anchor_digest!=self._anchor.digest or r.item_set_digest!=item_set
                    or not _syn(r.reviewer,"preflight-reviewer") or r.source_reviewer!=self._anchor.readiness_reviewer
                    or _identity(r.reviewer)==_identity(r.source_reviewer) or not r.review_complete or r.approval_recorded
                    or r.activation_recorded or r.deployment_recorded or r.status!="OPERATOR_REVIEW_DOCKET_READY_NOT_APPROVED_NOT_ACTIVATED"
                    or r.digest!=canonical_digest(p)):return False
        expected=[]
        if self._anchor:expected.append(("READINESS_ANCHORED",self._anchor.digest))
        expected.extend(("REVIEW_ITEM_RECORDED",x.digest) for x in self._items.values())
        if self._packet:expected.append(("PREFLIGHT_PACKET_RECORDED",self._packet.digest))
        if [(x["action"],x["artifact_digest"]) for x in self._events]!=expected:return False
        expected_holds=[("PARTIAL_BATCH_REQUIRES_HOLD",v.digest) for k,v in self._items.items() if k[1]=="PARTIAL_BATCH"]
        return [(x["reason"],x["attachment_digest"]) for x in self._holds]==expected_holds
    def evidence(self):
        ok=self._integrity(); complete=len(self._items)==24 and self._packet is not None
        expected_workstreams=tuple((5101+i*25,5125+i*25,n) for i,n in enumerate(WORKSTREAM_NAMES))
        return {"range":[5101,5500],"control_count":400,"workstream_count":16,"controls_per_workstream":25,
                "control_matrix_valid":WORKSTREAMS==expected_workstreams and len(CONTROL_ASPECTS)==25,
                "registered_control_count":len(self._controls),"review_item_count":len(self._items),"hold_count":len(self._holds),
                "event_count":len(self._events),"integrity_valid":ok,"complete_preflight_evidence":complete and ok,
                "maximum_state":"OPERATOR_REVIEW_DOCKET_READY_NOT_APPROVED_NOT_ACTIVATED" if self._packet else "PREFLIGHT_REVIEW_INCOMPLETE",
                "applied_lesson_ids":list(APPLIED_LESSONS),"applied_rule_ids":list(APPLIED_RULES),
                "external_calls":0,"document_transmissions":0,"electronic_signatures":0,"external_pg_calls":0,"card_network_calls":0,
                "payment_approvals":0,"cancellations":0,"refunds":0,"settlements":0,"transfers":0,"ledger_writes":0,
                "credential_reads":0,"deployments":0,"policy_prompt_weight_changes":0,"approval_recorded":False,"activation_recorded":False}
