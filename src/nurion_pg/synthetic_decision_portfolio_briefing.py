"""Synthetic, non-authorizing decision portfolio briefing controls #2901-#3100."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest
from .synthetic_feasibility_decision_portfolio import (
    DECISIONS, MAXIMUM_STATE as SOURCE_RECORDED, DecisionPortfolio,
    SyntheticFeasibilityDecisionPortfolio,
)

WORKSTREAMS = (
    (2901, 2925, "TYPED_PORTFOLIO_BOUNDARY"),
    (2926, 2950, "FIXED_PLAIN_LANGUAGE_TEMPLATE"),
    (2951, 2975, "SOURCE_DIGEST_VERSION_BINDING"),
    (2976, 3000, "BOUNDED_DISTRIBUTION_TRACE"),
    (3001, 3025, "OPERATOR_ACTION_BOUNDARY"),
    (3026, 3050, "INDEPENDENT_BRIEFING_REVIEW"),
    (3051, 3075, "REPLAY_CONFLICT_CONCURRENCY"),
    (3076, 3100, "APPEND_ONLY_CAPABILITY_EVIDENCE"),
)
MAX_BRIEFING_BATCH = 20
MAXIMUM_STATE = "SYNTHETIC_BRIEFING_RECORDED"
SOURCE_STATES = frozenset({SOURCE_RECORDED, "HELD"})
STATUS_TEXT = {SOURCE_RECORDED: "검증 기록 완료", "HELD": "추가 확인을 위해 보류"}
DECISION_TEXT = {"HOLD": "보류", "OBSERVE": "관찰", "REASSESS": "재검토"}
HOLD_TEXT = {"REVIEW_REJECTED": "독립 검토에서 보완 필요",
             "INTEGRITY_FINDING": "무결성 확인에서 보완 필요"}


def _synthetic(value: object, namespace: str) -> bool:
    return isinstance(value, str) and value.startswith(f"synthetic:{namespace}:")


def _digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _identity(value: str) -> str:
    return value.rsplit(":", 1)[-1]


def _count(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 400


@dataclass(frozen=True)
class BriefingSource:
    portfolio_id: str
    source_version: int
    source_digest: str
    status: str
    curator: str
    docket_ids: tuple[str, ...]
    decision_counts: tuple[tuple[str, int], ...]
    recorded_count: int
    held_count: int
    related_trace_digest: str
    digest: str


@dataclass(frozen=True)
class BriefingPacket:
    briefing_id: str
    author: str
    source_ids: tuple[str, ...]
    status_counts: tuple[tuple[str, int], ...]
    decision_counts: tuple[tuple[str, int], ...]
    evidence_link_ids: tuple[str, ...]
    plain_status: tuple[str, ...]
    plain_decisions: tuple[str, ...]
    plain_holds: tuple[str, ...]
    operator_action_required: bool
    approval_recorded: bool
    status: str
    version: int
    previous_digest: str | None
    digest: str


@dataclass(frozen=True)
class BriefingReview:
    review_id: str; briefing_id: str; source_version: int; reviewer: str
    accepted: bool; finding_digest: str; briefing_digest: str; digest: str


@dataclass(frozen=True)
class BriefingReceipt:
    receipt_id: str; briefing_id: str; source_version: int; verifier: str
    review_digest: str; operator_action_required: bool; approval_recorded: bool; digest: str


class SyntheticDecisionPortfolioBriefing:
    """Thread-safe in-memory briefing registry with no approval or execution capability."""

    def __init__(self) -> None:
        self._sources: dict[str, BriefingSource] = {}
        self._packets: dict[str, BriefingPacket] = {}
        self._members: dict[str, str] = {}
        self._history: list[BriefingPacket] = []
        self._events: list[dict[str, object]] = []
        self._reviews: dict[str, BriefingReview] = {}
        self._packet_reviews: dict[str, str] = {}
        self._receipts: dict[str, BriefingReceipt] = {}
        self._packet_receipts: dict[str, str] = {}
        self._holds: list[dict[str, object]] = []
        self._lock = RLock()

    @staticmethod
    def _source_digest(row: DecisionPortfolio) -> str:
        return SyntheticFeasibilityDecisionPortfolio._portfolio_digest(
            row.portfolio_id, row.curator, row.requested_limit, row.docket_ids,
            row.decision_counts, row.recorded_count, row.held_count, row.status,
            row.version, row.previous_digest)

    @staticmethod
    def _packet_digest(briefing_id, author, source_ids, status_counts, decision_counts,
                       evidence_link_ids, plain_status, plain_decisions, plain_holds,
                       operator_action_required, approval_recorded, status, version,
                       previous_digest):
        return canonical_digest(locals())

    def intake(self, row: DecisionPortfolio) -> BriefingSource:
        if not isinstance(row, DecisionPortfolio):
            raise GovernanceRejected("typed decision portfolio required")
        if (not _synthetic(row.portfolio_id, "decision-portfolio") or row.status not in SOURCE_STATES
                or row.version < 1 or not (1 <= len(row.docket_ids) <= MAX_BRIEFING_BATCH)
                or not (len(row.docket_ids) <= row.requested_limit <= MAX_BRIEFING_BATCH)
                or len(set(row.docket_ids)) != len(row.docket_ids)
                or not _synthetic(row.curator, "portfolio-curator")
                or tuple(key for key, _ in row.decision_counts) != tuple(sorted(DECISIONS))
                or not all(_count(value) for _, value in row.decision_counts)
                or sum(value for _, value in row.decision_counts) != len(row.docket_ids)
                or not _count(row.recorded_count) or not _count(row.held_count)
                or row.recorded_count + row.held_count != len(row.docket_ids)
                or not _digest(row.digest) or row.digest != self._source_digest(row)):
            raise GovernanceRejected("integral terminal decision portfolio required")
        trace = canonical_digest({"portfolio_id": row.portfolio_id, "members": row.docket_ids})
        payload = {"portfolio_id": row.portfolio_id, "source_version": row.version,
            "source_digest": row.digest, "status": row.status, "curator": row.curator,
            "docket_ids": row.docket_ids, "decision_counts": row.decision_counts,
            "recorded_count": row.recorded_count, "held_count": row.held_count,
            "related_trace_digest": trace}
        source = BriefingSource(**payload, digest=canonical_digest(payload))
        with self._lock:
            prior = self._sources.get(row.portfolio_id)
            if prior is not None:
                if prior == source: return prior
                raise GovernanceRejected("briefing source conflict")
            self._sources[row.portfolio_id] = source
            return source

    def _append(self, action: str, row: BriefingPacket, attachment=None):
        previous = self._events[-1]["digest"] if self._events else None
        event = {"sequence": len(self._events)+1, "action": action,
                 "briefing_digest": row.digest, "attachment_digest": attachment,
                 "previous_digest": previous}
        self._history.append(row); self._events.append({**event, "digest": canonical_digest(event)})
        self._packets[row.briefing_id] = row
        return row

    def _transition(self, old, action, status, attachment):
        values = dict(old.__dict__); values.update(status=status, version=old.version+1,
                                                   previous_digest=old.digest)
        values["digest"] = self._packet_digest(**{k: values[k] for k in values if k != "digest"})
        return self._append(action, BriefingPacket(**values), attachment)

    def author(self, briefing_id: str, author: str, limit: int) -> BriefingPacket:
        if (not _synthetic(briefing_id, "portfolio-briefing")
                or not _synthetic(author, "briefing-author")
                or not isinstance(limit, int) or isinstance(limit, bool)
                or not 1 <= limit <= MAX_BRIEFING_BATCH):
            raise GovernanceRejected("bounded synthetic briefing required")
        with self._lock:
            prior = self._packets.get(briefing_id)
            if prior is not None:
                if prior.author == author and len(prior.source_ids) <= limit: return prior
                raise GovernanceRejected("briefing conflict")
            selected = sorted((s for k, s in self._sources.items() if k not in self._members),
                              key=lambda s: s.portfolio_id)[:limit]
            if not selected or any(_identity(s.curator) == _identity(author) for s in selected):
                raise GovernanceRejected("unassigned sources and independent author required")
            ids = tuple(s.portfolio_id for s in selected)
            statuses = tuple((key, sum(s.status == key for s in selected)) for key in sorted(SOURCE_STATES))
            decisions = tuple((key, sum(dict(s.decision_counts)[key] for s in selected))
                              for key in sorted(DECISIONS))
            links = tuple(f"evidence:{canonical_digest({'id': s.portfolio_id, 'digest': s.source_digest})[:24]}"
                          for s in selected)
            plain_status = tuple(f"{STATUS_TEXT[key]}: {value}건" for key, value in statuses if value)
            plain_decisions = tuple(f"{DECISION_TEXT[key]}: {value}건" for key, value in decisions if value)
            hold_reasons = ("추가 확인이 필요한 항목이 있습니다.",) if any(s.held_count for s in selected) else ()
            base = dict(briefing_id=briefing_id, author=author, source_ids=ids,
                status_counts=statuses, decision_counts=decisions, evidence_link_ids=links,
                plain_status=plain_status, plain_decisions=plain_decisions, plain_holds=hold_reasons,
                operator_action_required=True, approval_recorded=False, status="DRAFTED",
                version=1, previous_digest=None)
            row = BriefingPacket(**base, digest=self._packet_digest(**base))
            for source in selected: self._members[source.portfolio_id] = briefing_id
            return self._append("BRIEFING_DRAFTED", row)

    def _roles(self, row):
        roles = {_identity(row.author)} | {_identity(self._sources[x].curator) for x in row.source_ids}
        review = self._reviews.get(self._packet_reviews.get(row.briefing_id, ""))
        receipt = self._receipts.get(self._packet_receipts.get(row.briefing_id, ""))
        if review: roles.add(_identity(review.reviewer))
        if receipt: roles.add(_identity(receipt.verifier))
        return roles

    def review(self, review_id, briefing_id, expected_version, reviewer, accepted, finding_digest):
        if (not _synthetic(review_id, "briefing-review") or not _synthetic(reviewer, "briefing-reviewer")
                or not isinstance(accepted, bool) or not _digest(finding_digest)):
            raise GovernanceRejected("valid briefing review required")
        with self._lock:
            prior = self._reviews.get(review_id)
            fields = (briefing_id, expected_version, reviewer, accepted, finding_digest)
            if prior:
                if fields == (prior.briefing_id, prior.source_version, prior.reviewer, prior.accepted, prior.finding_digest):
                    return self._packets[briefing_id]
                raise GovernanceRejected("briefing review conflict")
            old = self._packets.get(briefing_id)
            if (old is None or old.status != "DRAFTED" or old.version != expected_version
                    or briefing_id in self._packet_reviews or _identity(reviewer) in self._roles(old)
                    or not self._integrity()):
                raise GovernanceRejected("current integral briefing required")
            payload = dict(review_id=review_id, briefing_id=briefing_id, source_version=expected_version,
                reviewer=reviewer, accepted=accepted, finding_digest=finding_digest, briefing_digest=old.digest)
            artifact = BriefingReview(**payload, digest=canonical_digest(payload))
            self._reviews[review_id] = artifact; self._packet_reviews[briefing_id] = review_id
            row = self._transition(old, "BRIEFING_REVIEWED" if accepted else "BRIEFING_HELD",
                                   "REVIEWED" if accepted else "HELD", artifact.digest)
            if not accepted: self._append_hold(row, reviewer, "REVIEW_REJECTED", artifact.digest)
            return row

    def record(self, receipt_id, briefing_id, expected_version, review_digest, verifier):
        if (not _synthetic(receipt_id, "briefing-receipt") or not _synthetic(verifier, "briefing-verifier")
                or not _digest(review_digest)):
            raise GovernanceRejected("valid briefing receipt required")
        with self._lock:
            prior = self._receipts.get(receipt_id)
            fields = (briefing_id, expected_version, verifier, review_digest)
            if prior:
                if fields == (prior.briefing_id, prior.source_version, prior.verifier, prior.review_digest):
                    return self._packets[briefing_id]
                raise GovernanceRejected("briefing receipt conflict")
            old = self._packets.get(briefing_id); review = self._reviews.get(self._packet_reviews.get(briefing_id, ""))
            if (old is None or old.status != "REVIEWED" or old.version != expected_version
                    or briefing_id in self._packet_receipts or review is None or not review.accepted
                    or review.digest != review_digest or _identity(verifier) in self._roles(old)
                    or not self._integrity()):
                raise GovernanceRejected("reviewed current briefing required")
            payload = dict(receipt_id=receipt_id, briefing_id=briefing_id, source_version=expected_version,
                verifier=verifier, review_digest=review_digest, operator_action_required=True,
                approval_recorded=False)
            receipt = BriefingReceipt(**payload, digest=canonical_digest(payload))
            self._receipts[receipt_id] = receipt; self._packet_receipts[briefing_id] = receipt_id
            return self._transition(old, "BRIEFING_RECEIPT_RECORDED", MAXIMUM_STATE, receipt.digest)

    def _append_hold(self, row, actor, reason, attachment):
        previous = self._holds[-1]["digest"] if self._holds else None
        payload = dict(sequence=len(self._holds)+1, briefing_id=row.briefing_id, actor=actor,
                       reason=reason, briefing_digest=row.digest, attachment_digest=attachment,
                       previous_digest=previous)
        self._holds.append({**payload, "digest": canonical_digest(payload)})

    def audit_hold(self, briefing_id, expected_version, auditor, finding_digest):
        if not _synthetic(auditor, "briefing-auditor") or not _digest(finding_digest):
            raise GovernanceRejected("valid independent auditor required")
        with self._lock:
            old = self._packets.get(briefing_id)
            if (old is None or old.status == "HELD" or old.version != expected_version
                    or _identity(auditor) in self._roles(old) or not self._integrity()):
                raise GovernanceRejected("current integral briefing required")
            row = self._transition(old, "BRIEFING_HELD", "HELD", finding_digest)
            self._append_hold(row, auditor, "INTEGRITY_FINDING", finding_digest)
            return row

    def review_artifact(self, review_id): return self._reviews[review_id]

    def _source_integrity(self):
        for key, s in self._sources.items():
            payload = {k: v for k, v in s.__dict__.items() if k != "digest"}
            if (key != s.portfolio_id or s.status not in SOURCE_STATES or not _digest(s.source_digest)
                    or not 1 <= len(s.docket_ids) <= MAX_BRIEFING_BATCH
                    or len(set(s.docket_ids)) != len(s.docket_ids)
                    or not _synthetic(s.portfolio_id, "decision-portfolio")
                    or not _synthetic(s.curator, "portfolio-curator")
                    or tuple(k for k, _ in s.decision_counts) != tuple(sorted(DECISIONS))
                    or not all(_count(v) for _, v in s.decision_counts)
                    or sum(v for _, v in s.decision_counts) != len(s.docket_ids)
                    or not _count(s.recorded_count) or not _count(s.held_count)
                    or s.recorded_count+s.held_count != len(s.docket_ids)
                    or s.related_trace_digest != canonical_digest({"portfolio_id": s.portfolio_id, "members": s.docket_ids})
                    or s.digest != canonical_digest(payload)): return False
        return True

    def _packet_integrity(self):
        latest = {}; versions = {}; previous = {}
        for row in self._history:
            sources = [self._sources.get(x) for x in row.source_ids]
            statuses = tuple((k, sum(s is not None and s.status == k for s in sources)) for k in sorted(SOURCE_STATES))
            decisions = tuple((k, sum(dict(s.decision_counts)[k] for s in sources if s)) for k in sorted(DECISIONS))
            links = tuple(f"evidence:{canonical_digest({'id': s.portfolio_id, 'digest': s.source_digest})[:24]}" for s in sources if s)
            plain_status = tuple(f"{STATUS_TEXT[key]}: {value}건" for key, value in statuses if value)
            plain_decisions = tuple(f"{DECISION_TEXT[key]}: {value}건" for key, value in decisions if value)
            plain_holds = (("추가 확인이 필요한 항목이 있습니다.",)
                           if any(s and s.held_count for s in sources) else ())
            prior = latest.get(row.briefing_id)
            valid_transition = ((prior is None and row.version == 1 and row.status == "DRAFTED") or
                (prior is not None and ((prior.status == "DRAFTED" and row.status in {"REVIEWED", "HELD"})
                 or (prior.status == "REVIEWED" and row.status in {MAXIMUM_STATE, "HELD"})
                 or (prior.status == MAXIMUM_STATE and row.status == "HELD"))))
            payload = {k: v for k, v in row.__dict__.items() if k != "digest"}
            if (not valid_transition or row.version != versions.get(row.briefing_id, 0)+1
                    or row.previous_digest != previous.get(row.briefing_id) or any(s is None for s in sources)
                    or not 1 <= len(sources) <= MAX_BRIEFING_BATCH or len(set(row.source_ids)) != len(sources)
                    or row.status_counts != statuses or row.decision_counts != decisions
                    or row.evidence_link_ids != links or row.plain_status != plain_status
                    or row.plain_decisions != plain_decisions or row.plain_holds != plain_holds
                    or not _synthetic(row.briefing_id, "portfolio-briefing")
                    or not _synthetic(row.author, "briefing-author")
                    or any(_identity(row.author) == _identity(s.curator) for s in sources)
                    or not row.operator_action_required or row.approval_recorded
                    or row.digest != self._packet_digest(**payload)): return False
            latest[row.briefing_id] = row; versions[row.briefing_id] = row.version; previous[row.briefing_id] = row.digest
        expected = {sid: row.briefing_id for row in self._history if row.version == 1 for sid in row.source_ids}
        return latest == self._packets and expected == self._members

    def _artifact_integrity(self):
        history = {(row.briefing_id, row.version): row for row in self._history}
        for key, r in self._reviews.items():
            payload = {k: v for k, v in r.__dict__.items() if k != "digest"}
            source = history.get((r.briefing_id, r.source_version))
            result = history.get((r.briefing_id, r.source_version + 1))
            if (key != r.review_id or self._packet_reviews.get(r.briefing_id) != key
                    or source is None or source.status != "DRAFTED" or result is None
                    or result.status != ("REVIEWED" if r.accepted else "HELD")
                    or r.briefing_digest != source.digest or not _synthetic(r.reviewer, "briefing-reviewer")
                    or not isinstance(r.accepted, bool) or not _digest(r.finding_digest)
                    or _identity(r.reviewer) in ({_identity(source.author)} |
                        {_identity(self._sources[x].curator) for x in source.source_ids})
                    or r.digest != canonical_digest(payload)): return False
        for key, r in self._receipts.items():
            payload = {k: v for k, v in r.__dict__.items() if k != "digest"}
            review = self._reviews.get(self._packet_reviews.get(r.briefing_id, ""))
            result = history.get((r.briefing_id, r.source_version + 1))
            source = history.get((r.briefing_id, r.source_version))
            if (key != r.receipt_id or self._packet_receipts.get(r.briefing_id) != key
                    or review is None or not review.accepted or r.review_digest != review.digest
                    or r.source_version != review.source_version + 1
                    or source is None or source.status != "REVIEWED" or result is None
                    or result.status != MAXIMUM_STATE or not _synthetic(r.verifier, "briefing-verifier")
                    or _identity(r.verifier) in ({_identity(source.author), _identity(review.reviewer)} |
                        {_identity(self._sources[x].curator) for x in source.source_ids})
                    or not r.operator_action_required or r.approval_recorded
                    or r.digest != canonical_digest(payload)): return False
        return True

    def _chain_integrity(self):
        previous = None
        if len(self._events) != len(self._history): return False
        for i, (event, row) in enumerate(zip(self._events, self._history), 1):
            expected_attachment = None
            if row.status == "REVIEWED":
                review = self._reviews.get(self._packet_reviews.get(row.briefing_id, ""))
                expected_attachment = review.digest if review else None
            elif row.status == MAXIMUM_STATE:
                receipt = self._receipts.get(self._packet_receipts.get(row.briefing_id, ""))
                expected_attachment = receipt.digest if receipt else None
            elif row.status == "HELD":
                hold = next((item for item in self._holds
                    if item.get("briefing_digest") == row.digest), None)
                expected_attachment = hold.get("attachment_digest") if hold else None
            payload = dict(sequence=i, action=event.get("action"), briefing_digest=row.digest,
                           attachment_digest=event.get("attachment_digest"), previous_digest=previous)
            expected_action = {"DRAFTED":"BRIEFING_DRAFTED", "REVIEWED":"BRIEFING_REVIEWED",
                "HELD":"BRIEFING_HELD", MAXIMUM_STATE:"BRIEFING_RECEIPT_RECORDED"}.get(row.status)
            if (event.get("action") != expected_action
                    or event.get("attachment_digest") != expected_attachment
                    or event != {**payload, "digest": canonical_digest(payload)}): return False
            previous = event["digest"]
        previous = None
        for i, hold in enumerate(self._holds, 1):
            payload = {k: hold.get(k) for k in ("sequence", "briefing_id", "actor", "reason",
                "briefing_digest", "attachment_digest", "previous_digest")}
            row = next((item for item in self._history
                        if item.digest == hold.get("briefing_digest")), None)
            if hold.get("reason") == "REVIEW_REJECTED":
                review = self._reviews.get(self._packet_reviews.get(str(hold.get("briefing_id")), ""))
                semantic = (review is not None and not review.accepted
                    and hold.get("actor") == review.reviewer
                    and hold.get("attachment_digest") == review.digest)
            elif hold.get("reason") == "INTEGRITY_FINDING":
                semantic = (row is not None and _synthetic(hold.get("actor"), "briefing-auditor")
                    and _identity(str(hold.get("actor"))) not in self._roles(row)
                    and _digest(hold.get("attachment_digest")))
            else:
                semantic = False
            if (hold.get("sequence") != i or not semantic
                    or hold.get("previous_digest") != previous
                    or hold != {**payload, "digest": canonical_digest(payload)}): return False
            previous = hold["digest"]
        return True

    def _integrity(self): return self._source_integrity() and self._packet_integrity() and self._artifact_integrity() and self._chain_integrity()

    def evidence(self):
        observed = [n for start, end, _ in WORKSTREAMS for n in range(start, end+1)]
        matrix = len(WORKSTREAMS)==8 and observed == list(range(2901, 3101)) and all(e-s==24 for s,e,_ in WORKSTREAMS)
        checks = {"control_matrix": matrix, "source": self._source_integrity(),
                  "briefing": self._packet_integrity(), "artifact": self._artifact_integrity(),
                  "append_only": self._chain_integrity()}
        gaps = tuple(k for k,v in checks.items() if not v)
        return {"control_range":[2901,3100], "control_count":200, "workstream_count":8,
            "exactly_25_controls_per_workstream": all(e-s==24 for s,e,_ in WORKSTREAMS),
            "workstreams":[x for _,_,x in WORKSTREAMS], "control_matrix_valid":matrix,
            "maximum_batch":MAX_BRIEFING_BATCH, "source_count":len(self._sources),
            "briefing_count":len(self._packets), "source_integrity_valid":checks["source"],
            "briefing_integrity_valid":checks["briefing"], "artifact_integrity_valid":checks["artifact"],
            "append_only_chain_valid":checks["append_only"], "integrity_valid":all(checks.values()),
            "capability_ready":not gaps, "capability_gap_evidence":{"fail_closed":bool(gaps),"gaps":gaps},
            "fixed_template":True, "free_prompt_generation":False, "external_url_calls":0,
            "operator_action_required":True, "approval_recorded":False,
            "maximum_state":MAXIMUM_STATE, "non_authorizing":True, "non_executable":True,
            "external_calls":0, "ledger_writes":0, "runtime_policy_mutations":0}
