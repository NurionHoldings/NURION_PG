from __future__ import annotations

import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256
from pathlib import Path

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_patch_draft_shadow import SyntheticPatchDraftShadowBook
from nurion_pg.synthetic_patch_draft_shadow_review_docket import (
    MAXIMUM_PATCH_DRAFT_SHADOW_REVIEW_STATE,
    PatchDraftShadowReviewDecision,
    PatchDraftShadowReviewState,
    SyntheticPatchDraftShadowReviewDocket,
)
from tests.test_patch_operator_decision_intake import NOW
from tests.test_synthetic_patch_draft_shadow import (
    close_all,
    fixtures_for,
    reviewed_source,
)


FINDINGS = sha256(b"patch draft shadow independent findings").hexdigest()


def shadow_source(**fixture_overrides):
    resources, source_docket, ledger, review, manifest = reviewed_source()
    book = SyntheticPatchDraftShadowBook()
    assessment = book.evaluate(
        review,
        manifest.manifest_id,
        fixtures_for(manifest, **fixture_overrides),
        evaluated_at=NOW,
    )
    return (resources, source_docket, ledger, review), book, assessment


def close_resources(resources, docket=None):
    source_resources, source_docket, ledger, review = resources
    if docket is not None:
        docket.close()
    close_all(source_resources, source_docket, ledger, review)


class SyntheticPatchDraftShadowReviewDocketTests(unittest.TestCase):
    def test_pass_shadow_is_submitted_pending_without_authority(self):
        resources, book, assessment = shadow_source()
        docket = SyntheticPatchDraftShadowReviewDocket(":memory:")
        record = docket.submit_from_book(
            book, assessment.manifest_id, submitted_at=NOW
        )
        self.assertEqual(record.state, PatchDraftShadowReviewState.PENDING_ETERNIAN_REVIEW)
        self.assertEqual(record.shadow_assessment_digest, assessment.assessment_digest)
        self.assertFalse(record.automatic_review_allowed)
        self.assertFalse(record.operator_decision_recorded)
        self.assertFalse(record.source_code_changed)
        close_resources(resources, docket)

    def test_nonpass_shadow_is_rejected(self):
        for field in ("regression_test_passed", "source_code_changed"):
            resources, book, assessment = shadow_source(**{field: False if field.endswith("passed") else True})
            docket = SyntheticPatchDraftShadowReviewDocket(":memory:")
            with self.assertRaises(GovernanceRejected):
                docket.submit_from_book(book, assessment.manifest_id, submitted_at=NOW)
            close_resources(resources, docket)

    def test_pass_hold_and_reject_map_to_exact_states(self):
        mapping = {
            PatchDraftShadowReviewDecision.PASS: (
                PatchDraftShadowReviewState.READY_FOR_PATCH_DRAFT_OPERATOR_DECISION
            ),
            PatchDraftShadowReviewDecision.HOLD: PatchDraftShadowReviewState.HELD,
            PatchDraftShadowReviewDecision.REJECT: PatchDraftShadowReviewState.REJECTED,
        }
        for decision, state in mapping.items():
            resources, book, assessment = shadow_source()
            docket = SyntheticPatchDraftShadowReviewDocket(":memory:")
            record = docket.submit_from_book(book, assessment.manifest_id, submitted_at=NOW)
            reviewed = docket.record_eternian_review(
                record.shadow_id,
                review_id=f"synthetic:patch-draft-shadow-review:{decision.value.lower()}",
                reviewer_id=(
                    "synthetic:eternian-reviewer:patch-draft-shadow:"
                    f"{decision.value.lower()}"
                ),
                decision=decision,
                findings_digest=FINDINGS,
                reviewed_at=NOW,
            )
            self.assertEqual(reviewed.state, state)
            self.assertFalse(reviewed.operator_decision_recorded)
            close_resources(resources, docket)

    def test_submission_and_review_are_idempotent_but_collisions_fail(self):
        resources, book, assessment = shadow_source()
        docket = SyntheticPatchDraftShadowReviewDocket(":memory:")
        first = docket.submit_from_book(book, assessment.manifest_id, submitted_at=NOW)
        self.assertEqual(first, docket.submit_from_book(book, assessment.manifest_id, submitted_at=NOW))
        arguments = {
            "review_id": "synthetic:patch-draft-shadow-review:idempotent",
            "reviewer_id": "synthetic:eternian-reviewer:patch-draft-shadow:idempotent",
            "decision": PatchDraftShadowReviewDecision.PASS,
            "findings_digest": FINDINGS,
            "reviewed_at": NOW,
        }
        reviewed = docket.record_eternian_review(first.shadow_id, **arguments)
        self.assertEqual(reviewed, docket.record_eternian_review(first.shadow_id, **arguments))
        with self.assertRaises(GovernanceRejected):
            docket.record_eternian_review(
                first.shadow_id,
                **{**arguments, "findings_digest": sha256(b"changed").hexdigest()},
            )
        close_resources(resources, docket)

    def test_review_time_ids_and_database_targets_fail_closed(self):
        for target in ("review.sqlite3", "file:synthetic-review.sqlite3", "postgres://db"):
            with self.assertRaises(GovernanceRejected):
                SyntheticPatchDraftShadowReviewDocket(target)
        resources, book, assessment = shadow_source()
        docket = SyntheticPatchDraftShadowReviewDocket(":memory:")
        record = docket.submit_from_book(book, assessment.manifest_id, submitted_at=NOW)
        base = {
            "review_id": "synthetic:patch-draft-shadow-review:valid",
            "reviewer_id": "synthetic:eternian-reviewer:patch-draft-shadow:valid",
            "decision": PatchDraftShadowReviewDecision.PASS,
            "findings_digest": FINDINGS,
            "reviewed_at": NOW,
        }
        for override in (
            {"review_id": "bad"},
            {"reviewer_id": "bad"},
            {"reviewed_at": NOW - timedelta(seconds=1)},
            {"reviewed_at": NOW.replace(tzinfo=None)},
        ):
            with self.assertRaises(GovernanceRejected):
                docket.record_eternian_review(record.shadow_id, **{**base, **override})
        close_resources(resources, docket)

    def test_restart_preserves_state_and_bindings(self):
        resources, book, assessment = shadow_source()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic-patch-draft-shadow-review.sqlite3"
            docket = SyntheticPatchDraftShadowReviewDocket(path)
            record = docket.submit_from_book(book, assessment.manifest_id, submitted_at=NOW)
            docket.record_eternian_review(
                record.shadow_id,
                review_id="synthetic:patch-draft-shadow-review:restart",
                reviewer_id="synthetic:eternian-reviewer:patch-draft-shadow:restart",
                decision=PatchDraftShadowReviewDecision.PASS,
                findings_digest=FINDINGS,
                reviewed_at=NOW,
            )
            before = docket.evidence()
            docket.close()
            reopened = SyntheticPatchDraftShadowReviewDocket(path)
            self.assertEqual(before, reopened.evidence())
            self.assertEqual(
                reopened.get(record.shadow_id).state,
                PatchDraftShadowReviewState.READY_FOR_PATCH_DRAFT_OPERATOR_DECISION,
            )
            reopened.close()
        close_resources(resources)

    def test_concurrent_review_records_one_transition(self):
        resources, book, assessment = shadow_source()
        docket = SyntheticPatchDraftShadowReviewDocket(":memory:")
        record = docket.submit_from_book(book, assessment.manifest_id, submitted_at=NOW)

        def review(_):
            return docket.record_eternian_review(
                record.shadow_id,
                review_id="synthetic:patch-draft-shadow-review:concurrent",
                reviewer_id="synthetic:eternian-reviewer:patch-draft-shadow:concurrent",
                decision=PatchDraftShadowReviewDecision.PASS,
                findings_digest=FINDINGS,
                reviewed_at=NOW,
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(review, range(8)))
        self.assertTrue(all(item == results[0] for item in results))
        rows = docket._connection.execute(
            "SELECT COUNT(*) FROM synthetic_patch_draft_shadow_review_audit"
        ).fetchone()[0]
        self.assertEqual(rows, 2)
        close_resources(resources, docket)

    def test_audit_failure_rolls_back_submission_and_review(self):
        resources, book, assessment = shadow_source()
        docket = SyntheticPatchDraftShadowReviewDocket(":memory:")

        def fail(**_):
            raise sqlite3.IntegrityError("synthetic audit failure")

        docket._append_audit = fail
        with self.assertRaises(GovernanceRejected):
            docket.submit_from_book(book, assessment.manifest_id, submitted_at=NOW)
        self.assertEqual(
            docket._connection.execute(
                "SELECT COUNT(*) FROM synthetic_patch_draft_shadow_review_records"
            ).fetchone()[0],
            0,
        )
        close_resources(resources, docket)

        resources, book, assessment = shadow_source()
        docket = SyntheticPatchDraftShadowReviewDocket(":memory:")
        record = docket.submit_from_book(book, assessment.manifest_id, submitted_at=NOW)
        docket._append_audit = fail
        with self.assertRaises(GovernanceRejected):
            docket.record_eternian_review(
                record.shadow_id,
                review_id="synthetic:patch-draft-shadow-review:audit-failure",
                reviewer_id=(
                    "synthetic:eternian-reviewer:patch-draft-shadow:audit-failure"
                ),
                decision=PatchDraftShadowReviewDecision.PASS,
                findings_digest=FINDINGS,
                reviewed_at=NOW,
            )
        self.assertEqual(
            docket.get(record.shadow_id).state,
            PatchDraftShadowReviewState.PENDING_ETERNIAN_REVIEW,
        )
        close_resources(resources, docket)

    def test_tampering_blocks_get_ready_and_idempotent_replay(self):
        resources, book, assessment = shadow_source()
        docket = SyntheticPatchDraftShadowReviewDocket(":memory:")
        record = docket.submit_from_book(book, assessment.manifest_id, submitted_at=NOW)
        docket._connection.execute(
            "UPDATE synthetic_patch_draft_shadow_review_records "
            "SET assessment_json = '{}' WHERE shadow_id = ?", (record.shadow_id,)
        )
        with self.assertRaises(GovernanceRejected):
            docket.get(record.shadow_id)
        self.assertFalse(docket.verify_record_bindings())
        close_resources(resources, docket)

    def test_ready_source_requires_pass_and_is_read_only(self):
        resources, book, assessment = shadow_source()
        docket = SyntheticPatchDraftShadowReviewDocket(":memory:")
        record = docket.submit_from_book(book, assessment.manifest_id, submitted_at=NOW)
        with self.assertRaises(GovernanceRejected):
            docket.ready_source(record.shadow_id)
        docket.record_eternian_review(
            record.shadow_id,
            review_id="synthetic:patch-draft-shadow-review:ready",
            reviewer_id="synthetic:eternian-reviewer:patch-draft-shadow:ready",
            decision=PatchDraftShadowReviewDecision.PASS,
            findings_digest=FINDINGS,
            reviewed_at=NOW,
        )
        before = docket.evidence()["report_digest"]
        source = docket.ready_source(record.shadow_id)
        self.assertEqual(before, docket.evidence()["report_digest"])
        self.assertEqual(source.shadow_assessment_digest, assessment.assessment_digest)
        close_resources(resources, docket)

    def test_evidence_proves_non_authorizing_boundary(self):
        resources, book, assessment = shadow_source()
        docket = SyntheticPatchDraftShadowReviewDocket(":memory:")
        docket.submit_from_book(book, assessment.manifest_id, submitted_at=NOW)
        evidence = docket.evidence()
        self.assertTrue(evidence["audit_chain_valid"])
        self.assertTrue(evidence["record_bindings_valid"])
        self.assertEqual(
            evidence["maximum_state"], MAXIMUM_PATCH_DRAFT_SHADOW_REVIEW_STATE
        )
        for field in (
            "automatic_review_allowed", "operator_decision_method_present",
            "operator_decision_recorded", "patch_content_present",
            "diff_content_present", "source_code_changed", "filesystem_written",
            "application_method_present", "safety_baseline_relaxation_method_present",
            "execution_method_present", "network_access_method_present",
            "personal_data_used", "credentials_used", "money_movement_executed",
            "production_activation_allowed",
        ):
            self.assertFalse(evidence[field])
        close_resources(resources, docket)


if __name__ == "__main__":
    unittest.main()
