# AAROHA Payments

Payment behavior is selected with `PAYMENT_PROVIDER`. Payment amounts and currency come from the persisted booking. Browser input cannot set order amount, payment status, provider order reference or refund outcome.

## Development

Set `APP_ENV=development` and `PAYMENT_PROVIDER=mock` for local demonstrations and tests. The mock creates a pending transaction and an explicit local confirmation marks it paid with an internally generated `mock-` reference. It performs no money movement and does not implement refunds.

## Production: Razorpay Standard Checkout

Set `APP_ENV=production` and `PAYMENT_PROVIDER=razorpay`, then configure these deployment secrets:

- `RAZORPAY_KEY_ID`: public checkout key ID.
- `RAZORPAY_KEY_SECRET`: server-side API and payment-signature secret.
- `RAZORPAY_WEBHOOK_SECRET`: secret configured on the Razorpay webhook endpoint.

Configuration fails closed if any credential is absent; production rejects the mock provider. Keep all three values in the deployment secret manager, never in source, session or browser storage. `PAYMENT_PROVIDER=disabled` is safe when credentials are not yet configured, but leaves checkout unavailable.

The server creates a Razorpay Order using the booking's INR amount in paise and a unique receipt derived from the server transaction idempotency key. A repeated creation reuses an existing locally stored Order or looks it up by Razorpay's unique receipt before trying again. Checkout submits the returned provider identifiers and signature to AAROHA; the server verifies the HMAC, fetches the payment from Razorpay, and requires matching order, amount, INR currency and captured status before marking the booking paid.

Configure a HTTPS webhook URL at `/payments/razorpay/webhook` with `payment.captured`, `payment.failed`, and `refund.processed` events. The handler validates `X-Razorpay-Signature` against the unmodified request bytes using `RAZORPAY_WEBHOOK_SECRET` and deduplicates using `x-razorpay-event-id`. `payment.captured` is also checked against Razorpay's server-side payment API before fulfillment.

## Refunds

Only an authenticated administrator can initiate a full refund from Admin → Operations → Payment transactions. The refund links to the captured provider payment ID and uses the server-stored full booking amount. The result is not controlled by the browser. Refund initiation and completion are audit logged. If Razorpay returns a pending refund, the booking remains `refund_pending`; a signed `refund.processed` event validates payment, amount and currency before changing the booking to `refunded`.

If the refund API request times out, AAROHA records `reconciliation_required` and refuses another refund request. An administrator must reconcile the provider Dashboard/API state before any manual correction. This avoids duplicate refunds when the provider may have accepted a request whose response was lost.

The current payment model permits one payment transaction per booking. A failed Razorpay transaction is not silently retried or replaced; support must reconcile the failed attempt before a new payment can be created. No live or sandbox Razorpay credentials were available for this pass, so provider network calls, checkout, settlement and refunds have not been externally exercised. Automated tests mock the gateway transport.

## Provider References

- [Razorpay Orders API](https://razorpay.com/docs/api/orders/create/): server-created orders, smallest currency unit, unique receipts and receipt-based duplicate handling.
- [Razorpay checkout integration](https://razorpay.com/docs/server-integration/python/test-app/): checkout fields and payment signature verification.
- [Razorpay webhook validation](https://razorpay.com/docs/webhooks/validate-test/): raw-body HMAC and unique event IDs.
- [Razorpay webhook best practices](https://razorpay.com/docs/webhooks/best-practices/): at-least-once delivery and event ordering.
