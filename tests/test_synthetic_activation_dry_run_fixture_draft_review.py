from __future__ import annotations
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256
from nurion_pg.arkaon.governance import GovernanceRejected,canonical_digest
from nurion_pg.synthetic_activation_dry_run_fixture_draft_review import FIXTURE_DRAFT_REVIEW_MAXIMUM_STATE,FixtureDraftReviewDecision,FixtureDraftReviewState,SyntheticActivationDryRunFixtureDraftReviewDocket
from nurion_pg.synthetic_activation_dry_run_fixture_drafts import SyntheticActivationDryRunFixtureDraftBook
from tests.test_patch_draft_limited_promotion_reconfirmation_intake import NOW
from tests.test_synthetic_activation_dry_run_fixture_drafts import source
from tests.test_synthetic_patch_draft_limited_promotion_activation_drafts import close_sources

def draft_source():
    resources,sd,ledger,proposal_review,review=source();book=SyntheticActivationDryRunFixtureDraftBook()
    draft=book.draft_from_review(proposal_review,review.proposal.proposal_id,drafted_at=NOW)
    return resources,sd,ledger,book,draft

def review(docket,draft,decision=FixtureDraftReviewDecision.PASS,reviewed_at=NOW):
    return docket.record_eternian_review(draft.draft_id,review_id="synthetic:activation-dry-run-fixture-draft-review:draft",
        reviewer_id="synthetic:eternian-reviewer:activation-dry-run-fixture-draft:draft",decision=decision,
        findings_digest=sha256(b"fixture draft independent review").hexdigest(),reviewed_at=reviewed_at)

class FixtureDraftReviewTests(unittest.TestCase):
    def test_pass_is_ready_for_materialization_plan_only(self):
        resources,sd,ledger,book,draft=draft_source();docket=SyntheticActivationDryRunFixtureDraftReviewDocket();pending=docket.submit(book,draft.draft_id,submitted_at=NOW)
        self.assertEqual(pending.state,FixtureDraftReviewState.PENDING_ETERNIAN_REVIEW)
        final=review(docket,draft);self.assertIs(docket.ready_source(draft.draft_id),final)
        self.assertEqual(final.state.value,FIXTURE_DRAFT_REVIEW_MAXIMUM_STATE);close_sources(resources,sd,ledger)
    def test_hold_and_reject_are_not_ready(self):
        for decision in (FixtureDraftReviewDecision.HOLD,FixtureDraftReviewDecision.REJECT):
            resources,sd,ledger,book,draft=draft_source();docket=SyntheticActivationDryRunFixtureDraftReviewDocket();docket.submit(book,draft.draft_id,submitted_at=NOW);review(docket,draft,decision)
            with self.assertRaises(GovernanceRejected):docket.ready_source(draft.draft_id)
            close_sources(resources,sd,ledger)
    def test_type_time_and_review_metadata_fail_closed(self):
        resources,sd,ledger,book,draft=draft_source();docket=SyntheticActivationDryRunFixtureDraftReviewDocket()
        with self.assertRaises(GovernanceRejected):docket.submit(object(),draft.draft_id,submitted_at=NOW)
        for value in (NOW.replace(tzinfo=None),NOW-timedelta(seconds=1)):
            with self.assertRaises(GovernanceRejected):docket.submit(book,draft.draft_id,submitted_at=value)
        docket.submit(book,draft.draft_id,submitted_at=NOW)
        with self.assertRaises(GovernanceRejected):review(docket,draft,reviewed_at=NOW.replace(tzinfo=None))
        with self.assertRaises(GovernanceRejected):review(docket,draft,reviewed_at=NOW-timedelta(seconds=1))
        close_sources(resources,sd,ledger)
    def test_replay_concurrency_and_final_review_are_immutable(self):
        resources,sd,ledger,book,draft=draft_source();docket=SyntheticActivationDryRunFixtureDraftReviewDocket()
        with ThreadPoolExecutor(max_workers=4) as pool:items=list(pool.map(lambda _:docket.submit(book,draft.draft_id,submitted_at=NOW),range(8)))
        self.assertTrue(all(i is items[0] for i in items));self.assertEqual(len(docket.records),1)
        first=review(docket,draft);self.assertIs(review(docket,draft),first)
        with self.assertRaises(GovernanceRejected):review(docket,draft,FixtureDraftReviewDecision.HOLD)
        close_sources(resources,sd,ledger)
    def test_submission_and_review_tampering_are_detected(self):
        resources,sd,ledger,book,draft=draft_source();docket=SyntheticActivationDryRunFixtureDraftReviewDocket();item=docket.submit(book,draft.draft_id,submitted_at=NOW)
        object.__setattr__(item,"submitted_at",NOW+timedelta(seconds=1));self.assertFalse(docket.verify_chain());close_sources(resources,sd,ledger)
        resources,sd,ledger,book,draft=draft_source();docket=SyntheticActivationDryRunFixtureDraftReviewDocket();docket.submit(book,draft.draft_id,submitted_at=NOW);item=review(docket,draft)
        object.__setattr__(item,"findings_digest","f"*64);self.assertFalse(docket.verify_chain());close_sources(resources,sd,ledger)
    def test_rehashed_source_identity_blueprint_and_forbidden_tampering_detected(self):
        for field,value in (("draft_id","synthetic:activation-dry-run-fixture-draft:"+"f"*32),("blueprint_digest","f"*64),("fixture_content_present",True)):
            resources,sd,ledger,book,draft=draft_source();object.__setattr__(draft,field,value);object.__setattr__(draft,"draft_digest",canonical_digest(draft.digest_value()))
            docket=SyntheticActivationDryRunFixtureDraftReviewDocket()
            with self.assertRaises(GovernanceRejected):docket.submit(book,draft.draft_id,submitted_at=NOW)
            close_sources(resources,sd,ledger)
    def test_evidence_caps_authority(self):
        resources,sd,ledger,book,draft=draft_source();docket=SyntheticActivationDryRunFixtureDraftReviewDocket();docket.submit(book,draft.draft_id,submitted_at=NOW);review(docket,draft);e=docket.evidence()
        self.assertEqual(e["maximum_state"],FIXTURE_DRAFT_REVIEW_MAXIMUM_STATE);self.assertTrue(e["review_chain_valid"])
        for key in e:
            if key.endswith("_present") or key.endswith("_allowed") or key.endswith("_executed") or key.endswith("_used"):self.assertFalse(e[key])
        close_sources(resources,sd,ledger)

if __name__=="__main__":unittest.main()
