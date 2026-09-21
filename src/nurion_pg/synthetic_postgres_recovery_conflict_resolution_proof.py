"""Append-only recovery conflict-resolution docket contract #19901-#20300."""
from __future__ import annotations

from dataclasses import dataclass
from .arkaon.governance import GovernanceRejected,canonical_digest
from .synthetic_postgres_recovery_recommendation_concurrence_proof import APPLIED_LESSONS as PRIOR_LESSONS,APPLIED_RULES,STAGE_MAPPING as PRIOR_STAGE_MAPPING

APPLIED_LESSONS=tuple(sorted(PRIOR_LESSONS+("ARL-19901-001",)))
STAGE_MAPPING=PRIOR_STAGE_MAPPING+(("ARKAON-LESSONS-19901",(19901,20300)),)
RESOLUTION_STATE="RECOVERY_CONFLICT_RESOLUTION_NON_EXECUTABLE"
MAXIMUM_STATE="POSTGRES_RECOVERY_CONFLICT_RESOLUTION_PROOF_ONLY"

def _hex(value):return isinstance(value,str) and len(value)==64 and all(c in "0123456789abcdef" for c in value)

def canonical_conflict_set(rows):
    if not isinstance(rows,(tuple,list)) or not rows:raise GovernanceRejected("non-empty conflict set required")
    normalized=[]
    for row in rows:
        if not isinstance(row,(tuple,list)) or len(row)!=3:raise GovernanceRejected("exact conflict tuple required")
        concurrence_id,concurrence_digest,reviewer_subject=row
        if not isinstance(concurrence_id,str) or not concurrence_id or not _hex(concurrence_digest) or not isinstance(reviewer_subject,str) or not reviewer_subject:raise GovernanceRejected("complete conflict tuple required")
        normalized.append((concurrence_id,concurrence_digest,reviewer_subject))
    ordered=tuple(sorted(normalized))
    if len(ordered)!=len(set(ordered)) or len({row[0] for row in ordered})!=len(ordered):raise GovernanceRejected("unique conflict rows required")
    return ordered

def conflict_set_digest(rows):return canonical_digest(("NURION_RECOVERY_CONFLICT_SET_V1",canonical_conflict_set(rows)))

def deterministic_resolution_docket_id(recommendation_id,recommendation_digest,conflicts,resolution_key,author_subject,resolution_digest):
    if not all(isinstance(v,str) and v for v in (recommendation_id,resolution_key,author_subject)) or not _hex(recommendation_digest) or not _hex(resolution_digest):raise GovernanceRejected("complete resolution docket identity required")
    return "rrd_"+canonical_digest(("NURION_RECOVERY_CONFLICT_RESOLUTION_DOCKET_V1",recommendation_id,recommendation_digest,conflict_set_digest(conflicts),resolution_key,author_subject,resolution_digest))

def deterministic_resolution_round_id(docket_id,docket_digest,predecessor_round_id,predecessor_round_digest,round_number,reviewer_subject,verdict,rationale_digest,author_subject):
    if not all(isinstance(v,str) and v for v in (docket_id,reviewer_subject,author_subject)) or reviewer_subject==author_subject or not _hex(docket_digest) or not _hex(rationale_digest):raise GovernanceRejected("independent resolution round identity required")
    if verdict not in {"REVIEWED_HOLD","REVIEWED_NON_EXECUTABLE"} or not isinstance(round_number,int) or isinstance(round_number,bool) or round_number<1:raise GovernanceRejected("valid non-executable round required")
    genesis=round_number==1 and predecessor_round_id is None and predecessor_round_digest is None
    successor=round_number>1 and isinstance(predecessor_round_id,str) and bool(predecessor_round_id) and _hex(predecessor_round_digest)
    if not(genesis or successor):raise GovernanceRejected("exact predecessor-bound round required")
    return "rrx_"+canonical_digest(("NURION_RECOVERY_CONFLICT_RESOLUTION_ROUND_V1",docket_id,docket_digest,predecessor_round_id,predecessor_round_digest,round_number,reviewer_subject,verdict,rationale_digest))

@dataclass(frozen=True)
class ResolutionDocket:
    docket_id:str;recommendation_id:str;recommendation_digest:str;conflict_set_digest:str;resolution_key:str;author_subject:str;resolution_digest:str;state:str;digest:str

@dataclass(frozen=True)
class ResolutionRound:
    round_id:str;docket_id:str;docket_digest:str;predecessor_round_id:str|None;predecessor_round_digest:str|None;round_number:int;reviewer_subject:str;verdict:str;rationale_digest:str;state:str;digest:str

class ConflictResolutionLedger:
    def __init__(self):self._dockets={};self._rounds={};self._successors={}
    def add_docket(self,recommendation_id,recommendation_digest,conflicts,resolution_key,author_subject,resolution_digest):
        conflict_digest=conflict_set_digest(conflicts);docket_id=deterministic_resolution_docket_id(recommendation_id,recommendation_digest,conflicts,resolution_key,author_subject,resolution_digest);payload=dict(docket_id=docket_id,recommendation_id=recommendation_id,recommendation_digest=recommendation_digest,conflict_set_digest=conflict_digest,resolution_key=resolution_key,author_subject=author_subject,resolution_digest=resolution_digest,state=RESOLUTION_STATE);row=ResolutionDocket(**payload,digest=canonical_digest(payload))
        existing=self._dockets.get(docket_id)
        if existing and existing!=row:raise GovernanceRejected("resolution docket replay conflict")
        self._dockets[docket_id]=row;return row
    def add_round(self,docket_id,predecessor_round_id,predecessor_round_digest,round_number,reviewer_subject,verdict,rationale_digest):
        docket=self._dockets.get(docket_id)
        if not docket:raise GovernanceRejected("exact resolution docket required")
        round_id=deterministic_resolution_round_id(docket_id,docket.digest,predecessor_round_id,predecessor_round_digest,round_number,reviewer_subject,verdict,rationale_digest,docket.author_subject)
        if round_number==1:
            if any(row.docket_id==docket_id and row.round_number==1 for row in self._rounds.values()):raise GovernanceRejected("single genesis round required")
        else:
            predecessor=self._rounds.get(predecessor_round_id)
            if not predecessor or predecessor.digest!=predecessor_round_digest or predecessor.docket_id!=docket_id or predecessor.round_number!=round_number-1:raise GovernanceRejected("exact monotonic predecessor required")
            if predecessor_round_id in self._successors:raise GovernanceRejected("resolution round fork rejected")
        payload=dict(round_id=round_id,docket_id=docket_id,docket_digest=docket.digest,predecessor_round_id=predecessor_round_id,predecessor_round_digest=predecessor_round_digest,round_number=round_number,reviewer_subject=reviewer_subject,verdict=verdict,rationale_digest=rationale_digest,state=RESOLUTION_STATE);row=ResolutionRound(**payload,digest=canonical_digest(payload))
        existing=self._rounds.get(round_id)
        if existing and existing!=row:raise GovernanceRejected("resolution round replay conflict")
        self._rounds[round_id]=row
        if predecessor_round_id:self._successors[predecessor_round_id]=round_id
        return row
    def evidence(self):
        held=not self._rounds or any(row.verdict=="REVIEWED_HOLD" for row in self._rounds.values())
        return {"docket_count":len(self._dockets),"round_count":len(self._rounds),"held":held,"state":RESOLUTION_STATE,"payment_authority":False,"receipt_authority":False,"retry_authority":False,"approval_authority":False,"execution_authority":False,"production_database_writes":0,"maximum_state":MAXIMUM_STATE}
