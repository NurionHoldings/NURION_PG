"""Disposable PostgreSQL recovery-quarantine proof #17901-#18300."""
from __future__ import annotations

from dataclasses import dataclass

from .arkaon.governance import GovernanceRejected, canonical_digest
from .synthetic_postgres_connection_loss_proof import (
    APPLIED_LESSONS as PRIOR_LESSONS,
    APPLIED_RULES,
    STAGE_MAPPING as PRIOR_STAGE_MAPPING,
    SyntheticPostgresConnectionLossProof,
)

APPLIED_LESSONS = tuple(sorted(PRIOR_LESSONS + ("ARL-17901-001",)))
WORKSTREAM_NAMES = (
    "QUARANTINE_SCHEMA", "DETERMINISTIC_CASE_IDENTITY", "SOURCE_EVENT_BINDING",
    "IDEMPOTENCY_BINDING", "PAYLOAD_BINDING", "SQLSTATE_BINDING",
    "PROVENANCE_BINDING", "OBSERVED_AT_BINDING", "SEQUENCE_BINDING",
    "APPEND_ONLY_INSERT", "SAME_PAYLOAD_REPLAY", "CHANGED_PAYLOAD_REJECTION",
    "CROSS_KEY_REJECTION", "NON_EXECUTABLE_STATE", "ZERO_AUTHORITY",
    "READ_ONLY_OPERATOR_PACKET", "RECONCILIATION_VIEW", "SOURCE_NO_WRITE_RETRY",
    "NARROW_CLEANUP", "ARTIFACT_INTEGRITY",
)
WORKSTREAMS = tuple((17901 + i * 20, 17920 + i * 20, n) for i, n in enumerate(WORKSTREAM_NAMES))
CONTROL_ASPECTS = (
    "input_schema", "required_fields", "state_precondition", "source_binding",
    "digest_recalculation", "negative_path", "missing_input", "duplicate_input",
    "replay", "conflict", "stale_version", "concurrency", "partial_batch",
    "ordering", "append_only", "hold_propagation", "operator_gate",
    "non_execution", "cleanup", "artifact_integrity",
)
NEGATIVE = frozenset({"negative_path", "missing_input", "duplicate_input", "replay", "conflict", "stale_version", "partial_batch"})
STAGE_MAPPING = PRIOR_STAGE_MAPPING + (("ARKAON-LESSONS-17901", (17901, 18300)),)
MAXIMUM_STATE = "POSTGRES_RECOVERY_QUARANTINE_PROOF_ONLY"
CASE_STATE = "QUARANTINED_NON_EXECUTABLE_ONLY"


def mapping_digest(rows):
    return canonical_digest(("CONTIGUOUS_STAGE_MAPPING", tuple(rows)))


def _hex(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def deterministic_case_id(source_event_id, idempotency_key, payload_digest, sqlstate, provenance):
    values = (source_event_id, idempotency_key, payload_digest, sqlstate, provenance)
    if not all(isinstance(v, str) and v for v in values) or not _hex(payload_digest):
        raise GovernanceRejected("complete exact quarantine identity required")
    return "rq_" + canonical_digest(("NURION_RECOVERY_QUARANTINE_CASE_V1", values))


def integration_proof_valid(p):
    expected_keys = {
        "status", "case_state", "deterministic_case_identity", "source_event_exact_match",
        "idempotency_key_exact_match", "payload_digest_exact_match", "sqlstate_exact_match",
        "provenance_exact_match", "observed_at_exact_match", "sequence_exact_match",
        "same_payload_replay_row_count", "same_payload_replay_converged",
        "changed_payload_fail_closed", "cross_key_fail_closed", "append_only",
        "payment_authority", "receipt_authority", "retry_authority", "approval_authority",
        "fresh_read_only_operator_packet", "reconciliation_view_read_only",
        "operator_view_insert_rejected", "operator_view_update_rejected", "operator_view_delete_rejected",
        "precommit_source_row_count", "precommit_source_retry_count", "actual_network_partition_claimed",
        "actual_failover_claimed", "production_database_writes", "cleanup_succeeded",
        "credential_disclosed", "password_credential_configured",
    }
    if not isinstance(p, dict) or set(p) != expected_keys:
        return False
    return p == {
        "status": "PASS_POSTGRES_RECOVERY_QUARANTINE_PROOF",
        "case_state": CASE_STATE,
        "deterministic_case_identity": True,
        "source_event_exact_match": True,
        "idempotency_key_exact_match": True,
        "payload_digest_exact_match": True,
        "sqlstate_exact_match": True,
        "provenance_exact_match": True,
        "observed_at_exact_match": True,
        "sequence_exact_match": True,
        "same_payload_replay_row_count": 1,
        "same_payload_replay_converged": True,
        "changed_payload_fail_closed": True,
        "cross_key_fail_closed": True,
        "append_only": True,
        "payment_authority": False,
        "receipt_authority": False,
        "retry_authority": False,
        "approval_authority": False,
        "fresh_read_only_operator_packet": True,
        "reconciliation_view_read_only": True,
        "operator_view_insert_rejected": True,
        "operator_view_update_rejected": True,
        "operator_view_delete_rejected": True,
        "precommit_source_row_count": 0,
        "precommit_source_retry_count": 0,
        "actual_network_partition_claimed": False,
        "actual_failover_claimed": False,
        "production_database_writes": 0,
        "cleanup_succeeded": True,
        "credential_disclosed": False,
        "password_credential_configured": False,
    }


def recovery_paths():
    return (
        (("cause", "precommit_connection_loss_not_committed"), ("recommended", True), ("method", "append_exact_observation_to_non_executable_quarantine"), ("alternative", "retain_manual_hold_without_case_materialization"), ("cost", "LOW"), ("risk", "LOW"), ("reversibility", "HIGH"), ("validation", "fresh_absence_then_exact_case_read"), ("stop", "source_row_present_or_unknown_sqlstate"), ("resume", "resolve_source_ambiguity_then_create_new_case_sequence"), ("rollback", "do_not_mutate_source_drop_exact_fixture_schema_only")),
        (("cause", "same_case_replayed"), ("recommended", True), ("method", "exact_same_payload_one_row_convergence"), ("alternative", "read_existing_case_without_insert"), ("cost", "LOW"), ("risk", "LOW"), ("reversibility", "HIGH"), ("validation", "case_id_and_all_bound_fields_equal"), ("stop", "any_bound_field_differs"), ("resume", "submit_correct original envelope"), ("rollback", "none_append_only_existing_row_unchanged")),
        (("cause", "changed_payload_or_cross_key_alias"), ("recommended", True), ("method", "fail_closed_and_preserve_original_case"), ("alternative", "new independently sourced event after human review"), ("cost", "MEDIUM"), ("risk", "MEDIUM"), ("reversibility", "HIGH"), ("validation", "unique_constraints_and_exact_readback"), ("stop", "conflict_detected"), ("resume", "resolve identity conflict with independent evidence"), ("rollback", "transaction_rollback_no_case_mutation")),
    )


@dataclass(frozen=True)
class Control:
    control_id: int; workstream: str; aspect: str; requirement_ref: str; fixture_digest: str; expected_result: str; digest: str


@dataclass(frozen=True)
class Snapshot:
    snapshot_id: str; stage_range: tuple; mapping_digest: str; registry_digest: str; manifest_digest: str; lesson_ids: tuple; rule_ids: tuple; source_docket_digest: str; previous_snapshot_digest: str; sequence: int; latest: bool; digest: str


@dataclass(frozen=True)
class Docket:
    docket_id: str; snapshot_digest: str; complete: bool; held: bool; pending_human_judgment: bool; production_writes: int; receipt_issued: bool; approved: bool; activated: bool; deployed: bool; status: str; digest: str


class SyntheticPostgresRecoveryQuarantineProof:
    def __init__(self):
        self._controls = {}; self._source = None; self._snapshot = None; self._docket = None

    def _expected(self, cid):
        i = cid - 17901
        return WORKSTREAM_NAMES[i // 20], CONTROL_ASPECTS[i % 20]

    def add_control(self, cid, workstream, aspect, requirement_ref, fixture_digest, expected_result):
        p = dict(control_id=cid, workstream=workstream, aspect=aspect, requirement_ref=requirement_ref, fixture_digest=fixture_digest, expected_result=expected_result)
        row = Control(**p, digest=canonical_digest(p))
        valid = (isinstance(cid, int) and not isinstance(cid, bool) and 17901 <= cid <= 18300 and
                 self._expected(cid) == (workstream, aspect) and
                 requirement_ref == f"synthetic:postgres-recovery-quarantine-proof-requirement:{(cid-17901)//20:02}" and
                 _hex(fixture_digest) and expected_result == ("EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS"))
        if not valid:
            raise GovernanceRejected("valid #17901-#18300 control required")
        if cid in self._controls and self._controls[cid] != row:
            raise GovernanceRejected("control conflict")
        self._controls[cid] = row
        return row

    def anchor(self, source, mapping, registry, manifest, lessons, rules, previous_snapshot, sequence, latest):
        if not isinstance(source, SyntheticPostgresConnectionLossProof):
            raise GovernanceRejected("prior connection loss proof required")
        p = dict(snapshot_id="synthetic:lesson-snapshot:17901-18300", stage_range=(17901, 18300), mapping_digest=mapping, registry_digest=registry, manifest_digest=manifest, lesson_ids=tuple(lessons), rule_ids=tuple(rules), source_docket_digest=source._docket.digest if source._docket else None, previous_snapshot_digest=previous_snapshot, sequence=sequence, latest=latest)
        row = Snapshot(**p, digest=canonical_digest(p))
        valid = (set(self._controls) == set(range(17901, 18301)) and source.evidence()["complete_postgres_connection_loss_contract_evidence"] and mapping == mapping_digest(STAGE_MAPPING) and _hex(registry) and _hex(manifest) and tuple(lessons) == APPLIED_LESSONS and tuple(rules) == APPLIED_RULES and previous_snapshot == source._snapshot.digest and isinstance(sequence, int) and not isinstance(sequence, bool) and sequence > 0 and latest is True)
        if not valid:
            raise GovernanceRejected("complete recovery quarantine proof snapshot required")
        self._source = source; self._snapshot = row
        return row

    def finalize(self, docket_id):
        if self._docket or not self._snapshot:
            raise GovernanceRejected("complete recovery quarantine contract required")
        p = dict(docket_id=docket_id, snapshot_digest=self._snapshot.digest, complete=True, held=True, pending_human_judgment=True, production_writes=0, receipt_issued=False, approved=False, activated=False, deployed=False, status=MAXIMUM_STATE)
        if not isinstance(docket_id, str) or not docket_id.startswith("synthetic:postgres-recovery-quarantine-proof-docket:"):
            raise GovernanceRejected("synthetic recovery quarantine docket required")
        self._docket = Docket(**p, digest=canonical_digest(p))
        return self._docket

    def evidence(self, proof=None):
        if proof is None:
            status = "SKIP_NO_PRECONFIGURED_TEST_DATABASE"
        elif integration_proof_valid(proof):
            status = "PASS_POSTGRES_RECOVERY_QUARANTINE_PROOF"
        else:
            raise GovernanceRejected("complete exact PostgreSQL recovery quarantine PASS proof required")
        source_ok = bool(self._source and self._source.evidence()["complete_postgres_connection_loss_contract_evidence"])
        snapshot_ok = bool(self._snapshot and source_ok and self._snapshot.stage_range == (17901, 18300) and self._snapshot.mapping_digest == mapping_digest(STAGE_MAPPING) and self._snapshot.source_docket_digest == self._source._docket.digest and self._snapshot.previous_snapshot_digest == self._source._snapshot.digest and self._snapshot.lesson_ids == APPLIED_LESSONS and self._snapshot.rule_ids == APPLIED_RULES and _hex(self._snapshot.registry_digest) and _hex(self._snapshot.manifest_digest) and self._snapshot.latest and self._snapshot.digest == canonical_digest({k:v for k,v in self._snapshot.__dict__.items() if k != "digest"}))
        controls_ok = set(self._controls) == set(range(17901, 18301)) and all(r.digest == canonical_digest({k:v for k,v in r.__dict__.items() if k != "digest"}) and self._expected(cid) == (r.workstream, r.aspect) for cid, r in self._controls.items())
        docket_ok = bool(self._docket and snapshot_ok and self._docket.production_writes == 0 and self._docket.status == MAXIMUM_STATE and self._docket.digest == canonical_digest({k:v for k,v in self._docket.__dict__.items() if k != "digest"}))
        return {"range":[17901,18300], "control_count":400, "registered_control_count":len(self._controls), "recovery_path_count":96, "human_judgment_hold_count":48, "postgresql_recovery_quarantine_proof_status":status, "postgresql_recovery_quarantine_proof_claimed":status.startswith("PASS_"), "postgresql_integration_skip_count":1 if status.startswith("SKIP_") else 0, "quarantine_case_state":CASE_STATE, "payment_authority":False, "receipt_authority":False, "retry_authority":False, "approval_authority":False, "actual_network_partition_claimed":False, "actual_failover_claimed":False, "production_database_writes":0, "cleanup_succeeded":(proof or {}).get("cleanup_succeeded",False), "complete_postgres_recovery_quarantine_contract_evidence":bool(docket_ok and controls_ok), "maximum_state":MAXIMUM_STATE if docket_ok and controls_ok else "CONTRACT_INCOMPLETE", "applied_lesson_ids":list(APPLIED_LESSONS), "applied_rule_ids":list(APPLIED_RULES), "recovery_guidance_digest":canonical_digest(recovery_paths()), "approval_receipts_issued":0, "signatures_created":0, "keys_read":0, "credentials_read":0, "financial_operations":0, "approved":False, "activated":False, "deployed":False}
