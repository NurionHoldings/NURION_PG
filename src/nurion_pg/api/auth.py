"""Fail-closed API-key principal and merchant authorization boundary."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib
import hmac
import json
import re
from typing import Iterable,Protocol


IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class Role(StrEnum):
    MERCHANT_ADMIN = "merchant_admin"
    PAYMENT_OPERATOR = "payment_operator"
    AUDITOR = "auditor"


class Permission(StrEnum):
    TENANT_READ="tenant:read"
    PRINCIPAL_ADMIN="principal:admin"
    PAYMENT_READ="payment:read"
    PAYMENT_WRITE="payment:write"
    AUDIT_READ="audit:read"
    OPERATIONS_WRITE="operations:write"


ROLE_PERMISSIONS={
    Role.MERCHANT_ADMIN:frozenset({Permission.TENANT_READ,Permission.PRINCIPAL_ADMIN,Permission.PAYMENT_READ,Permission.PAYMENT_WRITE,Permission.AUDIT_READ,Permission.OPERATIONS_WRITE}),
    Role.PAYMENT_OPERATOR:frozenset({Permission.TENANT_READ,Permission.PAYMENT_READ,Permission.PAYMENT_WRITE}),
    Role.AUDITOR:frozenset({Permission.TENANT_READ,Permission.PAYMENT_READ,Permission.AUDIT_READ}),
}


@dataclass(frozen=True)
class Principal:
    principal_id: str
    merchant_id: str
    roles: frozenset[Role]
    key_id: str

    @property
    def permissions(self)->frozenset[Permission]:
        return frozenset(permission for role in self.roles for permission in ROLE_PERMISSIONS[role])


class Authenticator(Protocol):
    def authenticate(self,credential:str)->Principal|None:...


def authorize(principal:Principal,permission:Permission,merchant_id:str|None=None)->bool:
    return permission in principal.permissions and (merchant_id is None or merchant_id==principal.merchant_id)


@dataclass(frozen=True)
class ApiKeyRecord:
    key_id: str
    secret_sha256: str
    principal_id: str
    merchant_id: str
    roles: frozenset[Role]
    active: bool = True

    def __post_init__(self) -> None:
        if "_" in self.key_id:
            raise ValueError("key_id cannot contain underscore")
        for value in (self.key_id, self.principal_id, self.merchant_id):
            if not IDENTIFIER.fullmatch(value):
                raise ValueError("invalid auth identifier")
        if not re.fullmatch(r"[0-9a-f]{64}", self.secret_sha256):
            raise ValueError("secret_sha256 must be a lowercase SHA-256 digest")
        if not self.roles:
            raise ValueError("at least one role is required")


class ApiKeyRegistry:
    """Immutable, hash-only API-key registry pending OPS-E03 persistence."""

    def __init__(self, records: Iterable[ApiKeyRecord] = ()) -> None:
        indexed: dict[str, ApiKeyRecord] = {}
        for record in records:
            if record.key_id in indexed:
                raise ValueError("duplicate key_id")
            indexed[record.key_id] = record
        self._records = indexed

    @classmethod
    def from_json(cls, raw: str) -> "ApiKeyRegistry":
        if not raw.strip():
            return cls()
        try:
            values = json.loads(raw)
            if not isinstance(values, list):
                raise ValueError("registry must be a list")
            records = [
                ApiKeyRecord(
                    key_id=item["key_id"],
                    secret_sha256=item["secret_sha256"],
                    principal_id=item["principal_id"],
                    merchant_id=item["merchant_id"],
                    roles=frozenset(Role(role) for role in item["roles"]),
                    active=item.get("active", True),
                )
                for item in values
            ]
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid NURION_PG_API_KEYS_JSON") from exc
        return cls(records)

    def authenticate(self, credential: str) -> Principal | None:
        try:
            prefix, key_id, secret = credential.split("_", 2)
        except ValueError:
            return None
        if prefix != "npg" or not secret:
            return None
        digest = hashlib.sha256(secret.encode("utf-8")).hexdigest()
        record = self._records.get(key_id)
        expected = record.secret_sha256 if record is not None else "0" * 64
        secret_matches = hmac.compare_digest(digest, expected)
        if record is None or not record.active or not secret_matches:
            return None
        return Principal(record.principal_id, record.merchant_id, record.roles, record.key_id)


def secret_digest(secret: str) -> str:
    """Provisioning helper; plaintext secrets are never stored in the registry."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()
