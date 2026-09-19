"""Synthetic operator intent audit checkpoint #441-#455; read-only and non-authorizing."""
from __future__ import annotations
from dataclasses import dataclass,field
from datetime import datetime
from .arkaon.governance import GovernanceRejected,canonical_digest

def _d(v): return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _s(v,p): return isinstance(v,str) and v.startswith(p)

@dataclass(frozen=True)
class AuditStage:
    feature:int; state:str; payload:dict[str,object]; previous_digest:str; digest:str; key:str

@dataclass
class OperatorIntentAuditCheckpoint:
    receipt_report_digest:str
    stages:list[AuditStage]=field(default_factory=list)
    _keys:dict[str,tuple[str,AuditStage]]=field(default_factory=dict)

    def __post_init__(self):
        if not _d(self.receipt_report_digest): raise GovernanceRejected("receipt report digest required")

    def _add(self,feature,state,payload,key,version):
        if not _s(key,"synthetic:key:"): raise GovernanceRejected("synthetic key required")
        fingerprint=canonical_digest({"feature":feature,"payload":payload})
        if key in self._keys:
            old,item=self._keys[key]
            if old!=fingerprint: raise GovernanceRejected("idempotency conflict")
            return item
        if version!=len(self.stages) or feature!=441+len(self.stages): raise GovernanceRejected("ordered current version required")
        previous=self.stages[-1].digest if self.stages else self.receipt_report_digest
        item=AuditStage(feature,state,payload,previous,canonical_digest({"feature":feature,"state":state,"payload":payload,"previous_digest":previous}),key)
        self.stages.append(item); self._keys[key]=(fingerprint,item); return item

    def admit(self,source_state,features,authority_conferred,key,version=0):
        if source_state!="SYNTHETIC_OPERATOR_INTENT_RECEIPTS_COMPLETED" or features!=(426,440) or authority_conferred is not False: raise GovernanceRejected("non-authorizing completed receipt lineage required")
        return self._add(441,"INTENT_RECEIPT_LINEAGE_ADMITTED",{"features":features,"authority_conferred":False},key,version)

    def bind_scope(self,project,purpose,key,version):
        if project!="NURION_PG" or purpose!="READ_ONLY_INDEPENDENT_AUDIT": raise GovernanceRejected("fixed audit scope required")
        return self._add(442,"AUDIT_SCOPE_BOUND",{"project":project,"purpose":purpose},key,version)

    def freshness(self,issued,expires,now,key,version):
        if any(x.tzinfo is None for x in (issued,expires,now)) or not issued<=now<expires: raise GovernanceRejected("current aware audit window required")
        return self._add(443,"AUDIT_FRESHNESS_VERIFIED",{"issued":issued.isoformat(),"expires":expires.isoformat(),"as_of":now.isoformat()},key,version)

    def roles(self,operator,reviewer,key,version):
        if not _s(operator,"synthetic:operator:") or not _s(reviewer,"synthetic:auditor:") or operator==reviewer: raise GovernanceRejected("independent synthetic auditor required")
        return self._add(444,"AUDIT_ROLES_SEPARATED",{"operator":operator,"auditor":reviewer},key,version)

    def vocabulary(self,codes,key,version):
        required=("ACKNOWLEDGE_ONLY","CLOSE_CONSIDERATION","DEFER_CONSIDERATION","REQUEST_REVISION")
        if codes!=required: raise GovernanceRejected("complete non-authorizing vocabulary required")
        return self._add(445,"INTENT_VOCABULARY_AUDITED",{"codes":codes,"approval_code_absent":True},key,version)

    def authority(self,flags,key,version):
        required=("ACTIVATION_FALSE","AUTHORITY_FALSE","EXECUTION_FALSE","POLICY_CHANGE_FALSE")
        if flags!=required: raise GovernanceRejected("authority denial controls required")
        return self._add(446,"AUTHORITY_DENIAL_VERIFIED",{"flags":flags},key,version)

    def integrity(self,receipt_digest,chain_valid,key,version):
        if not _d(receipt_digest) or chain_valid is not True: raise GovernanceRejected("valid receipt digest chain required")
        return self._add(447,"RECEIPT_INTEGRITY_VERIFIED",{"receipt_digest":receipt_digest,"chain_valid":True},key,version)

    def replay(self,idempotent,conflict_blocked,key,version):
        if idempotent is not True or conflict_blocked is not True: raise GovernanceRejected("replay controls required")
        return self._add(448,"REPLAY_CONTROLS_VERIFIED",{"idempotent":True,"conflict_blocked":True},key,version)

    def supersession(self,coherent,automatic_effect,key,version):
        if coherent is not True or automatic_effect is not False: raise GovernanceRejected("non-automatic supersession required")
        return self._add(449,"SUPERSESSION_AUDITED",{"coherent":True,"automatic_effect":False},key,version)

    def privacy(self,raw_pii_accessed,credentials_accessed,key,version):
        if raw_pii_accessed is not False or credentials_accessed is not False: raise GovernanceRejected("privacy boundary required")
        return self._add(450,"PRIVACY_BOUNDARY_VERIFIED",{"raw_pii_accessed":False,"production_credentials_accessed":False},key,version)

    def effects(self,effects,key,version):
        if effects!=(): raise GovernanceRejected("side effects forbidden")
        return self._add(451,"SIDE_EFFECT_ABSENCE_VERIFIED",{"effects":effects},key,version)

    def findings(self,critical_findings,key,version):
        if critical_findings!=(): raise GovernanceRejected("critical findings block checkpoint")
        return self._add(452,"AUDIT_FINDINGS_CLEARED",{"critical_findings":critical_findings},key,version)

    def attest(self,auditor,checks,key,version):
        if auditor!=self.stages[3].payload["auditor"] or checks!=("AUTHORITY","INTEGRITY","PRIVACY","REPLAY","SCOPE"): raise GovernanceRejected("assigned complete attestation required")
        return self._add(453,"INDEPENDENT_AUDIT_ATTESTED",{"auditor":auditor,"checks":checks},key,version)

    def seal(self,previous_checkpoint,key,version):
        if previous_checkpoint is not None and not _d(previous_checkpoint): raise GovernanceRejected("valid previous checkpoint required")
        if tuple(x.feature for x in self.stages)!=tuple(range(441,454)): raise GovernanceRejected("complete audit lineage required")
        return self._add(454,"AUDIT_CHECKPOINT_SEALED",{"previous_checkpoint":previous_checkpoint,"stage_digests":tuple(x.digest for x in self.stages)},key,version)

    def complete(self,controls,key,version):
        required=("NO_AUTHORIZATION","NO_DEPLOYMENT","NO_MONEY_MOVEMENT","READ_ONLY","SYNTHETIC_ONLY")
        if controls!=required or tuple(x.feature for x in self.stages)!=tuple(range(441,455)): raise GovernanceRejected("fixed completion controls required")
        return self._add(455,"SYNTHETIC_OPERATOR_INTENT_AUDIT_COMPLETED",{"controls":controls},key,version)

    def evidence(self):
        if not self.stages or self.stages[-1].feature!=455: raise GovernanceRejected("completed audit required")
        out={"schema":"nurion.pg.synthetic-operator-intent-audit.v1","features":[x.feature for x in self.stages],"states":[x.state for x in self.stages],"receipt_report_digest":self.receipt_report_digest,"maximum_state":"SYNTHETIC_OPERATOR_INTENT_AUDIT_COMPLETED","synthetic_only":True,"read_only":True,"authority_conferred":False,"activation_allowed":False,"live_traffic_used":False,"merchant_blocking_allowed":False,"notification_allowed":False,"card_network_submission_allowed":False,"payment_allowed":False,"refund_allowed":False,"settlement_allowed":False,"transfer_allowed":False,"ledger_posting_allowed":False,"external_api_used":False,"deployment_allowed":False,"production_credentials_accessed":False,"automatic_policy_change_allowed":False}
        return {**out,"report_digest":canonical_digest(out)}
