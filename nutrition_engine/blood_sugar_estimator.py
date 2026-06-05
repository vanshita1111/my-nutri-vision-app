"""
Blood Sugar Impact Estimator
=============================
Produces educational estimates of a meal's potential glycaemic effect.

Algorithm
---------
1. Estimate Glycaemic Index (GI) for each food item via tiered lookup.
2. Compute Glycaemic Load (GL): GL = (GI × net_carbs_g) / 100
3. Apply three meal-level buffers that research shows flatten the
   post-prandial glucose curve:
     • Fiber  buffer  — slows absorption (max 50 % GL reduction)
     • Protein buffer — blunts peak via incretin/insulin response (max 25 %)
     • Fat buffer     — delays gastric emptying (max 20 %)
4. Normalise to a 0–100 score where GL ≈ 30 maps to score 100.
5. Classify: Low (< 34) / Moderate (34–67) / High (> 67).

Scientific references
---------------------
• Jenkins et al. (1981) Glycaemic index of foods — Am J Clin Nutr
• Brand-Miller et al. (2003) Glycaemic index, glycaemic load — Diabetes Care
• Atkinson et al. (2008) International GI tables — Diabetes Care
• IFCT 2017 — Indian Food Composition Tables

Disclaimer
----------
These are statistical estimates, NOT medical advice.
Individual glucose responses vary based on genetics, gut microbiome,
cooking method, ripeness, food combinations, and metabolic health.
"""

from __future__ import annotations
import re
from typing import Any

# ---------------------------------------------------------------------------
# GI Reference Table (values per 100 g, glucose = 100 reference)
# Primary sources: IFCT 2017, Brand-Miller/Atkinson international tables
# ---------------------------------------------------------------------------

_GI_TABLE: dict[str, float] = {
    # ── Rice & grains ───────────────────────────────────────────────────────
    "white rice": 73,      "steamed rice": 73,    "boiled rice": 73,
    "basmati rice": 58,    "brown rice": 68,       "red rice": 55,
    "biryani": 58,         "pulao": 60,            "fried rice": 65,
    "khichdi": 50,
    # ── Wheat / flatbreads ──────────────────────────────────────────────────
    "chapati": 62,         "roti": 62,             "whole wheat roti": 55,
    "paratha": 55,         "aloo paratha": 62,     "naan": 71,
    "puri": 65,            "bhatura": 68,           "white bread": 75,
    "whole wheat bread": 69, "bread": 73,
    # ── South Indian ────────────────────────────────────────────────────────
    "idli": 70,            "dosa": 55,             "uttapam": 55,
    "upma": 44,            "poha": 55,             "pongal": 52,
    "vada": 60,            "appam": 60,
    # ── Pasta / noodles ─────────────────────────────────────────────────────
    "pasta": 49,           "noodles": 52,          "macaroni": 47,
    "spaghetti": 46,
    # ── Legumes & dals (low GI) ─────────────────────────────────────────────
    "dal": 29,             "daal": 29,             "lentil": 29,
    "dal makhani": 25,     "dal tadka": 29,        "moong dal": 38,
    "toor dal": 29,        "masoor dal": 31,       "chana dal": 22,
    "urad dal": 43,
    "rajma": 24,           "kidney bean": 24,      "red kidney bean": 24,
    "chickpea": 28,        "chole": 28,            "chana": 28,
    "black chana": 25,
    "sambhar": 40,         "rasam": 30,
    "soybean": 15,         "edamame": 18,
    "peas": 48,            "green peas": 48,       "pea": 48,
    # ── Vegetables ──────────────────────────────────────────────────────────
    "potato": 78,          "aloo": 78,             "boiled potato": 78,
    "sweet potato": 63,    "shakarkandi": 63,
    "yam": 37,             "arbi": 50,
    "carrot": 39,          "gajar": 39,
    "beetroot": 64,        "beet": 64,
    "corn": 60,            "maize": 60,            "sweet corn": 60,
    "pumpkin": 75,         "kaddu": 75,
    "spinach": 15,         "palak": 15,
    "broccoli": 15,        "cauliflower": 15,      "gobi": 15,
    "cabbage": 10,         "patta gobi": 10,
    "tomato": 15,          "tamatar": 15,
    "onion": 10,           "pyaz": 10,
    "mushroom": 10,
    "eggplant": 15,        "baingan": 15,
    "lady finger": 20,     "okra": 20,             "bhindi": 20,
    "bitter gourd": 20,    "karela": 20,
    "bottle gourd": 15,    "lauki": 15,
    "ridge gourd": 15,
    "vegetable": 30,       "sabzi": 30,            "curry": 45,
    "mixed vegetable": 30, "veg": 30,
    "salad": 15,           "raita": 36,
    # ── Proteins (negligible GI) ─────────────────────────────────────────────
    "chicken": 0,          "chicken curry": 5,     "butter chicken": 8,
    "chicken tikka": 3,    "tandoori chicken": 2,
    "mutton": 0,           "lamb": 0,              "mutton curry": 5,
    "fish": 0,             "fish curry": 5,        "prawn": 0,
    "egg": 0,              "boiled egg": 0,        "fried egg": 0,
    "egg curry": 3,        "omelette": 2,
    "paneer": 27,          "paneer tikka": 25,     "palak paneer": 22,
    "paneer butter masala": 25,
    "tofu": 15,
    # ── Dairy ───────────────────────────────────────────────────────────────
    "milk": 31,            "doodh": 31,
    "curd": 36,            "yogurt": 36,           "dahi": 36,
    "lassi": 45,
    "ghee": 0,             "butter": 0,            "cream": 5,
    "cheese": 0,
    # ── Fruits ──────────────────────────────────────────────────────────────
    "apple": 36,           "orange": 43,           "banana": 51,
    "mango": 56,           "aam": 56,
    "grapes": 59,          "watermelon": 76,
    "papaya": 58,          "pear": 38,
    "guava": 31,           "amrood": 31,
    "pomegranate": 35,     "anar": 35,
    "strawberry": 40,
    # ── Snacks ──────────────────────────────────────────────────────────────
    "samosa": 55,          "pakora": 52,           "pakoda": 52,
    "bhujia": 62,          "chips": 56,            "mathri": 58,
    "biscuit": 59,         "cookie": 57,
    # ── Sweets / desserts (high GI) ──────────────────────────────────────────
    "sugar": 65,           "jaggery": 84,          "honey": 58,
    "gulab jamun": 75,     "jalebi": 82,
    "halwa": 70,           "kheer": 65,            "payasam": 65,
    "mithai": 70,          "ladoo": 72,            "barfi": 70,
    "ice cream": 57,
    # ── Cereals / breakfast ──────────────────────────────────────────────────
    "oats": 55,            "oatmeal": 55,          "porridge": 58,
    "cornflakes": 81,      "muesli": 57,
}

_DEFAULT_GI: float = 60.0  # conservative default for unrecognised items


# ---------------------------------------------------------------------------
# Explanations & recommendations
# ---------------------------------------------------------------------------

_DISCLAIMER = (
    "⚠️ Educational estimate only — not medical advice. Individual glucose "
    "responses vary based on personal metabolism, cooking method, portion size, "
    "and health conditions. People with diabetes or insulin resistance should "
    "consult a registered dietitian or physician."
)

_LEVEL_EXPLANATIONS: dict[str, str] = {
    "low": (
        "This meal is estimated to have a low glycaemic impact. "
        "It is rich in fibre, protein, or healthy fats that help maintain "
        "steady blood sugar levels after eating."
    ),
    "moderate": (
        "This meal may cause a moderate glucose response. "
        "It contains a mix of carbohydrates and buffers (fibre/protein/fat) "
        "that partially slow sugar absorption."
    ),
    "high": (
        "This meal may cause a higher glucose response, primarily due to "
        "rapidly absorbed carbohydrates with limited fibre or protein buffering. "
        "Portion size and eating speed can significantly affect the actual impact."
    ),
}


def _get_recommendations(
    level: str,
    fiber_g: float,
    protein_g: float,
    net_carbs: float,
    high_gi_items: list[str],
    has_diabetes_condition: bool = False,
) -> list[str]:
    recs: list[str] = []

    if level in ("moderate", "high"):
        fiber_ratio = fiber_g / max(1.0, net_carbs)
        if fiber_ratio < 0.15:
            recs.append(
                "Adding fibre-rich foods (vegetables, dal, whole grains) "
                "may reduce the estimated glucose impact."
            )
        protein_ratio = protein_g / max(1.0, net_carbs)
        if protein_ratio < 0.3:
            recs.append(
                "Including more protein (dal, paneer, eggs, legumes) "
                "can buffer the glucose rise."
            )
        if high_gi_items:
            item_str = " and ".join(high_gi_items[:2])
            recs.append(
                f"Consider smaller portions of {item_str}, "
                f"or swap for a lower-GI alternative (e.g., brown rice instead "
                f"of white rice, whole-wheat roti instead of maida)."
            )

    if level == "low":
        recs.append(
            "Great balance! The fibre and protein in this meal support "
            "steady energy without a sharp glucose spike."
        )
        if fiber_g >= 8:
            recs.append(
                "The high fibre content is especially helpful for sustained "
                "satiety and gut health."
            )

    if has_diabetes_condition and level != "low":
        recs.append(
            "As you have a metabolic health condition in your profile, "
            "consider monitoring your personal response to this meal and "
            "discussing meal timing with your healthcare provider."
        )

    # Always cap at 3 recommendations for readability
    return recs[:3]


# ---------------------------------------------------------------------------
# GI lookup
# ---------------------------------------------------------------------------

def _estimate_gi(food_label: str) -> float:
    """
    Return an estimated GI for a food label via tiered matching.
    """
    label = food_label.lower().strip()

    # 1. Exact match
    if label in _GI_TABLE:
        return _GI_TABLE[label]

    # 2. Longest substring match (label contains key, or key contains label)
    best_key: str | None = None
    best_len = 0
    for key in _GI_TABLE:
        if key in label or label in key:
            if len(key) > best_len:
                best_key = key
                best_len = len(key)
    if best_key is not None:
        return _GI_TABLE[best_key]

    # 3. Category regex fallback
    patterns: list[tuple[str, float]] = [
        (r"rice|biryani|pulao|pilaf",                     70.0),
        (r"roti|chapati|paratha|naan|bread|puri|bhatura",  65.0),
        (r"dal|daal|lentil|bean|legume|rajma|chole",       30.0),
        (r"chicken|mutton|lamb|fish|prawn|seafood|meat",    5.0),
        (r"egg",                                            2.0),
        (r"paneer|tofu|soy",                               20.0),
        (r"potato|aloo",                                   78.0),
        (r"vegetable|sabzi|veg|salad|greens",              25.0),
        (r"sweet|halwa|ladoo|mithai|dessert|jalebi",       72.0),
        (r"fruit|apple|banana|mango|orange",               50.0),
        (r"oat|cereal|porridge",                           55.0),
    ]
    for pattern, gi in patterns:
        if re.search(pattern, label):
            return gi

    return _DEFAULT_GI


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------

def estimate_blood_sugar_impact(
    items: list[dict[str, Any]],
    total: dict[str, Any],
    health_conditions: list[str] | None = None,
) -> dict[str, Any]:
    """
    Estimate blood sugar impact from a list of food items and macro totals.

    Parameters
    ----------
    items : list[dict]
        Food items from the pipeline result.
        Each dict must contain: label, grams, nutrition (calories/protein_g/
        fat_g/carbs_g/fiber_g), is_hidden_ingredient.
    total : dict
        Aggregated macro totals for the meal (same nutrition keys).
    health_conditions : list[str] | None
        User health conditions from profile (for personalised recommendations).

    Returns
    -------
    dict with keys: score, level, glycemic_load, carb_density,
    fiber_impact, protein_buffer, fat_buffer, explanation,
    recommendations, disclaimer, per_item_gi
    """
    health_conditions = health_conditions or []
    has_diabetes = any(
        c in ("diabetes", "prediabetes", "type_2_diabetes", "type_1_diabetes")
        for c in health_conditions
    )

    # ── Gather visible (non-hidden) items ──────────────────────────────────
    visible = [it for it in items if not it.get("is_hidden_ingredient")]

    total_weight_g = sum(it.get("grams", 0) for it in visible)

    # ── Per-item GL ────────────────────────────────────────────────────────
    per_item_gi: dict[str, float] = {}
    item_gls: list[float] = []
    high_gi_items: list[str] = []

    for item in visible:
        label = item.get("label", "unknown")
        n = item.get("nutrition", {})
        carbs = n.get("carbs_g", 0) or 0.0
        fiber = n.get("fiber_g", 0) or 0.0
        net = max(0.0, carbs - fiber)

        gi = _estimate_gi(label)
        per_item_gi[label] = gi
        gl = (gi * net) / 100.0
        item_gls.append(gl)

        if gi >= 65 and net > 5:
            high_gi_items.append(label)

    total_raw_gl = sum(item_gls)

    # ── Meal-level macros ──────────────────────────────────────────────────
    t_carbs   = float(total.get("carbs_g",   0) or 0)
    t_fiber   = float(total.get("fiber_g",   0) or 0)
    t_protein = float(total.get("protein_g", 0) or 0)
    t_fat     = float(total.get("fat_g",     0) or 0)
    t_net_carbs = max(0.01, t_carbs - t_fiber)

    # ── Buffer calculations ────────────────────────────────────────────────
    # Fiber: every gram of fiber buffers ~1.5× its weight in net carbs
    fiber_ratio  = t_fiber / t_net_carbs
    fiber_buffer = min(0.50, fiber_ratio * 1.5)

    # Protein: up to 25 % reduction at high protein:carb ratio
    protein_ratio  = t_protein / t_net_carbs
    protein_buffer = min(0.25, protein_ratio * 0.30)

    # Fat: up to 20 % reduction (slows gastric emptying)
    fat_ratio  = t_fat / t_net_carbs
    fat_buffer = min(0.20, fat_ratio * 0.25)

    # ── Adjusted GL and final score ────────────────────────────────────────
    adjusted_gl = (
        total_raw_gl
        * (1 - fiber_buffer)
        * (1 - protein_buffer)
        * (1 - fat_buffer)
    )

    # Normalise: GL=30 → score=100; GL=10 → score≈33; GL=0 → score=0
    score = max(0, min(100, round((adjusted_gl / 30.0) * 100)))

    # ── Classification ─────────────────────────────────────────────────────
    if score < 34:
        level = "low"
    elif score <= 67:
        level = "moderate"
    else:
        level = "high"

    # ── Carb density (% carbs by total food weight) ────────────────────────
    carb_density = round((t_carbs / max(1.0, total_weight_g)) * 100, 1)

    # ── Explanation ───────────────────────────────────────────────────────
    explanation = _build_explanation(
        level=level,
        adjusted_gl=adjusted_gl,
        total_raw_gl=total_raw_gl,
        fiber_buffer=fiber_buffer,
        protein_buffer=protein_buffer,
        fat_buffer=fat_buffer,
        high_gi_items=high_gi_items,
        t_fiber=t_fiber,
        t_protein=t_protein,
        t_net_carbs=t_net_carbs,
    )

    recommendations = _get_recommendations(
        level=level,
        fiber_g=t_fiber,
        protein_g=t_protein,
        net_carbs=t_net_carbs,
        high_gi_items=high_gi_items,
        has_diabetes_condition=has_diabetes,
    )

    return {
        "score": score,
        "level": level,
        "glycemic_load": round(adjusted_gl, 1),
        "raw_glycemic_load": round(total_raw_gl, 1),
        "carb_density": carb_density,
        "fiber_impact": round(fiber_buffer, 3),
        "protein_buffer": round(protein_buffer, 3),
        "fat_buffer": round(fat_buffer, 3),
        "explanation": explanation,
        "recommendations": recommendations,
        "disclaimer": _DISCLAIMER,
        "per_item_gi": {k: round(v) for k, v in per_item_gi.items()},
    }


def _build_explanation(
    level: str,
    adjusted_gl: float,
    total_raw_gl: float,
    fiber_buffer: float,
    protein_buffer: float,
    fat_buffer: float,
    high_gi_items: list[str],
    t_fiber: float,
    t_protein: float,
    t_net_carbs: float,
) -> str:
    base = _LEVEL_EXPLANATIONS[level]

    detail_parts: list[str] = []

    if high_gi_items:
        items_str = ", ".join(high_gi_items[:2])
        detail_parts.append(
            f"High-GI items detected: {items_str}."
        )

    if fiber_buffer >= 0.30:
        detail_parts.append(
            f"Fibre is providing a strong buffer ({round(fiber_buffer * 100)} % "
            f"reduction in estimated glucose load)."
        )
    elif fiber_buffer >= 0.10:
        detail_parts.append(
            f"Some fibre is present, giving a moderate buffer "
            f"({round(fiber_buffer * 100)} % reduction)."
        )

    if protein_buffer >= 0.15:
        detail_parts.append(
            f"The protein content is also helping to blunt the response "
            f"({round(protein_buffer * 100)} % buffer effect)."
        )

    if detail_parts:
        return base + " " + " ".join(detail_parts)
    return base
