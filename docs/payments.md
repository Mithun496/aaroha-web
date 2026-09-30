# Payment Behavior

## Development Mock

Set `APP_ENV=development` and `PAYMENT_PROVIDER=mock` only for local demonstrations and tests. The mock creates a pending transaction. An explicit local confirmation invokes the mock adapter, which generates `mock-<booking_reference>` internally; no browser-supplied transaction reference is trusted. That synthetic reference is not evidence of money movement. The mock stores no card number, CVV, or payment secret.

Transaction creation is unique per booking and uses a deterministic `booking:<booking_id>` idempotency key. The transaction amount and currency are copied from the server-owned booking. Verification checks transaction state and rechecks amount, currency, and booking reference before changing the booking payment status. Repeated verification for an already-paid transaction is idempotent.

## Production Provider

No production payment adapter exists. Configuration rejects named providers without an implementation; `PAYMENT_PROVIDER=mock` is rejected in production. `PAYMENT_PROVIDER=disabled` is the only supported production setting, and payment routes cannot collect or verify a real payment in this state.

Before enabling a provider, implement and test:

- Server-side checkout/session creation using the booking amount and currency.
- Provider-owned transaction references and deterministic idempotency passed to the provider.
- Authenticated, signature-verified callbacks or server-to-server status lookup. A browser-supplied reference must never mark a transaction paid.
- Duplicate, out-of-order, malformed, and replayed callback behavior.
- Explicit invalid-state handling and payment reconciliation.
- An authorized refund operation and provider-confirmed refund result. No refund flow currently exists.
- Provider failure handling, timeouts, logging without secrets, and tests against the provider's sandbox.

Do not collect/store card details, CVV, payment credentials, or raw provider secrets in AAROHA. Keep payment disabled until an adapter and these controls are in place. Real provider credentials and live/sandbox verification are external requirements; no live payment test has been performed.
