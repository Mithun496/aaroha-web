"""add Razorpay order, refund, and webhook state

Revision ID: g4b7c2e9a610
Revises: f3a8c1d7e904
Create Date: 2026-09-30
"""
from alembic import op
import sqlalchemy as sa


revision = "g4b7c2e9a610"
down_revision = "f3a8c1d7e904"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("payment_transactions") as batch_op:
        batch_op.add_column(sa.Column("provider_order_id", sa.String(length=180), nullable=True))
        batch_op.add_column(sa.Column("refund_reference", sa.String(length=180), nullable=True))
        batch_op.add_column(sa.Column("refund_status", sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column("refund_amount_minor", sa.Integer(), nullable=True))
        batch_op.create_unique_constraint("uq_payment_transactions_provider_order_id", ["provider_order_id"])
        batch_op.create_unique_constraint("uq_payment_transactions_refund_reference", ["refund_reference"])

    op.create_table(
        "payment_webhook_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(length=180), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_payment_webhook_events_event_id"),
    )
    op.create_index("ix_payment_webhook_events_event_id", "payment_webhook_events", ["event_id"])


def downgrade():
    op.drop_index("ix_payment_webhook_events_event_id", table_name="payment_webhook_events")
    op.drop_table("payment_webhook_events")
    with op.batch_alter_table("payment_transactions") as batch_op:
        batch_op.drop_constraint("uq_payment_transactions_refund_reference", type_="unique")
        batch_op.drop_constraint("uq_payment_transactions_provider_order_id", type_="unique")
        batch_op.drop_column("refund_amount_minor")
        batch_op.drop_column("refund_status")
        batch_op.drop_column("refund_reference")
        batch_op.drop_column("provider_order_id")
