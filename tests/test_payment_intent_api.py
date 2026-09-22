from dataclasses import replace
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from nurion_pg.api.app import create_app
from nurion_pg.api.auth import ApiKeyRecord,ApiKeyRegistry,Role,secret_digest
from nurion_pg.api.settings import Settings
from nurion_pg.payments import PaymentCommand,PaymentIntent,PaymentProblem,PaymentService,PaymentStatus,validate_command


class MemoryPayments:
    def __init__(self):self.intents={};self.receipts={}
    def create(self,merchant_id,amount,currency,key,digest,external_reference,metadata):
        receipt=self.receipts.get((merchant_id,key))
        if receipt:
            if receipt[0]!=("create",digest):raise PaymentProblem(409,"IDEMPOTENCY_CONFLICT","conflict")
            return receipt[1],True
        intent=PaymentIntent(str(uuid4()),merchant_id,amount,currency,PaymentStatus.REQUIRES_AUTHORIZATION,0,0,0,1,external_reference,metadata)
        self.intents[(merchant_id,intent.payment_intent_id)]=intent;self.receipts[(merchant_id,key)]=(("create",digest),intent);return intent,False
    def get(self,merchant_id,payment_intent_id):return self.intents.get((merchant_id,payment_intent_id))
    def request(self,merchant_id,payment_intent_id,command,amount,expected_version,key,digest):
        receipt=self.receipts.get((merchant_id,key))
        if receipt:
            if receipt[0]!=(command.value,digest):raise PaymentProblem(409,"IDEMPOTENCY_CONFLICT","conflict")
            return receipt[1],True
        intent=self.get(merchant_id,payment_intent_id)
        if not intent:raise PaymentProblem(404,"PAYMENT_INTENT_NOT_FOUND","missing")
        if intent.version!=expected_version:raise PaymentProblem(409,"VERSION_CONFLICT","changed")
        validate_command(intent,command,amount)
        pending={PaymentCommand.AUTHORIZE:PaymentStatus.AUTHORIZATION_PENDING,PaymentCommand.CAPTURE:PaymentStatus.CAPTURE_PENDING,PaymentCommand.CANCEL:PaymentStatus.CANCEL_PENDING,PaymentCommand.REFUND:PaymentStatus.REFUND_PENDING}[command]
        updated=replace(intent,status=pending,version=intent.version+1);self.intents[(merchant_id,payment_intent_id)]=updated;self.receipts[(merchant_id,key)]=((command.value,digest),updated);return updated,False


class PaymentIntentApiTests(unittest.TestCase):
    def setUp(self):
        records=[ApiKeyRecord("operator",secret_digest("secret"),"principal","merchant1",frozenset({Role.PAYMENT_OPERATOR})),ApiKeyRecord("auditor",secret_digest("audit"),"audit","merchant1",frozenset({Role.AUDITOR}))]
        self.repo=MemoryPayments();self.client=TestClient(create_app(Settings(environment="test"),ApiKeyRegistry(records),PaymentService(self.repo)))
        self.write={"x-api-key":"npg_operator_secret","idempotency-key":"create-1"};self.read={"x-api-key":"npg_auditor_audit"}

    def test_create_get_and_idempotent_replay(self):
        body={"amount":12500,"currency":"KRW","external_reference":"order-1","metadata":{"cart":"c1"}}
        created=self.client.post("/v1/merchants/merchant1/payment-intents",headers=self.write,json=body)
        self.assertEqual(created.status_code,201);self.assertEqual(created.headers["idempotent-replay"],"false")
        replay=self.client.post("/v1/merchants/merchant1/payment-intents",headers=self.write,json=body)
        self.assertEqual(replay.status_code,200);self.assertEqual(replay.json(),created.json());self.assertEqual(replay.headers["idempotent-replay"],"true")
        read=self.client.get(f"/v1/merchants/merchant1/payment-intents/{created.json()['payment_intent_id']}",headers=self.read)
        self.assertEqual(read.status_code,200);self.assertEqual(read.json()["amount"],12500)

    def test_authorization_request_is_pending_not_fake_success(self):
        created=self.client.post("/v1/merchants/merchant1/payment-intents",headers=self.write,json={"amount":1000,"currency":"KRW"}).json()
        headers={**self.write,"idempotency-key":"authorize-1"}
        response=self.client.post(f"/v1/merchants/merchant1/payment-intents/{created['payment_intent_id']}/authorize",headers=headers,json={"expected_version":1})
        self.assertEqual(response.status_code,202);self.assertEqual(response.json()["status"],"authorization_pending");self.assertEqual(response.json()["version"],2)
        replay=self.client.post(f"/v1/merchants/merchant1/payment-intents/{created['payment_intent_id']}/authorize",headers=headers,json={"expected_version":1})
        self.assertEqual(replay.status_code,200);self.assertEqual(replay.headers["idempotent-replay"],"true")

    def test_cross_tenant_write_and_auditor_write_are_denied(self):
        body={"amount":1000,"currency":"KRW"}
        self.assertEqual(self.client.post("/v1/merchants/other/payment-intents",headers=self.write,json=body).status_code,403)
        self.assertEqual(self.client.post("/v1/merchants/merchant1/payment-intents",headers={"x-api-key":"npg_auditor_audit","idempotency-key":"x"},json=body).status_code,403)

    def test_validation_conflict_and_version_guards(self):
        bad=self.client.post("/v1/merchants/merchant1/payment-intents",headers=self.write,json={"amount":0,"currency":"krw"})
        self.assertEqual(bad.status_code,422)
        created=self.client.post("/v1/merchants/merchant1/payment-intents",headers=self.write,json={"amount":1000,"currency":"KRW"}).json()
        conflict=self.client.post("/v1/merchants/merchant1/payment-intents",headers=self.write,json={"amount":2000,"currency":"KRW"})
        self.assertEqual(conflict.status_code,409);self.assertEqual(conflict.json()["error"]["code"],"IDEMPOTENCY_CONFLICT")
        stale=self.client.post(f"/v1/merchants/merchant1/payment-intents/{created['payment_intent_id']}/authorize",headers={**self.write,"idempotency-key":"stale"},json={"expected_version":9})
        self.assertEqual(stale.status_code,409);self.assertEqual(stale.json()["error"]["code"],"VERSION_CONFLICT")

    def test_missing_durable_payment_storage_is_unavailable(self):
        registry=ApiKeyRegistry([ApiKeyRecord("operator",secret_digest("secret"),"principal","merchant1",frozenset({Role.PAYMENT_OPERATOR}))])
        client=TestClient(create_app(Settings(environment="test"),registry))
        response=client.post("/v1/merchants/merchant1/payment-intents",headers=self.write,json={"amount":1000,"currency":"KRW"})
        self.assertEqual(response.status_code,503);self.assertEqual(response.json()["error"]["code"],"PAYMENT_STORAGE_UNAVAILABLE")


if __name__=="__main__":unittest.main()
