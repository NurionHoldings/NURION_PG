from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_activation_dry_run_designs import (
    DRY_RUN_DESIGN_SCOPE, DRY_RUN_DESIGN_STATE, DRY_RUN_REQUIRED_GATES,
    SyntheticActivationDryRunDesignBook,
)
from nurion_pg.synthetic_patch_draft_limited_promotion_activation_draft_review import (
    ActivationDraftReviewDecision, SyntheticActivationDraftReviewDocket,
)
from nurion_pg.synthetic_patch_draft_limited_promotion_activation_drafts import SyntheticPatchDraftLimitedPromotionActivationDraftBook
from tests.test_patch_draft_limited_promotion_reconfirmation_intake import NOW
from tests.test_synthetic_patch_draft_limited_promotion_activation_drafts import activation_sources, close_sources


def reviewed_source(decision=ActivationDraftReviewDecision.PASS):
    resources, source_docket, ledger, packet_book, receipt = activation_sources()
    drafts = SyntheticPatchDraftLimitedPromotionActivationDraftBook()
    draft = drafts.draft_from_receipt(ledger, receipt.receipt_id, packet_book, drafted_at=NOW)
    docket = SyntheticActivationDraftReviewDocket(); docket.submit(drafts, draft.draft_id, submitted_at=NOW)
    review = docket.record_eternian_review(
        draft.draft_id, review_id="synthetic:limited-promotion-activation-draft-review:design",
        reviewer_id="synthetic:eternian-reviewer:activation-draft:design", decision=decision,
        findings_digest=sha256(b"activation design review").hexdigest(), reviewed_at=NOW,
    )
    return resources, source_docket, ledger, docket, review


class SyntheticActivationDryRunDesignTests(unittest.TestCase):
    def test_design_freezes_exact_reviewed_scope_without_execution(self):
        resources, source_docket, ledger, docket, review = reviewed_source()
        before = docket.evidence()["report_digest"]
        design = SyntheticActivationDryRunDesignBook().design_from_review(docket, review.draft.draft_id, designed_at=NOW)
        self.assertEqual(before, docket.evidence()["report_digest"])
        self.assertEqual(design.source_review_digest, review.review_digest)
        self.assertEqual(design.manifest_digest, review.draft.manifest_digest)
        self.assertEqual(design.cohort_digest, review.draft.cohort_digest)
        self.assertEqual(design.required_gates, DRY_RUN_REQUIRED_GATES)
        self.assertFalse(design.dry_run_executed)
        close_sources(resources, source_docket, ledger)

    def test_hold_and_reject_reviews_are_blocked(self):
        for decision in (ActivationDraftReviewDecision.HOLD, ActivationDraftReviewDecision.REJECT):
            resources, source_docket, ledger, docket, review = reviewed_source(decision)
            with self.assertRaises(GovernanceRejected):
                SyntheticActivationDryRunDesignBook().design_from_review(docket, review.draft.draft_id, designed_at=NOW)
            close_sources(resources, source_docket, ledger)

    def test_typed_source_and_time_fail_closed(self):
        resources, source_docket, ledger, docket, review = reviewed_source()
        book = SyntheticActivationDryRunDesignBook()
        with self.assertRaises(GovernanceRejected): book.design_from_review(object(), review.draft.draft_id, designed_at=NOW)
        for value in (NOW.replace(tzinfo=None), NOW - timedelta(seconds=1)):
            with self.assertRaises(GovernanceRejected): book.design_from_review(docket, review.draft.draft_id, designed_at=value)
        close_sources(resources, source_docket, ledger)

    def test_exact_replay_and_concurrency_converge(self):
        resources, source_docket, ledger, docket, review = reviewed_source(); book = SyntheticActivationDryRunDesignBook()
        with ThreadPoolExecutor(max_workers=4) as pool:
            values = list(pool.map(lambda _: book.design_from_review(docket, review.draft.draft_id, designed_at=NOW), range(8)))
        self.assertTrue(all(v == values[0] for v in values)); self.assertEqual(len(book.designs), 1)
        close_sources(resources, source_docket, ledger)

    def test_source_and_design_tampering_fail_closed(self):
        resources, source_docket, ledger, docket, review = reviewed_source(); book = SyntheticActivationDryRunDesignBook()
        design = book.design_from_review(docket, review.draft.draft_id, designed_at=NOW)
        object.__setattr__(design, "scope", "PRODUCTION")
        self.assertFalse(book.verify_design_chain())
        close_sources(resources, source_docket, ledger)

    def test_source_change_during_design_discards_result(self):
        resources, source_docket, ledger, docket, review = reviewed_source(); book = SyntheticActivationDryRunDesignBook()
        original = docket.evidence; calls = 0
        def changing():
            nonlocal calls; calls += 1; value = original()
            return value if calls == 1 else {**value, "report_digest": "f" * 64}
        docket.evidence = changing
        with self.assertRaises(GovernanceRejected): book.design_from_review(docket, review.draft.draft_id, designed_at=NOW)
        self.assertEqual(book.designs, ())
        close_sources(resources, source_docket, ledger)

    def test_evidence_caps_design_authority(self):
        resources, source_docket, ledger, docket, review = reviewed_source(); book = SyntheticActivationDryRunDesignBook()
        book.design_from_review(docket, review.draft.draft_id, designed_at=NOW); evidence = book.evidence()
        self.assertEqual(evidence["maximum_state"], DRY_RUN_DESIGN_STATE); self.assertEqual(evidence["scope"], DRY_RUN_DESIGN_SCOPE)
        self.assertTrue(evidence["design_chain_valid"]); self.assertTrue(evidence["separate_review_required"])
        for key in evidence:
            if key.endswith("_present") or key.endswith("_allowed") or key.endswith("_executed") or key.endswith("_used"):
                self.assertFalse(evidence[key])
        close_sources(resources, source_docket, ledger)


if __name__ == "__main__": unittest.main()
