"""
Personalised fitness & lifestyle recommendations service.

Computes — without any LLM call — a full weekly workout plan,
daily step/water targets, supplement stack, and health tips
based on the user's goal, activity level, gender, and health conditions.
"""

from datetime import date
from typing import Optional, List


# ── Data structures ────────────────────────────────────────────────────────────

class Exercise:
    def __init__(self, name: str, sets: int, reps: str, rest_sec: int, note: str = ""):
        self.name     = name
        self.sets     = sets
        self.reps     = reps
        self.rest_sec = rest_sec
        self.note     = note

    def to_dict(self):
        d = {"name": self.name, "sets": self.sets, "reps": self.reps, "rest_sec": self.rest_sec}
        if self.note:
            d["note"] = self.note
        return d


class WorkoutDay:
    def __init__(
        self,
        day: str,
        workout_type: str,
        focus: str,
        exercises: List[Exercise],
        duration_mins: int,
        cardio_note: str = "",
    ):
        self.day          = day
        self.workout_type = workout_type
        self.focus        = focus
        self.exercises    = exercises
        self.duration_mins = duration_mins
        self.cardio_note  = cardio_note

    def to_dict(self):
        d = {
            "day":          self.day,
            "workout_type": self.workout_type,
            "focus":        self.focus,
            "exercises":    [e.to_dict() for e in self.exercises],
            "duration_mins": self.duration_mins,
        }
        if self.cardio_note:
            d["cardio_note"] = self.cardio_note
        return d


class Supplement:
    def __init__(self, name: str, reason: str, timing: str, priority: str, dose: str = ""):
        self.name     = name
        self.reason   = reason
        self.timing   = timing
        self.priority = priority   # "essential" | "recommended" | "optional"
        self.dose     = dose

    def to_dict(self):
        return {
            "name":     self.name,
            "reason":   self.reason,
            "timing":   self.timing,
            "priority": self.priority,
            "dose":     self.dose,
        }


# ── Exercise library ───────────────────────────────────────────────────────────

def _upper_push(level: str = "standard") -> List[Exercise]:
    if level == "beginner":
        return [
            Exercise("Push-ups",          3, "8-12",  60),
            Exercise("Incline Push-ups",  3, "10-15", 60, "Hands on a raised surface"),
            Exercise("Shoulder Taps",     3, "10/side", 45),
            Exercise("Tricep Dips",       3, "8-10",  60, "Use a sturdy chair"),
        ]
    return [
        Exercise("Push-ups",              3, "12-15", 60),
        Exercise("Dumbbell Chest Press",  4, "10-12", 75, "Or floor press"),
        Exercise("Dumbbell Shoulder Press", 3, "10-12", 60),
        Exercise("Lateral Raises",        3, "12-15", 45),
        Exercise("Tricep Overhead Extension", 3, "12",  60),
    ]


def _upper_pull(level: str = "standard") -> List[Exercise]:
    if level == "beginner":
        return [
            Exercise("Band / Towel Rows",  3, "10-12", 60, "Pull a towel around a door"),
            Exercise("Superman Hold",      3, "10",    45, "Lie face down, lift chest & legs"),
            Exercise("Bicep Curls",        3, "10-12", 60, "Use water bottles if no weights"),
            Exercise("Dead Bugs",          3, "8/side", 45),
        ]
    return [
        Exercise("Dumbbell Bent-Over Row", 4, "10-12", 75),
        Exercise("Pull-ups / Lat Pulldown", 3, "8-10",  90, "Assisted if needed"),
        Exercise("Face Pulls",             3, "15",    45, "Band or cable"),
        Exercise("Hammer Curls",           3, "12",    60),
        Exercise("Rear Delt Fly",          3, "12-15", 45),
    ]


def _lower_body(level: str = "standard", gender: str = "") -> List[Exercise]:
    glute_focus = gender == "female"
    if level == "beginner":
        return [
            Exercise("Bodyweight Squats",  3, "15",    45),
            Exercise("Reverse Lunges",     3, "10/leg", 45),
            Exercise("Glute Bridge",       3, "15",    45),
            Exercise("Calf Raises",        3, "20",    30),
            Exercise("Side-Lying Leg Raise", 3, "12/side", 30),
        ]
    base = [
        Exercise("Goblet Squat",           4, "12",    75, "Hold a dumbbell/kettlebell"),
        Exercise("Romanian Deadlift",      3, "10-12", 75),
        Exercise("Walking Lunges",         3, "12/leg", 60),
        Exercise("Calf Raises",            3, "20",    30),
    ]
    if glute_focus:
        base.insert(1, Exercise("Hip Thrust",  4, "12-15", 60, "Drive through heels, squeeze glutes"))
        base.insert(3, Exercise("Sumo Squat",  3, "15",    45))
    return base


def _hiit_circuit(level: str = "standard") -> List[Exercise]:
    if level == "beginner":
        return [
            Exercise("Jumping Jacks",      3, "30 sec", 30),
            Exercise("Bodyweight Squats",  3, "30 sec", 30),
            Exercise("High Knees (slow)",  3, "30 sec", 30),
            Exercise("Modified Push-ups",  3, "30 sec", 30),
            Exercise("March in Place",     3, "30 sec", 20),
        ]
    return [
        Exercise("Burpees",                4, "40 sec", 20),
        Exercise("Jump Squats",            4, "40 sec", 20),
        Exercise("Mountain Climbers",      4, "40 sec", 20),
        Exercise("High Knees",             4, "40 sec", 20),
        Exercise("Push-up to Shoulder Tap", 3, "40 sec", 25),
        Exercise("Jump Lunges",            3, "40 sec", 25),
    ]


def _core_session(level: str = "standard") -> List[Exercise]:
    if level == "beginner":
        return [
            Exercise("Plank",              3, "20-30 sec", 30),
            Exercise("Crunches",           3, "15",       30),
            Exercise("Bird Dog",           3, "8/side",   30),
            Exercise("Glute Bridge",       3, "15",       30),
        ]
    return [
        Exercise("Plank",                  3, "45-60 sec", 30),
        Exercise("Dead Bug",               3, "10/side",   30),
        Exercise("Russian Twists",         3, "15/side",   30, "Hold a weight"),
        Exercise("Hanging / Lying Leg Raise", 3, "12",    30),
        Exercise("Ab Wheel / Plank Rollout", 3, "10",     45),
    ]


def _cardio_day() -> List[Exercise]:
    return [
        Exercise("Brisk Walk or Jog",  1, "20-25 min", 0, "Moderate pace — you can hold a conversation"),
        Exercise("Jump Rope",          3, "90 sec",    60),
        Exercise("Cycling (stationary or outdoor)", 1, "15 min", 0, "Medium resistance"),
    ]


def _rest_day() -> List[Exercise]:
    return [
        Exercise("Foam Rolling / Stretching", 1, "10-15 min", 0, "Focus on sore areas"),
        Exercise("Leisurely Walk",            1, "20-30 min", 0, "Keep it easy"),
    ]


# ── Workout plan builders ──────────────────────────────────────────────────────

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _lose_plan(level: str, gender: str) -> List[WorkoutDay]:
    lvl = "beginner" if level == "sedentary" else "standard"
    return [
        WorkoutDay("Monday",    "HIIT",             "Full Body",          _hiit_circuit(lvl),         35, "5 min warm-up walk + 5 min cool-down"),
        WorkoutDay("Tuesday",   "Strength",          "Upper Body Push",    _upper_push(lvl),           40),
        WorkoutDay("Wednesday", "Cardio + Core",     "Endurance & Core",   _cardio_day() + _core_session(lvl), 40, "30 min cardio, then 15 min core"),
        WorkoutDay("Thursday",  "Strength",          "Lower Body",         _lower_body(lvl, gender),   45),
        WorkoutDay("Friday",    "HIIT",              "Full Body Burn",     _hiit_circuit(lvl),         35, "5 min warm-up + 5 min cool-down stretch"),
        WorkoutDay("Saturday",  "Active Recovery",  "Mobility & Walk",    _rest_day(),                30, "Light walk, yoga, or stretching — no intensity"),
        WorkoutDay("Sunday",    "Rest",              "Full Rest",          [],                          0,  "Complete rest. Sleep 7-9 hours."),
    ]


def _gain_plan(level: str, gender: str) -> List[WorkoutDay]:
    lvl = "beginner" if level == "sedentary" else "standard"
    return [
        WorkoutDay("Monday",    "Strength",  "Push — Chest, Shoulders, Triceps", _upper_push(lvl),         50),
        WorkoutDay("Tuesday",   "Strength",  "Pull — Back & Biceps",             _upper_pull(lvl),         50),
        WorkoutDay("Wednesday", "Strength",  "Lower Body & Glutes",              _lower_body(lvl, gender), 55),
        WorkoutDay("Thursday",  "Rest",      "Active Recovery",                  _rest_day(),               25, "Light walk + stretching"),
        WorkoutDay("Friday",    "Strength",  "Push — Volume Day",                _upper_push(lvl),         50),
        WorkoutDay("Saturday",  "Strength",  "Pull + Core",                      _upper_pull(lvl) + _core_session(lvl), 55),
        WorkoutDay("Sunday",    "Rest",      "Full Rest",                        [],                         0, "Complete rest. Sleep is when muscles grow."),
    ]


def _maintain_plan(level: str, gender: str) -> List[WorkoutDay]:
    lvl = "beginner" if level == "sedentary" else "standard"
    return [
        WorkoutDay("Monday",    "Strength",         "Full Body A",            _upper_push(lvl) + _lower_body(lvl, gender)[:3], 45),
        WorkoutDay("Tuesday",   "Cardio",           "Aerobic Endurance",      _cardio_day(),                                  35, "Keep heart rate at 60-70% max"),
        WorkoutDay("Wednesday", "Rest",             "Active Recovery",        _rest_day(),                                    20),
        WorkoutDay("Thursday",  "Strength",         "Full Body B",            _upper_pull(lvl) + _core_session(lvl),          45),
        WorkoutDay("Friday",    "HIIT / Cardio",    "Metabolic Conditioning", _hiit_circuit(lvl)[:4],                         30),
        WorkoutDay("Saturday",  "Active Recovery",  "Mobility & Flexibility", _rest_day(),                                    25, "Yoga or light stretching"),
        WorkoutDay("Sunday",    "Rest",             "Full Rest",              [],                                              0, "Complete rest."),
    ]


# ── Supplement builder ────────────────────────────────────────────────────────

def _base_supplements(goal: str) -> List[Supplement]:
    common = [
        Supplement("Multivitamin",  "Fills micronutrient gaps from food",           "Morning with breakfast", "essential",    "1 tablet/day"),
        Supplement("Omega-3 (Fish Oil)", "Reduces inflammation, supports heart & joints", "With a meal",      "essential",    "1-2 g EPA+DHA/day"),
        Supplement("Vitamin D3",    "Immune function, mood, bone health — most Indians are deficient", "Morning", "recommended", "1000-2000 IU/day"),
    ]
    if goal == "gain":
        return [
            Supplement("Whey Protein",  "Convenient source to hit daily protein target",  "Post-workout or before bed", "essential",    "1 scoop (25-30 g protein)"),
            Supplement("Creatine Monohydrate", "Proven to increase strength and muscle volume", "Any time with water",  "essential",    "5 g/day, no loading needed"),
            *common,
            Supplement("ZMA (Zinc + Magnesium)", "Improves sleep quality and testosterone levels", "Before bed on empty stomach", "optional", "As directed"),
        ]
    elif goal == "lose":
        return [
            *common,
            Supplement("Green Tea Extract", "Boosts metabolism and fat oxidation",       "Morning, before workout",    "recommended", "400-500 mg EGCG/day"),
            Supplement("Psyllium Husk",     "Increases fibre, improves satiety, reduces hunger", "Before meals with water", "recommended", "5 g in 250 ml water"),
            Supplement("L-Carnitine",       "Supports fat oxidation for energy",          "Before cardio on empty stomach", "optional", "1-2 g/day"),
        ]
    else:  # maintain
        return [
            *common,
            Supplement("Magnesium Glycinate", "Muscle recovery, sleep quality, reduces cramps", "Before bed",         "recommended", "200-400 mg/day"),
        ]


def _condition_supplements(conditions: List[str]) -> List[Supplement]:
    extras: List[Supplement] = []
    seen: set = set()

    mappings = {
        "diabetes": [
            Supplement("Berberine",  "Improves insulin sensitivity, lowers blood sugar naturally", "Before meals", "recommended", "500 mg 3x/day"),
            Supplement("Magnesium",  "Often depleted in diabetics; aids insulin signalling",       "With meals",   "recommended", "250-350 mg/day"),
        ],
        "pcod": [
            Supplement("Myo-Inositol", "Improves insulin sensitivity and hormonal balance in PCOS", "Morning on empty stomach", "essential", "2-4 g/day"),
            Supplement("Zinc",         "Reduces androgen excess, supports ovulation",              "With meals",   "recommended", "25-30 mg/day"),
        ],
        "hypothyroidism": [
            Supplement("Selenium",   "Supports thyroid hormone conversion (T4 → T3)",             "With meals",   "recommended", "100-200 mcg/day"),
            Supplement("Iodine",     "Essential for thyroid hormone synthesis",                   "With food",    "recommended", "150 mcg/day (check with doctor if on medication)"),
        ],
        "high_cholesterol": [
            Supplement("Plant Sterols", "Proven to reduce LDL cholesterol by 10-15%",            "With largest meal", "recommended", "2 g/day"),
            Supplement("Red Yeast Rice", "Natural statin-like effect on LDL",                    "With dinner",   "optional",    "1200 mg/day — consult doctor first"),
        ],
        "anemia": [
            Supplement("Iron (Ferrous Bisglycinate)", "Replenishes iron stores with fewer GI side effects", "Morning on empty stomach with Vitamin C", "essential", "As prescribed by doctor"),
            Supplement("Vitamin B12",  "Needed for red blood cell formation",                    "Morning",      "essential",   "500-1000 mcg/day"),
            Supplement("Vitamin C",    "Enhances non-haem iron absorption",                     "Alongside iron", "essential", "250-500 mg with iron dose"),
        ],
        "fatty_liver": [
            Supplement("Milk Thistle (Silymarin)", "Protects and helps regenerate liver cells",  "With meals",   "recommended", "150-300 mg/day"),
            Supplement("Choline",      "Essential for fat metabolism in the liver",              "With meals",   "recommended", "400-550 mg/day"),
        ],
        "ibs": [
            Supplement("Probiotics",   "Restores gut microbiome balance and reduces IBS symptoms", "Morning on empty stomach", "essential", "10-20 billion CFU/day"),
            Supplement("Peppermint Oil (enteric coated)", "Relieves IBS cramping and bloating", "Before meals", "recommended", "0.2-0.4 ml/cap, 3x/day"),
        ],
        "lactose_intolerance": [
            Supplement("Calcium + Vitamin D", "Replaces dairy-derived calcium",                 "With meals",   "essential",   "1000 mg Ca + 800 IU D3/day"),
        ],
        "gluten_sensitivity": [
            Supplement("Digestive Enzymes",  "Supports nutrient absorption in sensitive gut",   "With meals",   "recommended", "1-2 caps before meals"),
        ],
    }

    for c in conditions:
        for s in mappings.get(c, []):
            if s.name not in seen:
                seen.add(s.name)
                extras.append(s)

    return extras


# ── Main service ───────────────────────────────────────────────────────────────

class RecommendationsService:
    def generate(
        self,
        goal: Optional[str],
        activity_level: Optional[str],
        weight_kg: Optional[float],
        gender: Optional[str] = None,
        health_conditions: Optional[List[str]] = None,
    ) -> dict:
        g   = goal or "maintain"
        lvl = activity_level or "moderate"
        conditions = health_conditions or []

        # ── Workout plan ──────────────────────────────────────────────────────
        if g == "lose":
            plan = _lose_plan(lvl, gender or "")
        elif g == "gain":
            plan = _gain_plan(lvl, gender or "")
        else:
            plan = _maintain_plan(lvl, gender or "")

        # Reduce volume for active/very_active (they're already active outside)
        workout_days = [d for d in plan if d.workout_type != "Rest"]

        # ── Steps target ──────────────────────────────────────────────────────
        base_steps = {"lose": 10000, "maintain": 8000, "gain": 7000}
        daily_steps = base_steps.get(g, 8000)
        if lvl in ("active", "very_active"):
            daily_steps += 1000
        elif lvl == "sedentary":
            daily_steps -= 2000

        # Condition adjustments
        if "hypothyroidism" in conditions or "anemia" in conditions:
            daily_steps = min(daily_steps, 8000)

        # ── Water target ──────────────────────────────────────────────────────
        if weight_kg:
            water_ml = round(weight_kg * 33)
        else:
            water_ml = 2500
        if g == "gain" and weight_kg:
            water_ml += 300  # extra for protein metabolism
        water_glasses = round(water_ml / 250)

        # ── Supplements ──────────────────────────────────────────────────────
        supplements = _base_supplements(g) + _condition_supplements(conditions)

        # ── Lifestyle tips ────────────────────────────────────────────────────
        tips = self._lifestyle_tips(g, lvl, conditions, gender)

        # ── Weekly summary ────────────────────────────────────────────────────
        active_days = sum(1 for d in plan if d.workout_type not in ("Rest", "Active Recovery"))
        summary = self._weekly_summary(g, active_days, daily_steps)

        # ── Goal timeline ─────────────────────────────────────────────────────
        timeline = self._goal_timeline(g, weight_kg)

        return {
            "daily_steps":          daily_steps,
            "water_glasses":        water_glasses,
            "water_ml":             water_ml,
            "workout_plan":         [d.to_dict() for d in plan],
            "supplements":          [s.to_dict() for s in supplements],
            "lifestyle_tips":       tips,
            "weekly_workout_summary": summary,
            "goal_timeline_estimate": timeline,
        }

    @staticmethod
    def _lifestyle_tips(goal, level, conditions, gender) -> List[str]:
        tips = []

        if goal == "lose":
            tips += [
                "Eat your protein first at every meal — it reduces total calorie intake naturally.",
                "Walk after dinner for 15-20 min — blunts blood sugar spikes and burns extra calories.",
                "Avoid eating within 2 hours of bedtime to improve fat burning overnight.",
                "Replace liquid calories (juice, chai with sugar, sodas) with water or black coffee.",
            ]
        elif goal == "gain":
            tips += [
                "Eat within 30-45 minutes post-workout to maximise muscle protein synthesis.",
                "Never skip breakfast — your muscles need a constant amino acid supply.",
                "Sleep 7-9 hours every night — 70% of muscle repair happens during deep sleep.",
                "Progressive overload is king: add reps or weight every 1-2 weeks.",
            ]
        else:
            tips += [
                "Consistency beats perfection — 3 solid workouts per week beats sporadic intense sessions.",
                "Prioritise sleep (7-9 hours) — it regulates hunger hormones and energy levels.",
                "Track non-exercise movement (NEAT): take stairs, walk short distances.",
            ]

        if level == "sedentary":
            tips.insert(0, "Start slow: 2 workouts per week is better than 0. Build the habit before increasing intensity.")

        if gender == "female":
            tips.append("Strength train without fear of 'bulking' — it shapes and tones, and women lack the testosterone for large muscles.")

        if "diabetes" in conditions:
            tips.append("Check blood sugar before and after exercise; carry a fast carb source during workouts.")
        if "pcod" in conditions:
            tips.append("Consistent sleep timing (same bed/wake time daily) significantly improves hormonal regulation in PCOS.")
        if "hypertension" in conditions:
            tips.append("Avoid holding your breath during lifts (Valsalva manoeuvre) — it spikes blood pressure acutely.")
        if "hypothyroidism" in conditions:
            tips.append("Exercise in the morning when thyroid hormone levels and energy tend to be higher.")

        return tips[:6]

    @staticmethod
    def _weekly_summary(goal, active_days, steps) -> str:
        goal_str = {"lose": "fat loss", "gain": "muscle building", "maintain": "maintenance"}.get(goal, "your goal")
        return (
            f"Your plan includes {active_days} active training days per week, optimised for {goal_str}. "
            f"Target {steps:,} steps daily — this alone can account for 200-400 extra calories burned. "
            f"Stick to this plan for 8-12 weeks before evaluating results."
        )

    @staticmethod
    def _goal_timeline(goal, weight_kg) -> str:
        if goal == "lose":
            return "With a 400-600 kcal deficit and this training plan, expect 0.5-1 kg of fat loss per week. Results are visible in 4-6 weeks."
        elif goal == "gain":
            return "Natural muscle gain is 0.5-1 kg per month for women, 1-2 kg for men. Expect visible changes in 8-12 weeks with consistent training and nutrition."
        else:
            return "Maintenance is about sustaining your current composition while improving fitness. Strength gains will be visible within 4-6 weeks."
