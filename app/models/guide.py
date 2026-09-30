from datetime import datetime, timezone

from app.extensions import db


class GuideApplication(db.Model):

    __tablename__ = "guide_applications"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    # -------------------------
    # Basic account information
    # -------------------------

    phone_number = db.Column(
        db.String(30),
        nullable=False
    )

    email = db.Column(
        db.String(255),
        nullable=True
    )

    first_name = db.Column(
        db.String(100),
        nullable=False
    )

    last_name = db.Column(
        db.String(100),
        nullable=False
    )

    location = db.Column(
        db.String(255),
        nullable=False
    )

    # -------------------------
    # Professional information
    # -------------------------

    experience_years = db.Column(
        db.String(50),
        nullable=False
    )

    bio = db.Column(
        db.Text,
        nullable=False
    )

    languages = db.Column(
        db.JSON,
        nullable=False,
        default=list
    )

    # -------------------------
    # Services
    # -------------------------

    services = db.Column(
        db.JSON,
        nullable=False,
        default=list
    )

    areas = db.Column(
        db.JSON,
        nullable=False,
        default=list
    )

    max_group_size = db.Column(
        db.String(50),
        nullable=True
    )

    # -------------------------
    # Pricing
    # -------------------------

    pricing_type = db.Column(
        db.String(50),
        nullable=True
    )

    hourly_rate = db.Column(
        db.Float,
        nullable=True
    )

    half_day_rate = db.Column(
        db.Float,
        nullable=True
    )

    full_day_rate = db.Column(
        db.Float,
        nullable=True
    )

    pricing_group_size = db.Column(
        db.Integer,
        nullable=True
    )

    minimum_booking_notice = db.Column(
        db.Integer,
        nullable=True
    )

    # -------------------------
    # Availability
    # -------------------------

    available_days = db.Column(
        db.JSON,
        nullable=False,
        default=list
    )

    time_slots = db.Column(
        db.JSON,
        nullable=False,
        default=list
    )

    booking_notice = db.Column(
        db.String(50),
        nullable=True
    )

    booking_mode = db.Column(
        db.String(50),
        nullable=True
    )

    # -------------------------
    # Verification
    # -------------------------

    id_type = db.Column(
        db.String(50),
        nullable=True
    )

    # Do NOT store the actual identity document here.
    identity_document_path = db.Column(
        db.String(500),
        nullable=True
    )

    credential_type = db.Column(
        db.String(100),
        nullable=True
    )

    credential_number = db.Column(
        db.String(255),
        nullable=True
    )

    # Do NOT store uploaded documents publicly.
    credential_document_path = db.Column(
        db.String(500),
        nullable=True
    )

    # -------------------------
    # Photos
    # -------------------------

    profile_photo_path = db.Column(
        db.String(500),
        nullable=True
    )

    cover_photo_path = db.Column(
        db.String(500),
        nullable=True
    )

    gallery_photo_paths = db.Column(
        db.JSON,
        nullable=False,
        default=list
    )

    # -------------------------
    # Payout
    # -------------------------

    payout_method = db.Column(
        db.String(30),
        nullable=True
    )

    # We intentionally do not persist
    # bank account / UPI credentials yet.
    #
    # Secure payout-provider integration
    # will be implemented later.

    # -------------------------
    # Application state
    # -------------------------

    status = db.Column(
        db.String(50),
        nullable=False,
        default="draft"
    )

    submitted_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True
    )

    reviewed_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self):

        return (
            f"<GuideApplication "
            f"{self.id} "
            f"{self.first_name} "
            f"{self.last_name} "
            f"{self.status}>"
        )