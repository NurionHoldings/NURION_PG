"""Durable webhook evidence and provider-query reconciliation workflow."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any,Protocol

from nurion_pg.payments import PaymentCommand
from nurion_pg.providers import PaymentProvider,ProviderDisposition,provider_status_matches
from nurion_pg.toss_provider import TossWebhookBoundary

ALLOWED_EVENTS={"PAYMENT_STATUS_CHANGED","PAYMENT_CANCELED","PAYMENT_DEPOSITED"}
ALLOWED_STATUSES={"DONE","CANCELED","PARTIAL_CANCELED","ABORTED","EXPIRED"}

@dataclass(frozen=True)
class WebhookEvidence:
    merchant_id:str; provider:str; event_key:str; event_type:str; raw_sha256:str
    payment_key:str; order_id:str|None; provider_status:str; received_at:str|None=None

class WebhookStore(Protocol):
    def ingest(self,evidence:WebhookEvidence,sanitized:dict[str,Any])->tuple[str,bool]:...
    def pending_operation(self,merchant_id:str,payment_key:str)->tuple[str,str,str,int|None,PaymentCommand]|None:...
    def resolve(self,inbox_id:str,merchant_id:str,operation_id:str,payment_intent_id:str,result:Any)->None:...
    def quarantine(self,inbox_id:str,merchant_id:str,reason:str)->None:...

class TossWebhookVerifier:
    """Toss webhook has no assumed signature here; API lookup is authoritative proof."""
    def normalize(self,merchant_id:str,headers:dict[str,str],raw:bytes)->tuple[WebhookEvidence,dict[str,Any]]:
        if len(raw)>65536:raise ValueError("webhook body too large")
        try:value=json.loads(raw)
        except (UnicodeDecodeError,json.JSONDecodeError) as exc:raise ValueError("invalid webhook JSON") from exc
        event_type=value.get("eventType") or headers.get("x-toss-event-type")
        data=value.get("data") if isinstance(value.get("data"),dict) else value
        safe=TossWebhookBoundary.sanitize(data);status=safe.get("status");payment_key=safe.get("paymentKey")
        if event_type not in ALLOWED_EVENTS or status not in ALLOWED_STATUSES or not isinstance(payment_key,str) or not payment_key:raise ValueError("unsupported webhook event")
        digest=sha256(raw).hexdigest();event_key=headers.get("x-toss-webhook-id") or digest
        evidence=WebhookEvidence(merchant_id,"toss_payments",event_key,event_type,digest,payment_key,safe.get("orderId"),status)
        return evidence,safe

class WebhookReconciler:
    def __init__(self,store:WebhookStore,provider:PaymentProvider)->None:self.store=store;self.provider=provider
    def accept(self,merchant_id:str,headers:dict[str,str],raw:bytes)->tuple[str,bool]:
        evidence,safe=TossWebhookVerifier().normalize(merchant_id,{k.lower():v for k,v in headers.items()},raw)
        return self.store.ingest(evidence,safe)
    def reconcile(self,inbox_id:str,evidence:WebhookEvidence)->str:
        operation=self.store.pending_operation(evidence.merchant_id,evidence.payment_key)
        if operation is None:self.store.quarantine(inbox_id,evidence.merchant_id,"NO_MATCHING_PENDING_OPERATION");return "quarantined"
        result=self.provider.lookup(evidence.payment_key)
        if result.disposition not in {ProviderDisposition.SUCCEEDED,ProviderDisposition.DECLINED}:
            self.store.quarantine(inbox_id,evidence.merchant_id,"PROVIDER_OUTCOME_UNRESOLVED");return "quarantined"
        if result.payment_key!=evidence.payment_key or result.order_id!=operation[2] or (operation[3] is not None and result.total_amount!=operation[3]):
            self.store.quarantine(inbox_id,evidence.merchant_id,"PROVIDER_IDENTITY_MISMATCH");return "quarantined"
        if result.disposition==ProviderDisposition.SUCCEEDED and not provider_status_matches(operation[4],result.provider_status):
            self.store.quarantine(inbox_id,evidence.merchant_id,"PROVIDER_STATUS_MISMATCH");return "quarantined"
        self.store.resolve(inbox_id,evidence.merchant_id,operation[0],operation[1],result);return "resolved"
