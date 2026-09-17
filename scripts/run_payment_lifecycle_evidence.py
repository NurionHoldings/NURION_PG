"""Run a deterministic full synthetic payment lifecycle."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

from nurion_pg.payment_lifecycle import PaymentEngine, PaymentState


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    policy = json.loads(
        (ROOT / "config/payment-lifecycle-policy.json").read_text(encoding="utf-8")
    )
    if (
        set(policy["states"]) != {state.value for state in PaymentState}
        or set(policy["commands"]) != {"create", "authorize", "capture", "cancel", "refund"}
        or policy["mode"] != "UNREGISTERED_SYNTHETIC_ONLY"
        or policy["partial_capture_allowed"] is not False
        or policy["optimistic_version_required"] is not True
        or policy["idempotency_required"] is not True
        or policy["balanced_ledger_required"] is not True
        or policy["provider_adapter_allowed"] is not False
        or policy["credential_access_allowed"] is not False
        or policy["real_payment_data_allowed"] is not False
        or policy["money_movement_allowed"] is not False
        or policy["production_activation_allowed"] is not False
    ):
        raise SystemExit("payment lifecycle policy drift detected")
    now = datetime(2026, 9, 17, tzinfo=UTC)
    engine = PaymentEngine()
    engine.create(
        intent_id="synthetic:intent:evidence-001",
        merchant_ref="synthetic:merchant:evidence",
        customer_ref="synthetic:customer:evidence",
        amount_minor=10000,
        currency="KRW",
        policy_digest=sha256(b"synthetic-policy-v1").hexdigest(),
        idempotency_key="synthetic:command:create:evidence-001",
        now=now,
    )
    engine.authorize(
        "synthetic:intent:evidence-001",
        expected_version=1,
        idempotency_key="synthetic:command:authorize:evidence-001",
        now=now + timedelta(seconds=1),
    )
    engine.capture(
        "synthetic:intent:evidence-001",
        expected_version=2,
        idempotency_key="synthetic:command:capture:evidence-001",
        now=now + timedelta(seconds=2),
    )
    engine.refund(
        "synthetic:intent:evidence-001",
        amount_minor=2500,
        expected_version=3,
        idempotency_key="synthetic:command:refund-1:evidence-001",
        now=now + timedelta(seconds=3),
    )
    engine.refund(
        "synthetic:intent:evidence-001",
        amount_minor=7500,
        expected_version=4,
        idempotency_key="synthetic:command:refund-2:evidence-001",
        now=now + timedelta(seconds=4),
    )
    report = engine.evidence()
    intent = engine.get("synthetic:intent:evidence-001")
    if (
        intent.state is not PaymentState.REFUNDED
        or len(engine.events) != 5
        or len(engine.ledger.journals) != 3
        or not report["event_chains_valid"]
        or report["real_money_moved"] is not False
    ):
        raise SystemExit("synthetic payment lifecycle invariant failed")
    output = ROOT / "build/synthetic-payment-lifecycle-evidence.json"
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode("utf-8")).hexdigest()
    output.with_suffix(".json.sha256").write_text(digest + "\n", encoding="ascii")
    print(f"synthetic payment lifecycle: PASS {digest}")


if __name__ == "__main__":
    main()
