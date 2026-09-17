from __future__ import annotations
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256
from nurion_pg.arkaon.governance import GovernanceRejected,canonical_digest
from nurion_pg.synthetic_activation_dry_run_fixture_materialization_dry_run_plan_review import MATERIALIZATION_DRY_RUN_PLAN_REVIEW_MAXIMUM_STATE,MaterializationDryRunPlanReviewDecision,MaterializationDryRunPlanReviewState,SyntheticActivationDryRunFixtureMaterializationDryRunPlanReviewDocket
from nurion_pg.synthetic_activation_dry_run_fixture_materialization_dry_run_plans import SyntheticActivationDryRunFixtureMaterializationDryRunPlanBook
from tests.test_patch_draft_limited_promotion_reconfirmation_intake import NOW
from tests.test_synthetic_activation_dry_run_fixture_materialization_dry_run_plans import reviewed_specification_source
from tests.test_synthetic_patch_draft_limited_promotion_activation_drafts import close_sources

def plan_source():
    resources,sd,ledger,docket,review=reviewed_specification_source();book=SyntheticActivationDryRunFixtureMaterializationDryRunPlanBook()
    plan=book.plan_from_review(docket,review.specification.specification_id,planned_at=NOW);return resources,sd,ledger,book,plan
def review(docket,plan,decision=MaterializationDryRunPlanReviewDecision.PASS,reviewed_at=NOW):
    return docket.record_eternian_review(plan.plan_id,review_id="synthetic:activation-dry-run-fixture-materialization-dry-run-plan-review:draft",
        reviewer_id="synthetic:eternian-reviewer:activation-dry-run-fixture-materialization-dry-run-plan:draft",decision=decision,
        findings_digest=sha256(b"materialization dry-run plan independent review").hexdigest(),reviewed_at=reviewed_at)

class MaterializationDryRunPlanReviewTests(unittest.TestCase):
    def test_pass_is_ready_for_scenario_draft_only(self):
        resources,sd,ledger,book,plan=plan_source();docket=SyntheticActivationDryRunFixtureMaterializationDryRunPlanReviewDocket()
        pending=docket.submit(book,plan.plan_id,submitted_at=NOW);self.assertEqual(pending.state,MaterializationDryRunPlanReviewState.PENDING_ETERNIAN_REVIEW)
        final=review(docket,plan);self.assertIs(docket.ready_source(plan.plan_id),final);self.assertEqual(final.state.value,MATERIALIZATION_DRY_RUN_PLAN_REVIEW_MAXIMUM_STATE)
        close_sources(resources,sd,ledger)
    def test_hold_reject_type_and_time_fail_closed(self):
        for decision in (MaterializationDryRunPlanReviewDecision.HOLD,MaterializationDryRunPlanReviewDecision.REJECT):
            resources,sd,ledger,book,plan=plan_source();docket=SyntheticActivationDryRunFixtureMaterializationDryRunPlanReviewDocket()
            docket.submit(book,plan.plan_id,submitted_at=NOW);review(docket,plan,decision)
            with self.assertRaises(GovernanceRejected):docket.ready_source(plan.plan_id)
            close_sources(resources,sd,ledger)
        resources,sd,ledger,book,plan=plan_source();docket=SyntheticActivationDryRunFixtureMaterializationDryRunPlanReviewDocket()
        with self.assertRaises(GovernanceRejected):docket.submit(object(),plan.plan_id,submitted_at=NOW)
        with self.assertRaises(GovernanceRejected):docket.submit(book,plan.plan_id,submitted_at=NOW.replace(tzinfo=None))
        with self.assertRaises(GovernanceRejected):docket.submit(book,plan.plan_id,submitted_at=NOW-timedelta(seconds=1))
        close_sources(resources,sd,ledger)
    def test_replay_concurrency_and_final_review_are_immutable(self):
        resources,sd,ledger,book,plan=plan_source();docket=SyntheticActivationDryRunFixtureMaterializationDryRunPlanReviewDocket()
        with ThreadPoolExecutor(max_workers=4) as pool:items=list(pool.map(lambda _:docket.submit(book,plan.plan_id,submitted_at=NOW),range(8)))
        self.assertTrue(all(i is items[0] for i in items));first=review(docket,plan);self.assertIs(review(docket,plan),first)
        with self.assertRaises(GovernanceRejected):review(docket,plan,MaterializationDryRunPlanReviewDecision.HOLD)
        close_sources(resources,sd,ledger)
    def test_fully_rehashed_review_metadata_tampering_is_detected(self):
        resources,sd,ledger,book,plan=plan_source();docket=SyntheticActivationDryRunFixtureMaterializationDryRunPlanReviewDocket()
        docket.submit(book,plan.plan_id,submitted_at=NOW);item=review(docket,plan);object.__setattr__(item,"reviewed_at",NOW-timedelta(seconds=1))
        object.__setattr__(item,"review_digest",canonical_digest(item.review_value()));self.assertFalse(docket.verify_chain());close_sources(resources,sd,ledger)
    def test_rehashed_plan_and_nested_lineage_tampering_detected(self):
        for field,value in (("plan_id","synthetic:activation-dry-run-fixture-materialization-dry-run-plan:"+"f"*32),
            ("dry_run_contract_digest","f"*64),("synthetic_only",False),("fixture_content_present",True),("filesystem_written",True),("dry_run_executed",True)):
            resources,sd,ledger,book,plan=plan_source();object.__setattr__(plan,field,value);object.__setattr__(plan,"plan_digest",canonical_digest(plan.digest_value()))
            with self.assertRaises(GovernanceRejected):SyntheticActivationDryRunFixtureMaterializationDryRunPlanReviewDocket().submit(book,plan.plan_id,submitted_at=NOW)
            close_sources(resources,sd,ledger)
        resources,sd,ledger,book,plan=plan_source();object.__setattr__(plan.source_review,"findings_digest","f"*64)
        with self.assertRaises(GovernanceRejected):SyntheticActivationDryRunFixtureMaterializationDryRunPlanReviewDocket().submit(book,plan.plan_id,submitted_at=NOW)
        close_sources(resources,sd,ledger)
    def test_source_change_discards_submission(self):
        resources,sd,ledger,book,plan=plan_source();docket=SyntheticActivationDryRunFixtureMaterializationDryRunPlanReviewDocket();original=book.evidence;calls=0
        def changing():
            nonlocal calls;calls+=1;v=original();return v if calls==1 else {**v,"report_digest":"f"*64}
        book.evidence=changing
        with self.assertRaises(GovernanceRejected):docket.submit(book,plan.plan_id,submitted_at=NOW)
        self.assertEqual(docket.records,());close_sources(resources,sd,ledger)
    def test_evidence_caps_authority(self):
        resources,sd,ledger,book,plan=plan_source();docket=SyntheticActivationDryRunFixtureMaterializationDryRunPlanReviewDocket()
        docket.submit(book,plan.plan_id,submitted_at=NOW);review(docket,plan);e=docket.evidence()
        self.assertEqual(e["maximum_state"],MATERIALIZATION_DRY_RUN_PLAN_REVIEW_MAXIMUM_STATE);self.assertTrue(e["review_chain_valid"])
        for key in e:
            if key.endswith("_present") or key.endswith("_allowed") or key.endswith("_executed") or key.endswith("_used"):self.assertFalse(e[key])
        close_sources(resources,sd,ledger)

if __name__=="__main__":unittest.main()
