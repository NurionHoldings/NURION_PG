"""Synthetic delivery backpressure and lifecycle controls #701-#900."""
from dataclasses import dataclass,replace
from datetime import datetime
from threading import RLock
from .arkaon.governance import GovernanceRejected,canonical_digest

WORKSTREAMS=((701,725,"BACKPRESSURE"),(726,750,"DUPLICATE_DECISION"),(751,775,"PACKET_REFRESH"),(776,800,"SINGLE_WARNING"),(801,825,"SUPERSEDED_CLEANUP"),(826,850,"EXPIRED_CLEANUP"),(851,875,"VERIFIED_RESUME"),(876,900,"AUDIT_EVIDENCE"))
ACTIVE={"PENDING","HELD","READY"}
TERMINAL={"SUPERSEDED","EXPIRED","CLOSED"}

@dataclass(frozen=True)
class DeliveryPacket:
 packet_id:str;intent_digest:str;version:int;status:str;warning:str|None;created_at:datetime;expires_at:datetime;previous_digest:str|None;digest:str

class SyntheticDeliveryQueue:
 def __init__(self,capacity=100):
  if capacity<1:raise GovernanceRejected("positive capacity required")
  self.capacity=capacity;self._rows={};self._intent={};self._lock=RLock();self._events=[]
 def _make(self,packet_id,intent_digest,version,status,warning,created_at,expires_at,previous):
  if not packet_id.startswith("synthetic:packet:") or len(intent_digest)!=64 or created_at.tzinfo is None or expires_at.tzinfo is None or expires_at<=created_at:raise GovernanceRejected("valid synthetic packet required")
  payload={"packet_id":packet_id,"intent_digest":intent_digest,"version":version,"status":status,"warning":warning,"created_at":created_at.isoformat(),"expires_at":expires_at.isoformat(),"previous_digest":previous}
  return DeliveryPacket(packet_id,intent_digest,version,status,warning,created_at,expires_at,previous,canonical_digest(payload))
 def enqueue(self,packet_id,intent_digest,created_at,expires_at):
  with self._lock:
   active=sum(x.status in ACTIVE for x in self._rows.values())
   if active>=self.capacity:raise GovernanceRejected("backpressure capacity reached")
   existing_id=self._intent.get(intent_digest)
   if existing_id:
    existing=self._rows[existing_id]
    if existing.status in ACTIVE:return existing
   item=self._make(packet_id,intent_digest,1,"PENDING",None,created_at,expires_at,None)
   if packet_id in self._rows:raise GovernanceRejected("packet collision")
   self._rows[packet_id]=item;self._intent[intent_digest]=packet_id;self._events.append(("ENQUEUED",item.digest));return item
 def refresh(self,packet_id,expected_version,expires_at,now):
  with self._lock:
   old=self._require(packet_id,expected_version)
   if old.status not in ACTIVE or now.tzinfo is None or expires_at<=now:raise GovernanceRejected("refresh blocked")
   item=self._make(old.packet_id,old.intent_digest,old.version+1,old.status,old.warning,old.created_at,expires_at,old.digest);self._rows[packet_id]=item;self._events.append(("REFRESHED",item.digest));return item
 def warn(self,packet_id,expected_version,code):
  allowed={"CAPACITY_PRESSURE","DUPLICATE_REVIEW","STALE_PACKET"}
  with self._lock:
   old=self._require(packet_id,expected_version)
   if code not in allowed or old.warning is not None:raise GovernanceRejected("single warning required")
   item=replace(old,version=old.version+1,warning=code,previous_digest=old.digest,digest="")
   item=replace(item,digest=canonical_digest({"packet_id":item.packet_id,"intent_digest":item.intent_digest,"version":item.version,"status":item.status,"warning":item.warning,"created_at":item.created_at.isoformat(),"expires_at":item.expires_at.isoformat(),"previous_digest":item.previous_digest}));self._rows[packet_id]=item;self._events.append(("WARNED",item.digest));return item
 def transition(self,packet_id,expected_version,status,now):
  if status not in {"SUPERSEDED","EXPIRED","READY","CLOSED"}:raise GovernanceRejected("bounded status required")
  with self._lock:
   old=self._require(packet_id,expected_version)
   if now.tzinfo is None:raise GovernanceRejected("aware time required")
   if status=="EXPIRED" and now<old.expires_at:raise GovernanceRejected("not expired")
   if status=="READY" and (old.status!="HELD" or old.warning is not None or now>=old.expires_at):raise GovernanceRejected("resume verification failed")
   if old.status in TERMINAL:raise GovernanceRejected("terminal packet")
   item=replace(old,version=old.version+1,status=status,previous_digest=old.digest,digest="")
   item=replace(item,digest=canonical_digest({"packet_id":item.packet_id,"intent_digest":item.intent_digest,"version":item.version,"status":item.status,"warning":item.warning,"created_at":item.created_at.isoformat(),"expires_at":item.expires_at.isoformat(),"previous_digest":item.previous_digest}));self._rows[packet_id]=item;self._events.append((status,item.digest));return item
 def hold(self,packet_id,expected_version):
  with self._lock:
   old=self._require(packet_id,expected_version)
   if old.status!="PENDING":raise GovernanceRejected("pending packet required")
   item=replace(old,version=old.version+1,status="HELD",previous_digest=old.digest,digest="")
   item=replace(item,digest=canonical_digest({"packet_id":item.packet_id,"intent_digest":item.intent_digest,"version":item.version,"status":item.status,"warning":item.warning,"created_at":item.created_at.isoformat(),"expires_at":item.expires_at.isoformat(),"previous_digest":item.previous_digest}));self._rows[packet_id]=item;return item
 def clear_warning(self,packet_id,expected_version):
  with self._lock:
   old=self._require(packet_id,expected_version)
   if old.status!="HELD" or old.warning is None:raise GovernanceRejected("held warning required")
   item=replace(old,version=old.version+1,warning=None,previous_digest=old.digest,digest="")
   item=replace(item,digest=canonical_digest({"packet_id":item.packet_id,"intent_digest":item.intent_digest,"version":item.version,"status":item.status,"warning":item.warning,"created_at":item.created_at.isoformat(),"expires_at":item.expires_at.isoformat(),"previous_digest":item.previous_digest}));self._rows[packet_id]=item;return item
 def _require(self,packet_id,version):
  item=self._rows.get(packet_id)
  if item is None or item.version!=version:raise GovernanceRejected("current packet version required")
  return item
 def get(self,packet_id):return self._rows.get(packet_id)
 def evidence(self):
  counts={state:sum(x.status==state for x in self._rows.values()) for state in sorted(ACTIVE|TERMINAL)}
  out={"schema":"nurion.pg.synthetic-delivery-backpressure.v1","features":list(range(701,901)),"workstreams":[{"name":n,"start":s,"end":e} for s,e,n in WORKSTREAMS],"packet_count":len(self._rows),"status_counts":counts,"event_count":len(self._events),"maximum_state":"SYNTHETIC_DELIVERY_BACKPRESSURE_VERIFIED","synthetic_only":True,"in_memory_only":True,"automatic_approval_allowed":False,"external_delivery_used":False,"external_io_used":False,"production_credentials_accessed":False,"money_movement_allowed":False,"merge_allowed":False,"deployment_allowed":False}
  return {**out,"report_digest":canonical_digest(out)}
