"""Fail-closed registry for public regulatory evidence.

Official publications are evidence, never executable instructions. Registry
entries may support design drafts but can never activate production behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from urllib.parse import urlparse

from .governance import GovernanceRejected, canonical_digest


class SourceAuthority(StrEnum):
    PRIMARY_LAW = "PRIMARY_LAW"
    REGULATOR_ANNOUNCEMENT = "REGULATOR_ANNOUNCEMENT"
    REGULATOR_GUIDELINE = "REGULATOR_GUIDELINE"
    SECONDARY_ANALYSIS = "SECONDARY_ANALYSIS"


class EvidenceDisposition(StrEnum):
    DRAFTING_ONLY = "DRAFTING_ONLY"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    STALE = "STALE"
    CONFLICT = "CONFLICT"
    BLOCKED = "BLOCKED"


OFFICIAL_HOSTS = frozenset(
    {
        "law.go.kr",
        "www.law.go.kr",
        "fsc.go.kr",
        "www.fsc.go.kr",
        "fss.or.kr",
        "www.fss.or.kr",
        "gov.kr",
        "www.gov.kr",
    }
)


@dataclass(frozen=True)
class RegulatoryClaim:
    requirement_key: str
    statement: str
    lifecycle: str
    effective_on: str | None = None

    def __post_init__(self) -> None:
        if not self.requirement_key.strip() or not self.statement.strip() or not self.lifecycle.strip():
            raise GovernanceRejected("complete regulatory claim required")

    def canonical(self) -> dict[str, str | None]:
        return {
            "requirement_key": self.requirement_key,
            "statement": self.statement,
            "lifecycle": self.lifecycle,
            "effective_on": self.effective_on,
        }


@dataclass(frozen=True)
class RegulatoryEvidence:
    evidence_id: str
    url: str
    title: str
    authority: SourceAuthority
    publisher: str
    published_on: str | None
    retrieved_at: datetime
    revalidate_after: datetime
    document_version: str
    claims: tuple[RegulatoryClaim, ...]
    claim_snapshot_digest: str | None
    official_verified: bool
    content_capture_complete: bool
    conflicts_with: tuple[str, ...] = ()
    instruction_authority: bool = False
    operational_use_allowed: bool = False

    def __post_init__(self) -> None:
        parsed = urlparse(self.url)
        if (
            not self.evidence_id.strip()
            or parsed.scheme != "https"
            or not parsed.hostname
            or not self.title.strip()
            or not self.publisher.strip()
            or not self.document_version.strip()
            or self.retrieved_at.tzinfo is None
            or self.revalidate_after.tzinfo is None
            or self.revalidate_after <= self.retrieved_at
        ):
            raise GovernanceRejected("complete regulatory evidence metadata required")
        if self.instruction_authority or self.operational_use_allowed:
            raise GovernanceRejected("regulatory evidence cannot grant execution authority")
        if self.official_verified and parsed.hostname not in OFFICIAL_HOSTS:
            raise GovernanceRejected("official evidence host is not allowlisted")
        expected = canonical_digest([claim.canonical() for claim in self.claims])
        if self.content_capture_complete:
            if not self.claims or self.claim_snapshot_digest != expected:
                raise GovernanceRejected("complete capture requires matching claim digest")
        elif self.claim_snapshot_digest is not None:
            raise GovernanceRejected("metadata-only evidence cannot claim a content digest")

    @property
    def claim_keys(self) -> frozenset[str]:
        return frozenset(claim.requirement_key for claim in self.claims)


class RegulatoryRegistry:
    def __init__(self) -> None:
        self._items: dict[str, RegulatoryEvidence] = {}

    @property
    def items(self) -> tuple[RegulatoryEvidence, ...]:
        return tuple(self._items[key] for key in sorted(self._items))

    def register(self, evidence: RegulatoryEvidence) -> None:
        if evidence.evidence_id in self._items:
            raise GovernanceRejected("duplicate regulatory evidence identity")
        if evidence.evidence_id in evidence.conflicts_with:
            raise GovernanceRejected("evidence cannot conflict with itself")
        self._items[evidence.evidence_id] = evidence

    def disposition(self, evidence_id: str, *, now: datetime) -> EvidenceDisposition:
        if now.tzinfo is None:
            raise GovernanceRejected("timezone-aware review time required")
        evidence = self._items.get(evidence_id)
        if evidence is None:
            return EvidenceDisposition.BLOCKED
        if evidence.revalidate_after <= now:
            return EvidenceDisposition.STALE
        if evidence.conflicts_with:
            return EvidenceDisposition.CONFLICT
        if (
            evidence.authority is SourceAuthority.SECONDARY_ANALYSIS
            or not evidence.official_verified
            or not evidence.content_capture_complete
        ):
            return EvidenceDisposition.HUMAN_REVIEW
        return EvidenceDisposition.DRAFTING_ONLY

    def requirement_view(self, requirement_key: str, *, now: datetime) -> dict[str, object]:
        matching = [item for item in self.items if requirement_key in item.claim_keys]
        dispositions = {
            item.evidence_id: self.disposition(item.evidence_id, now=now).value for item in matching
        }
        statements = sorted(
            {
                claim.statement
                for item in matching
                for claim in item.claims
                if claim.requirement_key == requirement_key
            }
        )
        blocked = (
            not matching
            or len(statements) != 1
            or any(value != EvidenceDisposition.DRAFTING_ONLY.value for value in dispositions.values())
        )
        value = {
            "requirement_key": requirement_key,
            "evidence": dispositions,
            "statements": statements,
            "drafting_allowed": not blocked,
            "operational_use_allowed": False,
        }
        return {**value, "view_digest": canonical_digest(value)}

    def report(self, *, now: datetime) -> dict[str, object]:
        rows = [
            {
                "evidence_id": item.evidence_id,
                "authority": item.authority.value,
                "disposition": self.disposition(item.evidence_id, now=now).value,
                "claim_snapshot_digest": item.claim_snapshot_digest,
            }
            for item in self.items
        ]
        value = {
            "schema": "nurion.pg.regulatory-evidence-report.v1",
            "items": rows,
            "production_activation_allowed": False,
            "automatic_registry_update_allowed": False,
        }
        return {**value, "report_digest": canonical_digest(value)}

