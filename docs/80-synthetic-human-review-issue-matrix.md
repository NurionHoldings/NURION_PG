# Synthetic human-review issue matrix (#8701-#9100)

This stage converts the held proposal/counterargument/evidence bundles into a neutral comparison agenda for human review. It implements exactly 400 controls as 16 workstreams × 25 aspects.

The matrix preserves the four synthetic tenant↔NURION↔upstream PG directions and 20 ordered bundle positions. Each issue outcome is derived from actual claim, manifest, receipt, and version pairs in that precedence order. No answer-kind label can choose an outcome.

Each source bundle projection digest is recomputed from its flow, answer kind, claim, manifest, receipt, and version pairs. The source bundle-set digest is then recomputed from the complete ordered 20-projection set. Issues form an immediate-parent chain, and append-only event and hold chains fail closed on omission, reordering, replay, digest substitution, or partial batches. Source reviewers, compilers, chair, validator, matrix compiler, and matrix validator are role-separated.

Maximum state: `HUMAN_REVIEW_ISSUE_MATRIX_READY_ON_HOLD_NOT_CONCLUDED`.

This module is synthetic and in-memory only. It cannot transmit or sign documents, call a card network or external PG, approve/cancel/refund/settle/transfer money, write a real ledger, read operating credentials, deploy, conclude, recommend, accept, approve, activate, or alter policy, prompts, or weights.
