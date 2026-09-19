"""PostgreSQL repository readiness portfolio #501-#700; validation only."""
from dataclasses import dataclass
from .arkaon.governance import GovernanceRejected,canonical_digest

WORKSTREAMS=(
 (501,525,"CONTRACT_HARDENING"),
 (526,550,"AUTHORITATIVE_SCHEMA"),
 (551,575,"ALEMBIC_MIGRATION_DESIGN"),
 (576,600,"REPOSITORY_SEMANTICS"),
 (601,625,"CONCURRENCY_IDEMPOTENCY"),
 (626,650,"INTEGRITY_TAMPER_EVIDENCE"),
 (651,675,"POSTGRES_SQLITE_PARITY"),
 (676,700,"CI_AUDIT_RELEASE_GATE"),
)
REQUIRED_GATES=("ACCEPTANCE_DEFINED","FAIL_CLOSED","NO_CONDITIONAL_DDL","NO_EXTERNAL_IO","NO_TYPE_COERCION","ROLE_SEPARATED","SYNTHETIC_ONLY")

@dataclass(frozen=True)
class ReadinessControl:
 feature:int
 workstream:str
 ordinal:int
 gates:tuple[str,...]
 previous_digest:str
 digest:str

def build_readiness_portfolio(source_digest:str)->tuple[ReadinessControl,...]:
 if not isinstance(source_digest,str) or len(source_digest)!=64 or any(c not in "0123456789abcdef" for c in source_digest):raise GovernanceRejected("repository evidence digest required")
 controls=[];previous=source_digest
 for start,end,name in WORKSTREAMS:
  for feature in range(start,end+1):
   payload={"feature":feature,"workstream":name,"ordinal":feature-start+1,"gates":REQUIRED_GATES}
   digest=canonical_digest({**payload,"previous_digest":previous})
   controls.append(ReadinessControl(feature,name,feature-start+1,REQUIRED_GATES,previous,digest));previous=digest
 return tuple(controls)

def validate_readiness_portfolio(controls):
 if len(controls)!=200 or tuple(x.feature for x in controls)!=tuple(range(501,701)):raise GovernanceRejected("continuous #501-#700 portfolio required")
 previous=controls[0].previous_digest
 counts={name:0 for _,_,name in WORKSTREAMS}
 for item in controls:
  if item.workstream not in counts or item.gates!=REQUIRED_GATES:raise GovernanceRejected("fixed workstream gates required")
  expected=canonical_digest({"feature":item.feature,"workstream":item.workstream,"ordinal":item.ordinal,"gates":item.gates,"previous_digest":previous})
  if item.previous_digest!=previous or item.digest!=expected:raise GovernanceRejected("tamper-evident lineage required")
  counts[item.workstream]+=1;previous=item.digest
 if any(value!=25 for value in counts.values()):raise GovernanceRejected("25 controls per workstream required")
 return True

def readiness_evidence(controls):
 validate_readiness_portfolio(controls)
 out={"schema":"nurion.pg.postgres-repository-readiness.v1","features":[x.feature for x in controls],"feature_count":len(controls),"workstreams":[{"name":name,"start":start,"end":end,"control_count":25} for start,end,name in WORKSTREAMS],"maximum_state":"POSTGRES_REPOSITORY_READINESS_PORTFOLIO_COMPLETED","planning_and_validation_only":True,"postgres_connection_used":False,"migration_executed":False,"conditional_ddl_allowed":False,"type_coercion_allowed":False,"persistent_storage_used":False,"external_io_used":False,"production_credentials_accessed":False,"payment_allowed":False,"refund_allowed":False,"settlement_allowed":False,"transfer_allowed":False,"ledger_posting_allowed":False,"deployment_allowed":False,"merge_allowed":False}
 return {**out,"portfolio_digest":controls[-1].digest,"report_digest":canonical_digest(out)}
