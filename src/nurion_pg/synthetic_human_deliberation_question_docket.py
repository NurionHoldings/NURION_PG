"""Synthetic/in-memory human deliberation question docket controls #7101-#7500."""
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest

WORKSTREAM_NAMES=(
    "NONBINDING_SIMULATION_SOURCE_ANCHOR","LESSON_RULE_REGISTRY_BINDING","TENANT_QUESTION_DOCUMENT",
    "NURION_QUESTION_DOCUMENT","UPSTREAM_QUESTION_DOCUMENT","FOUR_DIRECTION_QUESTION_ROUTE",
    "ASSUMPTION_QUESTION","RESIDUAL_RISK_QUESTION","ADDITIONAL_EVIDENCE_REQUEST","UNRESOLVED_MEANING_QUESTION",
    "QUESTION_DOCUMENT_PROVENANCE","SOURCE_REVIEWER_COMPILER_LINEAGE","HUMAN_CHAIR_ROLE_SEPARATION",
    "APPEND_ONLY_QUESTION_HOLD","INDEPENDENT_DELIBERATION_DOCKET","NON_DECISION_NON_EXECUTION_BOUNDARY",
)
WORKSTREAMS=tuple((7101+i*25,7125+i*25,n) for i,n in enumerate(WORKSTREAM_NAMES))
CONTROL_ASPECTS=(
    "input_schema","required_fields","semantic_label","source_type","tenant_scope","role_scope",
    "state_precondition","latest_sequence","source_binding","digest_recalculation","negative_path","missing_input",
    "duplicate_input","replay","conflict","stale_version","concurrency","partial_batch","ordering","append_only",
    "hold_propagation","review_independence","receipt_lineage","operator_gate","non_execution",
)
NEGATIVE=frozenset({"negative_path","missing_input","duplicate_input","replay","conflict","stale_version","partial_batch"})
PARTIES=("TENANT_AGENCY","NURION_PG","UPSTREAM_PG")
FLOWS=("tenant_to_nurion","nurion_to_upstream","upstream_to_nurion","nurion_to_tenant")
FLOW_PARTIES={"tenant_to_nurion":("TENANT_AGENCY","NURION_PG"),"nurion_to_upstream":("NURION_PG","UPSTREAM_PG"),"upstream_to_nurion":("UPSTREAM_PG","NURION_PG"),"nurion_to_tenant":("NURION_PG","TENANT_AGENCY")}
QUESTION_KINDS=("ASSUMPTION","RESIDUAL_RISK","ADDITIONAL_EVIDENCE","UNRESOLVED_MEANING","SAFE_BOUNDARY")
APPLIED_LESSONS=("ARL-3901-001","ARL-4301-001","ARL-4301-002","ARL-4301-003","ARL-4701-001","ARL-5101-001","ARL-5501-001","ARL-5901-001","ARL-6301-001","ARL-6701-001","ARL-7101-001")
APPLIED_RULES=tuple(f"ARP-{i:02}" for i in range(1,9))

def _syn(v,k):return isinstance(v,str) and v.startswith(f"synthetic:{k}:")
def _hex(v):return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _identity(v):return v.rsplit(":",1)[-1].casefold()

@dataclass(frozen=True)
class Control: control_id:int;workstream:str;aspect:str;requirement_ref:str;fixture_digest:str;expected_result:str;digest:str
@dataclass(frozen=True)
class SimulationAnchor:
    anchor_id:str;simulation_packet_digest:str;simulation_case_set_digest:str;lesson_registry_digest:str;remediation_manifest_digest:str
    applied_lesson_ids:tuple[str,...];applied_rule_ids:tuple[str,...];party_document_digests:tuple[tuple[str,str],...]
    route_binding_digests:tuple[tuple[str,str],...];source_sequence:int;is_latest:bool;source_reviewers:tuple[str,str,str]
    source_compilers:tuple[str,str,str];source_lineage_digest:str;status:str;digest:str
@dataclass(frozen=True)
class DeliberationQuestion:
    question_id:str;flow:str;kind:str;source_party:str;counterparty:str;anchor_digest:str;source_document_digest:str
    route_binding_digest:str;question_digest:str;assumption_digest:str;residual_risk_digest:str;evidence_request_digest:str
    drafter:str;human_reviewer:str;status:str;digest:str
@dataclass(frozen=True)
class QuestionDocket:
    docket_id:str;anchor_digest:str;question_set_digest:str;chair:str;source_reviewers:tuple[str,str,str]
    source_compilers:tuple[str,str,str];source_lineage_digest:str;complete:bool;published:bool;recommended:bool
    consent_recorded:bool;decision_recorded:bool;approval_recorded:bool;activation_recorded:bool;deployment_recorded:bool;status:str;digest:str

class SyntheticHumanDeliberationQuestionDocket:
    """Builds an inert question docket; humans still provide evidence and make every decision."""
    def __init__(self):
        self._controls={};self._anchor=None;self._questions={};self._docket=None;self._events=[];self._holds=[];self._lock=RLock()

    def add_control(self,cid,workstream,aspect,requirement_ref,fixture_digest,expected_result):
        p=dict(control_id=cid,workstream=workstream,aspect=aspect,requirement_ref=requirement_ref,fixture_digest=fixture_digest,expected_result=expected_result);r=Control(**p,digest=canonical_digest(p))
        with self._lock:
            if not self._valid_control(r):raise GovernanceRejected("valid #7101-#7500 control required")
            old=self._controls.get(cid)
            if old:
                if old==r:return old
                raise GovernanceRejected("control conflict")
            self._controls[cid]=r;return r

    def anchor_source(self,anchor_id,simulation_packet_digest,simulation_case_set_digest,lesson_registry_digest,remediation_manifest_digest,
                      applied_lesson_ids,applied_rule_ids,party_document_digests,route_binding_digests,source_sequence,is_latest,source_reviewers,source_compilers):
        reviewers=tuple(source_reviewers);compilers=tuple(source_compilers)
        p=dict(anchor_id=anchor_id,simulation_packet_digest=simulation_packet_digest,simulation_case_set_digest=simulation_case_set_digest,
               lesson_registry_digest=lesson_registry_digest,remediation_manifest_digest=remediation_manifest_digest,
               applied_lesson_ids=tuple(applied_lesson_ids),applied_rule_ids=tuple(applied_rule_ids),party_document_digests=tuple(party_document_digests),
               route_binding_digests=tuple(route_binding_digests),source_sequence=source_sequence,is_latest=is_latest,source_reviewers=reviewers,
               source_compilers=compilers,source_lineage_digest=canonical_digest(("SIMULATION_SOURCE_LINEAGE",simulation_packet_digest,reviewers,compilers)),
               status="NONBINDING_SIMULATION_ANCHORED_NOT_RECOMMENDED")
        r=SimulationAnchor(**p,digest=canonical_digest(p))
        with self._lock:
            if not self._anchor_valid(r):raise GovernanceRejected("latest semantically-bound simulation source required")
            if self._anchor:
                if self._anchor==r:return self._anchor
                raise GovernanceRejected("anchor conflict")
            self._anchor=r;self._event("SIMULATION_SOURCE_ANCHORED",r.digest);return r

    def add_question(self,question_id,flow,kind,question_digest,assumption_digest,residual_risk_digest,evidence_request_digest,drafter,human_reviewer):
        with self._lock:
            if not self._anchor:raise GovernanceRejected("source anchor required")
            source,counter=FLOW_PARTIES.get(flow,(None,None));docs=dict(self._anchor.party_document_digests);route=dict(self._anchor.route_binding_digests).get(flow)
            p=dict(question_id=question_id,flow=flow,kind=kind,source_party=source,counterparty=counter,anchor_digest=self._anchor.digest,
                   source_document_digest=docs.get(source),route_binding_digest=route,question_digest=question_digest,assumption_digest=assumption_digest,
                   residual_risk_digest=residual_risk_digest,evidence_request_digest=evidence_request_digest,drafter=drafter,human_reviewer=human_reviewer,
                   status="QUESTION_HELD_FOR_HUMAN_DELIBERATION")
            r=DeliberationQuestion(**p,digest=canonical_digest(p));key=(flow,kind)
            if not self._question_valid(r,key):raise GovernanceRejected("bound synthetic human question required")
            old=self._questions.get(key)
            if old:
                if old==r:return old
                raise GovernanceRejected("question conflict")
            self._questions[key]=r;self._event("DELIBERATION_QUESTION_RECORDED",r.digest);self._hold("HUMAN_ANSWER_AND_EVIDENCE_REQUIRED",r.digest);return r

    def finalize(self,docket_id,chair):
        with self._lock:
            if self._docket or set(self._questions)!={(f,k) for f in FLOWS for k in QUESTION_KINDS} or not self._integrity():raise GovernanceRejected("exact intact question set required")
            if not _syn(docket_id,"human-question-docket") or not _syn(chair,"human-deliberation-chair"):raise GovernanceRejected("synthetic human chair required")
            occupied=(self._anchor.source_reviewers+self._anchor.source_compilers
                      +tuple(x.drafter for x in self._questions.values())
                      +tuple(x.human_reviewer for x in self._questions.values()))
            if _identity(chair) in {_identity(x) for x in occupied}:raise GovernanceRejected("independent human chair required")
            qset=canonical_digest(tuple(self._questions[k].digest for k in sorted(self._questions)))
            p=dict(docket_id=docket_id,anchor_digest=self._anchor.digest,question_set_digest=qset,chair=chair,
                   source_reviewers=self._anchor.source_reviewers,source_compilers=self._anchor.source_compilers,source_lineage_digest=self._anchor.source_lineage_digest,
                   complete=True,published=False,recommended=False,consent_recorded=False,decision_recorded=False,approval_recorded=False,
                   activation_recorded=False,deployment_recorded=False,status="HUMAN_DELIBERATION_QUESTION_DOCKET_READY_NOT_ANSWERED_NOT_DECIDED")
            self._docket=QuestionDocket(**p,digest=canonical_digest(p));self._event("QUESTION_DOCKET_RECORDED",self._docket.digest);return self._docket

    def _expected(self,cid):i=cid-7101;return WORKSTREAM_NAMES[i//25],CONTROL_ASPECTS[i%25]
    def _valid_control(self,r):
        p={k:v for k,v in r.__dict__.items() if k!="digest"}
        return isinstance(r.control_id,int) and not isinstance(r.control_id,bool) and 7101<=r.control_id<=7500 and self._expected(r.control_id)==(r.workstream,r.aspect) and r.requirement_ref==f"synthetic:question-requirement:{(r.control_id-7101)//25:02}" and _hex(r.fixture_digest) and r.expected_result==("EXPECTED_REJECTION" if r.aspect in NEGATIVE else "PASS") and r.digest==canonical_digest(p)
    def _registry_valid(self):return set(self._controls)==set(range(7101,7501)) and all(k==v.control_id and self._valid_control(v) for k,v in self._controls.items())
    def _anchor_valid(self,a):
        p={k:v for k,v in a.__dict__.items() if k!="digest"};docs=dict(a.party_document_digests)
        routes=tuple((f,canonical_digest(("HUMAN_QUESTION_ROUTE",f,FLOW_PARTIES[f],tuple(a.party_document_digests),a.simulation_packet_digest))) for f in FLOWS);identities=a.source_reviewers+a.source_compilers
        return self._registry_valid() and _syn(a.anchor_id,"question-anchor") and all(_hex(x) for x in (a.simulation_packet_digest,a.simulation_case_set_digest,a.lesson_registry_digest,a.remediation_manifest_digest)) and a.applied_lesson_ids==APPLIED_LESSONS and a.applied_rule_ids==APPLIED_RULES and tuple(x for x,_ in a.party_document_digests)==PARTIES and len(docs)==3 and all(_hex(x) for x in docs.values()) and a.route_binding_digests==routes and isinstance(a.source_sequence,int) and not isinstance(a.source_sequence,bool) and a.source_sequence>0 and a.is_latest is True and len(a.source_reviewers)==3 and all(_syn(x,k) for x,k in zip(a.source_reviewers,("readiness-reviewer","preflight-reviewer","reconsideration-reviewer"))) and len(a.source_compilers)==3 and all(_syn(x,"packet-compiler") for x in a.source_compilers) and len({_identity(x) for x in identities})==6 and a.source_lineage_digest==canonical_digest(("SIMULATION_SOURCE_LINEAGE",a.simulation_packet_digest,a.source_reviewers,a.source_compilers)) and a.status=="NONBINDING_SIMULATION_ANCHORED_NOT_RECOMMENDED" and a.digest==canonical_digest(p)
    def _question_valid(self,r,key):
        if not self._anchor:return False
        p={k:v for k,v in r.__dict__.items() if k!="digest"};source,counter=FLOW_PARTIES.get(r.flow,(None,None));doc=dict(self._anchor.party_document_digests).get(source);route=dict(self._anchor.route_binding_digests).get(r.flow)
        assumption=canonical_digest(("QUESTION_ASSUMPTION",source,doc,r.flow,r.kind,route,self._anchor.simulation_case_set_digest));risk=canonical_digest(("QUESTION_RESIDUAL_RISK",source,counter,r.flow,r.kind,assumption,route));request=canonical_digest(("ADDITIONAL_EVIDENCE_REQUEST",counter,r.flow,r.kind,assumption,risk,route));question=canonical_digest(("HUMAN_DELIBERATION_QUESTION",r.flow,r.kind,assumption,risk,request,self._anchor.simulation_packet_digest))
        return key==(r.flow,r.kind) and r.flow in FLOWS and r.kind in QUESTION_KINDS and _syn(r.question_id,"deliberation-question") and (r.source_party,r.counterparty)==(source,counter) and r.anchor_digest==self._anchor.digest and r.source_document_digest==doc and r.route_binding_digest==route and (r.question_digest,r.assumption_digest,r.residual_risk_digest,r.evidence_request_digest)==(question,assumption,risk,request) and r.drafter==f"synthetic:question-drafter:{source}" and r.human_reviewer==f"synthetic:human-reviewer:{counter}" and _identity(r.drafter)!=_identity(r.human_reviewer) and r.status=="QUESTION_HELD_FOR_HUMAN_DELIBERATION" and r.digest==canonical_digest(p)
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
        if not self._registry_valid() or not self._chain(self._events,True) or not self._chain(self._holds,False) or (self._anchor and not self._anchor_valid(self._anchor)) or any(not self._question_valid(v,k) for k,v in self._questions.items()):return False
        if self._docket:
            r=self._docket;p={k:v for k,v in r.__dict__.items() if k!="digest"};qset=canonical_digest(tuple(self._questions[k].digest for k in sorted(self._questions)));occupied=(self._anchor.source_reviewers+self._anchor.source_compilers+tuple(x.drafter for x in self._questions.values())+tuple(x.human_reviewer for x in self._questions.values()))
            if not _syn(r.docket_id,"human-question-docket") or r.anchor_digest!=self._anchor.digest or r.question_set_digest!=qset or not _syn(r.chair,"human-deliberation-chair") or r.source_reviewers!=self._anchor.source_reviewers or r.source_compilers!=self._anchor.source_compilers or r.source_lineage_digest!=self._anchor.source_lineage_digest or _identity(r.chair) in {_identity(x) for x in occupied} or not r.complete or r.published or r.recommended or r.consent_recorded or r.decision_recorded or r.approval_recorded or r.activation_recorded or r.deployment_recorded or r.status!="HUMAN_DELIBERATION_QUESTION_DOCKET_READY_NOT_ANSWERED_NOT_DECIDED" or r.digest!=canonical_digest(p):return False
        expected=[]
        if self._anchor:expected.append(("SIMULATION_SOURCE_ANCHORED",self._anchor.digest))
        expected.extend(("DELIBERATION_QUESTION_RECORDED",x.digest) for x in self._questions.values())
        if self._docket:expected.append(("QUESTION_DOCKET_RECORDED",self._docket.digest))
        if [(x["action"],x["artifact_digest"]) for x in self._events]!=expected:return False
        return [(x["reason"],x["attachment_digest"]) for x in self._holds]==[("HUMAN_ANSWER_AND_EVIDENCE_REQUIRED",x.digest) for x in self._questions.values()]
    def evidence(self):
        ok=self._integrity();complete=len(self._questions)==20 and self._docket is not None;matrix=WORKSTREAMS==tuple((7101+i*25,7125+i*25,n) for i,n in enumerate(WORKSTREAM_NAMES)) and len(CONTROL_ASPECTS)==25
        return {"range":[7101,7500],"control_count":400,"workstream_count":16,"controls_per_workstream":25,"control_matrix_valid":matrix,"registered_control_count":len(self._controls),"question_count":len(self._questions),"hold_count":len(self._holds),"event_count":len(self._events),"integrity_valid":ok,"complete_human_deliberation_evidence":complete and ok,"maximum_state":"HUMAN_DELIBERATION_QUESTION_DOCKET_READY_NOT_ANSWERED_NOT_DECIDED" if self._docket else "QUESTION_DOCKET_INCOMPLETE","applied_lesson_ids":list(APPLIED_LESSONS),"applied_rule_ids":list(APPLIED_RULES),"external_calls":0,"document_transmissions":0,"electronic_signatures":0,"external_pg_calls":0,"card_network_calls":0,"payment_approvals":0,"cancellations":0,"refunds":0,"settlements":0,"transfers":0,"ledger_writes":0,"credential_reads":0,"deployments":0,"policy_prompt_weight_changes":0,"published":False,"recommended":False,"consent_recorded":False,"decision_recorded":False,"approval_recorded":False,"activation_recorded":False}
