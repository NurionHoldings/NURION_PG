"""Synthetic delivery backpressure and lifecycle controls #701-#900."""
from dataclasses import dataclass,replace
from datetime import datetime
from threading import RLock
from .arkaon.governance import GovernanceRejected,canonical_digest

def _hex_digest(value):return isinstance(value,str) and len(value)==64 and all(ch in "0123456789abcdef" for ch in value)

WORKSTREAMS=((701,725,"BACKPRESSURE"),(726,750,"DUPLICATE_DECISION"),(751,775,"PACKET_REFRESH"),(776,800,"SINGLE_WARNING"),(801,825,"SUPERSEDED_CLEANUP"),(826,850,"EXPIRED_CLEANUP"),(851,875,"VERIFIED_RESUME"),(876,900,"AUDIT_EVIDENCE"))
ACTIVE={"PENDING","HELD","READY"}
TERMINAL={"SUPERSEDED","EXPIRED","CLOSED"}

@dataclass(frozen=True)
class ResumeReceipt:
 packet_id:str;source_version:int;resulting_version:int;verifier:str;receipt_digest:str;record_digest:str

@dataclass(frozen=True)
class DeliveryPacket:
 packet_id:str;intent_digest:str;version:int;status:str;warning:str|None;created_at:datetime;expires_at:datetime;previous_digest:str|None;digest:str

class SyntheticDeliveryQueue:
 def __init__(self,capacity=100):
  if capacity<1:raise GovernanceRejected("positive capacity required")
  self.capacity=capacity;self._rows={};self._intent={};self._lock=RLock();self._events=[];self._history=[];self._resume_receipts={}
 def _make(self,packet_id,intent_digest,version,status,warning,created_at,expires_at,previous):
  if not packet_id.startswith("synthetic:packet:") or not _hex_digest(intent_digest) or created_at.tzinfo is None or expires_at.tzinfo is None or expires_at<=created_at:raise GovernanceRejected("valid synthetic packet required")
  payload={"packet_id":packet_id,"intent_digest":intent_digest,"version":version,"status":status,"warning":warning,"created_at":created_at.isoformat(),"expires_at":expires_at.isoformat(),"previous_digest":previous}
  return DeliveryPacket(packet_id,intent_digest,version,status,warning,created_at,expires_at,previous,canonical_digest(payload))
 def _record(self,action,item,receipt_record_digest=None):
  self._history.append(item);previous=self._events[-1]["digest"] if self._events else None
  payload={"action":action,"packet_digest":item.digest,"receipt_record_digest":receipt_record_digest,"previous_digest":previous,"sequence":len(self._events)+1}
  self._events.append({**payload,"digest":canonical_digest(payload)})
 def enqueue(self,packet_id,intent_digest,created_at,expires_at):
  with self._lock:
   existing_id=self._intent.get(intent_digest)
   if existing_id:
    existing=self._rows[existing_id]
    if existing.status in ACTIVE and created_at<existing.expires_at:return existing
   active=sum(x.status in ACTIVE and created_at<x.expires_at for x in self._rows.values())
   if active>=self.capacity:raise GovernanceRejected("backpressure capacity reached")
   item=self._make(packet_id,intent_digest,1,"PENDING",None,created_at,expires_at,None)
   if packet_id in self._rows:raise GovernanceRejected("packet collision")
   self._rows[packet_id]=item;self._intent[intent_digest]=packet_id;self._record("ENQUEUED",item);return item
 def refresh(self,packet_id,expected_version,expires_at,now):
  with self._lock:
   old=self._require(packet_id,expected_version)
   if old.status not in ACTIVE or now.tzinfo is None or now>=old.expires_at or expires_at<=now:raise GovernanceRejected("refresh blocked")
   item=self._make(old.packet_id,old.intent_digest,old.version+1,old.status,old.warning,old.created_at,expires_at,old.digest);self._rows[packet_id]=item;self._record("REFRESHED",item);return item
 def warn(self,packet_id,expected_version,code,now):
  allowed={"CAPACITY_PRESSURE","DUPLICATE_REVIEW","STALE_PACKET"}
  with self._lock:
   old=self._require(packet_id,expected_version)
   if now.tzinfo is None or now>=old.expires_at or old.status not in ACTIVE or code not in allowed or old.warning is not None:raise GovernanceRejected("single current active warning required")
   item=replace(old,version=old.version+1,warning=code,previous_digest=old.digest,digest="")
   item=replace(item,digest=canonical_digest({"packet_id":item.packet_id,"intent_digest":item.intent_digest,"version":item.version,"status":item.status,"warning":item.warning,"created_at":item.created_at.isoformat(),"expires_at":item.expires_at.isoformat(),"previous_digest":item.previous_digest}));self._rows[packet_id]=item;self._record("WARNED",item);return item
 def transition(self,packet_id,expected_version,status,now):
  if status not in {"SUPERSEDED","EXPIRED","READY","CLOSED"}:raise GovernanceRejected("bounded status required")
  with self._lock:
   old=self._require(packet_id,expected_version)
   if now.tzinfo is None:raise GovernanceRejected("aware time required")
   if status=="EXPIRED" and now<old.expires_at:raise GovernanceRejected("not expired")
   if status=="READY":
    receipt=self._resume_receipts.get(packet_id)
    if old.status!="HELD" or old.warning is not None or now>=old.expires_at or receipt is None or receipt.packet_id!=packet_id or receipt.resulting_version!=old.version or not self._receipt_valid(receipt):raise GovernanceRejected("resume verification failed")
   if old.status in TERMINAL:raise GovernanceRejected("terminal packet")
   item=replace(old,version=old.version+1,status=status,previous_digest=old.digest,digest="")
   item=replace(item,digest=canonical_digest({"packet_id":item.packet_id,"intent_digest":item.intent_digest,"version":item.version,"status":item.status,"warning":item.warning,"created_at":item.created_at.isoformat(),"expires_at":item.expires_at.isoformat(),"previous_digest":item.previous_digest}));self._rows[packet_id]=item;self._record(status,item);return item
 def hold(self,packet_id,expected_version,now):
  with self._lock:
   old=self._require(packet_id,expected_version)
   if now.tzinfo is None or now>=old.expires_at or old.status!="PENDING":raise GovernanceRejected("current pending packet required")
   item=replace(old,version=old.version+1,status="HELD",previous_digest=old.digest,digest="")
   item=replace(item,digest=canonical_digest({"packet_id":item.packet_id,"intent_digest":item.intent_digest,"version":item.version,"status":item.status,"warning":item.warning,"created_at":item.created_at.isoformat(),"expires_at":item.expires_at.isoformat(),"previous_digest":item.previous_digest}));self._rows[packet_id]=item;self._record("HELD",item);return item
 def clear_warning(self,packet_id,expected_version,now):
  with self._lock:
   old=self._require(packet_id,expected_version)
   if now.tzinfo is None or now>=old.expires_at or old.status!="HELD" or old.warning is None:raise GovernanceRejected("current held warning required")
   item=replace(old,version=old.version+1,warning=None,previous_digest=old.digest,digest="")
   item=replace(item,digest=canonical_digest({"packet_id":item.packet_id,"intent_digest":item.intent_digest,"version":item.version,"status":item.status,"warning":item.warning,"created_at":item.created_at.isoformat(),"expires_at":item.expires_at.isoformat(),"previous_digest":item.previous_digest}));self._rows[packet_id]=item;self._record("WARNING_CLEARED",item);return item
 def _receipt_valid(self,receipt):
  if not isinstance(receipt,ResumeReceipt) or not receipt.verifier.startswith("synthetic:verifier:") or not _hex_digest(receipt.receipt_digest):return False
  payload={"packet_id":receipt.packet_id,"source_version":receipt.source_version,"resulting_version":receipt.resulting_version,"verifier":receipt.verifier,"receipt_digest":receipt.receipt_digest}
  return receipt.record_digest==canonical_digest(payload)
 def verify_resume(self,packet_id,expected_version,verifier,receipt_digest,now):
  with self._lock:
   existing=self._resume_receipts.get(packet_id)
   if existing is not None:
    if expected_version==existing.source_version and verifier==existing.verifier and receipt_digest==existing.receipt_digest and self._receipt_valid(existing):return self._rows[packet_id]
    raise GovernanceRejected("resume receipt conflict")
   old=self._require(packet_id,expected_version)
   if now.tzinfo is None or now>=old.expires_at or old.status!="HELD" or old.warning is not None or not isinstance(verifier,str) or not verifier.startswith("synthetic:verifier:") or not _hex_digest(receipt_digest):raise GovernanceRejected("valid independent resume receipt required")
   item=replace(old,version=old.version+1,previous_digest=old.digest,digest="")
   item=replace(item,digest=canonical_digest({"packet_id":item.packet_id,"intent_digest":item.intent_digest,"version":item.version,"status":item.status,"warning":item.warning,"created_at":item.created_at.isoformat(),"expires_at":item.expires_at.isoformat(),"previous_digest":item.previous_digest}))
   payload={"packet_id":packet_id,"source_version":old.version,"resulting_version":item.version,"verifier":verifier,"receipt_digest":receipt_digest};receipt=ResumeReceipt(**payload,record_digest=canonical_digest(payload))
   self._rows[packet_id]=item;self._resume_receipts[packet_id]=receipt;self._record("RESUME_VERIFIED",item,receipt.record_digest);return item
 def _require(self,packet_id,version):
  item=self._rows.get(packet_id)
  if item is None or item.version!=version:raise GovernanceRejected("current packet version required")
  return item
 def get(self,packet_id):
  with self._lock:return self._rows.get(packet_id)
 def _event_chain_valid(self):
  previous=None;history_by_digest={item.digest:item for item in self._history};receipt_by_digest={receipt.record_digest:receipt for receipt in self._resume_receipts.values() if self._receipt_valid(receipt)}
  for sequence,event in enumerate(self._events,1):
   payload={"action":event["action"],"packet_digest":event["packet_digest"],"receipt_record_digest":event["receipt_record_digest"],"previous_digest":previous,"sequence":sequence}
   history_item=history_by_digest.get(event["packet_digest"]);receipt=receipt_by_digest.get(event["receipt_record_digest"])
   if (event["action"]=="RESUME_VERIFIED" and (receipt is None or history_item is None or receipt.packet_id!=history_item.packet_id)) or (event["action"]!="RESUME_VERIFIED" and event["receipt_record_digest"] is not None) or history_item is None or event["previous_digest"]!=previous or event["digest"]!=canonical_digest(payload):return False
   previous=event["digest"]
  return True
 def _history_chain_valid(self):
  tips={}
  for item in self._history:
   previous_item=tips.get(item.packet_id);expected_previous=None if previous_item is None else previous_item.digest
   if item.previous_digest!=expected_previous:return False
   try:rebuilt=self._make(item.packet_id,item.intent_digest,item.version,item.status,item.warning,item.created_at,item.expires_at,item.previous_digest)
   except GovernanceRejected:return False
   if rebuilt!=item:return False
   tips[item.packet_id]=item
  return all(packet_id in tips and item==tips[packet_id] for packet_id,item in self._rows.items())
 def evidence(self):
  with self._lock:
   counts={state:sum(x.status==state for x in self._rows.values()) for state in sorted(ACTIVE|TERMINAL)}
   packet_count=len(self._rows);event_count=len(self._events);history_count=len(self._history);resume_receipt_count=len(self._resume_receipts);receipt_integrity_valid=all(key==receipt.packet_id and self._receipt_valid(receipt) for key,receipt in self._resume_receipts.items());event_chain_valid=self._event_chain_valid();history_chain_valid=self._history_chain_valid()
  out={"schema":"nurion.pg.synthetic-delivery-backpressure.v1","features":list(range(701,901)),"workstreams":[{"name":n,"start":s,"end":e} for s,e,n in WORKSTREAMS],"packet_count":packet_count,"status_counts":counts,"event_count":event_count,"history_count":history_count,"resume_receipt_count":resume_receipt_count,"receipt_integrity_valid":receipt_integrity_valid,"event_chain_valid":event_chain_valid,"history_chain_valid":history_chain_valid,"maximum_state":"SYNTHETIC_DELIVERY_BACKPRESSURE_VERIFIED","synthetic_only":True,"in_memory_only":True,"automatic_approval_allowed":False,"external_delivery_used":False,"external_io_used":False,"production_credentials_accessed":False,"money_movement_allowed":False,"merge_allowed":False,"deployment_allowed":False}
  return {**out,"report_digest":canonical_digest(out)}
