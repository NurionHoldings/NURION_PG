import base64,json,unittest
from dataclasses import replace
from nurion_pg.payments import PaymentCommand,PaymentProblem
from nurion_pg.providers import CircuitBreaker,ProviderCommand,ProviderDisposition,ProviderExecutor
from nurion_pg.toss_provider import HttpResponse,TossPaymentsAdapter,TossWebhookBoundary,redact

CMD=ProviderCommand("op-1","pi-1",PaymentCommand.AUTHORIZE,1500,"KRW","order-1","pay-key")

class FakeTransport:
    def __init__(self,*responses):self.responses=list(responses);self.calls=[]
    def __call__(self,*args):self.calls.append(args);value=self.responses.pop(0);return value() if callable(value) else value

class Repo:
    def __init__(self):self.applied=[]
    def operation_for_provider(self,*_):return CMD
    def apply_provider_result(self,*a,**kw):self.applied.append((a,kw));return "intent"

class TossProviderTests(unittest.TestCase):
    def adapter(self,transport,**kw):return TossPaymentsAdapter("test_sk_secret",base_url="http://127.0.0.1:9999",transport=transport,sleep=lambda _:None,**kw)
    def test_confirm_uses_basic_auth_idempotency_and_allowlisted_result(self):
        command=replace(CMD,payment_key="pk-1")
        t=FakeTransport(HttpResponse(200,json.dumps({"paymentKey":"pk-1","orderId":"order-1","totalAmount":1500,"status":"DONE","card":{"number":"secret"}}).encode()))
        result=self.adapter(t).execute(command);method,url,headers,body,timeout=t.calls[0]
        self.assertEqual((method,url),("POST","http://127.0.0.1:9999/v1/payments/confirm"));self.assertEqual(base64.b64decode(headers["Authorization"].split()[1]).decode(),"test_sk_secret:");self.assertEqual(headers["Idempotency-Key"],"op-1")
        self.assertEqual((result.disposition,result.payment_key,result.order_id,result.total_amount,result.settled),(ProviderDisposition.SUCCEEDED,"pk-1","order-1",1500,True));self.assertNotIn("card",result.__dict__)
    def test_cancel_and_refund_contract(self):
        t=FakeTransport(HttpResponse(200,b'{"status":"CANCELED","paymentKey":"pk","orderId":"order-1","totalAmount":1500}'))
        self.adapter(t).execute(replace(CMD,command=PaymentCommand.REFUND,amount=500));payload=json.loads(t.calls[0][3]);self.assertEqual(payload["cancelAmount"],500);self.assertIn("cancelReason",payload)
        unsupported=self.adapter(FakeTransport()).execute(replace(CMD,command=PaymentCommand.CAPTURE));self.assertEqual((unsupported.disposition,unsupported.code),(ProviderDisposition.DECLINED,"COMMAND_NOT_SUPPORTED"))
    def test_retry_then_success_and_unknown_transport_outcome(self):
        t=FakeTransport(HttpResponse(503,b'{}'),HttpResponse(200,b'{"status":"DONE","paymentKey":"pay-key","orderId":"order-1","totalAmount":1500}'));self.assertEqual(self.adapter(t,retries=1).execute(CMD).disposition,ProviderDisposition.SUCCEEDED)
        t=FakeTransport(lambda:(_ for _ in ()).throw(TimeoutError()));self.assertEqual(self.adapter(t,retries=0).execute(CMD).disposition,ProviderDisposition.UNKNOWN)
    def test_error_is_classified_without_leaking_body(self):
        t=FakeTransport(HttpResponse(400,b'{"code":"REJECT_CARD_PAYMENT","message":"card 1234"}'));r=self.adapter(t).execute(CMD);self.assertEqual((r.disposition,r.code,r.message),(ProviderDisposition.DECLINED,"REJECT_CARD_PAYMENT","Provider rejected the request"))
        self.assertNotIn("1234",repr(r));self.assertEqual(redact("secret-value"),"se***ue")
    def test_circuit_breaker_fails_closed(self):
        clock=[0.0];b=CircuitBreaker(1,10,lambda:clock[0]);b.failure()
        with self.assertRaises(PaymentProblem):b.allow()
        clock[0]=11;b.allow()
    def test_executor_only_applies_terminal_results(self):
        repo=Repo();provider=self.adapter(FakeTransport(HttpResponse(503,b'{}')),retries=0);result,intent=ProviderExecutor(repo,provider).execute("m1","op-1");self.assertIsNone(intent);self.assertFalse(repo.applied)
        repo=Repo();provider=self.adapter(FakeTransport(HttpResponse(200,b'{"status":"DONE","paymentKey":"pay-key","orderId":"order-1","totalAmount":1500}')));result,intent=ProviderExecutor(repo,provider).execute("m1","op-1");self.assertEqual(intent,"intent");self.assertTrue(repo.applied);self.assertTrue(repo.applied[0][1]["provider_settled"])
    def test_executor_rejects_identity_or_amount_mismatch(self):
        for body in (b'{"status":"DONE","paymentKey":"other","orderId":"order-1","totalAmount":1500}',b'{"status":"DONE","paymentKey":"pay-key","orderId":"wrong","totalAmount":1500}',b'{"status":"DONE","paymentKey":"pay-key","orderId":"order-1","totalAmount":999}'):
            repo=Repo();result,intent=ProviderExecutor(repo,self.adapter(FakeTransport(HttpResponse(200,body)))).execute("m1","op-1")
            self.assertEqual(result.code,"PROVIDER_RESPONSE_MISMATCH");self.assertIsNone(intent);self.assertFalse(repo.applied)
    def test_lookup_omits_idempotency_header(self):
        t=FakeTransport(HttpResponse(200,b'{"status":"DONE","paymentKey":"pay-key","orderId":"order-1","totalAmount":1500}'))
        self.adapter(t).lookup("pay-key");self.assertNotIn("Idempotency-Key",t.calls[0][2])
    def test_webhook_is_sanitized_evidence_not_command(self):
        self.assertEqual(TossWebhookBoundary.sanitize({"paymentKey":"pk","status":"DONE","card":{"number":"x"}}),{"paymentKey":"pk","status":"DONE"})

if __name__=="__main__":unittest.main()
