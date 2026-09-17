from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.synthetic_patch_draft_review_docket import (
    PatchDraftReviewDecision,
    SyntheticPatchDraftReviewDocket,
)
from nurion_pg.synthetic_patch_draft_shadow import (
    MAXIMUM_PATCH_DRAFT_SHADOW_DECISION,
    PatchDraftShadowDecision,
    PatchDraftShadowItemDecision,
    SyntheticPatchDraftShadowBook,
    SyntheticPatchDraftShadowFixture,
)
from tests.test_patch_operator_decision_intake import NOW
from tests.test_synthetic_patch_draft_review_docket import (
    FINDINGS,
    close_source,
    manifest_source,
)


def reviewed_source(decision=PatchDraftReviewDecision.PASS):
    resources, source_docket, ledger, book, manifest = manifest_source()
    review = SyntheticPatchDraftReviewDocket(":memory:")
    review.submit_from_book(book, manifest.source_receipt_id, submitted_at=NOW)
    review.record_eternian_review(
        manifest.manifest_id,
        review_id=f"synthetic:patch-draft-review:shadow-{decision.value.lower()}",
        reviewer_id=(
            "synthetic:eternian-reviewer:patch-draft:shadow-"
            f"{decision.value.lower()}"
        ),
        decision=decision,
        findings_digest=FINDINGS,
        reviewed_at=NOW,
    )
    return resources, source_docket, ledger, review, manifest


def fixture_for(manifest, index, **overrides):
    scope = manifest.draft_scopes[index]
    values = {
        "fixture_id": f"synthetic:patch-draft-shadow-fixture:test-{index}",
        "manifest_id": manifest.manifest_id,
        "manifest_digest": manifest.manifest_digest,
        "draft_scope": scope,
        "target_path_digest": manifest.target_path_digests[index],
        "candidate_artifact_digest": sha256(
            f"candidate:{scope}".encode("ascii")
        ).hexdigest(),
        "synthetic_input_only": True,
        "manifest_binding_verified": True,
        "expected_metadata_change_observed": True,
        "fail_closed_baseline_preserved": True,
        "regression_test_passed": True,
        "concurrency_failure_tests_passed": True,
        "sha256_evidence_reproduced": True,
        "eternian_review_retained": True,
        "patch_content_present": False,
        "diff_content_present": False,
        "source_code_changed": False,
        "filesystem_written": False,
        "network_access_used": False,
        "production_access_used": False,
        "credentials_used": False,
        "personal_data_used": False,
        "money_movement_executed": False,
    }
    values.update(overrides)
    return SyntheticPatchDraftShadowFixture(
        **values, fixture_digest=canonical_digest(values)
    )


def fixtures_for(manifest, **first_overrides):
    return tuple(
        fixture_for(manifest, index, **(first_overrides if index == 0 else {}))
        for index in range(len(manifest.draft_scopes))
    )


def close_all(resources, source_docket, ledger, review):
    review.close()
    close_source(resources, source_docket, ledger)


class SyntheticPatchDraftShadowTests(unittest.TestCase):
    def test_passed_fixtures_create_review_candidate_without_patch_content(self):
        resources, source_docket, ledger, review, manifest = reviewed_source()
        before = review.evidence()["report_digest"]
        assessment = SyntheticPatchDraftShadowBook().evaluate(
            review, manifest.manifest_id, fixtures_for(manifest), evaluated_at=NOW
        )
        self.assertEqual(before, review.evidence()["report_digest"])
        self.assertEqual(
            assessment.decision,
            PatchDraftShadowDecision.PROPOSED_FOR_ETERNIAN_REVIEW,
        )
        self.assertTrue(
            all(item.decision is PatchDraftShadowItemDecision.PASS
                for item in assessment.item_results)
        )
        self.assertFalse(assessment.patch_content_present)
        self.assertFalse(assessment.diff_content_present)
        self.assertFalse(assessment.source_code_changed)
        close_all(resources, source_docket, ledger, review)

    def test_incomplete_controls_require_human_review(self):
        resources, source_docket, ledger, review, manifest = reviewed_source()
        assessment = SyntheticPatchDraftShadowBook().evaluate(
            review,
            manifest.manifest_id,
            fixtures_for(manifest, regression_test_passed=False),
            evaluated_at=NOW,
        )
        self.assertEqual(assessment.decision, PatchDraftShadowDecision.HUMAN_REVIEW)
        close_all(resources, source_docket, ledger, review)

    def test_any_forbidden_side_effect_blocks_shadow(self):
        for field in (
            "patch_content_present", "diff_content_present", "source_code_changed",
            "filesystem_written", "network_access_used", "production_access_used",
            "credentials_used", "personal_data_used", "money_movement_executed",
        ):
            resources, source_docket, ledger, review, manifest = reviewed_source()
            assessment = SyntheticPatchDraftShadowBook().evaluate(
                review,
                manifest.manifest_id,
                fixtures_for(manifest, **{field: True}),
                evaluated_at=NOW,
            )
            self.assertEqual(assessment.decision, PatchDraftShadowDecision.BLOCKED)
            close_all(resources, source_docket, ledger, review)

    def test_nonpass_review_cannot_source_shadow(self):
        for decision in (PatchDraftReviewDecision.HOLD, PatchDraftReviewDecision.REJECT):
            resources, source_docket, ledger, review, manifest = reviewed_source(decision)
            with self.assertRaises(GovernanceRejected):
                SyntheticPatchDraftShadowBook().evaluate(
                    review,
                    manifest.manifest_id,
                    fixtures_for(manifest),
                    evaluated_at=NOW,
                )
            close_all(resources, source_docket, ledger, review)

    def test_invalid_time_and_untyped_inputs_are_blocked(self):
        resources, source_docket, ledger, review, manifest = reviewed_source()
        book = SyntheticPatchDraftShadowBook()
        with self.assertRaises(GovernanceRejected):
            book.evaluate(object(), manifest.manifest_id, fixtures_for(manifest), evaluated_at=NOW)
        with self.assertRaises(GovernanceRejected):
            book.evaluate(review, manifest.manifest_id, (), evaluated_at=NOW)
        for value in (NOW - timedelta(seconds=1), NOW.replace(tzinfo=None)):
            with self.assertRaises(GovernanceRejected):
                book.evaluate(
                    review, manifest.manifest_id, fixtures_for(manifest), evaluated_at=value
                )
        close_all(resources, source_docket, ledger, review)

    def test_exact_fixture_set_target_and_manifest_binding_are_required(self):
        resources, source_docket, ledger, review, manifest = reviewed_source()
        book = SyntheticPatchDraftShadowBook()
        with self.assertRaises(GovernanceRejected):
            book.evaluate(
                review, manifest.manifest_id, fixtures_for(manifest)[:1], evaluated_at=NOW
            )
        duplicate = (fixture_for(manifest, 0), fixture_for(manifest, 0))
        with self.assertRaises(GovernanceRejected):
            book.evaluate(review, manifest.manifest_id, duplicate, evaluated_at=NOW)
        with self.assertRaises(GovernanceRejected):
            book.evaluate(
                review,
                manifest.manifest_id,
                fixtures_for(manifest, target_path_digest="f" * 64),
                evaluated_at=NOW,
            )
        with self.assertRaises(GovernanceRejected):
            book.evaluate(
                review,
                manifest.manifest_id,
                fixtures_for(manifest, manifest_digest="f" * 64),
                evaluated_at=NOW,
            )
        close_all(resources, source_docket, ledger, review)

    def test_same_target_and_candidate_requires_human_review(self):
        resources, source_docket, ledger, review, manifest = reviewed_source()
        assessment = SyntheticPatchDraftShadowBook().evaluate(
            review,
            manifest.manifest_id,
            fixtures_for(
                manifest,
                candidate_artifact_digest=manifest.target_path_digests[0],
            ),
            evaluated_at=NOW,
        )
        self.assertEqual(assessment.decision, PatchDraftShadowDecision.HUMAN_REVIEW)
        close_all(resources, source_docket, ledger, review)

    def test_concurrent_replay_is_idempotent_and_collision_blocked(self):
        resources, source_docket, ledger, review, manifest = reviewed_source()
        book = SyntheticPatchDraftShadowBook()
        fixtures = fixtures_for(manifest)

        def evaluate(_):
            return book.evaluate(review, manifest.manifest_id, fixtures, evaluated_at=NOW)

        with ThreadPoolExecutor(max_workers=4) as pool:
            assessments = list(pool.map(evaluate, range(8)))
        self.assertTrue(all(item == assessments[0] for item in assessments))
        collision = fixtures_for(manifest, regression_test_passed=False)
        with self.assertRaises(GovernanceRejected):
            book.evaluate(review, manifest.manifest_id, collision, evaluated_at=NOW)
        self.assertEqual(len(book.assessments), 1)
        close_all(resources, source_docket, ledger, review)

    def test_fixture_and_assessment_tampering_fail_closed(self):
        resources, source_docket, ledger, review, manifest = reviewed_source()
        fixtures = fixtures_for(manifest)
        object.__setattr__(fixtures[0], "fixture_digest", "f" * 64)
        with self.assertRaises(GovernanceRejected):
            SyntheticPatchDraftShadowBook().evaluate(
                review, manifest.manifest_id, fixtures, evaluated_at=NOW
            )
        book = SyntheticPatchDraftShadowBook()
        assessment = book.evaluate(
            review, manifest.manifest_id, fixtures_for(manifest), evaluated_at=NOW
        )
        object.__setattr__(assessment, "source_code_changed", True)
        self.assertFalse(book.verify_assessment_chain())
        close_all(resources, source_docket, ledger, review)

    def test_rehashed_shadow_identity_tamper_breaks_chain(self):
        resources, source_docket, ledger, review, manifest = reviewed_source()
        book = SyntheticPatchDraftShadowBook()
        assessment = book.evaluate(
            review, manifest.manifest_id, fixtures_for(manifest), evaluated_at=NOW
        )
        object.__setattr__(assessment, "shadow_id", "synthetic:patch-draft-shadow:tampered")
        object.__setattr__(
            assessment, "assessment_digest", canonical_digest(assessment.digest_value())
        )
        self.assertFalse(book.verify_assessment_chain())
        close_all(resources, source_docket, ledger, review)

    def test_evidence_proves_metadata_only_no_execution(self):
        resources, source_docket, ledger, review, manifest = reviewed_source()
        book = SyntheticPatchDraftShadowBook()
        book.evaluate(review, manifest.manifest_id, fixtures_for(manifest), evaluated_at=NOW)
        evidence = book.evidence()
        self.assertTrue(evidence["assessment_chain_valid"])
        self.assertEqual(
            evidence["maximum_decision"], MAXIMUM_PATCH_DRAFT_SHADOW_DECISION
        )
        for field in (
            "source_docket_state_changed", "patch_content_present",
            "diff_content_present", "source_code_changed", "filesystem_written",
            "application_method_present", "safety_baseline_relaxation_method_present",
            "execution_method_present", "network_access_method_present",
            "personal_data_used", "credentials_used", "money_movement_executed",
            "production_activation_allowed",
        ):
            self.assertFalse(evidence[field])
        close_all(resources, source_docket, ledger, review)


if __name__ == "__main__":
    unittest.main()
