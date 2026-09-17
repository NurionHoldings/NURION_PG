"""Synthetic, non-authorizing role-separated benchmark for a PG release draft."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from .arkaon.governance import GovernanceRejected,canonical_digest
from .arkaon_release_evidence_manifest_draft import ArkaonReleaseEvidenceManifestDraft
FOUNDRY_COMMIT="24ae4a601ee449649e40804119fa37667f731076"
FOUNDRY_PATTERN_ID="apf.public.role-separated-benchmark"
FOUNDRY_PACKAGE_HASH="4bd1359b51ea2a958833ad52e91ab49b20b9f8777c6bb3d3f653504ac2f1eca7"
FOUNDRY_PATTERN_STATUS="ETHERNIAN_REVIEW_REQUIRED"
BENCHMARK_STATE="SYNTHETIC_PG_ROLE_SEPARATED_RELEASE_BENCHMARK_RECORDED"
class BenchmarkRole(StrEnum):
    PRODUCER="PRODUCER";ATTACKER="ATTACKER";JUDGE="JUDGE";APPROVER="APPROVER"
class BenchmarkOutcome(StrEnum):PASS="PASS";HOLD="HOLD"
def _valid_digest(v:object)->bool:return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
@dataclass(frozen=True)
class RoleResult:
    role:BenchmarkRole;actor_id:str;result_digest:str;passed:bool;critical_failure:bool=False
    def validate(self)->None:
        if (not isinstance(self.role,BenchmarkRole) or not isinstance(self.actor_id,str) or not self.actor_id.startswith("synthetic:")
            or not _valid_digest(self.result_digest) or type(self.passed) is not bool or type(self.critical_failure) is not bool):
            raise GovernanceRejected("valid synthetic role result required")
@dataclass(frozen=True)
class ArkaonRoleSeparatedReleaseBenchmark:
    manifest_digest:str;results:tuple[RoleResult,...];attack_findings_digest:str;judge_observed_attack_findings_digest:str
    recorded_at:datetime;outcome:BenchmarkOutcome;state:str;foundry_commit:str;foundry_pattern_id:str
    foundry_package_hash:str;foundry_pattern_status:str;benchmark_digest:str
    def __post_init__(self)->None:
        for result in self.results:result.validate()
        roles={r.role for r in self.results};actors={r.actor_id for r in self.results}
        expected=BenchmarkOutcome.PASS if all(r.passed and not r.critical_failure for r in self.results) else BenchmarkOutcome.HOLD
        if (not _valid_digest(self.manifest_digest) or len(self.results)!=4 or roles!=set(BenchmarkRole) or len(actors)!=4
            or not _valid_digest(self.attack_findings_digest) or self.judge_observed_attack_findings_digest!=self.attack_findings_digest
            or self.recorded_at.tzinfo is None or self.outcome is not expected or self.state!=BENCHMARK_STATE
            or self.foundry_commit!=FOUNDRY_COMMIT or self.foundry_pattern_id!=FOUNDRY_PATTERN_ID
            or self.foundry_package_hash!=FOUNDRY_PACKAGE_HASH or self.foundry_pattern_status!=FOUNDRY_PATTERN_STATUS
            or self.benchmark_digest!=canonical_digest(self.digest_value())):raise GovernanceRejected("valid role-separated release benchmark required")
    def digest_value(self)->dict[str,object]:
        return {"manifest_digest":self.manifest_digest,"results":[{"role":r.role.value,"actor_id":r.actor_id,
            "result_digest":r.result_digest,"passed":r.passed,"critical_failure":r.critical_failure} for r in self.results],
            "attack_findings_digest":self.attack_findings_digest,"judge_observed_attack_findings_digest":self.judge_observed_attack_findings_digest,
            "recorded_at":self.recorded_at.isoformat(),"outcome":self.outcome.value,"state":self.state,"foundry_commit":self.foundry_commit,
            "foundry_pattern_id":self.foundry_pattern_id,"foundry_package_hash":self.foundry_package_hash,
            "foundry_pattern_status":self.foundry_pattern_status,"release_approval":False,"deployment_allowed":False}
def record_role_separated_benchmark(manifest:ArkaonReleaseEvidenceManifestDraft,results:tuple[RoleResult,...],*,
    attack_findings_digest:str,judge_observed_attack_findings_digest:str,recorded_at:datetime)->ArkaonRoleSeparatedReleaseBenchmark:
    if not isinstance(manifest,ArkaonReleaseEvidenceManifestDraft):raise GovernanceRejected("typed release manifest draft required")
    if not isinstance(results,tuple) or any(not isinstance(r,RoleResult) for r in results):
        raise GovernanceRejected("typed role result tuple required")
    for result in results:result.validate()
    manifest.__post_init__();outcome=BenchmarkOutcome.PASS if all(r.passed and not r.critical_failure for r in results) else BenchmarkOutcome.HOLD
    values={"manifest_digest":manifest.manifest_digest,"results":[{"role":r.role.value,"actor_id":r.actor_id,
        "result_digest":r.result_digest,"passed":r.passed,"critical_failure":r.critical_failure} for r in results],
        "attack_findings_digest":attack_findings_digest,"judge_observed_attack_findings_digest":judge_observed_attack_findings_digest,
        "recorded_at":recorded_at.isoformat(),"outcome":outcome.value,"state":BENCHMARK_STATE,"foundry_commit":FOUNDRY_COMMIT,
        "foundry_pattern_id":FOUNDRY_PATTERN_ID,"foundry_package_hash":FOUNDRY_PACKAGE_HASH,"foundry_pattern_status":FOUNDRY_PATTERN_STATUS,
        "release_approval":False,"deployment_allowed":False}
    return ArkaonRoleSeparatedReleaseBenchmark(manifest.manifest_digest,results,attack_findings_digest,judge_observed_attack_findings_digest,
        recorded_at,outcome,BENCHMARK_STATE,FOUNDRY_COMMIT,FOUNDRY_PATTERN_ID,FOUNDRY_PACKAGE_HASH,FOUNDRY_PATTERN_STATUS,canonical_digest(values))
def evidence(item:ArkaonRoleSeparatedReleaseBenchmark)->dict[str,object]:
    if not isinstance(item,ArkaonRoleSeparatedReleaseBenchmark):raise GovernanceRejected("typed role-separated benchmark required")
    item.__post_init__();values={"schema":"nurion.pg.arkaon-role-separated-release-benchmark-evidence.v1","mode":"UNREGISTERED_SYNTHETIC_ONLY",
        "benchmark_digest":item.benchmark_digest,"outcome":item.outcome.value,"role_count":len(item.results),"unique_actor_count":len({r.actor_id for r in item.results}),
        "attack_findings_visible_to_judge":item.attack_findings_digest==item.judge_observed_attack_findings_digest,
        "critical_failure_vetoed":item.outcome is BenchmarkOutcome.HOLD if any(r.critical_failure for r in item.results) else True,
        "maximum_state":BENCHMARK_STATE,"foundry_pattern_status":FOUNDRY_PATTERN_STATUS,"release_approval_present":False,
        "deployment_method_present":False,"network_access_method_present":False,"automatic_merge_method_present":False,
        "credentials_used":False,"money_movement_executed":False,"deployment_allowed":False}
    return {**values,"report_digest":canonical_digest(values)}
