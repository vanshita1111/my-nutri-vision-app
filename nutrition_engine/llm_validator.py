"""
LLM validation layer using Claude API.
- Sanity-checks estimated weights and calories
- Identifies hidden ingredients (cooking oil, butter, cream)
- Provides Indian food cultural context
- Returns validated + enriched nutrition data
"""

import base64
import json
import asyncio
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING

# Allow use both standalone and inside the FastAPI app
try:
    from app.config import settings as _settings
    _ANTHROPIC_KEY = _settings.ANTHROPIC_API_KEY
    _CLAUDE_MODEL  = _settings.CLAUDE_MODEL
    _MAX_TOKENS    = _settings.LLM_MAX_TOKENS
except Exception:
    _ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    _CLAUDE_MODEL  = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
    _MAX_TOKENS    = 2048

if TYPE_CHECKING:
    from nutrition_engine.pipeline import FoodItem


def _extract_json(text: str) -> str:
    """
    Extract the first well-formed JSON object from text.
    Handles: markdown code fences, leading prose, trailing comments/content.
    """
    text = text.strip()
    # Strip code fence wrapper if present
    if text.startswith("```"):
        lines = text.split("\n")
        inner_lines = []
        for i, line in enumerate(lines):
            if i == 0:
                continue  # skip opening fence
            if line.strip() == "```":
                break  # stop at closing fence
            inner_lines.append(line)
        text = "\n".join(inner_lines).strip()

    # Find the JSON object by tracking brace depth — strips prose before/after
    start = text.find("{")
    if start < 0:
        return text
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return text[start:]


def _strip_fences(text: str) -> str:
    """Legacy alias kept for compatibility."""
    return _extract_json(text)


SYSTEM_PROMPT = """You are a senior registered dietitian with deep expertise in Indian cuisine
and food science. You have access to IFCT 2017 (Indian Food Composition Tables) and USDA
FoodData. You are precise, honest about uncertainty, and always flag implausible values."""


def _build_analysis_prompt(food_items: list, estimated_weights: dict) -> str:
    return f"""I have identified these food items from a meal photo taken in India:

Food items detected: {json.dumps([item["label"] for item in food_items], indent=2)}

Estimated weights (grams) from computer vision: {json.dumps(estimated_weights, indent=2)}

Please perform a thorough nutritional analysis:

1. **Validate weights**: Are these plausible for a typical single meal in India?
   Flag any that seem too high or too low.

2. **Hidden ingredients**: What invisible ingredients would typically be present?
   (e.g., ghee in roti, oil in sabzi, cream in dal makhani, sugar in chai)
   Be specific: "roti typically has 5g ghee applied" not just "ghee present".

3. **Food identification**: If the label might be wrong (e.g., detected "dal"
   could be "dal makhani" which has much higher fat), note the likely actual dish
   and provide corrected macros.

4. **Corrected nutrition**: For each item, provide macros using IFCT 2017 values
   where available (more accurate for Indian foods than USDA).

Return ONLY valid JSON in this exact format:
{{
  "validated_items": [
    {{
      "original_label": "rice",
      "corrected_label": "steamed basmati rice",
      "original_grams": 150,
      "validated_grams": 150,
      "weight_plausible": true,
      "nutrition_per_100g": {{
        "calories": 130,
        "protein_g": 2.7,
        "fat_g": 0.3,
        "carbs_g": 28.0,
        "fiber_g": 0.4
      }},
      "nutrition_source": "ifct"
    }}
  ],
  "hidden_ingredients": [
    {{
      "name": "ghee",
      "estimated_grams": 10,
      "reason": "Standard serving of 2 rotis typically has 5g ghee each",
      "nutrition_per_100g": {{
        "calories": 900, "protein_g": 0, "fat_g": 99, "carbs_g": 0, "fiber_g": 0
      }}
    }}
  ],
  "overall_confidence": "medium",
  "confidence_reason": "Weights look plausible but dal type ambiguous",
  "cultural_notes": "This looks like a standard North Indian thali.",
  "meal_balance_notes": "Good protein-carb balance. Low on vegetables."
}}"""


class LLMValidator:
    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=_ANTHROPIC_KEY)
        return self._client

    async def validate(self, food_items: list) -> tuple[list, dict]:
        """
        Validate and enrich food items using Claude.

        Returns:
            (enriched_items: list[dict], metadata: dict)
        """
        if not _ANTHROPIC_KEY:
            return self._passthrough(food_items)

        estimated_weights = {item["label"]: item.get("grams", 0) for item in food_items}

        try:
            response_text = await asyncio.to_thread(
                self._call_claude, food_items, estimated_weights
            )
            parsed = json.loads(_strip_fences(response_text))
            return self._merge_results(food_items, parsed)
        except Exception as e:
            print(f"[LLMValidator] Claude API error: {e}")
            return self._passthrough(food_items)

    def _call_claude(self, food_items: list, estimated_weights: dict) -> str:
        client = self._get_client()
        message = client.messages.create(
            model=_CLAUDE_MODEL,
            max_tokens=_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": _build_analysis_prompt(food_items, estimated_weights)}
            ],
        )
        return message.content[0].text

    @staticmethod
    def _merge_results(original_items: list, llm_response: dict) -> tuple[list, dict]:
        """Merge LLM corrections back into food item list."""
        validated_map = {
            v["original_label"].lower(): v
            for v in llm_response.get("validated_items", [])
        }

        enriched = []
        for item in original_items:
            label_key = item["label"].lower()
            v = validated_map.get(label_key, {})

            corrected_grams = v.get("validated_grams") or item.get("grams", 0)
            per_100g = v.get("nutrition_per_100g", {})
            factor = corrected_grams / 100.0

            if per_100g:
                nutrition = {k: round(val * factor, 2) for k, val in per_100g.items()}
            else:
                nutrition = item.get("nutrition", {})

            enriched.append({
                "label": v.get("corrected_label") or item["label"],
                "original_label": item["label"],
                "grams": corrected_grams,
                "gram_confidence": item.get("gram_confidence", "low"),
                "nutrition": nutrition,
                "nutrition_source": v.get("nutrition_source", item.get("nutrition_source", "fallback")),
                "weight_plausible": v.get("weight_plausible", True),
            })

        # Add hidden ingredients
        for hidden in llm_response.get("hidden_ingredients", []):
            grams = hidden.get("estimated_grams", 0)
            per_100g = hidden.get("nutrition_per_100g", {})
            factor = grams / 100.0
            enriched.append({
                "label": hidden["name"],
                "original_label": hidden["name"],
                "grams": grams,
                "gram_confidence": "low",
                "nutrition": {k: round(v * factor, 2) for k, v in per_100g.items()},
                "nutrition_source": "llm",
                "is_hidden_ingredient": True,
                "hidden_reason": hidden.get("reason", ""),
            })

        metadata = {
            "llm_confidence": llm_response.get("overall_confidence", "low"),
            "confidence_reason": llm_response.get("confidence_reason", ""),
            "cultural_notes": llm_response.get("cultural_notes", ""),
            "meal_balance_notes": llm_response.get("meal_balance_notes", ""),
        }

        return enriched, metadata

    async def analyze_image_with_vision(self, image_path: str) -> dict:
        """
        Full vision-first analysis: reads the image, sends it to Claude Vision,
        and returns a complete nutrition report dict (same shape as pipeline._build_report).
        Used when YOLO / SAM2 model weights are absent.
        """
        if not _ANTHROPIC_KEY:
            return self._vision_fallback_mock()

        try:
            with open(image_path, "rb") as f:
                image_bytes = f.read()
            image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

            response_text = await asyncio.to_thread(
                self._call_claude_vision, image_b64
            )
            parsed = json.loads(_strip_fences(response_text))

            # Build enriched items directly from Claude's validated_items.
            # Do NOT use _merge_results([], parsed) — that function merges
            # Claude corrections INTO a YOLO detection list; when called with
            # an empty list it discards every validated_item.
            enriched = []
            for v in parsed.get("validated_items", []):
                grams = v.get("validated_grams") or v.get("original_grams") or 0
                per_100g = v.get("nutrition_per_100g", {})
                factor = grams / 100.0
                enriched.append({
                    "label": v.get("corrected_label") or v.get("original_label") or "unknown food",
                    "grams": grams,
                    "gram_confidence": "medium",
                    "nutrition": {k: round(val * factor, 2) for k, val in per_100g.items()},
                    "nutrition_source": v.get("nutrition_source", "llm"),
                    "is_hidden_ingredient": False,
                })

            for hidden in parsed.get("hidden_ingredients", []):
                grams = hidden.get("estimated_grams", 0)
                per_100g = hidden.get("nutrition_per_100g", {})
                factor = grams / 100.0
                enriched.append({
                    "label": hidden.get("name", "unknown"),
                    "grams": grams,
                    "gram_confidence": "low",
                    "nutrition": {k: round(val * factor, 2) for k, val in per_100g.items()},
                    "nutrition_source": "llm",
                    "is_hidden_ingredient": True,
                })

            total = {"calories": 0.0, "protein_g": 0.0, "fat_g": 0.0, "carbs_g": 0.0, "fiber_g": 0.0}
            clean_items = []
            for item in enriched:
                n = item.get("nutrition", {})
                for key in total:
                    total[key] = round(total[key] + n.get(key, 0), 2)
                clean_items.append({
                    "label": item["label"],
                    "grams": item.get("grams", 0),
                    "gram_confidence": item.get("gram_confidence", "medium"),
                    "portion_method": "vision",
                    "nutrition": n,
                    "nutrition_source": item.get("nutrition_source", "llm"),
                    "is_hidden_ingredient": item.get("is_hidden_ingredient", False),
                })

            visible_items = [it for it in clean_items if not it.get("is_hidden_ingredient")]
            if not visible_items:
                return {
                    "error": "no_food_detected",
                    "message": "No food items were detected. Please make sure the photo clearly shows food.",
                    "items": [],
                    "total": {"calories": 0.0, "protein_g": 0.0, "fat_g": 0.0, "carbs_g": 0.0, "fiber_g": 0.0},
                }

            return {
                "items": clean_items,
                "total": total,
                "llm_notes": " ".join(filter(None, [
                    parsed.get("cultural_notes", ""),
                    parsed.get("meal_balance_notes", ""),
                ])),
                "llm_confidence": parsed.get("overall_confidence", "medium"),
                "analysis_version": "2.0-vision",
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            print(f"[LLMValidator] Vision analysis error: {e}")
            return self._vision_fallback_mock()

    def _call_claude_vision(self, image_b64: str) -> str:
        client = self._get_client()
        prompt = (
            "You are a nutrition expert. Look at this food photo and identify EVERY food item visible.\n\n"
            "For each item provide:\n"
            "1. The exact food name (be specific: 'sliced cucumber', 'cherry tomatoes', not just 'vegetable')\n"
            "2. Estimated weight in grams based on typical portion and visual size\n"
            "3. Accurate nutritional values per 100g (use USDA/IFCT 2017 data)\n\n"
            "Also identify any hidden cooking ingredients (oil, ghee, butter, salt) if visible or likely.\n\n"
            "Return ONLY this JSON — no prose, no markdown:\n"
            "{\n"
            '  "validated_items": [\n'
            "    {\n"
            '      "original_label": "exact food name",\n'
            '      "corrected_label": "exact food name",\n'
            '      "original_grams": estimated_weight,\n'
            '      "validated_grams": estimated_weight,\n'
            '      "weight_plausible": true,\n'
            '      "nutrition_per_100g": {\n'
            '        "calories": 0, "protein_g": 0, "fat_g": 0, "carbs_g": 0, "fiber_g": 0\n'
            "      },\n"
            '      "nutrition_source": "usda"\n'
            "    }\n"
            "  ],\n"
            '  "hidden_ingredients": [],\n'
            '  "overall_confidence": "high",\n'
            '  "confidence_reason": "reason",\n'
            '  "cultural_notes": "notes",\n'
            '  "meal_balance_notes": "notes"\n'
            "}"
        )
        message = client.messages.create(
            model=_CLAUDE_MODEL,
            max_tokens=_MAX_TOKENS,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        return message.content[0].text

    @staticmethod
    def _vision_fallback_mock() -> dict:
        return {
            "items": [],
            "total": {"calories": 0.0, "protein_g": 0.0, "fat_g": 0.0, "carbs_g": 0.0, "fiber_g": 0.0},
            "llm_notes": "Analysis unavailable — Anthropic API key not configured.",
            "llm_confidence": "low",
            "analysis_version": "2.0-vision",
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _passthrough(food_items: list) -> tuple[list, dict]:
        return food_items, {"llm_confidence": "low", "confidence_reason": "LLM not available"}
