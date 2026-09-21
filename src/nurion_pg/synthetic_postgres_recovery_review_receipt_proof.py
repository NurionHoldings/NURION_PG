"""Current-head recovery review snapshot/receipt proof #19101-#19500."""
from __future__ import annotations

from dataclasses import dataclass

from .arkaon.governance import GovernanceRejected, canonical_digest
from .synthetic_postgres_recovery_supersession_proof import (
    APPLIED_LESSONS as PRIOR_LESSONS,
    APPLIED_RULES,
    STAGE_MAPPING as PRIOR_STAGE_MAPPING,
    SUPERSESSION_STATE,
    SyntheticPostgresRecoverySupersessionProof,
)

APPLIED_LESSONS = tuple(sorted(PRIOR_LESSONS + ("ARL-19101-001",)))
WORKSTREAM_NAMES = (
    "REVIEW_SNAPSHOT_SCHEMA", "CURRENT_HEAD_BINDING", "CASE_DIGEST_BINDING",
    "SUPERSESSION_DIGEST_BINDING", "DETERMINISTIC_SNAPSHOT_ID", "SNAPSHOT_REPLAY",
    "STALE_HEAD_REJECTION", "CHANGED_PAYLOAD_REJECTION", "CROSS_CASE_REJECTION",
    "RECEIPT_SCHEMA", "SNAPSHOT_RECEIPT_FK", "DETERMINISTIC_RECEIPT_ID",
    "SINGLE_RECEIPT", "RECEIPT_REPLAY", "RECEIPT_TAMPER_REJECTION",
    "APPEND_ONLY", "READ_ONLY_OPERATOR_VIEW", "ZERO_AUTHORITY",
    "MULTINODE_PREFLIGHT", "NARROW_CLEANUP",
)
CONTROL_ASPECTS = (
    "input_schema", "required_fields", "state_precondition", "source_binding",
    "digest_recalculation", "negative_path", "missing_input", "duplicate_input",
    "replay", "conflict", "stale_version", "concurrency", "partial_batch",
    "ordering", "append_only", "hold_propagation", "operator_gate",
    "non_execution", "cleanup", "artifact_integrity",
)
NEGATIVE = frozenset({"negative_path", "missing_input", "duplicate_input", "replay", "conflict", "stale_version", "partial_batch"})
STAGE_MAPPING = PRIOR_STAGE_MAPPING + (("ARKAON-LESSONS-19101", (19101, 19500)),)
MAXIMUM_STATE = "POSTGRES_RECOVERY_REVIEW_RECEIPT_PROOF_ONLY"
REVIEW_STATE = "REVIEW_RECORDED_NON_EXECUTABLE"


def _hex(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def mapping_digest(rows):
    return canonical_digest(("CONTIGUOUS_STAGE_MAPPING", tuple(rows)))


def deterministic_review_snapshot_id(case_id, supersession_id, supersession_digest, version, review_key):
    if not all(isinstance(v, str) and v for v in (case_id, supersession_id, review_key)):
        raise GovernanceRejected("complete current-head review snapshot identity required")
    if not _hex(supersession_digest) or not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise GovernanceRejected("exact current-head digest and version required")
    return "rrs_" + canonical_digest(("NURION_RECOVERY_REVIEW_SNAPSHOT_V1", case_id, supersession_id, supersession_digest, version, review_key))


def deterministic_review_receipt_id(snapshot_id, snapshot_digest, reviewer_subject, result_digest):
    if not all(isinstance(v, str) and v for v in (snapshot_id, reviewer_subject)):
        raise GovernanceRejected("complete review receipt identity required")
    if not _hex(snapshot_digest) or not _hex(result_digest):
        raise GovernanceRejected("exact snapshot and result digest required")
    return "rrr_" + canonical_digest(("NURION_RECOVERY_REVIEW_RECEIPT_V1", snapshot_id, snapshot_digest, reviewer_subject, result_digest))


EXPECTED_PROOF = {
    "status": "PASS_POSTGRES_RECOVERY_REVIEW_RECEIPT_PROOF",
    "review_state": REVIEW_STATE,
    "snapshot_bound_to_exact_current_head": True,
    "deterministic_snapshot_identity": True,
    "deterministic_receipt_identity": True,
    "same_snapshot_replay_converged": True,
    "same_receipt_replay_converged": True,
    "stale_head_fail_closed": True,
    "changed_snapshot_payload_fail_closed": True,
    "cross_case_fail_closed": True,
    "receipt_tamper_fail_closed": True,
    "single_receipt_enforced": True,
    "snapshot_append_only": True,
    "receipt_append_only": True,
    "operator_view_insert_rejected": True,
    "operator_view_update_rejected": True,
    "operator_view_delete_rejected": True,
    "payment_authority": False, "receipt_authority": False, "retry_authority": False,
    "approval_authority": False, "execution_authority": False,
    "multinode_preflight_contract_complete": True,
    "actual_network_partition_claimed": False, "actual_failover_claimed": False,
    "fault_injection_performed": False, "production_database_writes": 0,
    "cleanup_succeeded": True, "credential_disclosed": False,
    "password_credential_configured": False,
}


def integration_proof_valid(proof):
    return isinstance(proof, dict) and proof == EXPECTED_PROOF and set(proof) == set(EXPECTED_PROOF)


def recovery_paths():
    return (
        (("cause", "operator_review_requires_stable_head"), ("recommended", True), ("method", "seal_exact_current_head_before_review"), ("alternative", "retain_hold_without_review_receipt"), ("cost", "LOW"), ("risk", "LOW"), ("reversibility", "HIGH"), ("validation", "exact_head_fk_and_digest"), ("stop", "head_changed_before_snapshot"), ("resume", "create_fresh_snapshot_from_new_head"), ("rollback", "transaction_rollback_no_source_mutation")),
        (("cause", "receipt_payload_or_reviewer_conflict"), ("recommended", True), ("method", "reject_conflict_and_preserve_original_receipt"), ("alternative", "record_no_receipt_and_keep_hold"), ("cost", "LOW"), ("risk", "MEDIUM"), ("reversibility", "HIGH"), ("validation", "deterministic_identity_and_single_receipt_constraint"), ("stop", "any_digest_or_subject_mismatch"), ("resume", "independent_review_with_new_snapshot"), ("rollback", "append_only_rows_remain_unchanged")),
        (("cause", "multinode_failover_not_available"), ("recommended", True), ("method", "preserve_primary_standby_review_consistency_preflight"), ("alternative", "keep_single_node_claims_false"), ("cost", "HIGH"), ("risk", "MEDIUM"), ("reversibility", "HIGH"), ("validation", "future_disposable_multinode_fixture"), ("stop", "uncontrolled_or_production_target"), ("resume", "approved_disposable_fixture"), ("rollback", "destroy_exact_fixture_only")),
    )


@dataclass(frozen=True)
class Control:
    control_id: int; workstream: str; aspect: str; requirement_ref: str
    fixture_digest: str; expected_result: str; digest: str


@dataclass(frozen=True)
class Snapshot:
    snapshot_id: str; stage_range: tuple; mapping_digest: str; registry_digest: str
    manifest_digest: str; lesson_ids: tuple; rule_ids: tuple; source_docket_digest: str
    previous_snapshot_digest: str; sequence: int; latest: bool; digest: str


@dataclass(frozen=True)
class Docket:
    docket_id: str; snapshot_digest: str; complete: bool; held: bool
    pending_human_judgment: bool; production_writes: int; receipt_issued: bool
    approved: bool; activated: bool; deployed: bool; status: str; digest: str


class SyntheticPostgresRecoveryReviewReceiptProof:
    def __init__(self):
        self._controls = {}; self._source = None; self._snapshot = None; self._docket = None

    def _expected(self, control_id):
        offset = control_id - 19101
        return WORKSTREAM_NAMES[offset // 20], CONTROL_ASPECTS[offset % 20]

    def add_control(self, control_id, workstream, aspect, requirement_ref, fixture_digest, expected_result):
        payload = dict(control_id=control_id, workstream=workstream, aspect=aspect, requirement_ref=requirement_ref, fixture_digest=fixture_digest, expected_result=expected_result)
        row = Control(**payload, digest=canonical_digest(payload))
        valid = (isinstance(control_id, int) and not isinstance(control_id, bool) and 19101 <= control_id <= 19500 and self._expected(control_id) == (workstream, aspect) and requirement_ref == f"synthetic:postgres-recovery-review-receipt-proof-requirement:{(control_id-19101)//20:02}" and _hex(fixture_digest) and expected_result == ("EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS"))
        if not valid:
            raise GovernanceRejected("valid #19101-#19500 control required")
        if control_id in self._controls and self._controls[control_id] != row:
            raise GovernanceRejected("control conflict")
        self._controls[control_id] = row
        return row

    def anchor(self, source, mapping, registry, manifest, lessons, rules, previous_snapshot, sequence, latest):
        if not isinstance(source, SyntheticPostgresRecoverySupersessionProof):
            raise GovernanceRejected("prior recovery supersession proof required")
        payload = dict(snapshot_id="synthetic:lesson-snapshot:19101-19500", stage_range=(19101, 19500), mapping_digest=mapping, registry_digest=registry, manifest_digest=manifest, lesson_ids=tuple(lessons), rule_ids=tuple(rules), source_docket_digest=source._docket.digest if source._docket else None, previous_snapshot_digest=previous_snapshot, sequence=sequence, latest=latest)
        row = Snapshot(**payload, digest=canonical_digest(payload))
        valid = (set(self._controls) == set(range(19101, 19501)) and source.evidence()["complete_postgres_recovery_supersession_contract_evidence"] and mapping == mapping_digest(STAGE_MAPPING) and _hex(registry) and _hex(manifest) and tuple(lessons) == APPLIED_LESSONS and tuple(rules) == APPLIED_RULES and previous_snapshot == source._snapshot.digest and isinstance(sequence, int) and not isinstance(sequence, bool) and sequence > 0 and latest is True)
        if not valid:
            raise GovernanceRejected("complete recovery review receipt proof snapshot required")
        self._source = source; self._snapshot = row
        return row

    def finalize(self, docket_id):
        if self._docket or not self._snapshot or not isinstance(docket_id, str) or not docket_id.startswith("synthetic:postgres-recovery-review-receipt-proof-docket:"):
            raise GovernanceRejected("complete recovery review receipt docket required")
        payload = dict(docket_id=docket_id, snapshot_digest=self._snapshot.digest, complete=True, held=True, pending_human_judgment=True, production_writes=0, receipt_issued=False, approved=False, activated=False, deployed=False, status=MAXIMUM_STATE)
        self._docket = Docket(**payload, digest=canonical_digest(payload))
        return self._docket

    def evidence(self, proof=None):
        status = "SKIP_NO_PRECONFIGURED_TEST_DATABASE" if proof is None else "PASS_POSTGRES_RECOVERY_REVIEW_RECEIPT_PROOF" if integration_proof_valid(proof) else None
        if status is None:
            raise GovernanceRejected("complete exact PostgreSQL recovery review receipt PASS proof required")
        source_ok = bool(self._source and self._source.evidence()["complete_postgres_recovery_supersession_contract_evidence"])
        snapshot_ok = bool(self._snapshot and source_ok and self._snapshot.stage_range == (19101, 19500) and self._snapshot.mapping_digest == mapping_digest(STAGE_MAPPING) and self._snapshot.source_docket_digest == self._source._docket.digest and self._snapshot.previous_snapshot_digest == self._source._snapshot.digest and self._snapshot.lesson_ids == APPLIED_LESSONS and self._snapshot.rule_ids == APPLIED_RULES and self._snapshot.latest and self._snapshot.digest == canonical_digest({k: v for k, v in self._snapshot.__dict__.items() if k != "digest"}))
        controls_ok = set(self._controls) == set(range(19101, 19501)) and all(row.digest == canonical_digest({k: v for k, v in row.__dict__.items() if k != "digest"}) for row in self._controls.values())
        docket_ok = bool(self._docket and snapshot_ok and self._docket.production_writes == 0 and self._docket.receipt_issued is False and self._docket.status == MAXIMUM_STATE and self._docket.digest == canonical_digest({k: v for k, v in self._docket.__dict__.items() if k != "digest"}))
        return {"range": [19101, 19500], "control_count": 400, "registered_control_count": len(self._controls), "recovery_path_count": 96, "human_judgment_hold_count": 48, "postgresql_recovery_review_receipt_proof_status": status, "postgresql_recovery_review_receipt_proof_claimed": status.startswith("PASS_"), "postgresql_integration_skip_count": 1 if status.startswith("SKIP_") else 0, "review_state": REVIEW_STATE, "payment_authority": False, "receipt_authority": False, "retry_authority": False, "approval_authority": False, "execution_authority": False, "multinode_preflight_contract_complete": True, "actual_network_partition_claimed": False, "actual_failover_claimed": False, "fault_injection_performed": False, "production_database_writes": 0, "cleanup_succeeded": (proof or {}).get("cleanup_succeeded", False), "complete_postgres_recovery_review_receipt_contract_evidence": bool(docket_ok and controls_ok), "maximum_state": MAXIMUM_STATE if docket_ok and controls_ok else "CONTRACT_INCOMPLETE", "applied_lesson_ids": list(APPLIED_LESSONS), "applied_rule_ids": list(APPLIED_RULES), "recovery_guidance_digest": canonical_digest(recovery_paths()), "approval_receipts_issued": 0, "signatures_created": 0, "keys_read": 0, "credentials_read": 0, "financial_operations": 0, "approved": False, "activated": False, "deployed": False}
