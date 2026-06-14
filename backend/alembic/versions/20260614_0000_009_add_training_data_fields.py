"""add training data fields to meals

Revision ID: 009_training_data
Revises: 008_buddy_conversations
Create Date: 2026-06-14

Adds:
  meals.all_image_s3_keys  — JSON array of every S3 key submitted for this job
                             (multi-photo support; primary key stays in image_s3_key)
  meals.accuracy_rating    — user's 1-tap quality signal: accurate / roughly / inaccurate
"""

from alembic import op
import sqlalchemy as sa

revision = "009_training_data"
down_revision = "008_buddy_conversations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("meals", sa.Column("all_image_s3_keys", sa.JSON(),      nullable=True))
    op.add_column("meals", sa.Column("accuracy_rating",   sa.String(20),  nullable=True))


def downgrade() -> None:
    op.drop_column("meals", "accuracy_rating")
    op.drop_column("meals", "all_image_s3_keys")
