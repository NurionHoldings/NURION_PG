import unittest
from scripts.validate_auth_rbac_closure import validate

class AuthRbacClosureTests(unittest.TestCase):
    def test_auth_rbac_scope_is_complete_and_fail_closed(self):
        evidence=validate();self.assertEqual(evidence["completion_percent"],100);self.assertEqual(evidence["criteria_passed"],evidence["criteria_total"]);self.assertFalse(evidence["plaintext_secret_storage_allowed"]);self.assertFalse(evidence["cross_tenant_access_allowed"])

if __name__=="__main__":unittest.main()
