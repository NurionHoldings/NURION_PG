"""Toss Payments Core API adapter; transport is injected for offline testing."""
from __future__ import annotations

import base64,json,random,time
from dataclasses import dataclass
from typing import Callable
from urllib.error import HTTPError,URLError
from urllib.parse import quote,urlsplit
from urllib.request import Request,urlopen

from nurion_pg.payments import PaymentCommand
from nurion_pg.providers import CircuitBreaker,ProviderCommand,ProviderDisposition,ProviderResult

SAFE_CODES={"ALREADY_PROCESSED_PAYMENT","NOT_FOUND_PAYMENT","REJECT_CARD_PAYMENT","INVALID_REQUEST","NOT_SUPPORTED_METHOD","EXCEED_MAX_CARD_INSTALLMENT_PLAN"}
DECLINED_HTTP={400,401,403,404,409,422}

@dataclass(frozen=True)
class HttpResponse:
    status:int; body:bytes

Transport=Callable[[str,str,dict[str,str],bytes|None,float],HttpResponse]

def urllib_transport(method:str,url:str,headers:dict[str,str],body:bytes|None,timeout:float)->HttpResponse:
    try:
        with urlopen(Request(url,data=body,headers=headers,method=method),timeout=timeout) as response:return HttpResponse(response.status,response.read())
    except HTTPError as exc:return HttpResponse(exc.code,exc.read())


def redact(value:str)->str:
    """Safe diagnostic value; credentials and payment keys never survive."""
    if not value:return value
    return value[:2]+"***"+value[-2:] if len(value)>4 else "***"


class TossPaymentsAdapter:
    name="toss_payments"
    def __init__(self,secret_key:str,*,base_url:str="https://api.tosspayments.com",transport:Transport=urllib_transport,timeout:float=5,retries:int=2,breaker:CircuitBreaker|None=None,sleep=time.sleep)->None:
        endpoint=urlsplit(base_url);official=endpoint.scheme=="https" and endpoint.hostname=="api.tosspayments.com";loopback=endpoint.scheme in {"http","https"} and endpoint.hostname in {"127.0.0.1","localhost"}
        if not secret_key.startswith("test_sk_") or not (official or loopback) or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment or endpoint.path not in {"","/"}:raise ValueError("only Toss test secrets and official or loopback endpoints are allowed")
        self._secret=secret_key;self.base=base_url.rstrip("/");self.transport=transport;self.timeout=timeout;self.retries=retries;self.breaker=breaker or CircuitBreaker();self.sleep=sleep
    @classmethod
    def from_test_environment(cls,env:dict[str,str],**kwargs):
        if env.get("NURION_TOSS_TEST_EXECUTION")!="enabled":raise ValueError("Toss test execution is disabled")
        secret=env.get("TOSS_TEST_SECRET_KEY","");base=env.get("TOSS_TEST_BASE_URL","")
        if not base:raise ValueError("Toss test base URL is required")
        return cls(secret,base_url=base,**kwargs)
    def _headers(self,operation_id:str|None)->dict[str,str]:
        auth=base64.b64encode((self._secret+":").encode()).decode()
        headers={"Authorization":"Basic "+auth,"Content-Type":"application/json","User-Agent":"nurion-pg/1"}
        if operation_id:headers["Idempotency-Key"]=operation_id
        return headers
    def _call(self,method:str,path:str,operation_id:str|None,payload:dict|None,success_statuses:set[str])->ProviderResult:
        self.breaker.allow();body=json.dumps(payload,separators=(",",":"),ensure_ascii=False).encode() if payload is not None else None
        for attempt in range(self.retries+1):
            try:r=self.transport(method,self.base+path,self._headers(operation_id),body,self.timeout)
            except (TimeoutError,URLError,OSError):
                if attempt<self.retries:self.sleep(min(.1*(2**attempt)+random.random()*.02,.5));continue
                self.breaker.failure();return ProviderResult(ProviderDisposition.UNKNOWN,code="TRANSPORT_UNKNOWN",message="Provider outcome requires reconciliation")
            try:value=json.loads(r.body.decode()) if r.body else {}
            except (UnicodeDecodeError,json.JSONDecodeError):value={}
            if 200<=r.status<300:
                self.breaker.success();status=value.get("status");disp=ProviderDisposition.SUCCEEDED if status in success_statuses else ProviderDisposition.UNKNOWN
                total=value.get("totalAmount");total=total if isinstance(total,int) and not isinstance(total,bool) else None
                settled=status=="DONE"
                return ProviderResult(disp,status,value.get("paymentKey"),value.get("orderId"),total,settled,raw_status=r.status)
            code=value.get("code") if value.get("code") in SAFE_CODES else "PROVIDER_REJECTED" if r.status in DECLINED_HTTP else "PROVIDER_UNAVAILABLE"
            message="Provider rejected the request" if r.status in DECLINED_HTTP else "Provider is temporarily unavailable"
            if r.status in {429,500,502,503,504} and attempt<self.retries:self.sleep(min(.1*(2**attempt)+random.random()*.02,.5));continue
            if r.status not in DECLINED_HTTP:self.breaker.failure()
            disposition=ProviderDisposition.UNKNOWN if code=="ALREADY_PROCESSED_PAYMENT" else ProviderDisposition.DECLINED if r.status in DECLINED_HTTP else ProviderDisposition.RETRYABLE
            return ProviderResult(disposition,code=code,message=message,raw_status=r.status)
        raise AssertionError("unreachable")
    def execute(self,c:ProviderCommand)->ProviderResult:
        if c.command==PaymentCommand.AUTHORIZE:
            return self._call("POST","/v1/payments/confirm",c.operation_id,{"paymentKey":c.payment_key,"orderId":c.order_id,"amount":c.amount},{"DONE"})
        if c.command==PaymentCommand.CAPTURE:
            return ProviderResult(ProviderDisposition.DECLINED,code="COMMAND_NOT_SUPPORTED",message="Toss Core API does not expose a separate capture command")
        if not c.payment_key:return ProviderResult(ProviderDisposition.UNKNOWN,code="PAYMENT_KEY_REQUIRED",message="Reconciliation is required")
        reason=(c.reason or "requested by merchant")[:200]
        payload={"cancelReason":reason}
        if c.command==PaymentCommand.REFUND and c.amount is not None:payload["cancelAmount"]=c.amount
        return self._call("POST",f"/v1/payments/{quote(c.payment_key,safe='')}/cancel",c.operation_id,payload,{"CANCELED","PARTIAL_CANCELED"})
    def lookup(self,payment_key:str)->ProviderResult:return self._call("GET",f"/v1/payments/{quote(payment_key,safe='')}",None,None,{"DONE","CANCELED","PARTIAL_CANCELED"})


class TossWebhookBoundary:
    """Webhook is evidence only; reconciliation must authenticate and apply it."""
    ALLOWED={"paymentKey","orderId","status","totalAmount","balanceAmount","requestedAt","approvedAt"}
    @classmethod
    def sanitize(cls,payload:dict)->dict:return {k:payload[k] for k in cls.ALLOWED if k in payload}
