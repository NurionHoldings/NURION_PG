"""Synthetic/in-memory correction comparison, consent-conflict, and operator review readiness #6301-#6700."""
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest

WORKSTREAM_NAMES = (
    "CORRECTION_READINESS_RECEIPT_ANCHOR", "LESSON_RULE_REGISTRY_BINDING",
    "TENANT_CORRECTION_PROPOSAL", "NURION_CORRECTION_PROPOSAL",
    "UPSTREAM_CORRECTION_PROPOSAL", "FOUR_DIRECTION_CORRECTION_COMPARISON_ROUTE",
    "CONSENT_SCOPE_COMPARISON", "DATA_MEANING_COMPARISON",
    "ROLE_AUTHORITY_CONFLICT", "PARTIAL_BATCH_CONFLICT", "LINEAGE_BREAK_CONFLICT",
    "COUNTERPARTY_COUNTERPROPOSAL_DOCUMENT", "CONSENT_CONFLICT_COMPARISON_PROVENANCE",
    "APPEND_ONLY_CONFLICT_HOLD_CHAIN", "INDEPENDENT_REVIEW_PACKET_COMPILATION",
    "NON_CONSENT_NON_DECISION_BOUNDARY",
)
WORKSTREAMS = tuple((6301+i*25, 6325+i*25, n) for i,n in enumerate(WORKSTREAM_NAMES))
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
FLOW_PARTIES={
    "tenant_to_nurion":("TENANT_AGENCY","NURION_PG"),
    "nurion_to_upstream":("NURION_PG","UPSTREAM_PG"),
    "upstream_to_nurion":("UPSTREAM_PG","NURION_PG"),
    "nurion_to_tenant":("NURION_PG","TENANT_AGENCY"),
}
TOPICS=("CONSENT_SCOPE","DATA_MEANING","ROLE_AUTHORITY","PARTIAL_BATCH","LINEAGE_BREAK")
APPLIED_LESSONS=("ARL-3901-001","ARL-4301-001","ARL-4301-002","ARL-4301-003","ARL-4701-001","ARL-5101-001","ARL-5501-001","ARL-5901-001","ARL-6301-001")
APPLIED_RULES=tuple(f"ARP-{i:02}" for i in range(1,9))

def _syn(v,k): return isinstance(v,str) and v.startswith(f"synthetic:{k}:")
def _hex(v): return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _identity(v): return v.rsplit(":",1)[-1].casefold()

@dataclass(frozen=True)
class Control: control_id:int; workstream:str; aspect:str; requirement_ref:str; fixture_digest:str; expected_result:str; digest:str
@dataclass(frozen=True)
class CorrectionReadinessAnchor:
    anchor_id:str; correction_readiness_receipt_digest:str; correction_case_set_digest:str; lesson_registry_digest:str
    remediation_manifest_digest:str; applied_lesson_ids:tuple[str,...]; applied_rule_ids:tuple[str,...]
    correction_document_digests:tuple[tuple[str,str],...]; route_binding_digests:tuple[tuple[str,str],...]
    source_sequence:int; is_latest:bool; source_reviewers:tuple[str,str,str]; source_compiler:str
    reviewer_lineage_digest:str; status:str; digest:str
@dataclass(frozen=True)
class ConsentConflictCase:
    case_id:str; flow:str; topic:str; source_party:str; counterparty:str; anchor_digest:str
    source_correction_digest:str; counterproposal_digest:str; comparison_digest:str; route_binding_digest:str
    discloser:str; rebutter:str; status:str; digest:str
@dataclass(frozen=True)
class ReadinessPacket:
    packet_id:str; anchor_digest:str; case_set_digest:str; compiler:str; source_reviewers:tuple[str,str,str]
    complete:bool; published:bool; consent_recorded:bool; decision_recorded:bool; approval_recorded:bool; activation_recorded:bool
    deployment_recorded:bool; status:str; digest:str

class SyntheticCorrectionComparisonConsentConflictReviewReadiness:
    """Builds inert drafts and provenance only; it cannot publish, decide, approve, or execute."""
    def __init__(self):
        self._controls={}; self._anchor=None; self._cases={}; self._packet=None
        self._events=[]; self._holds=[]; self._lock=RLock()

    def add_control(self,cid,workstream,aspect,requirement_ref,fixture_digest,expected_result):
        p=dict(control_id=cid,workstream=workstream,aspect=aspect,requirement_ref=requirement_ref,fixture_digest=fixture_digest,expected_result=expected_result)
        row=Control(**p,digest=canonical_digest(p))
        with self._lock:
            if not self._valid_control(row): raise GovernanceRejected("valid #6301-#6700 control required")
            old=self._controls.get(cid)
            if old:
                if old==row:return old
                raise GovernanceRejected("control conflict")
            self._controls[cid]=row; return row

    def anchor_source(self,anchor_id,correction_readiness_receipt_digest,correction_case_set_digest,lesson_registry_digest,
                      remediation_manifest_digest,applied_lesson_ids,applied_rule_ids,correction_document_digests,
                      route_binding_digests,source_sequence,is_latest,source_reviewers,source_compiler):
        reviewers=tuple(source_reviewers)
        p=dict(anchor_id=anchor_id,correction_readiness_receipt_digest=correction_readiness_receipt_digest,
               correction_case_set_digest=correction_case_set_digest,lesson_registry_digest=lesson_registry_digest,
               remediation_manifest_digest=remediation_manifest_digest,applied_lesson_ids=tuple(applied_lesson_ids),
               applied_rule_ids=tuple(applied_rule_ids),correction_document_digests=tuple(correction_document_digests),
               route_binding_digests=tuple(route_binding_digests),source_sequence=source_sequence,is_latest=is_latest,
               source_reviewers=reviewers,source_compiler=source_compiler,
               reviewer_lineage_digest=canonical_digest(("CORRECTION_READINESS_REVIEWER_LINEAGE",correction_readiness_receipt_digest,reviewers,source_compiler)),
               status="CORRECTION_READINESS_ANCHORED_NOT_CONSENTED")
        row=CorrectionReadinessAnchor(**p,digest=canonical_digest(p))
        with self._lock:
            if not self._anchor_valid(row): raise GovernanceRejected("latest semantically-bound reconsideration source required")
            if self._anchor:
                if self._anchor==row:return self._anchor
                raise GovernanceRejected("anchor conflict")
            self._anchor=row; self._event("CORRECTION_READINESS_SOURCE_ANCHORED",row.digest); return row

    def add_case(self,case_id,flow,topic,source_correction_digest,counterproposal_digest,comparison_digest,discloser,rebutter):
        with self._lock:
            if not self._anchor: raise GovernanceRejected("source anchor required")
            source,counterparty=FLOW_PARTIES.get(flow,(None,None)); route=dict(self._anchor.route_binding_digests).get(flow)
            p=dict(case_id=case_id,flow=flow,topic=topic,source_party=source,counterparty=counterparty,
                   anchor_digest=self._anchor.digest,source_correction_digest=source_correction_digest,counterproposal_digest=counterproposal_digest,
                   comparison_digest=comparison_digest,route_binding_digest=route,discloser=discloser,
                   rebutter=rebutter,status="CONSENT_CONFLICT_HELD_NOT_DECIDED")
            row=ConsentConflictCase(**p,digest=canonical_digest(p)); key=(flow,topic)
            if not self._case_valid(row,key): raise GovernanceRejected("synthetic bound correction case required")
            old=self._cases.get(key)
            if old:
                if old==row:return old
                raise GovernanceRejected("case conflict")
            self._cases[key]=row; self._event("CONSENT_CONFLICT_RECORDED",row.digest); self._hold("CONSENT_CONFLICT_REQUIRES_OPERATOR_REVIEW",row.digest)
            return row

    def finalize(self,packet_id,compiler):
        with self._lock:
            if self._packet or set(self._cases)!={(f,t) for f in FLOWS for t in TOPICS} or not self._integrity():
                raise GovernanceRejected("exact intact correction case set required")
            if not _syn(packet_id,"operator-conflict-review-packet") or not _syn(compiler,"packet-compiler"):
                raise GovernanceRejected("synthetic compiler required")
            if _identity(compiler) in {_identity(x) for x in self._anchor.source_reviewers+(self._anchor.source_compiler,)}: raise GovernanceRejected("independent compiler required")
            case_set=canonical_digest(tuple(self._cases[k].digest for k in sorted(self._cases)))
            p=dict(packet_id=packet_id,anchor_digest=self._anchor.digest,case_set_digest=case_set,compiler=compiler,
                   source_reviewers=self._anchor.source_reviewers,complete=True,published=False,consent_recorded=False,decision_recorded=False,
                   approval_recorded=False,activation_recorded=False,deployment_recorded=False,
                   status="OPERATOR_CONFLICT_REVIEW_PACKET_READY_NOT_DECIDED_NOT_APPROVED")
            self._packet=ReadinessPacket(**p,digest=canonical_digest(p)); self._event("READINESS_PACKET_RECORDED",self._packet.digest)
            return self._packet

    def _expected(self,cid): i=cid-6301; return WORKSTREAM_NAMES[i//25],CONTROL_ASPECTS[i%25]
    def _valid_control(self,r):
        p={k:v for k,v in r.__dict__.items() if k!="digest"}
        return (isinstance(r.control_id,int) and not isinstance(r.control_id,bool) and 6301<=r.control_id<=6700
                and self._expected(r.control_id)==(r.workstream,r.aspect)
                and r.requirement_ref==f"synthetic:comparison-requirement:{(r.control_id-6301)//25:02}"
                and _hex(r.fixture_digest) and r.expected_result==("EXPECTED_REJECTION" if r.aspect in NEGATIVE else "PASS")
                and r.digest==canonical_digest(p))
    def _registry_valid(self): return set(self._controls)==set(range(6301,6701)) and all(k==v.control_id and self._valid_control(v) for k,v in self._controls.items())
    def _anchor_valid(self,a):
        p={k:v for k,v in a.__dict__.items() if k!="digest"}; docs=dict(a.correction_document_digests)
        expected_routes=tuple((f,canonical_digest(("CORRECTION_COMPARISON_ROUTE",f,FLOW_PARTIES[f],tuple(a.correction_document_digests),a.correction_readiness_receipt_digest))) for f in FLOWS)
        return (self._registry_valid() and _syn(a.anchor_id,"comparison-anchor")
                and all(_hex(x) for x in (a.correction_readiness_receipt_digest,a.correction_case_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest))
                and a.applied_lesson_ids==APPLIED_LESSONS and a.applied_rule_ids==APPLIED_RULES
                and tuple(x for x,_ in a.correction_document_digests)==PARTIES and len(docs)==3 and all(_hex(x) for x in docs.values())
                and a.route_binding_digests==expected_routes and isinstance(a.source_sequence,int) and not isinstance(a.source_sequence,bool)
                and a.source_sequence>0 and a.is_latest is True and len(a.source_reviewers)==3
                and all(_syn(x,k) for x,k in zip(a.source_reviewers,("readiness-reviewer","preflight-reviewer","reconsideration-reviewer")))
                and _syn(a.source_compiler,"packet-compiler")
                and len({_identity(x) for x in a.source_reviewers+(a.source_compiler,)})==4
                and a.reviewer_lineage_digest==canonical_digest(("CORRECTION_READINESS_REVIEWER_LINEAGE",a.correction_readiness_receipt_digest,a.source_reviewers,a.source_compiler))
                and a.status=="CORRECTION_READINESS_ANCHORED_NOT_CONSENTED"
                and a.digest==canonical_digest(p))
    def _case_valid(self,r,key):
        if not self._anchor:return False
        p={k:v for k,v in r.__dict__.items() if k!="digest"}; source,counterparty=FLOW_PARTIES.get(r.flow,(None,None))
        route=dict(self._anchor.route_binding_digests).get(r.flow); source_doc=dict(self._anchor.correction_document_digests).get(source)
        disclosure=canonical_digest(("SOURCE_CORRECTION_DOCUMENT",source,source_doc,r.flow,r.topic,route,self._anchor.correction_case_set_digest))
        rebuttal=canonical_digest(("COUNTERPROPOSAL_DOCUMENT",counterparty,r.flow,r.topic,disclosure,route))
        correction=canonical_digest(("CONSENT_CONFLICT_COMPARISON",source,counterparty,r.flow,r.topic,disclosure,rebuttal,route))
        return (key==(r.flow,r.topic) and r.flow in FLOWS and r.topic in TOPICS and _syn(r.case_id,"consent-conflict-case")
                and (r.source_party,r.counterparty)==(source,counterparty) and r.anchor_digest==self._anchor.digest
                and (r.source_correction_digest,r.counterproposal_digest,r.comparison_digest)==(disclosure,rebuttal,correction)
                and r.route_binding_digest==route and r.discloser==f"synthetic:discloser:{source}"
                and r.rebutter==f"synthetic:rebutter:{counterparty}" and r.status=="CONSENT_CONFLICT_HELD_NOT_DECIDED"
                and r.digest==canonical_digest(p))
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
        if any(not self._case_valid(v,k) for k,v in self._cases.items()):return False
        if self._packet:
            r=self._packet;p={k:v for k,v in r.__dict__.items() if k!="digest"};case_set=canonical_digest(tuple(self._cases[k].digest for k in sorted(self._cases)))
            if (not _syn(r.packet_id,"operator-conflict-review-packet") or r.anchor_digest!=self._anchor.digest or r.case_set_digest!=case_set
                    or not _syn(r.compiler,"packet-compiler") or r.source_reviewers!=self._anchor.source_reviewers
                    or _identity(r.compiler) in {_identity(x) for x in r.source_reviewers+(self._anchor.source_compiler,)} or not r.complete or r.published or r.consent_recorded
                    or r.decision_recorded or r.approval_recorded or r.activation_recorded or r.deployment_recorded
                    or r.status!="OPERATOR_CONFLICT_REVIEW_PACKET_READY_NOT_DECIDED_NOT_APPROVED" or r.digest!=canonical_digest(p)):return False
        expected=[]
        if self._anchor:expected.append(("CORRECTION_READINESS_SOURCE_ANCHORED",self._anchor.digest))
        expected.extend(("CONSENT_CONFLICT_RECORDED",x.digest) for x in self._cases.values())
        if self._packet:expected.append(("READINESS_PACKET_RECORDED",self._packet.digest))
        if [(x["action"],x["artifact_digest"]) for x in self._events]!=expected:return False
        holds=[("CONSENT_CONFLICT_REQUIRES_OPERATOR_REVIEW",x.digest) for x in self._cases.values()]
        return [(x["reason"],x["attachment_digest"]) for x in self._holds]==holds
    def evidence(self):
        ok=self._integrity(); complete=len(self._cases)==20 and self._packet is not None
        matrix=WORKSTREAMS==tuple((6301+i*25,6325+i*25,n) for i,n in enumerate(WORKSTREAM_NAMES)) and len(CONTROL_ASPECTS)==25
        return {"range":[6301,6700],"control_count":400,"workstream_count":16,"controls_per_workstream":25,
                "control_matrix_valid":matrix,"registered_control_count":len(self._controls),"case_count":len(self._cases),
                "hold_count":len(self._holds),"event_count":len(self._events),"integrity_valid":ok,"complete_operator_conflict_review_evidence":complete and ok,
                "maximum_state":"OPERATOR_CONFLICT_REVIEW_PACKET_READY_NOT_DECIDED_NOT_APPROVED" if self._packet else "OPERATOR_CONFLICT_REVIEW_INCOMPLETE",
                "applied_lesson_ids":list(APPLIED_LESSONS),"applied_rule_ids":list(APPLIED_RULES),
                "external_calls":0,"document_transmissions":0,"electronic_signatures":0,"external_pg_calls":0,"card_network_calls":0,
                "payment_approvals":0,"cancellations":0,"refunds":0,"settlements":0,"transfers":0,"ledger_writes":0,
                "credential_reads":0,"deployments":0,"policy_prompt_weight_changes":0,"published":False,"decision_recorded":False,
                "consent_recorded":False,"approval_recorded":False,"activation_recorded":False}
