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
            if not isinstance(parsed, dict):
                raise ValueError(f"Claude returned non-object JSON ({type(parsed).__name__})")
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

    def _encode_image(self, image_path: str) -> str:
        """Resize and base64-encode a single image for the Claude API."""
        try:
            import cv2 as _cv2
            img = _cv2.imread(image_path)
            if img is not None:
                h, w = img.shape[:2]
                max_dim = 1024
                if max(h, w) > max_dim:
                    scale = max_dim / max(h, w)
                    img = _cv2.resize(
                        img, (int(w * scale), int(h * scale)),
                        interpolation=_cv2.INTER_AREA,
                    )
                _, buf = _cv2.imencode(".jpg", img, [_cv2.IMWRITE_JPEG_QUALITY, 85])
                return base64.standard_b64encode(buf.tobytes()).decode("utf-8")
        except Exception:
            pass
        # Fallback: read raw bytes
        with open(image_path, "rb") as f:
            return base64.standard_b64encode(f.read()).decode("utf-8")

    async def analyze_image_with_vision(self, image_paths: "str | list[str]") -> dict:
        """
        Full vision-first analysis: encodes 1–4 images and sends them to Claude
        Vision in a single message so it can cross-reference food quantity with
        nutrition labels, packaging, and multiple angles.
        Returns a nutrition report dict (same shape as pipeline._build_report).
        """
        if isinstance(image_paths, str):
            image_paths = [image_paths]

        if not _ANTHROPIC_KEY:
            return self._vision_fallback_mock()

        response_text = ""
        try:
            images_b64 = [self._encode_image(p) for p in image_paths]

            response_text = await asyncio.to_thread(
                self._call_claude_vision, images_b64
            )
            parsed = json.loads(_strip_fences(response_text))
            if not isinstance(parsed, dict):
                raise ValueError(f"Claude returned non-object JSON ({type(parsed).__name__}): {response_text[:300]}")

            # ── Normalise validated_items ──────────────────────────────────
            # Claude occasionally returns items as a dict keyed by name,
            # or wraps each item as a JSON-encoded string. Handle all forms.
            raw_items = parsed.get("validated_items", [])
            if isinstance(raw_items, dict):
                raw_items = list(raw_items.values())
            elif not isinstance(raw_items, list):
                raw_items = []

            enriched = []
            for raw_v in raw_items:
                # Unwrap JSON-string-encoded item if needed
                if isinstance(raw_v, str):
                    try:
                        raw_v = json.loads(raw_v)
                    except Exception:
                        continue
                if not isinstance(raw_v, dict):
                    continue
                v = raw_v
                grams = v.get("validated_grams") or v.get("original_grams") or 0
                per_100g = v.get("nutrition_per_100g") or {}
                if not isinstance(per_100g, dict):
                    per_100g = {}
                factor = grams / 100.0
                enriched.append({
                    "label": v.get("corrected_label") or v.get("original_label") or "unknown food",
                    "grams": grams,
                    "gram_confidence": "medium",
                    "nutrition": {k: round(val * factor, 2) for k, val in per_100g.items()},
                    "nutrition_source": v.get("nutrition_source", "llm"),
                    "is_hidden_ingredient": False,
                })

            # ── Normalise hidden_ingredients ───────────────────────────────
            raw_hidden = parsed.get("hidden_ingredients", [])
            if isinstance(raw_hidden, dict):
                raw_hidden = list(raw_hidden.values())
            elif not isinstance(raw_hidden, list):
                raw_hidden = []

            for raw_h in raw_hidden:
                if isinstance(raw_h, str):
                    try:
                        raw_h = json.loads(raw_h)
                    except Exception:
                        continue
                if not isinstance(raw_h, dict):
                    continue
                hidden = raw_h
                grams = hidden.get("estimated_grams", 0)
                per_100g = hidden.get("nutrition_per_100g") or {}
                if not isinstance(per_100g, dict):
                    per_100g = {}
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
            print(f"[LLMValidator] Vision analysis error: {e} | response snippet: {response_text[:400]!r}")
            return self._vision_fallback_mock()

    def _call_claude_vision(self, images_b64: list) -> str:
        """Send 1–4 images to Claude Vision in a single message.

        Photo roles inferred by position:
          Photo 1 — the food itself (quantity / portion visible)
          Photo 2 — nutrition facts label or packaging (if present)
          Photos 3-4 — additional angles / close-ups

        Claude uses all photos together for maximum accuracy: it reads exact
        macros from a nutrition label and applies them to the portion size it
        can see in the food photo, instead of estimating from appearance alone.
        """
        client = self._get_client()

        n = len(images_b64)
        if n == 1:
            photo_context = (
                "You have been given 1 photo of a meal or food item."
            )
        else:
            roles = ["Photo 1: the food / portion being eaten"]
            if n >= 2:
                roles.append("Photo 2: likely a nutrition facts label or product packaging")
            for i in range(3, n + 1):
                roles.append(f"Photo {i}: additional angle or close-up")
            photo_context = (
                f"You have been given {n} photos of the same food/meal:\n"
                + "\n".join(f"  • {r}" for r in roles)
                + "\n\nCross-reference ALL photos. "
                  "If a nutrition label is present, use its exact macro values "
                  "and scale them to the portion size visible in the food photo. "
                  "This gives much higher accuracy than estimating from appearance alone."
            )

        prompt = (
            f"{photo_context}\n\n"
            "You are a senior registered dietitian specialising in Indian cuisine with access to IFCT 2017 and USDA FoodData.\n\n"
            "IDENTIFICATION — be maximally specific:\n"
            "  - 'dal makhani' not 'dal' (dal makhani has ~8g fat/100g from butter+cream vs 0.4g for plain toor dal)\n"
            "  - 'aloo paratha with ghee' not 'paratha'\n"
            "  - 'masala dosa with potato filling' not 'dosa'\n"
            "  - For packaged foods, read the brand and product name from the label.\n\n"
            "WEIGHT ESTIMATION — use all visual cues:\n"
            "  - Standard Indian steel katori (small bowl) = 150–180 ml ≈ 120–150g for dal/curry\n"
            "  - Standard roti / chapati = 30–35g per piece\n"
            "  - Standard paratha = 60–80g per piece\n"
            "  - Dinner plate rice serving = 150–200g cooked\n"
            "  - If a hand, coin, or other reference object is visible, use it to calibrate size.\n"
            "  - If a nutrition label is present in any photo, read the serving size directly from it.\n\n"
            "HIDDEN INGREDIENTS — always consider:\n"
            "  - Ghee/butter brushed on roti, paratha, naan (typically 5–10g per piece)\n"
            "  - Cooking oil in sabzi/curry (typically 10–15g per 150g serving)\n"
            "  - Cream/malai in rich curries (dal makhani, butter chicken, shahi paneer)\n"
            "  - Sugar in chai, mithai, packaged drinks\n\n"
            "NUTRITION SOURCE — preference order:\n"
            "  1. Nutrition label in photo (set nutrition_source: 'label')\n"
            "  2. IFCT 2017 for Indian foods (set nutrition_source: 'ifct')\n"
            "  3. USDA FoodData for others (set nutrition_source: 'usda')\n\n"
            "Return ONLY valid JSON — no prose, no markdown fences:\n"
            "{\n"
            '  "validated_items": [\n'
            "    {\n"
            '      "original_label": "exact food name",\n'
            '      "corrected_label": "exact food name",\n'
            '      "original_grams": 100,\n'
            '      "validated_grams": 100,\n'
            '      "weight_plausible": true,\n'
            '      "nutrition_per_100g": {\n'
            '        "calories": 0, "protein_g": 0, "fat_g": 0, "carbs_g": 0, "fiber_g": 0\n'
            "      },\n"
            '      "nutrition_source": "label"\n'
            "    }\n"
            "  ],\n"
            '  "hidden_ingredients": [],\n'
            '  "overall_confidence": "high",\n'
            '  "confidence_reason": "Nutrition label present — exact values used",\n'
            '  "cultural_notes": "",\n'
            '  "meal_balance_notes": ""\n'
            "}"
        )

        # Build content: one image block per photo, then the text prompt
        content: list = []
        for img_b64 in images_b64:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": img_b64,
                },
            })
        content.append({"type": "text", "text": prompt})

        message = client.messages.create(
            model=_CLAUDE_MODEL,
            max_tokens=_MAX_TOKENS,
            system=(
                "You are a senior registered dietitian with deep expertise in Indian cuisine, "
                "IFCT 2017, and USDA FoodData. You estimate food weights and macros from photos "
                "with high precision. You always return valid JSON exactly matching the requested schema."
            ),
            messages=[{"role": "user", "content": content}],
        )
        return message.content[0].text

    @staticmethod
    def _vision_fallback_mock() -> dict:
        return {
            "items": [],
            "total": {"calories": 0.0, "protein_g": 0.0, "fat_g": 0.0, "carbs_g": 0.0, "fiber_g": 0.0},
            "llm_notes": "Analysis temporarily unavailable — please try again.",
            "llm_confidence": "low",
            "analysis_version": "2.0-vision",
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _passthrough(food_items: list) -> tuple[list, dict]:
        return food_items, {"llm_confidence": "low", "confidence_reason": "LLM not available"}
