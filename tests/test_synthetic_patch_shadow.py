from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.synthetic_implementation_review_docket import (
    ImplementationProposalReviewDecision,
)
from nurion_pg.synthetic_patch_shadow import (
    MAXIMUM_PATCH_SHADOW_DECISION,
    PatchShadowDecision,
    PatchShadowItemDecision,
    SyntheticPatchShadowBook,
    SyntheticPatchShadowFixture,
)
from tests.test_operator_decision_intake import NOW
from tests.test_synthetic_implementation_review_docket import (
    FINDINGS,
    REVIEWER_ID,
    REVIEW_ID,
    close_source,
    pending_review,
)


def ready_review():
    resources = pending_review()
    case, remediation, source_docket, ledger, book, proposal, docket, _ = resources
    reviewed = docket.record_eternian_review(
        proposal.proposal_id,
        review_id=REVIEW_ID,
        reviewer_id=REVIEWER_ID,
        decision=ImplementationProposalReviewDecision.PASS,
        findings_digest=FINDINGS,
        reviewed_at=NOW,
    )
    return case, remediation, source_docket, ledger, book, proposal, docket, reviewed


def fixture(proposal, scope: str, index: int, **changes):
    values = {
        "fixture_id": f"synthetic:patch-shadow-fixture:{index}",
        "proposal_id": proposal.proposal_id,
        "proposal_digest": proposal.proposal_digest,
        "draft_scope": scope,
        "base_snapshot_digest": sha256(
            f"base:{index}".encode("ascii")
        ).hexdigest(),
        "candidate_patch_digest": sha256(
            f"candidate:{index}".encode("ascii")
        ).hexdigest(),
        "synthetic_input_only": True,
        "expected_change_observed": True,
        "fail_closed_baseline_preserved": True,
        "regression_test_passed": True,
        "concurrency_failure_tests_passed": True,
        "sha256_evidence_reproduced": True,
        "eternian_review_retained": True,
        "source_code_changed": False,
        "filesystem_written": False,
        "network_access_used": False,
        "production_access_used": False,
        "credentials_used": False,
        "personal_data_used": False,
        "money_movement_executed": False,
        **changes,
    }
    return SyntheticPatchShadowFixture(
        **values,
        fixture_digest=canonical_digest(values),
    )


def fixtures_for(proposal, **changes):
    return tuple(
        fixture(proposal, scope, index, **changes)
        for index, scope in enumerate(proposal.draft_scopes, start=1)
    )


def close_all(case, remediation, source_docket, ledger, review_docket):
    review_docket.close()
    close_source(case, remediation, source_docket, ledger)


class SyntheticPatchShadowTests(unittest.TestCase):
    def test_passed_fixtures_create_review_candidate_without_patch_content(self):
        resources = ready_review()
        case, remediation, source_docket, ledger, _, proposal, docket, _ = resources
        book = SyntheticPatchShadowBook()
        assessment = book.evaluate(
            docket, proposal.proposal_id, fixtures_for(proposal), evaluated_at=NOW
        )
        self.assertEqual(
            assessment.decision,
            PatchShadowDecision.PROPOSED_FOR_ETERNIAN_REVIEW,
        )
        self.assertTrue(
            all(
                result.decision is PatchShadowItemDecision.PASS
                for result in assessment.item_results
            )
        )
        self.assertFalse(assessment.patch_content_present)
        self.assertFalse(assessment.code_change_allowed)
        self.assertFalse(assessment.execution_allowed)
        self.assertTrue(book.verify_assessment_chain())
        close_all(case, remediation, source_docket, ledger, docket)

    def test_exact_fixture_set_and_proposal_binding_are_required(self):
        resources = ready_review()
        case, remediation, source_docket, ledger, _, proposal, docket, _ = resources
        book = SyntheticPatchShadowBook()
        with self.assertRaises(GovernanceRejected):
            book.evaluate(docket, proposal.proposal_id, (), evaluated_at=NOW)
        valid = fixture(proposal, proposal.draft_scopes[0], 1)
        with self.assertRaises(GovernanceRejected):
            book.evaluate(docket, proposal.proposal_id, (valid, valid), evaluated_at=NOW)
        wrong = fixture(
            proposal,
            proposal.draft_scopes[0],
            2,
            proposal_digest="f" * 64,
        )
        with self.assertRaises(GovernanceRejected):
            book.evaluate(docket, proposal.proposal_id, (wrong,), evaluated_at=NOW)
        close_all(case, remediation, source_docket, ledger, docket)

    def test_incomplete_controls_require_human_review(self):
        resources = ready_review()
        case, remediation, source_docket, ledger, _, proposal, docket, _ = resources
        assessment = SyntheticPatchShadowBook().evaluate(
            docket,
            proposal.proposal_id,
            fixtures_for(proposal, regression_test_passed=False),
            evaluated_at=NOW,
        )
        self.assertEqual(assessment.decision, PatchShadowDecision.HUMAN_REVIEW)
        self.assertEqual(
            assessment.item_results[0].reason,
            "incomplete_patch_shadow_controls",
        )
        close_all(case, remediation, source_docket, ledger, docket)

    def test_identical_base_and_candidate_require_human_review(self):
        resources = ready_review()
        case, remediation, source_docket, ledger, _, proposal, docket, _ = resources
        same = sha256(b"same synthetic snapshot").hexdigest()
        assessment = SyntheticPatchShadowBook().evaluate(
            docket,
            proposal.proposal_id,
            fixtures_for(
                proposal,
                base_snapshot_digest=same,
                candidate_patch_digest=same,
            ),
            evaluated_at=NOW,
        )
        self.assertEqual(assessment.decision, PatchShadowDecision.HUMAN_REVIEW)
        close_all(case, remediation, source_docket, ledger, docket)

    def test_any_forbidden_side_effect_blocks_shadow(self):
        for change in (
            {"source_code_changed": True},
            {"filesystem_written": True},
            {"network_access_used": True},
            {"production_access_used": True},
            {"credentials_used": True},
            {"personal_data_used": True},
            {"money_movement_executed": True},
        ):
            resources = ready_review()
            case, remediation, source_docket, ledger, _, proposal, docket, _ = resources
            assessment = SyntheticPatchShadowBook().evaluate(
                docket,
                proposal.proposal_id,
                fixtures_for(proposal, **change),
                evaluated_at=NOW,
            )
            self.assertEqual(assessment.decision, PatchShadowDecision.BLOCKED)
            close_all(case, remediation, source_docket, ledger, docket)

    def test_held_review_cannot_source_patch_shadow(self):
        resources = pending_review()
        case, remediation, source_docket, ledger, _, proposal, docket, _ = resources
        docket.record_eternian_review(
            proposal.proposal_id,
            review_id=REVIEW_ID,
            reviewer_id=REVIEWER_ID,
            decision=ImplementationProposalReviewDecision.HOLD,
            findings_digest=FINDINGS,
            reviewed_at=NOW,
        )
        with self.assertRaises(GovernanceRejected):
            SyntheticPatchShadowBook().evaluate(
                docket,
                proposal.proposal_id,
                fixtures_for(proposal),
                evaluated_at=NOW,
            )
        close_all(case, remediation, source_docket, ledger, docket)

    def test_source_docket_is_read_only(self):
        resources = ready_review()
        case, remediation, source_docket, ledger, _, proposal, docket, _ = resources
        before = docket.evidence()["report_digest"]
        SyntheticPatchShadowBook().evaluate(
            docket, proposal.proposal_id, fixtures_for(proposal), evaluated_at=NOW
        )
        self.assertEqual(before, docket.evidence()["report_digest"])
        close_all(case, remediation, source_docket, ledger, docket)

    def test_concurrent_replay_is_idempotent_and_collision_is_blocked(self):
        resources = ready_review()
        case, remediation, source_docket, ledger, _, proposal, docket, _ = resources
        book = SyntheticPatchShadowBook()
        fixtures = fixtures_for(proposal)

        def evaluate(_):
            return book.evaluate(
                docket, proposal.proposal_id, fixtures, evaluated_at=NOW
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            assessments = list(pool.map(evaluate, range(8)))
        self.assertTrue(all(item == assessments[0] for item in assessments))
        self.assertEqual(len(book.assessments), 1)
        with self.assertRaises(GovernanceRejected):
            book.evaluate(
                docket,
                proposal.proposal_id,
                fixtures_for(proposal, regression_test_passed=False),
                evaluated_at=NOW,
            )
        close_all(case, remediation, source_docket, ledger, docket)

    def test_tampered_fixture_and_assessment_fail_closed(self):
        resources = ready_review()
        case, remediation, source_docket, ledger, _, proposal, docket, _ = resources
        fixtures = fixtures_for(proposal)
        object.__setattr__(fixtures[0], "expected_change_observed", False)
        with self.assertRaises(GovernanceRejected):
            SyntheticPatchShadowBook().evaluate(
                docket, proposal.proposal_id, fixtures, evaluated_at=NOW
            )
        book = SyntheticPatchShadowBook()
        assessment = book.evaluate(
            docket, proposal.proposal_id, fixtures_for(proposal), evaluated_at=NOW
        )
        object.__setattr__(assessment, "patch_content_present", True)
        self.assertFalse(book.verify_assessment_chain())
        close_all(case, remediation, source_docket, ledger, docket)

    def test_rehashed_shadow_identity_tamper_breaks_chain(self):
        resources = ready_review()
        case, remediation, source_docket, ledger, _, proposal, docket, _ = resources
        book = SyntheticPatchShadowBook()
        assessment = book.evaluate(
            docket, proposal.proposal_id, fixtures_for(proposal), evaluated_at=NOW
        )
        object.__setattr__(assessment, "source_review_digest", "f" * 64)
        object.__setattr__(
            assessment,
            "assessment_digest",
            canonical_digest(assessment.digest_value()),
        )
        self.assertFalse(book.verify_assessment_chain())
        close_all(case, remediation, source_docket, ledger, docket)

    def test_invalid_time_and_untyped_inputs_are_blocked(self):
        resources = ready_review()
        case, remediation, source_docket, ledger, _, proposal, docket, _ = resources
        fixtures = fixtures_for(proposal)
        with self.assertRaises(GovernanceRejected):
            SyntheticPatchShadowBook().evaluate(
                object(), proposal.proposal_id, fixtures, evaluated_at=NOW
            )
        with self.assertRaises(GovernanceRejected):
            SyntheticPatchShadowBook().evaluate(
                docket,
                proposal.proposal_id,
                fixtures,
                evaluated_at=NOW - timedelta(seconds=1),
            )
        with self.assertRaises(GovernanceRejected):
            SyntheticPatchShadowBook().evaluate(
                docket,
                proposal.proposal_id,
                fixtures,
                evaluated_at=NOW.replace(tzinfo=None),
            )
        close_all(case, remediation, source_docket, ledger, docket)

    def test_evidence_proves_metadata_only_no_change_or_execution(self):
        resources = ready_review()
        case, remediation, source_docket, ledger, _, proposal, docket, _ = resources
        book = SyntheticPatchShadowBook()
        book.evaluate(
            docket, proposal.proposal_id, fixtures_for(proposal), evaluated_at=NOW
        )
        evidence = book.evidence()
        self.assertTrue(evidence["assessment_chain_valid"])
        self.assertEqual(
            evidence["maximum_decision"], MAXIMUM_PATCH_SHADOW_DECISION
        )
        for field in (
            "source_docket_state_changed",
            "patch_content_present",
            "file_write_method_present",
            "network_access_method_present",
            "code_change_method_present",
            "application_method_present",
            "safety_baseline_relaxation_method_present",
            "operator_decision_method_present",
            "execution_method_present",
            "personal_data_used",
            "credentials_used",
            "money_movement_executed",
            "production_activation_allowed",
        ):
            self.assertFalse(evidence[field])
        close_all(case, remediation, source_docket, ledger, docket)


if __name__ == "__main__":
    unittest.main()
