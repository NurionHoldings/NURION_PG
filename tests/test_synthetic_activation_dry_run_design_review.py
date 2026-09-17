from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_activation_dry_run_design_review import (
    DESIGN_REVIEW_MAXIMUM_STATE, DryRunDesignReviewDecision, DryRunDesignReviewState,
    SyntheticActivationDryRunDesignReviewDocket,
)
from nurion_pg.synthetic_activation_dry_run_designs import SyntheticActivationDryRunDesignBook
from tests.test_patch_draft_limited_promotion_reconfirmation_intake import NOW
from tests.test_synthetic_activation_dry_run_designs import reviewed_source
from tests.test_synthetic_patch_draft_limited_promotion_activation_drafts import close_sources

FINDINGS=sha256(b"activation dry-run design review").hexdigest()

def design_source():
    resources,source_docket,ledger,docket,review=reviewed_source()
    book=SyntheticActivationDryRunDesignBook(); design=book.design_from_review(docket,review.draft.draft_id,designed_at=NOW)
    return resources,source_docket,ledger,book,design

def pass_review(docket,design,**overrides):
    values={"review_id":"synthetic:activation-dry-run-design-review:pass",
            "reviewer_id":"synthetic:eternian-reviewer:activation-dry-run-design:pass",
            "decision":DryRunDesignReviewDecision.PASS,"findings_digest":FINDINGS,"reviewed_at":NOW}
    values.update(overrides); return docket.record_eternian_review(design.design_id,**values)

class SyntheticActivationDryRunDesignReviewTests(unittest.TestCase):
    def test_submission_is_pending_and_non_executing(self):
        resources,sd,ledger,book,design=design_source(); docket=SyntheticActivationDryRunDesignReviewDocket()
        item=docket.submit(book,design.design_id,submitted_at=NOW)
        self.assertIs(item.state,DryRunDesignReviewState.PENDING_ETERNIAN_REVIEW); self.assertIsNone(item.review_digest)
        close_sources(resources,sd,ledger)

    def test_pass_stops_at_fixture_proposal_readiness(self):
        resources,sd,ledger,book,design=design_source(); docket=SyntheticActivationDryRunDesignReviewDocket()
        docket.submit(book,design.design_id,submitted_at=NOW); item=pass_review(docket,design)
        self.assertIs(item.state,DryRunDesignReviewState.READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_PROPOSAL)
        self.assertEqual(docket.ready_source(design.design_id),item); close_sources(resources,sd,ledger)

    def test_hold_and_reject_are_not_ready(self):
        for decision,state in ((DryRunDesignReviewDecision.HOLD,DryRunDesignReviewState.HELD),(DryRunDesignReviewDecision.REJECT,DryRunDesignReviewState.REJECTED)):
            resources,sd,ledger,book,design=design_source(); docket=SyntheticActivationDryRunDesignReviewDocket(); docket.submit(book,design.design_id,submitted_at=NOW)
            item=docket.record_eternian_review(design.design_id,review_id=f"synthetic:activation-dry-run-design-review:{decision.value.lower()}",reviewer_id=f"synthetic:eternian-reviewer:activation-dry-run-design:{decision.value.lower()}",decision=decision,findings_digest=FINDINGS,reviewed_at=NOW)
            self.assertIs(item.state,state)
            with self.assertRaises(GovernanceRejected): docket.ready_source(design.design_id)
            close_sources(resources,sd,ledger)

    def test_invalid_source_time_and_metadata_fail_closed(self):
        resources,sd,ledger,book,design=design_source(); docket=SyntheticActivationDryRunDesignReviewDocket()
        with self.assertRaises(GovernanceRejected): docket.submit(object(),design.design_id,submitted_at=NOW)
        with self.assertRaises(GovernanceRejected): docket.submit(book,design.design_id,submitted_at=NOW.replace(tzinfo=None))
        docket.submit(book,design.design_id,submitted_at=NOW)
        for override in ({"review_id":"bad"},{"reviewer_id":"bad"},{"decision":"PASS"},{"findings_digest":"bad"},{"reviewed_at":NOW-timedelta(seconds=1)}):
            with self.assertRaises(GovernanceRejected): pass_review(docket,design,**override)
        close_sources(resources,sd,ledger)

    def test_review_is_concurrent_idempotent_and_immutable(self):
        resources,sd,ledger,book,design=design_source(); docket=SyntheticActivationDryRunDesignReviewDocket(); docket.submit(book,design.design_id,submitted_at=NOW)
        with ThreadPoolExecutor(max_workers=4) as pool: items=list(pool.map(lambda _:pass_review(docket,design),range(8)))
        self.assertTrue(all(i==items[0] for i in items))
        with self.assertRaises(GovernanceRejected): pass_review(docket,design,findings_digest="f"*64)
        close_sources(resources,sd,ledger)

    def test_tampering_breaks_chain(self):
        resources,sd,ledger,book,design=design_source(); docket=SyntheticActivationDryRunDesignReviewDocket(); item=docket.submit(book,design.design_id,submitted_at=NOW)
        object.__setattr__(item,"submission_digest","f"*64); self.assertFalse(docket.verify_chain())
        with self.assertRaises(GovernanceRejected): pass_review(docket,design)
        close_sources(resources,sd,ledger)

    def test_rehashed_review_tampering_is_detected(self):
        resources,sd,ledger,book,design=design_source(); docket=SyntheticActivationDryRunDesignReviewDocket(); docket.submit(book,design.design_id,submitted_at=NOW)
        item=pass_review(docket,design); object.__setattr__(item,"findings_digest","f"*64)
        self.assertFalse(docket.verify_chain()); close_sources(resources,sd,ledger)

    def test_evidence_caps_authority(self):
        resources,sd,ledger,book,design=design_source(); docket=SyntheticActivationDryRunDesignReviewDocket(); docket.submit(book,design.design_id,submitted_at=NOW); pass_review(docket,design)
        evidence=docket.evidence(); self.assertEqual(evidence["maximum_state"],DESIGN_REVIEW_MAXIMUM_STATE); self.assertTrue(evidence["review_chain_valid"])
        for key in evidence:
            if key.endswith("_present") or key.endswith("_allowed") or key.endswith("_executed") or key.endswith("_used"): self.assertFalse(evidence[key])
        close_sources(resources,sd,ledger)

if __name__=="__main__": unittest.main()
