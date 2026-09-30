# AAROHA Deployment

This guide describes the deployment code and required external services. Production payment code is implemented for Razorpay, but live payment processing still requires merchant credentials and an external sandbox validation.

## Local Development

Use `.env.example` as a development-only starting point. Local defaults are SQLite, console OTP, in-memory rate limits, local uploads, CSRF enabled, and the mock payment provider. Do not use these values in production.

```powershell
python -m pip install -r requirements.txt
copy .env.example .env
python -m flask --app app db upgrade
python run.py
```

## Production Requirements

Configure all of the following in the deployment environment, not in a committed file:

| Variable | Requirement |
| --- | --- |
| `APP_ENV` | Must be `production`. |
| `SECRET_KEY` | Random secret of at least 32 characters. |
| `ADMIN_EMAIL` | Required administrator login email. |
| `ADMIN_PASSWORD_HASH` | Werkzeug password hash, never a plaintext password. |
| `TRUSTED_HOSTS` | Comma-separated allowed hostnames, including the deployment hostname and any custom domains. |
| `DATABASE_URL` | PostgreSQL connection URL. SQLite is rejected in production. |
| `OTP_PROVIDER` | Must be `twilio`. |
| `TWILIO_ACCOUNT_SID` | Twilio account SID. |
| `TWILIO_AUTH_TOKEN` | Twilio secret; store only in deployment secrets. |
| `TWILIO_VERIFY_SERVICE_SID` | Twilio Verify service SID. |
| `RATELIMIT_STORAGE_URI` | Shared non-memory backend such as Redis, reachable by all workers. |
| `STORAGE_PROVIDER` | Must be `s3`. |
| `STORAGE_BUCKET` | Required S3-compatible bucket. |
| `STORAGE_ENDPOINT` | Optional endpoint for S3-compatible providers. |
| `STORAGE_REGION` | Optional when the S3 SDK environment supplies a region. |
| `STORAGE_ACCESS_KEY` / `STORAGE_SECRET_KEY` | Optional when using an IAM/default credential provider chain; never commit credentials. |
| `STORAGE_PUBLIC_BASE_URL` | Optional URL for public media only. Never point private identity keys at a public origin. |
| `PAYMENT_PROVIDER` | Set `razorpay` for production checkout or `disabled` to keep payments unavailable. Production rejects `mock`. |
| `RAZORPAY_KEY_ID` | Public Checkout key ID. Required when `PAYMENT_PROVIDER=razorpay`. |
| `RAZORPAY_KEY_SECRET` | Server-side API and Checkout signature secret. Required when `PAYMENT_PROVIDER=razorpay`. |
| `RAZORPAY_WEBHOOK_SECRET` | Secret configured for AAROHA's webhook URL. Required when `PAYMENT_PROVIDER=razorpay`. |
| `MAX_UPLOAD_BYTES` | Optional upload cap; defaults to 10 MiB. |
| `WTF_CSRF_ENABLED` | Must remain enabled. |
| `UPLOAD_DIR` | Writable local staging/root path; production private/public objects use S3. |
| `AI_PROVIDER` | Currently unused/disabled; no external AI integration is implemented. |
| `AUTO_CREATE_TABLES` | Development-only convenience; production ignores it and requires migrations. |
| `PORT` | Platform-provided listening port; Gunicorn defaults to `8000` if absent. |
| `HOST` | Used by `run.py` for local development only; defaults to `127.0.0.1`. |
| `GUNICORN_WORKERS` | Optional worker count; defaults to CPU-based calculation. |
| `GUNICORN_THREADS` | Optional threads per worker; defaults to `2`. |
| `GUNICORN_TIMEOUT` | Optional worker timeout in seconds; defaults to `60`. |
| `GUNICORN_LOG_LEVEL` | Optional Gunicorn log level; defaults to `info`. |

Keep `PAYMENT_PROVIDER=disabled` until the Razorpay merchant account, credentials and HTTPS webhook configuration are ready. Setting `PAYMENT_PROVIDER=razorpay` fails startup validation unless all three Razorpay variables are set. The adapter creates INR Orders, verifies checkout signatures and captured state server-to-server, and handles signed callbacks at `/payments/razorpay/webhook`. Configure `payment.captured`, `payment.failed` and `refund.processed`. Full refunds are admin initiated; pending refunds complete after a validated webhook. Validate the integration with Razorpay test credentials and test events before enabling live mode.

## Startup and Health

Expected build command:

```bash
pip install -r requirements.txt
```

Run migrations as a deployment pre-start/release step:

```bash
python -m flask --app app db upgrade
```

Start command:

```bash
gunicorn -c gunicorn.conf.py wsgi:app
```

Health endpoint: `/health`. It executes `SELECT 1` and returns 503 when the configured database is unavailable. The app does not seed demo data during startup. Production schema creation must use migrations; `AUTO_CREATE_TABLES` is ignored in production.

The Docker image uses Gunicorn and applies migrations before starting the server. Render's `preDeployCommand` applies the same migration. Confirm the selected Render plan includes the required PostgreSQL, persistent Redis-compatible rate-limit service, and object storage; ephemeral filesystem storage is not suitable for private documents.

## Deployment Checklist

- Use HTTPS and confirm the proxy topology before changing `ProxyFix` trust counts.
- Use a supported production plan with backups, persistent PostgreSQL, and monitoring.
- Configure Twilio Verify, shared rate-limit storage, and private S3-compatible object storage.
- Keep identity documents private; use the administrator-only download route.
- Keep payment collection disabled until Razorpay test credentials and HTTPS webhook configuration have been validated in an external sandbox.
- Run tests, clean-database migrations, and an external-service smoke test in the deployment environment.
- Do not claim PostgreSQL, Twilio, Redis, S3, or payment-provider verification based only on local tests.
