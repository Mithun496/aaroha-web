import logging
import os
import re
import secrets

from werkzeug.security import check_password_hash

logger = logging.getLogger(__name__)


def _provider():
    return os.getenv("OTP_PROVIDER", "console").strip().lower()


def _is_production():
    return os.getenv("APP_ENV", "development").strip().lower() == "production"


def _twilio_client():
    from twilio.rest import Client

    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    if not account_sid or not auth_token:
        raise RuntimeError("Twilio OTP provider is not fully configured.")
    return Client(account_sid, auth_token)


def normalize_phone_number(phone_number: str, default_country_code: str = "+91") -> str:
    candidate = (phone_number or "").strip().replace(" ", "")
    if not candidate:
        raise ValueError("Phone number is required.")
    candidate = candidate.replace(" ", "")
    candidate = candidate.replace("-", "")
    if candidate.startswith("00"):
        candidate = "+" + candidate[2:]
    if candidate.startswith("+"):
        normalized = candidate
    else:
        normalized = f"{default_country_code}{candidate}"
    if not re.fullmatch(r"\+[1-9]\d{7,14}", normalized):
        raise ValueError("Phone number is invalid.")
    return normalized


def generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def send_code(phone_number: str, code: str) -> bool:
    provider = _provider()
    if provider == "console":
        if _is_production():
            raise RuntimeError("Console OTP is disabled in production.")
        print(f"AAROHA DEVELOPMENT OTP for {phone_number}: {code}")
        return True
    if provider == "twilio":
        service_sid = os.getenv("TWILIO_VERIFY_SERVICE_SID", "").strip()
        if not service_sid:
            raise RuntimeError("Twilio OTP provider is not fully configured.")
        _twilio_client().verify.v2.services(service_sid).verifications.create(to=phone_number, channel="sms")
        return True
    raise RuntimeError(f"Unsupported OTP_PROVIDER: {provider}")


def verify_code(phone_number: str, supplied_code: str, expected_hash: str | None) -> bool:
    if not supplied_code or not supplied_code.strip():
        return False
    if _provider() == "twilio":
        service_sid = os.getenv("TWILIO_VERIFY_SERVICE_SID", "").strip()
        if not service_sid:
            raise RuntimeError("Twilio OTP provider is not fully configured.")
        try:
            result = _twilio_client().verify.v2.services(service_sid).verification_checks.create(
                to=phone_number,
                code=supplied_code.strip(),
            )
            return result.status == "approved"
        except Exception as exc:  # pragma: no cover - provider failure
            logger.warning("Twilio Verify check failed: %s", exc)
            return False
    if not expected_hash:
        return False
    try:
        return check_password_hash(expected_hash, supplied_code.strip())
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.warning("OTP verification failed for %s: %s", phone_number, exc)
        return False
