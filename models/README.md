# Model Weights

This directory stores trained model weights. Files are **not committed to git** (see .gitignore).

## Directory layout

```
models/
├── weights/
│   ├── food_detector_v1.pt          ← YOLOv8 PyTorch checkpoint (fine-tuned)
│   ├── food_detector_v1.onnx        ← ONNX export for inference
│   ├── food_classifier_best.pt      ← EfficientNet-B3 checkpoint
│   ├── food_classifier_best.onnx    ← ONNX export
│   ├── food_classifier_classes.json ← Class name list (101 classes)
│   └── sam2_hiera_large.pt          ← SAM2 weights (download separately)
└── configs/
    └── food_dataset.yaml            ← YOLO training config
```

## Downloading / obtaining weights

### YOLOv8 base weights (auto-download)
```bash
make download-models
# Downloads yolov8x.pt from Ultralytics
```

### Fine-tuned food detector
After downloading Food-101 and running `prepare_dataset.py`:
```bash
make train-detector       # ~8h on T4 GPU / ~24h on CPU
```

### SAM2 weights
```bash
# Download from Meta AI
wget https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_large.pt \
     -O models/weights/sam2_hiera_large.pt
```

### Depth Anything v2
Downloaded automatically from HuggingFace on first inference.
Model ID: `depth-anything/Depth-Anything-V2-Small-hf` (default, CPU-friendly)
Upgrade to Large for better accuracy on GPU: set `DEPTH_MODEL_ID` in `.env`.

---

## Model cards

### food_detector_v1 (YOLOv8m)
| Metric         | Value     |
|----------------|-----------|
| Base model     | YOLOv8m   |
| Dataset        | UECFood256 + Food-101 |
| Input size     | 640×640   |
| mAP@0.5        | TBD (update after training) |
| mAP@0.5:0.95   | TBD       |
| Inference time | ~15ms GPU / ~200ms CPU |

### food_classifier_best (EfficientNet-B3)
| Metric      | Value     |
|-------------|-----------|
| Base model  | EfficientNet-B3 (ImageNet) |
| Dataset     | Food-101  |
| Classes     | 101       |
| Top-1 acc   | TBD       |
| Top-5 acc   | TBD       |
| Input size  | 300×300   |

---

## Version history

| Version | Date       | Change                        |
|---------|------------|-------------------------------|
| v1.0    | 2026-01-01 | Initial YOLOv8m + EfficientNet |
