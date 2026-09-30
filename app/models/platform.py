from datetime import datetime, timezone
from uuid import uuid4

from app.extensions import db


class TravelerProfile(db.Model):
    __tablename__ = "traveler_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    phone_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=True)
    country = db.Column(db.String(120), nullable=True)
    travel_style = db.Column(db.String(80), nullable=True)
    trip_duration = db.Column(db.String(80), nullable=True)
    interests = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", backref="traveler_profile", uselist=False)

    def __repr__(self):
        return f"<TravelerProfile {self.phone_number}>"


class PartnerApplication(db.Model):
    __tablename__ = "partner_applications"

    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(30), nullable=False, index=True)
    category = db.Column(db.String(50), nullable=False, index=True)
    owner_name = db.Column(db.String(160), nullable=False)
    business_name = db.Column(db.String(180), nullable=False)
    location = db.Column(db.String(255), nullable=False)
    whatsapp = db.Column(db.String(30), nullable=True)
    description = db.Column(db.Text, nullable=True)
    details = db.Column(db.JSON, nullable=False, default=dict)
    verification_document_path = db.Column(db.String(500), nullable=True)
    status = db.Column(db.String(50), nullable=False, default="pending")
    submitted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Booking(db.Model):
    __tablename__ = "bookings"

    id = db.Column(db.Integer, primary_key=True)
    booking_reference = db.Column(db.String(24), unique=True, nullable=False, default=lambda: f"AAR-{uuid4().hex[:12].upper()}")
    traveler_phone = db.Column(db.String(30), nullable=False, index=True)
    booking_type = db.Column(db.String(40), nullable=False)
    provider_id = db.Column(db.Integer, nullable=True, index=True)
    service_id = db.Column(db.Integer, nullable=True, index=True)
    provider_name = db.Column(db.String(180), nullable=True)
    destination = db.Column(db.String(180), nullable=True)
    booking_date = db.Column(db.Date, nullable=True)
    booking_time = db.Column(db.String(40), nullable=True)
    duration_days = db.Column(db.Integer, nullable=False, default=1)
    guests = db.Column(db.Integer, nullable=False, default=1)
    message = db.Column(db.Text, nullable=True)
    amount = db.Column(db.Float, nullable=True)
    currency = db.Column(db.String(3), nullable=False, default="INR")
    payment_status = db.Column(db.String(30), nullable=False, default="unpaid")
    status = db.Column(db.String(40), nullable=False, default="pending")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class SOSIncident(db.Model):
    __tablename__ = "sos_incidents"

    id = db.Column(db.Integer, primary_key=True)
    traveler_phone = db.Column(db.String(30), nullable=False, index=True)
    safety_response = db.Column(db.String(20), nullable=False, default="yes")
    mode = db.Column(db.String(30), nullable=False, default="standard")
    location_text = db.Column(db.String(255), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(40), nullable=False, default="initiated")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class RentalPartner(db.Model):
    __tablename__ = "rental_partners"

    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(30), nullable=False, unique=True, index=True)
    owner_name = db.Column(db.String(160), nullable=False)
    business_name = db.Column(db.String(180), nullable=False)
    location = db.Column(db.String(255), nullable=False)
    whatsapp = db.Column(db.String(30), nullable=True)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(40), nullable=False, default="approved")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    vehicles = db.relationship("BikeVehicle", back_populates="provider", cascade="all, delete-orphan")


class BikeVehicle(db.Model):
    __tablename__ = "bike_vehicles"

    id = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(db.Integer, db.ForeignKey("rental_partners.id"), nullable=False, index=True)
    name = db.Column(db.String(180), nullable=False)
    vehicle_type = db.Column(db.String(80), nullable=False)
    registration_number = db.Column(db.String(80), nullable=True)
    location = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Float, nullable=False, default=0.0)
    pricing_unit = db.Column(db.String(40), nullable=False, default="day")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    provider = db.relationship("RentalPartner", back_populates="vehicles")
    availabilities = db.relationship("BikeVehicleAvailability", back_populates="vehicle", cascade="all, delete-orphan")


class BikeVehicleAvailability(db.Model):
    __tablename__ = "bike_vehicle_availability"

    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("bike_vehicles.id"), nullable=False, index=True)
    available_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.String(20), nullable=True)
    end_time = db.Column(db.String(20), nullable=True)
    is_available = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    vehicle = db.relationship("BikeVehicle", back_populates="availabilities")


class ResortListing(db.Model):
    __tablename__ = "resort_listings"

    id = db.Column(db.Integer, primary_key=True)
    provider_phone = db.Column(db.String(30), nullable=False, index=True)
    provider_id = db.Column(db.Integer, nullable=True, index=True)
    name = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, nullable=False)
    address = db.Column(db.String(255), nullable=False)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    contact = db.Column(db.String(80), nullable=True)
    whatsapp = db.Column(db.String(30), nullable=True)
    amenities = db.Column(db.JSON, nullable=False, default=list)
    room_info = db.Column(db.JSON, nullable=False, default=list)
    photos = db.Column(db.JSON, nullable=False, default=list)
    status = db.Column(db.String(40), nullable=False, default="pending")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class AutoCaptain(db.Model):
    __tablename__ = "auto_captains"

    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(30), nullable=False, unique=True, index=True)
    owner_name = db.Column(db.String(160), nullable=False)
    full_name = db.Column(db.String(180), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    vehicle_number = db.Column(db.String(80), nullable=True)
    vehicle_type = db.Column(db.String(80), nullable=True)
    status = db.Column(db.String(40), nullable=False, default="approved")
    is_online = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class CoracleOperator(db.Model):
    __tablename__ = "coracle_operators"

    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(30), nullable=False, unique=True, index=True)
    business_name = db.Column(db.String(180), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    boat_capacity = db.Column(db.Integer, nullable=True)
    price = db.Column(db.Float, nullable=False, default=0.0)
    status = db.Column(db.String(40), nullable=False, default="approved")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class EmergencyContact(db.Model):
    __tablename__ = "emergency_contacts"

    id = db.Column(db.Integer, primary_key=True)
    user_phone = db.Column(db.String(30), nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    relationship = db.Column(db.String(80), nullable=True)
    is_primary = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class PaymentTransaction(db.Model):
    __tablename__ = "payment_transactions"

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), nullable=False, unique=True, index=True)
    booking_reference = db.Column(db.String(24), nullable=False, index=True)
    gateway_reference = db.Column(db.String(180), nullable=True, unique=True)
    provider_order_id = db.Column(db.String(180), nullable=True, unique=True)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="INR")
    status = db.Column(db.String(30), nullable=False, default="created")
    idempotency_key = db.Column(db.String(180), nullable=False, unique=True)
    refund_reference = db.Column(db.String(180), nullable=True, unique=True)
    refund_status = db.Column(db.String(30), nullable=True)
    refund_amount_minor = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    booking = db.relationship("Booking", backref=db.backref("payment_transaction", uselist=False))


class PaymentWebhookEvent(db.Model):
    __tablename__ = "payment_webhook_events"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.String(180), nullable=False, unique=True, index=True)
    event_type = db.Column(db.String(80), nullable=False)
    payload_sha256 = db.Column(db.String(64), nullable=False)
    processed_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class Review(db.Model):
    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), nullable=False, unique=True, index=True)
    traveler_phone = db.Column(db.String(30), nullable=False, index=True)
    provider_id = db.Column(db.Integer, nullable=False, index=True)
    rating = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    booking = db.relationship("Booking", backref=db.backref("review", uselist=False))


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    recipient_phone = db.Column(db.String(30), nullable=False, index=True)
    notification_type = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(180), nullable=False)
    message = db.Column(db.Text, nullable=False)
    related_type = db.Column(db.String(50), nullable=True)
    related_id = db.Column(db.Integer, nullable=True)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    read_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    actor_email = db.Column(db.String(255), nullable=False)
    action = db.Column(db.String(80), nullable=False)
    object_type = db.Column(db.String(80), nullable=False)
    object_id = db.Column(db.Integer, nullable=True)
    metadata_json = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
