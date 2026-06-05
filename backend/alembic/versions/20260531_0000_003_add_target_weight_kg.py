"""add target_weight_kg to users

Revision ID: 003
Revises: 002
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa

revision = "003_target_weight"
down_revision = "002_is_hidden"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("target_weight_kg", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "target_weight_kg")
