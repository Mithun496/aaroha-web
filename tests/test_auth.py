import unittest
import os
import subprocess
import sys
import tempfile
from io import BytesIO
from pathlib import Path
from datetime import date, timedelta
from unittest.mock import patch
from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models.guide import GuideApplication
from app.models.otp import OTPChallenge
from app.models.platform import AutoCaptain, BikeVehicle, Booking, CoracleOperator, EmergencyContact, Notification, PartnerApplication, PaymentTransaction, RentalPartner, Review, SOSIncident, TravelerProfile
from app.models.user import User
from app.services.storage import get_private_file, get_public_media_bytes, save_image, save_private_file
from config import Config


class AuthFlowTests(unittest.TestCase):
    class TestConfig(Config):
        TESTING = True
        WTF_CSRF_ENABLED = False
        ENVIRONMENT = "testing"
        SQLALCHEMY_DATABASE_URI = "sqlite://"
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        AUTO_CREATE_TABLES = False

    def setUp(self):
        self.app = create_app(self.TestConfig)
        self.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.client = self.app.test_client()
        with self.app.app_context():
            db.drop_all()
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_health_endpoint(self):
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['status'], 'ok')

    def test_end_to_end_route_smoke_pages(self):
        public_paths = (
            '/', '/health', '/explore', '/guides', '/bikes', '/auto', '/coracles',
            '/services', '/stays', '/culture-guide', '/offline', '/offline/hampi.json',
            '/trip-planner', '/support', '/admin/login', '/auth/account-type',
        )
        for path in public_paths:
            with self.subTest(path=path):
                self.assertLess(self.client.get(path).status_code, 500)

        with self.client.session_transaction() as session:
            session.update(authenticated=True, account_type='traveler', phone_number='+919800000081')
        for path in ('/bookings', '/profile', '/notifications', '/emergency-contacts', '/sos'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

        with self.client.session_transaction() as session:
            session.update(account_type='partner', partner_category='bike_rental')
        self.assertEqual(self.client.get('/auth/partner/bike_rental').status_code, 200)
        self.assertLess(self.client.get('/partner/dashboard').status_code, 500)

        with self.client.session_transaction() as session:
            session.clear()
            session.update(admin_authenticated=True, admin_email='admin@example.com')
        for path in ('/admin/dashboard', '/admin/operations', '/admin/audit-logs', '/admin/partners'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_csrf_rejects_state_change_without_token(self):
        csrf_app = create_app(self.TestConfig)
        csrf_app.config.update(TESTING=True, WTF_CSRF_ENABLED=True)
        client = csrf_app.test_client()
        response = client.post('/auth/account-type', data={'account_type': 'traveler'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(client.post('/auth/account-type', data={'account_type': 'traveler', 'csrf_token': 'invalid'}).status_code, 400)
        self.assertEqual(client.post('/payments/AAR-CSRF/verify').status_code, 400)
        self.assertEqual(client.post('/admin/payments/1/refund').status_code, 400)
        with client.session_transaction() as session:
            session.update(authenticated=True, account_type='partner', partner_category='bike_rental', phone_number='+919700000001')
        self.assertEqual(client.post('/partner/bike/vehicles', data={'name': 'Bike'}).status_code, 400)
        self.assertEqual(client.post('/admin/logout').status_code, 400)

    def test_production_configuration_fails_closed_for_mock_and_memory_limits(self):
        environment = os.environ.copy()
        environment.update({
            'APP_ENV': 'production',
            'SECRET_KEY': 's' * 48,
            'TRUSTED_HOSTS': 'aaroha.example',
            'ADMIN_EMAIL': 'admin@example.com',
            'ADMIN_PASSWORD_HASH': generate_password_hash('test-only-password'),
            'DATABASE_URL': 'postgresql+psycopg://user:placeholder@db.example/aaroha',
            'OTP_PROVIDER': 'twilio',
            'TWILIO_ACCOUNT_SID': 'AC' + '0' * 32,
            'TWILIO_AUTH_TOKEN': 'test-only-token',
            'TWILIO_VERIFY_SERVICE_SID': 'VA' + '0' * 32,
            'RATELIMIT_STORAGE_URI': 'redis://localhost:6379/0',
            'STORAGE_PROVIDER': 's3',
            'STORAGE_BUCKET': 'test-bucket',
            'PAYMENT_PROVIDER': 'disabled',
        })
        command = [sys.executable, '-c', 'import config']
        valid = subprocess.run(command, env=environment, capture_output=True, text=True)
        self.assertEqual(valid.returncode, 0, valid.stderr)

        environment['PAYMENT_PROVIDER'] = 'mock'
        mock = subprocess.run(command, env=environment, capture_output=True, text=True)
        self.assertNotEqual(mock.returncode, 0)
        self.assertIn('not allowed in production', mock.stderr)

        environment['PAYMENT_PROVIDER'] = 'razorpay'
        incomplete_razorpay = subprocess.run(command, env=environment, capture_output=True, text=True)
        self.assertNotEqual(incomplete_razorpay.returncode, 0)
        self.assertIn('Razorpay key and webhook credentials are required', incomplete_razorpay.stderr)
        environment.update({
            'RAZORPAY_KEY_ID': 'rzp_test_configuration_key',
            'RAZORPAY_KEY_SECRET': 'test-only-secret',
            'RAZORPAY_WEBHOOK_SECRET': 'test-only-webhook-secret',
        })
        valid_razorpay = subprocess.run(command, env=environment, capture_output=True, text=True)
        self.assertEqual(valid_razorpay.returncode, 0, valid_razorpay.stderr)

        environment['PAYMENT_PROVIDER'] = 'disabled'
        environment['RATELIMIT_STORAGE_URI'] = 'memory://'
        memory_limiter = subprocess.run(command, env=environment, capture_output=True, text=True)
        self.assertNotEqual(memory_limiter.returncode, 0)
        self.assertIn('shared RATELIMIT_STORAGE_URI', memory_limiter.stderr)

    def test_traveler_booking_ownership_is_enforced(self):
        with self.app.app_context():
            db.session.add_all([
                Booking(traveler_phone='+919800000001', booking_type='guide', provider_id=1, provider_name='Visible', status='pending'),
                Booking(traveler_phone='+919800000002', booking_type='guide', provider_id=2, provider_name='Private', status='pending'),
            ])
            db.session.commit()
        with self.client.session_transaction() as session:
            session.update(authenticated=True, account_type='traveler', phone_number='+919800000001')
        response = self.client.get('/bookings')
        self.assertIn('Visible', response.get_data(as_text=True))
        self.assertNotIn('Private', response.get_data(as_text=True))

    def test_traveler_a_cannot_access_traveler_b_records(self):
        with self.app.app_context():
            profile_a = TravelerProfile(phone_number='+919800000041', first_name='Traveler A', last_name='A')
            profile_b = TravelerProfile(phone_number='+919800000042', first_name='PRIVATE-B-PROFILE', last_name='B')
            booking_a = Booking(traveler_phone=profile_a.phone_number, booking_type='guide', provider_id=41, provider_name='Guide A', status='completed')
            booking_b = Booking(traveler_phone=profile_b.phone_number, booking_type='guide', provider_id=42, provider_name='Guide B', status='completed')
            db.session.add_all([profile_a, profile_b, booking_a, booking_b])
            db.session.flush()
            review_b = Review(booking_id=booking_b.id, traveler_phone=profile_b.phone_number, provider_id=42, rating=5, text='Private traveler review text.')
            notification_b = Notification(recipient_phone=profile_b.phone_number, notification_type='private', title='PRIVATE-B-NOTIFICATION', message='Private notification body.')
            contact_b = EmergencyContact(user_phone=profile_b.phone_number, name='Private contact', phone='+919900000042')
            incident_b = SOSIncident(traveler_phone=profile_b.phone_number, location_text='PRIVATE-B-LOCATION', status='initiated')
            db.session.add_all([review_b, notification_b, contact_b, incident_b])
            db.session.commit()
            booking_b_id = booking_b.id
            booking_b_reference = booking_b.booking_reference
            notification_b_id = notification_b.id
            contact_b_id = contact_b.id

        with self.client.session_transaction() as session:
            session.update(authenticated=True, account_type='traveler', phone_number='+919800000041')

        response = self.client.get('/profile')
        self.assertNotIn('PRIVATE-B-PROFILE', response.get_data(as_text=True))
        response = self.client.get('/bookings')
        self.assertNotIn('Guide B', response.get_data(as_text=True))
        self.assertEqual(self.client.post(f'/reviews/{booking_b_id}', data={'rating': '5', 'text': 'This should not be accepted.'}).status_code, 404)
        response = self.client.get('/notifications')
        self.assertNotIn('PRIVATE-B-NOTIFICATION', response.get_data(as_text=True))
        self.assertEqual(self.client.post(f'/notifications/{notification_b_id}/read').status_code, 404)
        self.assertEqual(self.client.post(f'/emergency-contacts/{contact_b_id}/delete').status_code, 404)
        response = self.client.get('/sos')
        self.assertNotIn('PRIVATE-B-LOCATION', response.get_data(as_text=True))
        self.assertEqual(self.client.post(f'/payments/{booking_b_reference}').status_code, 404)

        with self.app.app_context():
            self.assertFalse(db.session.get(Notification, notification_b_id).is_read)
            self.assertIsNotNone(db.session.get(EmergencyContact, contact_b_id))
            self.assertIsNone(PaymentTransaction.query.filter_by(booking_reference=booking_b_reference).first())

    def test_private_file_route_requires_admin(self):
        response = self.client.get('/admin/private-file/private/identity/missing.pdf')
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as session:
            session.update(authenticated=True, account_type='traveler', phone_number='+919800000001')
        self.assertEqual(self.client.get('/admin/private-file/private/identity/missing.pdf').status_code, 302)
        with self.client.session_transaction() as session:
            session.update(account_type='partner', phone_number='+919900000001')
        self.assertEqual(self.client.get('/admin/private-file/private/identity/missing.pdf').status_code, 302)

    def test_admin_operations_are_protected_and_render_datasets(self):
        self.assertEqual(self.client.get('/admin/operations').status_code, 302)
        with self.client.session_transaction() as session:
            session.update(authenticated=True, account_type='traveler', phone_number='+919800000001')
        self.assertEqual(self.client.get('/admin/operations').status_code, 302)
        with self.client.session_transaction() as session:
            session.clear()
            session.update(admin_authenticated=True, admin_email='admin@example.com')
        response = self.client.get('/admin/operations')
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        for title in ('Users', 'Traveler profiles', 'Destinations', 'Bookings', 'SOS incidents', 'Payment transactions', 'Audit logs'):
            self.assertIn(title, body)

    def test_private_file_download_is_admin_only_and_missing_files_are_404(self):
        with tempfile.TemporaryDirectory() as temporary_directory, patch.dict(os.environ, {'STORAGE_PROVIDER': 'local'}):
            root = Path(temporary_directory)
            self.app.config['UPLOAD_DIR'] = root
            uploaded = FileStorage(stream=BytesIO(b'%PDF-1.4\nprivate document'), filename='identity.pdf')
            relative_path = save_private_file(uploaded, root, 'private/identity')
            with self.client.session_transaction() as session:
                session.update(admin_authenticated=True, admin_email='admin@example.com')

            response = self.client.get(f'/admin/private-file/{relative_path}')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'%PDF-1.4', response.data)
            self.assertIn('attachment', response.headers['Content-Disposition'].lower())
            self.assertEqual(response.headers['Cache-Control'], 'private, no-store')
            response.close()

            response = self.client.get('/admin/private-file/private/identity/missing.pdf')
            self.assertEqual(response.status_code, 404)

    def test_private_storage_rejects_traversal_and_public_paths(self):
        with tempfile.TemporaryDirectory() as temporary_directory, patch.dict(os.environ, {'STORAGE_PROVIDER': 'local'}):
            root = Path(temporary_directory)
            hostile_paths = [
                '../private/secret.pdf',
                'private/../../secret.pdf',
                r'private\..\public\secret.pdf',
                str((root / 'private' / 'secret.pdf').resolve()),
                'public/secret.pdf',
            ]
            for hostile_path in hostile_paths:
                with self.subTest(path=hostile_path), self.assertRaises(FileNotFoundError):
                    get_private_file(hostile_path, root)

    def test_public_media_is_separate_from_private_files(self):
        with tempfile.TemporaryDirectory() as temporary_directory, patch.dict(os.environ, {'STORAGE_PROVIDER': 'local'}):
            root = Path(temporary_directory)
            image_bytes = b'\x89PNG\r\n\x1a\npublic image data'
            image_path = save_image(FileStorage(stream=BytesIO(image_bytes), filename='cover.png'), root, 'public/guide')
            self.assertEqual(get_public_media_bytes(image_path, root), image_bytes)

            private_path = save_private_file(FileStorage(stream=BytesIO(b'%PDF-1.4 private'), filename='identity.pdf'), root, 'private/identity')
            with self.assertRaises(FileNotFoundError):
                get_public_media_bytes(private_path, root)
            with self.assertRaises(FileNotFoundError):
                get_public_media_bytes('../private/identity.pdf', root)

    def test_upload_validation_checks_extension_signature_and_size(self):
        with tempfile.TemporaryDirectory() as temporary_directory, patch.dict(os.environ, {'STORAGE_PROVIDER': 'local', 'MAX_UPLOAD_BYTES': '16'}):
            root = Path(temporary_directory)
            invalid_type = FileStorage(stream=BytesIO(b'%PDF-1.4'), filename='identity.exe')
            with self.assertRaisesRegex(ValueError, 'Unsupported file type'):
                save_private_file(invalid_type, root)

            invalid_signature = FileStorage(stream=BytesIO(b'not a pdf'), filename='identity.pdf')
            with self.assertRaisesRegex(ValueError, 'does not match'):
                save_private_file(invalid_signature, root)

            oversized = FileStorage(stream=BytesIO(b'%PDF-1.4' + b'x' * 20), filename='identity.pdf')
            with self.assertRaisesRegex(ValueError, 'too large'):
                save_private_file(oversized, root)

    def test_traveler_auth_and_profile_flow(self):
        with patch('app.routes.auth.generate_code', return_value='123456'), patch('app.routes.auth.send_code', return_value=True):
            resp = self.client.post('/auth/account-type', data={'account_type': 'traveler'}, follow_redirects=False)
            self.assertEqual(resp.status_code, 302)
            self.assertEqual(resp.headers['Location'], '/auth/phone')

            resp = self.client.post('/auth/phone', data={'phone_number': '9999999999'}, follow_redirects=False)
            self.assertEqual(resp.status_code, 302)
            self.assertEqual(resp.headers['Location'], '/auth/otp')

            with self.client.session_transaction() as session:
                self.assertNotIn('dev_otp', session)
                self.assertIn('otp_phone', session)

            with self.app.app_context():
                challenge = OTPChallenge.query.filter_by(phone_number='+919999999999', purpose='login').order_by(OTPChallenge.created_at.desc()).first()
                self.assertIsNotNone(challenge)
                self.assertNotEqual(challenge.code_hash, '123456')

            resp = self.client.post('/auth/otp', data={'otp': '123456'}, follow_redirects=False)
            self.assertEqual(resp.status_code, 302)
            self.assertEqual(resp.headers['Location'], '/auth/profile')

            with self.client.session_transaction() as session:
                self.assertTrue(session.get('authenticated'))
                self.assertEqual(session.get('account_type'), 'traveler')

            resp = self.client.post(
                '/auth/profile',
                data={
                    'first_name': 'Asha',
                    'last_name': 'Rao',
                    'country': 'India',
                    'travel_style': 'Solo',
                    'trip_duration': '3 days',
                    'interests': ['History', 'Solo'],
                },
                follow_redirects=False,
            )
            self.assertEqual(resp.status_code, 302)
            self.assertEqual(resp.headers['Location'], '/')

            with self.app.app_context():
                user = User.query.filter_by(phone_number='+919999999999').first()
                self.assertIsNotNone(user)
                profile = TravelerProfile.query.filter_by(phone_number='+919999999999').first()
                self.assertIsNotNone(profile)
                self.assertEqual(profile.first_name, 'Asha')

    def test_traveler_cannot_enter_partner_verification_flow(self):
        with self.client.session_transaction() as session:
            session.update(authenticated=True, account_type='traveler', phone_number='+919800000070')

        for path in ('/auth/partner/verification', '/auth/partner/submitted'):
            response = self.client.get(path, follow_redirects=False)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.headers['Location'], '/')
        response = self.client.post('/auth/partner/verification', follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as session:
            self.assertNotIn('verification_status', session)

    def test_otp_resend_has_per_phone_cooldown(self):
        with patch('app.routes.auth.generate_code', return_value='123456'), patch('app.routes.auth.send_code', return_value=True) as send_code:
            first = self.client.post('/auth/phone', data={'phone_number': '9999999998'})
            self.assertEqual(first.status_code, 302)
            second = self.client.post('/auth/phone', data={'phone_number': '9999999998'})
            self.assertEqual(second.status_code, 200)
            self.assertIn('wait before requesting another code', second.get_data(as_text=True))
            self.assertEqual(send_code.call_count, 1)

    def test_otp_displays_normalized_phone_number_once(self):
        phone = "+919800000081"
        with self.client.session_transaction() as session:
            session["phone_number"] = phone
        response = self.client.get("/auth/otp")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(phone, body)
        self.assertNotIn("+91 " + phone, body)

    def test_invalid_otp_is_rejected(self):
        with patch('app.routes.auth.generate_code', return_value='123456'), patch('app.routes.auth.send_code', return_value=True):
            self.client.post('/auth/account-type', data={'account_type': 'traveler'}, follow_redirects=False)
            self.client.post('/auth/phone', data={'phone_number': '9999999999'}, follow_redirects=False)
            response = self.client.post('/auth/otp', data={'otp': '999999'}, follow_redirects=False)
            self.assertEqual(response.status_code, 200)
            self.assertIn('Invalid OTP', response.get_data(as_text=True))

    def test_disabled_account_cannot_be_reactivated_by_otp_completion(self):
        with patch.dict(os.environ, {'OTP_PROVIDER': 'console'}), patch('app.routes.auth.generate_code', return_value='123456'), patch('app.routes.auth.send_code', return_value=True):
            self.client.post('/auth/account-type', data={'account_type': 'traveler'})
            self.client.post('/auth/phone', data={'phone_number': '9999999999'})
            with self.app.app_context():
                user = User(phone_number='+919999999999', country_code='+91', role='traveler', is_active=False)
                db.session.add(user)
                db.session.commit()

            response = self.client.post('/auth/otp', data={'otp': '123456'})
            self.assertEqual(response.status_code, 200)
            self.assertIn('disabled', response.get_data(as_text=True).lower())
            with self.client.session_transaction() as session:
                self.assertFalse(session.get('authenticated', False))
            with self.app.app_context():
                self.assertFalse(User.query.filter_by(phone_number='+919999999999').one().is_active)

    def test_verified_otp_cannot_be_replayed(self):
        with patch.dict(os.environ, {'OTP_PROVIDER': 'console'}), patch('app.routes.auth.generate_code', return_value='123456'), patch('app.routes.auth.send_code', return_value=True):
            self.client.post('/auth/account-type', data={'account_type': 'traveler'})
            self.client.post('/auth/phone', data={'phone_number': '9999999999'})
            response = self.client.post('/auth/otp', data={'otp': '123456'})
            self.assertEqual(response.status_code, 302)

            with self.client.session_transaction() as session:
                session.update(phone_number='+919999999999', account_type='traveler')

            response = self.client.post('/auth/otp', data={'otp': '123456'})
            self.assertEqual(response.status_code, 200)
            self.assertIn('already been used', response.get_data(as_text=True))

    def test_logout_routes_do_not_mutate_on_get_and_require_csrf(self):
        csrf_app = create_app(self.TestConfig)
        csrf_app.config.update(TESTING=True, WTF_CSRF_ENABLED=True)
        client = csrf_app.test_client()
        with client.session_transaction() as session:
            session.update(admin_authenticated=True)

        self.assertEqual(client.get('/auth/logout').status_code, 405)
        self.assertEqual(client.post('/auth/logout').status_code, 400)
        self.assertEqual(client.get('/admin/logout').status_code, 200)
        with client.session_transaction() as session:
            self.assertTrue(session.get('admin_authenticated'))
        self.assertEqual(client.post('/admin/logout').status_code, 400)

    def test_payout_credentials_are_not_retained_in_session(self):
        with self.client.session_transaction() as session:
            session.update(
                authenticated=True,
                account_type='partner',
                partner_category='guide',
                guide_profile={'first_name': 'Guide'},
                guide_services={'services': ['walk']},
                guide_pricing={'hourly_rate': 100},
                guide_availability={'available_days': ['monday']},
                guide_verification={'id_type': 'passport'},
                guide_photos={'cover_photo': 'cover.jpg'},
            )

        response = self.client.post('/auth/partner/guide/payout', data={
            'payout_method': 'bank',
            'account_holder': 'Guide Name',
            'account_number': '123456789012',
            'ifsc': 'ABCD0123456',
            'upi_id': 'guide@example',
        })
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as session:
            self.assertEqual(session['guide_payout'], {'payout_method': 'bank'})
            self.assertNotIn('account_number', str(dict(session)))

    def test_verification_numbers_are_not_retained_in_session(self):
        with self.client.session_transaction() as session:
            session.update(
                authenticated=True,
                account_type='partner',
                partner_category='guide',
                guide_profile={'first_name': 'Guide'},
                guide_services={'services': ['walk']},
                guide_pricing={'hourly_rate': 100},
                guide_availability={'available_days': ['monday']},
            )

        with patch('app.routes.auth.save_private_file', return_value='private/identity/random.pdf'):
            response = self.client.post('/auth/partner/guide/verification', data={
                'id_type': 'passport',
                'id_number': 'P1234567',
                'credential_type': 'license',
                'credential_number': 'CREDENTIAL-SECRET',
                'information_confirmed': 'yes',
                'verification_consent': 'yes',
                'identity_document': (BytesIO(b'%PDF-1.4'), 'identity.pdf'),
            }, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as session:
            verification = session['guide_verification']
            self.assertNotIn('id_number', verification)
            self.assertNotIn('credential_number', verification)

    def test_twilio_otp_uses_verify_check(self):
        class VerificationChecks:
            def create(self, **kwargs):
                self.kwargs = kwargs
                return type('Result', (), {'status': 'approved'})()

        class Services:
            def __init__(self):
                self.verification_checks = VerificationChecks()

        class Verify:
            def __init__(self):
                self.v2 = type('V2', (), {'services': lambda _self, _sid: type('Service', (), {'verification_checks': services.verification_checks})()})()

        services = Services()
        fake_client = type('Client', (), {'verify': Verify()})()

        with patch.dict(os.environ, {
            'OTP_PROVIDER': 'twilio',
            'TWILIO_ACCOUNT_SID': 'AC-test',
            'TWILIO_AUTH_TOKEN': 'test-token',
            'TWILIO_VERIFY_SERVICE_SID': 'VA-test',
        }), patch('app.services.otp._twilio_client', return_value=fake_client):
            from app.services.otp import verify_code

            self.assertTrue(verify_code('+919999999999', '123456', 'unrelated-local-hash'))
            self.assertEqual(services.verification_checks.kwargs, {'to': '+919999999999', 'code': '123456'})

    def test_partner_dashboard_lists_bookings_and_accepts_requests(self):
        guide_id = None
        booking_id = None

        with self.app.app_context():
            guide = GuideApplication(
                phone_number='+919900000001',
                email='guide@example.com',
                first_name='Ravi',
                last_name='Kumar',
                location='Hampi',
                experience_years='3',
                bio='Experienced heritage guide.',
                languages=['English', 'Kannada'],
                services=['heritage_walk'],
                areas=['hampi', 'sanapur'],
                available_days=['monday', 'tuesday'],
                time_slots=['morning'],
                status='approved',
                hourly_rate=1200,
                max_group_size='6',
            )
            db.session.add(guide)
            db.session.commit()
            guide_id = guide.id

            booking = Booking(
                traveler_phone='+919800000001',
                booking_type='guide',
                provider_id=guide.id,
                provider_name='Ravi Kumar',
                destination='Hampi',
                booking_date=date(2026, 9, 25),
                booking_time='09:00',
                guests=2,
                message='Need a heritage walk for two.',
                amount=1200,
                status='pending',
            )
            db.session.add(booking)
            db.session.commit()
            booking_id = booking.id

        with self.client.session_transaction() as session:
            session['authenticated'] = True
            session['account_type'] = 'partner'
            session['partner_category'] = 'guide'
            session['phone_number'] = '+919900000001'
            session['guide_application_id'] = guide_id

        response = self.client.get('/partner/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Need a heritage walk for two.', response.get_data(as_text=True))

        response = self.client.post(f'/partner/bookings/{booking_id}/decision', data={'action': 'complete'}, follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            self.assertEqual(db.session.get(Booking, booking_id).status, 'pending')

        response = self.client.post(f'/partner/bookings/{booking_id}/decision', data={'action': 'accept'}, follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers['Location'], '/partner/dashboard')

        with self.app.app_context():
            updated_booking = db.session.get(Booking, booking_id)
            self.assertEqual(updated_booking.status, 'confirmed')

    def test_provider_cannot_use_another_guides_application_id(self):
        with self.app.app_context():
            guide_b = GuideApplication(
                phone_number='+919900000042', email='private-guide@example.com', first_name='PRIVATE-GUIDE', last_name='B',
                location='Hampi', experience_years='3', bio='Private profile.', languages=['English'], services=['walk'],
                areas=['hampi'], available_days=['monday'], time_slots=['morning'], status='approved',
            )
            db.session.add(guide_b)
            db.session.commit()
            guide_b_id = guide_b.id

        with self.client.session_transaction() as session:
            session.update(authenticated=True, account_type='partner', partner_category='guide', phone_number='+919900000041', guide_application_id=guide_b_id)

        response = self.client.get('/partner/guide/profile/edit', follow_redirects=True)
        self.assertNotIn('PRIVATE-GUIDE', response.get_data(as_text=True))
        response = self.client.get('/auth/partner/guide/submitted', follow_redirects=True)
        self.assertNotIn('PRIVATE-GUIDE', response.get_data(as_text=True))

    def test_bike_provider_cannot_read_or_change_another_provider_booking(self):
        with self.app.app_context():
            partners = [
                RentalPartner(phone_number='+919700000051', owner_name='Partner A', business_name='Partner A Rentals', location='Hampi', status='approved'),
                RentalPartner(phone_number='+919700000052', owner_name='Partner B', business_name='Partner B Rentals', location='Hampi', status='approved'),
            ]
            db.session.add_all(partners)
            db.session.flush()
            vehicle = BikeVehicle(provider_id=partners[1].id, name='Private vehicle', vehicle_type='Scooter', location='Hampi', price=700, pricing_unit='day', is_active=True)
            db.session.add(vehicle)
            db.session.flush()
            booking = Booking(
                traveler_phone='+919800000052', booking_type='bike', provider_id=partners[1].id,
                service_id=vehicle.id, provider_name='Partner B Rentals', status='pending',
            )
            db.session.add(booking)
            db.session.commit()
            booking_id = booking.id

        with self.client.session_transaction() as session:
            session.update(authenticated=True, account_type='partner', partner_category='bike_rental', phone_number='+919700000051')

        response = self.client.get('/partner/dashboard')
        self.assertNotIn('+919800000052', response.get_data(as_text=True))
        self.assertEqual(self.client.post(f'/partner/bike/bookings/{booking_id}/decision', data={'action': 'accept'}).status_code, 404)
        with self.app.app_context():
            self.assertEqual(db.session.get(Booking, booking_id).status, 'pending')

    def test_bike_forms_include_csrf_tokens(self):
        with self.app.app_context():
            partner = RentalPartner(
                phone_number='+919700000020',
                owner_name='Leela',
                business_name='Hampi Rides',
                location='Hampi Bazaar',
                status='approved',
            )
            db.session.add(partner)
            db.session.flush()
            vehicle = BikeVehicle(
                provider_id=partner.id,
                name='City scooter',
                vehicle_type='Scooter',
                location='Hampi Bazaar',
                price=800,
                pricing_unit='day',
                is_active=True,
            )
            db.session.add(vehicle)
            db.session.commit()
            vehicle_id = vehicle.id

        with self.client.session_transaction() as session:
            session['authenticated'] = True
            session['account_type'] = 'partner'
            session['phone_number'] = '+919700000020'
            session['partner_category'] = 'bike_rental'

        response = self.client.get('/partner/bike/vehicles')
        self.assertEqual(response.status_code, 200)
        self.assertIn('name="csrf_token"', response.get_data(as_text=True))

        with self.client.session_transaction() as session:
            session.update(authenticated=True, account_type='traveler', phone_number='+919800000006')

        response = self.client.get(f'/bikes/{vehicle_id}')
        self.assertEqual(response.status_code, 200)
        self.assertIn('name="csrf_token"', response.get_data(as_text=True))

    def test_bike_partner_and_booking_flow(self):
        with self.app.app_context():
            application = PartnerApplication(
                phone_number='+919700000002',
                category='bike_rental',
                owner_name='Kiran',
                business_name='Hampi Wheels',
                location='Hampi Bazaar',
                whatsapp='+919700000002',
                description='Local bike rentals',
                details={'fleet_size': '12', 'vehicle_types': 'Scooter', 'pickup_point': 'Hampi Bazaar'},
                status='approved',
            )
            db.session.add(application)
            db.session.commit()

            vehicle = Booking(
                traveler_phone='+919800000001',
                booking_type='bike',
                provider_id=application.id,
                provider_name='Hampi Wheels',
                destination='Hampi Bazaar',
                booking_date=date(2026, 10, 2),
                booking_time='09:00',
                guests=1,
                message='Need a scooter for a day.',
                amount=900,
                status='pending',
            )
            db.session.add(vehicle)
            db.session.commit()

        response = self.client.get('/bikes')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Hampi Wheels', response.get_data(as_text=True))

        with self.app.app_context():
            booking = Booking.query.filter_by(booking_type='bike').order_by(Booking.id.desc()).first()
            self.assertIsNotNone(booking)
            self.assertEqual(booking.amount, 900)

    def test_bike_booking_uses_server_price_and_rejects_overlap(self):
        booking_date = date.today() + timedelta(days=2)
        with self.app.app_context():
            partner = RentalPartner(
                phone_number="+919700000003",
                owner_name="Maya",
                business_name="Hampi Ride Co",
                location="Kamalapura",
                status="approved",
            )
            db.session.add(partner)
            db.session.flush()
            partner_id = partner.id
            vehicle = BikeVehicle(
                provider_id=partner.id,
                name="Classic scooter",
                vehicle_type="Scooter",
                location="Kamalapura",
                price=750,
                pricing_unit="day",
                is_active=True,
            )
            db.session.add(vehicle)
            db.session.commit()
            vehicle_id = vehicle.id

        with self.client.session_transaction() as session:
            session["authenticated"] = True
            session["account_type"] = "traveler"
            session["phone_number"] = "+919800000001"

        form = {
            "booking_date": booking_date.isoformat(),
            "duration_days": "2",
            "booking_time": "09:00",
            "guests": "1",
            "amount": "1",
        }
        response = self.client.post(f"/bikes/{vehicle_id}", data=dict(form, duration_days="1000000000"), follow_redirects=False)
        self.assertEqual(response.status_code, 200)
        self.assertIn("between 1 and 30 days", response.get_data(as_text=True))
        response = self.client.post(f"/bikes/{vehicle_id}", data=form, follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            booking = Booking.query.filter_by(service_id=vehicle_id).one()
            self.assertEqual(booking.amount, 1500)
            self.assertEqual(booking.provider_id, partner_id)
            self.assertTrue(booking.booking_reference.startswith("AAR-"))

        response = self.client.post(f"/bikes/{vehicle_id}", data=form, follow_redirects=False)
        self.assertEqual(response.status_code, 200)
        self.assertIn("already requested", response.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(Booking.query.filter_by(service_id=vehicle_id).count(), 1)

    def test_auto_state_machine_and_coracle_validation(self):
        with self.app.app_context():
            captain = AutoCaptain(phone_number="+919700000010", owner_name="Captain", full_name="Auto Captain", location="Hampi", status="approved", is_online=True)
            operator = CoracleOperator(phone_number="+919700000011", business_name="River Rides", location="Tungabhadra", boat_capacity=4, price=250, status="approved")
            db.session.add_all([captain, operator])
            db.session.commit()
            captain_id = captain.id
            operator_id = operator.id

        with self.client.session_transaction() as session:
            session.update(authenticated=True, account_type="traveler", phone_number="+919800000001")
        response = self.client.post("/auto", data={"captain_id": captain_id, "pickup": "Hampi Bazaar", "destination": "Kamalapura"}, follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            auto_booking = Booking.query.filter_by(booking_type="auto").one()
            auto_booking_id = auto_booking.id
            self.assertEqual(auto_booking.status, "requested")
            self.assertEqual(Notification.query.filter_by(recipient_phone="+919700000010").count(), 1)

        with self.client.session_transaction() as session:
            session.update(account_type="partner", phone_number="+919700000010")
        response = self.client.post(f"/partner/service-bookings/{auto_booking_id}", data={"action": "accept"}, follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            self.assertEqual(db.session.get(Booking, auto_booking_id).status, "accepted")

        with self.client.session_transaction() as session:
            session.update(account_type="traveler", phone_number="+919800000001")
        future_date = (date.today() + timedelta(days=3)).isoformat()
        response = self.client.post("/coracles", data={"operator_id": operator_id, "booking_date": future_date, "booking_time": "10:00", "passengers": "5"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("capacity", response.get_data(as_text=True))
        response = self.client.post("/coracles", data={"operator_id": operator_id, "booking_date": future_date, "booking_time": "10:00", "passengers": "2"}, follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        response = self.client.post("/coracles", data={"operator_id": operator_id, "booking_date": future_date, "booking_time": "11:00", "passengers": "2"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("already requested", response.get_data(as_text=True))

    def test_provider_cannot_access_other_service_type_booking_with_colliding_id(self):
        with self.app.app_context():
            captain = AutoCaptain(phone_number='+919700000031', owner_name='Captain A', full_name='Captain A', location='Hampi', status='approved', is_online=True)
            operator = CoracleOperator(phone_number='+919700000032', business_name='Operator B', location='River', boat_capacity=4, price=250, status='approved')
            db.session.add_all([captain, operator])
            db.session.flush()
            self.assertEqual(captain.id, operator.id)
            booking = Booking(
                traveler_phone='+919800000031',
                booking_type='coracle',
                provider_id=operator.id,
                service_id=operator.id,
                provider_name=operator.business_name,
                status='pending',
            )
            db.session.add(booking)
            db.session.commit()
            booking_id = booking.id

        with self.client.session_transaction() as session:
            session.update(authenticated=True, account_type='partner', phone_number='+919700000031')

        response = self.client.get('/partner/service-bookings')
        self.assertNotIn('Operator B', response.get_data(as_text=True))
        response = self.client.post(f'/partner/service-bookings/{booking_id}', data={'action': 'accept'})
        self.assertEqual(response.status_code, 404)
        with self.app.app_context():
            self.assertEqual(db.session.get(Booking, booking_id).status, 'pending')

    def test_completed_booking_review_ui_and_validation(self):
        with self.app.app_context():
            booking = Booking(
                traveler_phone="+919800000001",
                booking_type="guide",
                provider_id=77,
                service_id=77,
                provider_name="Guide",
                booking_date=date.today(),
                amount=1200,
                status="completed",
            )
            db.session.add(booking)
            db.session.commit()
            booking_id = booking.id

        with self.client.session_transaction() as session:
            session.update(authenticated=True, account_type="traveler", phone_number="+919800000001")

        response = self.client.get('/bookings')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Write Review', response.get_data(as_text=True))
        self.assertIn(f'/reviews/{booking_id}', response.get_data(as_text=True))

        response = self.client.post(f'/reviews/{booking_id}', data={'rating': '6', 'text': 'Nice'}, follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            self.assertIsNone(Review.query.filter_by(booking_id=booking_id).first())

        response = self.client.post(f'/reviews/{booking_id}', data={'rating': '5', 'text': 'Excellent guide service throughout the trip.'}, follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            self.assertIsNotNone(Review.query.filter_by(booking_id=booking_id).first())

    def test_notifications_and_sos_contact_experience(self):
        with self.app.app_context():
            db.session.add(Notification(
                recipient_phone="+919800000001",
                notification_type="booking_status",
                title="Booking updated",
                message="Your guide booking is confirmed.",
                is_read=False,
            ))
            db.session.add(EmergencyContact(
                user_phone="+919800000001",
                name="Ananya",
                phone="+919900000999",
                relationship="Sibling",
                is_primary=True,
            ))
            db.session.commit()

        with self.client.session_transaction() as session:
            session.update(authenticated=True, account_type="traveler", phone_number="+919800000001")

        response = self.client.get('/notifications')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Unread', response.get_data(as_text=True))
        self.assertIn('Mark read', response.get_data(as_text=True))

        response = self.client.get('/sos')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Are you safe to speak?', response.get_data(as_text=True))
        self.assertIn('Ananya', response.get_data(as_text=True))
        self.assertIn('tel:', response.get_data(as_text=True))

        response = self.client.post('/sos', data={'safety_response': 'arbitrary', 'location_text': 'Hampi'})
        self.assertEqual(response.status_code, 400)
        with self.app.app_context():
            self.assertEqual(SOSIncident.query.filter_by(traveler_phone='+919800000001').count(), 0)

    def test_guide_rating_summary_excludes_other_service_type_id_collision(self):
        with self.app.app_context():
            guide = GuideApplication(
                phone_number='+919900000061', email='rating@example.com', first_name='Guide', last_name='One',
                location='Hampi', experience_years='3', bio='Guide profile.', languages=['English'], services=['walk'],
                areas=['hampi'], available_days=['monday'], time_slots=['morning'], status='approved',
            )
            db.session.add(guide)
            db.session.flush()
            bike_booking = Booking(traveler_phone='+919800000061', booking_type='bike', provider_id=guide.id, service_id=999, provider_name='Bike partner', status='completed')
            db.session.add(bike_booking)
            db.session.flush()
            db.session.add(Review(booking_id=bike_booking.id, traveler_phone=bike_booking.traveler_phone, provider_id=guide.id, rating=1, text='Bike review must not rate this guide.'))
            guide_id = guide.id
            db.session.commit()

        response = self.client.get(f'/guides/{guide_id}')
        body = response.get_data(as_text=True)
        self.assertNotIn('Bike review must not rate this guide.', body)
        self.assertNotIn('1 / 5', body)

    def test_mock_payment_and_completed_booking_review_are_server_owned(self):
        with self.app.app_context():
            booking = Booking(
                traveler_phone="+919800000001",
                booking_type="guide",
                provider_id=77,
                service_id=77,
                provider_name="Guide",
                booking_date=date.today(),
                amount=1200,
                status="completed",
            )
            paid_booking = Booking(
                traveler_phone="+919800000001",
                booking_type="guide",
                provider_id=78,
                service_id=78,
                provider_name="Guide Two",
                booking_date=date.today(),
                amount=900,
                status="confirmed",
            )
            db.session.add_all([booking, paid_booking])
            db.session.commit()
            booking_id, paid_booking_reference = booking.id, paid_booking.booking_reference

        with self.client.session_transaction() as session:
            session.update(authenticated=True, account_type="traveler", phone_number="+919800000001")
        response = self.client.post(f"/reviews/{booking_id}", data={"rating": "5", "text": "Excellent guide."}, follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            self.assertIsNotNone(Review.query.filter_by(booking_id=booking_id).first())

        with patch.dict(os.environ, {"PAYMENT_PROVIDER": "mock", "APP_ENV": "development"}):
            self.client.post(f"/payments/{paid_booking_reference}", data={}, follow_redirects=False)
            self.client.post(f"/payments/{paid_booking_reference}", data={}, follow_redirects=False)
            with self.app.app_context():
                self.assertEqual(PaymentTransaction.query.filter_by(booking_reference=paid_booking_reference).count(), 1)
            response = self.client.post(f"/payments/{paid_booking_reference}", data={"confirm_mock": "1", "gateway_reference": "attacker-controlled"}, follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            transaction = PaymentTransaction.query.filter_by(booking_reference=paid_booking_reference).one()
            self.assertEqual(transaction.status, "paid")


if __name__ == '__main__':
    unittest.main()
