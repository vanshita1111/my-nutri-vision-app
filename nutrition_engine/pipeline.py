"""
NutritionPipeline: orchestrates all stages from raw image to nutrition report.

Stages:
    1. Preprocess (OpenCV)
    2. Detect (YOLOv8)
    3. Segment (SAM2)
    4. Depth estimation (Depth Anything v2)
    5. Volume calculation
    6. Gram conversion
    7. Nutrition lookup
    8. LLM validation (Claude)
    9. Build report
"""

import os
import logging
from datetime import datetime, timezone

# Avoid circular import: nutrition_engine is imported by Celery workers before
# the FastAPI app is initialised, so we can't do `from app.config import settings`
# at module level. Use os.getenv() with sensible defaults instead.
try:
    from app.config import settings as _settings  # type: ignore
    _YOLO_PATH   = _settings.YOLO_MODEL_PATH
    _SAM2_PATH   = _settings.SAM2_MODEL_PATH
    _SAM2_CONFIG = _settings.SAM2_CONFIG
    _DEPTH_ID    = _settings.DEPTH_MODEL_ID
    _DEVICE      = _settings.DEVICE
except Exception:  # pragma: no cover
    _YOLO_PATH   = os.getenv("YOLO_MODEL_PATH",  "models/weights/yolov8n_food.pt")
    _SAM2_PATH   = os.getenv("SAM2_MODEL_PATH",  "models/weights/sam2_hiera_base.pt")
    _SAM2_CONFIG = os.getenv("SAM2_CONFIG",       "sam2_hiera_b.yaml")
    _DEPTH_ID    = os.getenv("DEPTH_MODEL_ID",    "LiheYoung/depth-anything-small-hf")
    _DEVICE      = os.getenv("DEVICE",            "cpu")

log = logging.getLogger(__name__)


class NutritionPipeline:
    def __init__(self, device: str = _DEVICE):
        self.device = device
        self.models_ready = False

        self._detector            = None
        self._secondary_classifier = None
        self._segmentor           = None
        self._depth_estimator     = None
        self._llm_validator       = None

    async def load_models(self):
        """Load all ML models. Called once at FastAPI startup."""
        from nutrition_engine.detector import FoodDetector
        from nutrition_engine.segmentor import FoodSegmentor
        from nutrition_engine.depth_estimator import DepthEstimator
        from nutrition_engine.llm_validator import LLMValidator
        from nutrition_engine.secondary_classifier import SecondaryClassifier

        self._detector = FoodDetector(_YOLO_PATH, self.device)
        self._detector.load()

        # Secondary EfficientNet classifier — gracefully a no-op if weights absent
        self._secondary_classifier = SecondaryClassifier()
        self._secondary_classifier.load()

        self._segmentor = FoodSegmentor(_SAM2_PATH, _SAM2_CONFIG, self.device)
        self._segmentor.load()

        self._depth_estimator = DepthEstimator(self.device, _DEPTH_ID)
        self._depth_estimator.load()

        self._llm_validator = LLMValidator()

        self.models_ready = True
        log.info("NutritionPipeline: all models loaded on device=%s", self.device)

    async def cleanup(self):
        """Release GPU memory on shutdown."""
        self._detector             = None
        self._secondary_classifier = None
        self._segmentor            = None
        self._depth_estimator      = None
        self._llm_validator        = None
        self.models_ready = False
        log.info("NutritionPipeline: models unloaded.")

    async def analyze(self, image_path: str) -> dict:
        """
        Full pipeline: image_path → nutrition report dict.
        Safe to call concurrently (each call creates independent local state).
        When YOLO/SAM2 model weights are absent, falls back to Claude Vision
        for direct food identification — accurate and no model files required.
        """
        from nutrition_engine.detector import preprocess_image
        from nutrition_engine.volume_calculator import calculate_volumes
        from nutrition_engine.gram_converter import volume_to_grams
        from nutrition_engine.nutrition_lookup import lookup_nutrition

        # ── Stage 1: Preprocess (blur check + normalise) ───────────────────────
        try:
            image = preprocess_image(image_path)
        except ValueError as e:
            return {"error": str(e), "items": [], "total": _zero_macros()}

        # ── Vision fallback: if YOLO weights absent, use Claude Vision ─────────
        if self._detector._use_mock:
            log.info("YOLO model absent — delegating to Claude Vision for food detection")
            return await self._llm_validator.analyze_image_with_vision(image_path)

        # ── Stage 2: Detect ────────────────────────────────────────────────────
        detections = self._detector.detect(image)
        if not detections:
            return {
                "error": "no_food_detected",
                "message": "No food items were detected. Please ensure food is clearly visible and well-lit.",
                "items": [],
                "total": _zero_macros(),
            }

        # ── Stage 2b: Secondary classification (low-confidence detections) ────
        # For any detection where YOLO confidence < 0.6, run EfficientNet-B3
        # and override the label if the classifier is more confident.
        if self._secondary_classifier is not None:
            detections = self._secondary_classifier.classify_detections(
                image_bgr=image,
                detections=detections,
                yolo_conf_threshold=0.6,
            )

        # ── Stage 3: Segment ───────────────────────────────────────────────────
        masks = self._segmentor.segment(image, detections)

        # ── Stage 4: Depth ─────────────────────────────────────────────────────
        depth_map = self._depth_estimator.estimate(image)

        # ── Stage 5: Volume ────────────────────────────────────────────────────
        volume_estimates = calculate_volumes(
            masks=masks,
            depth_map=depth_map,
            image_shape=image.shape,
            reference_detections=None,  # TODO: pass reference objects when detected
        )

        # ── Stage 6 + 7: Grams + Nutrition ────────────────────────────────────
        food_items_raw = []
        for det, _, vol_est in zip(detections, masks, volume_estimates):
            grams, gram_conf = volume_to_grams(det["label"], vol_est)
            macros, source = await lookup_nutrition(det["label"], grams)
            food_items_raw.append({
                "label": det["label"],
                "confidence": det["confidence"],
                "grams": grams,
                "gram_confidence": gram_conf,
                "nutrition": macros,
                "nutrition_source": source,
                "portion_method": vol_est.method,
            })

        # ── Stage 8: LLM validation ────────────────────────────────────────────
        validated_items, llm_meta = await self._llm_validator.validate(food_items_raw)

        # ── Stage 9: Report ────────────────────────────────────────────────────
        return self._build_report(validated_items, llm_meta)

    @staticmethod
    def _build_report(items: list, llm_meta: dict) -> dict:
        total = _zero_macros()

        clean_items = []
        for item in items:
            n = item.get("nutrition", {})
            for key in total:
                total[key] = round(total[key] + n.get(key, 0), 2)

            clean_items.append({
                "label": item["label"],
                "grams": item.get("grams", 0),
                "gram_confidence": item.get("gram_confidence", "low"),
                "portion_method": item.get("portion_method", "prior"),
                "nutrition": n,
                "nutrition_source": item.get("nutrition_source", "fallback"),
                "is_hidden_ingredient": item.get("is_hidden_ingredient", False),
            })

        return {
            "items": clean_items,
            "total": total,
            "llm_notes": " ".join(filter(None, [llm_meta.get("cultural_notes", ""), llm_meta.get("meal_balance_notes", "")])),
            "llm_confidence": llm_meta.get("llm_confidence", "low"),
            "analysis_version": "2.0",
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }


def _zero_macros() -> dict:
    return {"calories": 0.0, "protein_g": 0.0, "fat_g": 0.0, "carbs_g": 0.0, "fiber_g": 0.0}
