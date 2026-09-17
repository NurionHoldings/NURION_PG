from __future__ import annotations
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256
from nurion_pg.arkaon.governance import GovernanceRejected,canonical_digest
from nurion_pg.synthetic_activation_dry_run_fixture_proposal_review import FIXTURE_REVIEW_MAXIMUM_STATE,FixtureProposalReviewDecision,FixtureProposalReviewState,SyntheticActivationDryRunFixtureProposalReviewDocket
from nurion_pg.synthetic_activation_dry_run_fixture_proposals import SyntheticActivationDryRunFixtureProposalBook
from tests.test_patch_draft_limited_promotion_reconfirmation_intake import NOW
from tests.test_synthetic_activation_dry_run_fixture_proposals import proposal_source
from tests.test_synthetic_patch_draft_limited_promotion_activation_drafts import close_sources
FINDINGS=sha256(b"fixture proposal independent review").hexdigest()
def source():
    resources,sd,ledger,docket,review=proposal_source();book=SyntheticActivationDryRunFixtureProposalBook();proposal=book.propose_from_review(docket,review.design.design_id,proposed_at=NOW)
    return resources,sd,ledger,book,proposal
def passed(docket,proposal,**changes):
    v={"review_id":"synthetic:activation-dry-run-fixture-proposal-review:pass","reviewer_id":"synthetic:eternian-reviewer:activation-dry-run-fixture-proposal:pass",
       "decision":FixtureProposalReviewDecision.PASS,"findings_digest":FINDINGS,"reviewed_at":NOW};v.update(changes);return docket.record_eternian_review(proposal.proposal_id,**v)
class FixtureProposalReviewTests(unittest.TestCase):
    def test_pending_then_pass_stops_at_fixture_draft_readiness(self):
        resources,sd,ledger,book,p=source();d=SyntheticActivationDryRunFixtureProposalReviewDocket();pending=d.submit(book,p.proposal_id,submitted_at=NOW)
        self.assertIs(pending.state,FixtureProposalReviewState.PENDING_ETERNIAN_REVIEW);review=passed(d,p)
        self.assertIs(review.state,FixtureProposalReviewState.READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_DRAFT);self.assertEqual(d.ready_source(p.proposal_id),review);close_sources(resources,sd,ledger)
    def test_hold_and_reject_not_ready(self):
        for decision,state in ((FixtureProposalReviewDecision.HOLD,FixtureProposalReviewState.HELD),(FixtureProposalReviewDecision.REJECT,FixtureProposalReviewState.REJECTED)):
            resources,sd,ledger,book,p=source();d=SyntheticActivationDryRunFixtureProposalReviewDocket();d.submit(book,p.proposal_id,submitted_at=NOW)
            item=d.record_eternian_review(p.proposal_id,review_id=f"synthetic:activation-dry-run-fixture-proposal-review:{decision.value.lower()}",reviewer_id=f"synthetic:eternian-reviewer:activation-dry-run-fixture-proposal:{decision.value.lower()}",decision=decision,findings_digest=FINDINGS,reviewed_at=NOW)
            self.assertIs(item.state,state)
            with self.assertRaises(GovernanceRejected):d.ready_source(p.proposal_id)
            close_sources(resources,sd,ledger)
    def test_invalid_inputs_time_and_metadata_fail_closed(self):
        resources,sd,ledger,book,p=source();d=SyntheticActivationDryRunFixtureProposalReviewDocket()
        with self.assertRaises(GovernanceRejected):d.submit(object(),p.proposal_id,submitted_at=NOW)
        with self.assertRaises(GovernanceRejected):d.submit(book,p.proposal_id,submitted_at=NOW.replace(tzinfo=None))
        d.submit(book,p.proposal_id,submitted_at=NOW)
        for c in ({"review_id":"bad"},{"reviewer_id":"bad"},{"decision":"PASS"},{"findings_digest":"bad"},{"reviewed_at":NOW-timedelta(seconds=1)}):
            with self.assertRaises(GovernanceRejected):passed(d,p,**c)
        close_sources(resources,sd,ledger)
    def test_concurrent_idempotent_and_immutable(self):
        resources,sd,ledger,book,p=source();d=SyntheticActivationDryRunFixtureProposalReviewDocket();d.submit(book,p.proposal_id,submitted_at=NOW)
        with ThreadPoolExecutor(max_workers=4) as pool:items=list(pool.map(lambda _:passed(d,p),range(8)))
        self.assertTrue(all(i==items[0] for i in items))
        with self.assertRaises(GovernanceRejected):passed(d,p,findings_digest="f"*64)
        close_sources(resources,sd,ledger)
    def test_submission_and_review_tampering_break_chain(self):
        resources,sd,ledger,book,p=source();d=SyntheticActivationDryRunFixtureProposalReviewDocket();item=d.submit(book,p.proposal_id,submitted_at=NOW)
        object.__setattr__(item,"submission_digest","f"*64);self.assertFalse(d.verify_chain());close_sources(resources,sd,ledger)
        resources,sd,ledger,book,p=source();d=SyntheticActivationDryRunFixtureProposalReviewDocket();d.submit(book,p.proposal_id,submitted_at=NOW);item=passed(d,p)
        object.__setattr__(item,"findings_digest","f"*64);self.assertFalse(d.verify_chain());close_sources(resources,sd,ledger)
    def test_rehashed_source_identity_tampering_breaks_chain(self):
        resources,sd,ledger,book,p=source();d=SyntheticActivationDryRunFixtureProposalReviewDocket();d.submit(book,p.proposal_id,submitted_at=NOW)
        object.__setattr__(p,"proposal_id","synthetic:activation-dry-run-fixture-proposal:"+"f"*32);object.__setattr__(p,"proposal_digest",canonical_digest(p.digest_value()))
        self.assertFalse(d.verify_chain());close_sources(resources,sd,ledger)
    def test_evidence_caps_authority(self):
        resources,sd,ledger,book,p=source();d=SyntheticActivationDryRunFixtureProposalReviewDocket();d.submit(book,p.proposal_id,submitted_at=NOW);passed(d,p);e=d.evidence()
        self.assertEqual(e["maximum_state"],FIXTURE_REVIEW_MAXIMUM_STATE);self.assertTrue(e["review_chain_valid"])
        for k in e:
            if k.endswith("_present") or k.endswith("_allowed") or k.endswith("_executed") or k.endswith("_used"):self.assertFalse(e[k])
        close_sources(resources,sd,ledger)
if __name__=="__main__":unittest.main()
