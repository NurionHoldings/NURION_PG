# Synthetic Canary Readiness Docket #1501-#1700

This milestone adds a synthetic, in-memory readiness observation docket over completed canary metadata. It does not approve, deploy, authorize, deliver, pay, settle, transfer, access production credentials, call an external PG, write a real ledger, or change runtime policy.

## Control portfolio

| Range | Workstream | Controls |
|---|---|---:|
| #1501-#1525 | Completed canary intake | 25 |
| #1526-#1550 | Bounded portfolio batch (max 20) | 25 |
| #1551-#1575 | Minimum sample and completion validation | 25 |
| #1576-#1600 | Error-rate and p95 aggregation | 25 |
| #1601-#1625 | Independent readiness review | 25 |
| #1626-#1650 | Regression and integrity auto-hold | 25 |
| #1651-#1675 | Unauthorized docket and replay defense | 25 |
| #1676-#1700 | Audit evidence | 25 |

## State boundary

`INTAKE -> PORTFOLIO_BATCHED -> METRICS_ACCEPTED -> SYNTHETIC_READINESS_REVIEWED`

Any failed sample, completion, error, latency, or review condition terminates at `HELD`. `SYNTHETIC_READINESS_REVIEWED` is the maximum state and conveys no approval or operational authority.

## Integrity and concurrency

- An `RLock` serializes intake, portfolio reservation, aggregation, review, and one-time verification.
- Batch membership is deterministic, bounded to 20, unique within and across batches, and digest-bound.
- Completion and error thresholds use integer cross-products to preserve exact fractional boundaries.
- Aggregator, reviewer, and verifier identities are role-separated.
- Records, events, holds, metrics receipts, batches, and dockets are content-addressed and version-bound.
- Fabricated dockets, cross-canary replay, stale versions, semantic attachment substitution, and docket reuse fail closed.

## Verification

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_synthetic_canary_readiness_docket -v
PYTHONPATH=src python scripts/run_synthetic_canary_readiness_docket_evidence.py
PYTHONPATH=src python -m unittest discover -s tests -v
```
