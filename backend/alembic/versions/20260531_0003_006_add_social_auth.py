"""add social auth fields to users

Revision ID: 006
Revises: 005_health_conditions
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa

revision = "006_social_auth"
down_revision = "005_health_conditions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("auth_provider", sa.String(20), nullable=False, server_default="email"))
    op.add_column("users", sa.Column("google_id",    sa.String(128), nullable=True))
    op.add_column("users", sa.Column("apple_id",     sa.String(128), nullable=True))
    op.add_column("users", sa.Column("is_guest",     sa.Boolean(),   nullable=False, server_default="false"))
    op.create_unique_constraint("uq_users_google_id", "users", ["google_id"])
    op.create_unique_constraint("uq_users_apple_id",  "users", ["apple_id"])


def downgrade() -> None:
    op.drop_constraint("uq_users_apple_id",  "users", type_="unique")
    op.drop_constraint("uq_users_google_id", "users", type_="unique")
    op.drop_column("users", "is_guest")
    op.drop_column("users", "apple_id")
    op.drop_column("users", "google_id")
    op.drop_column("users", "auth_provider")
