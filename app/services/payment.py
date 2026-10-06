"""Server-owned payment adapters for the development mock and Razorpay."""
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.platform import AuditLog, Booking, PaymentTransaction, PaymentWebhookEvent


class PaymentError(RuntimeError):
    pass


class PaymentProvider:
    name = "base"

    def create_payment(self, transaction):
        raise NotImplementedError

    def verify_payment(self, transaction, payment_id, order_id, signature):
        raise NotImplementedError

    def refund_payment(self, transaction):
        raise NotImplementedError


class MockPaymentProvider(PaymentProvider):
    name = "mock"

    def create_payment(self, transaction):
        transaction.status = "pending"
        return transaction

    def verify_payment(self, transaction, payment_id=None, order_id=None, signature=None):
        transaction.gateway_reference = f"mock-{transaction.booking_reference}"
        transaction.status = "paid"
        return True

    def refund_payment(self, transaction):
        raise PaymentError("Refunds are not available through the development mock.")


def _gateway_request(method, path, payload=None):
    key_id = os.getenv("RAZORPAY_KEY_ID", "").strip()
    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
    if not key_id or not key_secret:
        raise PaymentError("Razorpay credentials are not configured.")
    import base64

    authorization = base64.b64encode(f"{key_id}:{key_secret}".encode()).decode()
    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(
        f"https://api.razorpay.com/v1{path}",
        data=body,
        method=method,
        headers={"Authorization": f"Basic {authorization}", "Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read())
    except HTTPError as error:
        # Do not leak API response bodies or credentials into logs/errors.
        raise PaymentError(f"Razorpay request failed with HTTP {error.code}.") from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise PaymentError("Razorpay request could not be completed.") from error


def _amount_minor(transaction):
    try:
        amount = Decimal(str(transaction.amount))
    except (InvalidOperation, TypeError):
        raise PaymentError("Payment amount is invalid.")
    if amount <= 0 or transaction.currency != "INR":
        raise PaymentError("Razorpay payments require a positive INR amount.")
    minor = int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if minor < 100:
        raise PaymentError("Razorpay requires a minimum payment of INR 1.00.")
    return minor


class RazorpayPaymentProvider(PaymentProvider):
    name = "razorpay"

    def __init__(self, request_func=None):
        self.request = request_func or _gateway_request

    def create_payment(self, transaction):
        amount = _amount_minor(transaction)
        if transaction.provider_order_id:
            return transaction
        # Razorpay documents receipt as unique and idempotent for Order creation.
        receipt = ("aar-" + transaction.idempotency_key.replace(":", "-"))[:40]
        order_payload = {
            "amount": amount,
            "currency": transaction.currency,
            "receipt": receipt,
            "partial_payment": False,
            "notes": {"booking_reference": transaction.booking_reference},
        }
        order = None
        # Recover a prior successful create if the app lost its response before
        # saving the provider ID. Razorpay documents receipt filtering and uses
        # the unique receipt as an idempotency key for Orders.
        try:
            existing = self.request("GET", f"/orders?{urlencode({'receipt': receipt, 'count': 100})}")
            order = next((row for row in existing.get("items", []) if row.get("receipt") == receipt), None)
        except PaymentError:
            pass
        if order is None:
            try:
                order = self.request("POST", "/orders", order_payload)
            except PaymentError:
                # A duplicate receipt can mean another concurrent request
                # created the order. Fetch and validate it before reusing.
                existing = self.request("GET", f"/orders?{urlencode({'receipt': receipt, 'count': 100})}")
                order = next((row for row in existing.get("items", []) if row.get("receipt") == receipt), None)
                if order is None:
                    raise
        if (order.get("amount") != amount or order.get("currency") != transaction.currency
                or not order.get("id") or order.get("receipt") != receipt):
            raise PaymentError("Razorpay returned an order that does not match this booking.")
        transaction.provider_order_id = order["id"]
        transaction.status = "pending"
        return transaction

    def verify_payment(self, transaction, payment_id, order_id, signature):
        if not payment_id or not signature or not transaction.provider_order_id:
            return False
        if order_id != transaction.provider_order_id:
            return False
        secret = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
        expected = hmac.new(secret.encode(), f"{transaction.provider_order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            return False
        payment = self.request("GET", f"/payments/{payment_id}")
        expected_amount = _amount_minor(transaction)
        if (payment.get("id") != payment_id or payment.get("order_id") != transaction.provider_order_id
                or payment.get("amount") != expected_amount or payment.get("currency") != transaction.currency
                or payment.get("status") != "captured" or payment.get("captured") is not True):
            return False
        transaction.gateway_reference = payment_id
        return True

    def refund_payment(self, transaction):
        if transaction.status != "refund_pending" or transaction.refund_status != "initiating" or not transaction.gateway_reference:
            raise PaymentError("Only a verified captured payment can be refunded.")
        amount = _amount_minor(transaction)
        result = self.request("POST", f"/payments/{transaction.gateway_reference}/refund", {
            "amount": amount,
            "notes": {"payment_transaction_id": str(transaction.id), "booking_reference": transaction.booking_reference},
        })
        if (not result.get("id") or result.get("payment_id") != transaction.gateway_reference
                or result.get("amount") != amount or result.get("currency") != transaction.currency):
            raise PaymentError("Razorpay returned a refund that does not match this payment.")
        transaction.refund_reference = result["id"]
        transaction.refund_amount_minor = amount
        transaction.refund_status = result.get("status") or "pending"
        if transaction.refund_status == "processed":
            _mark_refunded(transaction)
        else:
            transaction.status = "refund_pending"
        return transaction


def provider():
    configured = os.getenv("PAYMENT_PROVIDER", "disabled").strip().lower()
    environment = os.getenv("APP_ENV", "development").strip().lower()
    if configured == "mock" and environment != "production":
        return MockPaymentProvider()
    if configured == "razorpay":
        if not all(os.getenv(name, "").strip() for name in ("RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "RAZORPAY_WEBHOOK_SECRET")):
            raise PaymentError("Razorpay payment configuration is incomplete.")
        return RazorpayPaymentProvider()
    raise PaymentError("No production payment provider is configured.")


def _audit(action, transaction, actor="payment-system"):
    db.session.add(AuditLog(
        actor_email=actor,
        action=action,
        object_type="payment_transaction",
        object_id=transaction.id,
        metadata_json={"booking_reference": transaction.booking_reference, "status": transaction.status,
                       "refund_status": transaction.refund_status},
    ))


def create_transaction(booking: Booking):
    existing = PaymentTransaction.query.filter_by(booking_id=booking.id).first()
    if existing:
        if existing.status == "failed":
            raise PaymentError("This payment attempt failed. Contact support before retrying.")
        if existing.status in {"refund_pending", "refunded"}:
            raise PaymentError("This booking payment is no longer payable.")
        if existing.status == "created":
            provider().create_payment(existing)
            db.session.commit()
        return existing
    if booking.payment_status != "unpaid":
        raise PaymentError("This booking is not eligible for payment.")
    transaction = PaymentTransaction(
        booking_id=booking.id,
        booking_reference=booking.booking_reference,
        amount=booking.amount or 0,
        currency=booking.currency,
        idempotency_key=f"booking:{booking.id}",
        status="created",
    )
    db.session.add(transaction)
    try:
        db.session.flush()
        # Persist the server-generated request identity before an external call.
        db.session.commit()
        selected = provider()
        selected.create_payment(transaction)
        _audit("payment_order_created", transaction)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = PaymentTransaction.query.filter_by(booking_id=booking.id).first()
        if existing is not None:
            return existing
        raise
    except Exception:
        db.session.rollback()
        raise
    return transaction


def verify_transaction(transaction, payment_id=None, order_id=None, signature=None):
    if transaction.status == "paid":
        return True
    # Razorpay does not guarantee webhook delivery order. A signed captured
    # event may follow a failure event for the same order attempt.
    if transaction.status not in {"pending", "failed"}:
        return False
    booking = db.session.get(Booking, transaction.booking_id)
    if (booking is None or transaction.booking_reference != booking.booking_reference
            or transaction.amount != (booking.amount or 0) or transaction.currency != booking.currency
            or booking.payment_status != "unpaid"):
        return False
    selected = provider()
    if not selected.verify_payment(transaction, payment_id, order_id, signature):
        return False
    booking.payment_status = "paid"
    transaction.status = "paid"
    _audit("payment_captured", transaction)
    db.session.commit()
    return True


def _mark_refunded(transaction):
    transaction.refund_status = "processed"
    transaction.status = "refunded"
    booking = db.session.get(Booking, transaction.booking_id)
    if booking:
        booking.payment_status = "refunded"


def refund_payment(transaction, actor):
    # Serialize refund initiation on the transaction row. This keeps parallel
    # admin requests from each reaching the provider with the same payment.
    transaction = db.session.execute(
        db.select(PaymentTransaction)
        .where(PaymentTransaction.id == transaction.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one()
    if transaction.status == "refunded" or transaction.refund_reference or transaction.refund_status:
        return transaction
    if transaction.status != "paid":
        raise PaymentError("Only a captured payment can be refunded.")
    if not transaction.gateway_reference:
        raise PaymentError("The captured payment reference is missing.")
    selected = provider()
    transaction.status = "refund_pending"
    transaction.refund_status = "initiating"
    _audit("payment_refund_initiated", transaction, actor)
    db.session.commit()
    try:
        selected.refund_payment(transaction)
        provider_ref = transaction.refund_reference
        amount_minor = transaction.refund_amount_minor
        provider_status = transaction.refund_status
        # A signed refund.processed webhook may arrive before the synchronous
        # refund API response. Preserve its terminal state when that happens.
        db.session.refresh(transaction)
        if transaction.status != "refunded":
            transaction.refund_reference = provider_ref
            transaction.refund_amount_minor = amount_minor
            transaction.refund_status = provider_status
            if provider_status == "processed":
                _mark_refunded(transaction)
            else:
                transaction.status = "refund_pending"
    except Exception:
        # An API timeout is ambiguous. Keep the durable initiation marker and
        # require provider reconciliation before any second refund request.
        transaction.refund_status = "reconciliation_required"
        _audit("payment_refund_reconciliation_required", transaction, actor)
        db.session.commit()
        raise
    _audit("payment_refund_submitted", transaction, actor)
    db.session.commit()
    return transaction


def verify_webhook(raw_body, signature, event_id):
    secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "").strip()
    if not secret or not event_id or len(event_id) > 180 or not signature:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def process_webhook(raw_body, event_id):
    payload = json.loads(raw_body)
    event_type = payload.get("event", "")
    digest = hashlib.sha256(raw_body).hexdigest()
    existing = PaymentWebhookEvent.query.filter_by(event_id=event_id).first()
    if existing:
        return "duplicate"
    event = PaymentWebhookEvent(event_id=event_id, event_type=event_type, payload_sha256=digest)
    db.session.add(event)
    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        return "duplicate"
    entity = payload.get("payload", {})
    if event_type == "payment.captured":
        payment = (entity.get("payment") or {}).get("entity", {})
        transaction = PaymentTransaction.query.filter_by(provider_order_id=payment.get("order_id")).first()
        if transaction and transaction.status in {"pending", "failed"}:
            if verify_transaction(transaction, payment.get("id"), payment.get("order_id"), _checkout_signature(transaction, payment.get("id"))):
                # verify_transaction commits payment and audit. Event is committed below.
                pass
    elif event_type == "payment.failed":
        payment = (entity.get("payment") or {}).get("entity", {})
        transaction = PaymentTransaction.query.filter_by(provider_order_id=payment.get("order_id")).first()
        if transaction and transaction.status == "pending":
            transaction.status = "failed"
            _audit("payment_failed", transaction)
    elif event_type == "refund.processed":
        refund = (entity.get("refund") or {}).get("entity", {})
        transaction = PaymentTransaction.query.filter_by(gateway_reference=refund.get("payment_id")).first()
        if transaction and transaction.status == "refund_pending":
            expected_amount = _amount_minor(transaction)
            if (refund.get("currency") == transaction.currency and refund.get("amount") == expected_amount
                    and (transaction.refund_reference is None or transaction.refund_reference == refund.get("id"))):
                transaction.refund_reference = refund.get("id")
                transaction.refund_amount_minor = expected_amount
                _mark_refunded(transaction)
                _audit("payment_refund_processed", transaction)
    db.session.commit()
    return "processed"


def _checkout_signature(transaction, payment_id):
    secret = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
    if not secret or not transaction.provider_order_id or not payment_id:
        return ""
    return hmac.new(secret.encode(), f"{transaction.provider_order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
