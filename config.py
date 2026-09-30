import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv
from werkzeug.security import check_password_hash

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


def _database_url():
    value = os.getenv("DATABASE_URL", "").strip()
    if value.startswith("postgres://"):
        value = "postgresql+psycopg://" + value[len("postgres://"):]
    elif value.startswith("postgresql://") and "+psycopg" not in value:
        value = "postgresql+psycopg://" + value[len("postgresql://"):]
    elif value.startswith("sqlite:////") and re.match(r"^sqlite:////[A-Za-z]:", value):
        value = "sqlite:///" + value[len("sqlite:////") :]
    return value or f"sqlite:///{BASE_DIR / 'instance' / 'aaroha.db'}"


def _is_production():
    return os.getenv("APP_ENV", "development").strip().lower() == "production"


_environment = os.getenv("APP_ENV", "development").strip().lower()
if _environment not in {"development", "production", "testing"}:
    raise RuntimeError("APP_ENV must be development, testing, or production.")


class Config:
    APP_NAME = "AAROHA"
    DEBUG = False
    ENVIRONMENT = os.getenv("APP_ENV", "development").strip().lower()
    OTP_PROVIDER = os.getenv("OTP_PROVIDER", "console").strip().lower()
    PAYMENT_PROVIDER = os.getenv("PAYMENT_PROVIDER", "disabled").strip().lower()
    STORAGE_PROVIDER = os.getenv("STORAGE_PROVIDER", "local").strip().lower()
    TRUSTED_HOSTS = [host.strip() for host in os.getenv("TRUSTED_HOSTS", "").split(",") if host.strip()]

    SECRET_KEY = os.getenv("SECRET_KEY", "").strip()
    if _is_production() and len(SECRET_KEY) < 32:
        raise RuntimeError("SECRET_KEY must be set to a strong value in production.")
    if _is_production() and not os.getenv("ADMIN_EMAIL", "").strip():
        raise RuntimeError("ADMIN_EMAIL is required in production.")
    if _is_production() and not os.getenv("ADMIN_PASSWORD_HASH", "").strip():
        raise RuntimeError("ADMIN_PASSWORD_HASH is required in production.")
    if _is_production():
        try:
            check_password_hash(os.getenv("ADMIN_PASSWORD_HASH", ""), "configuration-validation-only")
        except (ValueError, TypeError) as error:
            raise RuntimeError("ADMIN_PASSWORD_HASH must be a valid Werkzeug password hash.") from error
    if _is_production() and not TRUSTED_HOSTS:
        raise RuntimeError("TRUSTED_HOSTS must list the production application hostnames.")
    if not SECRET_KEY:
        SECRET_KEY = "aaroha-local-development-key-change-before-production"

    if _is_production() and OTP_PROVIDER != "twilio":
        raise RuntimeError("OTP_PROVIDER=twilio is required in production.")
    if _is_production() and not all(os.getenv(name, "").strip() for name in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_VERIFY_SERVICE_SID")):
        raise RuntimeError("Twilio Verify credentials are required in production.")
    if _is_production() and PAYMENT_PROVIDER == "mock":
        raise RuntimeError("PAYMENT_PROVIDER=mock is not allowed in production.")
    if PAYMENT_PROVIDER not in {"disabled", "mock"}:
        raise RuntimeError("The configured PAYMENT_PROVIDER has no implemented adapter.")
    if _is_production() and STORAGE_PROVIDER != "s3":
        raise RuntimeError("STORAGE_PROVIDER=s3 is required in production.")
    if STORAGE_PROVIDER not in {"local", "s3"}:
        raise RuntimeError("Unsupported STORAGE_PROVIDER; choose local or s3.")
    if _is_production() and STORAGE_PROVIDER in {"", "local"}:
        raise RuntimeError("A persistent STORAGE_PROVIDER is required in production.")
    if _is_production() and STORAGE_PROVIDER == "s3" and not os.getenv("STORAGE_BUCKET", "").strip():
        raise RuntimeError("STORAGE_BUCKET is required when STORAGE_PROVIDER=s3.")
    storage_access_key = os.getenv("STORAGE_ACCESS_KEY", "").strip()
    storage_secret_key = os.getenv("STORAGE_SECRET_KEY", "").strip()
    if bool(storage_access_key) != bool(storage_secret_key):
        raise RuntimeError("STORAGE_ACCESS_KEY and STORAGE_SECRET_KEY must be configured together.")
    storage_endpoint = os.getenv("STORAGE_ENDPOINT", "").strip()
    if _is_production() and storage_endpoint and urlsplit(storage_endpoint).scheme != "https":
        raise RuntimeError("STORAGE_ENDPOINT must use HTTPS in production.")
    if _is_production() and not os.getenv("DATABASE_URL", "").strip().lower().startswith(("postgresql://", "postgresql+psycopg://", "postgres://")):
        raise RuntimeError("PostgreSQL DATABASE_URL is required in production.")

    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
    }

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _is_production()

    WTF_CSRF_ENABLED = os.getenv("WTF_CSRF_ENABLED", "true").strip().lower() not in {"0", "false", "no"}
    if _is_production() and not WTF_CSRF_ENABLED:
        raise RuntimeError("WTF_CSRF_ENABLED cannot be disabled in production.")
    WTF_CSRF_TIME_LIMIT = 3600

    RATELIMIT_DEFAULT = ["200 per day", "50 per hour"]
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    if _is_production() and RATELIMIT_STORAGE_URI.startswith("memory://"):
        raise RuntimeError("A shared RATELIMIT_STORAGE_URI is required in production.")

    JSON_SORT_KEYS = False

    PREFERRED_URL_SCHEME = "https" if _is_production() else "http"

    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
    if MAX_CONTENT_LENGTH < 1:
        raise RuntimeError("MAX_UPLOAD_BYTES must be greater than zero.")

    # Production deployment can provide a persistent storage directory.
    UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "instance" / "uploads")))
