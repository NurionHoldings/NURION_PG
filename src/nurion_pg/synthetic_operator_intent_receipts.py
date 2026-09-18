"""Synthetic operator consideration intent receipts #426-#440; non-authorizing."""
from __future__ import annotations
from dataclasses import dataclass,field
from datetime import datetime
from .arkaon.governance import GovernanceRejected,canonical_digest
def _d(v):return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _s(v,p="synthetic:"):return isinstance(v,str) and v.startswith(p)
@dataclass(frozen=True)
class IntentStage:feature:int;state:str;payload:dict[str,object];previous_digest:str;digest:str;key:str
@dataclass
class OperatorIntentReceipts:
 packet_digest:str;policy_digest:str
 stages:list[IntentStage]=field(default_factory=list);_keys:dict[str,tuple[str,IntentStage]]=field(default_factory=dict)
 def __post_init__(self):
  if not _d(self.packet_digest) or not _d(self.policy_digest):raise GovernanceRejected("immutable packet and policy required")
 def _add(self,f,state,payload,key,v):
  if not _s(key,"synthetic:key:"):raise GovernanceRejected("synthetic key required")
  fp=canonical_digest({"feature":f,"payload":payload})
  if key in self._keys:
   old,item=self._keys[key]
   if old!=fp:raise GovernanceRejected("idempotency conflict")
   return item
  if v!=len(self.stages) or f!=426+len(self.stages):raise GovernanceRejected("ordered current version required")
  prev=self.stages[-1].digest if self.stages else self.packet_digest;item=IntentStage(f,state,payload,prev,canonical_digest({"feature":f,"state":state,"payload":payload,"previous_digest":prev}),key);self.stages.append(item);self._keys[key]=(fp,item);return item
 def admit(self,state,packet_selection,blockers,assigned_operator,key,v=0):
  allowed_blockers={"CRITERIA_FAILED","ROLLBACK_TRIGGERED","FAIRNESS_CONCERN","CAPACITY_CONCERN","NONE"}
  if state!="SYNTHETIC_SHADOW_READINESS_REVIEW_COMPLETED" or packet_selection not in {"HOLD","REQUEST_REVISION","SUBMIT_FOR_OPERATOR_REVIEW"} or tuple(sorted(blockers))!=blockers or not blockers or len(blockers)!=len(set(blockers)) or not set(blockers)<=allowed_blockers or ("NONE" in blockers and len(blockers)!=1) or packet_selection=="SUBMIT_FOR_OPERATOR_REVIEW" and blockers!=("NONE",) or packet_selection!="SUBMIT_FOR_OPERATOR_REVIEW" and blockers==("NONE",) or not _s(assigned_operator,"synthetic:operator:"):raise GovernanceRejected("consistent readiness packet required")
  return self._add(426,"READINESS_PACKET_ADMITTED",{"selection":packet_selection,"blockers":blockers,"assigned_operator":assigned_operator},key,v)
 def bind_scope(self,project,features,purpose,key,v):
  if project!="NURION_PG" or features!=(381,425) or purpose!="READ_ONLY_CONSIDERATION":raise GovernanceRejected("fixed project scope required")
  return self._add(427,"INTENT_SCOPE_BOUND",{"project":project,"features":features,"purpose":purpose},key,v)
 def validity(self,issued,expires,now,key,v):
  if any(x.tzinfo is None for x in (issued,expires,now)) or not issued<=now<expires:raise GovernanceRejected("currently valid aware window required")
  return self._add(428,"INTENT_VALIDITY_CHECKED",{"issued":issued.isoformat(),"expires":expires.isoformat(),"as_of":now.isoformat()},key,v)
 def actor(self,operator,packet_operator,key,v):
  assigned=self.stages[0].payload["assigned_operator"] if self.stages else None
  if not _s(operator,"synthetic:operator:") or operator!=packet_operator or operator!=assigned:raise GovernanceRejected("packet-bound synthetic operator required")
  return self._add(429,"OPERATOR_IDENTITY_BOUND",{"operator":operator},key,v)
 def intent(self,code,key,v):
  allowed={"ACKNOWLEDGE_ONLY","REQUEST_REVISION","DEFER_CONSIDERATION","CLOSE_CONSIDERATION"}
  selection=self.stages[0].payload["selection"]
  if code not in allowed:raise GovernanceRejected("selection-bound intent code required")
  return self._add(430,"OPERATOR_INTENT_RECORDED",{"code":code,"authorization":False},key,v)
 def prerequisites(self,checks,key,v):
  required=("DIGESTS","NON_AUTHORITY","SAFETY","SCOPE")
  if checks!=required:raise GovernanceRejected("complete prerequisite checks required")
  return self._add(431,"INTENT_PREREQUISITES_VERIFIED",{"checks":checks},key,v)
 def reviewer(self,operator,reviewer,key,v):
  if operator!=self.stages[3].payload["operator"] or not _s(reviewer,"synthetic:reviewer:") or operator==reviewer:raise GovernanceRejected("independent reviewer required")
  return self._add(432,"INTENT_REVIEWER_ASSIGNED",{"operator":operator,"reviewer":reviewer},key,v)
 def nonce(self,value,key,v):
  if not _s(value,"synthetic:nonce:") or len(value)<24:raise GovernanceRejected("strong synthetic nonce required")
  return self._add(433,"INTENT_NONCE_BOUND",{"nonce_digest":canonical_digest(value)},key,v)
 def canonicalize(self,fields,key,v):
  required=("code","operator","packet_digest","scope_digest")
  if fields!=required:raise GovernanceRejected("fixed canonical intent fields required")
  return self._add(434,"INTENT_ENVELOPE_CANONICALIZED",{"fields":fields,"executable_fields_absent":True},key,v)
 def review(self,reviewer,checks,key,v):
  if reviewer!=self.stages[6].payload["reviewer"] or checks!=("IDENTITY","NONCE","SCOPE","SAFETY"):raise GovernanceRejected("assigned complete intent review required")
  return self._add(435,"INTENT_INDEPENDENTLY_REVIEWED",{"reviewer":reviewer,"checks":checks,"approval_granted":False},key,v)
 def receipt(self,receipt_id,key,v):
  if not _s(receipt_id,"synthetic:receipt:"):raise GovernanceRejected("synthetic receipt required")
  return self._add(436,"INTENT_RECEIPT_ISSUED",{"receipt_id":receipt_id,"intent_digest":self.stages[4].digest,"authority_conferred":False},key,v)
 def ledger(self,sequence,previous_receipt_digest,key,v):
  if sequence!=1 or previous_receipt_digest is not None:raise GovernanceRejected("initial receipt must start append-only ledger")
  return self._add(437,"INTENT_RECEIPT_APPENDED",{"sequence":sequence,"previous_receipt_digest":previous_receipt_digest,"receipt_digest":self.stages[10].digest},key,v)
 def supersession(self,supersedes,reason,key,v):
  if supersedes is not None and not _d(supersedes) or reason not in {"INITIAL","CORRECTION","OPERATOR_WITHDRAWAL"} or supersedes is None and reason!="INITIAL" or supersedes is not None and reason=="INITIAL":raise GovernanceRejected("coherent supersession metadata required")
  return self._add(438,"INTENT_SUPERSESSION_RECORDED",{"supersedes":supersedes,"reason":reason,"automatic_effect":False},key,v)
 def seal(self,previous_snapshot,key,v):
  if previous_snapshot is not None and not _d(previous_snapshot) or tuple(x.feature for x in self.stages)!=tuple(range(426,439)):raise GovernanceRejected("complete intent receipt lineage required")
  return self._add(439,"INTENT_RECEIPT_SNAPSHOT_SEALED",{"digests":tuple(x.digest for x in self.stages),"previous_snapshot":previous_snapshot},key,v)
 def complete(self,controls,key,v):
  required=("INTENT_NOT_APPROVAL","NO_ACTIVATION","READ_ONLY","SYNTHETIC_ONLY")
  if controls!=required or tuple(x.feature for x in self.stages)!=tuple(range(426,440)):raise GovernanceRejected("fixed intent controls required")
  return self._add(440,"SYNTHETIC_OPERATOR_INTENT_RECEIPTS_COMPLETED",{"controls":controls},key,v)
 def evidence(self):
  if not self.stages or self.stages[-1].feature!=440:raise GovernanceRejected("completed intent receipts required")
  out={"schema":"nurion.pg.synthetic-operator-intent-receipts.v1","features":[x.feature for x in self.stages],"states":[x.state for x in self.stages],"packet_digest":self.packet_digest,"policy_digest":self.policy_digest,"maximum_state":"SYNTHETIC_OPERATOR_INTENT_RECEIPTS_COMPLETED","synthetic_only":True,"read_only":True,"intent_is_approval":False,"authority_conferred":False,"activation_allowed":False,"promotion_allowed":False,"live_traffic_used":False,"merchant_blocking_allowed":False,"notification_allowed":False,"card_network_submission_allowed":False,"payment_allowed":False,"refund_allowed":False,"settlement_allowed":False,"transfer_allowed":False,"ledger_posting_allowed":False,"external_api_used":False,"deployment_allowed":False,"production_credentials_accessed":False,"automatic_policy_change_allowed":False}
  return {**out,"report_digest":canonical_digest(out)}
