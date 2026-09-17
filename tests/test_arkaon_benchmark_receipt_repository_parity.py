from __future__ import annotations
import unittest
from hashlib import sha256
from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.arkaon_benchmark_receipt_repository_parity import BenchmarkReceipt,MemoryBenchmarkReceiptRepository,SQLiteBenchmarkReceiptRepository,SYNTHETIC_NAMESPACE,_receipt,verify_repository_contract
from nurion_pg.arkaon_release_evidence_manifest_draft import draft_release_evidence_manifest
from nurion_pg.arkaon_role_separated_release_benchmark import BenchmarkRole,RoleResult,record_role_separated_benchmark
from tests.test_patch_draft_limited_promotion_reconfirmation_intake import NOW
def h(v:bytes)->str:return sha256(v).hexdigest()
def benchmark():
    manifest=draft_release_evidence_manifest(artifact_digest=h(b"a"),test_digest=h(b"t"),evidence_digest=h(b"e"),policy_digest=h(b"p"),drafted_at=NOW)
    results=tuple(RoleResult(role,f"synthetic:{role.value.lower()}",h(role.value.encode()),True) for role in BenchmarkRole);findings=h(b"f")
    return record_role_separated_benchmark(manifest,results,attack_findings_digest=findings,judge_observed_attack_findings_digest=findings,recorded_at=NOW)
class RepositoryParityTests(unittest.TestCase):
    def test_memory_sqlite_contract_parity(self):
        report=verify_repository_contract(benchmark(),idempotency_key="synthetic:parity:one")
        self.assertTrue(report["idempotent_retry_equal"]);self.assertTrue(report["adapter_outcomes_equal"])
        for key in report:
            if key.endswith("_present") or key.endswith("_allowed") or key.endswith("_executed") or key.endswith("_used"):self.assertFalse(report[key])
    def test_same_key_different_payload_rejected_by_both(self):
        one=_receipt(SYNTHETIC_NAMESPACE,"synthetic:key",h(b"one"),"PASS");two=_receipt(SYNTHETIC_NAMESPACE,"synthetic:key",h(b"two"),"HOLD")
        memory=MemoryBenchmarkReceiptRepository();sqlite=SQLiteBenchmarkReceiptRepository()
        try:
            memory.save(one);sqlite.save(one)
            with self.assertRaises(GovernanceRejected):memory.save(two)
            with self.assertRaises(GovernanceRejected):sqlite.save(two)
        finally:sqlite.close()
    def test_untyped_receipt_and_benchmark_fail_closed(self):
        with self.assertRaises(GovernanceRejected):MemoryBenchmarkReceiptRepository().save(object())
        with self.assertRaises(GovernanceRejected):verify_repository_contract(object(),idempotency_key="synthetic:key")
    def test_receipt_tamper_fails_closed(self):
        item=_receipt(SYNTHETIC_NAMESPACE,"synthetic:key",h(b"one"),"PASS");object.__setattr__(item,"outcome","HOLD")
        with self.assertRaises(GovernanceRejected):MemoryBenchmarkReceiptRepository().save(item)
if __name__=="__main__":unittest.main()
