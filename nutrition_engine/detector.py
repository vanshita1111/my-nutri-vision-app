"""
Food detector: wraps YOLOv8 (ONNX or .pt) for multi-item food detection.
Falls back to a mock detector when model weights are not yet downloaded.
"""

import numpy as np
from pathlib import Path
from typing import Optional
import cv2


class FoodDetector:
    def __init__(self, model_path: str, device: str = "cpu", confidence_threshold: float = 0.35):
        self.model_path = model_path
        self.device = device
        self.confidence_threshold = confidence_threshold
        self._model = None
        self._use_mock = not Path(model_path).exists()

    def load(self):
        if self._use_mock:
            print(f"[FoodDetector] Model not found at {self.model_path}. Using mock detector.")
            return
        try:
            from ultralytics import YOLO
            self._model = YOLO(self.model_path)
            self._model.to(self.device)
            print(f"[FoodDetector] Loaded YOLOv8 from {self.model_path}")
        except ImportError:
            print("[FoodDetector] ultralytics not installed. Using mock detector.")
            self._use_mock = True

    def detect(self, image: np.ndarray) -> list[dict]:
        """
        Run food detection on a preprocessed BGR numpy image.

        Returns:
            List of dicts: [{label, bbox [x1,y1,x2,y2], confidence}, ...]
        """
        if self._use_mock:
            return self._mock_detections(image)

        results = self._model(image, conf=self.confidence_threshold, verbose=False)
        detections = []
        for result in results:
            for box in result.boxes:
                detections.append({
                    "label": result.names[int(box.cls)],
                    "bbox": [int(x) for x in box.xyxy[0].tolist()],
                    "confidence": float(box.conf),
                })
        return detections

    @staticmethod
    def _mock_detections(image: np.ndarray) -> list[dict]:
        """Returns a mock detection for development/testing."""
        h, w = image.shape[:2]
        return [
            {
                "label": "rice",
                "bbox": [int(w * 0.1), int(h * 0.1), int(w * 0.5), int(h * 0.5)],
                "confidence": 0.88,
            },
            {
                "label": "dal",
                "bbox": [int(w * 0.55), int(h * 0.1), int(w * 0.9), int(h * 0.5)],
                "confidence": 0.79,
            },
        ]


def preprocess_image(image_path: str, target_size: int = 640) -> np.ndarray:
    """
    Load and preprocess an image for YOLO:
    - EXIF rotation fix
    - CLAHE (contrast normalisation)
    - Resize to target_size
    Returns BGR numpy array.
    """
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read image at {image_path}")

    # EXIF rotation
    img = _fix_exif_rotation(image_path, img)

    # Blur quality check — threshold from config (MIN_BLUR_SCORE), default 50.0
    # IMPORTANT: downscale to target_size FIRST so Laplacian variance is
    # resolution-independent. Mobile cameras shoot at 10–40 MP; computing
    # variance on the full image gives artificially low scores because
    # fine detail is spread across far more pixels than the threshold assumes.
    try:
        from app.config import settings as _cfg
        _min_blur = _cfg.MIN_BLUR_SCORE
    except Exception:
        import os
        _min_blur = float(os.getenv("MIN_BLUR_SCORE", "50.0"))

    h0, w0 = img.shape[:2]
    scale_chk = target_size / max(h0, w0)
    check_img = cv2.resize(img, (int(w0 * scale_chk), int(h0 * scale_chk)), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(check_img, cv2.COLOR_BGR2GRAY)
    blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
    import logging as _logging
    _logging.getLogger(__name__).debug("preprocess_image blur_score=%.1f threshold=%.1f", blur_score, _min_blur)
    if blur_score < _min_blur:
        raise ValueError(f"Image is too blurry (score={blur_score:.1f}). Please retake the photo in better light.")

    # Adaptive histogram equalisation (CLAHE) on L channel
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l_ch, a_ch, b_ch = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_ch = clahe.apply(l_ch)
    img = cv2.cvtColor(cv2.merge([l_ch, a_ch, b_ch]), cv2.COLOR_LAB2BGR)

    # Resize (keep aspect ratio, pad)
    img = _letterbox(img, target_size)

    return img


def _fix_exif_rotation(image_path: str, img: np.ndarray) -> np.ndarray:
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS
        pil_img = Image.open(image_path)
        exif_data = pil_img._getexif()
        if exif_data:
            orientation_key = next(
                (k for k, v in TAGS.items() if v == "Orientation"), None
            )
            orientation = exif_data.get(orientation_key, 1) if orientation_key else 1
            rotations = {3: 180, 6: 270, 8: 90}
            angle = rotations.get(orientation)
            if angle:
                img = np.rot90(img, k=angle // 90)
    except Exception:
        pass
    return img


def _letterbox(img: np.ndarray, target: int) -> np.ndarray:
    h, w = img.shape[:2]
    scale = target / max(h, w)
    new_w, new_h = int(w * scale), int(h * scale)
    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((target, target, 3), 114, dtype=np.uint8)
    top = (target - new_h) // 2
    left = (target - new_w) // 2
    canvas[top:top + new_h, left:left + new_w] = resized
    return canvas
