"""
Monocular depth estimator using Depth Anything v2 (HuggingFace pipeline).
Returns a normalised depth map (0 = far, 1 = close to camera).
Falls back to a flat uniform depth when the model is not available.
"""

import numpy as np


class DepthEstimator:
    def __init__(self, device: str = "cpu", model_id: str = "depth-anything/Depth-Anything-V2-Small-hf"):
        self.device = device
        self.model_id = model_id
        self._pipeline = None
        self._available = False

    def load(self):
        try:
            from transformers import pipeline as hf_pipeline
            self._pipeline = hf_pipeline(
                task="depth-estimation",
                model=self.model_id,
                device=0 if self.device == "cuda" else -1,
            )
            self._available = True
            print(f"[DepthEstimator] Loaded {self.model_id}")
        except Exception as e:
            print(f"[DepthEstimator] Could not load model ({e}). Using flat depth fallback.")
            self._available = False

    def estimate(self, image_bgr: np.ndarray) -> np.ndarray:
        """
        Args:
            image_bgr: Preprocessed BGR numpy array (H×W×3, uint8) — the same
                       image used for detection/segmentation so shapes match.

        Returns a 2D float32 array of shape (H, W) with values in [0, 1].
        0 = background / far, 1 = foreground / close to camera.
        """
        if not self._available or self._pipeline is None:
            return self._flat_depth(image_bgr)

        from PIL import Image as PILImage
        rgb = image_bgr[:, :, ::-1]  # BGR → RGB
        pil_img = PILImage.fromarray(rgb)

        result = self._pipeline(pil_img)
        depth_raw = np.array(result["depth"], dtype=np.float32)

        # Resize depth map to match input image shape (model may downsample internally)
        h, w = image_bgr.shape[:2]
        if depth_raw.shape != (h, w):
            import cv2
            depth_raw = cv2.resize(depth_raw, (w, h), interpolation=cv2.INTER_LINEAR)

        # Normalise to [0, 1]
        d_min, d_max = depth_raw.min(), depth_raw.max()
        if d_max - d_min < 1e-6:
            return np.ones_like(depth_raw) * 0.5

        depth_norm = (depth_raw - d_min) / (d_max - d_min)
        return depth_norm

    @staticmethod
    def _flat_depth(image_bgr: np.ndarray) -> np.ndarray:
        """Uniform 0.5 depth — volume estimation will fall back to prior-based estimation."""
        h, w = image_bgr.shape[:2]
        return np.ones((h, w), dtype=np.float32) * 0.5
