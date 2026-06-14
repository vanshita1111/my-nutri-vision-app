"""
Context assembler for AI Nutrition Buddy.

Builds a structured system-prompt block containing the user's full nutritional
context: profile, daily targets, today's intake, recent meals, and 7-day trend.

The assembled block is cached in Redis for 5 minutes (key: nv:buddy:ctx:{user_id}).
Call invalidate_buddy_context(user_id) whenever a meal is saved or deleted so the
next message always reflects current data.
"""

import json
import logging
from datetime import date, timedelta, datetime

from sqlalchemy import select, func, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User
from app.models.meal import Meal

log = logging.getLogger(__name__)

CACHE_TTL   = 300          # 5 minutes
CACHE_KEY   = "nv:buddy:ctx:{user_id}"


# ── Redis helpers ─────────────────────────────────────────────────────────────

def _redis():
    import redis as _r
    return _r.from_url(settings.REDIS_URL, decode_responses=True)


def invalidate_buddy_context(user_id: str) -> None:
    try:
        _redis().delete(CACHE_KEY.format(user_id=user_id))
    except Exception:
        pass


# ── Daily goal calculator (mirrors coaching router logic) ─────────────────────

def _calculate_daily_goals(user: User) -> dict:
    weight   = user.weight_kg or 65
    height   = user.height_cm or 165
    age      = 25
    if user.date_of_birth:
        age = max(14, (date.today() - user.date_of_birth).days // 365)

    gender   = user.gender or "female"
    activity = user.activity_level or "moderate"
    goal     = user.goal or "maintain"

    # Mifflin-St Jeor BMR
    if gender == "male":
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161

    multipliers = {"sedentary": 1.2, "light": 1.375, "moderate": 1.55, "active": 1.725, "very_active": 1.9}
    tdee = bmr * multipliers.get(activity, 1.55)

    if goal == "lose":
        calories = tdee - 400
    elif goal == "gain":
        calories = tdee + 300
    else:
        calories = tdee

    protein_g = weight * 1.6 if goal == "gain" else weight * 1.2
    fat_g     = calories * 0.25 / 9
    carbs_g   = (calories - protein_g * 4 - fat_g * 9) / 4
    fiber_g   = 25 if gender == "female" else 30

    # Cycle phase calorie adjustment
    adjustment = 0.0
    if gender == "female" and user.last_period_date:
        day_in_cycle = (date.today() - user.last_period_date).days % (user.cycle_length_days or 28)
        if day_in_cycle <= 5:
            adjustment = -0.05   # menstrual
        elif day_in_cycle <= 13:
            adjustment = 0.0     # follicular
        elif day_in_cycle <= 16:
            adjustment = 0.03    # ovulatory
        else:
            adjustment = 0.05    # luteal
        calories *= (1 + adjustment)

    return {
        "calories":  round(calories),
        "protein_g": round(protein_g),
        "fat_g":     round(fat_g),
        "carbs_g":   round(carbs_g),
        "fiber_g":   round(fiber_g),
    }


def _cycle_phase_label(user: User) -> str:
    if user.gender != "female" or not user.last_period_date:
        return ""
    day = (date.today() - user.last_period_date).days % (user.cycle_length_days or 28)
    if day <= 5:   return f"Menstrual (day {day})"
    if day <= 13:  return f"Follicular (day {day})"
    if day <= 16:  return f"Ovulatory (day {day})"
    return f"Luteal (day {day})"


# ── Context assembly ──────────────────────────────────────────────────────────

async def assemble_context(user: User, db: AsyncSession) -> str:
    """
    Returns a fully-formatted context string ready to be injected into the
    Claude system prompt. Cached in Redis for 5 minutes.
    """
    cache_key = CACHE_KEY.format(user_id=user.id)
    try:
        cached = _redis().get(cache_key)
        if cached:
            return cached
    except Exception:
        pass

    context = await _build_context(user, db)
    try:
        _redis().setex(cache_key, CACHE_TTL, context)
    except Exception:
        pass
    return context


async def _build_context(user: User, db: AsyncSession) -> str:
    goals      = _calculate_daily_goals(user)
    today_data = await _today_intake(user.id, db)
    recent     = await _recent_meals(user.id, db, days=3)
    trend      = await _weekly_trend(user.id, db)

    name       = user.full_name.split()[0] if user.full_name else "User"
    age        = ""
    if user.date_of_birth:
        age = str(max(14, (date.today() - user.date_of_birth).days // 365))

    conditions = ", ".join(user.health_conditions or []) or "None"
    cycle      = _cycle_phase_label(user)

    # --- Profile block ---
    lines = [
        "=== USER PROFILE ===",
        f"Name: {name}" + (f"  |  Age: {age}" if age else ""),
        f"Gender: {user.gender or 'not specified'}  |  Goal: {user.goal or 'not set'}  |  Activity: {user.activity_level or 'not set'}",
    ]
    if user.weight_kg:
        lines.append(f"Weight: {user.weight_kg}kg" + (f"  |  Height: {user.height_cm}cm" if user.height_cm else ""))
    if user.target_weight_kg:
        lines.append(f"Target weight: {user.target_weight_kg}kg")
    if cycle:
        lines.append(f"Cycle phase: {cycle}")
    lines.append(f"Health conditions: {conditions}")
    lines.append("")

    # --- Daily targets ---
    lines += [
        "=== DAILY TARGETS ===",
        f"Calories: {goals['calories']} kcal  |  Protein: {goals['protein_g']}g  |  Carbs: {goals['carbs_g']}g  |  Fat: {goals['fat_g']}g  |  Fiber: {goals['fiber_g']}g",
        "",
    ]

    # --- Today so far ---
    consumed = today_data["consumed"]
    remaining = {k: round(goals.get(k, 0) - consumed.get(k, 0), 1) for k in goals}
    pct_cal = round(consumed["calories"] / goals["calories"] * 100) if goals["calories"] else 0

    lines += [
        f"=== TODAY ({date.today().strftime('%b %d')}) ===",
        f"Consumed: {consumed['calories']} kcal ({pct_cal}% of target)  |  Protein: {consumed['protein_g']}g  |  Carbs: {consumed['carbs_g']}g  |  Fat: {consumed['fat_g']}g  |  Fiber: {consumed['fiber_g']}g",
        f"Remaining: Calories: {remaining['calories']} kcal  |  Protein: {remaining['protein_g']}g" + ("  ← LOW" if remaining["protein_g"] > goals["protein_g"] * 0.4 else ""),
        f"Meals logged today: {today_data['meal_count']}",
    ]
    if today_data["meal_summaries"]:
        for ms in today_data["meal_summaries"]:
            lines.append(f"  • {ms}")
    lines.append("")

    # --- Recent meals (last 3 days, excluding today) ---
    if recent:
        lines.append("=== RECENT MEALS (last 3 days) ===")
        for entry in recent:
            lines.append(f"  {entry}")
        lines.append("")

    # --- 7-day trend ---
    if trend:
        lines += [
            "=== 7-DAY TREND ===",
            f"Avg calories: {trend['avg_cal']}/{goals['calories']} kcal  |  Avg protein: {trend['avg_protein']}g/{goals['protein_g']}g",
            f"Days logged: {trend['days_logged']}/7  |  Best day: {trend['best_day']}",
        ]
        if trend["avg_protein"] < goals["protein_g"] * 0.8:
            lines.append("  ⚠ Protein consistently below target — flag this if user asks about goals.")
        lines.append("")

    return "\n".join(lines)


async def _today_intake(user_id: str, db: AsyncSession) -> dict:
    today = date.today()
    from sqlalchemy.orm import selectinload
    stmt = (
        select(Meal)
        .where(Meal.user_id == user_id, cast(Meal.eaten_at, Date) == today)
        .options(selectinload(Meal.food_items))
        .order_by(Meal.eaten_at)
    )
    result = await db.execute(stmt)
    meals = result.scalars().all()

    consumed = {"calories": 0.0, "protein_g": 0.0, "fat_g": 0.0, "carbs_g": 0.0, "fiber_g": 0.0}
    summaries = []
    for m in meals:
        consumed["calories"]  += m.total_calories  or 0
        consumed["protein_g"] += m.total_protein_g or 0
        consumed["fat_g"]     += m.total_fat_g     or 0
        consumed["carbs_g"]   += m.total_carbs_g   or 0
        consumed["fiber_g"]   += m.total_fiber_g   or 0
        labels = [fi.label for fi in (m.food_items or [])]
        time_str = m.eaten_at.strftime("%I:%M %p") if m.eaten_at else ""
        summaries.append(f"{time_str} — {', '.join(labels[:4])}{'…' if len(labels) > 4 else ''} ({round(m.total_calories or 0)} kcal)")

    return {
        "consumed":       {k: round(v, 1) for k, v in consumed.items()},
        "meal_count":     len(meals),
        "meal_summaries": summaries,
    }


async def _recent_meals(user_id: str, db: AsyncSession, days: int = 3) -> list[str]:
    since = date.today() - timedelta(days=days)
    today = date.today()
    from sqlalchemy.orm import selectinload
    stmt = (
        select(Meal)
        .where(Meal.user_id == user_id, cast(Meal.eaten_at, Date) >= since, cast(Meal.eaten_at, Date) < today)
        .options(selectinload(Meal.food_items))
        .order_by(Meal.eaten_at.desc())
        .limit(12)
    )
    result = await db.execute(stmt)
    meals = result.scalars().all()
    entries = []
    for m in meals:
        labels   = [fi.label for fi in (m.food_items or [])]
        day_str  = m.eaten_at.strftime("%b %d %I:%M %p") if m.eaten_at else ""
        entries.append(f"{day_str}: {', '.join(labels[:4])}{'…' if len(labels) > 4 else ''} ({round(m.total_calories or 0)} kcal, {round(m.total_protein_g or 0)}g protein)")
    return entries


async def _weekly_trend(user_id: str, db: AsyncSession) -> dict | None:
    since = date.today() - timedelta(days=7)
    stmt = (
        select(
            cast(Meal.eaten_at, Date).label("day"),
            func.sum(Meal.total_calories).label("cal"),
            func.sum(Meal.total_protein_g).label("protein"),
        )
        .where(Meal.user_id == user_id, cast(Meal.eaten_at, Date) >= since)
        .group_by("day")
    )
    result = await db.execute(stmt)
    rows = result.all()
    if not rows:
        return None

    cals    = [r.cal or 0 for r in rows]
    prots   = [r.protein or 0 for r in rows]
    best    = max(rows, key=lambda r: r.cal or 0)

    return {
        "days_logged":  len(rows),
        "avg_cal":      round(sum(cals) / len(cals)),
        "avg_protein":  round(sum(prots) / len(prots), 1),
        "best_day":     f"{best.day.strftime('%A')} ({round(best.cal or 0)} kcal)",
    }
