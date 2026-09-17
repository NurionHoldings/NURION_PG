from __future__ import annotations
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256
from nurion_pg.arkaon.governance import GovernanceRejected,canonical_digest
from nurion_pg.synthetic_activation_dry_run_fixture_materialization_specification_review import FIXTURE_MATERIALIZATION_SPECIFICATION_REVIEW_MAXIMUM_STATE,FixtureMaterializationSpecificationReviewDecision,FixtureMaterializationSpecificationReviewState,SyntheticActivationDryRunFixtureMaterializationSpecificationReviewDocket
from nurion_pg.synthetic_activation_dry_run_fixture_materialization_specifications import SyntheticActivationDryRunFixtureMaterializationSpecificationBook
from tests.test_patch_draft_limited_promotion_reconfirmation_intake import NOW
from tests.test_synthetic_activation_dry_run_fixture_materialization_specifications import reviewed_plan_source
from tests.test_synthetic_patch_draft_limited_promotion_activation_drafts import close_sources

def specification_source():
    resources,sd,ledger,docket,review=reviewed_plan_source();book=SyntheticActivationDryRunFixtureMaterializationSpecificationBook()
    specification=book.specify_from_review(docket,review.plan.plan_id,specified_at=NOW)
    return resources,sd,ledger,book,specification
def review(docket,specification,decision=FixtureMaterializationSpecificationReviewDecision.PASS,reviewed_at=NOW):
    return docket.record_eternian_review(specification.specification_id,
        review_id="synthetic:activation-dry-run-fixture-materialization-specification-review:draft",
        reviewer_id="synthetic:eternian-reviewer:activation-dry-run-fixture-materialization-specification:draft",
        decision=decision,findings_digest=sha256(b"fixture materialization specification independent review").hexdigest(),reviewed_at=reviewed_at)

class FixtureMaterializationSpecificationReviewTests(unittest.TestCase):
    def test_pass_is_ready_for_dry_run_plan_only(self):
        resources,sd,ledger,book,specification=specification_source();docket=SyntheticActivationDryRunFixtureMaterializationSpecificationReviewDocket()
        pending=docket.submit(book,specification.specification_id,submitted_at=NOW)
        self.assertEqual(pending.state,FixtureMaterializationSpecificationReviewState.PENDING_ETERNIAN_REVIEW)
        final=review(docket,specification);self.assertIs(docket.ready_source(specification.specification_id),final)
        self.assertEqual(final.state.value,FIXTURE_MATERIALIZATION_SPECIFICATION_REVIEW_MAXIMUM_STATE);close_sources(resources,sd,ledger)
    def test_hold_and_reject_are_not_ready(self):
        for decision in (FixtureMaterializationSpecificationReviewDecision.HOLD,FixtureMaterializationSpecificationReviewDecision.REJECT):
            resources,sd,ledger,book,specification=specification_source();docket=SyntheticActivationDryRunFixtureMaterializationSpecificationReviewDocket()
            docket.submit(book,specification.specification_id,submitted_at=NOW);review(docket,specification,decision)
            with self.assertRaises(GovernanceRejected):docket.ready_source(specification.specification_id)
            close_sources(resources,sd,ledger)
    def test_type_time_and_review_metadata_fail_closed(self):
        resources,sd,ledger,book,specification=specification_source();docket=SyntheticActivationDryRunFixtureMaterializationSpecificationReviewDocket()
        with self.assertRaises(GovernanceRejected):docket.submit(object(),specification.specification_id,submitted_at=NOW)
        for value in (NOW.replace(tzinfo=None),NOW-timedelta(seconds=1)):
            with self.assertRaises(GovernanceRejected):docket.submit(book,specification.specification_id,submitted_at=value)
        docket.submit(book,specification.specification_id,submitted_at=NOW)
        with self.assertRaises(GovernanceRejected):review(docket,specification,reviewed_at=NOW.replace(tzinfo=None))
        with self.assertRaises(GovernanceRejected):review(docket,specification,reviewed_at=NOW-timedelta(seconds=1))
        close_sources(resources,sd,ledger)
    def test_replay_concurrency_and_final_review_are_immutable(self):
        resources,sd,ledger,book,specification=specification_source();docket=SyntheticActivationDryRunFixtureMaterializationSpecificationReviewDocket()
        with ThreadPoolExecutor(max_workers=4) as pool:items=list(pool.map(lambda _:docket.submit(book,specification.specification_id,submitted_at=NOW),range(8)))
        self.assertTrue(all(i is items[0] for i in items));self.assertEqual(len(docket.records),1)
        first=review(docket,specification);self.assertIs(review(docket,specification),first)
        with self.assertRaises(GovernanceRejected):review(docket,specification,FixtureMaterializationSpecificationReviewDecision.HOLD)
        close_sources(resources,sd,ledger)
    def test_submission_review_and_fully_rehashed_metadata_tampering_detected(self):
        resources,sd,ledger,book,specification=specification_source();docket=SyntheticActivationDryRunFixtureMaterializationSpecificationReviewDocket()
        item=docket.submit(book,specification.specification_id,submitted_at=NOW);object.__setattr__(item,"submitted_at",NOW+timedelta(seconds=1))
        self.assertFalse(docket.verify_chain());close_sources(resources,sd,ledger)
        resources,sd,ledger,book,specification=specification_source();docket=SyntheticActivationDryRunFixtureMaterializationSpecificationReviewDocket()
        docket.submit(book,specification.specification_id,submitted_at=NOW);item=review(docket,specification)
        object.__setattr__(item,"reviewed_at",NOW-timedelta(seconds=1));object.__setattr__(item,"review_digest",canonical_digest(item.review_value()))
        self.assertFalse(docket.verify_chain());close_sources(resources,sd,ledger)
    def test_rehashed_specification_and_nested_lineage_tampering_detected(self):
        for field,value in (("specification_id","synthetic:activation-dry-run-fixture-materialization-specification:"+"f"*32),
            ("specification_descriptor_digest","f"*64),("synthetic_only",False),("fixture_content_present",True),
            ("fixture_bytes_present",True),("filesystem_path_present",True),("filesystem_written",True)):
            resources,sd,ledger,book,specification=specification_source();object.__setattr__(specification,field,value)
            object.__setattr__(specification,"specification_digest",canonical_digest(specification.digest_value()))
            with self.assertRaises(GovernanceRejected):SyntheticActivationDryRunFixtureMaterializationSpecificationReviewDocket().submit(
                book,specification.specification_id,submitted_at=NOW)
            close_sources(resources,sd,ledger)
        resources,sd,ledger,book,specification=specification_source();object.__setattr__(specification.source_review,"findings_digest","f"*64)
        with self.assertRaises(GovernanceRejected):SyntheticActivationDryRunFixtureMaterializationSpecificationReviewDocket().submit(
            book,specification.specification_id,submitted_at=NOW)
        close_sources(resources,sd,ledger)
    def test_source_change_discards_submission(self):
        resources,sd,ledger,book,specification=specification_source();docket=SyntheticActivationDryRunFixtureMaterializationSpecificationReviewDocket()
        original=book.evidence;calls=0
        def changing():
            nonlocal calls;calls+=1;v=original();return v if calls==1 else {**v,"report_digest":"f"*64}
        book.evidence=changing
        with self.assertRaises(GovernanceRejected):docket.submit(book,specification.specification_id,submitted_at=NOW)
        self.assertEqual(docket.records,());close_sources(resources,sd,ledger)
    def test_evidence_caps_authority(self):
        resources,sd,ledger,book,specification=specification_source();docket=SyntheticActivationDryRunFixtureMaterializationSpecificationReviewDocket()
        docket.submit(book,specification.specification_id,submitted_at=NOW);review(docket,specification);e=docket.evidence()
        self.assertEqual(e["maximum_state"],FIXTURE_MATERIALIZATION_SPECIFICATION_REVIEW_MAXIMUM_STATE);self.assertTrue(e["review_chain_valid"])
        for key in e:
            if key.endswith("_present") or key.endswith("_allowed") or key.endswith("_executed") or key.endswith("_used"):self.assertFalse(e[key])
        close_sources(resources,sd,ledger)

if __name__=="__main__":unittest.main()
