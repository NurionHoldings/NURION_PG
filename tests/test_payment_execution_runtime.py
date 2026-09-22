import json,threading,unittest
from dataclasses import replace
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from nurion_pg.payment_runtime import PaymentOperationWorker,ProviderCallbackBoundary
from nurion_pg.payments import PaymentCommand
from nurion_pg.providers import ProviderCommand,ProviderDisposition,ProviderResult
from nurion_pg.toss_provider import TossPaymentsAdapter

class Emulator(BaseHTTPRequestHandler):
 payments={};calls=[]
 def log_message(self,*_):pass
 def _body(self):return json.loads(self.rfile.read(int(self.headers.get("content-length","0"))) or b'{}')
 def _send(self,value,status=200):data=json.dumps(value).encode();self.send_response(status);self.send_header("content-type","application/json");self.send_header("content-length",str(len(data)));self.end_headers();self.wfile.write(data)
 def do_POST(self):
  body=self._body();self.calls.append((self.path,self.headers.get("Idempotency-Key"),body))
  if self.path=="/v1/payments/confirm":
   value={"paymentKey":body["paymentKey"],"orderId":body["orderId"],"totalAmount":body["amount"],"balanceAmount":body["amount"],"status":"DONE"};self.payments[body["paymentKey"]]=value;self._send(value);return
  key=self.path.split("/")[3];value=self.payments[key];cancel=body.get("cancelAmount",value["balanceAmount"]);value["balanceAmount"]-=cancel;value["status"]="CANCELED" if value["balanceAmount"]==0 else "PARTIAL_CANCELED";self._send(value)
 def do_GET(self):key=self.path.split("/")[3];self._send(self.payments[key])

class Repo:
 def __init__(self,command,result_unknown=False):self.command=command;self.queue=[("m1",command.operation_id)];self.applied=[];self.deferred=[];self.reconcile=False;self.bound=[]
 def claim_provider_operations(self,*_):q=self.queue;self.queue=[];return q
 def operation_for_provider(self,*_):return self.command
 def reconciliation_required(self,*_):return self.reconcile
 def defer_provider_operation(self,*args):self.deferred.append(args);self.reconcile=True
 def apply_provider_result(self,*args,**kw):self.applied.append((args,kw));return "intent"
 def bind_provider_payment_key(self,*args,**kwargs):self.bound.append((args,kwargs))

class Provider:
 name="test"
 def __init__(self):self.execute_count=0;self.lookup_count=0
 def execute(self,c):self.execute_count+=1;return ProviderResult(ProviderDisposition.UNKNOWN,code="TRANSPORT_UNKNOWN")
 def lookup(self,key):self.lookup_count+=1;return ProviderResult(ProviderDisposition.SUCCEEDED,"DONE",key,"order-1",1000,True)

class RuntimeTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.server=ThreadingHTTPServer(("127.0.0.1",0),Emulator);cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start();cls.adapter=TossPaymentsAdapter("test_sk_local",base_url=f"http://127.0.0.1:{cls.server.server_port}",retries=0)
 @classmethod
 def tearDownClass(cls):cls.server.shutdown();cls.server.server_close()
 def test_actual_http_roundtrip_confirm_partial_and_full_refund(self):
  command=ProviderCommand("op-confirm","pi",PaymentCommand.AUTHORIZE,1000,"KRW","order-e2e","pk-e2e");done=self.adapter.execute(command);self.assertEqual((done.disposition,done.provider_status,done.settled),(ProviderDisposition.SUCCEEDED,"DONE",True))
  partial=self.adapter.execute(replace(command,operation_id="op-r1",command=PaymentCommand.REFUND,amount=400));self.assertEqual(partial.provider_status,"PARTIAL_CANCELED")
  full=self.adapter.execute(replace(command,operation_id="op-r2",command=PaymentCommand.REFUND,amount=600));self.assertEqual(full.provider_status,"CANCELED");self.assertEqual(self.adapter.lookup("pk-e2e").provider_status,"CANCELED")
  cancel_source=replace(command,operation_id="op-confirm-cancel",order_id="order-cancel",payment_key="pk-cancel");self.assertEqual(self.adapter.execute(cancel_source).provider_status,"DONE")
  canceled=self.adapter.execute(replace(cancel_source,operation_id="op-cancel",command=PaymentCommand.CANCEL,amount=None));self.assertEqual(canceled.provider_status,"CANCELED")
  self.assertEqual(len({x[1] for x in Emulator.calls if x[1]}),5)
 def test_unknown_is_reconciliation_first_after_restart(self):
  command=ProviderCommand("op","pi",PaymentCommand.AUTHORIZE,1000,"KRW","order-1","pk");repo=Repo(command);provider=Provider();first=PaymentOperationWorker(repo,provider,"w1").run_once();self.assertEqual(first["deferred"],1)
  repo.queue=[("m1","op")];second=PaymentOperationWorker(repo,provider,"w2").run_once();self.assertEqual(second["completed"],1);self.assertEqual((provider.execute_count,provider.lookup_count),(1,1))
 def test_callback_rbac_and_binding(self):
  repo=Repo(ProviderCommand("op","pi",PaymentCommand.AUTHORIZE,1000,"KRW","order-1"));boundary=ProviderCallbackBoundary(repo)
  with self.assertRaises(PermissionError):boundary.bind("m1","op","pk","order-1",1000,"p",set())
  boundary.bind("m1","op","pk","order-1",1000,"p",{"payment_operator"});self.assertEqual(repo.bound[0][0][0:5],("m1","op","pk","order-1",1000));self.assertEqual(repo.bound[0][1]["principal_id"],"p")
 def test_environment_configuration_is_fail_closed(self):
  with self.assertRaises(ValueError):TossPaymentsAdapter.from_test_environment({})
  adapter=TossPaymentsAdapter.from_test_environment({"NURION_TOSS_TEST_EXECUTION":"enabled","TOSS_TEST_SECRET_KEY":"test_sk_local","TOSS_TEST_BASE_URL":f"http://127.0.0.1:{self.server.server_port}"},retries=0);self.assertTrue(adapter.base.startswith("http://127.0.0.1:"))
  with self.assertRaises(ValueError):TossPaymentsAdapter("test_sk_local",base_url="https://attacker.example")

if __name__=="__main__":unittest.main()
