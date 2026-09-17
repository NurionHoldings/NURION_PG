from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.patch_operator_decision_intake import (
    SyntheticPatchOperatorDecision,
    SyntheticPatchOperatorDecisionIntake,
)
from nurion_pg.patch_operator_decision_receipt_ledger import (
    SyntheticPatchDecisionReceiptLedger,
)
from nurion_pg.synthetic_patch_draft_manifests import (
    ALLOWED_PATCH_DRAFT_SCOPES,
    PATCH_DRAFT_MANIFEST_STATE,
    REQUIRED_PATCH_DRAFT_CHECKS,
    SyntheticPatchDraftManifestBook,
)
from tests.test_operator_decision_intake import key_registry
from tests.test_patch_operator_decision_intake import (
    NOW,
    decision_envelope,
    packet_source,
)
from tests.test_synthetic_patch_shadow_review_docket import close_resources


SCOPES = ALLOWED_PATCH_DRAFT_SCOPES[:2]
TARGETS = tuple(sha256(f"target:{item}".encode("ascii")).hexdigest() for item in SCOPES)


def receipted_source(
    decision: SyntheticPatchOperatorDecision = (
        SyntheticPatchOperatorDecision.AUTHORIZE_SYNTHETIC_PATCH_DRAFT
    ),
):
    resources, docket, record, packet_book, packet = packet_source()
    intake = SyntheticPatchOperatorDecisionIntake(key_registry())
    envelope = decision_envelope(packet, decision=decision)
    intake.assess(packet_book, record.shadow_id, envelope, received_at=NOW)
    ledger = SyntheticPatchDecisionReceiptLedger(":memory:")
    receipt = ledger.record_from_intake(intake, envelope.envelope_id, recorded_at=NOW)
    return resources, docket, ledger, receipt


class SyntheticPatchDraftManifestTests(unittest.TestCase):
    def test_authorized_receipt_creates_metadata_only_manifest(self):
        resources, docket, ledger, receipt = receipted_source()
        manifest = SyntheticPatchDraftManifestBook().draft_from_receipt(
            ledger,
            receipt.receipt_id,
            draft_scopes=SCOPES,
            target_path_digests=TARGETS,
            drafted_at=NOW,
        )
        self.assertEqual(manifest.state, PATCH_DRAFT_MANIFEST_STATE)
        self.assertEqual(manifest.required_checks, REQUIRED_PATCH_DRAFT_CHECKS)
        self.assertTrue(manifest.eternian_review_required)
        for value in (
            manifest.patch_content_present,
            manifest.diff_content_present,
            manifest.source_code_changed,
            manifest.filesystem_written,
            manifest.automatic_application_allowed,
            manifest.execution_allowed,
            manifest.production_activation_allowed,
        ):
            self.assertFalse(value)
        ledger.close()
        close_resources(resources, docket)

    def test_hold_and_reject_cannot_create_manifests(self):
        for decision in (
            SyntheticPatchOperatorDecision.HOLD,
            SyntheticPatchOperatorDecision.REJECT,
        ):
            resources, docket, ledger, receipt = receipted_source(decision)
            with self.assertRaises(GovernanceRejected):
                SyntheticPatchDraftManifestBook().draft_from_receipt(
                    ledger,
                    receipt.receipt_id,
                    draft_scopes=SCOPES,
                    target_path_digests=TARGETS,
                    drafted_at=NOW,
                )
            ledger.close()
            close_resources(resources, docket)

    def test_requires_typed_intact_receipt_ledger(self):
        with self.assertRaises(GovernanceRejected):
            SyntheticPatchDraftManifestBook().draft_from_receipt(
                object(),
                "synthetic:patch-decision-receipt:fake",
                draft_scopes=SCOPES,
                target_path_digests=TARGETS,
                drafted_at=NOW,
            )
        resources, docket, ledger, receipt = receipted_source()
        ledger._connection.execute(
            "UPDATE synthetic_patch_decision_receipt_audit SET audit_digest = ?",
            ("f" * 64,),
        )
        with self.assertRaises(GovernanceRejected):
            SyntheticPatchDraftManifestBook().draft_from_receipt(
                ledger,
                receipt.receipt_id,
                draft_scopes=SCOPES,
                target_path_digests=TARGETS,
                drafted_at=NOW,
            )
        ledger.close()
        close_resources(resources, docket)

    def test_scopes_and_target_digests_are_strictly_validated(self):
        resources, docket, ledger, receipt = receipted_source()
        invalid = (
            ((), ()),
            (("UNKNOWN_SCOPE",), ("a" * 64,)),
            ((SCOPES[0], SCOPES[0]), TARGETS),
            (tuple(reversed(SCOPES)), TARGETS),
            (SCOPES, TARGETS[:1]),
            (SCOPES, (TARGETS[0], TARGETS[0])),
            (SCOPES, ("not-a-digest", TARGETS[1])),
        )
        for scopes, targets in invalid:
            with self.assertRaises(GovernanceRejected):
                SyntheticPatchDraftManifestBook().draft_from_receipt(
                    ledger,
                    receipt.receipt_id,
                    draft_scopes=scopes,
                    target_path_digests=targets,
                    drafted_at=NOW,
                )
        ledger.close()
        close_resources(resources, docket)

    def test_draft_time_cannot_predate_receipt_or_be_naive(self):
        resources, docket, ledger, receipt = receipted_source()
        book = SyntheticPatchDraftManifestBook()
        for value in (NOW - timedelta(seconds=1), NOW.replace(tzinfo=None)):
            with self.assertRaises(GovernanceRejected):
                book.draft_from_receipt(
                    ledger,
                    receipt.receipt_id,
                    draft_scopes=SCOPES,
                    target_path_digests=TARGETS,
                    drafted_at=value,
                )
        ledger.close()
        close_resources(resources, docket)

    def test_exact_replay_is_idempotent_and_scope_collision_is_blocked(self):
        resources, docket, ledger, receipt = receipted_source()
        book = SyntheticPatchDraftManifestBook()
        first = book.draft_from_receipt(
            ledger,
            receipt.receipt_id,
            draft_scopes=SCOPES,
            target_path_digests=TARGETS,
            drafted_at=NOW,
        )
        second = book.draft_from_receipt(
            ledger,
            receipt.receipt_id,
            draft_scopes=SCOPES,
            target_path_digests=TARGETS,
            drafted_at=NOW + timedelta(seconds=1),
        )
        self.assertEqual(first, second)
        with self.assertRaises(GovernanceRejected):
            book.draft_from_receipt(
                ledger,
                receipt.receipt_id,
                draft_scopes=SCOPES[:1],
                target_path_digests=TARGETS[:1],
                drafted_at=NOW,
            )
        ledger.close()
        close_resources(resources, docket)

    def test_concurrent_replay_records_one_manifest(self):
        resources, docket, ledger, receipt = receipted_source()
        book = SyntheticPatchDraftManifestBook()

        def draft(_):
            return book.draft_from_receipt(
                ledger,
                receipt.receipt_id,
                draft_scopes=SCOPES,
                target_path_digests=TARGETS,
                drafted_at=NOW,
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            manifests = list(pool.map(draft, range(8)))
        self.assertTrue(all(item == manifests[0] for item in manifests))
        self.assertEqual(len(book.manifests), 1)
        self.assertTrue(book.verify_manifest_chain())
        ledger.close()
        close_resources(resources, docket)

    def test_source_receipt_is_read_only(self):
        resources, docket, ledger, receipt = receipted_source()
        before = ledger.evidence()["report_digest"]
        SyntheticPatchDraftManifestBook().draft_from_receipt(
            ledger,
            receipt.receipt_id,
            draft_scopes=SCOPES,
            target_path_digests=TARGETS,
            drafted_at=NOW,
        )
        self.assertEqual(before, ledger.evidence()["report_digest"])
        ledger.close()
        close_resources(resources, docket)

    def test_manifest_and_rehashed_source_tampering_fail_closed(self):
        resources, docket, ledger, receipt = receipted_source()
        book = SyntheticPatchDraftManifestBook()
        manifest = book.draft_from_receipt(
            ledger,
            receipt.receipt_id,
            draft_scopes=SCOPES,
            target_path_digests=TARGETS,
            drafted_at=NOW,
        )
        object.__setattr__(manifest, "source_receipt_digest", "f" * 64)
        object.__setattr__(
            manifest, "manifest_digest", canonical_digest(manifest.digest_value())
        )
        self.assertFalse(book.verify_manifest_chain())
        with self.assertRaises(GovernanceRejected):
            book.draft_from_receipt(
                ledger,
                receipt.receipt_id,
                draft_scopes=SCOPES,
                target_path_digests=TARGETS,
                drafted_at=NOW,
            )
        ledger.close()
        close_resources(resources, docket)

    def test_evidence_exposes_no_patch_or_execution_authority(self):
        resources, docket, ledger, receipt = receipted_source()
        book = SyntheticPatchDraftManifestBook()
        book.draft_from_receipt(
            ledger,
            receipt.receipt_id,
            draft_scopes=SCOPES,
            target_path_digests=TARGETS,
            drafted_at=NOW,
        )
        evidence = book.evidence()
        self.assertTrue(evidence["manifest_chain_valid"])
        self.assertTrue(evidence["metadata_only"])
        self.assertEqual(evidence["maximum_state"], PATCH_DRAFT_MANIFEST_STATE)
        for field in (
            "patch_content_present", "diff_content_present", "source_code_changed",
            "filesystem_written", "application_method_present",
            "safety_baseline_relaxation_allowed", "execution_method_present",
            "network_access_method_present", "personal_data_used", "credentials_used",
            "money_movement_executed", "production_activation_allowed",
        ):
            self.assertFalse(evidence[field])
        ledger.close()
        close_resources(resources, docket)


if __name__ == "__main__":
    unittest.main()
