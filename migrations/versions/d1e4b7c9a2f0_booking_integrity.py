"""add booking integrity fields

Revision ID: d1e4b7c9a2f0
Revises: c7a9b5f1d2e1
Create Date: 2026-09-25 00:00:00.000000

"""
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision = "d1e4b7c9a2f0"
down_revision = "c7a9b5f1d2e1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("bookings", sa.Column("booking_reference", sa.String(length=24), nullable=True))
    op.add_column("bookings", sa.Column("service_id", sa.Integer(), nullable=True))
    op.add_column("bookings", sa.Column("duration_days", sa.Integer(), nullable=True))
    op.add_column("bookings", sa.Column("currency", sa.String(length=3), nullable=True))
    op.add_column("bookings", sa.Column("payment_status", sa.String(length=30), nullable=True))

    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id FROM bookings WHERE booking_reference IS NULL")).fetchall()
    for row in rows:
        connection.execute(
            sa.text("UPDATE bookings SET booking_reference = :reference WHERE id = :id"),
            {"reference": f"AAR-{uuid4().hex[:12].upper()}", "id": row[0]},
        )
    connection.execute(sa.text("UPDATE bookings SET duration_days = 1 WHERE duration_days IS NULL"))
    connection.execute(sa.text("UPDATE bookings SET currency = 'INR' WHERE currency IS NULL"))
    connection.execute(sa.text("UPDATE bookings SET payment_status = 'unpaid' WHERE payment_status IS NULL"))

    with op.batch_alter_table("bookings") as batch_op:
        batch_op.alter_column("booking_reference", existing_type=sa.String(length=24), nullable=False)
        batch_op.alter_column("duration_days", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("currency", existing_type=sa.String(length=3), nullable=False)
        batch_op.alter_column("payment_status", existing_type=sa.String(length=30), nullable=False)
        batch_op.create_index("ix_bookings_service_id", ["service_id"], unique=False)
        batch_op.create_unique_constraint("uq_bookings_booking_reference", ["booking_reference"])


def downgrade():
    with op.batch_alter_table("bookings") as batch_op:
        batch_op.drop_constraint("uq_bookings_booking_reference", type_="unique")
        batch_op.drop_index("ix_bookings_service_id")
        batch_op.drop_column("payment_status")
        batch_op.drop_column("currency")
        batch_op.drop_column("duration_days")
        batch_op.drop_column("service_id")
        batch_op.drop_column("booking_reference")
