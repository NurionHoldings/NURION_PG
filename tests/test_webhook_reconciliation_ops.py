import json,unittest
from nurion_pg.payments import PaymentCommand
from nurion_pg.providers import ProviderDisposition,ProviderResult
from nurion_pg.webhook_reconciliation import TossWebhookVerifier,WebhookEvidence,WebhookReconciler

RAW=json.dumps({"eventType":"PAYMENT_STATUS_CHANGED","data":{"paymentKey":"pk-1","orderId":"order-1","status":"DONE","totalAmount":1000,"card":{"number":"secret"}}},separators=(",",":")).encode()
class Store:
 def __init__(self,op=("op-1","pi-1","order-1",1000,PaymentCommand.AUTHORIZE)):self.op=op;self.rows={};self.resolved=[];self.quarantined=[]
 def ingest(self,e,safe):
  key=(e.provider,e.event_key)
  if key in self.rows:return self.rows[key][0],True
  self.rows[key]=(f"in-{len(self.rows)+1}",e,safe);return self.rows[key][0],False
 def pending_operation(self,*_):return self.op
 def resolve(self,*args):self.resolved.append(args)
 def quarantine(self,*args):self.quarantined.append(args)
class Provider:
 name="toss_payments"
 def __init__(self,result):self.result=result;self.lookups=[]
 def lookup(self,key):self.lookups.append(key);return self.result

class WebhookOpsTests(unittest.TestCase):
 def test_raw_hash_dedupe_and_sensitive_data_allowlist(self):
  store=Store();svc=WebhookReconciler(store,Provider(None));first,replay=svc.accept("m1",{},RAW);second,replayed=svc.accept("m1",{},RAW)
  self.assertEqual(first,second);self.assertFalse(replay);self.assertTrue(replayed);safe=next(iter(store.rows.values()))[2];self.assertNotIn("card",safe)
 def test_untrusted_webhook_is_verified_by_provider_lookup(self):
  e,_=TossWebhookVerifier().normalize("m1",{},RAW);store=Store();result=ProviderResult(ProviderDisposition.SUCCEEDED,"DONE","pk-1","order-1",1000,True)
  self.assertEqual(WebhookReconciler(store,Provider(result)).reconcile("in-1",e),"resolved");self.assertEqual(len(store.resolved),1)
 def test_out_of_order_payload_does_not_override_provider_truth(self):
  late=json.dumps({"eventType":"PAYMENT_CANCELED","data":{"paymentKey":"pk-1","orderId":"order-1","status":"CANCELED"}}).encode();e,_=TossWebhookVerifier().normalize("m1",{},late)
  result=ProviderResult(ProviderDisposition.SUCCEEDED,"DONE","pk-1","order-1",1000,True);store=Store()
  self.assertEqual(WebhookReconciler(store,Provider(result)).reconcile("in-1",e),"resolved")
 def test_provider_status_must_match_pending_command(self):
  e,_=TossWebhookVerifier().normalize("m1",{},RAW);store=Store();result=ProviderResult(ProviderDisposition.SUCCEEDED,"CANCELED","pk-1","order-1",1000,False)
  self.assertEqual(WebhookReconciler(store,Provider(result)).reconcile("in-1",e),"quarantined");self.assertEqual(store.quarantined[0][2],"PROVIDER_STATUS_MISMATCH")
 def test_mismatch_unknown_and_unmatched_are_quarantined(self):
  e,_=TossWebhookVerifier().normalize("m1",{},RAW)
  for store,result in ((Store(None),ProviderResult(ProviderDisposition.SUCCEEDED,"DONE","pk-1","order-1",1000,True)),(Store(),ProviderResult(ProviderDisposition.UNKNOWN,code="TIMEOUT")),(Store(),ProviderResult(ProviderDisposition.SUCCEEDED,"DONE","other","order-1",1000,True))):
   self.assertEqual(WebhookReconciler(store,Provider(result)).reconcile("in",e),"quarantined");self.assertTrue(store.quarantined)
 def test_rejects_unknown_event_and_oversize(self):
  with self.assertRaises(ValueError):TossWebhookVerifier().normalize("m1",{},b'{}')
  with self.assertRaises(ValueError):TossWebhookVerifier().normalize("m1",{},b'x'*65537)

if __name__=="__main__":unittest.main()
