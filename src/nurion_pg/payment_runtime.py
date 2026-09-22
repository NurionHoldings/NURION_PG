"""Durable provider-operation worker orchestration."""
from __future__ import annotations
from nurion_pg.providers import ProviderDisposition,ProviderExecutor

class ProviderCallbackBoundary:
 def __init__(self,repository):self.repository=repository
 def bind(self,merchant_id:str,operation_id:str,payment_key:str,order_id:str,amount:int,principal_id:str,roles:set[str])->None:
  if "payment_operator" not in roles:raise PermissionError("payment operator role required")
  self.repository.bind_provider_payment_key(merchant_id,operation_id,payment_key,order_id,amount,principal_id=principal_id)

class PaymentOperationWorker:
 def __init__(self,repository,provider,worker_id:str):self.repository=repository;self.executor=ProviderExecutor(repository,provider);self.worker_id=worker_id
 def run_once(self,limit:int=20)->dict[str,int]:
  report={"claimed":0,"completed":0,"deferred":0}
  for merchant_id,operation_id in self.repository.claim_provider_operations(self.worker_id,limit):
   report["claimed"]+=1
   try:
    result,intent=(self.executor.reconcile(merchant_id,operation_id) if self.repository.reconciliation_required(merchant_id,operation_id) else self.executor.execute(merchant_id,operation_id))
    if intent is not None:report["completed"]+=1
    elif result.disposition in {ProviderDisposition.UNKNOWN,ProviderDisposition.RETRYABLE}:self.repository.defer_provider_operation(merchant_id,operation_id,self.worker_id,result.code or "UNRESOLVED");report["deferred"]+=1
   except Exception:
    self.repository.defer_provider_operation(merchant_id,operation_id,self.worker_id,"WORKER_FAILURE");report["deferred"]+=1
  return report
