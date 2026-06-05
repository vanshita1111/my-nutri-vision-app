"""
Dataset preparation: downloads Food-101 and UECFood256, converts to YOLO / ImageFolder format.

Usage:
    python training/scripts/prepare_dataset.py --dataset food101
    python training/scripts/prepare_dataset.py --dataset uecfood256
    python training/scripts/prepare_dataset.py --dataset all

Output layout (Food-101):
    training/data/food101/
        images/
            train/
                apple_pie/          ← class subdirectory (ImageFolder-compatible)
                    img1.jpg
                    ...
                baby_back_ribs/
                    ...
            val/
                apple_pie/
                    ...
        labels/
            train/
                apple_pie_img1.txt  ← YOLO bbox labels (whole image = 0.5 0.5 1.0 1.0)
            val/
                ...
        food_dataset.yaml

Note: `pyyaml` must be installed to run build_combined_yaml()
    pip install pyyaml
"""

import argparse
import shutil
import tarfile
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


def prepare_food101() -> list:
    """Download Food-101 and convert to ImageFolder + YOLO format."""
    print("Preparing Food-101...")
    food101_dir = DATA_DIR / "food101"
    food101_dir.mkdir(parents=True, exist_ok=True)

    tar_path = food101_dir / "food-101.tar.gz"
    if not tar_path.exists():
        print("Downloading Food-101 (~4.6 GB) — this will take a while...")
        url = "https://data.vision.ee.ethz.ch/cvl/food-101.tar.gz"
        urllib.request.urlretrieve(url, tar_path, reporthook=_progress_hook)
        print()  # newline after progress bar

    print("Extracting...")
    with tarfile.open(tar_path) as f:
        f.extractall(food101_dir)

    src = food101_dir / "food-101" / "images"
    classes = sorted([d.name for d in src.iterdir() if d.is_dir()])

    # Create output directories
    for split in ("train", "val"):
        for cls in classes:
            # ImageFolder layout: images/<split>/<class>/
            (food101_dir / "images" / split / cls).mkdir(parents=True, exist_ok=True)
        (food101_dir / "labels" / split).mkdir(parents=True, exist_ok=True)

    meta_dir = food101_dir / "food-101" / "meta"
    with open(meta_dir / "train.txt") as f:
        train_files = [line.strip() for line in f]
    with open(meta_dir / "test.txt") as f:
        val_files = [line.strip() for line in f]

    def _process(file_list: list, split: str) -> None:
        for entry in file_list:
            cls_name, img_stem = entry.split("/")
            class_id = classes.index(cls_name)
            src_img = src / cls_name / f"{img_stem}.jpg"
            if not src_img.exists():
                continue

            # Image goes into class subdirectory (required by datasets.ImageFolder)
            dst_img = food101_dir / "images" / split / cls_name / f"{img_stem}.jpg"
            shutil.copy(src_img, dst_img)

            # YOLO label: class cx cy w h (whole image bounding box for classification tasks)
            dst_lbl = food101_dir / "labels" / split / f"{cls_name}_{img_stem}.txt"
            dst_lbl.write_text(f"{class_id} 0.5 0.5 1.0 1.0\n")

    print(f"Organising {len(train_files)} train / {len(val_files)} val images...")
    _process(train_files, "train")
    _process(val_files, "val")

    yaml_text = _build_yaml(str(food101_dir), classes)
    (food101_dir / "food_dataset.yaml").write_text(yaml_text)
    print(f"Food-101 ready at {food101_dir}  ({len(classes)} classes)")
    return classes


def prepare_uecfood256() -> None:
    """Convert UECFood256 to YOLO detection format (has bounding-box annotations)."""
    print("\nPreparing UECFood256...")
    uec_dir = DATA_DIR / "uecfood256"
    uec_dir.mkdir(parents=True, exist_ok=True)
    print("UECFood256 requires manual download.")
    print("  1. Visit: http://foodcam.mobi/dataset256.html")
    print(f"  2. Place the extracted folder at: {uec_dir}")
    print("  Skipping automatic download.")


def _build_yaml(data_path: str, classes: list) -> str:
    """Build a YOLO dataset YAML string."""
    lines = [
        f"path: {data_path}",
        "train: images/train",
        "val: images/val",
        "",
        f"nc: {len(classes)}",
        "names:",
    ]
    for cls in classes:
        lines.append(f"  - {cls}")
    return "\n".join(lines) + "\n"


def build_combined_yaml() -> None:
    """Merge class lists from all prepared datasets into a single YAML."""
    try:
        import yaml  # pip install pyyaml
    except ImportError:
        print("WARNING: pyyaml not installed — skipping combined YAML. Run: pip install pyyaml")
        return

    all_classes: set = set()
    for candidate_yaml in [DATA_DIR / "food101" / "food_dataset.yaml"]:
        if candidate_yaml.exists():
            with open(candidate_yaml) as f:
                d = yaml.safe_load(f)
                all_classes.update(d.get("names", []))

    if not all_classes:
        print("No datasets found — skipping combined YAML.")
        return

    classes = sorted(all_classes)
    yaml_content = _build_yaml(str(DATA_DIR), classes)
    combined = DATA_DIR / "food_dataset.yaml"
    combined.write_text(yaml_content)
    print(f"Combined YAML: {len(classes)} classes → {combined}")


def _progress_hook(block_num: int, block_size: int, total_size: int) -> None:
    """Simple download progress indicator."""
    downloaded = block_num * block_size
    if total_size > 0:
        pct = min(100, downloaded * 100 / total_size)
        mb = downloaded / 1_048_576
        total_mb = total_size / 1_048_576
        print(f"\r  {pct:.1f}%  {mb:.0f} / {total_mb:.0f} MB", end="", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare food detection/classification datasets")
    parser.add_argument(
        "--dataset",
        choices=["food101", "uecfood256", "all"],
        default="food101",
        help="Which dataset to prepare",
    )
    args = parser.parse_args()

    if args.dataset in ("food101", "all"):
        prepare_food101()
    if args.dataset in ("uecfood256", "all"):
        prepare_uecfood256()

    build_combined_yaml()
    print("\nDataset preparation complete. Run: make train-detector")
