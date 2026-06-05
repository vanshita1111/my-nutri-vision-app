"""
Integration tests for the nutrition analysis pipeline.
Run: pytest backend/tests/test_pipeline.py -v -s

These tests run without GPU and without real model weights —
they exercise the fallback/mock paths.
"""

import asyncio
import os
import sys
import pytest
import numpy as np
from pathlib import Path

# Ensure backend and project root are on the path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Minimal env config for tests
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-32-chars-minimum!!")
os.environ.setdefault("DEVICE", "cpu")
os.environ.setdefault("YOLO_MODEL_PATH", "models/weights/food_detector_v1.onnx")
os.environ.setdefault("SAM2_MODEL_PATH", "models/weights/sam2_hiera_large.pt")


# ── Utility ──────────────────────────────────────────────────────────────────

def create_test_image(path: str, color: tuple = (40, 40, 40)):
    """
    Create a 640x640 test image with clear grayscale contrast so the
    Laplacian-variance blur check is satisfied even at MIN_BLUR_SCORE=20.

    Uses a dark-grey background (grayscale ≈ 40) with a white circle
    (grayscale = 255), giving a sharp edge and Laplacian variance >> 20.
    The `color` parameter is kept for API compatibility but ignored so
    callers that pass a tinted background still produce a sharp image.
    """
    import cv2
    img = np.full((640, 640, 3), 40, dtype=np.uint8)       # dark grey background
    cv2.circle(img, (320, 320), 150, (255, 255, 255), -1)   # bright white food circle
    cv2.imwrite(path, img)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestFoodDetector:
    def test_mock_detector_returns_detections(self):
        from nutrition_engine.detector import FoodDetector
        detector = FoodDetector("nonexistent_model.onnx", "cpu")
        detector.load()
        assert detector._use_mock is True

        img = np.full((640, 640, 3), 128, dtype=np.uint8)
        detections = detector.detect(img)
        assert len(detections) >= 1
        for d in detections:
            assert "label" in d
            assert "bbox" in d
            assert "confidence" in d
            assert 0 < d["confidence"] <= 1.0

    def test_preprocess_image(self, tmp_path):
        from nutrition_engine.detector import preprocess_image
        img_path = str(tmp_path / "test.jpg")
        create_test_image(img_path)
        img = preprocess_image(img_path)
        assert img is not None
        assert img.shape == (640, 640, 3)

    def test_blurry_image_raises(self, tmp_path):
        import cv2
        from nutrition_engine.detector import preprocess_image
        img_path = str(tmp_path / "blurry.jpg")
        # All-grey solid image = zero laplacian variance = very blurry
        solid = np.full((640, 640, 3), 128, dtype=np.uint8)
        cv2.imwrite(img_path, solid)
        with pytest.raises(ValueError, match="blurry"):
            preprocess_image(img_path)


class TestSegmentor:
    def test_bbox_mask_fallback(self):
        from nutrition_engine.segmentor import FoodSegmentor
        seg = FoodSegmentor("nonexistent.pt")
        seg.load()
        assert seg._use_mock is True

        img = np.zeros((640, 640, 3), dtype=np.uint8)
        detections = [{"label": "rice", "bbox": [100, 100, 400, 400], "confidence": 0.9}]
        results = seg.segment(img, detections)

        assert len(results) == 1
        assert results[0]["label"] == "rice"
        assert results[0]["mask"].shape == (640, 640)
        assert results[0]["mask"].sum() > 0


class TestVolumeCalculator:
    def test_volume_calculation(self):
        from nutrition_engine.volume_calculator import calculate_volumes, VolumeEstimate

        h, w = 640, 640
        mask = np.zeros((h, w), dtype=bool)
        mask[200:400, 200:400] = True

        depth_map = np.ones((h, w), dtype=np.float32) * 0.3
        depth_map[200:400, 200:400] = 0.7  # food closer to camera

        masks = [{"mask": mask, "label": "rice", "pixel_count": int(mask.sum())}]
        volumes = calculate_volumes(masks, depth_map, (h, w))

        assert len(volumes) == 1
        v = volumes[0]
        assert isinstance(v, VolumeEstimate)
        assert v.relative_height > 0
        assert v.pixel_count == 200 * 200


class TestGramConverter:
    def test_prior_fallback_returns_plausible_grams(self):
        from nutrition_engine.volume_calculator import VolumeEstimate
        from nutrition_engine.gram_converter import volume_to_grams

        est = VolumeEstimate(0, 0, 0, "prior")
        grams, confidence = volume_to_grams("rice", est)
        assert 60 <= grams <= 400
        assert confidence == "low"

    def test_depth_integration_returns_medium_confidence(self):
        from nutrition_engine.volume_calculator import VolumeEstimate
        from nutrition_engine.gram_converter import volume_to_grams

        # Simulate a valid depth-based volume
        est = VolumeEstimate(
            volume_relative=50000,
            pixel_count=40000,
            relative_height=1.25,
            method="depth_integration",
        )
        grams, confidence = volume_to_grams("dal", est)
        assert grams > 0
        assert confidence in ("low", "medium")


class TestNutritionLookup:
    def test_embedded_lookup_rice(self):
        result = asyncio.run(_test_rice_lookup())
        assert result["calories"] > 0
        assert result["protein_g"] >= 0

    def test_embedded_lookup_unknown_food(self):
        result = asyncio.run(_test_unknown_lookup())
        assert result["calories"] > 0


async def _test_rice_lookup():
    from nutrition_engine.nutrition_lookup import lookup_nutrition
    macros, source = await lookup_nutrition("rice", 150)
    assert source in ("embedded", "usda", "fallback")
    return macros


async def _test_unknown_lookup():
    from nutrition_engine.nutrition_lookup import lookup_nutrition
    macros, source = await lookup_nutrition("some_exotic_dish_xyz", 100)
    return macros


class TestCycleService:
    def test_known_phase_from_date(self):
        from datetime import date, timedelta
        from app.services.cycle_service import CycleService

        # 3 days ago = day 3 = menstrual
        last_period = date.today() - timedelta(days=3)
        svc = CycleService()
        info = svc.get_phase_info(last_period, cycle_length=28, weight_kg=60)
        assert info["phase"] == "menstrual"
        assert info["day_in_cycle"] == 4

    def test_unknown_phase_when_no_date(self):
        from app.services.cycle_service import CycleService
        svc = CycleService()
        info = svc.get_phase_info(None)
        assert info["phase"] == "unknown"
        assert "Settings" in info["phase_notes"]


async def test_full_pipeline_mock(tmp_path):
    """End-to-end pipeline test using mock models (no GPU needed)."""
    import cv2
    from nutrition_engine.pipeline import NutritionPipeline

    img_path = str(tmp_path / "meal.jpg")
    create_test_image(img_path, color=(100, 150, 80))

    pipeline = NutritionPipeline(device="cpu")
    await pipeline.load_models()

    result = await pipeline.analyze(img_path)

    assert "items" in result
    assert "total" in result
    total = result["total"]
    assert "calories" in total
    assert total["calories"] >= 0
    assert isinstance(result["items"], list)
    assert len(result["items"]) >= 1
