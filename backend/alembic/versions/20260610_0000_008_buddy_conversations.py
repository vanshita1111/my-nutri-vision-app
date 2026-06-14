"""Add conversations and messages tables for AI Nutrition Buddy

Revision ID: 008_buddy_conversations
Revises: 007_blood_sugar_impact
Create Date: 2026-06-10
"""
from alembic import op
import sqlalchemy as sa

revision = "008_buddy_conversations"
down_revision = "007_blood_sugar_impact"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id",         sa.String(36),  primary_key=True),
        sa.Column("user_id",    sa.String(36),  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title",      sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "messages",
        sa.Column("id",              sa.String(36),  primary_key=True),
        sa.Column("conversation_id", sa.String(36),  sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("role",            sa.String(20),  nullable=False),   # user | assistant
        sa.Column("content",         sa.Text(),      nullable=False),
        sa.Column("created_at",      sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("messages")
    op.drop_table("conversations")
