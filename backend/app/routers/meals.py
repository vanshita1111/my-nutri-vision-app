"""
Meal log CRUD + history endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, cast, Date
from datetime import date, timedelta
from pydantic import BaseModel, Field

from app.config import settings
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.models.meal import Meal
from app.schemas.nutrition import MealSummary, MealDetail, FoodItemDetail, DailyNutritionSummary, BloodSugarBreakdown


def _bust_coaching_cache(user_id: str) -> None:
    """Delete the 12-hour Redis coaching cache so the next request regenerates with fresh data."""
    try:
        import redis as _redis
        r = _redis.from_url(settings.REDIS_URL, decode_responses=True)
        r.delete(f"nv:coaching:weekly:{user_id}")
    except Exception:
        pass


class PortionAdjustment(BaseModel):
    food_item_id: str
    multiplier: float = Field(gt=0, le=10)


class PortionAdjustmentsRequest(BaseModel):
    adjustments: list[PortionAdjustment]

router = APIRouter()


@router.get("/meals", response_model=list[MealSummary])
async def list_meals(
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Paginated meal history for the authenticated user."""
    from sqlalchemy.orm import selectinload

    stmt = (
        select(Meal)
        .where(Meal.user_id == current_user.id)
        .options(selectinload(Meal.food_items))  # needed to count items without lazy-load error
        .order_by(Meal.eaten_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    meals = result.scalars().all()

    summaries = []
    for m in meals:
        summaries.append(MealSummary(
            id=m.id,
            meal_type=m.meal_type,
            total_calories=m.total_calories,
            total_protein_g=m.total_protein_g,
            total_fat_g=m.total_fat_g,
            total_carbs_g=m.total_carbs_g,
            eaten_at=m.eaten_at,
            item_count=len(m.food_items),
        ))
    return summaries


def _meal_to_detail(meal: Meal) -> MealDetail:
    """Convert ORM Meal → MealDetail schema (including nested food_items)."""
    items = []
    for fi in (meal.food_items or []):
        items.append(FoodItemDetail(
            id=fi.id,
            label=fi.label,
            grams=fi.estimated_grams or 0.0,
            gram_confidence=fi.gram_confidence or "low",
            is_hidden_ingredient=fi.is_hidden_ingredient or False,
            nutrition_source=fi.nutrition_source,
            nutrition={
                "calories":  fi.calories  or 0,
                "protein_g": fi.protein_g or 0,
                "fat_g":     fi.fat_g     or 0,
                "carbs_g":   fi.carbs_g   or 0,
                "fiber_g":   fi.fiber_g   or 0,
            },
        ))
    bs_impact = None
    if meal.blood_sugar_data:
        try:
            bs_impact = BloodSugarBreakdown(**meal.blood_sugar_data)
        except Exception:
            pass

    return MealDetail(
        id=meal.id,
        meal_type=meal.meal_type,
        total_calories=meal.total_calories,
        total_protein_g=meal.total_protein_g,
        total_fat_g=meal.total_fat_g,
        total_carbs_g=meal.total_carbs_g,
        total_fiber_g=meal.total_fiber_g,
        llm_notes=meal.llm_notes,
        analysis_version=meal.analysis_version,
        eaten_at=meal.eaten_at,
        food_items=items,
        blood_sugar_impact=bs_impact,
    )


@router.get("/meals/{meal_id}", response_model=MealDetail)
async def get_meal(
    meal_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return full meal detail including food items."""
    from sqlalchemy.orm import selectinload
    stmt = select(Meal).where(Meal.id == meal_id).options(selectinload(Meal.food_items))
    result = await db.execute(stmt)
    meal = result.scalar_one_or_none()
    if not meal or meal.user_id != current_user.id:
        raise HTTPException(404, "Meal not found.")
    return _meal_to_detail(meal)


@router.post("/meals/from-job/{job_id}", response_model=MealDetail)
async def get_meal_from_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Called by the confirm screen after analysis completes.
    Looks up the meal that was auto-persisted for this analysis job and returns it.
    """
    from sqlalchemy.orm import selectinload
    stmt = (
        select(Meal)
        .where(Meal.analysis_job_id == job_id, Meal.user_id == str(current_user.id))
        .options(selectinload(Meal.food_items))
    )
    result = await db.execute(stmt)
    meal = result.scalar_one_or_none()
    if not meal:
        raise HTTPException(404, "Meal not yet saved — analysis may still be processing.")
    return _meal_to_detail(meal)


@router.delete("/meals/{meal_id}/items/{item_id}", response_model=MealDetail)
async def delete_food_item(
    meal_id: str,
    item_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove one food item from a meal and recompute meal totals."""
    from sqlalchemy.orm import selectinload
    from app.models.food_item import FoodItem

    stmt = select(Meal).where(Meal.id == meal_id).options(selectinload(Meal.food_items))
    result = await db.execute(stmt)
    meal = result.scalar_one_or_none()
    if not meal or meal.user_id != current_user.id:
        raise HTTPException(404, "Meal not found.")

    item = next((fi for fi in meal.food_items if fi.id == item_id), None)
    if not item:
        raise HTTPException(404, "Food item not found.")

    await db.delete(item)

    # Recompute totals after removal
    remaining = [fi for fi in meal.food_items if fi.id != item_id]
    meal.total_calories  = round(sum(fi.calories  or 0 for fi in remaining), 2)
    meal.total_protein_g = round(sum(fi.protein_g or 0 for fi in remaining), 2)
    meal.total_fat_g     = round(sum(fi.fat_g     or 0 for fi in remaining), 2)
    meal.total_carbs_g   = round(sum(fi.carbs_g   or 0 for fi in remaining), 2)
    meal.total_fiber_g   = round(sum(fi.fiber_g   or 0 for fi in remaining), 2)

    await db.commit()
    await db.refresh(meal)
    _bust_coaching_cache(current_user.id)
    return _meal_to_detail(meal)


@router.delete("/meals/{meal_id}", status_code=204)
async def delete_meal(
    meal_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    meal = await db.get(Meal, meal_id)
    if not meal or meal.user_id != current_user.id:
        raise HTTPException(404, "Meal not found.")
    await db.delete(meal)
    await db.commit()
    _bust_coaching_cache(current_user.id)


@router.get("/nutrition/daily", response_model=list[DailyNutritionSummary])
async def daily_nutrition(
    days: int = Query(default=7, le=90),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate daily nutrition for the past N days."""
    since = date.today() - timedelta(days=days)
    stmt = (
        select(
            cast(Meal.eaten_at, Date).label("day"),
            func.sum(Meal.total_calories).label("calories"),
            func.sum(Meal.total_protein_g).label("protein_g"),
            func.sum(Meal.total_fat_g).label("fat_g"),
            func.sum(Meal.total_carbs_g).label("carbs_g"),
            func.sum(Meal.total_fiber_g).label("fiber_g"),
            func.count(Meal.id).label("meal_count"),
        )
        .where(Meal.user_id == current_user.id, cast(Meal.eaten_at, Date) >= since)
        .group_by("day")
        .order_by("day")
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        DailyNutritionSummary(
            date=row.day,
            total_calories=row.calories or 0,
            total_protein_g=row.protein_g or 0,
            total_fat_g=row.fat_g or 0,
            total_carbs_g=row.carbs_g or 0,
            total_fiber_g=row.fiber_g or 0,
            meal_count=row.meal_count,
        )
        for row in rows
    ]


@router.patch("/meals/{meal_id}/portions", response_model=MealDetail)
async def adjust_portions(
    meal_id: str,
    body: PortionAdjustmentsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Apply per-item multipliers from the confirm screen.
    Re-scales estimated_grams and all macro fields, then updates the meal totals.
    """
    from sqlalchemy.orm import selectinload

    stmt = select(Meal).where(Meal.id == meal_id).options(selectinload(Meal.food_items))
    result = await db.execute(stmt)
    meal = result.scalar_one_or_none()
    if not meal or meal.user_id != current_user.id:
        raise HTTPException(404, "Meal not found.")

    adj_map = {a.food_item_id: a.multiplier for a in body.adjustments}

    for fi in meal.food_items:
        m = adj_map.get(fi.id)
        if m is None or m == 1.0:
            continue
        fi.estimated_grams = round((fi.estimated_grams or 0) * m, 1)
        fi.calories  = round((fi.calories  or 0) * m, 2)
        fi.protein_g = round((fi.protein_g or 0) * m, 2)
        fi.fat_g     = round((fi.fat_g     or 0) * m, 2)
        fi.carbs_g   = round((fi.carbs_g   or 0) * m, 2)
        fi.fiber_g   = round((fi.fiber_g   or 0) * m, 2)

    # Recompute denormalised meal totals
    meal.total_calories  = round(sum(fi.calories  or 0 for fi in meal.food_items), 2)
    meal.total_protein_g = round(sum(fi.protein_g or 0 for fi in meal.food_items), 2)
    meal.total_fat_g     = round(sum(fi.fat_g     or 0 for fi in meal.food_items), 2)
    meal.total_carbs_g   = round(sum(fi.carbs_g   or 0 for fi in meal.food_items), 2)
    meal.total_fiber_g   = round(sum(fi.fiber_g   or 0 for fi in meal.food_items), 2)

    await db.commit()
    await db.refresh(meal)
    _bust_coaching_cache(current_user.id)
    return _meal_to_detail(meal)
