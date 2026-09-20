from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from hashlib import sha256
import unittest
from unittest.mock import patch

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.synthetic_design_validation_traceability import (
    CONTROL_ASPECTS, MAXIMUM_STATE, WORKSTREAMS,
    SyntheticDesignValidationTraceability,
)


def d(value): return sha256(value.encode()).hexdigest()


def populated(full=True):
    service = SyntheticDesignValidationTraceability()
    service.add_anchor("synthetic:p0-anchor:one", d("commit"), d("baseline-evidence"))
    streams = WORKSTREAMS if full else WORKSTREAMS[:1]
    for start, end, name in streams:
        controls = range(start, end + 1) if full else (start,)
        for control_id in controls:
            aspect = CONTROL_ASPECTS[(control_id - 3501) % 25]
            service.add_claim(
                f"synthetic:validation-claim:{control_id}", control_id, name, aspect,
                "synthetic:p0-anchor:one", f"synthetic:p0-requirement:{(control_id - 3501) // 25:02}",
                f"threat-{control_id}", d(f"fixture-{control_id}"),
                "EXPECTED_REJECTION" if aspect in {"negative_path", "missing_input", "duplicate_input", "conflict", "stale_version", "partial_batch"} else "PASS",
                d(f"evidence-{control_id}"), 1, "SECURITY", True,
            )
    return service


def drafted():
    service = populated()
    row = service.author("synthetic:validation-dossier:one", "synthetic:validation-author:author",
                         "synthetic:p0-anchor:one", tuple(service._claims))
    return service, row


def reviewed():
    service, row = drafted()
    row = service.review("synthetic:validation-review:one", row.dossier_id, row.version,
                         "synthetic:validation-reviewer:reviewer", True, d("finding"))
    return service, row


def recorded():
    service, row = reviewed()
    review = service.artifact("synthetic:validation-review:one")
    row = service.record("synthetic:validation-receipt:one", row.dossier_id, row.version,
                         "synthetic:validation-verifier:verifier", review.digest)
    return service, row


def integrated():
    service, row = recorded()
    out = service.generate_integration_drafts(
        row.dossier_id, "synthetic:tenant:agency-a", "synthetic:upstream-pg:pg-a", 1,
        "synthetic:correlation:one", "synthetic:idempotency:one",
        (("tenant_order_id", "merchant_reference"), ("amount_token", "amount_token")),
    )
    return service, row, out


class Tests(unittest.TestCase):
    def test_exact_400_matrix(self):
        e = SyntheticDesignValidationTraceability().evidence()
        self.assertEqual((e["control_count"], e["workstream_count"], e["controls_per_workstream"]), (400, 16, 25))
        self.assertTrue(e["control_matrix_valid"])

    def test_full_registry_covers_exact_range(self):
        service = populated(); e = service.evidence()
        self.assertEqual(set(service._control_claims), set(range(3501, 3901)))
        self.assertTrue(e["claim_coverage_complete"])

    def test_partial_dossier_fail_closed(self):
        service = populated(False)
        with self.assertRaises(GovernanceRejected):
            service.author("synthetic:validation-dossier:x", "synthetic:validation-author:a",
                           "synthetic:p0-anchor:one", tuple(service._claims))

    def test_anchor_idempotency_and_conflict(self):
        service = SyntheticDesignValidationTraceability()
        args = ("synthetic:p0-anchor:one", d("commit"), d("evidence"))
        self.assertIs(service.add_anchor(*args), service.add_anchor(*args))
        with self.assertRaises(GovernanceRejected): service.add_anchor(args[0], d("other"), args[2])

    def test_anchor_requires_reviewed_digests(self):
        service = SyntheticDesignValidationTraceability()
        for commit, evidence, reviewed_flag in (("bad", d("x"), True), (d("x"), "bad", True), (d("x"), d("y"), False)):
            with self.assertRaises(GovernanceRejected):
                service.add_anchor("synthetic:p0-anchor:x", commit, evidence, reviewed_flag)

    def test_claim_semantic_matrix(self):
        service = populated(False)
        args = dict(claim_id="synthetic:validation-claim:new", control_id=3502,
                    workstream=WORKSTREAMS[0][2], aspect=CONTROL_ASPECTS[1],
                    anchor_id="synthetic:p0-anchor:one", requirement_ref="synthetic:p0-requirement:00",
                    threat="threat", input_fixture_digest=d("f"), expected_result="PASS",
                    evidence_digest=d("e"), source_version=1, owner_role="SECURITY")
        for change in ({"aspect": "wrong"}, {"expected_result": "APPROVED"},
                       {"owner_role": "BOT"}, {"operator_approval_required": False}):
            with self.assertRaises(GovernanceRejected): service.add_claim(**(args | change))

    def test_duplicate_control_rejected(self):
        service = populated(False); old = next(iter(service._claims.values()))
        args = {k: v for k, v in old.__dict__.items() if k != "digest"} | {"claim_id": "synthetic:validation-claim:duplicate"}
        with self.assertRaises(GovernanceRejected): service.add_claim(**args)

    def test_claim_idempotency_conflict(self):
        service = populated(False); old = next(iter(service._claims.values()))
        args = {k: v for k, v in old.__dict__.items() if k != "digest"}
        self.assertIs(service.add_claim(**args), service.add_claim(**args))
        with self.assertRaises(GovernanceRejected): service.add_claim(**(args | {"threat": "different"}))

    def test_role_separation(self):
        service, row = drafted()
        with self.assertRaises(GovernanceRejected):
            service.review("synthetic:validation-review:x", row.dossier_id, row.version,
                           "synthetic:validation-reviewer:author", True, d("f"))
        service, row = reviewed(); review = service.artifact("synthetic:validation-review:one")
        with self.assertRaises(GovernanceRejected):
            service.record("synthetic:validation-receipt:x", row.dossier_id, row.version,
                           "synthetic:validation-verifier:reviewer", review.digest)

    def test_review_replay_conflict(self):
        service, row = drafted(); args = ("synthetic:validation-review:x", row.dossier_id,
            row.version, "synthetic:validation-reviewer:r", False, d("f"))
        out = service.review(*args); self.assertIs(out, service.review(*args)); self.assertEqual(out.status, "HELD")
        with self.assertRaises(GovernanceRejected): service.review(*args[:-1], d("other"))

    def test_receipt_replay_conflict(self):
        service, row = reviewed(); review = service.artifact("synthetic:validation-review:one")
        args = ("synthetic:validation-receipt:x", row.dossier_id, row.version,
                "synthetic:validation-verifier:v", review.digest)
        out = service.record(*args); self.assertIs(out, service.record(*args))
        with self.assertRaises(GovernanceRejected): service.record(*args[:-2], "synthetic:validation-verifier:z", review.digest)

    def test_concurrent_receipt_converges(self):
        service, row = reviewed(); review = service.artifact("synthetic:validation-review:one")
        args = ("synthetic:validation-receipt:x", row.dossier_id, row.version,
                "synthetic:validation-verifier:v", review.digest)
        with ThreadPoolExecutor(max_workers=8) as pool:
            rows = list(pool.map(lambda _: service.record(*args), range(20)))
        self.assertEqual(len({x.digest for x in rows}), 1)

    def test_stale_version_rejected(self):
        service, row = drafted()
        with self.assertRaises(GovernanceRejected):
            service.review("synthetic:validation-review:x", row.dossier_id, row.version + 1,
                           "synthetic:validation-reviewer:r", True, d("f"))

    def test_bounded_batch_and_missing_fail_closed(self):
        service, row = drafted()
        self.assertEqual(service.review_batch("synthetic:validation-reviewer:r", (row.dossier_id,)), (row,))
        with self.assertRaises(GovernanceRejected): service.review_batch("synthetic:validation-reviewer:r", tuple(str(x) for x in range(21)))
        with self.assertRaises(GovernanceRejected): service.review_batch("synthetic:validation-reviewer:r", ("missing",))

    def test_rehashed_claim_semantic_tamper_detected(self):
        service = populated(); key = next(iter(service._claims)); row = service._claims[key]
        payload = row.__dict__ | {"operator_approval_required": False}
        payload["digest"] = service.claim_digest(**{k: v for k, v in payload.items() if k != "digest"})
        service._claims[key] = replace(row, operator_approval_required=False, digest=payload["digest"])
        self.assertFalse(service.evidence()["registry_integrity_valid"])

    def test_event_and_hold_tamper_detected(self):
        service, row = drafted()
        row = service.review("synthetic:validation-review:x", row.dossier_id, row.version,
                             "synthetic:validation-reviewer:r", False, d("f"))
        service._events[-1]["action"] = "APPROVED"
        self.assertFalse(service.evidence()["append_only_chain_valid"])

    def test_audit_hold_and_collision(self):
        service, row = recorded()
        out = service.audit_hold(row.dossier_id, row.version, "synthetic:validation-auditor:a", d("f"))
        self.assertEqual(out.status, "HELD")
        service, row = recorded()
        with self.assertRaises(GovernanceRejected):
            service.audit_hold(row.dossier_id, row.version, "synthetic:validation-auditor:verifier", d("f"))

    def test_generate_four_bidirectional_documents_three_adapters(self):
        service, row, out = integrated()
        self.assertEqual((len(out["documents"]), len(out["adapters"])), (4, 3))
        self.assertTrue(service.evidence()["integration_lineage_valid"])
        self.assertEqual([x.flow for x in out["documents"]], ["tenant_to_nurion", "nurion_to_upstream", "upstream_to_nurion", "nurion_to_tenant"])

    def test_document_chain_and_fixed_gates(self):
        service, dossier, out = integrated(); previous = None
        receipt = service._receipts[service._dossier_receipts[dossier.dossier_id]]
        for row in out["documents"]:
            self.assertEqual(row.parent_document_digest, previous)
            self.assertEqual((row.dossier_id, row.dossier_digest, row.receipt_digest),
                             (dossier.dossier_id, dossier.digest, receipt.digest))
            self.assertEqual(row.status, "DRAFT_ONLY")
            self.assertFalse(row.consent_recorded or row.approval_recorded)
            previous = row.digest

    def test_adapter_is_inert(self):
        _, _, out = integrated()
        for row in out["adapters"]:
            self.assertEqual(row.mode, "SPECIFICATION_ONLY")
            self.assertFalse(row.transport_enabled or row.signing_enabled or row.external_api_enabled)

    def test_integration_requires_recorded_complete_dossier(self):
        service, row = drafted()
        with self.assertRaises(GovernanceRejected):
            service.generate_integration_drafts(row.dossier_id, "synthetic:tenant:a", "synthetic:upstream-pg:b", 1,
                "synthetic:correlation:c", "synthetic:idempotency:i", (("a", "b"),))

    def test_partial_or_duplicate_mapping_fail_closed(self):
        service, row = recorded()
        common = (row.dossier_id, "synthetic:tenant:a", "synthetic:upstream-pg:b", 1,
                  "synthetic:correlation:c", "synthetic:idempotency:i")
        for mapping in ((), (("a", "b"), ("a", "b")), (("", "b"),)):
            with self.assertRaises(GovernanceRejected): service.generate_integration_drafts(*common, mapping)

    def test_integration_idempotency_and_conflict(self):
        service, row, out = integrated()
        again = service.generate_integration_drafts(row.dossier_id, "synthetic:tenant:agency-a", "synthetic:upstream-pg:pg-a", 1,
            "synthetic:correlation:one", "synthetic:idempotency:one",
            (("tenant_order_id", "merchant_reference"), ("amount_token", "amount_token")))
        self.assertEqual(out, again)
        with self.assertRaises(GovernanceRejected):
            service.generate_integration_drafts(row.dossier_id, "synthetic:tenant:agency-a", "synthetic:upstream-pg:pg-a", 2,
                "synthetic:correlation:one", "synthetic:idempotency:one", (("a", "b"),))

    def test_rehashed_document_semantic_tamper_detected(self):
        service, _, out = integrated(); row = out["documents"][0]
        payload = row.__dict__ | {"approval_recorded": True}
        payload["digest"] = canonical_digest({k: v for k, v in payload.items() if k != "digest"})
        service._documents[row.document_id] = replace(row, approval_recorded=True, digest=payload["digest"])
        self.assertFalse(service.evidence()["integration_lineage_valid"])

    def test_rehashed_adapter_party_tamper_detected(self):
        service, _, out = integrated(); row = out["adapters"][0]
        payload = row.__dict__ | {"party_role": "synthetic:tenant:impostor"}
        payload["digest"] = canonical_digest({k: v for k, v in payload.items() if k != "digest"})
        service._adapters[row.adapter_id] = replace(row, party_role=payload["party_role"], digest=payload["digest"])
        self.assertFalse(service.evidence()["integration_lineage_valid"])

    def test_rehashed_document_flow_tamper_detected(self):
        service, _, out = integrated(); row = out["documents"][0]
        payload = row.__dict__ | {"flow": "nurion_to_upstream"}
        payload["digest"] = canonical_digest({k: v for k, v in payload.items() if k != "digest"})
        service._documents[row.document_id] = replace(row, flow=payload["flow"], digest=payload["digest"])
        self.assertFalse(service.evidence()["integration_lineage_valid"])

    def test_integration_is_bound_to_recorded_dossier_and_receipt(self):
        service, _, out = integrated(); row = out["documents"][0]
        payload = row.__dict__ | {"receipt_digest": d("forged-receipt")}
        payload["digest"] = canonical_digest({k: v for k, v in payload.items() if k != "digest"})
        service._documents[row.document_id] = replace(
            row, receipt_digest=payload["receipt_digest"], digest=payload["digest"])
        self.assertFalse(service.evidence()["integration_lineage_valid"])

    def test_integration_event_chain_detects_rehashed_semantic_tamper(self):
        service, _, _ = integrated()
        event = service._integration_events[0]
        payload = event | {"action": "DOCUMENT_TRANSMITTED"}
        payload["digest"] = canonical_digest({k: v for k, v in payload.items() if k != "digest"})
        service._integration_events[0] = payload
        self.assertFalse(service.evidence()["integration_lineage_valid"])

    def test_capability_gap_fail_closed(self):
        import nurion_pg.synthetic_design_validation_traceability as module
        with patch.object(module, "WORKSTREAMS", module.WORKSTREAMS[:-1]):
            e = SyntheticDesignValidationTraceability().evidence()
        self.assertFalse(e["capability_ready"]); self.assertIn("control_matrix", e["capability_gap_evidence"]["gaps"])

    def test_non_execution_boundary(self):
        e = SyntheticDesignValidationTraceability().evidence()
        self.assertEqual((e["external_calls"], e["external_pg_calls"], e["card_network_calls"],
                          e["ledger_writes"], e["money_movement"], e["document_transmissions"],
                          e["electronic_signatures"], e["external_registrations"]), (0,) * 8)
        self.assertFalse(e["approval_recorded"])


if __name__ == "__main__": unittest.main()
