import unittest
from scripts.validate_webhook_reconciliation_closure import validate
class ClosureTests(unittest.TestCase):
 def test_closure(self):self.assertEqual(validate()["criteria_passed"],15)
if __name__=="__main__":unittest.main()
