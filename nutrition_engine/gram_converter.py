"""
Converts volume estimates to grams using food-specific density tables.
Applies sanity-check ranges from typical serving sizes.
"""

import json
from pathlib import Path
from nutrition_engine.volume_calculator import VolumeEstimate, volume_to_ml


# ── Load density tables ──────────────────────────────────────────────────────

_DENSITY_DATA: dict = {}
_TABLES_DIR = Path(__file__).parent / "density_tables"

for _fname in ["usda_densities.json", "ifct_densities.json", "custom_densities.json"]:
    _path = _TABLES_DIR / _fname
    if _path.exists():
        try:
            _DENSITY_DATA.update(json.loads(_path.read_text()))
        except Exception:
            pass


# ── Typical serving ranges (grams) ──────────────────────────────────────────

SERVING_RANGES: dict[str, tuple[float, float]] = {
    "rice":       (60,  400),
    "biryani":    (150, 500),
    "dal":        (80,  400),
    "roti":       (30,  120),
    "paratha":    (50,  200),
    "naan":       (60,  180),
    "idli":       (30,  200),
    "dosa":       (60,  250),
    "sambar":     (80,  300),
    "sabzi":      (80,  300),
    "curry":      (100, 500),
    "chicken":    (80,  350),
    "fish":       (80,  300),
    "paneer":     (50,  200),
    "egg":        (45,   90),
    "salad":      (50,  400),
    "fruit":      (50,  300),
    "bread":      (25,  150),
    "pasta":      (80,  350),
    "pizza":      (80,  350),
    "burger":     (100, 400),
    "soup":       (150, 500),
    "yogurt":     (80,  300),
    "milk":       (100, 300),
    "juice":      (100, 400),
}

TYPICAL_SERVING_GRAMS: dict[str, float] = {
    "rice": 150, "biryani": 300, "dal": 200, "roti": 60,
    "paratha": 90, "naan": 90, "idli": 100, "dosa": 100,
    "sambar": 150, "sabzi": 150, "curry": 200, "chicken": 150,
    "fish": 150, "paneer": 100, "egg": 60, "salad": 120,
    "fruit": 150, "bread": 60, "pasta": 200, "soup": 250,
    "yogurt": 150, "milk": 200, "juice": 200,
}


def volume_to_grams(food_label: str, volume_estimate: VolumeEstimate) -> tuple[float, str]:
    """
    Convert a VolumeEstimate to grams.

    Returns:
        (grams: float, confidence: "high" | "medium" | "low")
    """
    volume_ml = volume_to_ml(volume_estimate)

    if volume_estimate.method == "prior" or volume_ml < 1.0:
        return _typical_serving(food_label), "low"

    density = _get_density(food_label)
    grams = volume_ml * density

    # Sanity clamp
    min_g, max_g = _serving_range(food_label)
    if grams < min_g * 0.5:
        grams = min_g
        confidence = "low"
    elif grams > max_g * 1.5:
        grams = max_g
        confidence = "low"
    elif volume_estimate.volume_cm3 is not None:
        confidence = "medium"   # metric depth available
    else:
        confidence = "low"      # relative depth only

    return round(grams, 1), confidence


def _get_density(food_label: str) -> float:
    """Density in g/ml. Returns 0.9 if unknown."""
    label_lower = food_label.lower()
    for key, data in _DENSITY_DATA.items():
        if key in label_lower or label_lower in key:
            return data.get("density_g_per_ml", 0.9)
    return 0.9


def _typical_serving(food_label: str) -> float:
    label_lower = food_label.lower()
    for key, val in TYPICAL_SERVING_GRAMS.items():
        if key in label_lower:
            return val
    return 120.0


def _serving_range(food_label: str) -> tuple[float, float]:
    label_lower = food_label.lower()
    for key, rng in SERVING_RANGES.items():
        if key in label_lower:
            return rng
    return (30.0, 600.0)
