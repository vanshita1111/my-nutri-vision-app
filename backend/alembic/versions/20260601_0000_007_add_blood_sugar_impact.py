"""Add blood_sugar_score, blood_sugar_level, blood_sugar_data to meals

Revision ID: 007_blood_sugar_impact
Revises: 006_social_auth
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "007_blood_sugar_impact"
down_revision = "006_social_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("meals", sa.Column("blood_sugar_score", sa.Float(), nullable=True))
    op.add_column("meals", sa.Column("blood_sugar_level", sa.String(20), nullable=True))
    op.add_column("meals", sa.Column("blood_sugar_data",  sa.JSON(),    nullable=True))


def downgrade() -> None:
    op.drop_column("meals", "blood_sugar_data")
    op.drop_column("meals", "blood_sugar_level")
    op.drop_column("meals", "blood_sugar_score")
