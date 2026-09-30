from datetime import datetime, timezone

from app.extensions import db


class Destination(db.Model):
    __tablename__ = "destinations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, unique=True, index=True)
    slug = db.Column(db.String(150), nullable=False, unique=True, index=True)
    region = db.Column(db.String(120), nullable=False, default="Hampi")
    category = db.Column(db.String(80), nullable=False, default="heritage")
    description = db.Column(db.Text, nullable=False)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    opening_hours = db.Column(db.Text, nullable=True)
    cultural_info = db.Column(db.Text, nullable=True)
    safety_info = db.Column(db.Text, nullable=True)
    highlights = db.Column(db.JSON, nullable=False, default=list)
    rules = db.Column(db.JSON, nullable=False, default=list)
    is_published = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    images = db.relationship("DestinationImage", back_populates="destination", cascade="all, delete-orphan")


class DestinationImage(db.Model):
    __tablename__ = "destination_images"

    id = db.Column(db.Integer, primary_key=True)
    destination_id = db.Column(db.Integer, db.ForeignKey("destinations.id"), nullable=False, index=True)
    image_url = db.Column(db.String(500), nullable=False)
    caption = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    destination = db.relationship("Destination", back_populates="images")
