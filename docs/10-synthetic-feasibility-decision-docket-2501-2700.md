# Synthetic Feasibility Decision Docket #2501-#2700

This module receives an observation-only feasibility portfolio and records an
inert decision docket. It is synthetic-only, in-memory, non-authorizing,
non-deployable, and non-executable.

## Control groups

Eight workstreams contain exactly 25 controls each: portfolio intake, bounded
batching (maximum 20), source-version and digest binding, inert decision draft,
independent review, replay/conflict hold, inert receipt, and append-only audit
evidence. The maximum state is `SYNTHETIC_DECISION_DOCKET_RECORDED`.

## Separation and integrity

Portfolio observer, docket analyst, reviewer, verifier, and integrity auditor
are separated by identity. Drafts bind the original portfolio version and
digest. Receipts bind draft and review digests; review replay and receipt reuse
fail closed. Record, event, batch, artifact, and hold chains are append-only and
tamper-evident.

The typed upstream intake recomputes the complete `PortfolioObservation`
digest and bounds unique membership before accepting it, preventing an
unverified caller-supplied summary from crossing the layer boundary.

ARKAON capability-gap evidence independently exposes missing, duplicate, or
unexpected controls and integrity observability gaps. Any gap produces a
deterministic fail-closed result without changing policy, prompts, or weights.

## Verification

```bash
PYTHONPATH=src python -m unittest tests.test_synthetic_feasibility_decision_docket -v
PYTHONPATH=src python -m unittest discover -s tests -q
PYTHONPATH=src python scripts/run_synthetic_feasibility_decision_docket_evidence.py
```

No real payment, approval, cancellation, refund, settlement, transfer, card
network, external PG, production credential, ledger, deployment, or runtime
policy/prompt/weight mutation is available.
