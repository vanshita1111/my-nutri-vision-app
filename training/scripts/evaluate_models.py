"""
Evaluate trained food detection and calorie estimation models.

Reports: mAP@0.5, mAP@0.5:0.95, per-class precision/recall, calorie MAE.

Usage:
    # YOLO validation only (default):
    python training/scripts/evaluate_models.py

    # + end-to-end calorie MAE on Nutrition5K:
    python training/scripts/evaluate_models.py --calorie-eval

Prerequisites:
    pip install ultralytics numpy
    Nutrition5K test labels CSV at training/data/nutrition5k/test_labels.csv
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
# nutrition_engine lives at the project root; backend app is under backend/.
# Both must be on sys.path so this script can import from either package.
_SCRIPTS_DIR  = Path(__file__).parent          # training/scripts/
_TRAINING_DIR = _SCRIPTS_DIR.parent            # training/
_PROJECT_ROOT = _TRAINING_DIR.parent           # project root (nutrition_engine is here)
_BACKEND_DIR  = _PROJECT_ROOT / "backend"      # backend/app is here

for _p in (_PROJECT_ROOT, _BACKEND_DIR):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

# ── Default paths (absolute, __file__-relative so CWD doesn't matter) ────────
_DEFAULT_MODEL    = str(_PROJECT_ROOT / "models" / "weights" / "food_detector_v1.pt")
_DEFAULT_DATA     = str(_TRAINING_DIR / "data" / "food_dataset.yaml")
_DEFAULT_IMGS     = str(_TRAINING_DIR / "data" / "nutrition5k" / "images")
_DEFAULT_N5K_CSV  = str(_TRAINING_DIR / "data" / "nutrition5k" / "test_labels.csv")
_RESULTS_PATH     = _TRAINING_DIR / "experiments" / "eval_results.json"


# ── YOLO evaluation ───────────────────────────────────────────────────────────

def evaluate_yolo(model_path: str, data_yaml: str, imgsz: int = 640, device: str = "cpu"):
    """Run YOLO validation and print / save metrics."""
    try:
        from ultralytics import YOLO
    except ImportError:
        print("ultralytics not installed. Run: pip install ultralytics")
        return None

    if not Path(model_path).exists():
        print(f"ERROR: model not found at {model_path}")
        print("Train first: make train-detector")
        return None

    if not Path(data_yaml).exists():
        print(f"ERROR: dataset YAML not found at {data_yaml}")
        print("Prepare first: make prepare-dataset")
        return None

    print(f"\nEvaluating YOLO model: {model_path}")
    print(f"Dataset: {data_yaml}\n")

    model = YOLO(model_path)
    metrics = model.val(data=data_yaml, imgsz=imgsz, device=device, verbose=True)

    print("\n" + "=" * 60)
    print("YOLO Validation Metrics")
    print("=" * 60)
    print(f"  mAP@0.5:      {metrics.box.map50:.4f}")
    print(f"  mAP@0.5:0.95: {metrics.box.map:.4f}")
    print(f"  Precision:    {metrics.box.mp:.4f}")
    print(f"  Recall:       {metrics.box.mr:.4f}")

    result_data = {
        "model": model_path,
        "map50": float(metrics.box.map50),
        "map":   float(metrics.box.map),
        "precision": float(metrics.box.mp),
        "recall":    float(metrics.box.mr),
    }

    _RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _RESULTS_PATH.write_text(json.dumps(result_data, indent=2))
    print(f"\nResults saved to {_RESULTS_PATH}")
    return metrics


# ── End-to-end calorie MAE evaluation ────────────────────────────────────────

async def _run_calorie_eval(model_path: str, test_images_dir: str, labels_csv: str):
    """Async core: load pipeline once, run every test image."""
    import csv

    try:
        import numpy as np
    except ImportError:
        print("numpy not installed. Run: pip install numpy")
        return

    from app.config import settings
    settings.DEVICE = "cpu"

    from nutrition_engine.pipeline import NutritionPipeline

    labels_path = Path(labels_csv)
    if not labels_path.exists():
        print(f"Nutrition5K test labels not found at {labels_path}")
        print("Download Nutrition5K and place test_labels.csv there.")
        return

    pipeline = NutritionPipeline(device="cpu")
    await pipeline.load_models()

    true_cals, pred_cals, errors = [], [], []

    with open(labels_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            img_path = Path(test_images_dir) / row["image_filename"]
            if not img_path.exists():
                continue
            true_cal = float(row["total_calories"])
            try:
                result = await pipeline.analyze(str(img_path))
                pred_cal = result["total"]["calories"]
                err = abs(true_cal - pred_cal)
                true_cals.append(true_cal)
                pred_cals.append(pred_cal)
                errors.append(err)
                print(f"  {row['image_filename']}: true={true_cal:.0f}  pred={pred_cal:.0f}  err={err:.0f}")
            except Exception as exc:
                print(f"  ERROR on {row['image_filename']}: {exc}")

    if not errors:
        print("No results — check that images exist and the pipeline ran without errors.")
        return

    errors_arr = np.array(errors)
    print(f"\n{'=' * 60}")
    print(f"Calorie Estimation Results  (n={len(errors)})")
    print(f"  MAE:    {np.mean(errors_arr):.1f} kcal")
    print(f"  Median: {np.median(errors_arr):.1f} kcal")
    print(f"  P90:    {np.percentile(errors_arr, 90):.1f} kcal")
    print(f"  RMSE:   {np.sqrt(np.mean(errors_arr ** 2)):.1f} kcal")

    cal_result = {
        "n": len(errors),
        "mae":    float(np.mean(errors_arr)),
        "median": float(np.median(errors_arr)),
        "p90":    float(np.percentile(errors_arr, 90)),
        "rmse":   float(np.sqrt(np.mean(errors_arr ** 2))),
    }

    if _RESULTS_PATH.exists():
        existing = json.loads(_RESULTS_PATH.read_text())
        existing["calorie_eval"] = cal_result
        _RESULTS_PATH.write_text(json.dumps(existing, indent=2))
    else:
        _RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _RESULTS_PATH.write_text(json.dumps({"calorie_eval": cal_result}, indent=2))

    print(f"\nCalorie eval results appended to {_RESULTS_PATH}")


def evaluate_calorie_mae(model_path: str, test_images_dir: str, labels_csv: str):
    """Synchronous entry point: runs the async evaluation in a fresh event loop."""
    asyncio.run(_run_calorie_eval(model_path, test_images_dir, labels_csv))


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate NutriVision models")
    parser.add_argument("--model",        default=_DEFAULT_MODEL,
                        help="Path to YOLO .pt or .onnx model")
    parser.add_argument("--data",         default=_DEFAULT_DATA,
                        help="Path to dataset YAML")
    parser.add_argument("--imgsz",        default=640, type=int,
                        help="Inference image size")
    parser.add_argument("--device",       default="cpu",
                        help="'cpu' or GPU index e.g. '0'")
    parser.add_argument("--calorie-eval", action="store_true",
                        help="Run end-to-end calorie MAE on Nutrition5K")
    parser.add_argument("--test-images",  default=_DEFAULT_IMGS,
                        help="Directory of Nutrition5K test images")
    parser.add_argument("--labels-csv",   default=_DEFAULT_N5K_CSV,
                        help="Nutrition5K test_labels.csv path")
    args = parser.parse_args()

    evaluate_yolo(args.model, args.data, imgsz=args.imgsz, device=args.device)

    if args.calorie_eval:
        evaluate_calorie_mae(args.model, args.test_images, args.labels_csv)
