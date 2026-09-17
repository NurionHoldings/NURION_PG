from __future__ import annotations
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256
from nurion_pg.arkaon.governance import GovernanceRejected,canonical_digest
from nurion_pg.synthetic_activation_dry_run_fixture_proposals import (
    FIXTURE_PROPOSAL_GATES,FIXTURE_PROPOSAL_SCOPE,FIXTURE_PROPOSAL_STATE,SyntheticActivationDryRunFixtureProposalBook,
)
from nurion_pg.synthetic_activation_dry_run_design_review import DryRunDesignReviewDecision,SyntheticActivationDryRunDesignReviewDocket
from nurion_pg.synthetic_activation_dry_run_designs import SyntheticActivationDryRunDesignBook
from tests.test_patch_draft_limited_promotion_reconfirmation_intake import NOW
from tests.test_synthetic_activation_dry_run_designs import reviewed_source
from tests.test_synthetic_patch_draft_limited_promotion_activation_drafts import close_sources

def proposal_source(decision=DryRunDesignReviewDecision.PASS):
    resources,sd,ledger,source_review,review=reviewed_source(); designs=SyntheticActivationDryRunDesignBook()
    design=designs.design_from_review(source_review,review.draft.draft_id,designed_at=NOW); docket=SyntheticActivationDryRunDesignReviewDocket()
    docket.submit(designs,design.design_id,submitted_at=NOW)
    final=docket.record_eternian_review(design.design_id,review_id="synthetic:activation-dry-run-design-review:proposal",
        reviewer_id="synthetic:eternian-reviewer:activation-dry-run-design:proposal",decision=decision,
        findings_digest=sha256(b"fixture proposal review").hexdigest(),reviewed_at=NOW)
    return resources,sd,ledger,docket,final

class FixtureProposalTests(unittest.TestCase):
    def test_proposal_contains_digests_only(self):
        resources,sd,ledger,docket,review=proposal_source();book=SyntheticActivationDryRunFixtureProposalBook();before=docket.evidence()["report_digest"]
        item=book.propose_from_review(docket,review.design.design_id,proposed_at=NOW)
        self.assertEqual(before,docket.evidence()["report_digest"]);self.assertEqual(item.scope,FIXTURE_PROPOSAL_SCOPE);self.assertEqual(item.required_gates,FIXTURE_PROPOSAL_GATES)
        self.assertFalse(item.fixture_content_present);self.assertFalse(item.fixture_file_created);close_sources(resources,sd,ledger)
    def test_hold_reject_and_invalid_inputs_fail_closed(self):
        for decision in (DryRunDesignReviewDecision.HOLD,DryRunDesignReviewDecision.REJECT):
            resources,sd,ledger,docket,review=proposal_source(decision)
            with self.assertRaises(GovernanceRejected):SyntheticActivationDryRunFixtureProposalBook().propose_from_review(docket,review.design.design_id,proposed_at=NOW)
            close_sources(resources,sd,ledger)
    def test_typed_source_and_time_required(self):
        resources,sd,ledger,docket,review=proposal_source();book=SyntheticActivationDryRunFixtureProposalBook()
        with self.assertRaises(GovernanceRejected):book.propose_from_review(object(),review.design.design_id,proposed_at=NOW)
        for value in (NOW.replace(tzinfo=None),NOW-timedelta(seconds=1)):
            with self.assertRaises(GovernanceRejected):book.propose_from_review(docket,review.design.design_id,proposed_at=value)
        close_sources(resources,sd,ledger)
    def test_exact_replay_and_concurrency_converge(self):
        resources,sd,ledger,docket,review=proposal_source();book=SyntheticActivationDryRunFixtureProposalBook()
        with ThreadPoolExecutor(max_workers=4) as pool:items=list(pool.map(lambda _:book.propose_from_review(docket,review.design.design_id,proposed_at=NOW),range(8)))
        self.assertTrue(all(i==items[0] for i in items));self.assertEqual(len(book.proposals),1);close_sources(resources,sd,ledger)
    def test_rehashed_forbidden_tampering_is_detected(self):
        resources,sd,ledger,docket,review=proposal_source();book=SyntheticActivationDryRunFixtureProposalBook();item=book.propose_from_review(docket,review.design.design_id,proposed_at=NOW)
        object.__setattr__(item,"fixture_content_present",True);object.__setattr__(item,"proposal_digest",canonical_digest(item.digest_value()))
        self.assertFalse(book.verify_proposal_chain());close_sources(resources,sd,ledger)
    def test_rehashed_identity_tampering_is_detected(self):
        resources,sd,ledger,docket,review=proposal_source();book=SyntheticActivationDryRunFixtureProposalBook();item=book.propose_from_review(docket,review.design.design_id,proposed_at=NOW)
        object.__setattr__(item,"proposal_id","synthetic:activation-dry-run-fixture-proposal:"+"f"*32);object.__setattr__(item,"proposal_digest",canonical_digest(item.digest_value()))
        self.assertFalse(book.verify_proposal_chain());close_sources(resources,sd,ledger)
    def test_source_change_discards_proposal(self):
        resources,sd,ledger,docket,review=proposal_source();book=SyntheticActivationDryRunFixtureProposalBook();original=docket.evidence;calls=0
        def changing():
            nonlocal calls;calls+=1;value=original();return value if calls==1 else {**value,"report_digest":"f"*64}
        docket.evidence=changing
        with self.assertRaises(GovernanceRejected):book.propose_from_review(docket,review.design.design_id,proposed_at=NOW)
        self.assertEqual(book.proposals,());close_sources(resources,sd,ledger)
    def test_evidence_caps_authority(self):
        resources,sd,ledger,docket,review=proposal_source();book=SyntheticActivationDryRunFixtureProposalBook();book.propose_from_review(docket,review.design.design_id,proposed_at=NOW);e=book.evidence()
        self.assertEqual(e["maximum_state"],FIXTURE_PROPOSAL_STATE);self.assertTrue(e["proposal_chain_valid"])
        for key in e:
            if key.endswith("_present") or key.endswith("_allowed") or key.endswith("_executed") or key.endswith("_used"):self.assertFalse(e[key])
        close_sources(resources,sd,ledger)
if __name__=="__main__":unittest.main()
