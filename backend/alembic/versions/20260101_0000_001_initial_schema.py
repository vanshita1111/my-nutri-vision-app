"""Initial schema — users, meals, food_items, foods (nutrition DB)

Revision ID: 001_initial
Revises:
Create Date: 2026-01-01 00:00:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pg_trgm for fuzzy food search
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ── users ────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id",               sa.String(36),  primary_key=True),
        sa.Column("email",            sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password",  sa.String(255), nullable=False),
        sa.Column("full_name",        sa.String(200)),
        sa.Column("is_active",        sa.Boolean,     nullable=False, server_default="true"),
        sa.Column("is_premium",       sa.Boolean,     nullable=False, server_default="false"),
        sa.Column("date_of_birth",    sa.Date),
        sa.Column("weight_kg",        sa.Float),
        sa.Column("height_cm",        sa.Float),
        sa.Column("activity_level",   sa.String(50)),
        sa.Column("goal",             sa.String(50)),
        sa.Column("last_period_date", sa.Date),
        sa.Column("cycle_length_days",sa.Integer, nullable=False, server_default="28"),
        sa.Column("created_at",       sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at",       sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # ── meals ────────────────────────────────────────────────────────────────
    op.create_table(
        "meals",
        sa.Column("id",                  sa.String(36), primary_key=True),
        sa.Column("user_id",             sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("analysis_job_id",     sa.String(36)),
        sa.Column("image_s3_key",        sa.String(500)),
        sa.Column("image_thumbnail_key", sa.String(500)),
        sa.Column("total_calories",      sa.Float),
        sa.Column("total_protein_g",     sa.Float),
        sa.Column("total_fat_g",         sa.Float),
        sa.Column("total_carbs_g",       sa.Float),
        sa.Column("total_fiber_g",       sa.Float),
        sa.Column("meal_type",           sa.String(50)),
        sa.Column("notes",               sa.Text),
        sa.Column("llm_notes",           sa.Text),
        sa.Column("analysis_version",    sa.String(10)),
        sa.Column("eaten_at",            sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at",          sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_meals_user_id",         "meals", ["user_id"])
    op.create_index("ix_meals_analysis_job_id", "meals", ["analysis_job_id"])
    op.create_index("ix_meals_eaten_at",        "meals", ["eaten_at"])

    # ── food_items ────────────────────────────────────────────────────────────
    op.create_table(
        "food_items",
        sa.Column("id",                    sa.String(36), primary_key=True),
        sa.Column("meal_id",               sa.String(36), sa.ForeignKey("meals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label",                 sa.String(200), nullable=False),
        sa.Column("detection_confidence",  sa.Float),
        sa.Column("bbox",                  postgresql.JSONB),
        sa.Column("estimated_grams",       sa.Float),
        sa.Column("gram_confidence",       sa.String(10)),
        sa.Column("portion_method",        sa.String(50)),
        sa.Column("calories",              sa.Float),
        sa.Column("protein_g",             sa.Float),
        sa.Column("fat_g",                 sa.Float),
        sa.Column("carbs_g",               sa.Float),
        sa.Column("fiber_g",               sa.Float),
        sa.Column("user_corrected_grams",  sa.Float),
        sa.Column("user_corrected_label",  sa.String(200)),
        sa.Column("nutrition_source",      sa.String(50)),
    )
    op.create_index("ix_food_items_meal_id", "food_items", ["meal_id"])

    # ── foods (nutrition DB) ──────────────────────────────────────────────────
    op.create_table(
        "foods",
        sa.Column("food_id",             sa.String(100), primary_key=True),
        sa.Column("name",                sa.Text,        nullable=False),
        sa.Column("category",            sa.Text),
        sa.Column("source",              sa.String(20),  nullable=False, server_default="ifct"),
        sa.Column("calories_per_100g",   sa.Float),
        sa.Column("protein_g_per_100g",  sa.Float),
        sa.Column("fat_g_per_100g",      sa.Float),
        sa.Column("carbs_g_per_100g",    sa.Float),
        sa.Column("fiber_g_per_100g",    sa.Float),
        sa.Column("iron_mg_per_100g",    sa.Float),
        sa.Column("calcium_mg_per_100g", sa.Float),
        sa.Column("zinc_mg_per_100g",    sa.Float),
        sa.Column("created_at",          sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # GIN index for fast fuzzy search (requires pg_trgm)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_foods_name_trgm
        ON foods USING GIN (name gin_trgm_ops)
    """)


def downgrade() -> None:
    op.drop_table("food_items")
    op.drop_table("meals")
    op.drop_table("users")
    op.drop_table("foods")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
