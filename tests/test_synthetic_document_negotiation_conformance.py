from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from hashlib import sha256
import unittest

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.synthetic_document_negotiation_conformance import (
    CONTROL_ASPECTS, NEGATIVE, WORKSTREAMS, SyntheticDocumentNegotiationConformance,
)

def d(x): return sha256(x.encode()).hexdigest()

def populated(full=True):
    s=SyntheticDocumentNegotiationConformance()
    streams=WORKSTREAMS if full else WORKSTREAMS[:1]
    for start,end,name in streams:
        ids=range(start,end+1) if full else (start,)
        for cid in ids:
            aspect=CONTROL_ASPECTS[(cid-3901)%25]
            s.add_control(cid,name,aspect,f"synthetic:negotiation-requirement:{(cid-3901)//25:02}",d(f"fixture:{cid}"),"EXPECTED_REJECTION" if aspect in NEGATIVE else "PASS")
    return s

def anchored():
    s=populated(); b=s.anchor_bundle("synthetic:negotiation-bundle:one",d("dossier"),d("receipt"),tuple(d(f"doc:{x}") for x in range(4)),tuple(d(f"adapter:{x}") for x in range(3))); return s,b

def specified():
    s,b=anchored()
    for party in ("TENANT_AGENCY","NURION_PG","UPSTREAM_PG"):
        s.add_profile(f"synthetic:capability-profile:{party.lower()}",party,1,2,("TOKEN_AMOUNT","TOKEN_ID"),("COPY_TOKEN","RENAME"))
    s.add_rule("synthetic:mapping-rule:order","order_token","merchant_token","COPY_TOKEN","TOKEN_ID")
    s.add_rule("synthetic:mapping-rule:amount","amount_token","amount_token","COPY_TOKEN","TOKEN_AMOUNT")
    return s,b

def proposed():
    s,b=specified(); r=s.propose_round("synthetic:negotiation-round:one","TENANT_AGENCY",1,"synthetic:correlation:one","synthetic:idempotency:one"); return s,b,r

def complete():
    s,b,r=proposed(); s.run_cases(r.round_id); receipt=s.review("synthetic:conformance-receipt:one",r.round_id,"synthetic:conformance-reviewer:reviewer",r.proposer); return s,b,r,receipt

class Tests(unittest.TestCase):
    def test_exact_matrix(self):
        e=populated().evidence(); self.assertEqual((e["control_count"],e["workstream_count"],e["controls_per_workstream"]),(400,16,25)); self.assertTrue(e["control_matrix_valid"])
    def test_exact_range(self): self.assertEqual(set(populated()._controls),set(range(3901,4301)))
    def test_partial_bundle_fails(self):
        s=populated(False)
        with self.assertRaises(GovernanceRejected): s.anchor_bundle("synthetic:negotiation-bundle:x",d("a"),d("b"),tuple(d(str(x)) for x in range(4)),tuple(d("a"+str(x)) for x in range(3)))
    def test_control_idempotency_conflict(self):
        s=populated(False); row=next(iter(s._controls.values())); args={k:v for k,v in row.__dict__.items() if k!="digest"}
        self.assertIs(s.add_control(**args),s.add_control(**args))
        with self.assertRaises(GovernanceRejected): s.add_control(**(args|{"fixture_digest":d("other")}))
    def test_bundle_shape_and_idempotency(self):
        s,b=anchored(); docs=tuple(x[1] for x in b.document_bindings); adapters=tuple(x[1] for x in b.adapter_bindings)
        self.assertIs(s.anchor_bundle(b.bundle_id,b.dossier_digest,b.receipt_digest,docs,adapters),b)
        with self.assertRaises(GovernanceRejected): s.anchor_bundle(b.bundle_id,b.dossier_digest,b.receipt_digest,docs[:3],adapters)
    def test_profiles_require_three_parties(self):
        s,_=anchored(); s.add_profile("synthetic:capability-profile:t","TENANT_AGENCY",1,1,("TOKEN_ID",),("COPY_TOKEN",))
        with self.assertRaises(GovernanceRejected): s.propose_round("synthetic:negotiation-round:x","TENANT_AGENCY",1,"synthetic:correlation:x","synthetic:idempotency:x")
    def test_profile_disallows_executable_op(self):
        s,_=anchored()
        with self.assertRaises(GovernanceRejected): s.add_profile("synthetic:capability-profile:t","TENANT_AGENCY",1,1,("TOKEN_ID",),("HTTP_POST",))
    def test_rule_allowlist_and_unique_source(self):
        s,_=specified()
        with self.assertRaises(GovernanceRejected): s.add_rule("synthetic:mapping-rule:x","order_token","x","HTTP_POST","TOKEN_ID")
        with self.assertRaises(GovernanceRejected): s.add_rule("synthetic:mapping-rule:y","order_token","y","RENAME","TOKEN_ID")
    def test_version_intersection_fail_closed(self):
        s,_=specified()
        with self.assertRaises(GovernanceRejected): s.propose_round("synthetic:negotiation-round:x","TENANT_AGENCY",3,"synthetic:correlation:x","synthetic:idempotency:x")
        self.assertEqual(s.evidence()["hold_count"],1)
    def test_round_fixed_review_state(self):
        _,_,r=proposed(); self.assertEqual(r.status,"REVIEW_REQUIRED")
    def test_round_chain_and_bounded(self):
        s,_,r=proposed()
        r2=s.propose_round("synthetic:negotiation-round:two","NURION_PG",1,r.correlation_id,r.idempotency_key)
        r3=s.propose_round("synthetic:negotiation-round:three","UPSTREAM_PG",1,r.correlation_id,r.idempotency_key)
        self.assertEqual((r2.previous_digest,r3.previous_digest),(r.digest,r2.digest))
        with self.assertRaises(GovernanceRejected): s.propose_round("synthetic:negotiation-round:four","TENANT_AGENCY",1,r.correlation_id,r.idempotency_key)
    def test_round_lineage_conflict(self):
        s,_,r=proposed()
        with self.assertRaises(GovernanceRejected): s.propose_round("synthetic:negotiation-round:two","NURION_PG",1,"synthetic:correlation:other",r.idempotency_key)
    def test_400_cases(self):
        s,_,r=proposed(); rows=s.run_cases(r.round_id); self.assertEqual(len(rows),400); self.assertTrue(all(x.status=="SYNTHETIC_PASS" for x in rows))
    def test_cases_single_run(self):
        s,_,r=proposed(); s.run_cases(r.round_id)
        with self.assertRaises(GovernanceRejected): s.run_cases(r.round_id)
    def test_review_separation(self):
        s,_,r=proposed(); s.run_cases(r.round_id)
        with self.assertRaises(GovernanceRejected): s.review("synthetic:conformance-receipt:x",r.round_id,"synthetic:conformance-reviewer:tenant_agency",r.proposer)
        with self.assertRaises(GovernanceRejected): s.review("synthetic:conformance-receipt:x",r.round_id,"synthetic:conformance-reviewer:reviewer","forged-author")
    def test_review_requires_complete_cases(self):
        s,_,r=proposed()
        with self.assertRaises(GovernanceRejected): s.review("synthetic:conformance-receipt:x",r.round_id,"synthetic:conformance-reviewer:r",r.proposer)

    def test_cases_and_review_require_latest_round(self):
        s,_,r=proposed()
        latest=s.propose_round("synthetic:negotiation-round:two","NURION_PG",1,r.correlation_id,r.idempotency_key)
        with self.assertRaises(GovernanceRejected): s.run_cases(r.round_id)
        s.run_cases(latest.round_id)
        with self.assertRaises(GovernanceRejected):
            s.review("synthetic:conformance-receipt:x",r.round_id,"synthetic:conformance-reviewer:reviewer",r.proposer)

    def test_mapping_rules_require_common_party_capability(self):
        s,_=anchored()
        s.add_profile("synthetic:capability-profile:t","TENANT_AGENCY",1,1,("TOKEN_ID",),("COPY_TOKEN",))
        s.add_profile("synthetic:capability-profile:n","NURION_PG",1,1,("TOKEN_ID",),("COPY_TOKEN",))
        s.add_profile("synthetic:capability-profile:u","UPSTREAM_PG",1,1,("TOKEN_OTHER",),("COPY_TOKEN",))
        s.add_rule("synthetic:mapping-rule:x","a","b","COPY_TOKEN","TOKEN_ID")
        with self.assertRaises(GovernanceRejected):
            s.propose_round("synthetic:negotiation-round:x","TENANT_AGENCY",1,"synthetic:correlation:x","synthetic:idempotency:x")

    def test_event_artifact_rehash_substitution_detected(self):
        s,_=anchored(); event=s._events[0]
        payload=event|{"artifact_digest":d("substitute")}
        payload["digest"]=canonical_digest({k:v for k,v in payload.items() if k!="digest"})
        s._events[0]=payload
        self.assertFalse(s.evidence()["integrity_valid"])
    def test_receipt_never_approves(self):
        _,_,_,x=complete(); self.assertTrue(x.operator_approval_required); self.assertFalse(x.approval_recorded); self.assertEqual(x.status,"REVIEW_RECORDED_NOT_APPROVED")
    def test_control_rehash_tamper(self):
        s=populated(); row=s._controls[3901]; p=row.__dict__|{"workstream":"WRONG"}; p["digest"]=canonical_digest({k:v for k,v in p.items() if k!="digest"}); s._controls[3901]=replace(row,workstream="WRONG",digest=p["digest"]); self.assertFalse(s.evidence()["integrity_valid"])
    def test_bundle_rehash_tamper(self):
        s,b=anchored(); p=b.__dict__|{"status":"TRANSMITTED"}; p["digest"]=canonical_digest({k:v for k,v in p.items() if k!="digest"}); s._bundle=replace(b,status="TRANSMITTED",digest=p["digest"]); self.assertFalse(s.evidence()["integrity_valid"])
    def test_bundle_rehashed_flow_label_tamper(self):
        s,b=anchored(); bindings=(("nurion_to_upstream",b.document_bindings[0][1]),)+b.document_bindings[1:]; p=b.__dict__|{"document_bindings":bindings}; p["digest"]=canonical_digest({k:v for k,v in p.items() if k!="digest"}); s._bundle=replace(b,document_bindings=bindings,digest=p["digest"]); self.assertFalse(s.evidence()["integrity_valid"])
    def test_profile_rehash_tamper(self):
        s,_=specified(); row=s._profiles["TENANT_AGENCY"]; p=row.__dict__|{"mode":"ACTIVE"}; p["digest"]=canonical_digest({k:v for k,v in p.items() if k!="digest"}); s._profiles[row.party]=replace(row,mode="ACTIVE",digest=p["digest"]); self.assertFalse(s.evidence()["integrity_valid"])
    def test_round_semantic_rehash_tamper(self):
        s,_,r=proposed(); p=r.__dict__|{"status":"ACCEPTED"}; p["digest"]=canonical_digest({k:v for k,v in p.items() if k!="digest"}); s._rounds[0]=replace(r,status="ACCEPTED",digest=p["digest"]); self.assertFalse(s.evidence()["integrity_valid"])
    def test_case_rehash_tamper(self):
        s,_,r=proposed(); s.run_cases(r.round_id); row=s._cases[3901]; p=row.__dict__|{"observed_result":"PASS" if row.expected_result!="PASS" else "EXPECTED_REJECTION"}; p["digest"]=canonical_digest({k:v for k,v in p.items() if k!="digest"}); s._cases[3901]=replace(row,observed_result=p["observed_result"],digest=p["digest"]); self.assertFalse(s.evidence()["integrity_valid"])
    def test_event_rehash_semantic_tamper(self):
        s,_=anchored(); x=s._events[0]|{"action":"BUNDLE_TRANSMITTED"}; x["digest"]=canonical_digest({k:v for k,v in x.items() if k!="digest"}); s._events[0]=x; self.assertFalse(s.evidence()["integrity_valid"])
    def test_concurrent_same_control_converges(self):
        s=SyntheticDocumentNegotiationConformance(); cid=3901; args=(cid,WORKSTREAMS[0][2],CONTROL_ASPECTS[0],"synthetic:negotiation-requirement:00",d("f"),"PASS")
        with ThreadPoolExecutor(max_workers=8) as pool: rows=list(pool.map(lambda _:s.add_control(*args),range(20)))
        self.assertEqual(len({x.digest for x in rows}),1)
    def test_complete_evidence(self):
        s,_,_,_=complete(); e=s.evidence(); self.assertTrue(e["capability_ready"]); self.assertTrue(e["complete_review_evidence"]); self.assertEqual(e["conformance_case_count"],400)
    def test_non_execution_boundary(self):
        e=complete()[0].evidence(); keys=("external_calls","document_transmissions","electronic_signatures","external_pg_calls","card_network_calls","ledger_writes","money_movement","credential_reads","deployments","policy_prompt_weight_changes"); self.assertEqual(tuple(e[k] for k in keys),(0,)*len(keys)); self.assertFalse(e["approval_recorded"])

if __name__ == "__main__": unittest.main()
