# AAROHA — Travel Companion MVP

AAROHA is a travel companion focused on the Hampi region, with traveler tools, verified local guides, partner onboarding and an admin verification workflow.

## Included

- Traveler exploration for Hampi, Sanapur, Anegundi, Kamalapura, Gangavathi and Hosapete
- India Culture Guide
- Personalized trip planner MVP
- Offline Hampi travel pack download
- AAROHA SOS coordination page
- Verified guide directory and booking requests
- Guide partner onboarding and approval workflow
- Partner registration flows for bike rentals, auto drivers, coracle operators and resort owners
- Resort listing fields without online resort booking
- Admin login, application dashboard, guide review and decision workflow
- PostgreSQL-ready configuration and ordered Alembic migrations
- CSRF protection, rate limiting, secure cookies in production and security headers
- Gunicorn, Docker and Render deployment files
- `/health` endpoint for monitoring

## Local Development

```powershell
python -m pip install -r requirements.txt
copy .env.example .env
# Edit .env: keep APP_ENV=development; configure an admin hash if using /admin.
python run.py
```

The local mock OTP prints its code to the server console. The development payment mock can be confirmed locally and generates its synthetic reference internally; it is not a payment integration. Local storage writes under `instance/uploads`.

Create an administrator password hash with:

```powershell
python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('ChangeThisAdminPassword123!', method='pbkdf2:sha256'))"
```

Set the result and `ADMIN_EMAIL` in the local `.env`. The database defaults to SQLite when `DATABASE_URL` is unset. Run migrations with:

```powershell
python -m flask --app app db upgrade
```

## Production Configuration

Production startup requires `APP_ENV=production`, a 32+ character `SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD_HASH`, PostgreSQL `DATABASE_URL`, Twilio Verify credentials, a non-memory shared `RATELIMIT_STORAGE_URI`, and S3-compatible `STORAGE_PROVIDER=s3` with a bucket. Configure HTTPS termination and persistent backups. Do not use local SQLite, console OTP, local file storage, disabled CSRF, or the mock payment provider in production.

```bash
python -m flask --app app db upgrade
gunicorn -c gunicorn.conf.py wsgi:app
```

Environment variables and external requirements are detailed in [docs/deployment.md](docs/deployment.md).
Route ownership rules and security boundaries are documented in [docs/authorization-matrix.md](docs/authorization-matrix.md) and [docs/security.md](docs/security.md). See [docs/payments.md](docs/payments.md) and [docs/storage.md](docs/storage.md) for the current provider abstractions and verification limits.

## Known Production Gaps

The repository has no production payment-provider adapter and no refund flow. Keep `PAYMENT_PROVIDER=disabled` until a server-side provider adapter, signed callback verification, refund handling, and provider-specific tests are implemented. A real Twilio account, Redis-compatible shared limiter, PostgreSQL database, and S3-compatible bucket are also external requirements; they have not been exercised by the local test suite.

For repeatable local demo data only:

```bash
python -m flask --app app seed-destinations
python -m flask --app app seed-demo
```

S3-compatible storage uses `STORAGE_BUCKET`, optional `STORAGE_ENDPOINT` and `STORAGE_REGION`, and either IAM/default credential-chain access or `STORAGE_ACCESS_KEY` plus `STORAGE_SECRET_KEY`. `STORAGE_PUBLIC_BASE_URL` is optional and must point only at intentionally public media. Identity documents use the private namespace and are served only through the administrator route.

## Key URLs

- `/` — traveler home
- `/explore` — destination discovery
- `/trip-planner` — trip planner
- `/culture-guide` — culture guide
- `/guides` — verified guides
- `/offline` — offline travel pack
- `/sos` — safety workflow
- `/admin/login` — administrator login
- `/admin/operations` — administrator-only read-only operational data
- `/partner/dashboard` — approved guide dashboard
- `/health` — health check
