from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_patch_draft_limited_promotion_activation_draft_review import (
    ACTIVATION_DRAFT_REVIEW_MAXIMUM_STATE,
    ActivationDraftReviewDecision,
    ActivationDraftReviewState,
    SyntheticActivationDraftReviewDocket,
)
from nurion_pg.synthetic_patch_draft_limited_promotion_activation_drafts import (
    SyntheticPatchDraftLimitedPromotionActivationDraftBook,
)
from tests.test_patch_draft_limited_promotion_reconfirmation_intake import NOW
from tests.test_synthetic_patch_draft_limited_promotion_activation_drafts import (
    activation_sources,
    close_sources,
)


FINDINGS = sha256(b"independent activation draft review").hexdigest()


def source():
    resources, source_docket, ledger, packet_book, receipt = activation_sources()
    book = SyntheticPatchDraftLimitedPromotionActivationDraftBook()
    draft = book.draft_from_receipt(ledger, receipt.receipt_id, packet_book, drafted_at=NOW)
    return resources, source_docket, ledger, book, draft


def pass_review(docket, draft, **overrides):
    values = {
        "review_id": "synthetic:limited-promotion-activation-draft-review:pass",
        "reviewer_id": "synthetic:eternian-reviewer:activation-draft:pass",
        "decision": ActivationDraftReviewDecision.PASS,
        "findings_digest": FINDINGS,
        "reviewed_at": NOW,
    }
    values.update(overrides)
    return docket.record_eternian_review(draft.draft_id, **values)


class ActivationDraftReviewTests(unittest.TestCase):
    def test_submission_is_pending_and_non_executing(self):
        resources, source_docket, ledger, book, draft = source()
        docket = SyntheticActivationDraftReviewDocket()
        record = docket.submit(book, draft.draft_id, submitted_at=NOW)
        self.assertIs(record.state, ActivationDraftReviewState.PENDING_ETERNIAN_REVIEW)
        self.assertIsNone(record.review_digest)
        close_sources(resources, source_docket, ledger)

    def test_pass_stops_at_dry_run_design_readiness(self):
        resources, source_docket, ledger, book, draft = source()
        docket = SyntheticActivationDraftReviewDocket()
        docket.submit(book, draft.draft_id, submitted_at=NOW)
        reviewed = pass_review(docket, draft)
        self.assertIs(reviewed.state, ActivationDraftReviewState.READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_DESIGN)
        self.assertEqual(docket.ready_source(draft.draft_id), reviewed)
        close_sources(resources, source_docket, ledger)

    def test_hold_and_reject_are_not_ready(self):
        for decision, state in ((ActivationDraftReviewDecision.HOLD, ActivationDraftReviewState.HELD), (ActivationDraftReviewDecision.REJECT, ActivationDraftReviewState.REJECTED)):
            resources, source_docket, ledger, book, draft = source()
            docket = SyntheticActivationDraftReviewDocket(); docket.submit(book, draft.draft_id, submitted_at=NOW)
            record = docket.record_eternian_review(
                draft.draft_id,
                review_id=f"synthetic:limited-promotion-activation-draft-review:{decision.value.lower()}",
                reviewer_id=f"synthetic:eternian-reviewer:activation-draft:{decision.value.lower()}",
                decision=decision, findings_digest=FINDINGS, reviewed_at=NOW,
            )
            self.assertIs(record.state, state)
            with self.assertRaises(GovernanceRejected): docket.ready_source(draft.draft_id)
            close_sources(resources, source_docket, ledger)

    def test_invalid_source_time_and_review_metadata_fail_closed(self):
        resources, source_docket, ledger, book, draft = source()
        docket = SyntheticActivationDraftReviewDocket()
        with self.assertRaises(GovernanceRejected): docket.submit(object(), draft.draft_id, submitted_at=NOW)
        with self.assertRaises(GovernanceRejected): docket.submit(book, draft.draft_id, submitted_at=NOW.replace(tzinfo=None))
        docket.submit(book, draft.draft_id, submitted_at=NOW)
        for override in ({"review_id": "bad"}, {"reviewer_id": "bad"}, {"decision": "PASS"}, {"findings_digest": "bad"}, {"reviewed_at": NOW - timedelta(seconds=1)}):
            with self.assertRaises(GovernanceRejected): pass_review(docket, draft, **override)
        close_sources(resources, source_docket, ledger)

    def test_review_is_idempotent_immutable_and_concurrent(self):
        resources, source_docket, ledger, book, draft = source()
        docket = SyntheticActivationDraftReviewDocket(); docket.submit(book, draft.draft_id, submitted_at=NOW)
        with ThreadPoolExecutor(max_workers=4) as pool:
            records = list(pool.map(lambda _: pass_review(docket, draft), range(8)))
        self.assertTrue(all(item == records[0] for item in records))
        with self.assertRaises(GovernanceRejected): pass_review(docket, draft, findings_digest="f" * 64)
        close_sources(resources, source_docket, ledger)

    def test_tampering_is_detected(self):
        resources, source_docket, ledger, book, draft = source()
        docket = SyntheticActivationDraftReviewDocket(); record = docket.submit(book, draft.draft_id, submitted_at=NOW)
        object.__setattr__(record, "record_digest", "f" * 64)
        self.assertFalse(docket.verify_chain())
        with self.assertRaises(GovernanceRejected): pass_review(docket, draft)
        close_sources(resources, source_docket, ledger)

    def test_evidence_caps_authority(self):
        resources, source_docket, ledger, book, draft = source()
        docket = SyntheticActivationDraftReviewDocket(); docket.submit(book, draft.draft_id, submitted_at=NOW); pass_review(docket, draft)
        evidence = docket.evidence()
        self.assertEqual(evidence["maximum_state"], ACTIVATION_DRAFT_REVIEW_MAXIMUM_STATE)
        self.assertTrue(evidence["review_chain_valid"])
        for key in evidence:
            if key.endswith("_present") or key.endswith("_allowed") or key.endswith("_executed") or key.endswith("_recorded") or key.endswith("_used"):
                self.assertFalse(evidence[key])
        close_sources(resources, source_docket, ledger)


if __name__ == "__main__":
    unittest.main()
