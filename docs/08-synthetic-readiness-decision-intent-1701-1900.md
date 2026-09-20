# Synthetic Readiness Decision Intent #1701-#1900

This synthetic, in-memory layer converts an already reviewed readiness docket into an inert
operator-intent record. It does not approve, authorize, execute, deploy, call an external PG,
access production credentials, affect a payment or ledger, or mutate runtime policy.

## Workstreams

| Controls | Workstream | Boundary |
|---|---|---|
| #1701-#1725 | Readiness docket intake | Synthetic docket identifiers and content digests only |
| #1726-#1750 | Bounded intent batch | Deterministic, non-overlapping batches of at most 20 |
| #1751-#1775 | Operator intent draft | Three-value allowlist; no command or executable payload |
| #1776-#1800 | Independent intent review | Operator and reviewer separation with version binding |
| #1801-#1825 | Non-authorizing boundary | Explicit inert and non-executable assertions |
| #1826-#1850 | Rejection/integrity auto-hold | Rejections become append-only synthetic holds |
| #1851-#1875 | Intent receipt replay defense | Third-role verification and cross-docket reuse blocking |
| #1876-#1900 | Audit evidence | Record, event, artifact, batch, hold, and replay integrity |

## Maximum state

`SYNTHETIC_INTENT_RECORDED` means only that an independently reviewed synthetic intent was
recorded. It is not an operator decision, approval, authorization, or permission to execute.

## Fail-closed invariants

- Intake, batching, drafting, review, and receipt APIs use exact-retry idempotency.
- Conflicting retries, stale versions, ownership mismatches, unknown intent kinds, or cross-docket
  receipt substitution are rejected.
- Operator, reviewer, and verifier identities must be distinct.
- Every transition is attached to a content-addressed artifact and append-only event chain.
- Evidence re-computes artifacts and semantic event bindings instead of trusting stored digests.
