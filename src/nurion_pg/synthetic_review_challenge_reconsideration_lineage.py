"""Synthetic/in-memory review challenge and reconsideration lineage controls #5501-#5900."""
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest

WORKSTREAM_NAMES = (
    "PREFLIGHT_PACKET_SOURCE_ANCHOR", "LESSON_RULE_REGISTRY_BINDING",
    "TENANT_CHALLENGE_DOCUMENT", "NURION_CHALLENGE_DOCUMENT",
    "UPSTREAM_CHALLENGE_DOCUMENT", "FOUR_DIRECTION_CHALLENGE_ROUTE",
    "EVIDENCE_GAP_GROUND", "SEMANTIC_BINDING_GROUND", "ROLE_CONFLICT_GROUND",
    "PARTIAL_BATCH_GROUND", "LINEAGE_BREAK_GROUND", "RECONSIDERATION_ASSIGNMENT",
    "INDEPENDENT_REVIEWER_SEPARATION", "APPEND_ONLY_CHALLENGE_HOLD_CHAIN",
    "RECONSIDERATION_RECEIPT_LINEAGE", "NON_DECISION_ACTIVATION_BOUNDARY",
)
WORKSTREAMS = tuple((5501+i*25, 5525+i*25, n) for i,n in enumerate(WORKSTREAM_NAMES))
CONTROL_ASPECTS = (
    "input_schema","required_fields","semantic_label","source_type","tenant_scope",
    "role_scope","state_precondition","latest_sequence","source_binding","digest_recalculation",
    "negative_path","missing_input","duplicate_input","replay","conflict","stale_version",
    "concurrency","partial_batch","ordering","append_only","hold_propagation",
    "review_independence","receipt_lineage","operator_gate","non_execution",
)
NEGATIVE=frozenset({"negative_path","missing_input","duplicate_input","replay","conflict","stale_version","partial_batch"})
PARTIES=("TENANT_AGENCY","NURION_PG","UPSTREAM_PG")
FLOWS=("tenant_to_nurion","nurion_to_upstream","upstream_to_nurion","nurion_to_tenant")
FLOW_SOURCE_PARTY=dict(zip(FLOWS,("TENANT_AGENCY","NURION_PG","UPSTREAM_PG","NURION_PG")))
GROUNDS=("EVIDENCE_GAP","SEMANTIC_BINDING","ROLE_CONFLICT","PARTIAL_BATCH","LINEAGE_BREAK")
APPLIED_LESSONS=("ARL-3901-001","ARL-4301-001","ARL-4301-002","ARL-4301-003","ARL-4701-001","ARL-5101-001","ARL-5501-001")
APPLIED_RULES=tuple(f"ARP-{i:02}" for i in range(1,9))

def _syn(v,k): return isinstance(v,str) and v.startswith(f"synthetic:{k}:")
def _hex(v): return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _identity(v): return v.rsplit(":",1)[-1].casefold()

@dataclass(frozen=True)
class Control: control_id:int; workstream:str; aspect:str; requirement_ref:str; fixture_digest:str; expected_result:str; digest:str
@dataclass(frozen=True)
class SourceAnchor:
    anchor_id:str; preflight_packet_digest:str; item_set_digest:str; lesson_registry_digest:str
    remediation_manifest_digest:str; applied_lesson_ids:tuple[str,...]; applied_rule_ids:tuple[str,...]
    party_document_digests:tuple[tuple[str,str],...]; route_binding_digests:tuple[tuple[str,str],...]
    source_sequence:int; is_latest:bool; readiness_reviewer:str; preflight_reviewer:str; status:str; digest:str
@dataclass(frozen=True)
class Challenge:
    challenge_id:str; flow:str; ground:str; anchor_digest:str; document_digest:str
    route_binding_digest:str; challenger:str; status:str; digest:str
@dataclass(frozen=True)
class ReconsiderationReceipt:
    receipt_id:str; anchor_digest:str; challenge_set_digest:str; reviewer:str
    source_reviewers:tuple[str,str]; review_complete:bool; decision_recorded:bool
    approval_recorded:bool; activation_recorded:bool; deployment_recorded:bool; status:str; digest:str

class SyntheticReviewChallengeReconsiderationLineage:
    """Records inert objections and reconsideration provenance; never decides or executes."""
    def __init__(self):
        self._controls={}; self._anchor=None; self._challenges={}; self._receipt=None
        self._events=[]; self._holds=[]; self._lock=RLock()

    def add_control(self,cid,workstream,aspect,requirement_ref,fixture_digest,expected_result):
        p=dict(control_id=cid,workstream=workstream,aspect=aspect,requirement_ref=requirement_ref,fixture_digest=fixture_digest,expected_result=expected_result)
        row=Control(**p,digest=canonical_digest(p))
        with self._lock:
            if not self._valid_control(row): raise GovernanceRejected("valid #5501-#5900 control required")
            old=self._controls.get(cid)
            if old:
                if old==row:return old
                raise GovernanceRejected("control conflict")
            self._controls[cid]=row; return row

    def anchor_source(self,anchor_id,preflight_packet_digest,item_set_digest,lesson_registry_digest,
                      remediation_manifest_digest,applied_lesson_ids,applied_rule_ids,
                      party_document_digests,route_binding_digests,source_sequence,is_latest,
                      readiness_reviewer,preflight_reviewer):
        p=dict(anchor_id=anchor_id,preflight_packet_digest=preflight_packet_digest,item_set_digest=item_set_digest,
               lesson_registry_digest=lesson_registry_digest,remediation_manifest_digest=remediation_manifest_digest,
               applied_lesson_ids=tuple(applied_lesson_ids),applied_rule_ids=tuple(applied_rule_ids),
               party_document_digests=tuple(party_document_digests),route_binding_digests=tuple(route_binding_digests),
               source_sequence=source_sequence,is_latest=is_latest,readiness_reviewer=readiness_reviewer,
               preflight_reviewer=preflight_reviewer,status="PREFLIGHT_PACKET_ANCHORED_NOT_DECIDED")
        row=SourceAnchor(**p,digest=canonical_digest(p))
        with self._lock:
            if not self._anchor_valid(row): raise GovernanceRejected("latest semantically-bound source required")
            if self._anchor:
                if self._anchor==row:return self._anchor
                raise GovernanceRejected("anchor conflict")
            self._anchor=row; self._event("PREFLIGHT_SOURCE_ANCHORED",row.digest); return row

    def add_challenge(self,challenge_id,flow,ground,document_digest,challenger):
        with self._lock:
            if not self._anchor: raise GovernanceRejected("source anchor required")
            route=dict(self._anchor.route_binding_digests).get(flow)
            p=dict(challenge_id=challenge_id,flow=flow,ground=ground,anchor_digest=self._anchor.digest,
                   document_digest=document_digest,route_binding_digest=route,challenger=challenger,
                   status="CHALLENGE_OPEN_HOLD")
            row=Challenge(**p,digest=canonical_digest(p)); key=(flow,ground)
            if not self._challenge_valid(row,key): raise GovernanceRejected("synthetic bound challenge required")
            old=self._challenges.get(key)
            if old:
                if old==row:return old
                raise GovernanceRejected("challenge conflict")
            self._challenges[key]=row; self._event("CHALLENGE_RECORDED",row.digest); self._hold("OPEN_CHALLENGE_BLOCKS_DECISION",row.digest)
            return row

    def finalize(self,receipt_id,reviewer):
        with self._lock:
            if self._receipt or set(self._challenges)!={(f,g) for f in FLOWS for g in GROUNDS} or not self._integrity():
                raise GovernanceRejected("exact intact challenge set required")
            if not _syn(receipt_id,"reconsideration-receipt") or not _syn(reviewer,"reconsideration-reviewer"):
                raise GovernanceRejected("synthetic reviewer required")
            sources=(self._anchor.readiness_reviewer,self._anchor.preflight_reviewer)
            if _identity(reviewer) in {_identity(x) for x in sources}: raise GovernanceRejected("independent reviewer required")
            challenge_set=canonical_digest(tuple(self._challenges[k].digest for k in sorted(self._challenges)))
            p=dict(receipt_id=receipt_id,anchor_digest=self._anchor.digest,challenge_set_digest=challenge_set,
                   reviewer=reviewer,source_reviewers=sources,review_complete=True,decision_recorded=False,
                   approval_recorded=False,activation_recorded=False,deployment_recorded=False,
                   status="RECONSIDERATION_DOCKET_READY_NOT_DECIDED_NOT_ACTIVATED")
            self._receipt=ReconsiderationReceipt(**p,digest=canonical_digest(p)); self._event("RECONSIDERATION_RECEIPT_RECORDED",self._receipt.digest)
            return self._receipt

    def _expected(self,cid): i=cid-5501; return WORKSTREAM_NAMES[i//25],CONTROL_ASPECTS[i%25]
    def _valid_control(self,r):
        p={k:v for k,v in r.__dict__.items() if k!="digest"}
        return (isinstance(r.control_id,int) and not isinstance(r.control_id,bool) and 5501<=r.control_id<=5900
                and self._expected(r.control_id)==(r.workstream,r.aspect)
                and r.requirement_ref==f"synthetic:challenge-requirement:{(r.control_id-5501)//25:02}"
                and _hex(r.fixture_digest) and r.expected_result==("EXPECTED_REJECTION" if r.aspect in NEGATIVE else "PASS")
                and r.digest==canonical_digest(p))
    def _registry_valid(self): return set(self._controls)==set(range(5501,5901)) and all(k==v.control_id and self._valid_control(v) for k,v in self._controls.items())
    def _anchor_valid(self,a):
        p={k:v for k,v in a.__dict__.items() if k!="digest"}; docs=dict(a.party_document_digests)
        expected_routes=tuple((f,canonical_digest(("CHALLENGE_ROUTE",f,tuple(a.party_document_digests),a.preflight_packet_digest))) for f in FLOWS)
        return (self._registry_valid() and _syn(a.anchor_id,"challenge-anchor")
                and all(_hex(x) for x in (a.preflight_packet_digest,a.item_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest))
                and a.applied_lesson_ids==APPLIED_LESSONS and a.applied_rule_ids==APPLIED_RULES
                and tuple(x for x,_ in a.party_document_digests)==PARTIES and len(docs)==3 and all(_hex(x) for x in docs.values())
                and a.route_binding_digests==expected_routes and isinstance(a.source_sequence,int) and not isinstance(a.source_sequence,bool)
                and a.source_sequence>0 and a.is_latest is True and _syn(a.readiness_reviewer,"readiness-reviewer")
                and _syn(a.preflight_reviewer,"preflight-reviewer") and _identity(a.readiness_reviewer)!=_identity(a.preflight_reviewer)
                and a.status=="PREFLIGHT_PACKET_ANCHORED_NOT_DECIDED" and a.digest==canonical_digest(p))
    def _challenge_valid(self,r,key):
        if not self._anchor:return False
        p={k:v for k,v in r.__dict__.items() if k!="digest"}
        source_party=FLOW_SOURCE_PARTY.get(r.flow);route=dict(self._anchor.route_binding_digests).get(r.flow)
        source_document=dict(self._anchor.party_document_digests).get(source_party)
        expected_document=canonical_digest(("CHALLENGE_DOCUMENT",source_party,source_document,r.flow,r.ground,route))
        return (key==(r.flow,r.ground) and r.flow in FLOWS and r.ground in GROUNDS and _syn(r.challenge_id,"challenge")
                and r.document_digest==expected_document and r.challenger==f"synthetic:challenger:{source_party}"
                and r.anchor_digest==self._anchor.digest and r.route_binding_digest==route
                and r.status=="CHALLENGE_OPEN_HOLD" and r.digest==canonical_digest(p))
    def _event(self,action,artifact):
        prev=self._events[-1]["digest"] if self._events else None;p=dict(sequence=len(self._events)+1,action=action,artifact_digest=artifact,previous_digest=prev);self._events.append({**p,"digest":canonical_digest(p)})
    def _hold(self,reason,artifact):
        prev=self._holds[-1]["digest"] if self._holds else None;p=dict(sequence=len(self._holds)+1,reason=reason,attachment_digest=artifact,previous_digest=prev);self._holds.append({**p,"digest":canonical_digest(p)})
    @staticmethod
    def _chain(chain,event):
        prev=None
        for i,x in enumerate(chain,1):
            keys=("sequence","action","artifact_digest","previous_digest") if event else ("sequence","reason","attachment_digest","previous_digest");p={k:x.get(k) for k in keys}
            if x!={**p,"digest":canonical_digest(p)} or x["sequence"]!=i or x["previous_digest"]!=prev:return False
            prev=x["digest"]
        return True
    def _integrity(self):
        if not self._registry_valid() or not self._chain(self._events,True) or not self._chain(self._holds,False):return False
        if self._anchor and not self._anchor_valid(self._anchor):return False
        if any(not self._challenge_valid(v,k) for k,v in self._challenges.items()):return False
        if self._receipt:
            r=self._receipt;p={k:v for k,v in r.__dict__.items() if k!="digest"};cs=canonical_digest(tuple(self._challenges[k].digest for k in sorted(self._challenges)))
            if (not _syn(r.receipt_id,"reconsideration-receipt") or r.anchor_digest!=self._anchor.digest or r.challenge_set_digest!=cs
                    or not _syn(r.reviewer,"reconsideration-reviewer") or r.source_reviewers!=(self._anchor.readiness_reviewer,self._anchor.preflight_reviewer)
                    or _identity(r.reviewer) in {_identity(x) for x in r.source_reviewers} or not r.review_complete or r.decision_recorded
                    or r.approval_recorded or r.activation_recorded or r.deployment_recorded
                    or r.status!="RECONSIDERATION_DOCKET_READY_NOT_DECIDED_NOT_ACTIVATED" or r.digest!=canonical_digest(p)):return False
        expected=[]
        if self._anchor:expected.append(("PREFLIGHT_SOURCE_ANCHORED",self._anchor.digest))
        expected.extend(("CHALLENGE_RECORDED",x.digest) for x in self._challenges.values())
        if self._receipt:expected.append(("RECONSIDERATION_RECEIPT_RECORDED",self._receipt.digest))
        if [(x["action"],x["artifact_digest"]) for x in self._events]!=expected:return False
        holds=[("OPEN_CHALLENGE_BLOCKS_DECISION",x.digest) for x in self._challenges.values()]
        return [(x["reason"],x["attachment_digest"]) for x in self._holds]==holds
    def evidence(self):
        ok=self._integrity();complete=len(self._challenges)==20 and self._receipt is not None
        matrix=WORKSTREAMS==tuple((5501+i*25,5525+i*25,n) for i,n in enumerate(WORKSTREAM_NAMES)) and len(CONTROL_ASPECTS)==25
        return {"range":[5501,5900],"control_count":400,"workstream_count":16,"controls_per_workstream":25,
                "control_matrix_valid":matrix,"registered_control_count":len(self._controls),"challenge_count":len(self._challenges),
                "hold_count":len(self._holds),"event_count":len(self._events),"integrity_valid":ok,"complete_reconsideration_evidence":complete and ok,
                "maximum_state":"RECONSIDERATION_DOCKET_READY_NOT_DECIDED_NOT_ACTIVATED" if self._receipt else "CHALLENGE_REVIEW_INCOMPLETE",
                "applied_lesson_ids":list(APPLIED_LESSONS),"applied_rule_ids":list(APPLIED_RULES),
                "external_calls":0,"document_transmissions":0,"electronic_signatures":0,"external_pg_calls":0,"card_network_calls":0,
                "payment_approvals":0,"cancellations":0,"refunds":0,"settlements":0,"transfers":0,"ledger_writes":0,
                "credential_reads":0,"deployments":0,"policy_prompt_weight_changes":0,"decision_recorded":False,"approval_recorded":False,"activation_recorded":False}
