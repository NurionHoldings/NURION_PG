"""Synthetic operator intent audit registry parity #456-#470; metadata-only."""
from dataclasses import dataclass,field
from .arkaon.governance import GovernanceRejected,canonical_digest

def _d(v):return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _s(v,p):return isinstance(v,str) and v.startswith(p)
@dataclass(frozen=True)
class Stage:feature:int;state:str;payload:dict;previous_digest:str;digest:str;key:str
@dataclass
class OperatorAuditRegistryParity:
 audit_digest:str;stages:list[Stage]=field(default_factory=list);_keys:dict=field(default_factory=dict)
 def __post_init__(self):
  if not _d(self.audit_digest):raise GovernanceRejected("audit digest required")
 def _add(self,f,state,p,key,v):
  if not _s(key,"synthetic:key:"):raise GovernanceRejected("synthetic key required")
  fp=canonical_digest({"feature":f,"payload":p})
  if key in self._keys:
   old,item=self._keys[key]
   if old!=fp:raise GovernanceRejected("idempotency conflict")
   return item
  if v!=len(self.stages) or f!=456+len(self.stages):raise GovernanceRejected("ordered current version required")
  prev=self.stages[-1].digest if self.stages else self.audit_digest
  item=Stage(f,state,p,prev,canonical_digest({"feature":f,"state":state,"payload":p,"previous_digest":prev}),key);self.stages.append(item);self._keys[key]=(fp,item);return item
 def admit(self,state,features,read_only,key,v=0):
  if state!="SYNTHETIC_OPERATOR_INTENT_AUDIT_COMPLETED" or features!=(441,455) or read_only is not True:raise GovernanceRejected("completed read-only audit required")
  return self._add(456,"AUDIT_CHECKPOINT_ADMITTED",{"features":features,"read_only":True},key,v)
 def contract(self,schema,fields,key,v):
  required=("checkpoint_digest","sequence","previous_digest","report_digest")
  if schema!="nurion.pg.operator-audit-registry.v1" or fields!=required:raise GovernanceRejected("fixed registry contract required")
  return self._add(457,"REGISTRY_CONTRACT_BOUND",{"schema":schema,"fields":fields},key,v)
 def backends(self,names,key,v):
  if names!=("memory","sqlite-memory"):raise GovernanceRejected("fixed synthetic backends required")
  return self._add(458,"SYNTHETIC_BACKENDS_BOUND",{"backends":names},key,v)
 def fixture(self,fixture_digest,key,v):
  if not _d(fixture_digest):raise GovernanceRejected("fixture digest required")
  return self._add(459,"PARITY_FIXTURE_BOUND",{"fixture_digest":fixture_digest},key,v)
 def write_preview(self,sequence,previous,key,v):
  if sequence!=1 or previous is not None:raise GovernanceRejected("initial append-only preview required")
  return self._add(460,"WRITE_PREVIEW_CREATED",{"sequence":sequence,"previous_digest":previous,"executed":False},key,v)
 def memory(self,digest,count,key,v):
  if not _d(digest) or count!=1:raise GovernanceRejected("valid memory observation required")
  return self._add(461,"MEMORY_OBSERVED",{"digest":digest,"count":count},key,v)
 def sqlite(self,digest,count,persistent_file,key,v):
  if not _d(digest) or count!=1 or persistent_file is not False:raise GovernanceRejected("in-memory sqlite observation required")
  return self._add(462,"SQLITE_MEMORY_OBSERVED",{"digest":digest,"count":count,"persistent_file":False},key,v)
 def parity(self,memory_digest,sqlite_digest,key,v):
  if not _d(memory_digest) or memory_digest!=sqlite_digest:raise GovernanceRejected("backend parity required")
  return self._add(463,"BACKEND_PARITY_VERIFIED",{"digest":memory_digest,"equal":True},key,v)
 def replay(self,idempotent,conflict_blocked,key,v):
  if idempotent is not True or conflict_blocked is not True:raise GovernanceRejected("replay controls required")
  return self._add(464,"REPLAY_PARITY_VERIFIED",{"idempotent":True,"conflict_blocked":True},key,v)
 def concurrency(self,single_winner,key,v):
  if single_winner is not True:raise GovernanceRejected("single-winner concurrency required")
  return self._add(465,"CONCURRENCY_PARITY_VERIFIED",{"single_winner":True},key,v)
 def tamper(self,memory_detected,sqlite_detected,key,v):
  if memory_detected is not True or sqlite_detected is not True:raise GovernanceRejected("tamper detection parity required")
  return self._add(466,"TAMPER_PARITY_VERIFIED",{"memory_detected":True,"sqlite_detected":True},key,v)
 def privacy(self,pii,credentials,key,v):
  if pii is not False or credentials is not False:raise GovernanceRejected("privacy boundary required")
  return self._add(467,"REGISTRY_PRIVACY_VERIFIED",{"pii_accessed":False,"production_credentials_accessed":False},key,v)
 def effects(self,effects,key,v):
  if effects!=():raise GovernanceRejected("side effects forbidden")
  return self._add(468,"REGISTRY_SIDE_EFFECTS_ABSENT",{"effects":effects},key,v)
 def seal(self,previous,key,v):
  if previous is not None and not _d(previous) or tuple(x.feature for x in self.stages)!=tuple(range(456,469)):raise GovernanceRejected("complete parity lineage required")
  return self._add(469,"REGISTRY_PARITY_SEALED",{"previous_checkpoint":previous,"digests":tuple(x.digest for x in self.stages)},key,v)
 def complete(self,controls,key,v):
  required=("IN_MEMORY_ONLY","NO_AUTHORITY","NO_EXTERNAL_IO","READ_ONLY","SYNTHETIC_ONLY")
  if controls!=required or tuple(x.feature for x in self.stages)!=tuple(range(456,470)):raise GovernanceRejected("fixed completion controls required")
  return self._add(470,"SYNTHETIC_OPERATOR_AUDIT_REGISTRY_PARITY_COMPLETED",{"controls":controls},key,v)
 def evidence(self):
  if not self.stages or self.stages[-1].feature!=470:raise GovernanceRejected("completed registry parity required")
  out={"schema":"nurion.pg.synthetic-operator-audit-registry-parity.v1","features":[x.feature for x in self.stages],"maximum_state":"SYNTHETIC_OPERATOR_AUDIT_REGISTRY_PARITY_COMPLETED","synthetic_only":True,"read_only":True,"in_memory_only":True,"authority_conferred":False,"external_io_used":False,"production_credentials_accessed":False,"payment_allowed":False,"refund_allowed":False,"settlement_allowed":False,"transfer_allowed":False,"ledger_posting_allowed":False,"deployment_allowed":False}
  return {**out,"report_digest":canonical_digest(out)}
