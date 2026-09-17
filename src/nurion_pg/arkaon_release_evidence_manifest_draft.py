"""Non-deployable PG analog of ARKAON Release Manifest Binding."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from .arkaon.governance import GovernanceRejected, canonical_digest
FOUNDRY_COMMIT = "24ae4a601ee449649e40804119fa37667f731076"
FOUNDRY_PATTERN_ID = "apf.public.release-manifest-binding"
FOUNDRY_PACKAGE_HASH = "d417f4d7f0205ba1bf03a4f8d1ed2edf4dacbb4e67186a4754b42ac5af420a2e"
FOUNDRY_PATTERN_STATUS = "ETHERNIAN_REVIEW_REQUIRED"
MANIFEST_DRAFT_STATE = "SYNTHETIC_PG_RELEASE_EVIDENCE_MANIFEST_DRAFTED"
def _valid_digest(value: object) -> bool:
    return isinstance(value,str) and len(value)==64 and all(c in "0123456789abcdef" for c in value)
@dataclass(frozen=True)
class ArkaonReleaseEvidenceManifestDraft:
    artifact_digest:str;test_digest:str;evidence_digest:str;policy_digest:str;drafted_at:datetime
    foundry_commit:str;foundry_pattern_id:str;foundry_package_hash:str;foundry_pattern_status:str
    state:str;manifest_digest:str
    def __post_init__(self)->None:
        if (not all(_valid_digest(v) for v in (self.artifact_digest,self.test_digest,self.evidence_digest,self.policy_digest,self.foundry_package_hash))
            or self.drafted_at.tzinfo is None or self.foundry_commit!=FOUNDRY_COMMIT or self.foundry_pattern_id!=FOUNDRY_PATTERN_ID
            or self.foundry_package_hash!=FOUNDRY_PACKAGE_HASH or self.foundry_pattern_status!=FOUNDRY_PATTERN_STATUS
            or self.state!=MANIFEST_DRAFT_STATE or self.manifest_digest!=canonical_digest(self.digest_value())):
            raise GovernanceRejected("valid non-deployable release evidence manifest draft required")
    def digest_value(self)->dict[str,object]:
        return {"artifact_digest":self.artifact_digest,"test_digest":self.test_digest,"evidence_digest":self.evidence_digest,
            "policy_digest":self.policy_digest,"drafted_at":self.drafted_at.isoformat(),"foundry_commit":self.foundry_commit,
            "foundry_pattern_id":self.foundry_pattern_id,"foundry_package_hash":self.foundry_package_hash,
            "foundry_pattern_status":self.foundry_pattern_status,"state":self.state,"clean_room_analog":True,
            "externally_promoted_pattern":False,"signed_release":False,"deployable":False,"deployment_allowed":False}
def draft_release_evidence_manifest(*,artifact_digest:str,test_digest:str,evidence_digest:str,policy_digest:str,drafted_at:datetime)->ArkaonReleaseEvidenceManifestDraft:
    values={"artifact_digest":artifact_digest,"test_digest":test_digest,"evidence_digest":evidence_digest,"policy_digest":policy_digest,
        "drafted_at":drafted_at.isoformat(),"foundry_commit":FOUNDRY_COMMIT,"foundry_pattern_id":FOUNDRY_PATTERN_ID,
        "foundry_package_hash":FOUNDRY_PACKAGE_HASH,"foundry_pattern_status":FOUNDRY_PATTERN_STATUS,"state":MANIFEST_DRAFT_STATE,
        "clean_room_analog":True,"externally_promoted_pattern":False,"signed_release":False,"deployable":False,"deployment_allowed":False}
    return ArkaonReleaseEvidenceManifestDraft(artifact_digest,test_digest,evidence_digest,policy_digest,drafted_at,FOUNDRY_COMMIT,
        FOUNDRY_PATTERN_ID,FOUNDRY_PACKAGE_HASH,FOUNDRY_PATTERN_STATUS,MANIFEST_DRAFT_STATE,canonical_digest(values))
def evidence(manifest:ArkaonReleaseEvidenceManifestDraft)->dict[str,object]:
    if not isinstance(manifest,ArkaonReleaseEvidenceManifestDraft):raise GovernanceRejected("typed release evidence manifest draft required")
    manifest.__post_init__()
    values={"schema":"nurion.pg.arkaon-release-evidence-manifest-draft-evidence.v1","mode":"UNREGISTERED_SYNTHETIC_ONLY",
        "manifest_digest":manifest.manifest_digest,"foundry_commit":manifest.foundry_commit,"foundry_pattern_id":manifest.foundry_pattern_id,
        "foundry_package_hash":manifest.foundry_package_hash,"foundry_pattern_status":manifest.foundry_pattern_status,
        "maximum_state":MANIFEST_DRAFT_STATE,"clean_room_analog":True,"external_signature_present":False,
        "pattern_promotion_present":False,"release_signing_method_present":False,"deployment_method_present":False,
        "network_access_method_present":False,"automatic_merge_method_present":False,"credentials_used":False,
        "money_movement_executed":False,"deployable":False,"deployment_allowed":False}
    return {**values,"report_digest":canonical_digest(values)}
