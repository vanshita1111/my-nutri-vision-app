"""
Personalised daily nutrition goals (TDEE + macro split + cycle adjustment).
Factors in health conditions for adjusted macro targets and nutrition tips.
"""

from datetime import date
from typing import Optional, List


ACTIVITY_MULTIPLIERS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}

# Per-condition: (protein_pct, fat_pct, carbs_pct, fiber_g, tips)
CONDITION_PROFILES = {
    "diabetes": {
        "carbs_pct": 0.30, "protein_pct": 0.30, "fat_pct": 0.40,
        "fiber_g": 35,
        "tips": [
            "Choose low-GI carbs: oats, legumes, and non-starchy vegetables.",
            "Distribute carbs evenly across meals to avoid blood-sugar spikes.",
            "Limit refined sugar and sugary drinks entirely.",
        ],
    },
    "pcod": {
        "carbs_pct": 0.30, "protein_pct": 0.35, "fat_pct": 0.35,
        "fiber_g": 30,
        "tips": [
            "Prioritise anti-inflammatory foods: berries, leafy greens, fatty fish.",
            "Eat high-protein meals to improve insulin sensitivity.",
            "Limit processed carbs and sugar to reduce androgen levels.",
        ],
    },
    "hypertension": {
        "carbs_pct": 0.40, "protein_pct": 0.30, "fat_pct": 0.30,
        "fiber_g": 30,
        "tips": [
            "Limit sodium to under 1500 mg/day — avoid processed and packaged foods.",
            "Include potassium-rich foods: bananas, spinach, sweet potato.",
            "Favour unsaturated fats (olive oil, avocado) over saturated fats.",
        ],
    },
    "hypothyroidism": {
        "carbs_pct": 0.40, "protein_pct": 0.30, "fat_pct": 0.30,
        "fiber_g": 25,
        "tips": [
            "Include iodine-rich foods: dairy, eggs, and seaweed.",
            "Eat cooked cruciferous vegetables rather than raw to reduce goitrogens.",
            "Ensure adequate selenium intake: Brazil nuts, sunflower seeds.",
        ],
    },
    "high_cholesterol": {
        "carbs_pct": 0.45, "protein_pct": 0.30, "fat_pct": 0.25,
        "fiber_g": 35,
        "tips": [
            "Eat soluble fibre daily: oats, flaxseed, apples — binds cholesterol.",
            "Replace saturated fats with omega-3 sources: walnuts, flaxseed, salmon.",
            "Avoid trans fats (hydrogenated oils) found in fried and packaged snacks.",
        ],
    },
    "anemia": {
        "carbs_pct": 0.45, "protein_pct": 0.30, "fat_pct": 0.25,
        "fiber_g": 25,
        "tips": [
            "Pair iron-rich foods (spinach, lentils, red meat) with vitamin C sources.",
            "Avoid tea or coffee with meals — they inhibit iron absorption.",
            "Include vitamin B12 sources: eggs, dairy, or fortified foods if vegetarian.",
        ],
    },
    "fatty_liver": {
        "carbs_pct": 0.35, "protein_pct": 0.30, "fat_pct": 0.35,
        "fiber_g": 30,
        "tips": [
            "Avoid alcohol and fructose-sweetened drinks entirely.",
            "Eat antioxidant-rich foods: green tea, turmeric, cruciferous vegetables.",
            "Choose healthy fats: olive oil and avocado over butter or ghee.",
        ],
    },
    "ibs": {
        "carbs_pct": 0.45, "protein_pct": 0.25, "fat_pct": 0.30,
        "fiber_g": 20,
        "tips": [
            "Follow a low-FODMAP approach: avoid onion, garlic, wheat, and high-lactose dairy.",
            "Eat smaller, more frequent meals to reduce gut stress.",
            "Keep a food diary to identify personal trigger foods.",
        ],
    },
    "lactose_intolerance": {
        "carbs_pct": 0.45, "protein_pct": 0.30, "fat_pct": 0.25,
        "fiber_g": 25,
        "tips": [
            "Replace dairy with calcium-fortified plant milks (almond, soy, oat).",
            "Include non-dairy calcium: tofu, sesame seeds, broccoli, ragi.",
            "Try aged cheeses or yogurt — lower in lactose and often tolerated.",
        ],
    },
    "gluten_sensitivity": {
        "carbs_pct": 0.45, "protein_pct": 0.30, "fat_pct": 0.25,
        "fiber_g": 25,
        "tips": [
            "Choose naturally gluten-free grains: rice, quinoa, millet, buckwheat.",
            "Always read labels — gluten hides in sauces, soups, and processed foods.",
            "Focus on whole foods to minimise cross-contamination risk.",
        ],
    },
}


class GoalsService:
    def calculate(
        self,
        weight_kg: Optional[float],
        height_cm: Optional[float],
        date_of_birth: Optional[date],
        activity_level: Optional[str],
        goal: Optional[str],
        gender: Optional[str] = None,
        target_weight_kg: Optional[float] = None,
        health_conditions: Optional[List[str]] = None,
        last_period_date: Optional[date] = None,
        cycle_length: int = 28,
    ) -> dict:
        if not weight_kg or not height_cm:
            return {**self._default_goals(), "setup_required": True, "condition_tips": []}

        age = self._calc_age(date_of_birth) if date_of_birth else 30
        bmr = self._bmr(weight_kg, height_cm, age, gender)
        activity_mult = ACTIVITY_MULTIPLIERS.get(activity_level or "moderate", 1.55)
        tdee = bmr * activity_mult

        goal_adj = self._goal_adjustment(goal, weight_kg, target_weight_kg)
        calorie_goal = tdee + goal_adj

        # Cycle adjustment (female only)
        cycle_adj = 0.0
        if last_period_date and gender != "male":
            from app.services.cycle_service import CycleService
            phase_info = CycleService().get_phase_info(last_period_date, cycle_length, weight_kg, goal)
            cycle_adj = calorie_goal * phase_info["calorie_adjustment_pct"]

        final_calories = round(calorie_goal + cycle_adj)

        # Macro split — condition-adjusted if applicable
        protein_pct, fat_pct, carbs_pct, fiber_g = self._macro_split(health_conditions)
        protein_g = round((final_calories * protein_pct) / 4)
        fat_g     = round((final_calories * fat_pct) / 9)
        carbs_g   = round((final_calories * carbs_pct) / 4)

        # Collect condition-specific tips (up to 3 per condition, deduplicated)
        condition_tips = self._collect_tips(health_conditions)

        return {
            "daily_calorie_goal": final_calories,
            "protein_g": protein_g,
            "fat_g": fat_g,
            "carbs_g": carbs_g,
            "fiber_g": fiber_g,
            "water_ml": round(weight_kg * 35),
            "bmr": round(bmr),
            "tdee": round(tdee),
            "cycle_calorie_adjustment": round(cycle_adj),
            "setup_required": False,
            "condition_tips": condition_tips,
        }

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _bmr(weight_kg: float, height_cm: float, age: int, gender: Optional[str]) -> float:
        base = (10 * weight_kg) + (6.25 * height_cm) - (5 * age)
        return base + 5 if gender == "male" else base - 161

    @staticmethod
    def _goal_adjustment(goal: Optional[str], weight_kg: float, target_weight_kg: Optional[float]) -> float:
        if not goal or goal == "maintain":
            return 0

        if target_weight_kg and weight_kg:
            gap = abs(weight_kg - target_weight_kg)
            if goal == "lose":
                return -200 if gap <= 3 else -400 if gap <= 7 else -600
            elif goal == "gain":
                return 150 if gap <= 3 else 300 if gap <= 7 else 450

        return -500 if goal == "lose" else 300

    @staticmethod
    def _macro_split(conditions: Optional[List[str]]) -> tuple[float, float, float, int]:
        """Return (protein_pct, fat_pct, carbs_pct, fiber_g) adjusted for conditions."""
        if not conditions:
            return 0.30, 0.30, 0.40, 25

        # Average across all active condition profiles
        active = [CONDITION_PROFILES[c] for c in conditions if c in CONDITION_PROFILES]
        if not active:
            return 0.30, 0.30, 0.40, 25

        p = sum(a["protein_pct"] for a in active) / len(active)
        f = sum(a["fat_pct"]     for a in active) / len(active)
        c = sum(a["carbs_pct"]   for a in active) / len(active)
        fiber = max(a["fiber_g"] for a in active)

        # Normalise to sum to 1.0
        total = p + f + c
        return round(p / total, 3), round(f / total, 3), round(c / total, 3), fiber

    @staticmethod
    def _collect_tips(conditions: Optional[List[str]]) -> List[str]:
        seen: set[str] = set()
        tips: List[str] = []
        for c in (conditions or []):
            profile = CONDITION_PROFILES.get(c)
            if profile:
                for tip in profile["tips"]:
                    if tip not in seen:
                        seen.add(tip)
                        tips.append(tip)
        return tips

    @staticmethod
    def _calc_age(dob: date) -> int:
        today = date.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    @staticmethod
    def _default_goals() -> dict:
        return {
            "daily_calorie_goal": 2000,
            "protein_g": 150,
            "fat_g": 67,
            "carbs_g": 200,
            "fiber_g": 25,
            "water_ml": 2500,
            "bmr": None,
            "tdee": None,
            "cycle_calorie_adjustment": 0,
        }
