"""
Nutrition DB endpoints: food search, cycle phase info, daily goals.
"""

from fastapi import APIRouter, Depends, Query
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.nutrition import FoodSearchResult, CyclePhaseInfo
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("/nutrition/search", response_model=list[FoodSearchResult])
async def search_foods(
    q: str = Query(min_length=2, description="Food name to search (fuzzy match)"),
    limit: int = Query(default=10, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Full-text fuzzy search across IFCT + USDA food DB."""
    from app.services.nutrition_db import NutritionDatabase
    ndb = NutritionDatabase(db)
    results = await ndb.search(q, limit=limit)
    return results


@router.get("/nutrition/cycle-phase", response_model=CyclePhaseInfo)
async def get_cycle_phase(
    current_user: User = Depends(get_current_user),
):
    """Return current menstrual cycle phase and phase-specific nutrition recommendations."""
    from app.services.cycle_service import CycleService
    service = CycleService()
    return service.get_phase_info(
        last_period_date=current_user.last_period_date,
        cycle_length=current_user.cycle_length_days,
        weight_kg=current_user.weight_kg,
        goal=current_user.goal,
    )


@router.get("/nutrition/daily-goals")
async def get_daily_goals(current_user: User = Depends(get_current_user)):
    """Calculate personalised daily nutrition goals (TDEE + macros + cycle adjustment)."""
    from app.services.goals_service import GoalsService
    service = GoalsService()
    return service.calculate(
        weight_kg=current_user.weight_kg,
        height_cm=current_user.height_cm,
        date_of_birth=current_user.date_of_birth,
        activity_level=current_user.activity_level,
        goal=current_user.goal,
        gender=current_user.gender,
        target_weight_kg=current_user.target_weight_kg,
        health_conditions=current_user.health_conditions or [],
        last_period_date=current_user.last_period_date,
        cycle_length=current_user.cycle_length_days,
    )
