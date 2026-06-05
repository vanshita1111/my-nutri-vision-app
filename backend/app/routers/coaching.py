"""
Coaching endpoints — personalised nutrition advice powered by Claude.

GET /coaching/weekly-summary
    Looks at the last 7 days of meals and returns:
      - A plain-language summary of eating patterns
      - 3 actionable tips tailored to the user's goals and cycle phase
      - Average daily calories and logged-day streak

Results are cached in Redis for 12 hours per user to avoid repeated LLM calls.
"""

import json
import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.models.meal import Meal

log = logging.getLogger(__name__)
router = APIRouter()

CACHE_TTL = 60 * 60 * 12  # 12 hours
CACHE_PREFIX = "nv:coaching:weekly:"


# ── Response schema ────────────────────────────────────────────────────────────

from pydantic import BaseModel
from typing import Optional

class WeeklySummaryResponse(BaseModel):
    summary:       str
    tips:          list[str]
    avg_calories:  float
    streak_days:   int
    cycle_phase:   Optional[str] = None


# ── Redis helper ───────────────────────────────────────────────────────────────

def _get_redis():
    import redis as _redis
    return _redis.from_url(settings.REDIS_URL, decode_responses=True)


def _cache_get(user_id: str) -> Optional[dict]:
    try:
        raw = _get_redis().get(f"{CACHE_PREFIX}{user_id}")
        return json.loads(raw) if raw else None
    except Exception as exc:
        log.debug("Cache read failed: %s", exc)
        return None


def _cache_set(user_id: str, data: dict) -> None:
    try:
        _get_redis().setex(f"{CACHE_PREFIX}{user_id}", CACHE_TTL, json.dumps(data))
    except Exception as exc:
        log.debug("Cache write failed: %s", exc)


# ── Endpoint ───────────────────────────────────────────────────────────────────

@router.get("/coaching/recommendations")
async def get_recommendations(current_user: User = Depends(get_current_user)):
    """
    Return personalised workout plan, daily steps, water target,
    supplement stack, and lifestyle tips based on the user's profile.
    """
    from app.services.recommendations_service import RecommendationsService
    return RecommendationsService().generate(
        goal=current_user.goal,
        activity_level=current_user.activity_level,
        weight_kg=current_user.weight_kg,
        gender=current_user.gender,
        health_conditions=current_user.health_conditions or [],
    )


@router.get("/coaching/weekly-summary", response_model=WeeklySummaryResponse)
async def weekly_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # ── Return cached result if fresh ─────────────────────────────────────────
    cached = _cache_get(str(current_user.id))
    if cached:
        return WeeklySummaryResponse(**cached)

    # ── Fetch last 7 days of meals ─────────────────────────────────────────────
    today    = date.today()
    week_ago = today - timedelta(days=7)

    stmt = (
        select(Meal)
        .where(
            Meal.user_id == str(current_user.id),
            Meal.eaten_at >= week_ago,
        )
        .order_by(Meal.eaten_at.asc())
    )
    result = await db.execute(stmt)
    meals  = result.scalars().all()

    # ── Compute stats ──────────────────────────────────────────────────────────
    avg_calories = 0.0
    streak_days  = 0

    if meals:
        total_cal    = sum(m.total_calories or 0 for m in meals)
        logged_dates = {m.eaten_at.date() for m in meals}
        avg_calories = round(total_cal / max(len(logged_dates), 1), 1)

        check = today
        while check in logged_dates:
            streak_days += 1
            check -= timedelta(days=1)

    # ── Get cycle phase ────────────────────────────────────────────────────────
    cycle_phase = None
    try:
        from app.services.cycle_service import CycleService
        if current_user.last_period_date and current_user.gender != "male":
            phase_info  = CycleService().get_phase_info(
                current_user.last_period_date,
                current_user.cycle_length_days or 28,
            )
            cycle_phase = phase_info.get("phase")
    except Exception:
        pass

    # ── Build prompt and call Claude ───────────────────────────────────────────
    meals_summary = _format_meals_for_prompt(meals)
    prompt = _build_prompt(
        user=current_user,
        meals_summary=meals_summary,
        avg_calories=avg_calories,
        streak_days=streak_days,
        cycle_phase=cycle_phase,
    )

    summary_text, tips = await _call_claude(prompt)

    response_data = {
        "summary":      summary_text,
        "tips":         tips,
        "avg_calories": avg_calories,
        "streak_days":  streak_days,
        "cycle_phase":  cycle_phase,
    }

    _cache_set(str(current_user.id), response_data)

    return WeeklySummaryResponse(**response_data)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _format_meals_for_prompt(meals) -> str:
    if not meals:
        return "No meals logged in the past 7 days."

    lines = []
    for m in meals:
        cal  = m.total_calories  or 0
        prot = m.total_protein_g or 0
        carb = m.total_carbs_g   or 0
        fat  = m.total_fat_g     or 0
        day  = m.eaten_at.strftime("%A") if m.eaten_at else "Unknown day"
        lines.append(f"- {day}: {cal:.0f} kcal (P:{prot:.0f}g  C:{carb:.0f}g  F:{fat:.0f}g)")

    return "\n".join(lines)


def _build_prompt(
    user: User,
    meals_summary: str,
    avg_calories: float,
    streak_days: int,
    cycle_phase: str | None,
) -> str:
    goal_map = {
        "lose":     "lose weight",
        "maintain": "maintain current weight",
        "gain":     "gain muscle",
    }
    goal_str  = goal_map.get(user.goal or "maintain", "maintain weight")
    cycle_str = (
        f"She is currently in the {cycle_phase} phase of her menstrual cycle."
        if cycle_phase else ""
    )

    return f"""You are a warm, evidence-based nutrition coach. A user has asked for their weekly nutrition summary.

USER PROFILE:
- Goal: {goal_str}
- Activity level: {user.activity_level or "not specified"}
- Logging streak: {streak_days} consecutive days
- Average daily calories this week: {avg_calories:.0f} kcal
{cycle_str}

MEALS LOGGED THIS WEEK:
{meals_summary}

Please respond with a JSON object with exactly these two keys:
{{
  "summary": "<2-3 sentence plain-language summary of their week — patterns, what went well, what to watch>",
  "tips": ["<tip 1>", "<tip 2>", "<tip 3>"]
}}

Guidelines:
- Be encouraging and specific (mention actual numbers when helpful)
- Tips must be concrete and actionable, not generic
- If cycle phase is provided, include 1 cycle-specific tip
- Keep the summary under 80 words
- Return ONLY the JSON, no preamble"""


async def _call_claude(prompt: str) -> tuple[str, list[str]]:
    import os

    try:
        import anthropic

        api_key = settings.ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        client  = anthropic.AsyncAnthropic(api_key=api_key)
        message = await client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)

        summary = data.get("summary", "Great work logging your meals this week!")
        tips    = data.get("tips", [])
        if not isinstance(tips, list):
            tips = [str(tips)]
        return summary, tips[:3]

    except Exception as exc:
        log.warning("Claude coaching call failed: %s — returning fallback response", exc)
        return _fallback_summary(), _fallback_tips()


def _fallback_summary() -> str:
    return (
        "You've been making great progress tracking your meals! "
        "Consistent logging is the first step to reaching your nutrition goals. "
        "Keep it up — every meal logged is data that helps you improve."
    )


def _fallback_tips() -> list[str]:
    return [
        "Aim to include a source of protein in every meal to stay fuller longer.",
        "Try to eat at least 5 different vegetables this week for a wider range of micronutrients.",
        "Drinking water before meals can help with portion control and digestion.",
    ]
