import unittest
from scripts.validate_test_payment_execution_closure import validate
class ClosureTests(unittest.TestCase):
 def test_closure(self):self.assertEqual(validate()["criteria_passed"],21)
if __name__=="__main__":unittest.main()
