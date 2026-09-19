from __future__ import annotations

import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256
from pathlib import Path

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_patch_draft_limited_promotion_activation_manifests import (
    SyntheticPatchDraftLimitedPromotionActivationManifestBook,
)
from nurion_pg.synthetic_patch_draft_limited_promotion_activation_review_docket import (
    MAXIMUM_ACTIVATION_MANIFEST_REVIEW_STATE,
    ActivationManifestReviewDecision,
    ActivationManifestReviewState,
    SyntheticPatchDraftLimitedPromotionActivationReviewDocket,
)
from tests.test_patch_draft_limited_promotion_reconfirmation_intake import NOW
from tests.test_synthetic_patch_draft_limited_promotion_activation_manifests import (
    activation_sources,
)
from tests.test_synthetic_patch_draft_limited_promotion_shadow_review_docket import (
    close_resources,
)


FINDINGS = sha256(b"activation final review findings").hexdigest()


def manifest_source():
    resources, source_docket, ledger, packet_book, _, receipt = activation_sources()
    book = SyntheticPatchDraftLimitedPromotionActivationManifestBook()
    manifest = book.draft_from_receipt(
        ledger, receipt.receipt_id, packet_book, drafted_at=NOW
    )
    return (resources, source_docket, ledger), book, manifest


def close_all(resources, docket=None):
    source_resources, source_docket, ledger = resources
    if docket is not None:
        docket.close()
    ledger.close()
    close_resources(source_resources, source_docket)


def review(docket, manifest_id, decision, **overrides):
    values = {
        "review_id": (
            "synthetic:limited-promotion-activation-final-review:"
            f"{decision.value.lower()}"
        ),
        "reviewer_id": (
            "synthetic:eternian-reviewer:limited-promotion-activation:"
            f"{decision.value.lower()}"
        ),
        "decision": decision,
        "findings_digest": FINDINGS,
        "reviewed_at": NOW,
    }
    values.update(overrides)
    return docket.record_eternian_review(manifest_id, **values)


class ActivationManifestReviewDocketTests(unittest.TestCase):
    def test_submit_pending_and_pass_to_operator_decision_ready(self):
        resources, book, manifest = manifest_source()
        docket = SyntheticPatchDraftLimitedPromotionActivationReviewDocket(":memory:")
        pending = docket.submit_from_book(book, manifest.manifest_id, submitted_at=NOW)
        self.assertEqual(pending.state, ActivationManifestReviewState.PENDING_ETERNIAN_FINAL_REVIEW)
        reviewed = review(docket, manifest.manifest_id, ActivationManifestReviewDecision.PASS)
        self.assertEqual(
            reviewed.state,
            ActivationManifestReviewState.READY_FOR_SYNTHETIC_LIMITED_PROMOTION_OPERATOR_DECISION,
        )
        self.assertFalse(reviewed.operator_decision_recorded)
        self.assertFalse(reviewed.activation_allowed)
        close_all(resources, docket)

    def test_hold_and_reject_never_create_ready_source(self):
        for decision, expected in (
            (ActivationManifestReviewDecision.HOLD, ActivationManifestReviewState.HELD),
            (ActivationManifestReviewDecision.REJECT, ActivationManifestReviewState.REJECTED),
        ):
            resources, book, manifest = manifest_source()
            docket = SyntheticPatchDraftLimitedPromotionActivationReviewDocket(":memory:")
            docket.submit_from_book(book, manifest.manifest_id, submitted_at=NOW)
            self.assertEqual(review(docket, manifest.manifest_id, decision).state, expected)
            with self.assertRaises(GovernanceRejected):
                docket.ready_source(manifest.manifest_id)
            close_all(resources, docket)

    def test_typed_time_ids_and_database_targets_fail_closed(self):
        for target in ("review.sqlite3", "file:synthetic-review.sqlite3", "postgres://prod"):
            with self.assertRaises(GovernanceRejected):
                SyntheticPatchDraftLimitedPromotionActivationReviewDocket(target)
        resources, book, manifest = manifest_source()
        docket = SyntheticPatchDraftLimitedPromotionActivationReviewDocket(":memory:")
        with self.assertRaises(GovernanceRejected):
            docket.submit_from_book(object(), manifest.manifest_id, submitted_at=NOW)
        for value in (NOW - timedelta(seconds=1), NOW.replace(tzinfo=None)):
            with self.assertRaises(GovernanceRejected):
                docket.submit_from_book(book, manifest.manifest_id, submitted_at=value)
        docket.submit_from_book(book, manifest.manifest_id, submitted_at=NOW)
        for override in (
            {"review_id": "bad"}, {"reviewer_id": "bad"},
            {"findings_digest": "bad"},
            {"reviewed_at": NOW - timedelta(seconds=1)},
        ):
            with self.assertRaises(GovernanceRejected):
                review(docket, manifest.manifest_id, ActivationManifestReviewDecision.PASS, **override)
        close_all(resources, docket)

    def test_submission_and_review_are_idempotent(self):
        resources, book, manifest = manifest_source()
        docket = SyntheticPatchDraftLimitedPromotionActivationReviewDocket(":memory:")
        first = docket.submit_from_book(book, manifest.manifest_id, submitted_at=NOW)
        self.assertEqual(first, docket.submit_from_book(book, manifest.manifest_id, submitted_at=NOW))
        reviewed = review(docket, manifest.manifest_id, ActivationManifestReviewDecision.PASS)
        self.assertEqual(reviewed, review(docket, manifest.manifest_id, ActivationManifestReviewDecision.PASS))
        with self.assertRaises(GovernanceRejected):
            review(
                docket, manifest.manifest_id, ActivationManifestReviewDecision.PASS,
                findings_digest=sha256(b"changed").hexdigest(),
            )
        close_all(resources, docket)

    def test_concurrent_review_records_one_transition(self):
        resources, book, manifest = manifest_source()
        docket = SyntheticPatchDraftLimitedPromotionActivationReviewDocket(":memory:")
        docket.submit_from_book(book, manifest.manifest_id, submitted_at=NOW)
        with ThreadPoolExecutor(max_workers=4) as pool:
            records = list(pool.map(
                lambda _: review(docket, manifest.manifest_id, ActivationManifestReviewDecision.PASS),
                range(8),
            ))
        self.assertTrue(all(item == records[0] for item in records))
        self.assertEqual(
            docket._connection.execute(
                "SELECT COUNT(*) FROM synthetic_activation_manifest_review_audit"
            ).fetchone()[0], 2,
        )
        close_all(resources, docket)

    def test_restart_preserves_review_and_integrity(self):
        resources, book, manifest = manifest_source()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic-activation-review.sqlite3"
            docket = SyntheticPatchDraftLimitedPromotionActivationReviewDocket(path)
            docket.submit_from_book(book, manifest.manifest_id, submitted_at=NOW)
            expected = review(docket, manifest.manifest_id, ActivationManifestReviewDecision.PASS)
            report = docket.evidence()
            docket.close()
            reopened = SyntheticPatchDraftLimitedPromotionActivationReviewDocket(path)
            self.assertEqual(reopened.get(manifest.manifest_id), expected)
            self.assertEqual(reopened.evidence(), report)
            reopened.close()
        close_all(resources)

    def test_audit_failure_rolls_back(self):
        resources, book, manifest = manifest_source()
        docket = SyntheticPatchDraftLimitedPromotionActivationReviewDocket(":memory:")
        def fail(**_):
            raise sqlite3.IntegrityError("audit failure")
        docket._append_audit = fail
        with self.assertRaises(GovernanceRejected):
            docket.submit_from_book(book, manifest.manifest_id, submitted_at=NOW)
        self.assertEqual(
            docket._connection.execute(
                "SELECT COUNT(*) FROM synthetic_activation_manifest_review_records"
            ).fetchone()[0], 0,
        )
        close_all(resources, docket)

    def test_tampering_blocks_get_and_replay(self):
        resources, book, manifest = manifest_source()
        docket = SyntheticPatchDraftLimitedPromotionActivationReviewDocket(":memory:")
        docket.submit_from_book(book, manifest.manifest_id, submitted_at=NOW)
        docket._connection.execute(
            "UPDATE synthetic_activation_manifest_review_records SET manifest_json = '{}'"
        )
        with self.assertRaises(GovernanceRejected):
            docket.get(manifest.manifest_id)
        self.assertFalse(docket.verify_record_bindings())
        close_all(resources, docket)

    def test_ready_source_is_read_only(self):
        resources, book, manifest = manifest_source()
        docket = SyntheticPatchDraftLimitedPromotionActivationReviewDocket(":memory:")
        docket.submit_from_book(book, manifest.manifest_id, submitted_at=NOW)
        with self.assertRaises(GovernanceRejected):
            docket.ready_source(manifest.manifest_id)
        review(docket, manifest.manifest_id, ActivationManifestReviewDecision.PASS)
        before = docket.evidence()["report_digest"]
        self.assertEqual(docket.ready_source(manifest.manifest_id).manifest, manifest)
        self.assertEqual(before, docket.evidence()["report_digest"])
        close_all(resources, docket)

    def test_evidence_proves_non_activating_boundary(self):
        resources, book, manifest = manifest_source()
        docket = SyntheticPatchDraftLimitedPromotionActivationReviewDocket(":memory:")
        docket.submit_from_book(book, manifest.manifest_id, submitted_at=NOW)
        evidence = docket.evidence()
        self.assertTrue(evidence["metadata_valid"])
        self.assertTrue(evidence["audit_chain_valid"])
        self.assertTrue(evidence["record_bindings_valid"])
        self.assertEqual(evidence["maximum_state"], MAXIMUM_ACTIVATION_MANIFEST_REVIEW_STATE)
        for field in (
            "automatic_review_allowed", "operator_decision_recording_method_present",
            "candidate_content_present", "patch_content_present", "diff_content_present",
            "source_code_changed", "filesystem_written", "activation_method_present",
            "rollback_execution_method_present", "safety_baseline_relaxation_method_present",
            "execution_method_present", "network_access_method_present",
            "external_blocker_close_method_present", "automatic_merge_method_present",
            "automatic_deploy_method_present", "personal_data_used", "credentials_used",
            "money_movement_executed", "production_activation_allowed",
        ):
            self.assertFalse(evidence[field])
        close_all(resources, docket)


if __name__ == "__main__":
    unittest.main()
