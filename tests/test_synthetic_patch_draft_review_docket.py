from __future__ import annotations

import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256
from pathlib import Path

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_patch_draft_manifests import SyntheticPatchDraftManifestBook
from nurion_pg.synthetic_patch_draft_review_docket import (
    MAXIMUM_PATCH_DRAFT_REVIEW_STATE,
    PatchDraftReviewDecision,
    PatchDraftReviewState,
    SyntheticPatchDraftReviewDocket,
)
from tests.test_patch_operator_decision_intake import NOW
from tests.test_synthetic_patch_draft_manifests import (
    SCOPES,
    TARGETS,
    receipted_source,
)
from tests.test_synthetic_patch_shadow_review_docket import close_resources


FINDINGS = sha256(b"patch draft review findings").hexdigest()


def manifest_source():
    resources, docket, ledger, receipt = receipted_source()
    book = SyntheticPatchDraftManifestBook()
    manifest = book.draft_from_receipt(
        ledger,
        receipt.receipt_id,
        draft_scopes=SCOPES,
        target_path_digests=TARGETS,
        drafted_at=NOW,
    )
    return resources, docket, ledger, book, manifest


def close_source(resources, docket, ledger):
    ledger.close()
    close_resources(resources, docket)


class SyntheticPatchDraftReviewDocketTests(unittest.TestCase):
    def test_requires_synthetic_sqlite_target(self):
        with self.assertRaises(GovernanceRejected):
            SyntheticPatchDraftReviewDocket("patch-review.sqlite3")
        with self.assertRaises(GovernanceRejected):
            SyntheticPatchDraftReviewDocket("postgresql://prod/review")

    def test_manifest_is_persisted_pending_review_without_authority(self):
        resources, source_docket, ledger, book, manifest = manifest_source()
        review = SyntheticPatchDraftReviewDocket(":memory:")
        record = review.submit_from_book(
            book, manifest.source_receipt_id, submitted_at=NOW
        )
        self.assertEqual(record.state, PatchDraftReviewState.PENDING_ETERNIAN_REVIEW)
        self.assertIsNone(record.review_id)
        self.assertFalse(record.patch_content_present)
        self.assertFalse(record.diff_content_present)
        self.assertFalse(record.source_code_changed)
        self.assertTrue(review.verify_record_bindings())
        review.close()
        close_source(resources, source_docket, ledger)

    def test_pass_stops_at_ready_for_synthetic_patch_draft_shadow(self):
        resources, source_docket, ledger, book, manifest = manifest_source()
        review = SyntheticPatchDraftReviewDocket(":memory:")
        review.submit_from_book(book, manifest.source_receipt_id, submitted_at=NOW)
        record = review.record_eternian_review(
            manifest.manifest_id,
            review_id="synthetic:patch-draft-review:pass",
            reviewer_id="synthetic:eternian-reviewer:patch-draft:pass",
            decision=PatchDraftReviewDecision.PASS,
            findings_digest=FINDINGS,
            reviewed_at=NOW,
        )
        self.assertEqual(
            record.state,
            PatchDraftReviewState.READY_FOR_SYNTHETIC_PATCH_DRAFT_SHADOW,
        )
        self.assertEqual(review.ready_source(manifest.manifest_id), record)
        self.assertFalse(record.automatic_application_allowed)
        self.assertFalse(record.production_activation_allowed)
        review.close()
        close_source(resources, source_docket, ledger)

    def test_hold_and_reject_are_terminal_and_not_shadow_ready(self):
        for decision, expected in (
            (PatchDraftReviewDecision.HOLD, PatchDraftReviewState.HELD),
            (PatchDraftReviewDecision.REJECT, PatchDraftReviewState.REJECTED),
        ):
            resources, source_docket, ledger, book, manifest = manifest_source()
            review = SyntheticPatchDraftReviewDocket(":memory:")
            review.submit_from_book(book, manifest.source_receipt_id, submitted_at=NOW)
            record = review.record_eternian_review(
                manifest.manifest_id,
                review_id=f"synthetic:patch-draft-review:{decision.value.lower()}",
                reviewer_id=(
                    "synthetic:eternian-reviewer:patch-draft:"
                    f"{decision.value.lower()}"
                ),
                decision=decision,
                findings_digest=FINDINGS,
                reviewed_at=NOW,
            )
            self.assertEqual(record.state, expected)
            with self.assertRaises(GovernanceRejected):
                review.ready_source(manifest.manifest_id)
            review.close()
            close_source(resources, source_docket, ledger)

    def test_requires_typed_intact_book_and_valid_submission_time(self):
        review = SyntheticPatchDraftReviewDocket(":memory:")
        with self.assertRaises(GovernanceRejected):
            review.submit_from_book(object(), "synthetic:receipt:fake", submitted_at=NOW)
        resources, source_docket, ledger, book, manifest = manifest_source()
        with self.assertRaises(GovernanceRejected):
            review.submit_from_book(
                book, manifest.source_receipt_id,
                submitted_at=NOW - timedelta(seconds=1),
            )
        with self.assertRaises(GovernanceRejected):
            review.submit_from_book(
                book, manifest.source_receipt_id,
                submitted_at=NOW.replace(tzinfo=None),
            )
        object.__setattr__(manifest, "patch_content_present", True)
        with self.assertRaises(GovernanceRejected):
            review.submit_from_book(book, manifest.source_receipt_id, submitted_at=NOW)
        review.close()
        close_source(resources, source_docket, ledger)

    def test_submission_replay_is_idempotent_and_collision_fails(self):
        resources, source_docket, ledger, book, manifest = manifest_source()
        review = SyntheticPatchDraftReviewDocket(":memory:")
        first = review.submit_from_book(book, manifest.source_receipt_id, submitted_at=NOW)
        second = review.submit_from_book(
            book, manifest.source_receipt_id, submitted_at=NOW + timedelta(seconds=1)
        )
        self.assertEqual(first, second)
        object.__setattr__(manifest, "manifest_digest", "f" * 64)
        with self.assertRaises(GovernanceRejected):
            review.submit_from_book(book, manifest.source_receipt_id, submitted_at=NOW)
        review.close()
        close_source(resources, source_docket, ledger)

    def test_review_metadata_time_and_concurrent_idempotency(self):
        resources, source_docket, ledger, book, manifest = manifest_source()
        review = SyntheticPatchDraftReviewDocket(":memory:")
        review.submit_from_book(book, manifest.source_receipt_id, submitted_at=NOW)
        invalid = (
            ("bad", "synthetic:eternian-reviewer:patch-draft:x", NOW),
            ("synthetic:patch-draft-review:x", "bad", NOW),
            (
                "synthetic:patch-draft-review:x",
                "synthetic:eternian-reviewer:patch-draft:x",
                NOW.replace(tzinfo=None),
            ),
        )
        for review_id, reviewer_id, reviewed_at in invalid:
            with self.assertRaises(GovernanceRejected):
                review.record_eternian_review(
                    manifest.manifest_id,
                    review_id=review_id,
                    reviewer_id=reviewer_id,
                    decision=PatchDraftReviewDecision.PASS,
                    findings_digest=FINDINGS,
                    reviewed_at=reviewed_at,
                )

        def record(_):
            return review.record_eternian_review(
                manifest.manifest_id,
                review_id="synthetic:patch-draft-review:concurrent",
                reviewer_id="synthetic:eternian-reviewer:patch-draft:concurrent",
                decision=PatchDraftReviewDecision.PASS,
                findings_digest=FINDINGS,
                reviewed_at=NOW,
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            records = list(pool.map(record, range(8)))
        self.assertTrue(all(item == records[0] for item in records))
        self.assertTrue(review.verify_record_bindings())
        review.close()
        close_source(resources, source_docket, ledger)

    def test_restart_preserves_review_and_integrity(self):
        resources, source_docket, ledger, book, manifest = manifest_source()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic-patch-draft-reviews.sqlite3"
            review = SyntheticPatchDraftReviewDocket(path)
            review.submit_from_book(book, manifest.source_receipt_id, submitted_at=NOW)
            expected = review.record_eternian_review(
                manifest.manifest_id,
                review_id="synthetic:patch-draft-review:restart",
                reviewer_id="synthetic:eternian-reviewer:patch-draft:restart",
                decision=PatchDraftReviewDecision.PASS,
                findings_digest=FINDINGS,
                reviewed_at=NOW,
            )
            report = review.evidence()
            review.close()
            reopened = SyntheticPatchDraftReviewDocket(path)
            self.assertEqual(reopened.get(manifest.manifest_id), expected)
            self.assertEqual(reopened.evidence(), report)
            reopened.close()
        close_source(resources, source_docket, ledger)

    def test_audit_failure_rolls_back_submission_and_review(self):
        resources, source_docket, ledger, book, manifest = manifest_source()
        review = SyntheticPatchDraftReviewDocket(":memory:")

        def fail(*_):
            raise sqlite3.IntegrityError("audit failure")

        review._append_audit = fail
        with self.assertRaises(GovernanceRejected):
            review.submit_from_book(book, manifest.source_receipt_id, submitted_at=NOW)
        self.assertEqual(
            review._connection.execute(
                "SELECT COUNT(*) FROM synthetic_patch_draft_review_records"
            ).fetchone()[0],
            0,
        )
        review.close()
        close_source(resources, source_docket, ledger)

    def test_stored_manifest_and_audit_tampering_are_detected(self):
        resources, source_docket, ledger, book, manifest = manifest_source()
        review = SyntheticPatchDraftReviewDocket(":memory:")
        review.submit_from_book(book, manifest.source_receipt_id, submitted_at=NOW)
        review._connection.execute(
            "UPDATE synthetic_patch_draft_review_audit SET audit_digest = ?",
            ("f" * 64,),
        )
        self.assertFalse(review.verify_record_bindings())
        with self.assertRaises(GovernanceRejected):
            review.ready_source(manifest.manifest_id)
        review._connection.execute(
            "UPDATE synthetic_patch_draft_review_records SET manifest_json = '{}'"
        )
        with self.assertRaises(GovernanceRejected):
            review.get(manifest.manifest_id)
        review.close()
        close_source(resources, source_docket, ledger)

    def test_evidence_caps_state_and_exposes_no_patch_authority(self):
        resources, source_docket, ledger, book, manifest = manifest_source()
        review = SyntheticPatchDraftReviewDocket(":memory:")
        review.submit_from_book(book, manifest.source_receipt_id, submitted_at=NOW)
        evidence = review.evidence()
        self.assertEqual(evidence["maximum_state"], MAXIMUM_PATCH_DRAFT_REVIEW_STATE)
        self.assertTrue(evidence["audit_chain_valid"])
        self.assertTrue(evidence["record_bindings_valid"])
        for field in (
            "patch_content_present", "diff_content_present", "source_code_changed",
            "filesystem_written", "application_method_present",
            "safety_baseline_relaxation_method_present", "execution_method_present",
            "network_access_method_present", "money_movement_executed",
            "production_activation_allowed",
        ):
            self.assertFalse(evidence[field])
        review.close()
        close_source(resources, source_docket, ledger)


if __name__ == "__main__":
    unittest.main()
