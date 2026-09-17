from __future__ import annotations
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256
from nurion_pg.arkaon.governance import GovernanceRejected,canonical_digest
from nurion_pg.synthetic_activation_dry_run_fixture_materialization_plan_review import FIXTURE_MATERIALIZATION_PLAN_REVIEW_MAXIMUM_STATE,FixtureMaterializationPlanReviewDecision,FixtureMaterializationPlanReviewState,SyntheticActivationDryRunFixtureMaterializationPlanReviewDocket
from nurion_pg.synthetic_activation_dry_run_fixture_materialization_plans import SyntheticActivationDryRunFixtureMaterializationPlanBook
from tests.test_patch_draft_limited_promotion_reconfirmation_intake import NOW
from tests.test_synthetic_activation_dry_run_fixture_materialization_plans import reviewed_source
from tests.test_synthetic_patch_draft_limited_promotion_activation_drafts import close_sources

def plan_source():
    resources,sd,ledger,docket,review=reviewed_source();book=SyntheticActivationDryRunFixtureMaterializationPlanBook()
    plan=book.plan_from_review(docket,review.draft.draft_id,planned_at=NOW);return resources,sd,ledger,book,plan
def review(docket,plan,decision=FixtureMaterializationPlanReviewDecision.PASS,reviewed_at=NOW):
    return docket.record_eternian_review(plan.plan_id,review_id="synthetic:activation-dry-run-fixture-materialization-plan-review:draft",
        reviewer_id="synthetic:eternian-reviewer:activation-dry-run-fixture-materialization-plan:draft",decision=decision,
        findings_digest=sha256(b"fixture materialization plan independent review").hexdigest(),reviewed_at=reviewed_at)

class FixtureMaterializationPlanReviewTests(unittest.TestCase):
    def test_pass_is_ready_for_specification_only(self):
        resources,sd,ledger,book,plan=plan_source();docket=SyntheticActivationDryRunFixtureMaterializationPlanReviewDocket();pending=docket.submit(book,plan.plan_id,submitted_at=NOW)
        self.assertEqual(pending.state,FixtureMaterializationPlanReviewState.PENDING_ETERNIAN_REVIEW)
        final=review(docket,plan);self.assertIs(docket.ready_source(plan.plan_id),final)
        self.assertEqual(final.state.value,FIXTURE_MATERIALIZATION_PLAN_REVIEW_MAXIMUM_STATE);close_sources(resources,sd,ledger)
    def test_hold_and_reject_are_not_ready(self):
        for decision in (FixtureMaterializationPlanReviewDecision.HOLD,FixtureMaterializationPlanReviewDecision.REJECT):
            resources,sd,ledger,book,plan=plan_source();docket=SyntheticActivationDryRunFixtureMaterializationPlanReviewDocket()
            docket.submit(book,plan.plan_id,submitted_at=NOW);review(docket,plan,decision)
            with self.assertRaises(GovernanceRejected):docket.ready_source(plan.plan_id)
            close_sources(resources,sd,ledger)
    def test_type_time_and_review_metadata_fail_closed(self):
        resources,sd,ledger,book,plan=plan_source();docket=SyntheticActivationDryRunFixtureMaterializationPlanReviewDocket()
        with self.assertRaises(GovernanceRejected):docket.submit(object(),plan.plan_id,submitted_at=NOW)
        for value in (NOW.replace(tzinfo=None),NOW-timedelta(seconds=1)):
            with self.assertRaises(GovernanceRejected):docket.submit(book,plan.plan_id,submitted_at=value)
        docket.submit(book,plan.plan_id,submitted_at=NOW)
        with self.assertRaises(GovernanceRejected):review(docket,plan,reviewed_at=NOW.replace(tzinfo=None))
        with self.assertRaises(GovernanceRejected):review(docket,plan,reviewed_at=NOW-timedelta(seconds=1))
        close_sources(resources,sd,ledger)
    def test_replay_concurrency_and_final_review_are_immutable(self):
        resources,sd,ledger,book,plan=plan_source();docket=SyntheticActivationDryRunFixtureMaterializationPlanReviewDocket()
        with ThreadPoolExecutor(max_workers=4) as pool:items=list(pool.map(lambda _:docket.submit(book,plan.plan_id,submitted_at=NOW),range(8)))
        self.assertTrue(all(i is items[0] for i in items));self.assertEqual(len(docket.records),1)
        first=review(docket,plan);self.assertIs(review(docket,plan),first)
        with self.assertRaises(GovernanceRejected):review(docket,plan,FixtureMaterializationPlanReviewDecision.HOLD)
        close_sources(resources,sd,ledger)
    def test_submission_and_review_tampering_are_detected(self):
        resources,sd,ledger,book,plan=plan_source();docket=SyntheticActivationDryRunFixtureMaterializationPlanReviewDocket();item=docket.submit(book,plan.plan_id,submitted_at=NOW)
        object.__setattr__(item,"submitted_at",NOW+timedelta(seconds=1));self.assertFalse(docket.verify_chain());close_sources(resources,sd,ledger)
        resources,sd,ledger,book,plan=plan_source();docket=SyntheticActivationDryRunFixtureMaterializationPlanReviewDocket();docket.submit(book,plan.plan_id,submitted_at=NOW);item=review(docket,plan)
        object.__setattr__(item,"findings_digest","f"*64);self.assertFalse(docket.verify_chain());close_sources(resources,sd,ledger)
    def test_rehashed_plan_and_nested_lineage_tampering_detected(self):
        for field,value in (("plan_id","synthetic:activation-dry-run-fixture-materialization-plan:"+"f"*32),("artifact_descriptor_digest","f"*64),
            ("synthetic_only",False),("fixture_content_present",True),("filesystem_written",True)):
            resources,sd,ledger,book,plan=plan_source();object.__setattr__(plan,field,value);object.__setattr__(plan,"plan_digest",canonical_digest(plan.digest_value()))
            with self.assertRaises(GovernanceRejected):SyntheticActivationDryRunFixtureMaterializationPlanReviewDocket().submit(book,plan.plan_id,submitted_at=NOW)
            close_sources(resources,sd,ledger)
        resources,sd,ledger,book,plan=plan_source();object.__setattr__(plan.source_review,"findings_digest","f"*64)
        with self.assertRaises(GovernanceRejected):SyntheticActivationDryRunFixtureMaterializationPlanReviewDocket().submit(book,plan.plan_id,submitted_at=NOW)
        close_sources(resources,sd,ledger)
    def test_source_change_discards_submission(self):
        resources,sd,ledger,book,plan=plan_source();docket=SyntheticActivationDryRunFixtureMaterializationPlanReviewDocket();original=book.evidence;calls=0
        def changing():
            nonlocal calls;calls+=1;v=original();return v if calls==1 else {**v,"report_digest":"f"*64}
        book.evidence=changing
        with self.assertRaises(GovernanceRejected):docket.submit(book,plan.plan_id,submitted_at=NOW)
        self.assertEqual(docket.records,());close_sources(resources,sd,ledger)
    def test_evidence_caps_authority(self):
        resources,sd,ledger,book,plan=plan_source();docket=SyntheticActivationDryRunFixtureMaterializationPlanReviewDocket()
        docket.submit(book,plan.plan_id,submitted_at=NOW);review(docket,plan);e=docket.evidence()
        self.assertEqual(e["maximum_state"],FIXTURE_MATERIALIZATION_PLAN_REVIEW_MAXIMUM_STATE);self.assertTrue(e["review_chain_valid"])
        for key in e:
            if key.endswith("_present") or key.endswith("_allowed") or key.endswith("_executed") or key.endswith("_used"):self.assertFalse(e[key])
        close_sources(resources,sd,ledger)

if __name__=="__main__":unittest.main()
