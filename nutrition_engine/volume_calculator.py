"""
Volume estimation from segmentation masks + depth maps.

Two strategies:
1. depth_integration: use depth values within the mask relative to background.
2. reference_scale: use a detected reference object (plate/fork/coin) for pixel→cm calibration.
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional


@dataclass
class VolumeEstimate:
    volume_relative: float        # Arbitrary relative units
    pixel_count: int
    relative_height: float        # Relative depth above surface
    method: str                   # depth_integration | reference_scale | prior
    scale_px_per_cm: Optional[float] = None
    volume_cm3: Optional[float] = None   # Set when reference object present


# Calibration factor: 1 relative volume unit ≈ X ml
# Tuned on Nutrition5K ground truth; adjust after validation
RELATIVE_TO_ML_FACTOR = 0.0023


# Real-world sizes of common reference objects (cm)
REFERENCE_SIZES_CM = {
    "dinner_plate":  26.0,
    "side_plate":    19.0,
    "bowl":          15.0,
    "fork":          18.5,
    "spoon":         17.0,
    "teaspoon":       9.0,
    "credit_card":    8.56,
    "ten_rupee_coin": 2.7,
    "five_rupee_coin": 2.3,
}


def calculate_volumes(
    masks: list[dict],
    depth_map: np.ndarray,
    image_shape: tuple,
    reference_detections: Optional[list[dict]] = None,
) -> list[VolumeEstimate]:
    """
    Args:
        masks: output of FoodSegmentor.segment()
        depth_map: normalised depth (H×W, float32)
        image_shape: (H, W, C)
        reference_detections: optional YOLO detections of reference objects
    """
    scale_px_per_cm = None
    if reference_detections:
        scale_px_per_cm = _detect_scale(reference_detections)

    volumes = []
    for mask_data in masks:
        mask = mask_data["mask"].astype(bool)

        if mask.sum() == 0:
            volumes.append(VolumeEstimate(0.0, 0, 0.0, "prior"))
            continue

        # Depth integration method
        depth_food = depth_map[mask]
        bg_mask = ~mask
        depth_bg = depth_map[bg_mask]

        food_mean = depth_food.mean()
        bg_mean = depth_bg.mean() if bg_mask.sum() > 0 else food_mean

        # Food is closer to camera → higher depth value (after inversion)
        relative_height = max(0.0, float(food_mean - bg_mean))
        pixel_count = int(mask.sum())
        volume_rel = pixel_count * relative_height

        est = VolumeEstimate(
            volume_relative=volume_rel,
            pixel_count=pixel_count,
            relative_height=relative_height,
            method="depth_integration",
            scale_px_per_cm=scale_px_per_cm,
        )

        # If we have a scale factor, compute metric volume
        if scale_px_per_cm and scale_px_per_cm > 0:
            area_cm2 = pixel_count / (scale_px_per_cm ** 2)
            # Height in cm from relative depth ratio and assumed max food height (8cm)
            height_cm = relative_height * 8.0
            est.volume_cm3 = round(area_cm2 * height_cm, 2)

        volumes.append(est)

    return volumes


def volume_to_ml(estimate: VolumeEstimate) -> float:
    """Convert a VolumeEstimate to millilitres."""
    if estimate.volume_cm3 is not None:
        return estimate.volume_cm3  # 1 cm³ = 1 ml
    if estimate.volume_relative > 0:
        return estimate.volume_relative * RELATIVE_TO_ML_FACTOR
    return 0.0


def _detect_scale(reference_detections: list[dict]) -> Optional[float]:
    """Find the most reliable reference object and return px/cm scale."""
    best = None
    for det in reference_detections:
        label = det["label"].lower().replace(" ", "_")
        if label in REFERENCE_SIZES_CM:
            real_cm = REFERENCE_SIZES_CM[label]
            x1, y1, x2, y2 = det["bbox"]
            pixel_span = max(x2 - x1, y2 - y1)
            if pixel_span > 10:
                px_per_cm = pixel_span / real_cm
                if best is None or det["confidence"] > best["confidence"]:
                    best = {"px_per_cm": px_per_cm, "confidence": det["confidence"]}
    return best["px_per_cm"] if best else None
