"""
Fine-tune YOLOv8 on food detection dataset.

Usage:
    python training/scripts/train_detector.py [--model yolov8m.pt] [--epochs 100]

Prerequisites:
    pip install ultralytics
    Place dataset in training/data/ following YOLO format (images/, labels/, food_dataset.yaml)
"""

import argparse
import shutil
from pathlib import Path

try:
    from ultralytics import YOLO
except ImportError:
    raise SystemExit("ultralytics not installed. Run: pip install ultralytics")


# All paths are resolved relative to this file so the script works regardless
# of the working directory (Makefile does `cd training && python scripts/...`).
_SCRIPTS_DIR = Path(__file__).parent          # training/scripts/
_TRAINING_DIR = _SCRIPTS_DIR.parent           # training/
_PROJECT_ROOT = _TRAINING_DIR.parent          # project root

DEFAULT_YAML = _TRAINING_DIR / "data" / "food_dataset.yaml"
WEIGHTS_DIR  = _PROJECT_ROOT / "models" / "weights"


def train(
    model_size: str = "yolov8m.pt",
    data_yaml: str = str(DEFAULT_YAML),
    epochs: int = 100,
    imgsz: int = 640,
    batch: int = 16,
    device: str = "cpu",
    project: str = str(_TRAINING_DIR / "experiments"),
    name: str = "food_detector_v1",
):
    print(f"\n{'='*60}")
    print(f"Training YOLOv8 food detector")
    print(f"  Model:   {model_size}")
    print(f"  Data:    {data_yaml}")
    print(f"  Epochs:  {epochs}")
    print(f"  Device:  {device}")
    print(f"{'='*60}\n")

    if not Path(data_yaml).exists():
        print(f"ERROR: Dataset YAML not found at {data_yaml}")
        print("Run: python training/scripts/prepare_dataset.py first")
        return None

    model = YOLO(model_size)

    results = model.train(
        data=data_yaml,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        project=project,
        name=name,
        patience=20,
        lr0=0.001,
        lrf=0.01,
        momentum=0.937,
        weight_decay=0.0005,
        warmup_epochs=3,
        augment=True,
        mixup=0.1,
        copy_paste=0.1,
        degrees=10,
        translate=0.1,
        scale=0.5,
        flipud=0.0,
        fliplr=0.5,
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,
        save=True,
        plots=True,
    )

    # Export best model to ONNX
    best_pt = Path(project) / name / "weights" / "best.pt"
    if best_pt.exists():
        print(f"\nExporting to ONNX...")
        best_model = YOLO(str(best_pt))
        # simplify=True requires onnxsim; skip gracefully if not installed
        try:
            best_model.export(format="onnx", imgsz=imgsz, simplify=True)
        except Exception:
            best_model.export(format="onnx", imgsz=imgsz, simplify=False)

        # Copy to models/weights/
        WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy(str(best_pt), str(WEIGHTS_DIR / "food_detector_v1.pt"))
        onnx_src = best_pt.parent / "best.onnx"
        if onnx_src.exists():
            shutil.copy(str(onnx_src), str(WEIGHTS_DIR / "food_detector_v1.onnx"))
        print(f"Weights saved to {WEIGHTS_DIR}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train YOLOv8 food detector")
    parser.add_argument("--model",   default="yolov8m.pt",   help="Model variant (yolov8n/s/m/l/x.pt)")
    parser.add_argument("--epochs",  default=100, type=int,  help="Training epochs")
    parser.add_argument("--batch",   default=16,  type=int,  help="Batch size")
    parser.add_argument("--imgsz",   default=640, type=int,  help="Image size")
    parser.add_argument("--device",  default="cpu",           help="'cpu' or '0' for GPU 0")
    parser.add_argument("--data",    default=str(DEFAULT_YAML), help="Path to dataset YAML")
    args = parser.parse_args()

    train(
        model_size=args.model,
        data_yaml=args.data,
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        device=args.device,
    )
