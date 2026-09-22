import unittest
from scripts.validate_ledger_settlement_closure import validate
class ClosureTests(unittest.TestCase):
 def test_closure(self):self.assertEqual(validate()["criteria_passed"],20)
if __name__=="__main__":unittest.main()
