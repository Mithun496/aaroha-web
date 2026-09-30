import os

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.platform import Booking, PaymentTransaction


class PaymentProvider:
    name = "base"

    def create(self, transaction):
        raise NotImplementedError

    def verify(self, transaction, gateway_reference):
        raise NotImplementedError


class MockPaymentProvider(PaymentProvider):
    name = "mock"

    def create(self, transaction):
        transaction.status = "pending"
        return transaction

    def verify(self, transaction):
        # This synthetic reference is generated inside the development adapter.
        # No browser-supplied value is accepted as payment-provider evidence.
        transaction.gateway_reference = f"mock-{transaction.booking_reference}"
        transaction.status = "paid"
        return True


def provider():
    configured = os.getenv("PAYMENT_PROVIDER", "disabled").strip().lower()
    if configured == "mock" and os.getenv("APP_ENV", "development").strip().lower() != "production":
        return MockPaymentProvider()
    raise RuntimeError("No production payment provider is configured.")


def create_transaction(booking: Booking):
    existing = PaymentTransaction.query.filter_by(booking_id=booking.id).first()
    if existing:
        return existing
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
        provider().create(transaction)
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


def verify_transaction(transaction):
    if transaction.status == "paid":
        return True
    if transaction.status != "pending":
        return False
    booking = db.session.get(Booking, transaction.booking_id)
    if (
        booking is None
        or transaction.booking_reference != booking.booking_reference
        or transaction.amount != (booking.amount or 0)
        or transaction.currency != booking.currency
    ):
        return False
    if not provider().verify(transaction):
        return False
    booking.payment_status = "paid"
    transaction.status = "paid"
    db.session.commit()
    return True
