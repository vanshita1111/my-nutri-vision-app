"""
Secondary food classifier using EfficientNet-B3.

Invoked by the pipeline when YOLO detection confidence < 0.6 to provide
a second opinion on the food label. If the classifier's top-1 confidence
exceeds YOLO's, the classifier label wins.

Falls back gracefully to returning the YOLO label unchanged when:
  - Model weights are not present
  - Inference errors out (e.g., wrong ONNX opset)
  - Input image is invalid
"""

import os
import logging
import numpy as np
from typing import Tuple, Optional

log = logging.getLogger(__name__)

# Path to the ONNX weights produced by train_classifier.py
# train_classifier.py exports to: models/weights/food_classifier_best.onnx
_DEFAULT_WEIGHTS = os.path.join(
    os.path.dirname(__file__), "..", "models", "weights", "food_classifier_best.onnx"
)

# Labels file: JSON list produced by train_classifier.py
# train_classifier.py saves: models/weights/food_classifier_classes.json
_DEFAULT_LABELS = os.path.join(
    os.path.dirname(__file__), "..", "models", "weights", "food_classifier_classes.json"
)

# Input shape expected by the EfficientNet ONNX export: [1, 3, 300, 300] BGR
_INPUT_H = 300
_INPUT_W = 300

# ImageNet normalisation (used during training via torchvision transforms)
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32)


class SecondaryClassifier:
    """
    ONNX Runtime EfficientNet-B3 classifier.

    Usage:
        clf = SecondaryClassifier()
        clf.load()
        label, conf = clf.classify(crop_bgr)
    """

    def __init__(
        self,
        weights_path: str = _DEFAULT_WEIGHTS,
        labels_path:  str = _DEFAULT_LABELS,
    ):
        self._weights_path = weights_path
        self._labels_path  = labels_path
        self._session      = None
        self._labels: list[str] = []
        self._ready = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def load(self) -> None:
        """Load ONNX model and class labels. Silent no-op if weights missing."""
        if not os.path.exists(self._weights_path):
            log.warning(
                "EfficientNet weights not found at %s — secondary classifier disabled.",
                self._weights_path,
            )
            return

        try:
            import onnxruntime as ort  # type: ignore

            opts = ort.SessionOptions()
            opts.inter_op_num_threads = 2
            opts.intra_op_num_threads = 2
            self._session = ort.InferenceSession(
                self._weights_path,
                sess_options=opts,
                providers=["CPUExecutionProvider"],
            )
            log.info("EfficientNet-B3 classifier loaded from %s", self._weights_path)
        except Exception as exc:
            log.error("Failed to load EfficientNet ONNX session: %s", exc)
            return

        # Load label list — train_classifier.py saves a JSON array, not a plain text file
        if os.path.exists(self._labels_path):
            try:
                import json
                with open(self._labels_path) as f:
                    self._labels = json.load(f)
                if not isinstance(self._labels, list):
                    raise ValueError("Expected a JSON list of class names")
            except Exception as exc:
                log.warning("Could not load labels from %s: %s — using numeric class IDs.", self._labels_path, exc)
                self._labels = []
        else:
            log.warning("Labels file not found at %s — using numeric class IDs.", self._labels_path)

        self._ready = True

    # ── Inference ─────────────────────────────────────────────────────────────

    def classify(self, crop_bgr: np.ndarray) -> Tuple[str, float]:
        """
        Classify a single food crop.

        Args:
            crop_bgr: uint8 BGR image cropped to the food item bounding box.

        Returns:
            (label, confidence) — confidence is in [0, 1].
            If the classifier is unavailable returns ("unknown", 0.0).
        """
        if not self._ready or self._session is None:
            return "unknown", 0.0

        try:
            tensor = self._preprocess(crop_bgr)
            input_name = self._session.get_inputs()[0].name
            logits = self._session.run(None, {input_name: tensor})[0][0]  # shape (num_classes,)
            probs  = _softmax(logits)
            top_idx  = int(np.argmax(probs))
            top_conf = float(probs[top_idx])
            label    = self._labels[top_idx] if top_idx < len(self._labels) else str(top_idx)
            return label, top_conf
        except Exception as exc:
            log.debug("EfficientNet inference failed: %s", exc)
            return "unknown", 0.0

    def classify_detections(
        self,
        image_bgr: np.ndarray,
        detections: list[dict],
        yolo_conf_threshold: float = 0.6,
    ) -> list[dict]:
        """
        Re-classify any detection whose YOLO confidence is below the threshold.

        Args:
            image_bgr: Full BGR image.
            detections: List of YOLO detection dicts with keys:
                        label, confidence, bbox [x1, y1, x2, y2].
            yolo_conf_threshold: Below this confidence, run the classifier.

        Returns:
            Updated detections list (same length, possibly with relabelled items).
        """
        if not self._ready:
            return detections

        updated = []
        for det in detections:
            if det.get("confidence", 1.0) >= yolo_conf_threshold:
                updated.append(det)
                continue

            bbox = det.get("bbox")
            if bbox is None:
                updated.append(det)
                continue

            x1, y1, x2, y2 = [int(v) for v in bbox]
            h, w = image_bgr.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)

            if x2 <= x1 or y2 <= y1:
                updated.append(det)
                continue

            crop = image_bgr[y1:y2, x1:x2]
            clf_label, clf_conf = self.classify(crop)

            if clf_label != "unknown" and clf_conf > det["confidence"]:
                log.debug(
                    "Secondary classifier overrode '%s' (%.2f) → '%s' (%.2f)",
                    det["label"], det["confidence"], clf_label, clf_conf,
                )
                updated.append({
                    **det,
                    "label":      clf_label,
                    "confidence": clf_conf,
                    "classified_by": "efficientnet",
                })
            else:
                updated.append(det)

        return updated

    # ── Private ───────────────────────────────────────────────────────────────

    def _preprocess(self, bgr: np.ndarray) -> np.ndarray:
        """Resize → RGB → normalise → NCHW float32 tensor."""
        import cv2  # type: ignore
        rgb = cv2.cvtColor(
            cv2.resize(bgr, (_INPUT_W, _INPUT_H), interpolation=cv2.INTER_LINEAR),
            cv2.COLOR_BGR2RGB,
        ).astype(np.float32) / 255.0
        rgb = (rgb - _MEAN) / _STD
        # HWC → NCHW
        return rgb.transpose(2, 0, 1)[np.newaxis, ...]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - np.max(x))
    return e / e.sum()
