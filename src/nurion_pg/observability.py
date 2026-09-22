"""Low-cardinality operational telemetry contract."""
from __future__ import annotations
import json,re,time
from hashlib import sha256
SECRET=re.compile(r"(?i)(authorization|api[_-]?key|secret|password|paymentkey)")
METRICS=("http_request_duration_seconds","http_requests_total","http_request_errors_total","payment_operation_queue_depth","payment_operation_lease_expired_total","payment_operation_deadletter_total","webhook_inbox_depth","webhook_quarantine_total","provider_request_duration_seconds","provider_circuit_open","provider_unknown_total","outbox_oldest_unpublished_seconds","ledger_imbalance","settlement_hold_total","payout_pending_total","db_pool_in_use","migration_version","backup_restore_age_seconds")
class MetricsRegistry:
 def __init__(self):self._values={name:0.0 for name in METRICS}
 def set(self,name:str,value:float)->None:
  if name not in self._values:raise KeyError(name)
  self._values[name]=float(value)
 def increment(self,name:str,value:float=1)->None:self.set(name,self._values[name]+value)
 def render(self)->str:return "".join(f"# TYPE {name} gauge\n{name} {self._values[name]}\n" for name in METRICS)
def _redact(value):
 if isinstance(value,dict):return {k:("[REDACTED]" if SECRET.search(str(k)) else _redact(v)) for k,v in value.items()}
 if isinstance(value,list):return [_redact(v) for v in value]
 if isinstance(value,tuple):return tuple(_redact(v) for v in value)
 return value
def redact_fields(value:dict)->dict:return _redact(value)
def structured_log(event:str,*,correlation_id:str,merchant_id:str|None=None,**fields)->str:
 safe=redact_fields(fields);merchant_ref=sha256(merchant_id.encode()).hexdigest()[:16] if merchant_id else None;safe.update({"event":event,"correlation_id":correlation_id,"merchant_ref":merchant_ref,"timestamp_ms":int(time.time()*1000)});return json.dumps(safe,separators=(",",":"),sort_keys=True)
