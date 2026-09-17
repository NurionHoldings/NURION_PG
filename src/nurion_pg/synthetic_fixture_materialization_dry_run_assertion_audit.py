"""Read-only boundary audit for unevaluated materialization dry-run assertions."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from .arkaon.governance import GovernanceRejected,canonical_digest
from .synthetic_fixture_materialization_dry_run_assertions import ASSERTION_STATE,SyntheticFixtureMaterializationDryRunAssertion,SyntheticFixtureMaterializationDryRunAssertionBook
AUDIT_STATE="SYNTHETIC_FIXTURE_MATERIALIZATION_DRY_RUN_ASSERTION_BOUNDARY_AUDITED"
@dataclass(frozen=True)
class SyntheticFixtureMaterializationDryRunAssertionAudit:
    assertion_id:str;assertion_digest:str;audited_at:datetime;state:str;audit_digest:str
    def __post_init__(self)->None:
        if self.audited_at.tzinfo is None or self.state!=AUDIT_STATE or self.audit_digest!=canonical_digest(self.digest_value()):raise GovernanceRejected("valid read-only assertion audit required")
    def digest_value(self)->dict[str,object]:return {"assertion_id":self.assertion_id,"assertion_digest":self.assertion_digest,"audited_at":self.audited_at.isoformat(),
        "state":self.state,"evaluation_allowed":False,"dry_run_execution_allowed":False,"fixture_materialization_allowed":False,"activation_allowed":False}
def audit_assertion(book:SyntheticFixtureMaterializationDryRunAssertionBook,item:SyntheticFixtureMaterializationDryRunAssertion,*,audited_at:datetime)->SyntheticFixtureMaterializationDryRunAssertionAudit:
    if not isinstance(book,SyntheticFixtureMaterializationDryRunAssertionBook) or not book.verify_chain() or item not in book.assertions or item.state!=ASSERTION_STATE or audited_at.tzinfo is None or audited_at<item.drafted_at:
        raise GovernanceRejected("intact typed assertion chain required")
    values={"assertion_id":item.assertion_id,"assertion_digest":item.assertion_digest,"audited_at":audited_at.isoformat(),
        "state":AUDIT_STATE,"evaluation_allowed":False,"dry_run_execution_allowed":False,"fixture_materialization_allowed":False,"activation_allowed":False}
    return SyntheticFixtureMaterializationDryRunAssertionAudit(item.assertion_id,item.assertion_digest,audited_at,AUDIT_STATE,canonical_digest(values))
def evidence(audit:SyntheticFixtureMaterializationDryRunAssertionAudit)->dict[str,object]:
    v={"schema":"nurion.pg.synthetic-fixture-materialization-dry-run-assertion-audit-evidence.v1","mode":"UNREGISTERED_SYNTHETIC_ONLY",
       "audit_digest":audit.audit_digest,"maximum_state":AUDIT_STATE,"evaluation_method_present":False,"dry_run_execution_method_present":False,
       "fixture_materialization_method_present":False,"activation_method_present":False,"network_access_method_present":False,
       "automatic_merge_method_present":False,"automatic_deploy_method_present":False,"credentials_used":False,"money_movement_executed":False}
    return {**v,"report_digest":canonical_digest(v)}
