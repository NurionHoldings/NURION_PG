from __future__ import annotations
import unittest
from hashlib import sha256
from nurion_pg.arkaon.governance import GovernanceRejected,canonical_digest
from nurion_pg.synthetic_fixture_materialization_dry_run_assertions import ASSERTION_STATE,SyntheticFixtureMaterializationDryRunAssertionBook
from nurion_pg.synthetic_fixture_materialization_dry_run_expectation_review import ExpectationReviewDecision,SyntheticFixtureMaterializationDryRunExpectationReviewDocket
from nurion_pg.synthetic_fixture_materialization_dry_run_expectations import SyntheticFixtureMaterializationDryRunExpectationBook
from tests.test_patch_draft_limited_promotion_reconfirmation_intake import NOW
from tests.test_synthetic_fixture_materialization_dry_run_expectations import reviewed_scenario
from tests.test_synthetic_patch_draft_limited_promotion_activation_drafts import close_sources
def reviewed_expectation(decision=ExpectationReviewDecision.PASS):
    resources,sd,ledger,docket,review=reviewed_scenario();book=SyntheticFixtureMaterializationDryRunExpectationBook()
    item=book.draft_from_review(docket,review.scenario.scenario_id,drafted_at=NOW);reviews=SyntheticFixtureMaterializationDryRunExpectationReviewDocket()
    reviews.submit(book,item.expectation_id,submitted_at=NOW);final=reviews.record_eternian_review(item.expectation_id,
        review_id="synthetic:fixture-materialization-dry-run-expectation-review:assertion",
        reviewer_id="synthetic:eternian-reviewer:fixture-materialization-dry-run-expectation:assertion",decision=decision,
        findings_digest=sha256(b"assertion source").hexdigest(),reviewed_at=NOW);return resources,sd,ledger,reviews,final
class AssertionTests(unittest.TestCase):
    def test_unevaluated_assertion(self):
        resources,sd,ledger,docket,review=reviewed_expectation();book=SyntheticFixtureMaterializationDryRunAssertionBook()
        item=book.draft_from_review(docket,review.expectation.expectation_id,drafted_at=NOW);self.assertEqual(item.state,ASSERTION_STATE)
        self.assertFalse(item.evaluation_present);self.assertFalse(item.result_present);self.assertTrue(book.verify_chain());close_sources(resources,sd,ledger)
    def test_hold_reject_fail_closed(self):
        for decision in (ExpectationReviewDecision.HOLD,ExpectationReviewDecision.REJECT):
            resources,sd,ledger,docket,review=reviewed_expectation(decision)
            with self.assertRaises(GovernanceRejected):SyntheticFixtureMaterializationDryRunAssertionBook().draft_from_review(docket,review.expectation.expectation_id,drafted_at=NOW)
            close_sources(resources,sd,ledger)
    def test_replay_tamper_and_authority(self):
        resources,sd,ledger,docket,review=reviewed_expectation();book=SyntheticFixtureMaterializationDryRunAssertionBook()
        first=book.draft_from_review(docket,review.expectation.expectation_id,drafted_at=NOW);self.assertIs(first,book.draft_from_review(docket,review.expectation.expectation_id,drafted_at=NOW))
        object.__setattr__(first,"evaluation_present",True);object.__setattr__(first,"assertion_digest",canonical_digest(first.digest_value()));self.assertFalse(book.verify_chain());close_sources(resources,sd,ledger)
        e=SyntheticFixtureMaterializationDryRunAssertionBook().evidence()
        for key in e:
            if key.endswith("_present") or key.endswith("_allowed") or key.endswith("_executed") or key.endswith("_used"):self.assertFalse(e[key])
if __name__=="__main__":unittest.main()
