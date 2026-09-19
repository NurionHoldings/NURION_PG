from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from hashlib import sha256
import unittest
from unittest.mock import patch

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_p0_design_baseline_rfc import (
    MAXIMUM_STATE, WORKSTREAMS, RFCBaseline, SyntheticP0DesignBaselineRFC,
)

def digest(x): return sha256(x.encode()).hexdigest()

def populated(full=False):
    s=SyntheticP0DesignBaselineRFC()
    s.add_source("synthetic:official-source:one","https://www.w3.org/TR/WCAG22/","Official Standard","2026-09-01","STANDARD","2027-09-01",digest("content"))
    streams=WORKSTREAMS if full else WORKSTREAMS[:2]
    for i,(start,end,name) in enumerate(streams):
        controls=range(start,end+1) if full else (start,)
        s.add_requirement(f"synthetic:p0-requirement:{i}",name,controls,"required safety rationale","identified threat",(digest(f"e{i}"),),"SECURITY",True,("synthetic:official-source:one",))
    return s

def drafted(full=True):
    s=populated(full); ids=tuple(s._requirements)
    return s,s.author("synthetic:p0-rfc:one","synthetic:rfc-author:author",ids)

def reviewed():
    s,r=drafted(); r=s.review("synthetic:rfc-review:one",r.rfc_id,r.version,"synthetic:rfc-reviewer:reviewer",True,digest("finding")); return s,r

def recorded():
    s,r=reviewed(); a=s.artifact("synthetic:rfc-review:one")
    r=s.record("synthetic:rfc-receipt:one",r.rfc_id,r.version,"synthetic:rfc-verifier:verifier",a.digest); return s,r

class Tests(unittest.TestCase):
    def test_exact_400_matrix(self):
        e=SyntheticP0DesignBaselineRFC().evidence(); self.assertEqual((e["control_count"],e["workstream_count"]),(400,16)); self.assertTrue(e["control_matrix_valid"])
    def test_full_registry_covers_matrix(self):
        s=populated(True); self.assertEqual(len({n for r in s._requirements.values() for n in r.control_ids}),400); self.assertTrue(s.evidence()["registry_integrity_valid"])
    def test_source_idempotency_conflict(self):
        s=SyntheticP0DesignBaselineRFC(); args=("synthetic:official-source:x","https://www.w3.org/TR/WCAG22/","X","2026-09-01","STANDARD","2027-01-01",digest("x")); self.assertIs(s.add_source(*args),s.add_source(*args));
        with self.assertRaises(GovernanceRejected): s.add_source(*args[:-1],digest("y"))
    def test_expired_unreviewed_bad_scheme_rejected(self):
        base=("synthetic:official-source:x","https://www.w3.org/TR/WCAG22/","X","2026-01-01","STANDARD")
        for tail in (("2026-09-18",digest("x"),True),("2027-01-01",digest("x"),False)):
            with self.assertRaises(GovernanceRejected): SyntheticP0DesignBaselineRFC().add_source(*base,*tail)
        with self.assertRaises(GovernanceRejected): SyntheticP0DesignBaselineRFC().add_source(base[0],"http://www.w3.org/TR/WCAG22/",*base[2:],"2027-01-01",digest("x"))
        with self.assertRaises(GovernanceRejected): SyntheticP0DesignBaselineRFC().add_source(base[0],"https://attacker.example/x",*base[2:],"2027-01-01",digest("x"))
    def test_duplicate_source_rejected(self):
        s=populated();
        with self.assertRaises(GovernanceRejected): s.add_source("synthetic:official-source:two","https://www.w3.org/TR/WCAG22/","Official Standard","2026-09-01","STANDARD","2027-09-01",digest("content"))
    def test_invalid_class_and_digest_rejected(self):
        for c,d in (("BLOG",digest("x")),("LAW","bad")):
            with self.assertRaises(GovernanceRejected): SyntheticP0DesignBaselineRFC().add_source("synthetic:official-source:x","https://www.w3.org/TR/WCAG22/","X","2026-09-01",c,"2027-01-01",d)
    def test_requirement_semantics(self):
        s=populated();
        for changes in ({"approval_required":False},{"owner_role":"BOT"},{"control_ids":(9999,)},{"acceptance_evidence":("bad",)}):
            args=dict(requirement_id="synthetic:p0-requirement:x",workstream=WORKSTREAMS[0][2],control_ids=(3102,),rationale="why",threat="threat",acceptance_evidence=(digest("e"),),owner_role="SECURITY",approval_required=True,source_ids=("synthetic:official-source:one",)); args.update(changes)
            with self.assertRaises(GovernanceRejected): s.add_requirement(**args)
    def test_control_overlap_rejected(self):
        s=populated();
        with self.assertRaises(GovernanceRejected): s.add_requirement("synthetic:p0-requirement:x",WORKSTREAMS[0][2],(3101,),"why","threat",(digest("e"),),"SECURITY",True,("synthetic:official-source:one",))
    def test_requirement_idempotency_conflict(self):
        s=populated(); r=next(iter(s._requirements.values())); args=tuple(getattr(r,x) for x in ("requirement_id","workstream","control_ids","rationale","threat","acceptance_evidence","owner_role","approval_required","source_ids")); self.assertIs(s.add_requirement(*args),s.add_requirement(*args))
        with self.assertRaises(GovernanceRejected): s.add_requirement(*args[:-2],False,args[-1])
    def test_author_idempotency_conflict(self):
        s,r=drafted(); self.assertIs(r,s.author(r.rfc_id,r.author,r.requirement_ids))
        with self.assertRaises(GovernanceRejected): s.author(r.rfc_id,"synthetic:rfc-author:other",r.requirement_ids)
    def test_partial_control_set_cannot_author_baseline(self):
        s=populated(False)
        with self.assertRaises(GovernanceRejected):
            s.author("synthetic:p0-rfc:partial","synthetic:rfc-author:a",tuple(s._requirements))
    def test_membership_reuse_rejected(self):
        s,r=drafted();
        with self.assertRaises(GovernanceRejected): s.author("synthetic:p0-rfc:two","synthetic:rfc-author:b",r.requirement_ids)
    def test_fixed_plain_text_and_boundary(self):
        s,r=recorded(); self.assertEqual(r.status,MAXIMUM_STATE); self.assertIn("운영자 승인",r.plain_summary[1]); e=s.evidence(); self.assertFalse(e["approval_recorded"]); self.assertTrue(e["operator_approval_required"])
    def test_reviewer_role_separation(self):
        s,r=drafted();
        with self.assertRaises(GovernanceRejected): s.review("synthetic:rfc-review:x",r.rfc_id,r.version,"synthetic:rfc-reviewer:author",True,digest("f"))
    def test_verifier_role_separation(self):
        s,r=reviewed(); a=s.artifact("synthetic:rfc-review:one")
        with self.assertRaises(GovernanceRejected): s.record("synthetic:rfc-receipt:x",r.rfc_id,r.version,"synthetic:rfc-verifier:reviewer",a.digest)
    def test_review_replay_and_conflict(self):
        s,r=drafted(); args=("synthetic:rfc-review:x",r.rfc_id,r.version,"synthetic:rfc-reviewer:r",False,digest("f")); out=s.review(*args); self.assertIs(out,s.review(*args)); self.assertEqual(out.status,"HELD")
        with self.assertRaises(GovernanceRejected): s.review(*args[:-1],digest("z"))
    def test_receipt_replay_and_conflict(self):
        s,r=reviewed(); a=s.artifact("synthetic:rfc-review:one"); args=("synthetic:rfc-receipt:x",r.rfc_id,r.version,"synthetic:rfc-verifier:v",a.digest); out=s.record(*args); self.assertIs(out,s.record(*args))
        with self.assertRaises(GovernanceRejected): s.record(*args[:-2],"synthetic:rfc-verifier:z",a.digest)
    def test_concurrent_record_converges(self):
        s,r=reviewed(); a=s.artifact("synthetic:rfc-review:one"); args=("synthetic:rfc-receipt:x",r.rfc_id,r.version,"synthetic:rfc-verifier:v",a.digest)
        with ThreadPoolExecutor(max_workers=8) as p: rows=list(p.map(lambda _:s.record(*args),range(20)))
        self.assertEqual(len({x.digest for x in rows}),1)
    def test_bounded_review_batch(self):
        s,r=drafted(); self.assertEqual(s.review_batch("synthetic:rfc-reviewer:r",(r.rfc_id,)),(r,))
        with self.assertRaises(GovernanceRejected): s.review_batch("synthetic:rfc-reviewer:r",tuple(str(x) for x in range(21)))
        with self.assertRaises(GovernanceRejected): s.review_batch("synthetic:rfc-reviewer:r",("synthetic:p0-rfc:missing",))
    def test_auditor_independence_and_hold(self):
        s,r=recorded(); out=s.audit_hold(r.rfc_id,r.version,"synthetic:rfc-auditor:a",digest("f")); self.assertEqual(out.status,"HELD")
    def test_auditor_collision_rejected(self):
        s,r=recorded();
        with self.assertRaises(GovernanceRejected): s.audit_hold(r.rfc_id,r.version,"synthetic:rfc-auditor:verifier",digest("f"))
    def test_source_tamper_detected(self):
        s=populated(); k=next(iter(s._sources)); s._sources[k]=replace(s._sources[k],title="forged"); self.assertFalse(s.evidence()["integrity_valid"])
    def test_requirement_self_rehash_semantic_tamper_detected(self):
        s=populated(); k=next(iter(s._requirements)); r=s._requirements[k]; p=r.__dict__|{"approval_required":False}; p["digest"]=s.requirement_digest(**{x:y for x,y in p.items() if x!="digest"}); s._requirements[k]=replace(r,approval_required=False,digest=p["digest"]); self.assertFalse(s.evidence()["registry_integrity_valid"])
    def test_rfc_plain_text_tamper_detected(self):
        s,r=drafted(); s._rfcs[r.rfc_id]=replace(r,plain_summary=("승인됨",)); self.assertFalse(s.evidence()["rfc_integrity_valid"])
    def test_event_tamper_detected(self):
        s,r=reviewed(); s._events[-1]["action"]="APPROVED"; self.assertFalse(s.evidence()["append_only_chain_valid"])
    def test_hold_semantic_tamper_detected(self):
        s,r=drafted(); r=s.review("synthetic:rfc-review:x",r.rfc_id,r.version,"synthetic:rfc-reviewer:r",False,digest("f")); s._holds[0]["actor"]="synthetic:rfc-reviewer:impostor"; self.assertFalse(s.evidence()["append_only_chain_valid"])
    def test_capability_gap_fail_closed(self):
        import nurion_pg.synthetic_p0_design_baseline_rfc as m
        with patch.object(m,"WORKSTREAMS",m.WORKSTREAMS[:-1]): e=SyntheticP0DesignBaselineRFC().evidence()
        self.assertFalse(e["capability_ready"]); self.assertIn("control_matrix",e["capability_gap_evidence"]["gaps"])
    def test_inert_contract(self):
        e=SyntheticP0DesignBaselineRFC().evidence(); self.assertEqual((e["external_calls"],e["external_pg_calls"],e["ledger_writes"],e["ui_generation"],e["runtime_policy_mutations"]),(0,0,0,0,0)); self.assertFalse(e["free_prompt_generation"])

if __name__=="__main__": unittest.main()
