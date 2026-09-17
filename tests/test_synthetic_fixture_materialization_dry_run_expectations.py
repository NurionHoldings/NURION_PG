from __future__ import annotations
import unittest
from hashlib import sha256
from nurion_pg.arkaon.governance import GovernanceRejected,canonical_digest
from nurion_pg.synthetic_fixture_materialization_dry_run_expectations import EXPECTATION_STATE,SyntheticFixtureMaterializationDryRunExpectationBook
from nurion_pg.synthetic_fixture_materialization_dry_run_scenario_review import ScenarioReviewDecision,SyntheticFixtureMaterializationDryRunScenarioReviewDocket
from nurion_pg.synthetic_fixture_materialization_dry_run_scenarios import SyntheticFixtureMaterializationDryRunScenarioBook
from tests.test_patch_draft_limited_promotion_reconfirmation_intake import NOW
from tests.test_synthetic_fixture_materialization_dry_run_scenarios import source
from tests.test_synthetic_patch_draft_limited_promotion_activation_drafts import close_sources
def reviewed_scenario(decision=ScenarioReviewDecision.PASS):
    resources,sd,ledger,docket,review=source();scenarios=SyntheticFixtureMaterializationDryRunScenarioBook()
    scenario=scenarios.draft_from_review(docket,review.plan.plan_id,drafted_at=NOW);reviews=SyntheticFixtureMaterializationDryRunScenarioReviewDocket()
    reviews.submit(scenarios,scenario.scenario_id,submitted_at=NOW);final=reviews.record_eternian_review(scenario.scenario_id,
        review_id="synthetic:fixture-materialization-dry-run-scenario-review:expectation",
        reviewer_id="synthetic:eternian-reviewer:fixture-materialization-dry-run-scenario:expectation",decision=decision,
        findings_digest=sha256(b"expectation source").hexdigest(),reviewed_at=NOW);return resources,sd,ledger,reviews,final
class ExpectationTests(unittest.TestCase):
    def test_observation_free_expectation(self):
        resources,sd,ledger,docket,review=reviewed_scenario();book=SyntheticFixtureMaterializationDryRunExpectationBook()
        item=book.draft_from_review(docket,review.scenario.scenario_id,drafted_at=NOW);self.assertEqual(item.state,EXPECTATION_STATE)
        self.assertFalse(item.observations_present);self.assertFalse(item.result_present);self.assertTrue(book.verify_chain());close_sources(resources,sd,ledger)
    def test_hold_reject_fail_closed(self):
        for decision in (ScenarioReviewDecision.HOLD,ScenarioReviewDecision.REJECT):
            resources,sd,ledger,docket,review=reviewed_scenario(decision)
            with self.assertRaises(GovernanceRejected):SyntheticFixtureMaterializationDryRunExpectationBook().draft_from_review(docket,review.scenario.scenario_id,drafted_at=NOW)
            close_sources(resources,sd,ledger)
    def test_replay_tamper_and_authority(self):
        resources,sd,ledger,docket,review=reviewed_scenario();book=SyntheticFixtureMaterializationDryRunExpectationBook()
        first=book.draft_from_review(docket,review.scenario.scenario_id,drafted_at=NOW);self.assertIs(first,book.draft_from_review(docket,review.scenario.scenario_id,drafted_at=NOW))
        object.__setattr__(first,"observations_present",True);object.__setattr__(first,"expectation_digest",canonical_digest(first.digest_value()));self.assertFalse(book.verify_chain());close_sources(resources,sd,ledger)
        e=SyntheticFixtureMaterializationDryRunExpectationBook().evidence()
        for key in e:
            if key.endswith("_present") or key.endswith("_allowed") or key.endswith("_executed") or key.endswith("_used"):self.assertFalse(e[key])
if __name__=="__main__":unittest.main()
