from __future__ import annotations
import unittest
from datetime import timedelta
from hashlib import sha256
from nurion_pg.arkaon.governance import GovernanceRejected,canonical_digest
from nurion_pg.synthetic_fixture_materialization_dry_run_expectation_review import EXPECTATION_REVIEW_MAXIMUM_STATE,ExpectationReviewDecision,SyntheticFixtureMaterializationDryRunExpectationReviewDocket
from nurion_pg.synthetic_fixture_materialization_dry_run_expectations import SyntheticFixtureMaterializationDryRunExpectationBook
from tests.test_patch_draft_limited_promotion_reconfirmation_intake import NOW
from tests.test_synthetic_fixture_materialization_dry_run_expectations import reviewed_scenario
from tests.test_synthetic_patch_draft_limited_promotion_activation_drafts import close_sources
def expectation_source():
    resources,sd,ledger,docket,review=reviewed_scenario();book=SyntheticFixtureMaterializationDryRunExpectationBook()
    item=book.draft_from_review(docket,review.scenario.scenario_id,drafted_at=NOW);return resources,sd,ledger,book,item
def review(docket,item,decision=ExpectationReviewDecision.PASS):
    return docket.record_eternian_review(item.expectation_id,review_id="synthetic:fixture-materialization-dry-run-expectation-review:draft",
        reviewer_id="synthetic:eternian-reviewer:fixture-materialization-dry-run-expectation:draft",decision=decision,
        findings_digest=sha256(b"expectation review").hexdigest(),reviewed_at=NOW)
class ExpectationReviewTests(unittest.TestCase):
    def test_pass_hold_reject(self):
        resources,sd,ledger,book,item=expectation_source();docket=SyntheticFixtureMaterializationDryRunExpectationReviewDocket()
        docket.submit(book,item.expectation_id,submitted_at=NOW);final=review(docket,item);self.assertIs(docket.ready_source(item.expectation_id),final)
        self.assertEqual(final.state.value,EXPECTATION_REVIEW_MAXIMUM_STATE);close_sources(resources,sd,ledger)
        for decision in (ExpectationReviewDecision.HOLD,ExpectationReviewDecision.REJECT):
            resources,sd,ledger,book,item=expectation_source();docket=SyntheticFixtureMaterializationDryRunExpectationReviewDocket()
            docket.submit(book,item.expectation_id,submitted_at=NOW);review(docket,item,decision)
            with self.assertRaises(GovernanceRejected):docket.ready_source(item.expectation_id)
            close_sources(resources,sd,ledger)
    def test_type_time_and_tamper_fail_closed(self):
        resources,sd,ledger,book,item=expectation_source();docket=SyntheticFixtureMaterializationDryRunExpectationReviewDocket()
        with self.assertRaises(GovernanceRejected):docket.submit(object(),item.expectation_id,submitted_at=NOW)
        with self.assertRaises(GovernanceRejected):docket.submit(book,item.expectation_id,submitted_at=NOW-timedelta(seconds=1))
        record=docket.submit(book,item.expectation_id,submitted_at=NOW);object.__setattr__(record,"submitted_at",NOW-timedelta(seconds=1))
        object.__setattr__(record,"submission_digest",canonical_digest(record.submission_value()));self.assertFalse(docket.verify_chain());close_sources(resources,sd,ledger)
    def test_source_tamper_immutable_and_authority(self):
        resources,sd,ledger,book,item=expectation_source();object.__setattr__(item,"observations_present",True);object.__setattr__(item,"expectation_digest",canonical_digest(item.digest_value()))
        with self.assertRaises(GovernanceRejected):SyntheticFixtureMaterializationDryRunExpectationReviewDocket().submit(book,item.expectation_id,submitted_at=NOW)
        close_sources(resources,sd,ledger)
        resources,sd,ledger,book,item=expectation_source();docket=SyntheticFixtureMaterializationDryRunExpectationReviewDocket()
        docket.submit(book,item.expectation_id,submitted_at=NOW);first=review(docket,item);self.assertIs(review(docket,item),first)
        with self.assertRaises(GovernanceRejected):review(docket,item,ExpectationReviewDecision.HOLD)
        e=docket.evidence();self.assertTrue(e["review_chain_valid"]);self.assertEqual(e["review_digests"],[first.review_digest])
        for key in e:
            if key.endswith("_present") or key.endswith("_allowed") or key.endswith("_executed") or key.endswith("_used"):self.assertFalse(e[key])
        close_sources(resources,sd,ledger)
if __name__=="__main__":unittest.main()
