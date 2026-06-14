"""
Pydantic schemas for analysis endpoints.
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime


class MacroNutrients(BaseModel):
    calories: float = Field(default=0.0, ge=0)
    protein_g: float = Field(default=0.0, ge=0)
    fat_g: float = Field(default=0.0, ge=0)
    carbs_g: float = Field(default=0.0, ge=0)
    fiber_g: float = Field(default=0.0, ge=0)


class FoodItemResult(BaseModel):
    label: str
    grams: float
    gram_confidence: Literal["high", "medium", "low"]
    portion_method: Optional[str] = None
    detection_confidence: Optional[float] = None
    nutrition: MacroNutrients
    nutrition_source: Optional[str] = None  # ifct / usda / llm
    is_hidden_ingredient: Optional[bool] = False


class HiddenIngredient(BaseModel):
    name: str
    estimated_grams: float
    nutrition: MacroNutrients
    reason: str  # e.g. "Paratha typically fried in 10g ghee"


class BloodSugarImpact(BaseModel):
    score: float                          # 0–100 normalised score
    level: Literal["low", "moderate", "high"]
    glycemic_load: float                  # adjusted GL (after buffers)
    raw_glycemic_load: float = 0.0        # GL before buffers
    carb_density: float                   # % carbs by total food weight
    fiber_impact: float                   # 0–1 (higher = more protective)
    protein_buffer: float                 # 0–1
    fat_buffer: float                     # 0–1
    explanation: str
    recommendations: list[str] = Field(default_factory=list)
    disclaimer: str
    per_item_gi: dict = Field(default_factory=dict)  # {label: GI value}


class AnalysisResult(BaseModel):
    items: list[FoodItemResult]
    hidden_ingredients: list[HiddenIngredient] = Field(default_factory=list)
    total: MacroNutrients
    llm_notes: Optional[str] = None
    llm_confidence: Optional[Literal["high", "medium", "low"]] = None
    analysis_version: str = "2.0"
    analyzed_at: Optional[datetime] = None
    blood_sugar_impact: Optional[BloodSugarImpact] = None


class AnalysisJobCreate(BaseModel):
    """Returned immediately when a job is submitted."""
    job_id: str
    status: Literal["queued"] = "queued"


class AnalysisResponse(BaseModel):
    """Returned when polling for job status."""
    job_id: str
    status: Literal["queued", "processing", "complete", "failed"]
    result: Optional[AnalysisResult] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class UserCorrectionRequest(BaseModel):
    """User can correct a food item's label or grams after analysis."""
    food_item_id: str
    corrected_label: Optional[str] = None
    corrected_grams: Optional[float] = Field(default=None, gt=0, le=2000)


class AccuracyRatingRequest(BaseModel):
    """1-tap accuracy rating submitted after the user views their result."""
    rating: Literal["accurate", "roughly", "inaccurate"]
