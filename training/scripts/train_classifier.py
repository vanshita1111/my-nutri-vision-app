"""
Fine-tune EfficientNet-B3 on Food-101 as a secondary food classifier.

This model is used when YOLO confidence < 0.6 to verify the food label,
and as the primary classifier for zero-shot/rare Indian foods via the last
layer + CLIP embeddings.

Architecture:
  - EfficientNet-B3 backbone (ImageNet pretrained)
  - Frozen layers 0..5, trainable layers 6+ (transfer learning)
  - Custom head: AdaptiveAvgPool → Dropout(0.3) → Linear(1536 → n_classes)
  - Training: AdamW + CosineAnnealingLR + MixUp augmentation

Usage:
    python training/scripts/train_classifier.py [--epochs 50] [--device cpu]

Prerequisites:
    pip install torch torchvision timm
    python training/scripts/prepare_dataset.py --dataset food101
"""

import argparse
import json
import time
from pathlib import Path

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader
    from torchvision import datasets, transforms
    from torchvision.models import efficientnet_b3, EfficientNet_B3_Weights
except ImportError:
    raise SystemExit("PyTorch not installed. Run: pip install torch torchvision")


_SCRIPTS_DIR = Path(__file__).parent
_TRAINING_DIR = _SCRIPTS_DIR.parent
_PROJECT_ROOT = _TRAINING_DIR.parent

DATA_DIR    = _TRAINING_DIR / "data" / "food101"
OUTPUT_DIR  = _TRAINING_DIR / "experiments" / "classifier"
WEIGHTS_DIR = _PROJECT_ROOT / "models" / "weights"


def build_model(n_classes: int, freeze_backbone: bool = True) -> nn.Module:
    """EfficientNet-B3 with custom classification head."""
    model = efficientnet_b3(weights=EfficientNet_B3_Weights.IMAGENET1K_V1)

    if freeze_backbone:
        # Freeze first 6 feature blocks, train last 2 + head
        for name, param in model.features.named_parameters():
            block = int(name.split(".")[0])
            param.requires_grad = block >= 6

    # Replace classifier head.
    # NOTE: EfficientNet's forward() calls self.avgpool then torch.flatten BEFORE
    # passing to self.classifier, so the classifier receives a 1-D vector.
    # Do NOT add AdaptiveAvgPool2d or Flatten here — they would crash on 1-D input.
    in_features = model.classifier[1].in_features   # 1536 for B3
    model.classifier = nn.Sequential(
        nn.Dropout(p=0.3),
        nn.Linear(in_features, n_classes),
    )
    return model


def get_transforms(train: bool, img_size: int = 300):
    if train:
        return transforms.Compose([
            transforms.RandomResizedCrop(img_size, scale=(0.7, 1.0)),
            transforms.RandomHorizontalFlip(),
            transforms.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.3, hue=0.05),
            transforms.RandomRotation(15),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])
    return transforms.Compose([
        transforms.Resize(int(img_size * 1.14)),
        transforms.CenterCrop(img_size),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])


def mixup_data(x, y, alpha=0.2):
    """Apply MixUp augmentation to a batch."""
    if alpha > 0:
        lam = torch.distributions.Beta(alpha, alpha).sample().item()
    else:
        lam = 1.0
    idx = torch.randperm(x.size(0), device=x.device)
    mixed_x = lam * x + (1 - lam) * x[idx]
    y_a, y_b = y, y[idx]
    return mixed_x, y_a, y_b, lam


def mixup_criterion(criterion, pred, y_a, y_b, lam):
    return lam * criterion(pred, y_a) + (1 - lam) * criterion(pred, y_b)


def train_one_epoch(model, loader, criterion, optimizer, device, use_mixup=True):
    model.train()
    total_loss, correct, total = 0.0, 0, 0

    for images, labels in loader:
        images, labels = images.to(device), labels.to(device)

        if use_mixup:
            images, y_a, y_b, lam = mixup_data(images, labels)
            outputs = model(images)
            loss = mixup_criterion(criterion, outputs, y_a, y_b, lam)
        else:
            outputs = model(images)
            loss = criterion(outputs, labels)

        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()

        total_loss += loss.item() * images.size(0)
        _, predicted = outputs.max(1)
        correct += predicted.eq(labels).sum().item()
        total   += labels.size(0)

    return total_loss / total, correct / total


@torch.no_grad()
def validate(model, loader, criterion, device):
    model.eval()
    total_loss, correct, top5_correct, total = 0.0, 0, 0, 0

    for images, labels in loader:
        images, labels = images.to(device), labels.to(device)
        outputs = model(images)
        loss = criterion(outputs, labels)

        total_loss += loss.item() * images.size(0)
        _, top1_pred = outputs.max(1)
        correct += top1_pred.eq(labels).sum().item()

        _, top5_pred = outputs.topk(5, 1)
        top5_correct += top5_pred.eq(labels.view(-1, 1).expand_as(top5_pred)).any(1).sum().item()
        total += labels.size(0)

    return total_loss / total, correct / total, top5_correct / total


def train(
    data_dir: str   = str(DATA_DIR),
    epochs: int     = 50,
    batch: int      = 32,
    lr: float       = 3e-4,
    device_str: str = "cpu",
    img_size: int   = 300,
    workers: int    = 4,
):
    device = torch.device(device_str if torch.cuda.is_available() or device_str == "cpu" else "cpu")
    print(f"\n{'='*60}")
    print(f"EfficientNet-B3 Food Classifier Training")
    print(f"  Data:    {data_dir}")
    print(f"  Epochs:  {epochs}")
    print(f"  Device:  {device}")
    print(f"{'='*60}\n")

    train_dir = Path(data_dir) / "images" / "train"
    val_dir   = Path(data_dir) / "images" / "val"

    if not train_dir.exists():
        print(f"Training data not found at {train_dir}")
        print("Run: python training/scripts/prepare_dataset.py --dataset food101")
        return

    train_ds = datasets.ImageFolder(str(train_dir), transform=get_transforms(True,  img_size))
    val_ds   = datasets.ImageFolder(str(val_dir),   transform=get_transforms(False, img_size))

    n_classes = len(train_ds.classes)
    print(f"Classes: {n_classes} | Train: {len(train_ds)} | Val: {len(val_ds)}")

    train_loader = DataLoader(train_ds, batch_size=batch, shuffle=True,  num_workers=workers, pin_memory=True)
    val_loader   = DataLoader(val_ds,   batch_size=batch, shuffle=False, num_workers=workers, pin_memory=True)

    model = build_model(n_classes, freeze_backbone=True).to(device)

    # Count trainable parameters
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total     = sum(p.numel() for p in model.parameters())
    print(f"Parameters: {trainable:,} trainable / {total:,} total")

    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
    optimizer = optim.AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=lr, weight_decay=1e-4
    )
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)

    best_top1 = 0.0
    history   = []

    # Phase 2: unfreeze full backbone at halfway
    unfreeze_epoch = epochs // 2

    for epoch in range(1, epochs + 1):
        # Unfreeze backbone at midpoint, reduce LR
        if epoch == unfreeze_epoch:
            print(f"\n[Epoch {epoch}] Unfreezing full backbone...")
            for param in model.parameters():
                param.requires_grad = True
            # Re-init optimizer with lower LR for fine-tuning
            optimizer = optim.AdamW(model.parameters(), lr=lr / 10, weight_decay=1e-4)
            scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs - epoch, eta_min=1e-6)

        t0 = time.time()
        train_loss, train_acc = train_one_epoch(model, train_loader, criterion, optimizer, device)
        val_loss,   val_acc, val_top5 = validate(model, val_loader, criterion, device)
        scheduler.step()
        elapsed = time.time() - t0

        lr_now = optimizer.param_groups[0]["lr"]
        print(
            f"Epoch [{epoch:3d}/{epochs}] "
            f"loss={train_loss:.4f} acc={train_acc:.4f} | "
            f"val_loss={val_loss:.4f} val_top1={val_acc:.4f} val_top5={val_top5:.4f} | "
            f"lr={lr_now:.2e} | {elapsed:.1f}s"
        )

        history.append({
            "epoch": epoch, "train_loss": train_loss, "train_acc": train_acc,
            "val_loss": val_loss, "val_top1": val_acc, "val_top5": val_top5,
        })

        # Save best
        if val_acc > best_top1:
            best_top1 = val_acc
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_top1": val_acc,
                "classes": train_ds.classes,
            }, WEIGHTS_DIR / "food_classifier_best.pt")
            print(f"  ✓ New best top-1: {best_top1:.4f} — saved")

    # Save training history
    (OUTPUT_DIR / "classifier_history.json").write_text(json.dumps(history, indent=2))

    # Export to ONNX
    print("\nExporting best model to ONNX...")
    ckpt = torch.load(WEIGHTS_DIR / "food_classifier_best.pt", map_location="cpu")
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()
    dummy = torch.randn(1, 3, img_size, img_size)
    torch.onnx.export(
        model, dummy,
        str(WEIGHTS_DIR / "food_classifier_best.onnx"),
        opset_version=17,
        input_names=["image"],
        output_names=["logits"],
        dynamic_axes={"image": {0: "batch"}},
    )

    # Save class names
    (WEIGHTS_DIR / "food_classifier_classes.json").write_text(
        json.dumps(train_ds.classes)
    )

    print(f"\nDone! Best val top-1: {best_top1:.4f}")
    print(f"Weights: {WEIGHTS_DIR}/food_classifier_best.pt")
    print(f"ONNX:    {WEIGHTS_DIR}/food_classifier_best.onnx")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train EfficientNet-B3 food classifier")
    parser.add_argument("--epochs",  default=50,    type=int)
    parser.add_argument("--batch",   default=32,    type=int)
    parser.add_argument("--lr",      default=3e-4,  type=float)
    parser.add_argument("--device",  default="cpu")
    parser.add_argument("--imgsz",   default=300,   type=int)
    parser.add_argument("--workers", default=4,     type=int)
    parser.add_argument("--data",    default=str(DATA_DIR))
    args = parser.parse_args()

    train(
        data_dir=args.data,
        epochs=args.epochs,
        batch=args.batch,
        lr=args.lr,
        device_str=args.device,
        img_size=args.imgsz,
        workers=args.workers,
    )
