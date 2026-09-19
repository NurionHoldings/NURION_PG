from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from hashlib import sha256
import unittest

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.synthetic_integration_package_acceptance import (
    ALLOWED_ARTIFACTS, CONTROL_ASPECTS, FLOWS, FLOW_OWNERS, NEGATIVE, WORKSTREAMS,
    SyntheticIntegrationPackageAcceptance,
)

def d(x): return sha256(x.encode()).hexdigest()

def populated(full=True):
    s=SyntheticIntegrationPackageAcceptance(); streams=WORKSTREAMS if full else WORKSTREAMS[:1]
    for start,end,name in streams:
        ids=range(start,end+1) if full else (start,)
        for cid in ids:
            aspect=CONTROL_ASPECTS[(cid-4301)%25]
            s.add_control(cid,name,aspect,f"synthetic:package-requirement:{(cid-4301)//25:02}",d(f"fixture:{cid}"),"EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS")
    return s

def anchored():
    s=populated(); a=s.anchor_negotiation("synthetic:package-anchor:one",d("bundle"),d("round"),d("cases"),d("receipt")); return s,a

def specified():
    s,a=anchored()
    for ki,kind in enumerate(sorted(ALLOWED_ARTIFACTS)):
        for fi,flow in enumerate(FLOWS):
            s.add_artifact(f"synthetic:package-artifact:{ki}-{fi}",kind,FLOW_OWNERS[flow],flow,d(f"content:{kind}:{flow}"))
    return s,a

def assembled():
    s,a=specified(); m=s.assemble("synthetic:integration-package:one","synthetic:tenant:one","synthetic:upstream:one","synthetic:package-assembler:maker"); return s,a,m

def complete():
    s,a,m=assembled(); s.run_cases(m.package_id); r=s.review("synthetic:package-receipt:one",m.package_id,"synthetic:package-reviewer:checker","synthetic:package-assembler:maker"); return s,a,m,r

class Tests(unittest.TestCase):
    def test_exact_matrix(self):
        e=populated().evidence(); self.assertEqual((e["control_count"],e["workstream_count"],e["controls_per_workstream"]),(400,16,25)); self.assertTrue(e["control_matrix_valid"])
    def test_exact_range(self): self.assertEqual(set(populated()._controls),set(range(4301,4701)))
    def test_partial_registry_fails(self):
        s=populated(False)
        with self.assertRaises(GovernanceRejected): s.anchor_negotiation("synthetic:package-anchor:x",d("a"),d("b"),d("c"),d("d"))
    def test_control_idempotency_conflict(self):
        s=populated(False); row=next(iter(s._controls.values())); args={k:v for k,v in row.__dict__.items() if k!="digest"}
        self.assertIs(s.add_control(**args),s.add_control(**args))
        with self.assertRaises(GovernanceRejected): s.add_control(**(args|{"fixture_digest":d("other")}))
    def test_anchor_idempotency(self):
        s,a=anchored(); self.assertIs(s.anchor_negotiation(a.anchor_id,a.source_bundle_digest,a.negotiation_round_digest,a.case_set_digest,a.review_receipt_digest),a)
    def test_anchor_requires_digests(self):
        s=populated()
        with self.assertRaises(GovernanceRejected): s.anchor_negotiation("synthetic:package-anchor:x","bad",d("b"),d("c"),d("d"))
    def test_artifact_allowlist(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected): s.add_artifact("synthetic:package-artifact:x","EXECUTABLE","NURION_PG",FLOWS[0],d("x"))
    def test_artifact_requires_valid_party_flow(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected): s.add_artifact("synthetic:package-artifact:x","MOCK_PAIR","ATTACKER",FLOWS[0],d("x"))
    def test_artifact_party_must_own_flow(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected): s.add_artifact("synthetic:package-artifact:x","MOCK_PAIR","UPSTREAM_PG","tenant_to_nurion",d("x"))
    def test_artifact_idempotency_conflict(self):
        s,_=anchored(); x=s.add_artifact("synthetic:package-artifact:x","MOCK_PAIR",FLOW_OWNERS[FLOWS[0]],FLOWS[0],d("x")); self.assertIs(s.add_artifact(x.artifact_id,x.artifact_type,x.party,x.flow,x.content_digest),x)
        with self.assertRaises(GovernanceRejected): s.add_artifact(x.artifact_id,x.artifact_type,x.party,x.flow,d("other"))
    def test_partial_package_fail_closed(self):
        s,_=anchored(); s.add_artifact("synthetic:package-artifact:x","MOCK_PAIR",FLOW_OWNERS[FLOWS[0]],FLOWS[0],d("x"))
        with self.assertRaises(GovernanceRejected): s.assemble("synthetic:integration-package:x","synthetic:tenant:x","synthetic:upstream:x","synthetic:package-assembler:x")
        self.assertEqual(s.evidence()["hold_count"],1)
    def test_duplicate_kind_flow_fails_exactness(self):
        s,_=specified(); s.add_artifact("synthetic:package-artifact:duplicate","MOCK_PAIR",FLOW_OWNERS[FLOWS[0]],FLOWS[0],d("different"))
        with self.assertRaises(GovernanceRejected): s.assemble("synthetic:integration-package:x","synthetic:tenant:x","synthetic:upstream:x","synthetic:package-assembler:x")
    def test_manifest_inert_state(self): self.assertEqual(assembled()[2].status,"MOCK_ACCEPTANCE_REQUIRED")
    def test_route_bindings_exact(self): self.assertEqual(tuple(x[0] for x in assembled()[2].route_bindings),FLOWS)
    def test_400_cases(self):
        s,_,m=assembled(); rows=s.run_cases(m.package_id); self.assertEqual(len(rows),400); self.assertTrue(all(x.status=="SYNTHETIC_PASS" for x in rows))
    def test_cases_wrong_package(self):
        s,_,_=assembled()
        with self.assertRaises(GovernanceRejected): s.run_cases("synthetic:integration-package:other")
    def test_cases_single_run(self):
        s,_,m=assembled(); s.run_cases(m.package_id)
        with self.assertRaises(GovernanceRejected): s.run_cases(m.package_id)
    def test_review_requires_cases(self):
        s,_,m=assembled()
        with self.assertRaises(GovernanceRejected): s.review("synthetic:package-receipt:x",m.package_id,"synthetic:package-reviewer:checker","synthetic:package-assembler:maker")
    def test_review_role_separation(self):
        s,_,m=assembled(); s.run_cases(m.package_id)
        with self.assertRaises(GovernanceRejected): s.review("synthetic:package-receipt:x",m.package_id,"synthetic:package-reviewer:maker","synthetic:package-assembler:maker")
    def test_review_assembler_cannot_be_forged(self):
        s,_,m=assembled(); s.run_cases(m.package_id)
        with self.assertRaises(GovernanceRejected): s.review("synthetic:package-receipt:x",m.package_id,"synthetic:package-reviewer:checker","synthetic:package-assembler:other")
    def test_receipt_never_releases(self):
        r=complete()[3]; self.assertTrue(r.operator_release_required); self.assertFalse(r.release_recorded); self.assertEqual(r.status,"ACCEPTANCE_REVIEWED_NOT_RELEASED")
    def test_control_rehash_tamper(self):
        s=populated(); row=s._controls[4301]; p=row.__dict__|{"workstream":"WRONG"}; p["digest"]=canonical_digest({k:v for k,v in p.items() if k!="digest"}); s._controls[4301]=replace(row,workstream="WRONG",digest=p["digest"]); self.assertFalse(s.evidence()["integrity_valid"])
    def test_anchor_rehash_tamper(self):
        s,a=anchored(); p=a.__dict__|{"status":"APPROVED"}; p["digest"]=canonical_digest({k:v for k,v in p.items() if k!="digest"}); s._anchor=replace(a,status="APPROVED",digest=p["digest"]); self.assertFalse(s.evidence()["integrity_valid"])
    def test_artifact_rehash_mode_tamper(self):
        s,_=specified(); key=next(iter(s._artifacts)); row=s._artifacts[key]; p=row.__dict__|{"mode":"EXECUTABLE"}; p["digest"]=canonical_digest({k:v for k,v in p.items() if k!="digest"}); s._artifacts[key]=replace(row,mode="EXECUTABLE",digest=p["digest"]); self.assertFalse(s.evidence()["integrity_valid"])
    def test_manifest_rehash_status_tamper(self):
        s,_,m=assembled(); p=m.__dict__|{"status":"RELEASED"}; p["digest"]=canonical_digest({k:v for k,v in p.items() if k!="digest"}); s._manifest=replace(m,status="RELEASED",digest=p["digest"]); self.assertFalse(s.evidence()["integrity_valid"])
    def test_manifest_rehashed_route_substitution(self):
        s,_,m=assembled(); routes=((m.route_bindings[0][0],d("forged-route")),)+m.route_bindings[1:]
        p=m.__dict__|{"route_bindings":routes}; p["digest"]=canonical_digest({k:v for k,v in p.items() if k!="digest"})
        s._manifest=replace(m,route_bindings=routes,digest=p["digest"]); self.assertFalse(s.evidence()["integrity_valid"])
    def test_manifest_rehashed_assembler_substitution(self):
        s,_,m=assembled(); p=m.__dict__|{"assembler":"synthetic:package-assembler:attacker"}
        p["digest"]=canonical_digest({k:v for k,v in p.items() if k!="digest"})
        s._manifest=replace(m,assembler=p["assembler"],digest=p["digest"]); self.assertFalse(s.evidence()["integrity_valid"])
    def test_case_rehash_tamper(self):
        s,_,m=assembled(); s.run_cases(m.package_id); row=s._cases[4301]; observed="PASS" if row.expected_result!="PASS" else "EXPECTED_REJECTION"; p=row.__dict__|{"observed_result":observed}; p["digest"]=canonical_digest({k:v for k,v in p.items() if k!="digest"}); s._cases[4301]=replace(row,observed_result=observed,digest=p["digest"]); self.assertFalse(s.evidence()["integrity_valid"])
    def test_event_action_rehash_tamper(self):
        s,_=anchored(); x=s._events[0]|{"action":"PACKAGE_RELEASED"}; x["digest"]=canonical_digest({k:v for k,v in x.items() if k!="digest"}); s._events[0]=x; self.assertFalse(s.evidence()["integrity_valid"])
    def test_event_artifact_substitution(self):
        s,_=anchored(); x=s._events[0]|{"artifact_digest":d("substitute")}; x["digest"]=canonical_digest({k:v for k,v in x.items() if k!="digest"}); s._events[0]=x; self.assertFalse(s.evidence()["integrity_valid"])
    def test_receipt_rehash_release_tamper(self):
        s,_,_,r=complete(); p=r.__dict__|{"release_recorded":True}; p["digest"]=canonical_digest({k:v for k,v in p.items() if k!="digest"}); s._receipt=replace(r,release_recorded=True,digest=p["digest"]); self.assertFalse(s.evidence()["integrity_valid"])
    def test_receipt_rehash_review_false_tamper(self):
        s,_,_,r=complete(); p=r.__dict__|{"accepted_for_review":False}
        p["digest"]=canonical_digest({k:v for k,v in p.items() if k!="digest"})
        s._receipt=replace(r,accepted_for_review=False,digest=p["digest"]); self.assertFalse(s.evidence()["integrity_valid"])
    def test_concurrent_control_converges(self):
        s=SyntheticIntegrationPackageAcceptance(); args=(4301,WORKSTREAMS[0][2],CONTROL_ASPECTS[0],"synthetic:package-requirement:00",d("f"),"PASS")
        with ThreadPoolExecutor(max_workers=8) as pool: rows=list(pool.map(lambda _:s.add_control(*args),range(20)))
        self.assertEqual(len({x.digest for x in rows}),1)
    def test_complete_evidence(self):
        e=complete()[0].evidence(); self.assertTrue(e["capability_ready"]); self.assertTrue(e["complete_acceptance_evidence"]); self.assertEqual((e["artifact_count"],e["route_count"],e["mock_case_count"]),(28,4,400))
    def test_non_execution_boundary(self):
        e=complete()[0].evidence(); keys=("external_calls","document_transmissions","electronic_signatures","external_pg_calls","card_network_calls","ledger_writes","money_movement","credential_reads","deployments","policy_prompt_weight_changes"); self.assertEqual(tuple(e[k] for k in keys),(0,)*len(keys)); self.assertFalse(e["release_recorded"])

if __name__ == "__main__": unittest.main()
