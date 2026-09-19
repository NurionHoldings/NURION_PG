# Synthetic Proposal Feasibility Assessment & Review Portfolio #2101-#2500

This module is synthetic-only, in-memory, non-authorizing, non-deployable,
and non-executable. It evaluates recorded planning proposals without invoking
an external PG, using production credentials, writing a ledger, or changing
runtime policy, prompts, or weights.

## Control groups

- #2101-#2300: recorded proposal intake, bounded assessment batches (maximum
  20), dependency allowlist, risk/rollback/evidence sufficiency, independent
  review and verifier receipt, rejection/integrity holds, replay defence.
- #2301-#2500: observation-only feasibility review portfolio, bounded cohort
  evidence, dependency/risk/rollback grouping, independent portfolio review,
  replay/hold integrity, and deterministic audit evidence.

The 16 workstreams contain exactly 25 controls each. The maximum observable
state is `SYNTHETIC_FEASIBILITY_RECORDED`; it grants no approval, execution,
deployment, payment, ledger, settlement, or policy authority.

## Roles and fail-closed boundaries

Planner/assessor, reviewer, verifier, and optional integrity auditor identities
must be independent. Dependency profiles are allowlisted. `HIGH` risk,
non-rollbackable proposals, and fewer than two evidence items fail closed.
Receipts are source-version and artifact-digest bound and cannot be replayed
across proposals or reused.

## Verification

```bash
PYTHONPATH=src python -m unittest tests.test_synthetic_proposal_feasibility_assessment -v
PYTHONPATH=src python -m unittest discover -s tests -q
PYTHONPATH=src python scripts/run_synthetic_proposal_feasibility_assessment_evidence.py
```
