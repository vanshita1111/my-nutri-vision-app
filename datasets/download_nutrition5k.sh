#!/usr/bin/env bash
# Download Nutrition5K dataset from Google Research (~6 GB)
# Requires gsutil (Google Cloud SDK) and access approval.
#
# Access request: https://github.com/google-research/nutrition5k
# Usage: bash datasets/download_nutrition5k.sh

set -euo pipefail

DEST="training/data/nutrition5k"
GCS_PATH="gs://nutrition5k_dataset"

mkdir -p "$DEST"

# Check for gsutil
if ! command -v gsutil &> /dev/null; then
  echo "gsutil not found. Install Google Cloud SDK:"
  echo "  https://cloud.google.com/sdk/docs/install"
  echo ""
  echo "Or use the Python download script:"
  echo "  python datasets/download_nutrition5k_py.py"
  exit 1
fi

echo "Downloading Nutrition5K from Google Cloud Storage..."
echo "(This requires access approval at: https://github.com/google-research/nutrition5k)"
echo ""

gsutil -m cp -r "$GCS_PATH/nutrition5k_dataset_metadata_ingredients_only.csv" "$DEST/"
gsutil -m cp -r "$GCS_PATH/imagery/realsense_overhead/"                       "$DEST/images/"

echo ""
echo "Download complete. Files at: $DEST"
echo ""
echo "Dataset structure:"
echo "  $DEST/nutrition5k_dataset_metadata_ingredients_only.csv  ← labels"
echo "  $DEST/images/                                             ← RGBD images"
echo ""
echo "Next step: use evaluate_models.py with --calorie-eval flag"
