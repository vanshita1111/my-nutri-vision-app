"""Add is_hidden_ingredient column to food_items

Revision ID: 002_is_hidden
Revises: 001_initial
Create Date: 2026-05-25 00:00:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002_is_hidden"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "food_items",
        sa.Column(
            "is_hidden_ingredient",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("food_items", "is_hidden_ingredient")
