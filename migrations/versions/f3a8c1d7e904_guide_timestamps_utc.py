"""make guide application timestamps timezone-aware

Revision ID: f3a8c1d7e904
Revises: e2f6a1c4b8d0
Create Date: 2026-09-26 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "f3a8c1d7e904"
down_revision = "e2f6a1c4b8d0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("guide_applications") as batch_op:
        batch_op.alter_column(
            "submitted_at",
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using="submitted_at AT TIME ZONE 'UTC'",
        )
        batch_op.alter_column(
            "reviewed_at",
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using="reviewed_at AT TIME ZONE 'UTC'",
        )


def downgrade():
    with op.batch_alter_table("guide_applications") as batch_op:
        batch_op.alter_column(
            "reviewed_at",
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
            postgresql_using="reviewed_at AT TIME ZONE 'UTC'",
        )
        batch_op.alter_column(
            "submitted_at",
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
            postgresql_using="submitted_at AT TIME ZONE 'UTC'",
        )