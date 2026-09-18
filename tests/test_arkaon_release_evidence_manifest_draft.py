from __future__ import annotations
import unittest
from hashlib import sha256
from nurion_pg.arkaon.governance import GovernanceRejected,canonical_digest
from nurion_pg.arkaon_release_evidence_manifest_draft import FOUNDRY_COMMIT,FOUNDRY_PACKAGE_HASH,FOUNDRY_PATTERN_STATUS,MANIFEST_DRAFT_STATE,draft_release_evidence_manifest,evidence
from tests.test_patch_draft_limited_promotion_reconfirmation_intake import NOW
def digest(label:bytes)->str:return sha256(label).hexdigest()
def manifest():
    return draft_release_evidence_manifest(artifact_digest=digest(b"artifact"),test_digest=digest(b"tests"),
        evidence_digest=digest(b"evidence"),policy_digest=digest(b"policy"),drafted_at=NOW)
class ArkaonReleaseEvidenceManifestDraftTests(unittest.TestCase):
    def test_exact_binding_and_non_deployable_authority(self):
        item=manifest();self.assertEqual(item.state,MANIFEST_DRAFT_STATE);self.assertEqual(item.foundry_commit,FOUNDRY_COMMIT)
        self.assertEqual(item.foundry_package_hash,FOUNDRY_PACKAGE_HASH);self.assertEqual(item.foundry_pattern_status,FOUNDRY_PATTERN_STATUS)
        report=evidence(item)
        for key in report:
            if key.endswith("_present") or key.endswith("_allowed") or key.endswith("_executed") or key.endswith("_used") or key=="deployable":self.assertFalse(report[key])
    def test_invalid_digest_and_naive_time_fail_closed(self):
        with self.assertRaises(GovernanceRejected):draft_release_evidence_manifest(artifact_digest="bad",test_digest=digest(b"t"),evidence_digest=digest(b"e"),policy_digest=digest(b"p"),drafted_at=NOW)
        with self.assertRaises(GovernanceRejected):draft_release_evidence_manifest(artifact_digest=digest(b"a"),test_digest=digest(b"t"),evidence_digest=digest(b"e"),policy_digest=digest(b"p"),drafted_at=NOW.replace(tzinfo=None))
    def test_provenance_status_tamper_fails_closed(self):
        item=manifest();object.__setattr__(item,"foundry_pattern_status","PROMOTED");object.__setattr__(item,"manifest_digest",canonical_digest(item.digest_value()))
        with self.assertRaises(GovernanceRejected):evidence(item)
if __name__=="__main__":unittest.main()
