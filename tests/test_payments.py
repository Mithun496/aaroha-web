import hashlib
import hmac
import json
import os
import unittest
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.models.platform import Booking, PaymentTransaction, PaymentWebhookEvent
from app.services.payment import (
    PaymentError,
    RazorpayPaymentProvider,
    create_transaction,
    refund_payment,
    verify_transaction,
)
from config import Config


class PaymentTests(unittest.TestCase):
    class TestConfig(Config):
        TESTING = True
        SECRET_KEY = "payment-test-secret"
        WTF_CSRF_ENABLED = False
        SQLALCHEMY_DATABASE_URI = "sqlite://"
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        ENVIRONMENT = "testing"
        PAYMENT_PROVIDER = "mock"
        RAZORPAY_KEY_ID = "rzp_test_key"

    def setUp(self):
        self.app = create_app(self.TestConfig)
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            self.booking = Booking(
                traveler_phone="+919800000099",
                booking_type="guide",
                booking_reference="AAR-PAYMENT-TEST",
                amount=1250.50,
                currency="INR",
                payment_status="unpaid",
                status="confirmed",
            )
            self.second_booking = Booking(
                traveler_phone="+919800000098", booking_type="guide", booking_reference="AAR-PAYMENT-TEST2",
                amount=1250.50, currency="INR", payment_status="unpaid", status="confirmed",
            )
            db.session.add_all([self.booking, self.second_booking])
            db.session.commit()
            self.booking_id = self.booking.id
            self.second_booking_id = self.second_booking.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def get_booking(self):
        return db.session.get(Booking, self.booking_id)

    def test_provider_config_fails_closed_when_razorpay_keys_are_missing(self):
        from app.services.payment import provider
        with patch.dict(os.environ, {"PAYMENT_PROVIDER": "razorpay", "APP_ENV": "production"}, clear=True):
            with self.assertRaises(PaymentError):
                provider()

    def test_create_uses_server_amount_currency_and_idempotent_receipt(self):
        calls = []

        def request(method, path, payload=None):
            calls.append((method, path, payload))
            if method == "GET":
                return {"items": []}
            return {"id": "order_test_1", "amount": 125050, "currency": "INR", "receipt": payload["receipt"]}

        with self.app.app_context(), patch.dict(os.environ, {"RAZORPAY_KEY_ID": "key", "RAZORPAY_KEY_SECRET": "secret"}):
            transaction = PaymentTransaction(
                booking_id=self.booking_id,
                booking_reference=self.get_booking().booking_reference,
                amount=1250.50,
                currency="INR",
                idempotency_key="booking:1",
                status="created",
            )
            db.session.add(transaction)
            db.session.flush()
            adapter = RazorpayPaymentProvider(request)
            adapter.create_payment(transaction)
            adapter.create_payment(transaction)
            self.assertEqual(transaction.provider_order_id, "order_test_1")
            self.assertEqual(calls[1][2]["amount"], 125050)
            self.assertEqual(calls[1][2]["currency"], "INR")
            self.assertEqual(calls[1][2]["partial_payment"], False)
            self.assertEqual(len(calls), 2)

    def test_traveler_checkout_uses_server_created_order_and_public_key_only(self):
        self.app.config["RAZORPAY_KEY_ID"] = "rzp_test_public"
        def request(method, path, payload=None):
            if method == "GET":
                return {"items": []}
            return {"id": "order_checkout", "amount": 125050, "currency": "INR", "receipt": payload["receipt"]}

        with self.client.session_transaction() as session:
            session.update(authenticated=True, account_type="traveler", phone_number="+919800000099")
        with patch.dict(os.environ, {"PAYMENT_PROVIDER": "razorpay", "APP_ENV": "development",
            "RAZORPAY_KEY_ID": "rzp_test_public", "RAZORPAY_KEY_SECRET": "never-render-secret",
            "RAZORPAY_WEBHOOK_SECRET": "never-render-webhook"}), patch("app.services.payment._gateway_request", side_effect=request):
            response = self.client.post("/payments/AAR-PAYMENT-TEST")
        body=response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("order_checkout", body)
        self.assertIn("rzp_test_public", body)
        self.assertNotIn("never-render-secret", body)
        self.assertNotIn("never-render-webhook", body)
        self.assertIn("125050", body)

    def test_order_response_mismatch_is_rejected(self):
        def request(method, path, payload=None):
            if method == "GET":
                return {"items": []}
            return {"id": "order_bad", "amount": 100, "currency": "USD", "receipt": payload["receipt"]}

        with self.app.app_context(), patch.dict(os.environ, {"RAZORPAY_KEY_ID": "key", "RAZORPAY_KEY_SECRET": "secret"}):
            transaction = PaymentTransaction(booking_id=self.booking_id, booking_reference=self.get_booking().booking_reference,
                amount=1250.50, currency="INR", idempotency_key="booking:2", status="created")
            db.session.add(transaction)
            db.session.flush()
            with self.assertRaises(PaymentError):
                RazorpayPaymentProvider(request).create_payment(transaction)

    def test_verification_checks_signature_server_payment_and_amount_currency_booking(self):
        key_secret = "test-secret"
        payment_response = {"id": "pay_good", "order_id": "order_good", "amount": 125050,
                           "currency": "INR", "status": "captured", "captured": True}

        def request(method, path, payload=None):
            return payment_response

        with self.app.app_context(), patch.dict(os.environ, {
            "PAYMENT_PROVIDER": "razorpay", "APP_ENV": "development", "RAZORPAY_KEY_ID": "key",
            "RAZORPAY_KEY_SECRET": key_secret, "RAZORPAY_WEBHOOK_SECRET": "webhook",
        }), patch("app.services.payment.RazorpayPaymentProvider", return_value=RazorpayPaymentProvider(request)):
            transaction = PaymentTransaction(booking_id=self.booking_id, booking_reference=self.get_booking().booking_reference,
                amount=1250.50, currency="INR", idempotency_key="booking:3", status="pending", provider_order_id="order_good")
            db.session.add(transaction)
            db.session.commit()
            signature = hmac.new(key_secret.encode(), b"order_good|pay_good", hashlib.sha256).hexdigest()
            self.assertTrue(verify_transaction(transaction, "pay_good", "order_good", signature))
            self.assertTrue(verify_transaction(transaction, "attacker", "wrong", "bad"))
            self.assertEqual(self.get_booking().payment_status, "paid")

            mismatch = PaymentTransaction(booking_id=self.second_booking_id, booking_reference=db.session.get(Booking, self.second_booking_id).booking_reference,
                amount=1250.50, currency="INR", idempotency_key="booking:4", status="pending", provider_order_id="order_good_2")
            db.session.add(mismatch)
            db.session.commit()
            payment_response.update(id="pay_bad", order_id="order_good_2", currency="USD")
            signature = hmac.new(key_secret.encode(), b"order_good_2|pay_bad", hashlib.sha256).hexdigest()
            self.assertFalse(verify_transaction(mismatch, "pay_bad", "order_good_2", signature))
            self.assertEqual(mismatch.status, "pending")
            payment_response.update(id="pay_amount", currency="INR", amount=125049)
            signature = hmac.new(key_secret.encode(), b"order_good_2|pay_amount", hashlib.sha256).hexdigest()
            self.assertFalse(verify_transaction(mismatch, "pay_amount", "order_good_2", signature))
            self.assertEqual(mismatch.status, "pending")
            payment_response.update(id="pay_good_2", amount=125050)
            mismatch.amount = 1250.49
            signature = hmac.new(key_secret.encode(), b"order_good_2|pay_good_2", hashlib.sha256).hexdigest()
            self.assertFalse(verify_transaction(mismatch, "pay_good_2", "order_good_2", signature))

    def test_refund_is_authorized_by_server_adapter_and_idempotent(self):
        calls = []

        def request(method, path, payload=None):
            calls.append((method, path, payload))
            return {"id": "rfnd_test", "payment_id": "pay_test", "amount": 125050,
                    "currency": "INR", "status": "pending"}

        with self.app.app_context(), patch.dict(os.environ, {
            "PAYMENT_PROVIDER": "razorpay", "APP_ENV": "production", "RAZORPAY_KEY_ID": "key",
            "RAZORPAY_KEY_SECRET": "secret", "RAZORPAY_WEBHOOK_SECRET": "webhook",
        }), patch("app.services.payment.RazorpayPaymentProvider", return_value=RazorpayPaymentProvider(request)):
            transaction = PaymentTransaction(booking_id=self.booking_id, booking_reference=self.get_booking().booking_reference,
                amount=1250.50, currency="INR", idempotency_key="booking:5", status="paid", gateway_reference="pay_test")
            db.session.add(transaction)
            db.session.commit()
            refund_payment(transaction, "admin@example.test")
            refund_payment(transaction, "admin@example.test")
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][1], "/payments/pay_test/refund")
            self.assertEqual(calls[0][2]["amount"], 125050)
            self.assertEqual(transaction.status, "refund_pending")
            self.assertEqual(transaction.refund_status, "pending")
            self.assertFalse(self.get_booking().payment_status == "refunded")

    def test_admin_refund_action_is_authorized_and_audited(self):
        from app.models.platform import AuditLog
        calls = []

        def request(method, path, payload=None):
            calls.append(path)
            return {"id": "rfnd_admin", "payment_id": "pay_admin", "amount": 125050, "currency": "INR", "status": "pending"}

        with self.app.app_context():
            transaction = PaymentTransaction(booking_id=self.booking_id, booking_reference=self.get_booking().booking_reference,
                amount=1250.50, currency="INR", idempotency_key="booking:8", status="paid", gateway_reference="pay_admin")
            db.session.add(transaction)
            db.session.commit()
            transaction_id = transaction.id
        with self.client.session_transaction() as session:
            session.update(admin_authenticated=True, admin_email="ops@example.test")
        with patch.dict(os.environ, {"PAYMENT_PROVIDER": "razorpay", "APP_ENV": "production",
            "RAZORPAY_KEY_ID": "key", "RAZORPAY_KEY_SECRET": "secret", "RAZORPAY_WEBHOOK_SECRET": "webhook"}), \
            patch("app.services.payment.RazorpayPaymentProvider", return_value=RazorpayPaymentProvider(request)):
            response = self.client.post(f"/admin/payments/{transaction_id}/refund")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(calls, ["/payments/pay_admin/refund"])
        with self.app.app_context():
            actions = {row.action for row in AuditLog.query.filter_by(object_id=transaction_id).all()}
            self.assertIn("payment_refund_initiated", actions)
            self.assertIn("payment_refund_submitted", actions)

    def test_refund_timeout_requires_reconciliation_and_cannot_repeat(self):
        def request(method, path, payload=None):
            raise PaymentError("network timeout")

        with self.app.app_context(), patch.dict(os.environ, {"PAYMENT_PROVIDER": "razorpay", "APP_ENV": "production",
            "RAZORPAY_KEY_ID": "key", "RAZORPAY_KEY_SECRET": "secret", "RAZORPAY_WEBHOOK_SECRET": "webhook"}), \
            patch("app.services.payment.RazorpayPaymentProvider", return_value=RazorpayPaymentProvider(request)):
            transaction = PaymentTransaction(booking_id=self.booking_id, booking_reference=self.get_booking().booking_reference,
                amount=1250.50, currency="INR", idempotency_key="booking:9", status="paid", gateway_reference="pay_timeout")
            db.session.add(transaction)
            db.session.commit()
            with self.assertRaises(PaymentError):
                refund_payment(transaction, "ops@example.test")
            self.assertEqual(transaction.refund_status, "reconciliation_required")
            self.assertEqual(transaction.status, "refund_pending")
            self.assertIs(refund_payment(transaction, "ops@example.test"), transaction)

    def test_unauthorized_refund_route_requires_admin(self):
        with self.app.app_context():
            transaction = PaymentTransaction(booking_id=self.booking_id, booking_reference=self.get_booking().booking_reference,
                amount=1250.50, currency="INR", idempotency_key="booking:6", status="paid", gateway_reference="pay_test")
            db.session.add(transaction)
            db.session.commit()
            transaction_id = transaction.id
        response = self.client.post(f"/admin/payments/{transaction_id}/refund")
        self.assertEqual(response.status_code, 302)

    def test_verification_route_enforces_booking_owner_and_transaction_state(self):
        with self.app.app_context():
            transaction = PaymentTransaction(booking_id=self.booking_id, booking_reference=self.get_booking().booking_reference,
                amount=1250.50, currency="INR", idempotency_key="booking:10", status="refund_pending")
            db.session.add(transaction)
            db.session.commit()
        with self.client.session_transaction() as session:
            session.update(authenticated=True, account_type="traveler", phone_number="+919800000097")
        self.assertEqual(self.client.post("/payments/AAR-PAYMENT-TEST/verify").status_code, 404)
        with self.client.session_transaction() as session:
            session["phone_number"] = "+919800000099"
        self.assertEqual(self.client.post("/payments/AAR-PAYMENT-TEST/verify").status_code, 409)

    def test_webhook_requires_signature_and_duplicate_event_is_idempotent(self):
        raw = json.dumps({"event": "refund.processed", "payload": {"refund": {"entity": {
            "id": "rfnd_hook", "payment_id": "pay_hook", "amount": 125050, "currency": "INR"}}}}).encode()
        with patch.dict(os.environ, {"PAYMENT_PROVIDER": "razorpay", "RAZORPAY_KEY_ID": "key",
                                     "RAZORPAY_KEY_SECRET": "secret", "RAZORPAY_WEBHOOK_SECRET": "webhook"}):
            bad = self.client.post("/payments/razorpay/webhook", data=raw,
                                   headers={"x-razorpay-event-id": "event-1", "x-razorpay-signature": "invalid"})
            self.assertEqual(bad.status_code, 401)
            with self.app.app_context():
                transaction = PaymentTransaction(booking_id=self.booking_id, booking_reference=self.get_booking().booking_reference,
                    amount=1250.50, currency="INR", idempotency_key="booking:7", status="refund_pending",
                    gateway_reference="pay_hook", refund_status="pending")
                db.session.add(transaction)
                db.session.commit()
            signature = hmac.new(b"webhook", raw, hashlib.sha256).hexdigest()
            headers = {"x-razorpay-event-id": "event-1", "x-razorpay-signature": signature}
            first = self.client.post("/payments/razorpay/webhook", data=raw, headers=headers)
            second = self.client.post("/payments/razorpay/webhook", data=raw, headers=headers)
            self.assertEqual(first.status_code, 200)
            self.assertEqual(second.get_json()["status"], "duplicate")
            with self.app.app_context():
                transaction = PaymentTransaction.query.filter_by(gateway_reference="pay_hook").one()
                self.assertEqual(transaction.status, "refunded")
                self.assertEqual(self.get_booking().payment_status, "refunded")
                self.assertEqual(PaymentWebhookEvent.query.filter_by(event_id="event-1").count(), 1)

    def test_captured_webhook_after_failure_event_order_uses_provider_status(self):
        from app.services.payment import process_webhook
        with self.app.app_context():
            transaction = PaymentTransaction(booking_id=self.booking_id, booking_reference=self.get_booking().booking_reference,
                amount=1250.50, currency="INR", idempotency_key="booking:11", status="failed", provider_order_id="order_late")
            db.session.add(transaction)
            db.session.commit()
            payment_response = {"id": "pay_late", "order_id": "order_late", "amount": 125050,
                                "currency": "INR", "status": "captured", "captured": True}

            def request(method, path, payload=None):
                return payment_response

            with patch.dict(os.environ, {"PAYMENT_PROVIDER": "razorpay", "APP_ENV": "production",
                "RAZORPAY_KEY_ID": "key", "RAZORPAY_KEY_SECRET": "secret", "RAZORPAY_WEBHOOK_SECRET": "webhook"}), \
                patch("app.services.payment.RazorpayPaymentProvider", return_value=RazorpayPaymentProvider(request)):
                body=json.dumps({"event":"payment.captured","payload":{"payment":{"entity":{"id":"pay_late","order_id":"order_late"}}}}).encode()
                self.assertEqual(process_webhook(body, "event-late"), "processed")
            self.assertEqual(transaction.status, "paid")
            self.assertEqual(self.get_booking().payment_status, "paid")


if __name__ == "__main__":
    unittest.main()
