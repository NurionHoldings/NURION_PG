import unittest

from nurion_pg.payments import PaymentCommand,PaymentIntent,PaymentProblem,PaymentStatus,validate_command


class PaymentDomainTests(unittest.TestCase):
    def intent(self,**changes):
        values=dict(payment_intent_id="p",merchant_id="m",amount=1000,currency="KRW",status=PaymentStatus.AUTHORIZED,authorized_amount=1000,captured_amount=0,refunded_amount=0,version=1)
        values.update(changes);return PaymentIntent(**values)

    def test_capture_and_refund_limits(self):
        self.assertEqual(validate_command(self.intent(),PaymentCommand.CAPTURE,None),1000)
        with self.assertRaises(PaymentProblem):validate_command(self.intent(),PaymentCommand.CAPTURE,1001)
        captured=self.intent(status=PaymentStatus.CAPTURED,captured_amount=1000,refunded_amount=300)
        self.assertEqual(validate_command(captured,PaymentCommand.REFUND,None),700)
        with self.assertRaises(PaymentProblem):validate_command(captured,PaymentCommand.REFUND,701)

    def test_commands_fail_closed_by_state(self):
        created=self.intent(status=PaymentStatus.REQUIRES_AUTHORIZATION,authorized_amount=0)
        validate_command(created,PaymentCommand.AUTHORIZE,None)
        for command in (PaymentCommand.CAPTURE,PaymentCommand.REFUND):
            with self.assertRaises(PaymentProblem):validate_command(created,command,None)


if __name__=="__main__":unittest.main()
