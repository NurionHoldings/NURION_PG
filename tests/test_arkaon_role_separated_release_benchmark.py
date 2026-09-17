from __future__ import annotations
import unittest
from hashlib import sha256
from nurion_pg.arkaon.governance import GovernanceRejected,canonical_digest
from nurion_pg.arkaon_release_evidence_manifest_draft import draft_release_evidence_manifest
from nurion_pg.arkaon_role_separated_release_benchmark import BenchmarkOutcome,BenchmarkRole,RoleResult,evidence,record_role_separated_benchmark
from tests.test_patch_draft_limited_promotion_reconfirmation_intake import NOW
def h(v:bytes)->str:return sha256(v).hexdigest()
def manifest():return draft_release_evidence_manifest(artifact_digest=h(b"a"),test_digest=h(b"t"),evidence_digest=h(b"e"),policy_digest=h(b"p"),drafted_at=NOW)
def results(critical=False):return tuple(RoleResult(role,f"synthetic:{role.value.lower()}",h(role.value.encode()),True,critical and role is BenchmarkRole.ATTACKER) for role in BenchmarkRole)
class RoleSeparatedBenchmarkTests(unittest.TestCase):
    def test_four_distinct_roles_and_non_authority(self):
        findings=h(b"findings");item=record_role_separated_benchmark(manifest(),results(),attack_findings_digest=findings,judge_observed_attack_findings_digest=findings,recorded_at=NOW)
        self.assertIs(item.outcome,BenchmarkOutcome.PASS);report=evidence(item);self.assertEqual(report["unique_actor_count"],4)
        for key in report:
            if key.endswith("_present") or key.endswith("_allowed") or key.endswith("_executed") or key.endswith("_used"):self.assertFalse(report[key])
    def test_duplicate_actor_fails_closed(self):
        r=list(results());r[-1]=RoleResult(BenchmarkRole.APPROVER,r[0].actor_id,h(b"approver"),True)
        with self.assertRaises(GovernanceRejected):record_role_separated_benchmark(manifest(),tuple(r),attack_findings_digest=h(b"f"),judge_observed_attack_findings_digest=h(b"f"),recorded_at=NOW)
        with self.assertRaises(GovernanceRejected):record_role_separated_benchmark(manifest(),(object(),),attack_findings_digest=h(b"f"),judge_observed_attack_findings_digest=h(b"f"),recorded_at=NOW)
    def test_hidden_findings_fail_and_critical_failure_holds(self):
        with self.assertRaises(GovernanceRejected):record_role_separated_benchmark(manifest(),results(),attack_findings_digest=h(b"f"),judge_observed_attack_findings_digest=h(b"hidden"),recorded_at=NOW)
        item=record_role_separated_benchmark(manifest(),results(True),attack_findings_digest=h(b"f"),judge_observed_attack_findings_digest=h(b"f"),recorded_at=NOW)
        self.assertIs(item.outcome,BenchmarkOutcome.HOLD);self.assertTrue(evidence(item)["critical_failure_vetoed"])
    def test_provenance_tamper_fails_closed(self):
        f=h(b"f");item=record_role_separated_benchmark(manifest(),results(),attack_findings_digest=f,judge_observed_attack_findings_digest=f,recorded_at=NOW)
        object.__setattr__(item,"foundry_pattern_status","PROMOTED");object.__setattr__(item,"benchmark_digest",canonical_digest(item.digest_value()))
        with self.assertRaises(GovernanceRejected):evidence(item)
if __name__=="__main__":unittest.main()
