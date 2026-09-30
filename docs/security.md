# Security Controls and Limits

## Implemented in the repository

- Flask session cookies are `HttpOnly`, `SameSite=Lax`, and `Secure` in production.
- Production requires a 32+ character secret, explicit `TRUSTED_HOSTS`, PostgreSQL, Twilio Verify, S3-compatible storage, administrator credentials, and a non-memory rate-limit store.
- CSRF protection is enabled globally; production refuses `WTF_CSRF_ENABLED=false`. All rendered POST forms were audited for hidden CSRF tokens.
- Authenticated and administrator logout changes state only through POST. Admin GET logout displays a confirmation page.
- Global default limits and endpoint-specific OTP limits use Flask-Limiter. Production must configure a shared storage URI; `memory://` is rejected.
- Responses add `nosniff`, frame, referrer, permissions, and production HSTS headers.
- `ProxyFix` trusts one forwarded client, protocol, and host value. Configure only behind the expected single trusted proxy; do not expose the app directly with attacker-controlled forwarded headers.
- Public media and private verification files use separate namespaces. Local path resolution checks traversal and private/public boundaries. Uploads use randomized filenames, strict extensions, file signatures, and configured size limits.
- OTP challenges are hashed for local development, expire after five minutes, allow at most five attempts, are invalidated when replaced, cannot be replayed after verification, and have a per-phone resend cooldown plus IP rate limits. Twilio sends and verifies codes through Twilio Verify.
- Guide application IDs are bound to the authenticated phone. Traveler booking, profile, contact, notification, review, SOS, and payment lookups use the logged-in phone. Provider booking lookups bind provider identity, service type, and record ownership.
- Admin operational pages are read-only except for validated application decisions. Those decisions are CSRF-protected, state-checked, and audited.

## Not implemented or externally unverified

- No Content Security Policy is configured. Several templates contain inline scripts/styles; establish a CSP compatible with the UI before relying on it as a control.
- Hostname, proxy, TLS termination, cookie behavior, database backups, Redis persistence, S3 public-access policy, and alerting must be verified in the actual deployment.
- Twilio, PostgreSQL, Redis-compatible rate limiting, S3, and production Linux/Gunicorn have not been exercised in this workspace.
- There is no production payment-provider adapter, webhook signature validation, or refund flow. Production payment collection must remain disabled.
- SOS creates a local coordination record and displays user-initiated call/contact controls. It does not dispatch emergency services, share live location, or guarantee responder contact.

See [authorization-matrix.md](authorization-matrix.md), [payments.md](payments.md), [storage.md](storage.md), and [deployment.md](deployment.md) for route-specific rules and setup details.
