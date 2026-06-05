"""
Food segmentor: SAM2 prompted by YOLO bounding boxes.
Falls back to bounding-box mask when SAM weights not available.
"""

import numpy as np
from pathlib import Path


class FoodSegmentor:
    def __init__(self, model_path: str, config: str = "sam2_hiera_l.yaml", device: str = "cpu"):
        self.model_path = model_path
        self.config = config
        self.device = device
        self._predictor = None
        self._use_mock = not Path(model_path).exists()

    def load(self):
        if self._use_mock:
            print(f"[FoodSegmentor] SAM2 weights not found at {self.model_path}. Using bbox mask fallback.")
            return
        try:
            from sam2.build_sam import build_sam2
            from sam2.sam2_image_predictor import SAM2ImagePredictor
            sam2_model = build_sam2(self.config, self.model_path, device=self.device)
            self._predictor = SAM2ImagePredictor(sam2_model)
            print("[FoodSegmentor] SAM2 loaded.")
        except ImportError:
            print("[FoodSegmentor] sam2 not installed. Using bbox mask fallback.")
            self._use_mock = True

    def segment(self, image: np.ndarray, detections: list[dict]) -> list[dict]:
        """
        Generate pixel masks for each detected food item.

        Args:
            image: BGR numpy array (same size as used for detection)
            detections: list from FoodDetector.detect()

        Returns:
            List of dicts: [{label, mask (H×W bool), pixel_count, score}, ...]
        """
        if self._use_mock or self._predictor is None:
            return [self._bbox_mask(image, d) for d in detections]

        import torch
        rgb = image[:, :, ::-1]  # BGR → RGB
        self._predictor.set_image(rgb)
        results = []

        for det in detections:
            box = det["bbox"]
            center_x = (box[0] + box[2]) // 2
            center_y = (box[1] + box[3]) // 2

            with torch.inference_mode(), torch.autocast(self.device, dtype=torch.bfloat16):
                masks, scores, _ = self._predictor.predict(
                    point_coords=np.array([[center_x, center_y]]),
                    point_labels=np.array([1]),
                    box=np.array(box),
                    multimask_output=False,
                )

            mask = masks[0].astype(bool)
            results.append({
                "label": det["label"],
                "mask": mask,
                "pixel_count": int(mask.sum()),
                "score": float(scores[0]),
                "bbox": box,
            })

        return results

    @staticmethod
    def _bbox_mask(image: np.ndarray, detection: dict) -> dict:
        """Simple fallback: fill the bounding box as the mask."""
        h, w = image.shape[:2]
        mask = np.zeros((h, w), dtype=bool)
        x1, y1, x2, y2 = detection["bbox"]
        mask[y1:y2, x1:x2] = True
        return {
            "label": detection["label"],
            "mask": mask,
            "pixel_count": int(mask.sum()),
            "score": detection["confidence"],
            "bbox": detection["bbox"],
        }
