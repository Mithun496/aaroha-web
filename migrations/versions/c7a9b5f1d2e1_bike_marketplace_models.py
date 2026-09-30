"""bike marketplace models

Revision ID: c7a9b5f1d2e1
Revises: 3f7d2efab4ca
Create Date: 2026-09-25 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7a9b5f1d2e1'
down_revision = 'c5b0d89a7252'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'rental_partners',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('phone_number', sa.String(length=30), nullable=False),
        sa.Column('owner_name', sa.String(length=160), nullable=False),
        sa.Column('business_name', sa.String(length=180), nullable=False),
        sa.Column('location', sa.String(length=255), nullable=False),
        sa.Column('whatsapp', sa.String(length=30), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=40), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('phone_number')
    )
    with op.batch_alter_table('rental_partners') as batch_op:
        batch_op.create_index(batch_op.f('ix_rental_partners_phone_number'), ['phone_number'], unique=False)

    op.create_table(
        'bike_vehicles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=180), nullable=False),
        sa.Column('vehicle_type', sa.String(length=80), nullable=False),
        sa.Column('registration_number', sa.String(length=80), nullable=True),
        sa.Column('location', sa.String(length=200), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('pricing_unit', sa.String(length=40), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['provider_id'], ['rental_partners.id']),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('bike_vehicles') as batch_op:
        batch_op.create_index(batch_op.f('ix_bike_vehicles_provider_id'), ['provider_id'], unique=False)

    op.create_table(
        'bike_vehicle_availability',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('vehicle_id', sa.Integer(), nullable=False),
        sa.Column('available_date', sa.Date(), nullable=False),
        sa.Column('start_time', sa.String(length=20), nullable=True),
        sa.Column('end_time', sa.String(length=20), nullable=True),
        sa.Column('is_available', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['vehicle_id'], ['bike_vehicles.id']),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('bike_vehicle_availability') as batch_op:
        batch_op.create_index(batch_op.f('ix_bike_vehicle_availability_vehicle_id'), ['vehicle_id'], unique=False)

    op.create_table(
        'resort_listings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider_phone', sa.String(length=30), nullable=False),
        sa.Column('provider_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=180), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('address', sa.String(length=255), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('contact', sa.String(length=80), nullable=True),
        sa.Column('whatsapp', sa.String(length=30), nullable=True),
        sa.Column('amenities', sa.JSON(), nullable=False),
        sa.Column('room_info', sa.JSON(), nullable=False),
        sa.Column('photos', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=40), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('resort_listings') as batch_op:
        batch_op.create_index(batch_op.f('ix_resort_listings_provider_phone'), ['provider_phone'], unique=False)
        batch_op.create_index(batch_op.f('ix_resort_listings_provider_id'), ['provider_id'], unique=False)

    op.create_table(
        'auto_captains',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('phone_number', sa.String(length=30), nullable=False),
        sa.Column('owner_name', sa.String(length=160), nullable=False),
        sa.Column('full_name', sa.String(length=180), nullable=False),
        sa.Column('location', sa.String(length=200), nullable=False),
        sa.Column('vehicle_number', sa.String(length=80), nullable=True),
        sa.Column('vehicle_type', sa.String(length=80), nullable=True),
        sa.Column('status', sa.String(length=40), nullable=False),
        sa.Column('is_online', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('phone_number')
    )
    with op.batch_alter_table('auto_captains') as batch_op:
        batch_op.create_index(batch_op.f('ix_auto_captains_phone_number'), ['phone_number'], unique=False)

    op.create_table(
        'coracle_operators',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('phone_number', sa.String(length=30), nullable=False),
        sa.Column('business_name', sa.String(length=180), nullable=False),
        sa.Column('location', sa.String(length=200), nullable=False),
        sa.Column('boat_capacity', sa.Integer(), nullable=True),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('status', sa.String(length=40), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('phone_number')
    )
    with op.batch_alter_table('coracle_operators') as batch_op:
        batch_op.create_index(batch_op.f('ix_coracle_operators_phone_number'), ['phone_number'], unique=False)

    op.create_table(
        'emergency_contacts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_phone', sa.String(length=30), nullable=False),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('phone', sa.String(length=30), nullable=False),
        sa.Column('relationship', sa.String(length=80), nullable=True),
        sa.Column('is_primary', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('emergency_contacts') as batch_op:
        batch_op.create_index(batch_op.f('ix_emergency_contacts_user_phone'), ['user_phone'], unique=False)


def downgrade():
    op.drop_table('emergency_contacts')
    op.drop_table('coracle_operators')
    op.drop_table('auto_captains')
    op.drop_table('resort_listings')
    op.drop_table('bike_vehicle_availability')
    op.drop_table('bike_vehicles')
    op.drop_table('rental_partners')
