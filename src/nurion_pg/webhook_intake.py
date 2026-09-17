"""Closed synthetic webhook verification and quarantine boundary.

Acceptance proves envelope integrity only. It never changes a Payment Intent,
calls a provider, or authorizes a financial operation.
"""

from __future__ import annotations

import hmac
import json
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from enum import StrEnum
from hashlib import sha256
from threading import RLock
from types import MappingProxyType
from typing import Any

from .arkaon.governance import GovernanceRejected, canonical_digest


class WebhookEventType(StrEnum):
    AUTHORIZATION_RESULT = "AUTHORIZATION_RESULT"
    CAPTURE_RESULT = "CAPTURE_RESULT"
    CANCEL_RESULT = "CANCEL_RESULT"
    REFUND_RESULT = "REFUND_RESULT"


class WebhookDecision(StrEnum):
    ACCEPTED = "ACCEPTED"
    DUPLICATE = "DUPLICATE"
    QUARANTINED = "QUARANTINED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class SyntheticVerificationKey:
    provider_id: str
    key_id: str
    secret: str = field(repr=False)
    valid_from: datetime
    valid_until: datetime
    revoked: bool = False
    synthetic_only: bool = True

    def __post_init__(self) -> None:
        if (
            not self.provider_id.endswith(".invalid")
            or not self.key_id.startswith("synthetic:")
            or not self.secret.startswith("synthetic:")
            or len(self.secret) < 32
            or self.valid_from.tzinfo is None
            or self.valid_until.tzinfo is None
            or self.valid_until <= self.valid_from
            or not self.synthetic_only
        ):
            raise GovernanceRejected("valid synthetic verification key required")


class SyntheticKeyRegistry:
    def __init__(self) -> None:
        self._keys: dict[tuple[str, str], SyntheticVerificationKey] = {}

    def register(self, key: SyntheticVerificationKey) -> None:
        identity = (key.provider_id, key.key_id)
        if identity in self._keys:
            raise GovernanceRejected("duplicate verification key identity")
        self._keys[identity] = key

    def resolve(self, provider_id: str, key_id: str, *, at: datetime) -> SyntheticVerificationKey:
        if at.tzinfo is None:
            raise GovernanceRejected("timezone-aware key verification time required")
        key = self._keys.get((provider_id, key_id))
        if key is None or key.revoked or not key.valid_from <= at < key.valid_until:
            raise GovernanceRejected("unknown, revoked, or inactive verification key")
        return key

    def revoke(self, provider_id: str, key_id: str) -> None:
        identity = (provider_id, key_id)
        key = self._keys.get(identity)
        if key is None:
            raise GovernanceRejected("unknown verification key")
        self._keys[identity] = replace(key, revoked=True)


@dataclass(frozen=True)
class WebhookEnvelope:
    provider_id: str
    key_id: str
    event_id: str
    nonce: str
    aggregate_id: str
    sequence: int
    event_type: WebhookEventType
    occurred_at: datetime
    payload: Mapping[str, Any]
    signature: str
    synthetic_only: bool = True
    automatic_application_allowed: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.payload, Mapping):
            raise GovernanceRejected("mapping webhook payload required")
        payload = dict(self.payload)
        try:
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        except (TypeError, ValueError) as exc:
            raise GovernanceRejected("canonical JSON webhook payload required") from exc
        object.__setattr__(self, "payload", MappingProxyType(payload))
        if (
            not self.provider_id.endswith(".invalid")
            or not self.key_id.startswith("synthetic:")
            or not self.event_id.startswith("synthetic:")
            or not self.nonce.startswith("synthetic:")
            or not self.aggregate_id.startswith("synthetic:")
            or not isinstance(self.sequence, int)
            or isinstance(self.sequence, bool)
            or self.sequence <= 0
            or not isinstance(self.event_type, WebhookEventType)
            or self.occurred_at.tzinfo is None
            or not self.signature.startswith("sha256=")
            or len(self.signature) != 71
            or any(char not in "0123456789abcdef" for char in self.signature[7:])
            or not self.synthetic_only
            or self.automatic_application_allowed
        ):
            raise GovernanceRejected("complete non-applying synthetic webhook envelope required")

    def signing_value(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "key_id": self.key_id,
            "event_id": self.event_id,
            "nonce": self.nonce,
            "aggregate_id": self.aggregate_id,
            "sequence": self.sequence,
            "event_type": self.event_type.value,
            "occurred_at": self.occurred_at.isoformat(),
            "payload": dict(self.payload),
            "synthetic_only": self.synthetic_only,
            "automatic_application_allowed": self.automatic_application_allowed,
        }

    @property
    def envelope_digest(self) -> str:
        return canonical_digest({**self.signing_value(), "signature": self.signature})


def sign_envelope(envelope: WebhookEnvelope, secret: str) -> str:
    material = canonical_digest(envelope.signing_value()).encode("ascii")
    return "sha256=" + hmac.new(secret.encode("utf-8"), material, sha256).hexdigest()


@dataclass(frozen=True)
class IntakeReceipt:
    sequence: int
    event_id: str
    decision: WebhookDecision
    reason: str
    envelope_digest: str
    previous_digest: str
    receipt_digest: str
    automatic_application_allowed: bool = False


@dataclass
class _StoredEnvelope:
    envelope: WebhookEnvelope
    decision: WebhookDecision


class SyntheticWebhookIntake:
    _COMMON_FIELDS = frozenset({"intent_id", "expected_version", "outcome"})
    _AMOUNT_FIELDS = _COMMON_FIELDS | {"amount_minor"}
    _FORBIDDEN_FIELDS = frozenset(
        {
            "pan",
            "card_number",
            "cvv",
            "account_number",
            "resident_id",
            "name",
            "email",
            "phone",
            "address",
            "latitude",
            "longitude",
            "token",
            "secret",
        }
    )

    def __init__(
        self,
        key_registry: SyntheticKeyRegistry,
        *,
        max_age_seconds: int = 600,
        future_skew_seconds: int = 60,
        max_payload_bytes: int = 8192,
    ) -> None:
        if min(max_age_seconds, future_skew_seconds, max_payload_bytes) <= 0:
            raise GovernanceRejected("positive bounded webhook limits required")
        self.key_registry = key_registry
        self.max_age = timedelta(seconds=max_age_seconds)
        self.future_skew = timedelta(seconds=future_skew_seconds)
        self.max_payload_bytes = max_payload_bytes
        self._stored: dict[str, _StoredEnvelope] = {}
        self._nonce_owner: dict[tuple[str, str], str] = {}
        self._last_sequence: dict[str, int] = {}
        self.receipts: list[IntakeReceipt] = []
        self._lock = RLock()

    def verify_only(
        self, envelope: WebhookEnvelope, *, received_at: datetime
    ) -> str:
        """Verify an envelope without accepting, storing, or applying it."""
        with self._lock:
            if received_at.tzinfo is None:
                raise GovernanceRejected("timezone-aware receipt time required")
            self._verify(envelope, received_at=received_at)
            return envelope.envelope_digest

    def verify_quarantined_only(
        self, envelope: WebhookEnvelope, *, now: datetime
    ) -> str:
        """Reverify immutable quarantined material against current key state."""
        with self._lock:
            if now.tzinfo is None:
                raise GovernanceRejected("timezone-aware retry time required")
            self._verify(envelope, received_at=now)
            key = self.key_registry.resolve(envelope.provider_id, envelope.key_id, at=now)
            self._verify_signature(envelope, key)
            return envelope.envelope_digest

    def ingest(self, envelope: WebhookEnvelope, *, received_at: datetime) -> IntakeReceipt:
        with self._lock:
            if received_at.tzinfo is None:
                raise GovernanceRejected("timezone-aware receipt time required")
            existing = self._stored.get(envelope.event_id)
            if existing is not None:
                if existing.envelope.envelope_digest != envelope.envelope_digest:
                    return self._receipt(envelope, WebhookDecision.BLOCKED, "event_id_collision")
                if existing.decision is WebhookDecision.ACCEPTED:
                    return self._receipt(envelope, WebhookDecision.DUPLICATE, "exact_duplicate")
                return self._receipt(envelope, existing.decision, "already_quarantined")

            try:
                self._verify(envelope, received_at=received_at)
            except GovernanceRejected as exc:
                return self._receipt(envelope, WebhookDecision.BLOCKED, str(exc))

            nonce_identity = (envelope.provider_id, envelope.nonce)
            if nonce_identity in self._nonce_owner:
                return self._receipt(envelope, WebhookDecision.BLOCKED, "nonce_replay")

            self._nonce_owner[nonce_identity] = envelope.event_id
            expected = self._last_sequence.get(envelope.aggregate_id, 0) + 1
            if envelope.sequence < expected:
                return self._receipt(envelope, WebhookDecision.BLOCKED, "sequence_replay")
            if envelope.sequence > expected:
                self._stored[envelope.event_id] = _StoredEnvelope(
                    envelope, WebhookDecision.QUARANTINED
                )
                return self._receipt(envelope, WebhookDecision.QUARANTINED, "sequence_gap")

            self._stored[envelope.event_id] = _StoredEnvelope(envelope, WebhookDecision.ACCEPTED)
            self._last_sequence[envelope.aggregate_id] = envelope.sequence
            return self._receipt(envelope, WebhookDecision.ACCEPTED, "verified_envelope_only")

    def retry_quarantined(self, event_id: str, *, now: datetime) -> IntakeReceipt:
        with self._lock:
            stored = self._stored.get(event_id)
            if stored is None or stored.decision is not WebhookDecision.QUARANTINED:
                raise GovernanceRejected("quarantined event required")
            envelope = stored.envelope
            if now.tzinfo is None:
                raise GovernanceRejected("timezone-aware retry time required")
            try:
                self.verify_quarantined_only(envelope, now=now)
            except GovernanceRejected as exc:
                stored.decision = WebhookDecision.BLOCKED
                return self._receipt(envelope, WebhookDecision.BLOCKED, str(exc))
            expected = self._last_sequence.get(envelope.aggregate_id, 0) + 1
            if envelope.sequence > expected:
                return self._receipt(envelope, WebhookDecision.QUARANTINED, "sequence_gap")
            if envelope.sequence < expected:
                stored.decision = WebhookDecision.BLOCKED
                return self._receipt(envelope, WebhookDecision.BLOCKED, "sequence_replay")
            stored.decision = WebhookDecision.ACCEPTED
            self._last_sequence[envelope.aggregate_id] = envelope.sequence
            return self._receipt(envelope, WebhookDecision.ACCEPTED, "quarantine_released")

    def verify_receipts(self) -> bool:
        with self._lock:
            previous = "0" * 64
            for sequence, receipt in enumerate(self.receipts, start=1):
                expected = canonical_digest(
                    {
                        "sequence": sequence,
                        "event_id": receipt.event_id,
                        "decision": receipt.decision.value,
                        "reason": receipt.reason,
                        "envelope_digest": receipt.envelope_digest,
                        "previous_digest": previous,
                        "automatic_application_allowed": False,
                    }
                )
                if (
                    receipt.sequence != sequence
                    or receipt.previous_digest != previous
                    or receipt.receipt_digest != expected
                ):
                    return False
                previous = receipt.receipt_digest
            return True

    def evidence(self) -> dict[str, object]:
        with self._lock:
            counts = {decision.value: 0 for decision in WebhookDecision}
            for receipt in self.receipts:
                counts[receipt.decision.value] += 1
            value = {
                "schema": "nurion.pg.synthetic-webhook-intake-evidence.v1",
                "decision_counts": counts,
                "receipt_chain_valid": self.verify_receipts(),
                "accepted_event_ids": sorted(
                    event_id
                    for event_id, stored in self._stored.items()
                    if stored.decision is WebhookDecision.ACCEPTED
                ),
                "synthetic_only": True,
                "network_listener_present": False,
                "payment_state_automatically_changed": False,
                "production_activation_allowed": False,
            }
            return {**value, "report_digest": canonical_digest(value)}

    def _verify(self, envelope: WebhookEnvelope, *, received_at: datetime) -> None:
        age = received_at - envelope.occurred_at
        if age > self.max_age or age < -self.future_skew:
            raise GovernanceRejected("expired_or_future_event")
        key = self.key_registry.resolve(
            envelope.provider_id, envelope.key_id, at=envelope.occurred_at
        )
        self._verify_signature(envelope, key)
        self._verify_payload(envelope)

    @staticmethod
    def _verify_signature(
        envelope: WebhookEnvelope, key: SyntheticVerificationKey
    ) -> None:
        expected = sign_envelope(envelope, key.secret)
        if not hmac.compare_digest(expected, envelope.signature):
            raise GovernanceRejected("signature_mismatch")

    def _verify_payload(self, envelope: WebhookEnvelope) -> None:
        allowed = (
            self._AMOUNT_FIELDS
            if envelope.event_type in {
                WebhookEventType.CAPTURE_RESULT,
                WebhookEventType.REFUND_RESULT,
            }
            else self._COMMON_FIELDS
        )
        if set(envelope.payload) != allowed:
            raise GovernanceRejected("payload_schema_mismatch")
        if self._contains_forbidden_field(envelope.payload):
            raise GovernanceRejected("forbidden_personal_or_secret_field")
        payload_size = len(
            json.dumps(
                dict(envelope.payload),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        if payload_size > self.max_payload_bytes:
            raise GovernanceRejected("payload_too_large")
        intent_id = envelope.payload["intent_id"]
        outcome = envelope.payload["outcome"]
        if (
            not isinstance(intent_id, str)
            or intent_id != envelope.aggregate_id
            or not intent_id.startswith("synthetic:")
            or not isinstance(envelope.payload["expected_version"], int)
            or isinstance(envelope.payload["expected_version"], bool)
            or envelope.payload["expected_version"] <= 0
            or not isinstance(outcome, str)
            or outcome not in {"SUCCEEDED", "FAILED"}
        ):
            raise GovernanceRejected("invalid_synthetic_payload")
        if "amount_minor" in envelope.payload and (
            not isinstance(envelope.payload["amount_minor"], int)
            or isinstance(envelope.payload["amount_minor"], bool)
            or envelope.payload["amount_minor"] <= 0
        ):
            raise GovernanceRejected("invalid_amount")

    def _contains_forbidden_field(self, value: object) -> bool:
        if isinstance(value, Mapping):
            return any(
                str(key).lower() in self._FORBIDDEN_FIELDS
                or self._contains_forbidden_field(item)
                for key, item in value.items()
            )
        if isinstance(value, list):
            return any(self._contains_forbidden_field(item) for item in value)
        return False

    def _receipt(
        self, envelope: WebhookEnvelope, decision: WebhookDecision, reason: str
    ) -> IntakeReceipt:
        previous = self.receipts[-1].receipt_digest if self.receipts else "0" * 64
        sequence = len(self.receipts) + 1
        value = {
            "sequence": sequence,
            "event_id": envelope.event_id,
            "decision": decision.value,
            "reason": reason,
            "envelope_digest": envelope.envelope_digest,
            "previous_digest": previous,
            "automatic_application_allowed": False,
        }
        receipt = IntakeReceipt(
            sequence,
            envelope.event_id,
            decision,
            reason,
            envelope.envelope_digest,
            previous,
            canonical_digest(value),
        )
        self.receipts.append(receipt)
        return receipt
