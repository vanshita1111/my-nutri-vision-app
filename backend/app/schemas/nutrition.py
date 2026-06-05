"""
Pydantic schemas for nutrition DB and meal log endpoints.
"""

from pydantic import BaseModel, Field
from typing import Any, Optional, Literal
from datetime import datetime, date


class FoodSearchResult(BaseModel):
    food_id: str
    name: str
    category: Optional[str] = None
    source: str  # ifct / usda / openfoodfacts
    per_100g: dict  # {calories, protein_g, fat_g, carbs_g, fiber_g, ...}


class MealCreate(BaseModel):
    analysis_job_id: Optional[str] = None
    meal_type: Optional[Literal["breakfast", "lunch", "dinner", "snack"]] = None
    notes: Optional[str] = None
    eaten_at: Optional[datetime] = None


class MealUpdate(BaseModel):
    meal_type: Optional[Literal["breakfast", "lunch", "dinner", "snack"]] = None
    notes: Optional[str] = None
    eaten_at: Optional[datetime] = None


class MealSummary(BaseModel):
    id: str
    meal_type: Optional[str]
    total_calories: Optional[float]
    total_protein_g: Optional[float]
    total_fat_g: Optional[float]
    total_carbs_g: Optional[float]
    eaten_at: datetime
    image_thumbnail_url: Optional[str] = None
    item_count: int = 0


class DailyNutritionSummary(BaseModel):
    date: date
    total_calories: float
    total_protein_g: float
    total_fat_g: float
    total_carbs_g: float
    total_fiber_g: float
    meal_count: int
    calorie_goal: Optional[float] = None
    protein_goal_g: Optional[float] = None


class FoodItemDetail(BaseModel):
    id: str
    label: str
    grams: float = 0.0
    gram_confidence: Optional[str] = "low"
    is_hidden_ingredient: bool = False
    nutrition_source: Optional[str] = None
    nutrition: dict = {}  # {calories, protein_g, fat_g, carbs_g, fiber_g}

    class Config:
        from_attributes = True


class BloodSugarBreakdown(BaseModel):
    score: float
    level: str                              # low / moderate / high
    glycemic_load: float
    raw_glycemic_load: float = 0.0
    carb_density: float                     # percentage 0–100 (e.g. 25.0 = 25%)
    fiber_impact: float                     # decimal 0–1 (e.g. 0.30 = 30% reduction)
    protein_buffer: float                   # decimal 0–1
    fat_buffer: float                       # decimal 0–1
    explanation: str
    recommendations: list[str] = Field(default_factory=list)
    disclaimer: str
    per_item_gi: dict[str, Any] = Field(default_factory=dict)


class MealDetail(BaseModel):
    id: str
    meal_type: Optional[str] = None
    total_calories: Optional[float] = None
    total_protein_g: Optional[float] = None
    total_fat_g: Optional[float] = None
    total_carbs_g: Optional[float] = None
    total_fiber_g: Optional[float] = None
    llm_notes: Optional[str] = None
    analysis_version: Optional[str] = None
    eaten_at: datetime
    food_items: list[FoodItemDetail] = []
    blood_sugar_impact: Optional[BloodSugarBreakdown] = None

    class Config:
        from_attributes = True


class CyclePhaseInfo(BaseModel):
    phase: Literal["menstrual", "follicular", "ovulatory", "luteal", "unknown"]
    day_in_cycle: int
    calorie_adjustment_pct: float  # e.g. 0.05 = +5%
    protein_target_g: float
    iron_target_mg: float
    magnesium_target_mg: float
    phase_notes: str
    food_recommendations: list[str]
