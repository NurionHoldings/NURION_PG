"""Synthetic Payment Intent lifecycle with ledger-backed invariants.

The engine models behavior only. It has no provider adapter, network client,
credential input, card/account field, or capability to move real money.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from functools import wraps
from threading import RLock
from typing import Any

from .arkaon.governance import GovernanceRejected, canonical_digest
from .synthetic_finance import EntrySide, Journal, LedgerEntry, SyntheticLedger


class PaymentState(StrEnum):
    CREATED = "CREATED"
    SYNTHETIC_AUTHORIZED = "SYNTHETIC_AUTHORIZED"
    SYNTHETIC_CAPTURED = "SYNTHETIC_CAPTURED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"
    REFUNDED = "REFUNDED"
    CANCELLED = "CANCELLED"


class PaymentEventType(StrEnum):
    CREATED = "CREATED"
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    REFUNDED = "REFUNDED"
    CANCELLED = "CANCELLED"


def _synchronized(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)

    return wrapped


@dataclass
class PaymentIntent:
    intent_id: str
    merchant_ref: str
    customer_ref: str
    amount_minor: int
    currency: str
    policy_digest: str
    state: PaymentState = PaymentState.CREATED
    version: int = 1
    captured_minor: int = 0
    refunded_minor: int = 0
    synthetic_only: bool = True
    external_execution_allowed: bool = False

    def __post_init__(self) -> None:
        if (
            not self.intent_id.startswith("synthetic:")
            or not self.merchant_ref.startswith("synthetic:")
            or not self.customer_ref.startswith("synthetic:")
            or self.amount_minor <= 0
            or len(self.currency) != 3
            or not self.currency.isascii()
            or not self.currency.isalpha()
            or self.currency != self.currency.upper()
            or len(self.policy_digest) != 64
            or any(char not in "0123456789abcdef" for char in self.policy_digest)
            or not self.synthetic_only
            or self.external_execution_allowed
        ):
            raise GovernanceRejected("complete non-executable synthetic Payment Intent required")


@dataclass(frozen=True)
class PaymentEvent:
    sequence: int
    intent_id: str
    version: int
    event_type: PaymentEventType
    resulting_state: PaymentState
    amount_minor: int
    idempotency_key: str
    occurred_at: datetime
    payload_digest: str
    previous_digest: str
    event_digest: str


@dataclass
class PaymentEngine:
    ledger: SyntheticLedger = field(default_factory=SyntheticLedger)
    _intents: dict[str, PaymentIntent] = field(default_factory=dict)
    _events: list[PaymentEvent] = field(default_factory=list)
    _idempotency: dict[str, tuple[str, PaymentEvent]] = field(default_factory=dict)
    _lock: Any = field(default_factory=RLock, repr=False)

    @property
    def events(self) -> tuple[PaymentEvent, ...]:
        return tuple(self._events)

    @_synchronized
    def get(self, intent_id: str) -> PaymentIntent:
        return replace(self._get_mutable(intent_id))

    def _get_mutable(self, intent_id: str) -> PaymentIntent:
        try:
            return self._intents[intent_id]
        except KeyError as exc:
            raise GovernanceRejected("unknown synthetic Payment Intent") from exc

    @_synchronized
    def create(
        self,
        *,
        intent_id: str,
        merchant_ref: str,
        customer_ref: str,
        amount_minor: int,
        currency: str,
        policy_digest: str,
        idempotency_key: str,
        now: datetime,
    ) -> PaymentEvent:
        self._require_command_metadata(idempotency_key, now)
        payload = {
            "command": "create",
            "intent_id": intent_id,
            "merchant_ref": merchant_ref,
            "customer_ref": customer_ref,
            "amount_minor": amount_minor,
            "currency": currency,
            "policy_digest": policy_digest,
        }
        replay = self._replay(idempotency_key, payload)
        if replay is not None:
            return replay
        if intent_id in self._intents:
            raise GovernanceRejected("duplicate Payment Intent identity")
        intent = PaymentIntent(
            intent_id, merchant_ref, customer_ref, amount_minor, currency, policy_digest
        )
        self._intents[intent_id] = intent
        return self._emit(intent, PaymentEventType.CREATED, amount_minor, idempotency_key, payload, now)

    @_synchronized
    def authorize(
        self,
        intent_id: str,
        *,
        expected_version: int,
        idempotency_key: str,
        now: datetime,
    ) -> PaymentEvent:
        self._require_command_metadata(idempotency_key, now)
        payload = {
            "command": "authorize",
            "intent_id": intent_id,
            "expected_version": expected_version,
        }
        replay = self._replay(idempotency_key, payload)
        if replay is not None:
            return replay
        intent = self._get_mutable(intent_id)
        self._require_version(intent, expected_version)
        if intent.state is not PaymentState.CREATED:
            raise GovernanceRejected("authorization requires CREATED state")
        intent.state = PaymentState.SYNTHETIC_AUTHORIZED
        intent.version += 1
        return self._emit(
            intent, PaymentEventType.AUTHORIZED, intent.amount_minor, idempotency_key, payload, now
        )

    @_synchronized
    def capture(
        self,
        intent_id: str,
        *,
        expected_version: int,
        idempotency_key: str,
        now: datetime,
    ) -> PaymentEvent:
        self._require_command_metadata(idempotency_key, now)
        intent = self._get_mutable(intent_id)
        payload = {
            "command": "capture",
            "intent_id": intent_id,
            "expected_version": expected_version,
            "amount_minor": intent.amount_minor,
        }
        replay = self._replay(idempotency_key, payload)
        if replay is not None:
            return replay
        self._require_version(intent, expected_version)
        if intent.state is not PaymentState.SYNTHETIC_AUTHORIZED:
            raise GovernanceRejected("capture requires SYNTHETIC_AUTHORIZED state")
        journal = Journal(
            journal_id=f"synthetic:journal:capture:{intent.intent_id}",
            idempotency_key=f"synthetic:ledger:{idempotency_key}",
            created_at=now,
            entries=(
                LedgerEntry(
                    "synthetic:provider-clearing-receivable",
                    EntrySide.DEBIT,
                    intent.amount_minor,
                    intent.currency,
                ),
                LedgerEntry(
                    f"synthetic:merchant-payable:{intent.merchant_ref}",
                    EntrySide.CREDIT,
                    intent.amount_minor,
                    intent.currency,
                ),
            ),
            evidence_digest=intent.policy_digest,
        )
        self.ledger.post(journal)
        intent.captured_minor = intent.amount_minor
        intent.state = PaymentState.SYNTHETIC_CAPTURED
        intent.version += 1
        return self._emit(
            intent, PaymentEventType.CAPTURED, intent.amount_minor, idempotency_key, payload, now
        )

    @_synchronized
    def cancel(
        self,
        intent_id: str,
        *,
        expected_version: int,
        idempotency_key: str,
        now: datetime,
    ) -> PaymentEvent:
        self._require_command_metadata(idempotency_key, now)
        payload = {
            "command": "cancel",
            "intent_id": intent_id,
            "expected_version": expected_version,
        }
        replay = self._replay(idempotency_key, payload)
        if replay is not None:
            return replay
        intent = self._get_mutable(intent_id)
        self._require_version(intent, expected_version)
        if intent.state not in {PaymentState.CREATED, PaymentState.SYNTHETIC_AUTHORIZED}:
            raise GovernanceRejected("cancel is allowed only before capture")
        intent.state = PaymentState.CANCELLED
        intent.version += 1
        return self._emit(intent, PaymentEventType.CANCELLED, 0, idempotency_key, payload, now)

    @_synchronized
    def refund(
        self,
        intent_id: str,
        *,
        amount_minor: int,
        expected_version: int,
        idempotency_key: str,
        now: datetime,
    ) -> PaymentEvent:
        self._require_command_metadata(idempotency_key, now)
        payload = {
            "command": "refund",
            "intent_id": intent_id,
            "amount_minor": amount_minor,
            "expected_version": expected_version,
        }
        replay = self._replay(idempotency_key, payload)
        if replay is not None:
            return replay
        intent = self._get_mutable(intent_id)
        self._require_version(intent, expected_version)
        if intent.state not in {PaymentState.SYNTHETIC_CAPTURED, PaymentState.PARTIALLY_REFUNDED}:
            raise GovernanceRejected("refund requires captured funds")
        remaining = intent.captured_minor - intent.refunded_minor
        if amount_minor <= 0 or amount_minor > remaining:
            raise GovernanceRejected("refund exceeds refundable synthetic amount")
        refund_number = intent.refunded_minor + amount_minor
        journal = Journal(
            journal_id=f"synthetic:journal:refund:{intent.intent_id}:{refund_number}",
            idempotency_key=f"synthetic:ledger:{idempotency_key}",
            created_at=now,
            entries=(
                LedgerEntry(
                    f"synthetic:merchant-payable:{intent.merchant_ref}",
                    EntrySide.DEBIT,
                    amount_minor,
                    intent.currency,
                ),
                LedgerEntry(
                    "synthetic:provider-clearing-refund",
                    EntrySide.CREDIT,
                    amount_minor,
                    intent.currency,
                ),
            ),
            evidence_digest=intent.policy_digest,
        )
        self.ledger.post(journal)
        intent.refunded_minor = refund_number
        intent.state = (
            PaymentState.REFUNDED
            if intent.refunded_minor == intent.captured_minor
            else PaymentState.PARTIALLY_REFUNDED
        )
        intent.version += 1
        return self._emit(
            intent, PaymentEventType.REFUNDED, amount_minor, idempotency_key, payload, now
        )

    @_synchronized
    def verify_event_chains(self) -> bool:
        previous_by_intent: dict[str, str] = {}
        version_by_intent: dict[str, int] = {}
        for sequence, event in enumerate(self._events, start=1):
            previous = previous_by_intent.get(event.intent_id, "0" * 64)
            expected_version = version_by_intent.get(event.intent_id, 0) + 1
            expected = canonical_digest(
                {
                    "sequence": sequence,
                    "intent_id": event.intent_id,
                    "version": event.version,
                    "event_type": event.event_type.value,
                    "resulting_state": event.resulting_state.value,
                    "amount_minor": event.amount_minor,
                    "idempotency_key": event.idempotency_key,
                    "occurred_at": event.occurred_at.isoformat(),
                    "payload_digest": event.payload_digest,
                    "previous_digest": previous,
                }
            )
            if (
                event.sequence != sequence
                or event.version != expected_version
                or event.previous_digest != previous
                or event.event_digest != expected
            ):
                return False
            previous_by_intent[event.intent_id] = event.event_digest
            version_by_intent[event.intent_id] = event.version
        return True

    @_synchronized
    def evidence(self) -> dict[str, object]:
        intents = [
            {
                "intent_id": item.intent_id,
                "state": item.state.value,
                "version": item.version,
                "amount_minor": item.amount_minor,
                "captured_minor": item.captured_minor,
                "refunded_minor": item.refunded_minor,
            }
            for item in sorted(self._intents.values(), key=lambda value: value.intent_id)
        ]
        value = {
            "schema": "nurion.pg.synthetic-payment-lifecycle-evidence.v1",
            "intents": intents,
            "event_digests": [event.event_digest for event in self._events],
            "event_chains_valid": self.verify_event_chains(),
            "ledger_report_digest": self.ledger.evidence()["report_digest"],
            "synthetic_only": True,
            "provider_adapter_present": False,
            "credentials_accessed": False,
            "real_money_moved": False,
            "production_activation_allowed": False,
        }
        return {**value, "report_digest": canonical_digest(value)}

    def _emit(
        self,
        intent: PaymentIntent,
        event_type: PaymentEventType,
        amount_minor: int,
        idempotency_key: str,
        payload: dict[str, object],
        now: datetime,
    ) -> PaymentEvent:
        if not idempotency_key.startswith("synthetic:") or now.tzinfo is None:
            raise GovernanceRejected("synthetic idempotency key and aware time required")
        payload_digest = canonical_digest(payload)
        previous = next(
            (event.event_digest for event in reversed(self._events) if event.intent_id == intent.intent_id),
            "0" * 64,
        )
        sequence = len(self._events) + 1
        event_value = {
            "sequence": sequence,
            "intent_id": intent.intent_id,
            "version": intent.version,
            "event_type": event_type.value,
            "resulting_state": intent.state.value,
            "amount_minor": amount_minor,
            "idempotency_key": idempotency_key,
            "occurred_at": now.isoformat(),
            "payload_digest": payload_digest,
            "previous_digest": previous,
        }
        event = PaymentEvent(
            sequence=sequence,
            intent_id=intent.intent_id,
            version=intent.version,
            event_type=event_type,
            resulting_state=intent.state,
            amount_minor=amount_minor,
            idempotency_key=idempotency_key,
            occurred_at=now,
            payload_digest=payload_digest,
            previous_digest=previous,
            event_digest=canonical_digest(event_value),
        )
        self._events.append(event)
        self._idempotency[idempotency_key] = (payload_digest, event)
        return event

    def _replay(self, key: str, payload: dict[str, object]) -> PaymentEvent | None:
        if not key.startswith("synthetic:"):
            raise GovernanceRejected("synthetic idempotency key required")
        existing = self._idempotency.get(key)
        if existing is None:
            return None
        payload_digest, event = existing
        if payload_digest != canonical_digest(payload):
            raise GovernanceRejected("idempotency key payload mismatch")
        return event

    @staticmethod
    def _require_command_metadata(key: str, now: datetime) -> None:
        if not key.startswith("synthetic:") or now.tzinfo is None:
            raise GovernanceRejected("synthetic idempotency key and aware time required")

    @staticmethod
    def _require_version(intent: PaymentIntent, expected: int) -> None:
        if expected != intent.version:
            raise GovernanceRejected("stale Payment Intent version")
