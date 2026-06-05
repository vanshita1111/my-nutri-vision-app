"""
Nutrition database service: local IFCT/USDA lookup + USDA API fallback.
"""

import json
import httpx
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.config import settings

# Pre-load embedded fallback nutrition data (small curated table)
_EMBEDDED_NUTRITION_FILE = Path(__file__).parent.parent.parent / "nutrition_engine" / "density_tables" / "embedded_nutrition.json"
_EMBEDDED_NUTRITION: dict = {}
if _EMBEDDED_NUTRITION_FILE.exists():
    _EMBEDDED_NUTRITION = json.loads(_EMBEDDED_NUTRITION_FILE.read_text())


class NutritionDatabase:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def search(self, query: str, limit: int = 10) -> list[dict]:
        """Fuzzy search using pg_trgm similarity."""
        try:
            sql = text("""
                SELECT food_id, name, category, source,
                       calories_per_100g, protein_g_per_100g,
                       fat_g_per_100g, carbs_g_per_100g, fiber_g_per_100g
                FROM foods
                WHERE similarity(name, :q) > 0.2
                ORDER BY similarity(name, :q) DESC
                LIMIT :limit
            """)
            result = await self.db.execute(sql, {"q": query, "limit": limit})
            rows = result.fetchall()
        except Exception:
            # DB not seeded yet — return empty
            return []

        return [
            {
                "food_id": r.food_id,
                "name": r.name,
                "category": r.category,
                "source": r.source,
                "per_100g": {
                    "calories": r.calories_per_100g,
                    "protein_g": r.protein_g_per_100g,
                    "fat_g": r.fat_g_per_100g,
                    "carbs_g": r.carbs_g_per_100g,
                    "fiber_g": r.fiber_g_per_100g,
                },
            }
            for r in rows
        ]

    async def lookup(self, food_label: str, weight_grams: float) -> dict:
        """Look up macros for a food, scaled to weight_grams."""
        per_100g = await self._get_per_100g(food_label)
        return self._scale(per_100g, weight_grams)

    async def _get_per_100g(self, food_label: str) -> dict:
        # 1. Embedded fallback (fast, no DB needed)
        label_lower = food_label.lower()
        for key, data in _EMBEDDED_NUTRITION.items():
            if key in label_lower or label_lower in key:
                return data

        # 2. USDA API
        usda_result = await self._query_usda(food_label)
        if usda_result:
            return usda_result

        # 3. Generic fallback
        return {"calories": 150, "protein_g": 5, "fat_g": 5, "carbs_g": 20, "fiber_g": 2}

    async def _query_usda(self, food_label: str) -> dict | None:
        if not settings.USDA_API_KEY:
            return None
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    f"{settings.USDA_API_BASE}/foods/search",
                    params={"query": food_label, "api_key": settings.USDA_API_KEY, "pageSize": 1},
                )
                data = resp.json()
            foods = data.get("foods", [])
            if not foods:
                return None
            nutrients = {n["nutrientName"]: n["value"] for n in foods[0].get("foodNutrients", [])}
            return {
                "calories": nutrients.get("Energy", 0),
                "protein_g": nutrients.get("Protein", 0),
                "fat_g": nutrients.get("Total lipid (fat)", 0),
                "carbs_g": nutrients.get("Carbohydrate, by difference", 0),
                "fiber_g": nutrients.get("Fiber, total dietary", 0),
            }
        except Exception:
            return None

    @staticmethod
    def _scale(per_100g: dict, weight: float) -> dict:
        factor = weight / 100.0
        return {k: round(v * factor, 2) for k, v in per_100g.items()}
