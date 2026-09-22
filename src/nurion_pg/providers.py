"""Provider-neutral payment execution boundary."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import time
from typing import Any, Protocol

from nurion_pg.payments import PaymentCommand, PaymentProblem


class ProviderDisposition(StrEnum):
    SUCCEEDED="succeeded"; DECLINED="declined"; RETRYABLE="retryable"; UNKNOWN="unknown"


@dataclass(frozen=True)
class ProviderCommand:
    operation_id:str; payment_intent_id:str; command:PaymentCommand; amount:int|None
    currency:str; order_id:str; payment_key:str|None=None; reason:str|None=None


@dataclass(frozen=True)
class ProviderResult:
    disposition:ProviderDisposition; provider_status:str|None=None; payment_key:str|None=None
    order_id:str|None=None; total_amount:int|None=None
    settled:bool=False; code:str|None=None; message:str|None=None; raw_status:int|None=None

    @property
    def terminal(self)->bool:return self.disposition in {ProviderDisposition.SUCCEEDED,ProviderDisposition.DECLINED}


class PaymentProvider(Protocol):
    name:str
    def execute(self,command:ProviderCommand)->ProviderResult:...
    def lookup(self,payment_key:str)->ProviderResult:...


class PaymentOperationStore(Protocol):
    def operation_for_provider(self,merchant_id:str,operation_id:str)->ProviderCommand:...
    def apply_provider_result(self,merchant_id:str,payment_intent_id:str,operation_id:str,succeeded:bool,*,provider_name:str|None=None,provider_payment_key:str|None=None,provider_status:str|None=None,provider_error_code:str|None=None,provider_settled:bool=False)->Any:...


class ProviderExecutor:
    """Only terminal provider results mutate the Payment Intent."""
    def __init__(self,repository:PaymentOperationStore,provider:PaymentProvider)->None:self.repository=repository;self.provider=provider

    def execute(self,merchant_id:str,operation_id:str)->tuple[ProviderResult,Any|None]:
        command=self.repository.operation_for_provider(merchant_id,operation_id)
        result=self.provider.execute(command)
        if not result.terminal:return result,None
        mismatch=self._mismatch(command,result)
        if mismatch:return mismatch,None
        intent=self.repository.apply_provider_result(merchant_id,command.payment_intent_id,operation_id,result.disposition==ProviderDisposition.SUCCEEDED,provider_name=self.provider.name,provider_payment_key=result.payment_key,provider_status=result.provider_status,provider_error_code=result.code,provider_settled=result.settled)
        return result,intent

    def reconcile(self,merchant_id:str,operation_id:str)->tuple[ProviderResult,Any|None]:
        command=self.repository.operation_for_provider(merchant_id,operation_id)
        if not command.payment_key:
            return ProviderResult(ProviderDisposition.UNKNOWN,code="PAYMENT_KEY_REQUIRED",message="Reconciliation requires a bound payment key"),None
        result=self.provider.lookup(command.payment_key)
        if not result.terminal:return result,None
        mismatch=self._mismatch(command,result)
        if mismatch:return mismatch,None
        intent=self.repository.apply_provider_result(merchant_id,command.payment_intent_id,operation_id,result.disposition==ProviderDisposition.SUCCEEDED,provider_name=self.provider.name,provider_payment_key=result.payment_key,provider_status=result.provider_status,provider_error_code=result.code,provider_settled=result.settled)
        return result,intent

    @staticmethod
    def _mismatch(command:ProviderCommand,result:ProviderResult)->ProviderResult|None:
        if result.disposition!=ProviderDisposition.SUCCEEDED:return None
        if not provider_status_matches(command.command,result.provider_status):
            return ProviderResult(ProviderDisposition.UNKNOWN,code="PROVIDER_STATUS_MISMATCH",message="Provider status requires reconciliation")
        if not result.payment_key or result.payment_key!=command.payment_key or result.order_id!=command.order_id:
            return ProviderResult(ProviderDisposition.UNKNOWN,code="PROVIDER_RESPONSE_MISMATCH",message="Provider identity requires reconciliation")
        if command.command==PaymentCommand.AUTHORIZE and result.total_amount!=command.amount:
            return ProviderResult(ProviderDisposition.UNKNOWN,code="PROVIDER_RESPONSE_MISMATCH",message="Provider amount requires reconciliation")
        return None


def provider_status_matches(command:PaymentCommand,status:str|None)->bool:
    expected={
        PaymentCommand.AUTHORIZE:{"DONE"},
        PaymentCommand.CAPTURE:set(),
        PaymentCommand.CANCEL:{"CANCELED"},
        PaymentCommand.REFUND:{"CANCELED","PARTIAL_CANCELED"},
    }
    return status in expected[command]


class CircuitBreaker:
    def __init__(self,failures:int=3,cooldown_seconds:float=30,clock=time.monotonic)->None:
        if failures<1 or cooldown_seconds<=0:raise ValueError("invalid circuit breaker")
        self.limit=failures;self.cooldown=cooldown_seconds;self.clock=clock;self.count=0;self.opened_at:float|None=None
    def allow(self)->None:
        if self.opened_at is None:return
        if self.clock()-self.opened_at>=self.cooldown:self.count=0;self.opened_at=None;return
        raise PaymentProblem(503,"PROVIDER_CIRCUIT_OPEN","Payment provider is temporarily unavailable")
    def success(self)->None:self.count=0;self.opened_at=None
    def failure(self)->None:
        self.count+=1
        if self.count>=self.limit:self.opened_at=self.clock()
