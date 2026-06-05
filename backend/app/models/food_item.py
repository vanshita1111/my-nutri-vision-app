"""
FoodItem ORM model — individual detected food items within a meal.
"""

import uuid
from typing import Optional
from sqlalchemy import String, Float, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class FoodItem(Base):
    __tablename__ = "food_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    meal_id: Mapped[str] = mapped_column(String(36), ForeignKey("meals.id", ondelete="CASCADE"), nullable=False, index=True)

    # Detection
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    detection_confidence: Mapped[Optional[float]] = mapped_column(Float)
    bbox: Mapped[Optional[dict]] = mapped_column(JSON)  # {x1, y1, x2, y2}

    # Portion
    estimated_grams: Mapped[Optional[float]] = mapped_column(Float)
    gram_confidence: Mapped[Optional[str]] = mapped_column(String(10))  # high/medium/low
    portion_method: Mapped[Optional[str]] = mapped_column(String(50))  # depth_integration/reference_object/prior

    # Nutrition (per this item, already scaled to estimated_grams)
    calories: Mapped[Optional[float]] = mapped_column(Float)
    protein_g: Mapped[Optional[float]] = mapped_column(Float)
    fat_g: Mapped[Optional[float]] = mapped_column(Float)
    carbs_g: Mapped[Optional[float]] = mapped_column(Float)
    fiber_g: Mapped[Optional[float]] = mapped_column(Float)

    # User corrections
    user_corrected_grams: Mapped[Optional[float]] = mapped_column(Float)
    user_corrected_label: Mapped[Optional[str]] = mapped_column(String(200))

    # Hidden ingredient flag (oil, butter, salt added during cooking, not visible)
    is_hidden_ingredient: Mapped[bool] = mapped_column(default=False, nullable=False, server_default="false")

    # Nutrition DB source
    nutrition_source: Mapped[Optional[str]] = mapped_column(String(50))  # ifct/usda/llm/openfoodfacts

    # Relationship
    meal: Mapped["Meal"] = relationship("Meal", back_populates="food_items")  # noqa: F821

    def __repr__(self) -> str:
        return f"<FoodItem label={self.label} grams={self.estimated_grams} kcal={self.calories}>"
