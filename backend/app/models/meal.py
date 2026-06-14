"""
Meal ORM model — one meal = one photo analysis session.
"""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Float, ForeignKey, Text, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Meal(Base):
    __tablename__ = "meals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_job_id: Mapped[Optional[str]] = mapped_column(String(36), index=True)

    # Image — primary key kept for backwards compat; all keys stored for training data
    image_s3_key: Mapped[Optional[str]] = mapped_column(String(500))
    image_thumbnail_key: Mapped[Optional[str]] = mapped_column(String(500))
    all_image_s3_keys: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Training signal — 1-tap user accuracy rating collected post-analysis
    accuracy_rating: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Aggregated nutrition (denormalised for fast history queries)
    total_calories: Mapped[Optional[float]] = mapped_column(Float)
    total_protein_g: Mapped[Optional[float]] = mapped_column(Float)
    total_fat_g: Mapped[Optional[float]] = mapped_column(Float)
    total_carbs_g: Mapped[Optional[float]] = mapped_column(Float)
    total_fiber_g: Mapped[Optional[float]] = mapped_column(Float)

    # Metadata
    meal_type: Mapped[Optional[str]] = mapped_column(String(50))  # breakfast/lunch/dinner/snack
    notes: Mapped[Optional[str]] = mapped_column(Text)
    llm_notes: Mapped[Optional[str]] = mapped_column(Text)
    analysis_version: Mapped[Optional[str]] = mapped_column(String(10))
    eaten_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Blood sugar impact (calculated post-analysis, nullable for legacy meals)
    blood_sugar_score: Mapped[Optional[float]] = mapped_column(Float)         # 0–100
    blood_sugar_level: Mapped[Optional[str]]   = mapped_column(String(20))    # low/moderate/high
    blood_sugar_data:  Mapped[Optional[dict]]  = mapped_column(JSON)          # full breakdown

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="meals")  # noqa: F821
    food_items: Mapped[list["FoodItem"]] = relationship("FoodItem", back_populates="meal", cascade="all, delete-orphan")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Meal id={self.id} calories={self.total_calories}>"
