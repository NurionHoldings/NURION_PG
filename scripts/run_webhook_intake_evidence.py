"""Exercise signature, duplicate, replay and order controls synthetically."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

from nurion_pg.webhook_intake import (
    SyntheticKeyRegistry,
    SyntheticVerificationKey,
    SyntheticWebhookIntake,
    WebhookDecision,
    WebhookEnvelope,
    WebhookEventType,
    sign_envelope,
)


ROOT = Path(__file__).resolve().parents[1]
SECRET = "synthetic:webhook-secret:only-for-tests:0001"


def envelope(*, event_id: str, nonce: str, sequence: int, event_type: WebhookEventType):
    amount = event_type in {WebhookEventType.CAPTURE_RESULT, WebhookEventType.REFUND_RESULT}
    payload = {
        "intent_id": "synthetic:intent:webhook-evidence",
        "expected_version": sequence,
        "outcome": "SUCCEEDED",
        **({"amount_minor": 1000} if amount else {}),
    }
    value = WebhookEnvelope(
        "synthetic-provider.invalid",
        "synthetic:key:001",
        event_id,
        nonce,
        "synthetic:intent:webhook-evidence",
        sequence,
        event_type,
        datetime(2026, 9, 17, tzinfo=UTC) + timedelta(seconds=sequence),
        payload,
        "sha256=" + "0" * 64,
    )
    return replace(value, signature=sign_envelope(value, SECRET))


def main() -> None:
    policy = json.loads((ROOT / "config/webhook-intake-policy.json").read_text(encoding="utf-8"))
    if (
        policy["mode"] != "UNREGISTERED_SYNTHETIC_ONLY"
        or set(policy["allowed_event_types"]) != {item.value for item in WebhookEventType}
        or policy["real_provider_allowed"] is not False
        or policy["real_personal_data_allowed"] is not False
        or policy["operational_secret_allowed"] is not False
        or policy["automatic_payment_application_allowed"] is not False
        or policy["network_listener_allowed"] is not False
        or policy["production_activation_allowed"] is not False
    ):
        raise SystemExit("webhook policy drift detected")
    key_registry = SyntheticKeyRegistry()
    key_registry.register(
        SyntheticVerificationKey(
            "synthetic-provider.invalid",
            "synthetic:key:001",
            SECRET,
            datetime(2026, 9, 1, tzinfo=UTC),
            datetime(2026, 10, 1, tzinfo=UTC),
        )
    )
    intake = SyntheticWebhookIntake(
        key_registry,
        max_age_seconds=policy["max_age_seconds"],
        future_skew_seconds=policy["future_skew_seconds"],
        max_payload_bytes=policy["max_payload_bytes"],
    )
    received_at = datetime(2026, 9, 17, 0, 5, tzinfo=UTC)
    second = envelope(
        event_id="synthetic:event:002", nonce="synthetic:nonce:002", sequence=2,
        event_type=WebhookEventType.CAPTURE_RESULT,
    )
    if intake.ingest(second, received_at=received_at).decision is not WebhookDecision.QUARANTINED:
        raise SystemExit("out-of-order event must be quarantined")
    first = envelope(
        event_id="synthetic:event:001", nonce="synthetic:nonce:001", sequence=1,
        event_type=WebhookEventType.AUTHORIZATION_RESULT,
    )
    if intake.ingest(first, received_at=received_at).decision is not WebhookDecision.ACCEPTED:
        raise SystemExit("valid first event must be accepted")
    if intake.retry_quarantined(second.event_id, now=received_at).decision is not WebhookDecision.ACCEPTED:
        raise SystemExit("resolved sequence gap must release quarantine")
    if intake.ingest(first, received_at=received_at).decision is not WebhookDecision.DUPLICATE:
        raise SystemExit("exact replay must be idempotent duplicate")
    tampered = replace(first, signature="sha256=" + "f" * 64, event_id="synthetic:event:bad")
    if intake.ingest(tampered, received_at=received_at).decision is not WebhookDecision.BLOCKED:
        raise SystemExit("tampered signature must be blocked")
    report = intake.evidence()
    if (
        not report["receipt_chain_valid"]
        or report["payment_state_automatically_changed"] is not False
        or report["production_activation_allowed"] is not False
    ):
        raise SystemExit("webhook evidence boundary failed")
    output = ROOT / "build/synthetic-webhook-intake-evidence.json"
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode("utf-8")).hexdigest()
    output.with_suffix(".json.sha256").write_text(digest + "\n", encoding="ascii")
    print(f"synthetic webhook intake: PASS {digest}")


if __name__ == "__main__":
    main()

