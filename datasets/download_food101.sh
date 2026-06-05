#!/usr/bin/env bash
# Download Food-101 dataset (~4.6 GB)
# Usage: bash datasets/download_food101.sh

set -euo pipefail

DEST="training/data/food101"
URL="http://data.vision.ee.ethz.ch/cvl/food-101.tar.gz"
ARCHIVE="$DEST/food-101.tar.gz"

mkdir -p "$DEST"

if [ -f "$ARCHIVE" ]; then
  echo "Archive already exists at $ARCHIVE — skipping download."
else
  echo "Downloading Food-101 (~4.6 GB)..."
  curl -L --progress-bar -o "$ARCHIVE" "$URL"
  echo "Download complete."
fi

echo "Extracting..."
tar -xzf "$ARCHIVE" -C "$DEST"
echo "Extracted to $DEST/food-101/"

echo ""
echo "Next step: run the dataset preparation script to convert to YOLO format:"
echo "  python training/scripts/prepare_dataset.py --dataset food101"
