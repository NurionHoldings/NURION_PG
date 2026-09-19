"""Synthetic/in-memory non-binding resolution alternative simulation #6701-#7100."""
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest

WORKSTREAM_NAMES = (
    "CONFLICT_REVIEW_PACKET_ANCHOR", "LESSON_RULE_REGISTRY_BINDING",
    "TENANT_CONDITION_DOCUMENT", "NURION_CONDITION_DOCUMENT",
    "UPSTREAM_CONDITION_DOCUMENT", "FOUR_DIRECTION_ALTERNATIVE_ROUTE",
    "SCOPE_ALTERNATIVE", "TIMING_ALTERNATIVE", "DATA_MEANING_ALTERNATIVE",
    "RESPONSIBILITY_ALTERNATIVE", "RESIDUAL_RISK_ALTERNATIVE",
    "CONDITION_IMPACT_RISK_COMPARISON", "SOURCE_COMPILER_LINEAGE",
    "APPEND_ONLY_SIMULATION_HOLD", "INDEPENDENT_SIMULATION_PACKET",
    "NON_BINDING_NON_RECOMMENDATION_BOUNDARY",
)
WORKSTREAMS = tuple((6701+i*25, 6725+i*25, n) for i,n in enumerate(WORKSTREAM_NAMES))
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
DIMENSIONS=("SCOPE","TIMING","DATA_MEANING","RESPONSIBILITY","RESIDUAL_RISK")
APPLIED_LESSONS=("ARL-3901-001","ARL-4301-001","ARL-4301-002","ARL-4301-003","ARL-4701-001","ARL-5101-001","ARL-5501-001","ARL-5901-001","ARL-6301-001","ARL-6701-001")
APPLIED_RULES=tuple(f"ARP-{i:02}" for i in range(1,9))

def _syn(v,k): return isinstance(v,str) and v.startswith(f"synthetic:{k}:")
def _hex(v): return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _identity(v): return v.rsplit(":",1)[-1].casefold()

@dataclass(frozen=True)
class Control: control_id:int; workstream:str; aspect:str; requirement_ref:str; fixture_digest:str; expected_result:str; digest:str
@dataclass(frozen=True)
class ConflictReviewAnchor:
    anchor_id:str; conflict_review_packet_digest:str; conflict_case_set_digest:str; lesson_registry_digest:str
    remediation_manifest_digest:str; applied_lesson_ids:tuple[str,...]; applied_rule_ids:tuple[str,...]
    party_document_digests:tuple[tuple[str,str],...]; route_binding_digests:tuple[tuple[str,str],...]
    source_sequence:int; is_latest:bool; source_reviewers:tuple[str,str,str]; source_compilers:tuple[str,str]
    source_lineage_digest:str; status:str; digest:str
@dataclass(frozen=True)
class AlternativeCase:
    case_id:str; flow:str; dimension:str; source_party:str; counterparty:str; anchor_digest:str
    condition_digest:str; impact_digest:str; residual_risk_digest:str; comparison_digest:str; route_binding_digest:str
    simulator:str; evaluator:str; status:str; digest:str
@dataclass(frozen=True)
class SimulationPacket:
    packet_id:str; anchor_digest:str; case_set_digest:str; compiler:str; source_reviewers:tuple[str,str,str]
    source_compilers:tuple[str,str]; source_lineage_digest:str
    complete:bool; published:bool; recommended:bool; consent_recorded:bool; decision_recorded:bool
    approval_recorded:bool; activation_recorded:bool; deployment_recorded:bool; status:str; digest:str

class SyntheticNonbindingResolutionAlternativeSimulation:
    """Creates inert comparisons only; it cannot recommend, consent, decide, approve, or execute."""
    def __init__(self):
        self._controls={}; self._anchor=None; self._cases={}; self._packet=None
        self._events=[]; self._holds=[]; self._lock=RLock()

    def add_control(self,cid,workstream,aspect,requirement_ref,fixture_digest,expected_result):
        p=dict(control_id=cid,workstream=workstream,aspect=aspect,requirement_ref=requirement_ref,fixture_digest=fixture_digest,expected_result=expected_result)
        row=Control(**p,digest=canonical_digest(p))
        with self._lock:
            if not self._valid_control(row): raise GovernanceRejected("valid #6701-#7100 control required")
            old=self._controls.get(cid)
            if old:
                if old==row:return old
                raise GovernanceRejected("control conflict")
            self._controls[cid]=row; return row

    def anchor_source(self,anchor_id,conflict_review_packet_digest,conflict_case_set_digest,lesson_registry_digest,
                      remediation_manifest_digest,applied_lesson_ids,applied_rule_ids,party_document_digests,
                      route_binding_digests,source_sequence,is_latest,source_reviewers,source_compilers):
        reviewers=tuple(source_reviewers);compilers=tuple(source_compilers)
        p=dict(anchor_id=anchor_id,conflict_review_packet_digest=conflict_review_packet_digest,
               conflict_case_set_digest=conflict_case_set_digest,lesson_registry_digest=lesson_registry_digest,
               remediation_manifest_digest=remediation_manifest_digest,applied_lesson_ids=tuple(applied_lesson_ids),
               applied_rule_ids=tuple(applied_rule_ids),party_document_digests=tuple(party_document_digests),
               route_binding_digests=tuple(route_binding_digests),source_sequence=source_sequence,is_latest=is_latest,
               source_reviewers=reviewers,source_compilers=compilers,
               source_lineage_digest=canonical_digest(("CONFLICT_REVIEW_SOURCE_LINEAGE",conflict_review_packet_digest,reviewers,compilers)),
               status="CONFLICT_REVIEW_ANCHORED_NOT_DECIDED")
        row=ConflictReviewAnchor(**p,digest=canonical_digest(p))
        with self._lock:
            if not self._anchor_valid(row): raise GovernanceRejected("latest semantically-bound conflict review source required")
            if self._anchor:
                if self._anchor==row:return self._anchor
                raise GovernanceRejected("anchor conflict")
            self._anchor=row;self._event("CONFLICT_REVIEW_SOURCE_ANCHORED",row.digest);return row

    def add_case(self,case_id,flow,dimension,condition_digest,impact_digest,residual_risk_digest,comparison_digest,simulator,evaluator):
        with self._lock:
            if not self._anchor:raise GovernanceRejected("source anchor required")
            source,counterparty=FLOW_PARTIES.get(flow,(None,None));route=dict(self._anchor.route_binding_digests).get(flow)
            p=dict(case_id=case_id,flow=flow,dimension=dimension,source_party=source,counterparty=counterparty,
                   anchor_digest=self._anchor.digest,condition_digest=condition_digest,impact_digest=impact_digest,
                   residual_risk_digest=residual_risk_digest,comparison_digest=comparison_digest,route_binding_digest=route,
                   simulator=simulator,evaluator=evaluator,status="NONBINDING_ALTERNATIVE_HELD_NOT_RECOMMENDED")
            row=AlternativeCase(**p,digest=canonical_digest(p));key=(flow,dimension)
            if not self._case_valid(row,key):raise GovernanceRejected("synthetic bound alternative case required")
            old=self._cases.get(key)
            if old:
                if old==row:return old
                raise GovernanceRejected("case conflict")
            self._cases[key]=row;self._event("NONBINDING_ALTERNATIVE_SIMULATED",row.digest);self._hold("ALTERNATIVE_REQUIRES_HUMAN_REVIEW",row.digest);return row

    def finalize(self,packet_id,compiler):
        with self._lock:
            if self._packet or set(self._cases)!={(f,d) for f in FLOWS for d in DIMENSIONS} or not self._integrity():raise GovernanceRejected("exact intact alternative set required")
            if not _syn(packet_id,"nonbinding-simulation-packet") or not _syn(compiler,"simulation-compiler"):raise GovernanceRejected("synthetic compiler required")
            occupied=self._anchor.source_reviewers+self._anchor.source_compilers
            if _identity(compiler) in {_identity(x) for x in occupied}:raise GovernanceRejected("independent compiler required")
            case_set=canonical_digest(tuple(self._cases[k].digest for k in sorted(self._cases)))
            p=dict(packet_id=packet_id,anchor_digest=self._anchor.digest,case_set_digest=case_set,compiler=compiler,
                   source_reviewers=self._anchor.source_reviewers,source_compilers=self._anchor.source_compilers,
                   source_lineage_digest=self._anchor.source_lineage_digest,complete=True,published=False,recommended=False,
                   consent_recorded=False,decision_recorded=False,approval_recorded=False,activation_recorded=False,
                   deployment_recorded=False,status="NONBINDING_ALTERNATIVE_PACKET_READY_NOT_RECOMMENDED_NOT_DECIDED")
            self._packet=SimulationPacket(**p,digest=canonical_digest(p));self._event("SIMULATION_PACKET_RECORDED",self._packet.digest);return self._packet

    def _expected(self,cid):i=cid-6701;return WORKSTREAM_NAMES[i//25],CONTROL_ASPECTS[i%25]
    def _valid_control(self,r):
        p={k:v for k,v in r.__dict__.items() if k!="digest"}
        return (isinstance(r.control_id,int) and not isinstance(r.control_id,bool) and 6701<=r.control_id<=7100
                and self._expected(r.control_id)==(r.workstream,r.aspect)
                and r.requirement_ref==f"synthetic:alternative-requirement:{(r.control_id-6701)//25:02}"
                and _hex(r.fixture_digest) and r.expected_result==("EXPECTED_REJECTION" if r.aspect in NEGATIVE else "PASS")
                and r.digest==canonical_digest(p))
    def _registry_valid(self):return set(self._controls)==set(range(6701,7101)) and all(k==v.control_id and self._valid_control(v) for k,v in self._controls.items())
    def _anchor_valid(self,a):
        p={k:v for k,v in a.__dict__.items() if k!="digest"};docs=dict(a.party_document_digests)
        routes=tuple((f,canonical_digest(("NONBINDING_ALTERNATIVE_ROUTE",f,FLOW_PARTIES[f],tuple(a.party_document_digests),a.conflict_review_packet_digest))) for f in FLOWS)
        identities=a.source_reviewers+a.source_compilers
        return (self._registry_valid() and _syn(a.anchor_id,"alternative-anchor")
                and all(_hex(x) for x in (a.conflict_review_packet_digest,a.conflict_case_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest))
                and a.applied_lesson_ids==APPLIED_LESSONS and a.applied_rule_ids==APPLIED_RULES
                and tuple(x for x,_ in a.party_document_digests)==PARTIES and len(docs)==3 and all(_hex(x) for x in docs.values())
                and a.route_binding_digests==routes and isinstance(a.source_sequence,int) and not isinstance(a.source_sequence,bool) and a.source_sequence>0 and a.is_latest is True
                and len(a.source_reviewers)==3 and all(_syn(x,k) for x,k in zip(a.source_reviewers,("readiness-reviewer","preflight-reviewer","reconsideration-reviewer")))
                and len(a.source_compilers)==2 and all(_syn(x,"packet-compiler") for x in a.source_compilers)
                and len({_identity(x) for x in identities})==5
                and a.source_lineage_digest==canonical_digest(("CONFLICT_REVIEW_SOURCE_LINEAGE",a.conflict_review_packet_digest,a.source_reviewers,a.source_compilers))
                and a.status=="CONFLICT_REVIEW_ANCHORED_NOT_DECIDED" and a.digest==canonical_digest(p))
    def _case_valid(self,r,key):
        if not self._anchor:return False
        p={k:v for k,v in r.__dict__.items() if k!="digest"};source,counterparty=FLOW_PARTIES.get(r.flow,(None,None));route=dict(self._anchor.route_binding_digests).get(r.flow);doc=dict(self._anchor.party_document_digests).get(source)
        condition=canonical_digest(("ALTERNATIVE_CONDITION",source,doc,r.flow,r.dimension,route,self._anchor.conflict_case_set_digest))
        impact=canonical_digest(("ALTERNATIVE_IMPACT",counterparty,r.flow,r.dimension,condition,route))
        risk=canonical_digest(("ALTERNATIVE_RESIDUAL_RISK",source,counterparty,r.flow,r.dimension,condition,impact,route))
        comparison=canonical_digest(("NONBINDING_COMPARISON",r.flow,r.dimension,condition,impact,risk,self._anchor.conflict_review_packet_digest))
        simulator=f"synthetic:alternative-simulator:{source}";evaluator=f"synthetic:risk-evaluator:{counterparty}"
        return (key==(r.flow,r.dimension) and r.flow in FLOWS and r.dimension in DIMENSIONS and _syn(r.case_id,"alternative-case")
                and (r.source_party,r.counterparty)==(source,counterparty) and r.anchor_digest==self._anchor.digest
                and (r.condition_digest,r.impact_digest,r.residual_risk_digest,r.comparison_digest)==(condition,impact,risk,comparison)
                and r.route_binding_digest==route and r.simulator==simulator and r.evaluator==evaluator
                and _identity(r.simulator)!=_identity(r.evaluator) and r.status=="NONBINDING_ALTERNATIVE_HELD_NOT_RECOMMENDED"
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
            r=self._packet;p={k:v for k,v in r.__dict__.items() if k!="digest"};case_set=canonical_digest(tuple(self._cases[k].digest for k in sorted(self._cases)));occupied=self._anchor.source_reviewers+self._anchor.source_compilers
            if (not _syn(r.packet_id,"nonbinding-simulation-packet") or r.anchor_digest!=self._anchor.digest or r.case_set_digest!=case_set or not _syn(r.compiler,"simulation-compiler")
                    or r.source_reviewers!=self._anchor.source_reviewers or r.source_compilers!=self._anchor.source_compilers
                    or r.source_lineage_digest!=self._anchor.source_lineage_digest or _identity(r.compiler) in {_identity(x) for x in occupied}
                    or not r.complete or r.published or r.recommended or r.consent_recorded or r.decision_recorded or r.approval_recorded or r.activation_recorded or r.deployment_recorded
                    or r.status!="NONBINDING_ALTERNATIVE_PACKET_READY_NOT_RECOMMENDED_NOT_DECIDED" or r.digest!=canonical_digest(p)):return False
        expected=[]
        if self._anchor:expected.append(("CONFLICT_REVIEW_SOURCE_ANCHORED",self._anchor.digest))
        expected.extend(("NONBINDING_ALTERNATIVE_SIMULATED",x.digest) for x in self._cases.values())
        if self._packet:expected.append(("SIMULATION_PACKET_RECORDED",self._packet.digest))
        if [(x["action"],x["artifact_digest"]) for x in self._events]!=expected:return False
        holds=[("ALTERNATIVE_REQUIRES_HUMAN_REVIEW",x.digest) for x in self._cases.values()]
        return [(x["reason"],x["attachment_digest"]) for x in self._holds]==holds
    def evidence(self):
        ok=self._integrity();complete=len(self._cases)==20 and self._packet is not None
        matrix=WORKSTREAMS==tuple((6701+i*25,6725+i*25,n) for i,n in enumerate(WORKSTREAM_NAMES)) and len(CONTROL_ASPECTS)==25
        return {"range":[6701,7100],"control_count":400,"workstream_count":16,"controls_per_workstream":25,"control_matrix_valid":matrix,
                "registered_control_count":len(self._controls),"case_count":len(self._cases),"hold_count":len(self._holds),"event_count":len(self._events),
                "integrity_valid":ok,"complete_nonbinding_simulation_evidence":complete and ok,
                "maximum_state":"NONBINDING_ALTERNATIVE_PACKET_READY_NOT_RECOMMENDED_NOT_DECIDED" if self._packet else "NONBINDING_SIMULATION_INCOMPLETE",
                "applied_lesson_ids":list(APPLIED_LESSONS),"applied_rule_ids":list(APPLIED_RULES),"external_calls":0,"document_transmissions":0,
                "electronic_signatures":0,"external_pg_calls":0,"card_network_calls":0,"payment_approvals":0,"cancellations":0,"refunds":0,
                "settlements":0,"transfers":0,"ledger_writes":0,"credential_reads":0,"deployments":0,"policy_prompt_weight_changes":0,
                "published":False,"recommended":False,"consent_recorded":False,"decision_recorded":False,"approval_recorded":False,"activation_recorded":False}
