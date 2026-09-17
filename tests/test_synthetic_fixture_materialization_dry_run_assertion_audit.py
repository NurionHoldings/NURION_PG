from __future__ import annotations
import unittest
from datetime import timedelta
from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_fixture_materialization_dry_run_assertion_audit import AUDIT_STATE,audit_assertion,evidence
from nurion_pg.synthetic_fixture_materialization_dry_run_assertions import SyntheticFixtureMaterializationDryRunAssertionBook
from tests.test_patch_draft_limited_promotion_reconfirmation_intake import NOW
from tests.test_synthetic_fixture_materialization_dry_run_assertions import reviewed_expectation
from tests.test_synthetic_patch_draft_limited_promotion_activation_drafts import close_sources
class AssertionAuditTests(unittest.TestCase):
    def test_read_only_audit_and_authority(self):
        resources,sd,ledger,docket,review=reviewed_expectation();book=SyntheticFixtureMaterializationDryRunAssertionBook();item=book.draft_from_review(docket,review.expectation.expectation_id,drafted_at=NOW)
        audit=audit_assertion(book,item,audited_at=NOW);self.assertEqual(audit.state,AUDIT_STATE);e=evidence(audit)
        for key in e:
            if key.endswith("_present") or key.endswith("_allowed") or key.endswith("_executed") or key.endswith("_used"):self.assertFalse(e[key])
        close_sources(resources,sd,ledger)
    def test_invalid_chain_fails_closed(self):
        resources,sd,ledger,docket,review=reviewed_expectation();book=SyntheticFixtureMaterializationDryRunAssertionBook();item=book.draft_from_review(docket,review.expectation.expectation_id,drafted_at=NOW)
        object.__setattr__(item,"evaluation_present",True)
        with self.assertRaises(GovernanceRejected):audit_assertion(book,item,audited_at=NOW)
        object.__setattr__(item,"evaluation_present",False)
        with self.assertRaises(GovernanceRejected):audit_assertion(book,item,audited_at=NOW-timedelta(seconds=1))
        close_sources(resources,sd,ledger)
if __name__=="__main__":unittest.main()
