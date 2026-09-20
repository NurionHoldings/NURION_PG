"""Synthetic durable operator-audit repository planning lock #471-#485."""
from dataclasses import dataclass,field
from .arkaon.governance import GovernanceRejected,canonical_digest
def _d(v):return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _s(v,p):return isinstance(v,str) and v.startswith(p)
@dataclass(frozen=True)
class Stage:feature:int;state:str;payload:dict;previous_digest:str;digest:str;key:str
@dataclass
class OperatorAuditRepositoryPlan:
 parity_digest:str;stages:list[Stage]=field(default_factory=list);_keys:dict=field(default_factory=dict)
 def __post_init__(self):
  if not _d(self.parity_digest):raise GovernanceRejected("parity digest required")
 def _add(self,f,state,p,key,v):
  if not _s(key,"synthetic:key:"):raise GovernanceRejected("synthetic key required")
  fp=canonical_digest({"feature":f,"payload":p})
  if key in self._keys:
   old,item=self._keys[key]
   if old!=fp:raise GovernanceRejected("idempotency conflict")
   return item
  if v!=len(self.stages) or f!=471+len(self.stages):raise GovernanceRejected("ordered current version required")
  prev=self.stages[-1].digest if self.stages else self.parity_digest;item=Stage(f,state,p,prev,canonical_digest({"feature":f,"state":state,"payload":p,"previous_digest":prev}),key);self.stages.append(item);self._keys[key]=(fp,item);return item
 def discover(self,state,features,key,v=0):
  if state!="SYNTHETIC_OPERATOR_AUDIT_REGISTRY_PARITY_COMPLETED" or features!=(456,470):raise GovernanceRejected("completed parity source required")
  return self._add(471,"DISCOVERY_LOCKED",{"features":features},key,v)
 def requirements(self,items,key,v):
  required=("APPEND_ONLY","AUDITABLE","IDEMPOTENT","ROLE_SEPARATED","TAMPER_EVIDENT")
  if items!=required:raise GovernanceRejected("fixed requirements required")
  return self._add(472,"REQUIREMENTS_LOCKED",{"items":items},key,v)
 def conflicts(self,forbidden,key,v):
  required=("EXTERNAL_IO","LIVE_TRAFFIC","MONEY_MOVEMENT","OPERATING_CREDENTIALS","POLICY_MUTATION")
  if forbidden!=required:raise GovernanceRejected("complete conflicts required")
  return self._add(473,"CONFLICT_CHECK_LOCKED",{"forbidden":forbidden},key,v)
 def architecture(self,components,key,v):
  required=("DOMAIN_PORT","POSTGRES_ADAPTER","SQLITE_TEST_ADAPTER","MIGRATION","EVIDENCE_EXPORT")
  if components!=required:raise GovernanceRejected("fixed architecture required")
  return self._add(474,"ARCHITECTURE_LOCKED",{"components":components},key,v)
 def schema(self,columns,key,v):
  required=("id","checkpoint_digest","sequence","previous_digest","report_digest","created_at")
  if columns!=required:raise GovernanceRejected("minimal schema required")
  return self._add(475,"SCHEMA_LOCKED",{"columns":columns},key,v)
 def invariants(self,items,key,v):
  required=("DIGEST_CHAIN","IMMUTABLE_ROWS","MONOTONIC_SEQUENCE","UNIQUE_CHECKPOINT","UNIQUE_IDEMPOTENCY")
  if items!=required:raise GovernanceRejected("repository invariants required")
  return self._add(476,"INVARIANTS_LOCKED",{"items":items},key,v)
 def transactions(self,isolation,single_winner,key,v):
  if isolation!="SERIALIZABLE_OR_LOCKED_EQUIVALENT" or single_winner is not True:raise GovernanceRejected("transaction boundary required")
  return self._add(477,"TRANSACTION_MODEL_LOCKED",{"isolation":isolation,"single_winner":True},key,v)
 def migration(self,fresh,downgrade_reupgrade,key,v):
  if fresh is not True or downgrade_reupgrade is not True:raise GovernanceRejected("migration verification required")
  return self._add(478,"MIGRATION_PLAN_LOCKED",{"fresh_upgrade":True,"downgrade_reupgrade":True},key,v)
 def parity(self,postgres,sqlite_after_pg,key,v):
  if postgres is not True or sqlite_after_pg is not True:raise GovernanceRejected("cross-database parity required")
  return self._add(479,"DATABASE_PARITY_PLAN_LOCKED",{"postgres":True,"sqlite_after_pg":True},key,v)
 def acceptance(self,criteria,key,v):
  required=("CONCURRENCY","FRESH_SCHEMA","IDEMPOTENCY","ROLLBACK","TAMPER","TYPE_PARITY")
  if criteria!=required:raise GovernanceRejected("complete acceptance criteria required")
  return self._add(480,"ACCEPTANCE_CRITERIA_LOCKED",{"criteria":criteria},key,v)
 def fixtures(self,synthetic_only,pii,key,v):
  if synthetic_only is not True or pii is not False:raise GovernanceRejected("synthetic fixtures required")
  return self._add(481,"FIXTURE_POLICY_LOCKED",{"synthetic_only":True,"pii":False},key,v)
 def rollout(self,small_pr,no_merge,key,v):
  if small_pr is not True or no_merge is not True:raise GovernanceRejected("small unmerged PR required")
  return self._add(482,"ROLLOUT_BOUNDARY_LOCKED",{"small_pr":True,"no_merge":True},key,v)
 def reviewers(self,designer,auditor,key,v):
  if not _s(designer,"synthetic:designer:") or not _s(auditor,"synthetic:auditor:") or designer==auditor:raise GovernanceRejected("role-separated review required")
  return self._add(483,"REVIEW_ROLES_LOCKED",{"designer":designer,"auditor":auditor},key,v)
 def seal(self,previous,key,v):
  if previous is not None and not _d(previous) or tuple(x.feature for x in self.stages)!=tuple(range(471,484)):raise GovernanceRejected("complete plan lineage required")
  return self._add(484,"PLANNING_SNAPSHOT_SEALED",{"previous":previous,"digests":tuple(x.digest for x in self.stages)},key,v)
 def complete(self,controls,key,v):
  required=("NO_IMPLEMENTATION","NO_MIGRATION_RUN","NO_PERSISTENCE","NO_PRODUCTION","PLANNING_LOCK")
  if controls!=required or tuple(x.feature for x in self.stages)!=tuple(range(471,485)):raise GovernanceRejected("planning lock controls required")
  return self._add(485,"OPERATOR_AUDIT_REPOSITORY_PLANNING_LOCKED",{"controls":controls},key,v)
 def evidence(self):
  if not self.stages or self.stages[-1].feature!=485:raise GovernanceRejected("completed planning lock required")
  out={"schema":"nurion.pg.operator-audit-repository-plan.v1","features":[x.feature for x in self.stages],"maximum_state":"OPERATOR_AUDIT_REPOSITORY_PLANNING_LOCKED","planning_only":True,"synthetic_only":True,"implementation_present":False,"migration_executed":False,"persistence_used":False,"external_io_used":False,"production_credentials_accessed":False,"deployment_allowed":False,"merge_allowed":False}
  return {**out,"report_digest":canonical_digest(out)}
