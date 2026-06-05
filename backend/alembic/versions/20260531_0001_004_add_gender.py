"""add gender to users

Revision ID: 004
Revises: 003_target_weight
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa

revision = "004_gender"
down_revision = "003_target_weight"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("gender", sa.String(10), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "gender")
