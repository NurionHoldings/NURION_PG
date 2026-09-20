"""Synthetic, in-memory, non-authorizing P0 design baseline RFC controls #3101-#3500."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from threading import RLock
from urllib.parse import urlparse

from .arkaon.governance import GovernanceRejected, canonical_digest

WORKSTREAM_NAMES = (
    "DOMAIN_GLOSSARY", "PAYMENT_VS_INTERNAL_APPROVAL_VOCABULARY", "TRUST_BOUNDARIES",
    "TOKENIZED_DATA_FLOW", "CONCEPTUAL_FUND_FLOW", "DOUBLE_ENTRY_LEDGER_INVARIANTS",
    "PAYMENT_STATE_MACHINE", "CANCELLATION_REFUND_STATE_MACHINE",
    "SETTLEMENT_SUBLEDGER_STATE_MACHINE", "RECONCILIATION_EXCEPTION_MODEL",
    "IDEMPOTENCY_CONCURRENCY_CONTRACTS", "INBOX_OUTBOX_SIGNED_WEBHOOK_CONTRACTS",
    "TENANT_AUTH_MAKER_CHECKER_BREAK_GLASS", "IMMUTABLE_AUDIT_DR_OBSERVABILITY_SLO",
    "HOME_PORTAL_DETAIL_RELATED_RECORD_IA", "OFFICIAL_SOURCE_TRACEABILITY_APPROVAL_GATES",
)
WORKSTREAMS = tuple((3101 + i*25, 3125 + i*25, name) for i, name in enumerate(WORKSTREAM_NAMES))
SOURCE_CLASSES = frozenset({"LAW", "STANDARD", "GUIDANCE"})
TRUSTED_SOURCE_HOSTS = frozenset({
    "law.go.kr", "pcisecuritystandards.org", "owasp.org", "postgresql.org",
    "apache.org", "opentelemetry.io", "w3.org", "google.com", "github.com",
    "stripe.com", "bok.or.kr",
})
OWNER_ROLES = frozenset({"PRODUCT", "SECURITY", "COMPLIANCE", "LEDGER", "PAYMENTS", "SETTLEMENT", "SRE", "UX"})
PLAIN_TEMPLATES = {"DRAFTED": "설계 초안이 작성되었습니다.", "REVIEWED": "독립 검토를 통과했습니다.",
                   "HELD": "보완이 필요해 중단되었습니다.", "RECORDED": "검증 기록이 보관되었습니다."}
MAX_REVIEW_BATCH = 20
MAXIMUM_STATE = "SYNTHETIC_P0_BASELINE_RECORDED"


def _syn(value, kind): return isinstance(value, str) and value.startswith(f"synthetic:{kind}:")
def _hex(value): return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)
def _identity(value): return value.rsplit(":", 1)[-1]


@dataclass(frozen=True)
class OfficialSource:
    source_id: str; url: str; title: str; accessed_on: str; classification: str
    expires_on: str; content_digest: str; reviewed: bool; digest: str


@dataclass(frozen=True)
class RFCRequirement:
    requirement_id: str; workstream: str; control_ids: tuple[int, ...]; rationale: str
    threat: str; acceptance_evidence: tuple[str, ...]; owner_role: str
    approval_required: bool; source_ids: tuple[str, ...]; digest: str


@dataclass(frozen=True)
class RFCBaseline:
    rfc_id: str; author: str; requirement_ids: tuple[str, ...]; source_ids: tuple[str, ...]
    plain_summary: tuple[str, ...]; status: str; version: int; previous_digest: str|None; digest: str


@dataclass(frozen=True)
class RFCReview:
    review_id: str; rfc_id: str; source_version: int; reviewer: str; accepted: bool
    finding_digest: str; rfc_digest: str; digest: str


@dataclass(frozen=True)
class RFCReceipt:
    receipt_id: str; rfc_id: str; source_version: int; verifier: str; review_digest: str
    operator_approval_required: bool; approval_recorded: bool; digest: str


class SyntheticP0DesignBaselineRFC:
    """RFC registry only: it cannot execute payments, ledgers, APIs, UI, or policy changes."""
    def __init__(self, today="2026-09-19"):
        self.today = date.fromisoformat(today)
        self._sources = {}; self._requirements = {}; self._rfcs = {}; self._history = []
        self._reviews = {}; self._rfc_reviews = {}; self._receipts = {}; self._rfc_receipts = {}
        self._members = {}; self._events = []; self._holds = []; self._lock = RLock()

    @staticmethod
    def source_digest(source_id, url, title, accessed_on, classification, expires_on, content_digest, reviewed):
        return canonical_digest(locals())

    @staticmethod
    def requirement_digest(requirement_id, workstream, control_ids, rationale, threat,
                           acceptance_evidence, owner_role, approval_required, source_ids):
        return canonical_digest(locals())

    @staticmethod
    def rfc_digest(rfc_id, author, requirement_ids, source_ids, plain_summary, status, version, previous_digest):
        return canonical_digest(locals())

    def add_source(self, source_id, url, title, accessed_on, classification, expires_on,
                   content_digest, reviewed=True):
        payload = dict(source_id=source_id, url=url, title=title, accessed_on=accessed_on,
            classification=classification, expires_on=expires_on, content_digest=content_digest,
            reviewed=reviewed)
        row = OfficialSource(**payload, digest=self.source_digest(**payload))
        with self._lock:
            if not self._valid_source(row): raise GovernanceRejected("current reviewed official source required")
            prior = self._sources.get(source_id)
            if prior: 
                if prior == row: return prior
                raise GovernanceRejected("source conflict")
            if any(s.url == url and s.title == title for s in self._sources.values()):
                raise GovernanceRejected("duplicate source")
            self._sources[source_id] = row; return row

    def add_requirement(self, requirement_id, workstream, control_ids, rationale, threat,
                        acceptance_evidence, owner_role, approval_required, source_ids):
        control_ids, acceptance_evidence, source_ids = tuple(control_ids), tuple(acceptance_evidence), tuple(source_ids)
        payload = dict(requirement_id=requirement_id, workstream=workstream, control_ids=control_ids,
            rationale=rationale, threat=threat, acceptance_evidence=acceptance_evidence,
            owner_role=owner_role, approval_required=approval_required, source_ids=source_ids)
        row = RFCRequirement(**payload, digest=self.requirement_digest(**payload))
        with self._lock:
            if not self._valid_requirement(row): raise GovernanceRejected("integral sourced requirement required")
            prior = self._requirements.get(requirement_id)
            if prior:
                if prior == row: return prior
                raise GovernanceRejected("requirement conflict")
            claimed = {n for r in self._requirements.values() for n in r.control_ids}
            if claimed.intersection(control_ids): raise GovernanceRejected("control overlap")
            self._requirements[requirement_id] = row; return row

    def author(self, rfc_id, author, requirement_ids):
        requirement_ids = tuple(requirement_ids)
        with self._lock:
            prior = self._rfcs.get(rfc_id)
            if prior:
                if prior.author == author and prior.requirement_ids == requirement_ids: return prior
                raise GovernanceRejected("rfc conflict")
            requirements = [self._requirements.get(x) for x in requirement_ids]
            selected_controls = {n for r in requirements if r is not None for n in r.control_ids}
            if (not _syn(rfc_id, "p0-rfc") or not _syn(author, "rfc-author") or not requirements
                    or any(x is None for x in requirements) or len(set(requirement_ids)) != len(requirement_ids)
                    or selected_controls != set(range(3101, 3501))
                    or any(x in self._members for x in requirement_ids) or not self._registry_integrity()):
                raise GovernanceRejected("integral unassigned requirements required")
            sources = tuple(sorted({s for r in requirements for s in r.source_ids}))
            base = dict(rfc_id=rfc_id, author=author, requirement_ids=requirement_ids, source_ids=sources,
                plain_summary=(PLAIN_TEMPLATES["DRAFTED"], "운영자 승인이 있어야 다음 단계로 갈 수 있습니다."),
                status="DRAFTED", version=1, previous_digest=None)
            row = RFCBaseline(**base, digest=self.rfc_digest(**base))
            for rid in requirement_ids: self._members[rid] = rfc_id
            return self._append("RFC_DRAFTED", row)

    def review(self, review_id, rfc_id, expected_version, reviewer, accepted, finding_digest):
        with self._lock:
            prior = self._reviews.get(review_id)
            args = (rfc_id, expected_version, reviewer, accepted, finding_digest)
            if prior:
                if args == (prior.rfc_id, prior.source_version, prior.reviewer, prior.accepted, prior.finding_digest): return self._rfcs[rfc_id]
                raise GovernanceRejected("review conflict")
            old = self._rfcs.get(rfc_id)
            if (old is None or old.status != "DRAFTED" or old.version != expected_version
                    or not _syn(review_id, "rfc-review") or not _syn(reviewer, "rfc-reviewer") or not isinstance(accepted, bool)
                    or not _hex(finding_digest) or _identity(reviewer) in self._roles(old)
                    or rfc_id in self._rfc_reviews or not self._integrity()):
                raise GovernanceRejected("independent current review required")
            payload = dict(review_id=review_id, rfc_id=rfc_id, source_version=expected_version,
                reviewer=reviewer, accepted=accepted, finding_digest=finding_digest, rfc_digest=old.digest)
            artifact = RFCReview(**payload, digest=canonical_digest(payload))
            self._reviews[review_id] = artifact; self._rfc_reviews[rfc_id] = review_id
            row = self._transition(old, "RFC_REVIEWED" if accepted else "RFC_HELD", "REVIEWED" if accepted else "HELD", artifact.digest)
            if not accepted: self._hold(row, reviewer, "REVIEW_REJECTED", artifact.digest)
            return row

    def record(self, receipt_id, rfc_id, expected_version, verifier, review_digest):
        with self._lock:
            prior = self._receipts.get(receipt_id)
            args = (rfc_id, expected_version, verifier, review_digest)
            if prior:
                if args == (prior.rfc_id, prior.source_version, prior.verifier, prior.review_digest): return self._rfcs[rfc_id]
                raise GovernanceRejected("receipt conflict")
            old = self._rfcs.get(rfc_id); review = self._reviews.get(self._rfc_reviews.get(rfc_id, ""))
            if (old is None or old.status != "REVIEWED" or old.version != expected_version or review is None
                    or not review.accepted or review.digest != review_digest or not _syn(verifier, "rfc-verifier")
                    or not _syn(receipt_id, "rfc-receipt") or _identity(verifier) in self._roles(old)
                    or rfc_id in self._rfc_receipts or not self._integrity()):
                raise GovernanceRejected("reviewed current rfc required")
            payload = dict(receipt_id=receipt_id, rfc_id=rfc_id, source_version=expected_version,
                verifier=verifier, review_digest=review_digest, operator_approval_required=True, approval_recorded=False)
            receipt = RFCReceipt(**payload, digest=canonical_digest(payload)); self._receipts[receipt_id] = receipt
            self._rfc_receipts[rfc_id] = receipt_id
            return self._transition(old, "RFC_RECEIPT_RECORDED", MAXIMUM_STATE, receipt.digest)

    def review_batch(self, reviewer, rfc_ids):
        ids = tuple(rfc_ids)
        if not _syn(reviewer,"rfc-reviewer") or not 1 <= len(ids) <= MAX_REVIEW_BATCH or len(set(ids)) != len(ids): raise GovernanceRejected("bounded unique review batch required")
        rows = [self._rfcs.get(x) for x in ids]
        if any(row is None or _identity(reviewer) in self._roles(row) for row in rows):
            raise GovernanceRejected("complete independent review batch required")
        return tuple(rows)

    def audit_hold(self, rfc_id, expected_version, auditor, finding_digest):
        with self._lock:
            old = self._rfcs.get(rfc_id)
            if (old is None or old.status == "HELD" or old.version != expected_version or not _syn(auditor, "rfc-auditor")
                    or not _hex(finding_digest) or _identity(auditor) in self._roles(old) or not self._integrity()):
                raise GovernanceRejected("independent audit required")
            row = self._transition(old, "RFC_HELD", "HELD", finding_digest); self._hold(row, auditor, "AUDIT_FINDING", finding_digest); return row

    def artifact(self, review_id): return self._reviews[review_id]
    def _roles(self, row):
        roles = {_identity(row.author)}
        rev = self._reviews.get(self._rfc_reviews.get(row.rfc_id, "")); rec = self._receipts.get(self._rfc_receipts.get(row.rfc_id, ""))
        if rev: roles.add(_identity(rev.reviewer))
        if rec: roles.add(_identity(rec.verifier))
        return roles

    def _append(self, action, row, attachment=None):
        prev = self._events[-1]["digest"] if self._events else None
        payload = dict(sequence=len(self._events)+1, action=action, rfc_digest=row.digest,
                       attachment_digest=attachment, previous_digest=prev)
        self._events.append({**payload, "digest":canonical_digest(payload)}); self._history.append(row); self._rfcs[row.rfc_id]=row; return row

    def _transition(self, old, action, status, attachment):
        values = old.__dict__ | {"status":status, "version":old.version+1, "previous_digest":old.digest,
            "plain_summary":(PLAIN_TEMPLATES["RECORDED" if status == MAXIMUM_STATE else status],
                             "운영자 승인이 있어야 다음 단계로 갈 수 있습니다.")}
        values["digest"] = self.rfc_digest(**{k:v for k,v in values.items() if k!="digest"})
        return self._append(action, RFCBaseline(**values), attachment)

    def _hold(self, row, actor, reason, attachment):
        prev=self._holds[-1]["digest"] if self._holds else None
        p=dict(sequence=len(self._holds)+1,rfc_id=row.rfc_id,actor=actor,reason=reason,rfc_digest=row.digest,attachment_digest=attachment,previous_digest=prev)
        self._holds.append({**p,"digest":canonical_digest(p)})

    def _valid_source(self, s):
        try: accessed=date.fromisoformat(s.accessed_on); expires=date.fromisoformat(s.expires_on)
        except (ValueError,TypeError): return False
        parsed=urlparse(s.url)
        host=(parsed.hostname or "").lower()
        trusted=any(host==allowed or host.endswith("."+allowed)
                    for allowed in TRUSTED_SOURCE_HOSTS)
        p={k:v for k,v in s.__dict__.items() if k!="digest"}
        return (_syn(s.source_id,"official-source") and parsed.scheme=="https" and trusted
            and bool(s.title.strip()) and s.classification in SOURCE_CLASSES and accessed<=self.today<=expires
            and _hex(s.content_digest) and s.reviewed is True and s.digest==self.source_digest(**p))

    def _valid_requirement(self, r):
        expected=next(((a,b) for a,b,n in WORKSTREAMS if n==r.workstream),None)
        p={k:v for k,v in r.__dict__.items() if k!="digest"}
        return (_syn(r.requirement_id,"p0-requirement") and expected is not None and r.control_ids
            and len(set(r.control_ids))==len(r.control_ids) and all(expected[0]<=x<=expected[1] for x in r.control_ids)
            and bool(r.rationale.strip()) and bool(r.threat.strip()) and r.acceptance_evidence
            and all(_hex(x) for x in r.acceptance_evidence) and r.owner_role in OWNER_ROLES
            and r.approval_required is True and r.source_ids and len(set(r.source_ids))==len(r.source_ids)
            and all(x in self._sources and self._valid_source(self._sources[x]) for x in r.source_ids)
            and r.digest==self.requirement_digest(**p))

    def _registry_integrity(self):
        if any(k!=s.source_id or not self._valid_source(s) for k,s in self._sources.items()): return False
        if any(k!=r.requirement_id or not self._valid_requirement(r) for k,r in self._requirements.items()): return False
        controls=[x for r in self._requirements.values() for x in r.control_ids]
        return len(controls)==len(set(controls))

    def _rfc_integrity(self):
        latest={}; versions={}; previous={}
        for row in self._history:
            reqs=[self._requirements.get(x) for x in row.requirement_ids]
            controls={n for req in reqs if req is not None for n in req.control_ids}
            sources=tuple(sorted({s for r in reqs if r for s in r.source_ids}))
            expected_text=(PLAIN_TEMPLATES["RECORDED" if row.status==MAXIMUM_STATE else row.status],"운영자 승인이 있어야 다음 단계로 갈 수 있습니다.")
            prior=latest.get(row.rfc_id); transition=(prior is None and row.version==1 and row.status=="DRAFTED") or (prior and ((prior.status=="DRAFTED" and row.status in {"REVIEWED","HELD"}) or (prior.status=="REVIEWED" and row.status in {MAXIMUM_STATE,"HELD"}) or (prior.status==MAXIMUM_STATE and row.status=="HELD")))
            p={k:v for k,v in row.__dict__.items() if k!="digest"}
            if (not transition or row.version!=versions.get(row.rfc_id,0)+1 or row.previous_digest!=previous.get(row.rfc_id)
                or any(r is None for r in reqs) or controls!=set(range(3101,3501))
                or row.source_ids!=sources or row.plain_summary!=expected_text
                or not _syn(row.rfc_id,"p0-rfc") or not _syn(row.author,"rfc-author") or row.digest!=self.rfc_digest(**p)): return False
            latest[row.rfc_id]=row; versions[row.rfc_id]=row.version; previous[row.rfc_id]=row.digest
        expected={rid:row.rfc_id for row in self._history if row.version==1 for rid in row.requirement_ids}
        return latest==self._rfcs and expected==self._members

    def _artifact_integrity(self):
        history={(r.rfc_id,r.version):r for r in self._history}
        for k,a in self._reviews.items():
            p={x:y for x,y in a.__dict__.items() if x!="digest"}; src=history.get((a.rfc_id,a.source_version)); out=history.get((a.rfc_id,a.source_version+1))
            if (k!=a.review_id or self._rfc_reviews.get(a.rfc_id)!=k or src is None or out is None
                or src.status!="DRAFTED" or out.status!=("REVIEWED" if a.accepted else "HELD")
                or not _syn(a.review_id,"rfc-review") or not _syn(a.reviewer,"rfc-reviewer")
                or not isinstance(a.accepted,bool) or not _hex(a.finding_digest)
                or a.rfc_digest!=src.digest or _identity(a.reviewer) in {_identity(src.author)}
                or a.digest!=canonical_digest(p)): return False
        for k,a in self._receipts.items():
            p={x:y for x,y in a.__dict__.items() if x!="digest"}; rev=self._reviews.get(self._rfc_reviews.get(a.rfc_id,"")); src=history.get((a.rfc_id,a.source_version)); out=history.get((a.rfc_id,a.source_version+1))
            if (k!=a.receipt_id or self._rfc_receipts.get(a.rfc_id)!=k or rev is None or not rev.accepted
                or src is None or out is None or src.status!="REVIEWED" or out.status!=MAXIMUM_STATE
                or not _syn(a.receipt_id,"rfc-receipt") or not _syn(a.verifier,"rfc-verifier")
                or a.source_version!=rev.source_version+1 or a.review_digest!=rev.digest
                or _identity(a.verifier) in {_identity(src.author),_identity(rev.reviewer)}
                or not a.operator_approval_required or a.approval_recorded
                or a.digest!=canonical_digest(p)): return False
        return True

    def _chain_integrity(self):
        prev=None
        if len(self._events)!=len(self._history): return False
        actions={"DRAFTED":"RFC_DRAFTED","REVIEWED":"RFC_REVIEWED","HELD":"RFC_HELD",MAXIMUM_STATE:"RFC_RECEIPT_RECORDED"}
        for i,(e,r) in enumerate(zip(self._events,self._history),1):
            p=dict(sequence=i,action=e.get("action"),rfc_digest=r.digest,attachment_digest=e.get("attachment_digest"),previous_digest=prev)
            attachment=e.get("attachment_digest")
            if r.status=="DRAFTED": expected=None
            elif r.status=="REVIEWED":
                artifact=self._reviews.get(self._rfc_reviews.get(r.rfc_id,"")); expected=artifact.digest if artifact else None
            elif r.status==MAXIMUM_STATE:
                artifact=self._receipts.get(self._rfc_receipts.get(r.rfc_id,"")); expected=artifact.digest if artifact else None
            else:
                hold=next((x for x in self._holds if x.get("rfc_digest")==r.digest),None); expected=hold.get("attachment_digest") if hold else None
            if e.get("action")!=actions[r.status] or attachment!=expected or e!={**p,"digest":canonical_digest(p)}: return False
            prev=e["digest"]
        prev=None
        for i,h in enumerate(self._holds,1):
            p={k:h.get(k) for k in ("sequence","rfc_id","actor","reason","rfc_digest","attachment_digest","previous_digest")}
            row=next((x for x in self._history if x.digest==h.get("rfc_digest")),None)
            if h.get("reason")=="REVIEW_REJECTED":
                review=self._reviews.get(self._rfc_reviews.get(str(h.get("rfc_id")),"")); semantic=review is not None and not review.accepted and h.get("actor")==review.reviewer and h.get("attachment_digest")==review.digest
            elif h.get("reason")=="AUDIT_FINDING":
                semantic=row is not None and _syn(h.get("actor"),"rfc-auditor") and _identity(h.get("actor")) not in self._roles(row) and _hex(h.get("attachment_digest"))
            else: semantic=False
            if h.get("sequence")!=i or h.get("previous_digest")!=prev or not semantic or h!={**p,"digest":canonical_digest(p)}: return False
            prev=h["digest"]
        return True
    def _integrity(self): return self._registry_integrity() and self._rfc_integrity() and self._artifact_integrity() and self._chain_integrity()

    def evidence(self):
        observed=[n for a,b,_ in WORKSTREAMS for n in range(a,b+1)]
        matrix=len(WORKSTREAMS)==16 and observed==list(range(3101,3501)) and all(b-a==24 for a,b,_ in WORKSTREAMS)
        claimed={n for r in self._requirements.values() for n in r.control_ids}
        coverage=claimed==set(range(3101,3501))
        checks={"control_matrix":matrix,"coverage":coverage,"registry":self._registry_integrity(),"rfc":self._rfc_integrity(),"artifact":self._artifact_integrity(),"append_only":self._chain_integrity()}; gaps=tuple(k for k,v in checks.items() if not v)
        return {"control_range":[3101,3500],"control_count":400,"workstream_count":16,"workstreams":list(WORKSTREAM_NAMES),
            "exactly_25_controls_per_workstream":all(b-a==24 for a,b,_ in WORKSTREAMS),"control_matrix_valid":matrix,
            "requirement_coverage_complete":coverage,
            "source_count":len(self._sources),"requirement_count":len(self._requirements),"rfc_count":len(self._rfcs),
            "registry_integrity_valid":checks["registry"],"rfc_integrity_valid":checks["rfc"],"artifact_integrity_valid":checks["artifact"],"append_only_chain_valid":checks["append_only"],"integrity_valid":all(checks.values()),
            "capability_ready":not gaps,"capability_gap_evidence":{"fail_closed":bool(gaps),"gaps":gaps},"maximum_review_batch":20,
            "fixed_plain_language":True,"free_prompt_generation":False,"operator_approval_required":True,"approval_recorded":False,
            "non_authorizing":True,"non_deployable":True,"external_calls":0,"external_pg_calls":0,"ledger_writes":0,"ui_generation":0,"runtime_policy_mutations":0,"maximum_state":MAXIMUM_STATE}
