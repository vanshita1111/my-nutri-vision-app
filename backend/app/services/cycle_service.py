"""
Menstrual cycle phase detection and phase-aware nutrition recommendations.
"""

from datetime import date, timedelta
from typing import Optional


PHASE_DATA = {
    "menstrual": {
        "days": (1, 5),
        "calorie_adjustment_pct": 0.0,
        "protein_target_g_per_kg": 1.6,
        "iron_target_mg": 18.0,
        "magnesium_target_mg": 320.0,
        "phase_notes": (
            "Iron loss is highest during menstruation. "
            "Focus on iron-rich foods to replenish stores. "
            "Magnesium helps reduce cramps and fatigue."
        ),
        "food_recommendations": [
            "Rajma / kidney beans — high iron + protein",
            "Spinach dal — iron + folate",
            "Dark chocolate (70%+) — magnesium",
            "Sesame seeds (til) — iron + calcium",
            "Beetroot — iron + folate",
            "Dates (khajur) — quick iron boost",
        ],
    },
    "follicular": {
        "days": (6, 13),
        "calorie_adjustment_pct": 0.0,
        "protein_target_g_per_kg": 1.6,
        "iron_target_mg": 18.0,
        "magnesium_target_mg": 280.0,
        "phase_notes": (
            "Estrogen is rising — energy levels increase and you recover from exercise faster. "
            "Good time to push training intensity. Higher carb tolerance."
        ),
        "food_recommendations": [
            "Brown rice — sustained energy",
            "Egg whites — lean protein for muscle repair",
            "Fruits (berries, mango) — antioxidants + carbs",
            "Quinoa — complete protein",
            "Curd / Greek yogurt — probiotics + protein",
        ],
    },
    "ovulatory": {
        "days": (14, 17),
        "calorie_adjustment_pct": 0.05,
        "protein_target_g_per_kg": 1.7,
        "iron_target_mg": 18.0,
        "magnesium_target_mg": 280.0,
        "phase_notes": (
            "Energy expenditure is highest. "
            "Anti-inflammatory foods support recovery. Libido and confidence peak."
        ),
        "food_recommendations": [
            "Salmon / flaxseeds — omega-3 anti-inflammatory",
            "Cruciferous veggies (broccoli, cauliflower) — estrogen metabolism",
            "Turmeric milk — anti-inflammatory",
            "Avocado — healthy fats",
            "Chicken / paneer — high protein for peak performance",
        ],
    },
    "luteal": {
        "days": (18, 28),
        "calorie_adjustment_pct": 0.1,
        "protein_target_g_per_kg": 1.8,
        "iron_target_mg": 18.0,
        "magnesium_target_mg": 360.0,
        "phase_notes": (
            "Progesterone drives cravings, bloating, and fatigue. "
            "Increase magnesium and B6 intake to reduce PMS symptoms. "
            "Higher calorie budget is physiologically justified — don't ignore hunger."
        ),
        "food_recommendations": [
            "Dark chocolate — magnesium + mood boost",
            "Banana — B6 + serotonin precursor",
            "Pumpkin seeds — zinc + magnesium",
            "Warm dal khichdi — comfort + balanced macros",
            "Chamomile / ashwagandha tea — cortisol reduction",
            "Sweet potato — complex carbs for craving management",
        ],
    },
}


class CycleService:
    def get_phase_info(
        self,
        last_period_date: Optional[date],
        cycle_length: int = 28,
        weight_kg: Optional[float] = None,
        goal: Optional[str] = None,
    ) -> dict:
        if last_period_date is None:
            return {
                "phase": "unknown",
                "day_in_cycle": 0,
                "calorie_adjustment_pct": 0.0,
                "protein_target_g": 50.0,
                "iron_target_mg": 18.0,
                "magnesium_target_mg": 280.0,
                "phase_notes": "Add your last period date in Settings to get cycle-aware nutrition.",
                "food_recommendations": [],
            }

        today = date.today()
        days_since = (today - last_period_date).days
        day_in_cycle = (days_since % cycle_length) + 1

        phase = self._get_phase(day_in_cycle, cycle_length)
        data = PHASE_DATA[phase]

        kg = weight_kg or 60.0
        protein_g = round(data["protein_target_g_per_kg"] * kg, 1)

        return {
            "phase": phase,
            "day_in_cycle": day_in_cycle,
            "calorie_adjustment_pct": data["calorie_adjustment_pct"],
            "protein_target_g": protein_g,
            "iron_target_mg": data["iron_target_mg"],
            "magnesium_target_mg": data["magnesium_target_mg"],
            "phase_notes": data["phase_notes"],
            "food_recommendations": data["food_recommendations"],
        }

    @staticmethod
    def _get_phase(day: int, cycle_length: int) -> str:
        # Scale phases proportionally to user's cycle length
        scale = cycle_length / 28
        if day <= round(5 * scale):
            return "menstrual"
        elif day <= round(13 * scale):
            return "follicular"
        elif day <= round(17 * scale):
            return "ovulatory"
        else:
            return "luteal"
