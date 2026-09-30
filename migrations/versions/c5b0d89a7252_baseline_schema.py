"""baseline schema

Revision ID: c5b0d89a7252
Revises: 
Create Date: 2026-09-25 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c5b0d89a7252"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("phone_number", sa.String(length=30), nullable=False),
        sa.Column("country_code", sa.String(length=10), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=100), nullable=True),
        sa.Column("last_name", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone_number"),
    )
    with op.batch_alter_table("users") as batch_op:
        batch_op.create_index(batch_op.f("ix_users_email"), ["email"], unique=False)

    op.create_table(
        "otp_challenges",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("phone_number", sa.String(length=30), nullable=False),
        sa.Column("purpose", sa.String(length=30), nullable=False),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("otp_challenges") as batch_op:
        batch_op.create_index(batch_op.f("ix_otp_challenges_phone_number"), ["phone_number"], unique=False)

    op.create_table(
        "traveler_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("phone_number", sa.String(length=30), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=True),
        sa.Column("country", sa.String(length=120), nullable=True),
        sa.Column("travel_style", sa.String(length=80), nullable=True),
        sa.Column("trip_duration", sa.String(length=80), nullable=True),
        sa.Column("interests", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone_number"),
    )
    with op.batch_alter_table("traveler_profiles") as batch_op:
        batch_op.create_index(batch_op.f("ix_traveler_profiles_user_id"), ["user_id"], unique=False)

    op.create_table(
        "partner_applications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("phone_number", sa.String(length=30), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("owner_name", sa.String(length=160), nullable=False),
        sa.Column("business_name", sa.String(length=180), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column("whatsapp", sa.String(length=30), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("verification_document_path", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("partner_applications") as batch_op:
        batch_op.create_index(batch_op.f("ix_partner_applications_category"), ["category"], unique=False)
        batch_op.create_index(batch_op.f("ix_partner_applications_phone_number"), ["phone_number"], unique=False)

    op.create_table(
        "guide_applications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("phone_number", sa.String(length=30), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column("experience_years", sa.String(length=50), nullable=False),
        sa.Column("bio", sa.Text(), nullable=False),
        sa.Column("languages", sa.JSON(), nullable=False),
        sa.Column("services", sa.JSON(), nullable=False),
        sa.Column("areas", sa.JSON(), nullable=False),
        sa.Column("max_group_size", sa.String(length=50), nullable=True),
        sa.Column("pricing_type", sa.String(length=50), nullable=True),
        sa.Column("hourly_rate", sa.Float(), nullable=True),
        sa.Column("half_day_rate", sa.Float(), nullable=True),
        sa.Column("full_day_rate", sa.Float(), nullable=True),
        sa.Column("pricing_group_size", sa.Integer(), nullable=True),
        sa.Column("minimum_booking_notice", sa.Integer(), nullable=True),
        sa.Column("available_days", sa.JSON(), nullable=False),
        sa.Column("time_slots", sa.JSON(), nullable=False),
        sa.Column("booking_notice", sa.String(length=50), nullable=True),
        sa.Column("booking_mode", sa.String(length=50), nullable=True),
        sa.Column("id_type", sa.String(length=50), nullable=True),
        sa.Column("identity_document_path", sa.String(length=500), nullable=True),
        sa.Column("credential_type", sa.String(length=100), nullable=True),
        sa.Column("credential_number", sa.String(length=255), nullable=True),
        sa.Column("credential_document_path", sa.String(length=500), nullable=True),
        sa.Column("profile_photo_path", sa.String(length=500), nullable=True),
        sa.Column("cover_photo_path", sa.String(length=500), nullable=True),
        sa.Column("gallery_photo_paths", sa.JSON(), nullable=False),
        sa.Column("payout_method", sa.String(length=30), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("traveler_phone", sa.String(length=30), nullable=False),
        sa.Column("booking_type", sa.String(length=40), nullable=False),
        sa.Column("provider_id", sa.Integer(), nullable=True),
        sa.Column("provider_name", sa.String(length=180), nullable=True),
        sa.Column("destination", sa.String(length=180), nullable=True),
        sa.Column("booking_date", sa.Date(), nullable=True),
        sa.Column("booking_time", sa.String(length=40), nullable=True),
        sa.Column("guests", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("amount", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("bookings") as batch_op:
        batch_op.create_index(batch_op.f("ix_bookings_provider_id"), ["provider_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_bookings_traveler_phone"), ["traveler_phone"], unique=False)

    op.create_table(
        "sos_incidents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("traveler_phone", sa.String(length=30), nullable=False),
        sa.Column("safety_response", sa.String(length=20), nullable=False),
        sa.Column("mode", sa.String(length=30), nullable=False),
        sa.Column("location_text", sa.String(length=255), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("sos_incidents") as batch_op:
        batch_op.create_index(batch_op.f("ix_sos_incidents_traveler_phone"), ["traveler_phone"], unique=False)

    op.create_table(
        "destinations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("slug", sa.String(length=150), nullable=False),
        sa.Column("region", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("opening_hours", sa.Text(), nullable=True),
        sa.Column("cultural_info", sa.Text(), nullable=True),
        sa.Column("safety_info", sa.Text(), nullable=True),
        sa.Column("highlights", sa.JSON(), nullable=False),
        sa.Column("rules", sa.JSON(), nullable=False),
        sa.Column("is_published", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )
    with op.batch_alter_table("destinations") as batch_op:
        batch_op.create_index(batch_op.f("ix_destinations_name"), ["name"], unique=False)
        batch_op.create_index(batch_op.f("ix_destinations_slug"), ["slug"], unique=False)

    op.create_table(
        "destination_images",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("destination_id", sa.Integer(), nullable=False),
        sa.Column("image_url", sa.String(length=500), nullable=False),
        sa.Column("caption", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["destination_id"], ["destinations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("destination_images") as batch_op:
        batch_op.create_index(batch_op.f("ix_destination_images_destination_id"), ["destination_id"], unique=False)


def downgrade():
    op.drop_table("destination_images")
    op.drop_table("destinations")
    op.drop_table("sos_incidents")
    op.drop_table("bookings")
    op.drop_table("guide_applications")
    op.drop_table("partner_applications")
    op.drop_table("traveler_profiles")
    op.drop_table("otp_challenges")
    op.drop_table("users")
