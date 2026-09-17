from __future__ import annotations
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256
from nurion_pg.arkaon.governance import GovernanceRejected,canonical_digest
from nurion_pg.synthetic_activation_dry_run_fixture_drafts import FIXTURE_DRAFT_GATES,FIXTURE_DRAFT_SCOPE,FIXTURE_DRAFT_STATE,SyntheticActivationDryRunFixtureDraftBook
from nurion_pg.synthetic_activation_dry_run_fixture_proposal_review import FixtureProposalReviewDecision,SyntheticActivationDryRunFixtureProposalReviewDocket
from nurion_pg.synthetic_activation_dry_run_fixture_proposals import SyntheticActivationDryRunFixtureProposalBook
from tests.test_patch_draft_limited_promotion_reconfirmation_intake import NOW
from tests.test_synthetic_activation_dry_run_fixture_proposals import proposal_source
from tests.test_synthetic_patch_draft_limited_promotion_activation_drafts import close_sources
def source(decision=FixtureProposalReviewDecision.PASS):
    resources,sd,ledger,docket,review=proposal_source();book=SyntheticActivationDryRunFixtureProposalBook();p=book.propose_from_review(docket,review.design.design_id,proposed_at=NOW)
    r=SyntheticActivationDryRunFixtureProposalReviewDocket();r.submit(book,p.proposal_id,submitted_at=NOW)
    final=r.record_eternian_review(p.proposal_id,review_id="synthetic:activation-dry-run-fixture-proposal-review:draft",reviewer_id="synthetic:eternian-reviewer:activation-dry-run-fixture-proposal:draft",
        decision=decision,findings_digest=sha256(b"fixture draft source review").hexdigest(),reviewed_at=NOW)
    return resources,sd,ledger,r,final
class FixtureDraftTests(unittest.TestCase):
    def test_draft_is_blueprint_digests_only(self):
        resources,sd,ledger,docket,review=source();book=SyntheticActivationDryRunFixtureDraftBook();before=docket.evidence()["report_digest"]
        item=book.draft_from_review(docket,review.proposal.proposal_id,drafted_at=NOW)
        self.assertEqual(before,docket.evidence()["report_digest"]);self.assertEqual(item.scope,FIXTURE_DRAFT_SCOPE);self.assertEqual(item.required_gates,FIXTURE_DRAFT_GATES)
        self.assertFalse(item.fixture_content_present);self.assertFalse(item.fixture_serialized);self.assertFalse(item.fixture_file_created);close_sources(resources,sd,ledger)
    def test_hold_reject_and_invalid_inputs_fail_closed(self):
        for decision in (FixtureProposalReviewDecision.HOLD,FixtureProposalReviewDecision.REJECT):
            resources,sd,ledger,docket,review=source(decision)
            with self.assertRaises(GovernanceRejected):SyntheticActivationDryRunFixtureDraftBook().draft_from_review(docket,review.proposal.proposal_id,drafted_at=NOW)
            close_sources(resources,sd,ledger)
    def test_type_and_time_fail_closed(self):
        resources,sd,ledger,docket,review=source();book=SyntheticActivationDryRunFixtureDraftBook()
        with self.assertRaises(GovernanceRejected):book.draft_from_review(object(),review.proposal.proposal_id,drafted_at=NOW)
        for value in (NOW.replace(tzinfo=None),NOW-timedelta(seconds=1)):
            with self.assertRaises(GovernanceRejected):book.draft_from_review(docket,review.proposal.proposal_id,drafted_at=value)
        close_sources(resources,sd,ledger)
    def test_replay_and_concurrency_converge(self):
        resources,sd,ledger,docket,review=source();book=SyntheticActivationDryRunFixtureDraftBook()
        with ThreadPoolExecutor(max_workers=4) as pool:items=list(pool.map(lambda _:book.draft_from_review(docket,review.proposal.proposal_id,drafted_at=NOW),range(8)))
        self.assertTrue(all(i==items[0] for i in items));self.assertEqual(len(book.drafts),1);close_sources(resources,sd,ledger)
    def test_rehashed_identity_and_forbidden_tampering_detected(self):
        resources,sd,ledger,docket,review=source();book=SyntheticActivationDryRunFixtureDraftBook();item=book.draft_from_review(docket,review.proposal.proposal_id,drafted_at=NOW)
        object.__setattr__(item,"draft_id","synthetic:activation-dry-run-fixture-draft:"+"f"*32);object.__setattr__(item,"draft_digest",canonical_digest(item.digest_value()));self.assertFalse(book.verify_draft_chain());close_sources(resources,sd,ledger)
        resources,sd,ledger,docket,review=source();book=SyntheticActivationDryRunFixtureDraftBook();item=book.draft_from_review(docket,review.proposal.proposal_id,drafted_at=NOW)
        object.__setattr__(item,"fixture_content_present",True);object.__setattr__(item,"draft_digest",canonical_digest(item.digest_value()));self.assertFalse(book.verify_draft_chain());close_sources(resources,sd,ledger)
    def test_rehashed_blueprint_tampering_is_detected(self):
        resources,sd,ledger,docket,review=source();book=SyntheticActivationDryRunFixtureDraftBook();item=book.draft_from_review(docket,review.proposal.proposal_id,drafted_at=NOW)
        object.__setattr__(item,"blueprint_digest","f"*64);object.__setattr__(item,"draft_digest",canonical_digest(item.digest_value()))
        self.assertFalse(book.verify_draft_chain());close_sources(resources,sd,ledger)
    def test_source_change_discards_draft(self):
        resources,sd,ledger,docket,review=source();book=SyntheticActivationDryRunFixtureDraftBook();original=docket.evidence;calls=0
        def changing():
            nonlocal calls;calls+=1;v=original();return v if calls==1 else {**v,"report_digest":"f"*64}
        docket.evidence=changing
        with self.assertRaises(GovernanceRejected):book.draft_from_review(docket,review.proposal.proposal_id,drafted_at=NOW)
        self.assertEqual(book.drafts,());close_sources(resources,sd,ledger)
    def test_evidence_caps_authority(self):
        resources,sd,ledger,docket,review=source();book=SyntheticActivationDryRunFixtureDraftBook();book.draft_from_review(docket,review.proposal.proposal_id,drafted_at=NOW);e=book.evidence()
        self.assertEqual(e["maximum_state"],FIXTURE_DRAFT_STATE);self.assertTrue(e["draft_chain_valid"])
        for k in e:
            if k.endswith("_present") or k.endswith("_allowed") or k.endswith("_executed") or k.endswith("_used"):self.assertFalse(e[k])
        close_sources(resources,sd,ledger)
if __name__=="__main__":unittest.main()
