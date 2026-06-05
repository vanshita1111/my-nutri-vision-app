"""add health_conditions to users

Revision ID: 005
Revises: 004_gender
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa

revision = "005_health_conditions"
down_revision = "004_gender"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("health_conditions", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "health_conditions")
