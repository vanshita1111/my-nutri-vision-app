"""
Nutrition lookup: embedded table → USDA API → LLM fallback.
This module is used by the pipeline (no DB session needed — uses httpx directly).
"""

import json
import asyncio
import os
from pathlib import Path
from functools import lru_cache
from typing import Optional

import httpx


# ── Embedded nutrition data (no DB needed for pipeline) ─────────────────────

@lru_cache(maxsize=1)
def _load_embedded() -> dict:
    path = Path(__file__).parent / "density_tables" / "embedded_nutrition.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}


# ── Public API ────────────────────────────────────────────────────────────────

async def lookup_nutrition(food_label: str, weight_grams: float) -> tuple[dict, str]:
    """
    Returns (macro_dict, source) where source is one of: embedded / usda / fallback.
    macro_dict keys: calories, protein_g, fat_g, carbs_g, fiber_g
    """
    per_100g, source = await _get_per_100g(food_label)
    macros = _scale(per_100g, weight_grams)
    return macros, source


async def _get_per_100g(food_label: str) -> tuple[dict, str]:
    label_lower = food_label.lower()
    embedded = _load_embedded()

    # 1. Embedded table
    for key, data in embedded.items():
        if key in label_lower or label_lower in key:
            return data, "embedded"

    # 2. USDA API
    if os.getenv("USDA_API_KEY", ""):
        usda = await _query_usda(food_label)
        if usda:
            return usda, "usda"

    # 3. Statistical fallback
    return _statistical_fallback(food_label), "fallback"


async def _query_usda(food_label: str) -> Optional[dict]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{os.getenv('USDA_API_BASE', 'https://api.nal.usda.gov/fdc/v1')}/foods/search",
                params={"query": food_label, "api_key": os.getenv("USDA_API_KEY", ""), "pageSize": 1},
            )
        foods = resp.json().get("foods", [])
        if not foods:
            return None
        nutrients = {n["nutrientName"]: n.get("value", 0) for n in foods[0].get("foodNutrients", [])}
        return {
            "calories":  nutrients.get("Energy", 0),
            "protein_g": nutrients.get("Protein", 0),
            "fat_g":     nutrients.get("Total lipid (fat)", 0),
            "carbs_g":   nutrients.get("Carbohydrate, by difference", 0),
            "fiber_g":   nutrients.get("Fiber, total dietary", 0),
        }
    except Exception:
        return None


def _statistical_fallback(food_label: str) -> dict:
    """Very rough per-100g estimates as last resort."""
    label = food_label.lower()
    if "rice" in label or "biryani" in label:
        return {"calories": 130, "protein_g": 2.7, "fat_g": 0.3, "carbs_g": 28, "fiber_g": 0.4}
    if "dal" in label or "lentil" in label:
        return {"calories": 116, "protein_g": 9, "fat_g": 0.4, "carbs_g": 20, "fiber_g": 4}
    if "roti" in label or "chapati" in label:
        return {"calories": 297, "protein_g": 9, "fat_g": 3.7, "carbs_g": 57, "fiber_g": 2}
    if "paratha" in label:
        return {"calories": 326, "protein_g": 8, "fat_g": 11, "carbs_g": 48, "fiber_g": 2}
    if "chicken" in label:
        return {"calories": 165, "protein_g": 31, "fat_g": 3.6, "carbs_g": 0, "fiber_g": 0}
    if "paneer" in label:
        return {"calories": 265, "protein_g": 18, "fat_g": 20, "carbs_g": 3, "fiber_g": 0}
    if "egg" in label:
        return {"calories": 155, "protein_g": 13, "fat_g": 11, "carbs_g": 1, "fiber_g": 0}
    if "salad" in label:
        return {"calories": 20, "protein_g": 1.5, "fat_g": 0.3, "carbs_g": 3, "fiber_g": 1.5}
    # Generic mixed dish
    return {"calories": 150, "protein_g": 6, "fat_g": 5, "carbs_g": 20, "fiber_g": 2}


def _scale(per_100g: dict, weight: float) -> dict:
    factor = weight / 100.0
    return {k: round(v * factor, 2) for k, v in per_100g.items()}
