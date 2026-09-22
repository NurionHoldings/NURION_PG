"""Payment Intent domain model and fail-closed command service."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from hashlib import sha256
import json
import re
from typing import Any, Protocol


CURRENCY = re.compile(r"^[A-Z]{3}$")
IDEMPOTENCY_KEY = re.compile(r"^[\x21-\x7e]{1,128}$")


class PaymentStatus(StrEnum):
    REQUIRES_AUTHORIZATION = "requires_authorization"
    AUTHORIZATION_PENDING = "authorization_pending"
    AUTHORIZED = "authorized"
    CAPTURE_PENDING = "capture_pending"
    PARTIALLY_CAPTURED = "partially_captured"
    CAPTURED = "captured"
    CANCEL_PENDING = "cancel_pending"
    CANCELED = "canceled"
    REFUND_PENDING = "refund_pending"
    PARTIALLY_REFUNDED = "partially_refunded"
    REFUNDED = "refunded"
    FAILED = "failed"


class PaymentCommand(StrEnum):
    AUTHORIZE = "authorize"
    CAPTURE = "capture"
    CANCEL = "cancel"
    REFUND = "refund"


@dataclass(frozen=True)
class PaymentIntent:
    payment_intent_id: str
    merchant_id: str
    amount: int
    currency: str
    status: PaymentStatus
    authorized_amount: int
    captured_amount: int
    refunded_amount: int
    version: int
    external_reference: str | None = None
    metadata: dict[str, Any] | None = None

    def public_view(self) -> dict[str, Any]:
        value=asdict(self);value["status"]=self.status.value;value["metadata"]=self.metadata or {};return value


class PaymentProblem(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code=status_code;self.code=code;self.message=message


class PaymentRepository(Protocol):
    def create(self, merchant_id:str, amount:int, currency:str, idempotency_key:str, request_digest:str, external_reference:str|None, metadata:dict[str,Any]) -> tuple[PaymentIntent,bool]:...
    def get(self, merchant_id:str, payment_intent_id:str) -> PaymentIntent|None:...
    def request(self, merchant_id:str, payment_intent_id:str, command:PaymentCommand, amount:int|None, expected_version:int, idempotency_key:str, request_digest:str) -> tuple[PaymentIntent,bool]:...


def canonical_digest(value: dict[str, Any]) -> str:
    return sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()


def validate_create(amount:int,currency:str,external_reference:str|None,metadata:dict[str,Any]) -> None:
    if isinstance(amount,bool) or not 1<=amount<=9_999_999_999_999:raise PaymentProblem(422,"INVALID_AMOUNT","Amount must be a positive minor-unit integer")
    if not CURRENCY.fullmatch(currency):raise PaymentProblem(422,"INVALID_CURRENCY","Currency must be a three-letter uppercase code")
    if external_reference is not None and not 1<=len(external_reference)<=128:raise PaymentProblem(422,"INVALID_EXTERNAL_REFERENCE","External reference is too long")
    encoded=json.dumps(metadata,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    if len(encoded)>8192:raise PaymentProblem(422,"METADATA_TOO_LARGE","Metadata exceeds 8192 bytes")


def validate_idempotency_key(value:str) -> None:
    if not IDEMPOTENCY_KEY.fullmatch(value):raise PaymentProblem(400,"INVALID_IDEMPOTENCY_KEY","A visible ASCII Idempotency-Key of at most 128 characters is required")


def validate_command(intent:PaymentIntent,command:PaymentCommand,amount:int|None) -> int|None:
    if command==PaymentCommand.AUTHORIZE:
        if intent.status!=PaymentStatus.REQUIRES_AUTHORIZATION:raise PaymentProblem(409,"INVALID_PAYMENT_STATE","Authorization cannot be requested from the current state")
        if amount is not None:raise PaymentProblem(422,"UNEXPECTED_AMOUNT","Authorize does not accept an amount")
    elif command==PaymentCommand.CAPTURE:
        if intent.status not in {PaymentStatus.AUTHORIZED,PaymentStatus.PARTIALLY_CAPTURED}:raise PaymentProblem(409,"INVALID_PAYMENT_STATE","Capture requires an authorized payment")
        remaining=intent.authorized_amount-intent.captured_amount
        amount=remaining if amount is None else amount
        if isinstance(amount,bool) or not 1<=amount<=remaining:raise PaymentProblem(422,"CAPTURE_LIMIT_EXCEEDED","Capture exceeds the authorized remainder")
    elif command==PaymentCommand.CANCEL:
        if intent.status not in {PaymentStatus.REQUIRES_AUTHORIZATION,PaymentStatus.AUTHORIZATION_PENDING,PaymentStatus.AUTHORIZED}:raise PaymentProblem(409,"INVALID_PAYMENT_STATE","Cancellation is unavailable from the current state")
        if amount is not None:raise PaymentProblem(422,"UNEXPECTED_AMOUNT","Cancel does not accept an amount")
    elif command==PaymentCommand.REFUND:
        if intent.status not in {PaymentStatus.PARTIALLY_CAPTURED,PaymentStatus.CAPTURED,PaymentStatus.PARTIALLY_REFUNDED}:raise PaymentProblem(409,"INVALID_PAYMENT_STATE","Refund requires captured funds")
        remaining=intent.captured_amount-intent.refunded_amount
        amount=remaining if amount is None else amount
        if isinstance(amount,bool) or not 1<=amount<=remaining:raise PaymentProblem(422,"REFUND_LIMIT_EXCEEDED","Refund exceeds the captured remainder")
    return amount


PENDING_STATUS={
    PaymentCommand.AUTHORIZE:PaymentStatus.AUTHORIZATION_PENDING,
    PaymentCommand.CAPTURE:PaymentStatus.CAPTURE_PENDING,
    PaymentCommand.CANCEL:PaymentStatus.CANCEL_PENDING,
    PaymentCommand.REFUND:PaymentStatus.REFUND_PENDING,
}


class PaymentService:
    def __init__(self,repository:PaymentRepository)->None:self.repository=repository

    def create(self,merchant_id:str,amount:int,currency:str,idempotency_key:str,external_reference:str|None=None,metadata:dict[str,Any]|None=None)->tuple[PaymentIntent,bool]:
        validate_idempotency_key(idempotency_key);metadata=metadata or {};validate_create(amount,currency,external_reference,metadata)
        body={"amount":amount,"currency":currency,"external_reference":external_reference,"metadata":metadata}
        return self.repository.create(merchant_id,amount,currency,idempotency_key,canonical_digest(body),external_reference,metadata)

    def get(self,merchant_id:str,payment_intent_id:str)->PaymentIntent:
        result=self.repository.get(merchant_id,payment_intent_id)
        if result is None:raise PaymentProblem(404,"PAYMENT_INTENT_NOT_FOUND","Payment Intent was not found")
        return result

    def request(self,merchant_id:str,payment_intent_id:str,command:PaymentCommand,amount:int|None,expected_version:int,idempotency_key:str)->tuple[PaymentIntent,bool]:
        validate_idempotency_key(idempotency_key)
        if isinstance(expected_version,bool) or expected_version<1:raise PaymentProblem(422,"INVALID_EXPECTED_VERSION","Expected version must be positive")
        digest=canonical_digest({"payment_intent_id":payment_intent_id,"command":command.value,"amount":amount,"expected_version":expected_version})
        return self.repository.request(merchant_id,payment_intent_id,command,amount,expected_version,idempotency_key,digest)
